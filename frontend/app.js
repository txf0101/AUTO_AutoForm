/*
 * AutoForm Agent Runtime Console frontend.
 *
 * This file is written as plain browser JavaScript so the project can be opened
 * in VSCode without a build step.  The code is split into clear sections:
 * state, bridge adapter, render functions, event handlers and initialization.
 * A future React/Vue/Svelte rewrite can preserve the same state shape and bridge
 * methods, which keeps the long-term migration path straightforward.
 */

/**
 * Central application state.
 *
 * The UI is rendered from this object.  The production prompt path runs through
 * the OpenAI Agents SDK capable Python runtime outside the browser.  This page
 * only forwards prompts and mirrors preview data returned by the HTTP bridge,
 * then calls render functions from one explicit state object so new developers
 * can follow every screen update.
 */
const appState = {
  activeConversationId: "conv-1",
  bridgeMode: "mock",
  bridgeEndpoint: "http://127.0.0.1:4317/codex",
  conversations: [
    {
      id: "conv-1",
      title: "AutoForm 初始对话",
      createdAt: new Date().toISOString(),
      messages: [
        {
          role: "system",
          text: "已建立本地演示会话。发送 prompt 后，页面会把文本交给 Python 后端运行时，并展示返回的操作流预览。",
          time: new Date().toISOString(),
        },
      ],
    },
  ],
  timeline: [
    {
      id: "step-discover",
      title: "发现 AutoForm 安装",
      detail: "读取注册表、安装目录和 ProgramData",
      state: "ready",
    },
    {
      id: "step-parse",
      title: "读取工程摘要",
      detail: "解析 .afd 可读片段和 QuickLink 数据",
      state: "ready",
    },
    {
      id: "step-solver",
      title: "执行求解检查",
      detail: "计划 AFFormingSolver kinematic check",
      state: "ready",
    },
  ],
  preview: {
    phase: "Idle",
    title: "等待任务",
    subtitle: "发送 prompt 后会显示后端运行时阶段",
    solver: "待执行",
    solverDetail: "准备 kinematic check",
    activeTool: "无活动工具",
  },
};

/**
 * AgentRuntimeBridge is the only place that knows how prompts leave the browser.
 *
 * Current limitation:
 * A static web page cannot run OpenAI Agents SDK or AutoForm tools directly.
 * The mock implementation keeps the visual workflow inspectable, and the HTTP
 * branch talks to `autoform_agent.http_bridge`, which delegates to the Python
 * `autoform_agent.agent_runtime` module.
 */
class AgentRuntimeBridge {
  constructor(state) {
    this.state = state;
  }

  /**
   * Create a frontend conversation for the visual shell.
   *
   * The production agent session is managed by Python, not by browser
   * JavaScript.  Keeping this method local avoids mixing UI state with runtime
   * process lifecycle.
   */
  createConversation() {
    const nextIndex = this.state.conversations.length + 1;
    const conversation = {
      id: `conv-${Date.now()}`,
      title: `AutoForm 对话 ${nextIndex}`,
      createdAt: new Date().toISOString(),
      codexConversationId: null,
      messages: [
        {
          role: "system",
          text: "已在前端创建新对话。这里只维护页面状态；后端 Agent runtime 负责理解 prompt 和选择工具。",
          time: new Date().toISOString(),
        },
      ],
    };

    this.state.conversations.unshift(conversation);
    this.state.activeConversationId = conversation.id;
    return conversation;
  }

  /**
   * Send a prompt through the page-level bridge.
   *
   * The `mock` branch simulates a useful response and MCP progress.  The `http`
   * branch sends the prompt to the local HTTP bridge.  The HTTP bridge delegates
   * to Python runtime code, so the frontend does not decide which AutoForm tool
   * should run.
   */
  async sendPrompt(prompt) {
    if (this.state.bridgeMode === "http") {
      return this.sendPromptToHttpAdapter(prompt);
    }

    await wait(450);
    simulateToolProgress("autoform_discover_installation", "running");
    await wait(550);
    simulateToolProgress("autoform_get_afd_project_summary", "running");
    await wait(550);
    simulateToolProgress("autoform_forming_solver_kinematic_plan", "complete");

    return {
      role: "assistant",
      text:
        "我会先发现 AutoForm 安装，再读取当前 AFD 工程摘要，并生成 kinematic check 计划。" +
        "当前演示模式已经把这些动作映射到后端操作流；真实运行时会由 autoform_agent.agent_runtime 接管 prompt。",
      time: new Date().toISOString(),
    };
  }

  async sendPromptToHttpAdapter(prompt) {
    const response = await fetch(this.state.bridgeEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversationId: this.state.activeConversationId,
        prompt,
        uiContext: {
          project: "Solver_R13.afd",
          activeTool: this.state.preview.activeTool,
        },
      }),
    });

    if (!response.ok) {
      throw new Error(`Agent runtime adapter returned HTTP ${response.status}`);
    }

    const reply = await response.json();
    applyBridgeStatus(reply);
    return reply;
  }
}

