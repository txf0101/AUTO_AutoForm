/*
 * AutoForm Agent Console frontend.
 *
 * The page has four panels and one responsibility: collect the user's prompt,
 * collect request-scoped API settings, and display the Python runtime result.
 * AutoForm workflow decisions stay in `autoform_agent.agent_runtime`; the
 * browser only forwards a small JSON contract to the localhost HTTP bridge.
 */

const DEFAULT_ENDPOINT = "http://127.0.0.1:4317/api/agent";

const PROVIDER_PRESETS = {
  deepseek: {
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    apiMode: "chat_completions",
  },
  openai: {
    label: "OpenAI",
    baseUrl: "",
    model: "gpt-4.1-mini",
    apiMode: "responses",
  },
  custom: {
    label: "OpenAI-compatible",
    baseUrl: "",
    model: "gpt-4.1-mini",
    apiMode: "chat_completions",
  },
};

const appState = {
  conversationId: `web-${Date.now()}`,
  endpoint: DEFAULT_ENDPOINT,
  lastPayload: {},
  lastResponse: {},
  terminalLines: [
    "AutoForm Agent Console ready.",
    `Runtime endpoint: ${DEFAULT_ENDPOINT}`,
    "Provider preset: DeepSeek, chat_completions",
    "Waiting for prompt...",
  ],
  apiConfig: {
    provider: "deepseek",
    baseUrl: PROVIDER_PRESETS.deepseek.baseUrl,
    model: PROVIDER_PRESETS.deepseek.model,
    apiMode: PROVIDER_PRESETS.deepseek.apiMode,
    apiKey: "",
  },
  summary: {
    connection: "待发送",
    provider: "DeepSeek",
    model: PROVIDER_PRESETS.deepseek.model,
    apiMode: PROVIDER_PRESETS.deepseek.apiMode,
    tools: "待读取",
    queue: "待检查",
    sdk: "待检查",
    key: "未输入",
  },
  api: {
    sdk: "待检查",
    apiKey: "未输入",
    apiKeySource: "none",
    openaiCalled: "false",
    baseUrl: PROVIDER_PRESETS.deepseek.baseUrl,
  },
};

class AgentRuntimeBridge {
  constructor(state) {
    this.state = state;
  }

