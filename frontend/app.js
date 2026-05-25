/*
 * AutoForm Agent Console frontend.
 *
 * The page is deliberately small: user input, status summary, terminal-like
 * output, and API request/usage details.  AutoForm workflow control lives in
 * Python (`autoform_agent.agent_runtime`), so this file only forwards prompt
 * payloads and renders backend facts.
 */

const appState = {
  conversationId: `web-${Date.now()}`,
  endpoint: "http://127.0.0.1:4317/codex",
  lastPayload: {},
  lastResponse: {},
  terminalLines: [
    "AutoForm Agent Console ready.",
    "Runtime endpoint: http://127.0.0.1:4317/codex",
    "Waiting for prompt...",
  ],
  summary: {
    connection: "待发送",
    runtime: "AutoForm Agent Runtime",
    model: "gpt-4.1-mini",
    tools: "待读取",
    queue: "待检查",
    openai: "未调用",
  },
  api: {
    sdk: "待检查",
    apiKey: "待检查",
    openaiCalled: "false",
  },
};

class AgentRuntimeBridge {
  constructor(state) {
    this.state = state;
  }

  async sendPrompt(prompt) {
    const payload = {
      conversationId: this.state.conversationId,
      prompt,
      uiContext: {
        surface: "four-panel-console",
        requestedPanels: ["input", "summary", "terminal", "api"],
      },
    };
    this.state.lastPayload = payload;
    renderApiPanel();
    appendTerminal(`USER> ${prompt}`);
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
    this.state.lastResponse = reply;
    applyRuntimeReply(reply, elapsedMs);
    return reply;
  }
}

const bridge = new AgentRuntimeBridge(appState);

/*
 * DOM bindings stay flat because the page has only four panels.  Each renderer
 * below owns one panel, which keeps later backend contract changes easy to
 * audit for developers who are new to the frontend.
 */
const elements = {
  promptForm: document.querySelector("[data-prompt-form]"),
  promptInput: document.querySelector("[data-prompt-input]"),
  insertExampleButton: document.querySelector("[data-insert-example]"),
  endpointInput: document.querySelector("[data-bridge-endpoint]"),
  sendButton: document.querySelector("[data-send-button]"),
  terminalOutput: document.querySelector("[data-terminal-output]"),
  summaryConnection: document.querySelector("[data-summary-connection]"),
  summaryRuntime: document.querySelector("[data-summary-runtime]"),
  summaryModel: document.querySelector("[data-summary-model]"),
  summaryTools: document.querySelector("[data-summary-tools]"),
  summaryQueue: document.querySelector("[data-summary-queue]"),
  summaryOpenai: document.querySelector("[data-summary-openai]"),
  apiEndpoint: document.querySelector("[data-api-endpoint]"),
  apiSdk: document.querySelector("[data-api-sdk]"),
  apiKey: document.querySelector("[data-api-key]"),
  apiOpenaiCalled: document.querySelector("[data-api-openai-called]"),
  apiInput: document.querySelector("[data-api-input]"),
  apiResponse: document.querySelector("[data-api-response]"),
};

function applyRuntimeReply(reply, elapsedMs) {
  const runtime = reply.runtime || {};
  const metrics = reply.metrics || {};

  appState.summary = {
    connection: metrics.connection || "已返回",
    runtime: runtime.name || "autoform-agent-runtime",
    model: metrics.model || runtime.model || "未返回",
    tools: metrics.tools || "未返回",
    queue: metrics.queue || "未返回",
    openai: runtime.openaiCalled ? "已调用" : "未调用",
  };

  appState.api = {
    sdk: booleanLabel(runtime.sdkAvailable),
    apiKey: booleanLabel(runtime.apiKeyConfigured),
    openaiCalled: String(Boolean(runtime.openaiCalled)),
  };

  appendTerminal(`HTTP 200 in ${elapsedMs} ms`);
  appendTerminal(
    `RUNTIME provider=${runtime.provider || "unknown"} model=${runtime.model || "unknown"} sdk=${appState.api.sdk} api_key=${appState.api.apiKey} openai_called=${appState.api.openaiCalled}`,
  );
  for (const step of reply.timeline || []) {
    appendTerminal(`STEP ${step.state}: ${step.title} - ${step.detail}`);
  }
  appendTerminal(`AGENT> ${reply.text || "(empty response)"}`);

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
  elements.summaryRuntime.textContent = appState.summary.runtime;
  elements.summaryModel.textContent = appState.summary.model;
  elements.summaryTools.textContent = appState.summary.tools;
  elements.summaryQueue.textContent = appState.summary.queue;
  elements.summaryOpenai.textContent = appState.summary.openai;
}

function renderTerminal() {
  elements.terminalOutput.textContent = appState.terminalLines.join("\n");
  elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
}

function renderApiPanel() {
  elements.apiEndpoint.textContent = appState.endpoint;
  elements.apiSdk.textContent = appState.api.sdk;
  elements.apiKey.textContent = appState.api.apiKey;
  elements.apiOpenaiCalled.textContent = appState.api.openaiCalled;
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
}

function bindEvents() {
  elements.endpointInput.addEventListener("input", () => {
    appState.endpoint = elements.endpointInput.value.trim();
    renderApiPanel();
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

applyStartupOptions();
bindEvents();
renderAll();