const bridge = new AgentRuntimeBridge(appState);

const elements = {
  conversationList: document.querySelector("[data-conversation-list]"),
  conversationCount: document.querySelector("[data-conversation-count]"),
  activeConversationTitle: document.querySelector("[data-active-conversation-title]"),
  messageList: document.querySelector("[data-message-list]"),
  promptForm: document.querySelector("[data-prompt-form]"),
  promptInput: document.querySelector("[data-prompt-input]"),
  newConversationButton: document.querySelector("[data-new-conversation]"),
  insertExampleButton: document.querySelector("[data-insert-example]"),
  runDemoButton: document.querySelector("[data-run-demo]"),
  resetDemoButton: document.querySelector("[data-reset-demo]"),
  bridgeMode: document.querySelector("[data-bridge-mode]"),
  bridgeEndpoint: document.querySelector("[data-bridge-endpoint]"),
  timeline: document.querySelector("[data-timeline]"),
  activeTool: document.querySelector("[data-active-tool]"),
  previewPhase: document.querySelector("[data-preview-phase]"),
  previewTitle: document.querySelector("[data-preview-title]"),
  previewSubtitle: document.querySelector("[data-preview-subtitle]"),
  metricConnection: document.querySelector("[data-metric-connection]"),
  metricTools: document.querySelector("[data-metric-tools]"),
  metricQueue: document.querySelector("[data-metric-queue]"),
  metricSolver: document.querySelector("[data-metric-solver]"),
  metricSolverDetail: document.querySelector("[data-metric-solver-detail]"),
};

function getActiveConversation() {
  return appState.conversations.find((item) => item.id === appState.activeConversationId);
}

function addMessage(role, text) {
  const conversation = getActiveConversation();
  conversation.messages.push({ role, text, time: new Date().toISOString() });
  renderMessages();
}

/**
 * Apply status data returned by the local HTTP adapter.
 *
 * The adapter is allowed to return only a chat message, but when it also sends
 * timeline, preview, or metric fields the page reflects that server state. This
 * keeps the frontend contract small while still proving that the browser is
 * receiving live data from Python rather than replaying the mock flow.
 */
function applyBridgeStatus(reply) {
  if (Array.isArray(reply.timeline)) {
    const updatesById = new Map(reply.timeline.map((item) => [item.id, item]));
    appState.timeline = appState.timeline.map((item) => ({
      ...item,
      ...(updatesById.get(item.id) || {}),
    }));
  }

  if (reply.preview && typeof reply.preview === "object") {
    appState.preview = {
      ...appState.preview,
      ...reply.preview,
    };
  }

  renderTimeline();
  renderPreview();

  if (reply.metrics && typeof reply.metrics === "object") {
    if (reply.metrics.connection) {
      elements.metricConnection.textContent = reply.metrics.connection;
    }
    if (reply.metrics.tools && elements.metricTools) {
      elements.metricTools.textContent = reply.metrics.tools;
    }
    if (reply.metrics.queue && elements.metricQueue) {
      elements.metricQueue.textContent = reply.metrics.queue;
    }
  }
}

function renderConversations() {
  elements.conversationCount.textContent = String(appState.conversations.length);
  elements.conversationList.innerHTML = "";

  for (const conversation of appState.conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation-item";
    button.setAttribute("aria-current", String(conversation.id === appState.activeConversationId));
    button.dataset.conversationId = conversation.id;
    button.innerHTML = `
      <strong>${escapeHtml(conversation.title)}</strong>
      <span>${conversation.messages.length} 条消息</span>
    `;
    elements.conversationList.appendChild(button);
  }
}

function renderMessages() {
  const conversation = getActiveConversation();
  elements.activeConversationTitle.textContent = conversation.title;
  elements.messageList.innerHTML = "";

  for (const message of conversation.messages) {
    const item = document.createElement("article");
    item.className = `message message-${message.role}`;
    item.innerHTML = `
      <span class="message-meta">${roleLabel(message.role)} · ${formatTime(message.time)}</span>
      ${escapeHtml(message.text)}
    `;
    elements.messageList.appendChild(item);
  }

  elements.messageList.scrollTop = elements.messageList.scrollHeight;
  renderConversations();
}

function renderTimeline() {
  elements.timeline.innerHTML = "";

  for (const item of appState.timeline) {
    const row = document.createElement("li");
    row.className = "timeline-item";
    row.innerHTML = `
      <span class="timeline-icon">${timelineIcon(item.state)}</span>
      <div>
        <p>${escapeHtml(item.title)}</p>
        <small>${escapeHtml(item.detail)}</small>
      </div>
      <span class="timeline-state">${stateLabel(item.state)}</span>
    `;
    elements.timeline.appendChild(row);
  }
}