  async sendPrompt(prompt) {
    const runtimeConfig = buildRuntimeConfigForRequest();
    const payload = {
      conversationId: this.state.conversationId,
      prompt,
      runtimeConfig,
      uiContext: {
        surface: "four-panel-console",
        requestedPanels: ["input", "summary", "terminal", "api"],
      },
    };

    this.state.lastPayload = redactPayloadForDisplay(payload);
    renderApiPanel();
    appendTerminal(`USER> ${prompt}`);
    appendTerminal(
      `CONFIG provider=${runtimeConfig.provider} model=${runtimeConfig.model || "(provider default)"} api_mode=${runtimeConfig.apiMode} key=${runtimeConfig.apiKey ? "request" : "env-or-missing"}`,
    );
    appendTerminal(`POST ${this.state.endpoint}`);

    const startedAt = performance.now();
    const response = await fetch(this.state.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const elapsedMs = Math.round(performance.now() - startedAt);

    if (!response.ok) {
      throw new Error(`Agent runtime returned HTTP ${response.status}`);
    }

    const reply = await response.json();
    this.state.lastResponse = redactPayloadForDisplay(reply);
    applyRuntimeReply(reply, elapsedMs);
    return reply;
  }
}

const bridge = new AgentRuntimeBridge(appState);

/*
 * DOM bindings are intentionally grouped here.  When maintainers add a backend
 * response field later, they only need to touch this map and the matching
 * renderer instead of searching event handlers across the file.
 */
const elements = {
  promptForm: document.querySelector("[data-prompt-form]"),
  promptInput: document.querySelector("[data-prompt-input]"),
  insertExampleButton: document.querySelector("[data-insert-example]"),
  endpointInput: document.querySelector("[data-bridge-endpoint]"),
  sendButton: document.querySelector("[data-send-button]"),
  terminalOutput: document.querySelector("[data-terminal-output]"),
  summaryConnection: document.querySelector("[data-summary-connection]"),
  summaryProvider: document.querySelector("[data-summary-provider]"),
  summaryModel: document.querySelector("[data-summary-model]"),
  summaryApiMode: document.querySelector("[data-summary-api-mode]"),
  summaryTools: document.querySelector("[data-summary-tools]"),
  summaryQueue: document.querySelector("[data-summary-queue]"),
  summarySdk: document.querySelector("[data-summary-sdk]"),
  summaryKey: document.querySelector("[data-summary-key]"),
  providerSelect: document.querySelector("[data-provider-select]"),
  providerBaseUrl: document.querySelector("[data-provider-base-url]"),
  providerModel: document.querySelector("[data-provider-model]"),
  apiMode: document.querySelector("[data-api-mode]"),
  providerApiKey: document.querySelector("[data-provider-api-key]"),
  applyProviderPreset: document.querySelector("[data-apply-provider-preset]"),
  clearApiKey: document.querySelector("[data-clear-api-key]"),
  apiEndpoint: document.querySelector("[data-api-endpoint]"),
  apiSdk: document.querySelector("[data-api-sdk]"),
  apiKey: document.querySelector("[data-api-key]"),
  apiKeySource: document.querySelector("[data-api-key-source]"),
  apiOpenaiCalled: document.querySelector("[data-api-openai-called]"),
  apiBaseUrl: document.querySelector("[data-api-base-url]"),
  apiInput: document.querySelector("[data-api-input]"),
  apiResponse: document.querySelector("[data-api-response]"),
};

function applyRuntimeReply(reply, elapsedMs) {
  const runtime = reply.runtime || {};
  const metrics = reply.metrics || {};

  appState.summary = {
    connection: metrics.connection || "已返回",
    provider: metrics.provider || runtime.providerLabel || providerLabel(appState.apiConfig.provider),
    model: metrics.model || runtime.model || appState.apiConfig.model || "未返回",
    apiMode: metrics.apiMode || runtime.apiMode || appState.apiConfig.apiMode,
    tools: metrics.tools || "未返回",
    queue: metrics.queue || "未返回",
    sdk: booleanLabel(runtime.sdkAvailable),
    key: keyStatusLabel(runtime),
  };

  appState.api = {
    sdk: booleanLabel(runtime.sdkAvailable),
    apiKey: keyStatusLabel(runtime),
    apiKeySource: runtime.apiKeySource || (appState.apiConfig.apiKey ? "request" : "none"),
    openaiCalled: String(Boolean(runtime.openaiCalled)),
    baseUrl: runtime.baseUrl || metrics.baseUrl || appState.apiConfig.baseUrl || "OpenAI default",
  };

  appendTerminal(`HTTP 200 in ${elapsedMs} ms`);
  appendTerminal(
    `RUNTIME provider=${runtime.providerLabel || runtime.provider || "unknown"} model=${runtime.model || "unknown"} api_mode=${runtime.apiMode || "unknown"} base_url=${runtime.baseUrl || "OpenAI default"} sdk=${appState.api.sdk} key=${appState.api.apiKeySource} sdk_call=${appState.api.openaiCalled}`,
  );
  for (const step of reply.timeline || []) {
    appendTerminal(`STEP ${step.state}: ${step.title} - ${step.detail}`);
  }
  appendTerminal(`AGENT> ${reply.text || "(empty response)"}`);

  renderAll();
}

function buildRuntimeConfigForRequest() {
  syncApiConfigFromDom();
  const runtimeConfig = {
    provider: appState.apiConfig.provider,
    baseUrl: appState.apiConfig.baseUrl,
    model: appState.apiConfig.model,
    apiMode: appState.apiConfig.apiMode,
  };

  if (appState.apiConfig.apiKey) {
    runtimeConfig.apiKey = appState.apiConfig.apiKey;
  }
  return runtimeConfig;
}

function syncApiConfigFromDom() {
  appState.apiConfig = {
    provider: elements.providerSelect.value,
    baseUrl: elements.providerBaseUrl.value.trim(),
    model: elements.providerModel.value.trim(),
    apiMode: elements.apiMode.value,
    apiKey: elements.providerApiKey.value.trim(),
  };
}

function applyProviderPreset(force = false) {
  const provider = elements.providerSelect.value;
  const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.custom;

  if (force || !elements.providerBaseUrl.value.trim()) {
    elements.providerBaseUrl.value = preset.baseUrl;
  }
  if (force || !elements.providerModel.value.trim()) {
    elements.providerModel.value = preset.model;
  }
  if (force || elements.apiMode.value === "auto") {
    elements.apiMode.value = preset.apiMode;
  }

  syncApiConfigFromDom();
  appState.summary.provider = preset.label;
  appState.summary.model = appState.apiConfig.model || preset.model;
  appState.summary.apiMode = appState.apiConfig.apiMode;
  appState.api.baseUrl = appState.apiConfig.baseUrl || "OpenAI default";
  renderAll();
}

function appendTerminal(line) {
  const time = new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
  appState.terminalLines.push(`[${time}] ${line}`);
  if (appState.terminalLines.length > 180) {
    appState.terminalLines = appState.terminalLines.slice(-180);
  }
  renderTerminal();
}

function renderSummary() {
  elements.summaryConnection.textContent = appState.summary.connection;
  elements.summaryProvider.textContent = appState.summary.provider;
  elements.summaryModel.textContent = appState.summary.model;
  elements.summaryApiMode.textContent = appState.summary.apiMode;
  elements.summaryTools.textContent = appState.summary.tools;
  elements.summaryQueue.textContent = appState.summary.queue;
  elements.summarySdk.textContent = appState.summary.sdk;
  elements.summaryKey.textContent = appState.summary.key;
}

function renderTerminal() {
  elements.terminalOutput.textContent = appState.terminalLines.join("\n");
  elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
}

function renderApiPanel() {
  elements.apiEndpoint.textContent = appState.endpoint;
  elements.apiSdk.textContent = appState.api.sdk;
  elements.apiKey.textContent = appState.apiConfig.apiKey ? "页面会话 key 已输入" : appState.api.apiKey;
  elements.apiKeySource.textContent = appState.apiConfig.apiKey ? "request" : appState.api.apiKeySource;
  elements.apiOpenaiCalled.textContent = appState.api.openaiCalled;
  elements.apiBaseUrl.textContent = appState.apiConfig.baseUrl || appState.api.baseUrl || "OpenAI default";
  elements.apiInput.textContent = prettyJson(appState.lastPayload);
  elements.apiResponse.textContent = prettyJson(trimRuntimeResponse(appState.lastResponse));
}

function renderAll() {
  renderSummary();
  renderTerminal();
  renderApiPanel();
}

function applyStartupOptions() {
  const options = new URLSearchParams(window.location.search);
  const endpoint = options.get("endpoint");
  if (endpoint) {
    appState.endpoint = endpoint;
    elements.endpointInput.value = endpoint;
  }

  const provider = options.get("provider");
  if (provider && PROVIDER_PRESETS[provider]) {
    elements.providerSelect.value = provider;
    applyProviderPreset(true);
  }
}

function bindEvents() {
  elements.endpointInput.addEventListener("input", () => {
    appState.endpoint = elements.endpointInput.value.trim() || DEFAULT_ENDPOINT;
    renderApiPanel();
  });

  elements.providerSelect.addEventListener("change", () => {
    applyProviderPreset(true);
  });

  for (const input of [elements.providerBaseUrl, elements.providerModel, elements.apiMode, elements.providerApiKey]) {
    const eventName = input.tagName === "SELECT" ? "change" : "input";
    input.addEventListener(eventName, () => {
      syncApiConfigFromDom();
      appState.summary.provider = providerLabel(appState.apiConfig.provider);
      appState.summary.model = appState.apiConfig.model || "待配置";
      appState.summary.apiMode = appState.apiConfig.apiMode;
      appState.summary.key = appState.apiConfig.apiKey ? "页面会话 key 已输入" : "未输入";
      renderAll();
    });
  }

  elements.applyProviderPreset.addEventListener("click", () => {
    applyProviderPreset(true);
  });

  elements.clearApiKey.addEventListener("click", () => {
    elements.providerApiKey.value = "";
    syncApiConfigFromDom();
    appState.summary.key = "未输入";
    appState.api.apiKey = "未输入";
    appState.api.apiKeySource = "none";
    appendTerminal("INFO cleared page session API key");
    renderAll();
  });

  elements.insertExampleButton.addEventListener("click", () => {
    elements.promptInput.value = "请读取当前 AutoForm 安装和队列状态，并规划 kinematic check。";
    elements.promptInput.focus();
  });

  elements.promptForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = elements.promptInput.value.trim();
    if (!prompt) {
      appendTerminal("WARN empty prompt ignored");
      return;
    }

    elements.sendButton.disabled = true;
    elements.sendButton.textContent = "发送中";

    try {
      await bridge.sendPrompt(prompt);
    } catch (error) {
      appState.summary.connection = "请求失败";
      appendTerminal(`ERROR ${error.message}`);
      renderSummary();
    } finally {
      elements.sendButton.disabled = false;
      elements.sendButton.textContent = "发送";
    }
  });
}

function trimRuntimeResponse(reply) {
  if (!reply || Object.keys(reply).length === 0) {
    return {};
  }
  return {
    role: reply.role,
    text: reply.text,
    metrics: reply.metrics,
    runtime: reply.runtime,
    preview: reply.preview,
  };
}

function redactPayloadForDisplay(value) {
  if (Array.isArray(value)) {
    return value.map((item) => redactPayloadForDisplay(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        /apiKey|api_key|OPENAI_API_KEY/i.test(key) && item ? "[redacted]" : redactPayloadForDisplay(item),
      ]),
    );
  }
  return value;
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2);
}

function booleanLabel(value) {
  if (value === true) {
    return "true";
  }
  if (value === false) {
    return "false";
  }
  return "待检查";
}

function keyStatusLabel(runtime) {
  if (runtime.apiKeyConfigured === true) {
    return runtime.apiKeySource === "request" ? "页面会话 key 已输入" : "后端环境已配置";
  }
  if (appState.apiConfig.apiKey) {
    return "页面会话 key 已输入";
  }
  return "未输入";
}

function providerLabel(provider) {
  return (PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.custom).label;
}

applyStartupOptions();
bindEvents();
renderAll();