function renderPreview() {
  const preview = appState.preview;
  elements.activeTool.textContent = preview.activeTool;
  elements.previewPhase.textContent = preview.phase;
  elements.previewTitle.textContent = preview.title;
  elements.previewSubtitle.textContent = preview.subtitle;
  elements.metricSolver.textContent = preview.solver;
  elements.metricSolverDetail.textContent = preview.solverDetail;
  elements.metricConnection.textContent = appState.bridgeMode === "mock" ? "页面演示" : "HTTP 待确认";
}

function renderAll() {
  renderConversations();
  renderMessages();
  renderTimeline();
  renderPreview();
}

/**
 * Read startup options from the page URL.
 *
 * The launcher opens `index.html?bridge=http` after starting the local bridge.
 * This function applies that setting to both the state object and the visible
 * `<select>`, so users do not need to manually switch away from demo mode.
 */
function applyStartupOptions() {
  const options = new URLSearchParams(window.location.search);
  const bridgeMode = options.get("bridge");
  const bridgeEndpoint = options.get("endpoint");

  if (bridgeMode === "http" || bridgeMode === "mock") {
    appState.bridgeMode = bridgeMode;
    elements.bridgeMode.value = bridgeMode;
  }

  if (bridgeEndpoint) {
    appState.bridgeEndpoint = bridgeEndpoint;
    elements.bridgeEndpoint.value = bridgeEndpoint;
  }
}

function resetDemoState() {
  appState.timeline = appState.timeline.map((item) => ({ ...item, state: "ready" }));
  appState.preview = {
    phase: "Idle",
    title: "等待任务",
    subtitle: "发送 prompt 后会显示 MCP 预览阶段",
    solver: "待执行",
    solverDetail: "准备 kinematic check",
    activeTool: "无活动工具",
  };
  renderTimeline();
  renderPreview();
}

function simulateToolProgress(toolName, finalState) {
  const toolToStep = {
    autoform_discover_installation: "step-discover",
    autoform_get_afd_project_summary: "step-parse",
    autoform_forming_solver_kinematic_plan: "step-solver",
  };

  const targetStep = toolToStep[toolName];
  appState.timeline = appState.timeline.map((item) => {
    if (item.id !== targetStep) {
      return item;
    }
    return { ...item, state: finalState };
  });

  appState.preview = {
    phase: finalState === "complete" ? "Plan Ready" : "Running",
    title: toolName,
    subtitle: finalState === "complete" ? "已生成可检查的后端操作计划" : "页面正在等待后端运行时状态",
    solver: finalState === "complete" ? "计划完成" : "处理中",
    solverDetail: finalState === "complete" ? "等待真实执行确认" : "正在更新操作流",
    activeTool: toolName,
  };

  renderTimeline();
  renderPreview();
}

function bindEvents() {
  elements.newConversationButton.addEventListener("click", () => {
    bridge.createConversation();
    resetDemoState();
    renderAll();
  });

  elements.conversationList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-conversation-id]");
    if (!button) {
      return;
    }
    appState.activeConversationId = button.dataset.conversationId;
    renderAll();
  });

  elements.bridgeMode.addEventListener("change", () => {
    appState.bridgeMode = elements.bridgeMode.value;
    renderPreview();
  });

  elements.bridgeEndpoint.addEventListener("input", () => {
    appState.bridgeEndpoint = elements.bridgeEndpoint.value.trim();
  });

  elements.insertExampleButton.addEventListener("click", () => {
    elements.promptInput.value =
      "请读取当前 AutoForm 工程摘要，规划一次 kinematic check，并把 MCP 工具调用步骤显示在软件预览界面。";
    elements.promptInput.focus();
  });

  elements.runDemoButton.addEventListener("click", async () => {
    resetDemoState();
    addMessage("user", "运行一次 AutoForm MCP 示例流程。");
    const reply = await bridge.sendPrompt("运行一次 AutoForm MCP 示例流程。");
    addMessage(reply.role, reply.text);
  });

  elements.resetDemoButton.addEventListener("click", resetDemoState);

  elements.promptForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = elements.promptInput.value.trim();
    if (!prompt) {
      return;
    }

    elements.promptInput.value = "";
    addMessage("user", prompt);

    try {
      const reply = await bridge.sendPrompt(prompt);
      addMessage(reply.role || "assistant", reply.text || "Codex 返回了空响应。");
    } catch (error) {
      addMessage("assistant", `发送失败：${error.message}`);
    }
  });
}

function roleLabel(role) {
  return {
    user: "你",
    assistant: "Agent",
    system: "系统",
  }[role] || role;
}

function stateLabel(state) {
  return {
    ready: "就绪",
    running: "运行中",
    complete: "完成",
  }[state] || state;
}

function timelineIcon(state) {
  return {
    ready: "·",
    running: "…",
    complete: "✓",
  }[state] || "·";
}

function formatTime(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

applyStartupOptions();
bindEvents();
renderAll();
