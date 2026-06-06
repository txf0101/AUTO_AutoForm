/*
这个脚本驱动本地网页界面：读取用户输入，调用 HTTP bridge，展示状态、事件、图谱、证据和错误信息。读它时可以从页面按钮开始找，再顺着 fetch 请求看后端返回如何被渲染。

This script drives the local web interface: it reads user input, calls the HTTP bridge, and renders status, events, graphs, evidence, and errors. Start from the page buttons, then follow the fetch calls to see how backend responses are displayed.
*/

/*
 * AutoForm P0 Workbench frontend.
 *
 * R3 uses typed RunEvent fixtures before any live multi-agent backend is
 * connected. The original HTTP bridge path is kept for one-off runtime calls.
 */

const DEFAULT_ENDPOINT = "http://127.0.0.1:4317/api/agent";
const DEFAULT_FIXTURE_URL = "../fixtures/run_events_demo.jsonl";

const PROVIDER_PRESETS = {
  deepseek: {
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    apiMode: "chat_completions",
  },
  custom: {
    label: "Chat completions compatible",
    baseUrl: "",
    model: "deepseek-v4-flash",
    apiMode: "chat_completions",
  },
};

const DEFAULT_AGENTS = [
  "center_agent",
  "demand_process_planning_agent",
  "geometry_data_agent",
  "material_agent",
  "process_setting_agent",
  "solver_execution_agent",
  "postprocessing_agent",
  "diagnosis_optimization_agent",
  "report_collation_agent",
];

// The graph is a business view, not a raw debug dump of backend role IDs.
// These nine nodes match the Agent development documents. Internal nodes such
// as User, UI, Runtime, Gateway, manager, solver, and result_review are mapped
// below so old events still animate the correct business square.
const AGENT_LABELS = {
  center_agent: "中心Agent",
  demand_process_planning_agent: "需求与工艺规划Agent",
  geometry_data_agent: "几何与数据Agent",
  material_agent: "材料Agent",
  process_setting_agent: "工艺设置Agent",
  solver_execution_agent: "求解执行Agent",
  postprocessing_agent: "后处理Agent",
  diagnosis_optimization_agent: "诊断与优化Agent",
  report_collation_agent: "报告整理Agent",
};

const AGENT_NODE_ALIASES = {
  manager: "center_agent",
  ui_workbench: "center_agent",
  runtime_executor: "center_agent",
  user: "",
  human_reviewer: "center_agent",
  validator: "center_agent",
  mcp_gateway: "center_agent",
  demand_triage_agent: "demand_process_planning_agent",
  rag_evidence_agent: "demand_process_planning_agent",
  process_planning_agent: "demand_process_planning_agent",
  quicklink: "geometry_data_agent",
  materials: "material_agent",
  project_workflow: "process_setting_agent",
  script_agent: "process_setting_agent",
  autoform_adapter: "process_setting_agent",
  solver: "solver_execution_agent",
  result_review: "postprocessing_agent",
  installation: "diagnosis_optimization_agent",
  reporting: "report_collation_agent",
};

// Visual rule: green means "working right now". Finished states are normalized
// back to idle so completed work does not look active in the graph.
const AGENT_STATE_LABELS = {
  idle: "待命",
  planned: "待命",
  running: "工作中",
  done: "待命",
  complete: "待命",
  completed: "待命",
  ready: "待命",
  blocked: "阻断",
  failed: "失败",
  waiting_for_human: "待批准",
};

const appState = {
  conversationId: `web-${Date.now()}`,
  endpoint: DEFAULT_ENDPOINT,
  fixtureUrl: DEFAULT_FIXTURE_URL,
  lastPayload: {},
  lastResponse: {},
  replayEvents: [],
  replayIndex: 0,
  replayLoaded: false,
  replayStatus: "fixture idle",
  terminalLines: [
    "AutoForm P0 Workbench ready.",
    "Replay fixture: built-in demo",
    `Local bridge: ${DEFAULT_ENDPOINT}`,
  ],
  apiConfig: {
    provider: "deepseek",
    baseUrl: PROVIDER_PRESETS.deepseek.baseUrl,
    model: PROVIDER_PRESETS.deepseek.model,
    apiMode: PROVIDER_PRESETS.deepseek.apiMode,
    apiKey: "",
  },
  localExecution: {
    enabled: false,
    scope: "mcp_gateway",
    projectOperation: "new_project",
    exampleName: "",
  },
  summary: {
    run: "未加载",
    task: "未创建",
    stage: "P0",
    route: "待定",
    evidence: 0,
    patch: 0,
    key: "未输入",
    token: 0,
  },
  api: {
    runtime: "待检查",
    apiKey: "未输入",
    apiKeySource: "none",
    apiKeyFingerprint: "none",
    directApiCalled: "false",
    baseUrl: PROVIDER_PRESETS.deepseek.baseUrl,
  },
  graph: {
    nodes: Object.fromEntries(DEFAULT_AGENTS.map((agentId) => [agentId, "idle"])),
    edges: [],
  },
  usage: {
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
    total_tokens: 0,
  },
  agentMessages: [],
  currentTurnMessageKeys: new Set(),
  conversationContext: {},
};

class AgentRuntimeBridge {
  constructor(state) {
    this.state = state;
  }

  async sendPrompt(prompt, options = {}) {
    const runtimeConfig = buildRuntimeConfigForRequest(options);
    const localExecution = buildLocalExecutionContext();
    const payload = {
      conversationId: this.state.conversationId,
      prompt,
      runtimeConfig,
      uiContext: {
        surface: "p0-run-event-workbench",
        requestedPanels: ["input", "summary", "graph", "terminal", "credentials", "usage"],
        localExecution,
      },
    };
    const conversationContext = buildConversationContextForRequest();
    if (conversationContext) {
      payload.conversationContext = conversationContext;
    }
    if (localExecution.approved) {
      payload.agentToolExecutionApproved = true;
    }

    this.state.lastPayload = redactPayloadForDisplay(payload);
    this.state.currentTurnMessageKeys = new Set();
    appendUserMessage(prompt);
    renderApiPanel();
    appendTerminal(`USER> ${prompt}`);
    appendTerminal(
      `CONFIG provider=${runtimeConfig.provider} model=${runtimeConfig.model || "(provider default)"} api_mode=${runtimeConfig.apiMode} key=${runtimeConfig.apiKey ? "request" : "env-or-missing"}`,
    );
    appendTerminal(
      `LOCAL execution=${localExecution.approved ? "approved" : "disabled"} mcp_control=${localExecution.approved ? "approved" : "blocked"} scope=${localExecution.scope} project_operation=${localExecution.projectOperation} example_hint=${localExecution.exampleName || "none"} mode=${localExecution.mode}`,
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
    updateConversationContextFromReply(reply);
    return reply;
  }
}

const bridge = new AgentRuntimeBridge(appState);

/*
 * Centralized DOM bindings keep the fixture replay and HTTP bridge path aligned.
 * Tests assert these markers so future UI edits cannot silently drop a panel.
 */
const elements = {
  replayStatus: document.querySelector("[data-replay-status]"),
  promptForm: document.querySelector("[data-prompt-form]"),
  promptInput: document.querySelector("[data-prompt-input]"),
  insertExampleButton: document.querySelector("[data-insert-example]"),
  stepReplayButton: document.querySelector("[data-step-replay]"),
  runReplayButton: document.querySelector("[data-run-replay]"),
  resetReplayButton: document.querySelector("[data-reset-replay]"),
  sendButton: document.querySelector("[data-send-button]"),
  terminalOutput: document.querySelector("[data-terminal-output]"),
  agentDialog: document.querySelector("[data-agent-dialog]"),
  summaryRun: document.querySelector("[data-summary-run]"),
  summaryTask: document.querySelector("[data-summary-task]"),
  summaryStage: document.querySelector("[data-summary-stage]"),
  summaryRoute: document.querySelector("[data-summary-route]"),
  summaryEvidence: document.querySelector("[data-summary-evidence]"),
  summaryPatch: document.querySelector("[data-summary-patch]"),
  summaryKey: document.querySelector("[data-summary-key]"),
  summaryToken: document.querySelector("[data-summary-token]"),
  agentGraph: document.querySelector("[data-agent-graph]"),
  edgeList: document.querySelector("[data-edge-list]"),
  providerSelect: document.querySelector("[data-provider-select]"),
  providerBaseUrl: document.querySelector("[data-provider-base-url]"),
  providerModel: document.querySelector("[data-provider-model]"),
  apiMode: document.querySelector("[data-api-mode]"),
  providerApiKey: document.querySelector("[data-provider-api-key]"),
  localExecution: document.querySelector("[data-local-execution]"),
  demoExample: document.querySelector("[data-demo-example]"),
  applyProviderPreset: document.querySelector("[data-apply-provider-preset]"),
  testConnectionButton: document.querySelector("[data-test-connection]"),
  clearApiKey: document.querySelector("[data-clear-api-key]"),
  apiEndpoint: document.querySelector("[data-api-endpoint]"),
  apiRuntime: document.querySelector("[data-api-runtime]"),
  apiKey: document.querySelector("[data-api-key]"),
  apiKeySource: document.querySelector("[data-api-key-source]"),
  apiKeyFingerprint: document.querySelector("[data-api-key-fingerprint]"),
  apiDirectCalled: document.querySelector("[data-api-direct-called]"),
  apiBaseUrl: document.querySelector("[data-api-base-url]"),
  apiInput: document.querySelector("[data-api-input]"),
  apiResponse: document.querySelector("[data-api-response]"),
  usageInput: document.querySelector("[data-usage-input]"),
  usageOutput: document.querySelector("[data-usage-output]"),
  usageCached: document.querySelector("[data-usage-cached]"),
  usageTotal: document.querySelector("[data-usage-total]"),
};

async function loadFixtureFromInput() {
  try {
    const response = await fetch(appState.fixtureUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`fixture returned HTTP ${response.status}`);
    }
    const events = parseJsonl(await response.text());
    if (!events.length) {
      throw new Error("fixture has no events");
    }
    appState.replayEvents = events;
    appState.replayLoaded = true;
    resetReplayState(false);
    appState.replayStatus = `loaded ${events.length} events`;
    appendTerminal(`FIXTURE loaded ${events.length} events from ${appState.fixtureUrl}`);
  } catch (error) {
    appState.replayStatus = "fixture load failed";
    appendTerminal(`ERROR fixture load failed: ${error.message}`);
  } finally {
    renderAll();
  }
}

function parseJsonl(source) {
  return source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function resetReplayState(writeLog = true) {
  appState.replayIndex = 0;
  appState.summary = {
    run: appState.replayEvents[0]?.run_id || "未加载",
    task: "未创建",
    stage: "P0",
    route: "待定",
    evidence: 0,
    patch: 0,
    key: appState.apiConfig.apiKey ? "页面会话 key 已输入" : "未输入",
    token: 0,
  };
  appState.graph = {
    nodes: Object.fromEntries(DEFAULT_AGENTS.map((agentId) => [agentId, "idle"])),
    edges: [],
  };
  appState.usage = {
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
    total_tokens: 0,
  };
  appState.agentMessages = [];
  appState.currentTurnMessageKeys = new Set();
  appState.lastResponse = {};
  if (writeLog) {
    appendTerminal("REPLAY reset");
  }
  renderAll();
}

function stepReplay() {
  if (!appState.replayLoaded || appState.replayIndex >= appState.replayEvents.length) {
    return;
  }
  const event = appState.replayEvents[appState.replayIndex];
  appState.replayIndex += 1;
  applyRunEvent(event);
  appState.replayStatus =
    appState.replayIndex === appState.replayEvents.length
      ? `complete ${appState.replayIndex}/${appState.replayEvents.length}`
      : `event ${appState.replayIndex}/${appState.replayEvents.length}`;
  renderAll();
}

function runReplayToEnd() {
  while (appState.replayLoaded && appState.replayIndex < appState.replayEvents.length) {
    stepReplay();
  }
}

function applyRunEvent(event, options = {}) {
  const payload = event.payload || {};

  appState.summary.run = event.run_id;
  if (payload.task_id) {
    appState.summary.task = payload.task_id;
  }

  switch (event.type) {
    case "run_started":
      appState.summary.stage = payload.phase || payload.state || appState.summary.stage;
      appendTerminal(`RUN ${payload.run_id || event.run_id} ${payload.state || "started"}`);
      break;
    case "user_input_received":
      appendTerminal(`EVENT user_input_received ${payload.prompt_summary || ""}`.trim());
      break;
    case "task_card_created":
      appState.summary.task = payload.task_id;
      appState.summary.stage = payload.phase || appState.summary.stage;
      appState.summary.route = payload.task_type || appState.summary.route;
      appendTerminal(`TASK ${payload.task_id} ${payload.task_type} risk=${payload.risk_level}`);
      break;
    case "route_decision":
      if (Array.isArray(payload.route)) {
        for (const roleId of payload.route) {
          markAgent(roleId, "planned");
        }
        for (let index = 0; index < payload.route.length - 1; index += 1) {
          addEdge(`route_${index}_${payload.route[index]}_${payload.route[index + 1]}`, payload.route[index], payload.route[index + 1], "transferring");
        }
      }
      appState.summary.route = (payload.route || []).map(agentLabel).join(" -> ");
      appendTerminal(`ROUTE ${appState.summary.route}`);
      break;
    case "context_view_built":
      appendTerminal(
        `CONTEXT roles=${(payload.selected_role_ids || []).length} gateway_tools=${(payload.allowed_gateway_tools || []).length}`,
      );
      break;
    case "agent_node_started":
      markAgent(payload.agent_id || event.source_agent, payload.state || "running");
      appendTerminal(`NODE ${payload.agent_id || event.source_agent} ${payload.state || "running"}`);
      break;
    case "agent_planned":
      markAgent(payload.role_id || event.target_agent, "planned");
      appendTerminal(`NODE ${payload.role_id || event.target_agent} planned`);
      break;
    case "agent_started":
      markAgent(payload.role_id || event.target_agent, "running");
      appendTerminal(`NODE ${payload.role_id || event.target_agent} running`);
      break;
    case "agent_delta":
      markAgent(payload.role_id || event.source_agent, "running");
      appendTerminal(`DELTA ${payload.role_id || event.source_agent}: ${payload.summary || ""}`.trim());
      break;
    case "agent_completed":
      markAgent(payload.role_id || event.source_agent, "done");
      appendTerminal(`NODE ${payload.role_id || event.source_agent} completed`);
      break;
    case "agent_blocked":
      markAgent(payload.role_id || event.target_agent, "blocked");
      appendTerminal(`NODE ${payload.role_id || event.target_agent} blocked ${payload.reason || ""}`.trim());
      break;
    case "agent_edge_transfer":
      addEdge(payload.edge_id || `${event.source_agent}->${event.target_agent}`, event.source_agent, event.target_agent, payload.state || "transferring");
      appendTerminal(`EDGE ${event.source_agent} -> ${event.target_agent} ${payload.state || "transferring"}`);
      break;
    case "edge_transfer":
      addEdge(
        payload.edge_id || `${event.source_agent}->${event.target_agent}`,
        event.source_agent,
        event.target_agent,
        payload.status || payload.state || "transferring",
      );
      appendTerminal(`EDGE ${event.source_agent} -> ${event.target_agent} ${payload.status || payload.state || "transferring"}`);
      break;
    case "tool_requested":
      markAgent(event.source_agent, "running");
      markAgent(event.target_agent, "running");
      addEdge(`tool_${payload.node_id || event.event_id}_${payload.sequence || 1}`, event.source_agent, event.target_agent, "transferring");
      appendTerminal(`TOOL request ${payload.tool} by ${payload.role_id || event.source_agent}`);
      break;
    case "tool_completed":
      markAgent(event.source_agent, "idle");
      markAgent(event.target_agent, "idle");
      addEdge(`tool_${payload.node_id || event.event_id}_${payload.sequence || 1}`, event.source_agent, event.target_agent, "completed");
      appendTerminal(`TOOL complete ${toolLabel(payload)}`);
      break;
    case "tool_blocked":
      markAgent(event.source_agent, "blocked");
      markAgent(event.target_agent, "blocked");
      addEdge(`tool_${payload.node_id || event.event_id}_${payload.sequence || 1}`, event.source_agent, event.target_agent, "blocked");
      appendTerminal(`TOOL blocked ${toolLabel(payload)}`);
      break;
    case "tool_failed":
      markAgent(event.source_agent, "blocked");
      markAgent(event.target_agent, "blocked");
      addEdge(`tool_${payload.node_id || event.event_id}_${payload.sequence || 1}`, event.source_agent, event.target_agent, "blocked");
      appendTerminal(`TOOL failed ${toolLabel(payload)}`);
      break;
    case "approval_required":
      markAgent(event.target_agent || "human_reviewer", "running");
      appState.summary.stage = "waiting_for_human";
      appendTerminal(`APPROVAL ${payload.required_decision || "required"} ${payload.reason || ""}`.trim());
      break;
    case "evidence_bundle_packed":
      appState.summary.evidence += 1;
      appendTerminal(`EVIDENCE ${payload.evidence_bundle_id} confidence=${payload.confidence}`);
      break;
    case "context_patch_proposed":
      appState.summary.patch += 1;
      appendTerminal(`PATCH ${patchLabel(payload)}`);
      break;
    case "patch_reviewed":
      appendTerminal(`REVIEW ${reviewLabel(payload)} allowed=${payload.allowed_to_merge}`);
      break;
    case "agent_message":
      if (options.renderDialogMessages !== false) {
        appendAgentMessage(payload);
      }
      markAgent(payload.agent_id || event.source_agent, "running");
      appendTerminal(`AGENT ${payload.speaker || agentLabel(payload.agent_id || event.source_agent)}: ${payload.text || ""}`.trim());
      break;
    case "user_input_requested":
      if (options.renderDialogMessages !== false) {
        appendUserInputRequest(payload);
      }
      markAgent(payload.target_agent || "center_agent", "waiting_for_human");
      appendTerminal(`USER_INPUT_REQUEST ${payload.request_id || ""} questions=${Array.isArray(payload.questions) ? payload.questions.length : 0}`.trim());
      break;
    case "command_line":
      appendTerminal(scriptConsoleLabel(payload));
      break;
    case "token_usage_snapshot":
      applyUsage(payload);
      appendTerminal(`USAGE ${payload.agent_id} total=${payload.total_tokens}`);
      break;
    case "stage_summary":
      appState.summary.stage = payload.status || appState.summary.stage;
      closeRunningAgents();
      if (!appState.lastResponse || Object.keys(appState.lastResponse).length === 0 || appState.lastResponse.object_type === "StageSummary") {
        appState.lastResponse = payload;
      }
      appendTerminal(`SUMMARY ${payload.status}: ${payload.summary}`);
      break;
    case "run_paused":
    case "run_resumed":
    case "run_blocked":
    case "run_completed":
      appState.summary.stage = payload.state || event.type.replace("run_", "");
      if (event.type === "run_blocked") {
        markAgent(event.source_agent, "blocked");
      }
      if (event.type === "run_completed") {
        closeRunningAgents();
      }
      appendTerminal(`RUN ${event.type.replace("run_", "")} ${payload.state || ""}`.trim());
      break;
    case "error":
      appendTerminal(`ERROR ${payload.message || "unknown error"}`);
      break;
    default:
      appendTerminal(`EVENT ${event.type}`);
  }
}

function patchLabel(payload) {
  const patch =
    payload.context_patches?.[0] ||
    payload.material_patch?.context_patch ||
    payload.process_context_patch ||
    payload;
  return `${patch.patch_id || payload.object_type || "candidate"} ${patch.target_path || payload.task_id || ""} status=${patch.review_status || "candidate"}`;
}

function reviewLabel(payload) {
  return payload.patch_id || payload.task_id || payload.reviewed_by || payload.object_type || "patch_review";
}

function scriptConsoleLabel(payload) {
  const consoleLine = Array.isArray(payload.console_lines) ? payload.console_lines[0] : null;
  const level = payload.level || consoleLine?.level || "info";
  const text = payload.text || consoleLine?.text || payload.status || "";
  return `${level.toUpperCase()} ${text}`.trim();
}

function toolLabel(payload) {
  const summary = payload.result_summary || {};
  const status = payload.status || payload.gateway_result?.status || "unknown";
  const tool = payload.tool || payload.intent?.tool || "tool";
  const detail = summary.result_type ? ` result=${summary.result_type}` : "";
  return `${tool} status=${status}${detail}`;
}

function closeRunningAgents() {
  // Stage summaries and run-completed events mean the visible work burst ended.
  // Any node still marked running is reset to the quiet standby color.
  for (const [agentId, state] of Object.entries(appState.graph.nodes)) {
    if (state === "running") {
      appState.graph.nodes[agentId] = "idle";
    }
  }
}

function markAgent(agentId, state) {
  // Unknown or hidden internal roles return an empty string and are skipped.
  // That keeps raw runtime noise out of the nine-node business graph.
  const graphAgentId = normalizeGraphAgentId(agentId);
  if (!graphAgentId) {
    return;
  }
  appState.graph.nodes[graphAgentId] = normalizeAgentState(state);
}

function addEdge(edgeId, sourceAgent, targetAgent, state) {
  // Edges also use the business-role mapping. If two internal roles collapse to
  // the same visible node, the edge is omitted because it would only show noise.
  const source = normalizeGraphAgentId(sourceAgent);
  const target = normalizeGraphAgentId(targetAgent);
  if (!source || !target || source === target) {
    return;
  }
  const existingIndex = appState.graph.edges.findIndex((edge) => edge.edge_id === edgeId);
  const edge = { edge_id: edgeId, source_agent: source, target_agent: target, state };
  if (existingIndex >= 0) {
    appState.graph.edges[existingIndex] = edge;
  } else {
    appState.graph.edges.push(edge);
  }
}

function normalizeGraphAgentId(agentId) {
  const raw = String(agentId || "").trim();
  if (!raw) {
    return "";
  }
  if (DEFAULT_AGENTS.includes(raw)) {
    return raw;
  }
  return AGENT_NODE_ALIASES[raw] || "";
}

function normalizeAgentState(state) {
  const normalized = String(state || "idle").trim();
  if (normalized === "done" || normalized === "complete" || normalized === "completed" || normalized === "ready") {
    return "idle";
  }
  return AGENT_STATE_LABELS[normalized] ? normalized : "idle";
}

function applyUsage(payload) {
  appState.usage = {
    input_tokens: Number(payload.input_tokens || 0),
    output_tokens: Number(payload.output_tokens || 0),
    cached_tokens: Number(payload.cached_tokens || 0),
    total_tokens: Number(payload.total_tokens || 0),
  };
  appState.summary.token = appState.usage.total_tokens;
}

function applyRuntimeReply(reply, elapsedMs) {
  const runtime = reply.runtime || {};
  const metrics = reply.metrics || {};
  const priorMessageCount = appState.agentMessages.length;

  appState.summary.run = metrics.runId || appState.summary.run;
  appState.summary.route = metrics.tools || "runtime response";
  appState.summary.key = keyStatusLabel(runtime);
  appState.api = {
    runtime: booleanLabel(runtime.directApiAvailable),
    apiKey: keyStatusLabel(runtime),
    apiKeySource: runtime.apiKeySource || (appState.apiConfig.apiKey ? "request" : "none"),
    apiKeyFingerprint: runtime.apiKeyFingerprint || "none",
    directApiCalled: String(Boolean(runtime.directApiCalled)),
    baseUrl: runtime.baseUrl || metrics.baseUrl || appState.apiConfig.baseUrl || "provider default",
  };

  appendTerminal(`HTTP 200 in ${elapsedMs} ms`);
  appendTerminal(
    `RUNTIME provider=${runtime.providerLabel || runtime.provider || "unknown"} model=${runtime.model || "unknown"} api_mode=${runtime.apiMode || "unknown"} direct_api_called=${appState.api.directApiCalled} direct_api_available=${appState.api.runtime} key=${appState.api.apiKeySource}`,
  );
  if (reply.usage) {
    applyUsage(reply.usage);
  }
  if (Array.isArray(reply.events) && reply.events.length) {
    for (const event of reply.events) {
      applyRunEvent(event, { renderDialogMessages: false });
    }
  } else {
    for (const step of reply.timeline || []) {
      appendTerminal(`STEP ${step.state}: ${step.title} - ${step.detail}`);
    }
  }
  if (appState.agentMessages.length === priorMessageCount) {
    appendAgentMessage(buildDialogTurnMessage(reply));
  }
  appendToolRunDetails(reply.toolRuns);
  appendTerminal(`AGENT> ${reply.text || "(empty response)"}`);

  renderAll();
}

function buildDialogTurnMessage(reply) {
  return {
    agent_id: "center_agent",
    speaker: "中心Agent",
    text: dialogSummaryText(reply),
    details: buildDialogDetails(reply),
  };
}

function dialogSummaryText(reply) {
  const runtime = reply?.runtime && typeof reply.runtime === "object" ? reply.runtime : {};
  const explicit = firstNonEmptyString(reply?.dialogSummary, reply?.dialog_summary, runtime.dialogSummary, runtime.dialog_summary);
  if (explicit) {
    return compactDialogText(explicit, 520);
  }
  const agentText = lastUserFacingAgentText(reply?.agentMessages);
  if (agentText) {
    return compactDialogText(agentText, 520);
  }
  const toolSummary = toolRunDialogSummary(reply?.toolRuns);
  if (toolSummary) {
    return toolSummary;
  }
  const cleanText = cleanRuntimeDialogText(reply?.text);
  if (cleanText) {
    return compactDialogText(cleanText, 520);
  }
  return "后端已返回运行结果，但本轮没有提供可直接展示的工程摘要；详细执行记录已保留在下方命令输出。";
}

function lastUserFacingAgentText(agentMessages) {
  if (!Array.isArray(agentMessages)) {
    return "";
  }
  for (const message of agentMessages.slice().reverse()) {
    const text = String(message?.text || message?.message || "").trim();
    if (!text || !isDialogSummaryCandidate(text)) {
      continue;
    }
    const agentId = String(message?.agent_id || message?.agentId || "");
    const speaker = String(message?.speaker || "");
    if (agentId === "center_agent" || speaker.includes("用户")) {
      return text;
    }
  }
  const fallback = agentMessages
    .map((message) => String(message?.text || message?.message || "").trim())
    .filter(isDialogSummaryCandidate)
    .pop();
  return fallback || "";
}

function isDialogSummaryCandidate(text) {
  const normalized = String(text || "").trim();
  if (!normalized) {
    return false;
  }
  if (normalized.includes("详细命令输出保留") || normalized.includes("本轮工具摘要")) {
    return false;
  }
  return !looksLikeRuntimeLog(normalized);
}

function toolRunDialogSummary(toolRuns) {
  if (!Array.isArray(toolRuns) || !toolRuns.length) {
    return "";
  }
  const geometryImport = [...toolRuns].reverse().find((run) => run?.tool === "autoform_import_geometry_to_new_project");
  if (geometryImport) {
    const result = geometryImport.result && typeof geometryImport.result === "object" ? geometryImport.result : {};
    const project = result.output_afd_path || result.run_dir || result.source_geometry_path;
    const evidence = result.evidence_dir ? ` evidence_dir=${compactDialogText(result.evidence_dir, 180)}.` : "";
    const status = result.status || geometryImport.status || "unknown";
    return project
      ? `geometry import returned ${status}. current_project=${compactDialogText(project, 180)}.${evidence}`
      : `geometry import returned ${status} without an output project path.`;
  }
  const projectRun = [...toolRuns].reverse().find((run) => run?.tool === "autoform_project_run");
  if (projectRun) {
    const result = projectRun.result && typeof projectRun.result === "object" ? projectRun.result : {};
    const args = projectRun.arguments && typeof projectRun.arguments === "object" ? projectRun.arguments : {};
    const project = result.working_project || result.run_dir || args.afd_path || args.example_name;
    const status = projectRun.status || result.status || "unknown";
    return project
      ? `工程工具已返回 ${status}。当前工程：${compactDialogText(project, 180)}。`
      : `工程工具已返回 ${status}，本轮没有返回工程路径。`;
  }
  const startUi = [...toolRuns].reverse().find((run) => run?.tool === "autoform_start_ui");
  if (startUi) {
    return `AutoForm 主界面启动请求已返回 ${startUi.status || "unknown"}；新建工程向导参数仍需在 GUI 内确认。`;
  }
  const blocked = toolRuns.find((run) => String(run?.status || "").includes("blocked"));
  if (blocked) {
    return `${toolLabel(blocked)} 需要本机工具控制批准或补充参数后才能继续。`;
  }
  return `本轮已处理 ${toolRuns.length} 个工具结果；可展开查看 Agent 明细，完整命令日志保留在下方。`;
}

function buildDialogDetails(reply) {
  const details = [];
  const currentProject = reply?.runtime?.currentProject;
  if (currentProject && typeof currentProject === "object") {
    details.push({
      type: "current_project",
      agent_id: "center_agent",
      speaker: "当前工程上下文",
      text: currentProjectDetailText(currentProject),
    });
  }
  if (Array.isArray(reply?.agentMessages)) {
    for (const message of reply.agentMessages) {
      const text = String(message?.text || message?.message || "").trim();
      if (!text) {
        continue;
      }
      details.push({
        type: "agent_message",
        agent_id: String(message?.agent_id || message?.agentId || ""),
        speaker: String(message?.speaker || agentLabel(message?.agent_id || message?.agentId)),
        text,
      });
    }
  }
  for (const run of compactToolRunsForDisplay(reply?.toolRuns) || []) {
    details.push({
      type: "tool_result",
      agent_id: "project_workflow",
      speaker: "工具结果",
      text: compactToolRunDetailText(run),
    });
  }
  const questions = Array.isArray(reply?.pendingUserInput?.questions) ? reply.pendingUserInput.questions : [];
  for (const question of questions) {
    const text = String(question?.text || "").trim();
    if (text) {
      details.push({
        type: "user_input_requested",
        agent_id: String(reply.pendingUserInput.source_agent || "center_agent"),
        speaker: "待用户确认",
        text,
      });
    }
  }
  return details.slice(0, 16);
}

function currentProjectDetailText(project) {
  const measurement = project.cad_measurement_result && typeof project.cad_measurement_result === "object"
    ? project.cad_measurement_result
    : undefined;
  const filenameCandidate = project.filename_dimension_candidate && typeof project.filename_dimension_candidate === "object"
    ? project.filename_dimension_candidate
    : undefined;
  const parts = [
    project.label,
    project.working_project ? `working_project=${project.working_project}` : "",
    project.afd_path ? `afd_path=${project.afd_path}` : "",
    project.output_afd_path ? `output_afd_path=${project.output_afd_path}` : "",
    project.source_geometry_path ? `source_geometry_path=${project.source_geometry_path}` : "",
    project.example_name ? `example=${project.example_name}` : "",
    project.run_dir ? `run_dir=${project.run_dir}` : "",
    project.evidence_dir ? `evidence_dir=${project.evidence_dir}` : "",
    measurement ? `cad_measurement=${cadMeasurementSummary(measurement)}` : "",
    filenameCandidate ? `filename_candidate=${dimensionObjectText(filenameCandidate)}` : "",
    project.last_tool_status ? `status=${project.last_tool_status}` : "",
  ].filter(Boolean);
  return parts.join("；");
}

function compactToolRunDetailText(run) {
  return [
    `${run.tool || "tool"} status=${run.status || "unknown"}`,
    run.example ? `example=${run.example}` : "",
    run.working_project ? `working_project=${run.working_project}` : "",
    run.output_afd_path ? `output_afd_path=${run.output_afd_path}` : "",
    run.source_geometry_path ? `source_geometry_path=${run.source_geometry_path}` : "",
    run.cad_measurement ? `cad_measurement=${run.cad_measurement}` : "",
    run.parser ? `parser=${run.parser}` : "",
    run.blocked_reason ? `blocked_reason=${run.blocked_reason}` : "",
    run.filename_candidate ? `filename_candidate=${run.filename_candidate}` : "",
    run.dimension_candidate ? `dimension_candidate=${run.dimension_candidate}` : "",
    run.run_dir ? `run_dir=${run.run_dir}` : "",
    run.evidence_dir ? `evidence_dir=${run.evidence_dir}` : "",
    run.gui_pid ? `gui_pid=${run.gui_pid}` : "",
    run.solver_returncode !== undefined ? `solver_returncode=${run.solver_returncode}` : "",
    run.error ? `error=${run.error}` : "",
  ]
    .filter(Boolean)
    .join("；");
}

function cadMeasurementSummary(measurement) {
  const parts = [
    `status=${measurement.status || "unknown"}`,
    measurement.parser ? `parser=${measurement.parser}` : "",
    measurement.status === "completed" ? `measured=${dimensionObjectText(measurement)}` : "",
    measurement.blocked_reason ? `blocked=${compactDialogText(measurement.blocked_reason, 120)}` : "",
    measurement.evidence_dir ? `evidence_dir=${measurement.evidence_dir}` : "",
  ].filter(Boolean);
  return parts.join(" ");
}

function dimensionObjectText(value) {
  if (!value || typeof value !== "object") {
    return "";
  }
  if (value.length !== undefined && value.width !== undefined && value.thickness !== undefined) {
    return `${value.length}x${value.width}x${value.thickness} ${value.unit || ""}`.trim();
  }
  return "";
}

function firstNonEmptyString(...values) {
  for (const value of values) {
    const text = String(value || "").trim();
    if (text) {
      return text;
    }
  }
  return "";
}

function cleanRuntimeDialogText(value) {
  const text = String(value || "").trim();
  if (!text || looksLikeRuntimeLog(text)) {
    return "";
  }
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !looksLikeRuntimeLog(line));
  if (!lines.length) {
    return "";
  }
  return lines.join(" ");
}

function looksLikeRuntimeLog(text) {
  const lines = String(text || "").split(/\r?\n/).filter(Boolean);
  if (!lines.length) {
    return false;
  }
  const noisy = lines.filter((line) =>
    /^\[\d{2}:\d{2}:\d{2}\]\s/.test(line) ||
    /^(NODE|TOOL|INFO|RUNTIME|EVENT|STEP|CONFIG|LOCAL|POST|HTTP|AGENT>|TOOL_RESULT)\b/.test(line.trim()) ||
    line.includes("Runtime response") ||
    line.includes("stdout") ||
    line.includes("stderr"),
  );
  return noisy.length >= Math.max(1, Math.ceil(lines.length * 0.5));
}

function compactDialogText(value, maximum = 520) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maximum) {
    return text;
  }
  return `${text.slice(0, maximum - 1).trim()}…`;
}

function appendToolRunDetails(toolRuns) {
  if (!Array.isArray(toolRuns) || !toolRuns.length) {
    return;
  }
  for (const run of toolRuns) {
    appendTerminal(`TOOL_RESULT ${run.tool || "tool"} status=${run.status || "unknown"}`);
    const result = run.result && typeof run.result === "object" ? run.result : {};
    if (result.working_project) {
      appendTerminal(`PROJECT ${result.working_project}`);
    } else if (result.output_afd_path) {
      appendTerminal(`PROJECT ${result.output_afd_path}`);
    } else if (result.run_dir) {
      appendTerminal(`RUN_DIR ${result.run_dir}`);
    }
    if (result.source_geometry_path) {
      appendTerminal(`SOURCE_GEOMETRY ${result.source_geometry_path}`);
    }
    if (result.evidence_dir) {
      appendTerminal(`EVIDENCE_DIR ${result.evidence_dir}`);
    }
    const gui = result.gui_observation && typeof result.gui_observation === "object" ? result.gui_observation : {};
    if (Object.keys(gui).length) {
      appendTerminal(`GUI launched=${Boolean(gui.launched)} pid=${gui.pid || "none"}`);
    }
    const solverCase = firstSolverCase(result);
    if (solverCase) {
      const stdoutSummary = solverCase.stdout_summary || {};
      appendTerminal(
        `SOLVER returncode=${solverCase.returncode} simulation_successful=${Boolean(stdoutSummary.simulation_successful)}`,
      );
    }
    if (run.error) {
      appendTerminal(`TOOL_ERROR ${run.error}`);
    }
  }
}

function firstSolverCase(result) {
  const cases = result?.solver?.cases;
  return Array.isArray(cases) && cases.length && typeof cases[0] === "object" ? cases[0] : null;
}

function buildRuntimeConfigForRequest(options = {}) {
  syncApiConfigFromDom();
  const runtimeConfig = {
    provider: appState.apiConfig.provider,
    baseUrl: appState.apiConfig.baseUrl,
    model: appState.apiConfig.model,
    apiMode: appState.apiConfig.apiMode,
  };

  if (options.connectionTest) {
    runtimeConfig.connectionTest = true;
  }
  if (appState.apiConfig.apiKey) {
    runtimeConfig.apiKey = appState.apiConfig.apiKey;
  }
  return runtimeConfig;
}

function buildConversationContextForRequest() {
  const context = appState.conversationContext;
  const history = compactProjectHistoryForContext(appState.agentMessages);
  if ((!context || typeof context !== "object" || !Object.keys(context).length) && !history.length) {
    return undefined;
  }
  return {
    schema_version: "autoform.frontend_conversation_context.v1",
    selected_role_ids: Array.isArray(context?.selected_role_ids) ? context.selected_role_ids.slice(0, 12) : [],
    material_card: compactMaterialCardForContext(context?.material_card),
    pending_user_input: context?.pending_user_input,
    shared_context_policy: context?.shared_context_policy,
    current_project: compactCurrentProjectForContext(context?.current_project),
    project_history: history,
    recent_user_prompts: history.filter((entry) => entry.source === "user").slice(-6),
    last_turn: context?.last_turn,
  };
}

function updateConversationContextFromReply(reply) {
  if (!reply || typeof reply !== "object") {
    return;
  }
  const centerPlan = reply.centerPlan || {};
  const contextView = centerPlan.context_view || {};
  const runtime = reply.runtime || {};
  const previous = appState.conversationContext || {};
  const materialCard = mergeMaterialContext(previous.material_card, extractMaterialCardFromReply(reply));
  const pendingUserInput = compactPendingUserInputForDisplay(reply.pendingUserInput) || previous.pending_user_input;
  const currentProject = extractCurrentProjectFromReply(reply) || compactCurrentProjectForContext(previous.current_project);
  const selectedRoleIds = Array.isArray(contextView.selected_role_ids)
    ? contextView.selected_role_ids.slice(0, 12)
    : Array.isArray(previous.selected_role_ids)
      ? previous.selected_role_ids.slice(0, 12)
      : [];

  appState.conversationContext = {
    schema_version: "autoform.frontend_conversation_context.v1",
    selected_role_ids: selectedRoleIds,
    material_card: materialCard,
    pending_user_input: pendingUserInput,
    shared_context_policy: compactSharedContextPolicy(contextView.shared_context_policy),
    current_project: currentProject,
    last_turn: {
      task_id: centerPlan.task_card?.task_id || previous.last_turn?.task_id,
      task_type: centerPlan.task_card?.task_type || previous.last_turn?.task_type,
      selected_role_ids: selectedRoleIds,
      pending_user_input: pendingUserInput,
      material_card: materialCard,
      current_project: currentProject,
      project_history: compactProjectHistoryForContext(appState.agentMessages),
      runtime_flags: {
        multiAgentPreparation: Boolean(runtime.multiAgentPreparation),
        multiAgentMaterialLookup: Boolean(runtime.multiAgentMaterialLookup),
        multiAgentMaterialResume: Boolean(runtime.multiAgentMaterialResume),
      },
    },
  };
}

function extractCurrentProjectFromReply(reply) {
  const runtimeProject = compactCurrentProjectForContext(reply?.runtime?.currentProject);
  if (runtimeProject) {
    return runtimeProject;
  }
  const toolProject = extractCurrentProjectFromToolRuns(reply?.toolRuns);
  if (toolProject) {
    return toolProject;
  }
  const runtime = reply?.runtime && typeof reply.runtime === "object" ? reply.runtime : {};
  if (runtime.existingProjectPathRequired) {
    return undefined;
  }
  const localExecution = appState.localExecution || {};
  if (localExecution.projectOperation === "new_project" && reply?.toolRuns?.some((run) => run?.tool === "autoform_start_ui")) {
    return compactCurrentProjectForContext({
      kind: "new_project",
      label: "新建工程入口",
      last_tool: "autoform_start_ui",
      last_tool_status: reply.toolRuns.find((run) => run?.tool === "autoform_start_ui")?.status,
      source: "frontend_project_operation",
    });
  }
  if (localExecution.projectOperation === "example_project" && localExecution.exampleName) {
    return compactCurrentProjectForContext({
      kind: "example_project",
      label: localExecution.exampleName,
      example_name: localExecution.exampleName,
      source: "frontend_project_operation",
    });
  }
  return undefined;
}

function extractCurrentProjectFromToolRuns(toolRuns) {
  if (!Array.isArray(toolRuns)) {
    return undefined;
  }
  for (const run of toolRuns.slice().reverse()) {
    const result = run?.result && typeof run.result === "object" ? run.result : {};
    const args = run?.arguments && typeof run.arguments === "object" ? run.arguments : {};
    const gui = result.gui_observation && typeof result.gui_observation === "object" ? result.gui_observation : {};
    if (run.tool === "autoform_import_geometry_to_new_project") {
      if (result.status && result.status !== "completed") {
        continue;
      }
      return compactCurrentProjectForContext({
        kind: "new_project_import",
        label: result.output_afd_path || result.source_geometry_path || result.run_dir || args.source_geometry_path || "geometry import",
        afd_path: result.output_afd_path || "",
        output_afd_path: result.output_afd_path || "",
        source_geometry_path: result.source_geometry_path || args.source_geometry_path || "",
        run_dir: result.run_dir || "",
        evidence_dir: result.evidence_dir || "",
        last_tool: run.tool || "",
        last_tool_status: result.status || run.status || "",
        gui_pid: result.gui_pid,
        source: "tool_result",
      });
    }
    const project = {
      kind: "",
      label: "",
      example_name: args.example_name || result.project?.name || "",
      afd_path: args.afd_path || result.project?.path || result.path || "",
      working_project: result.working_project || "",
      run_dir: result.run_dir || "",
      last_tool: run.tool || "",
      last_tool_status: run.status || result.status || "",
      gui_pid: gui.pid || result.gui_pid,
      source: "tool_result",
    };
    if (project.working_project || project.afd_path) {
      project.kind = project.example_name ? "example_project" : "afd_project";
      project.label = project.working_project || project.afd_path;
      return compactCurrentProjectForContext(project);
    }
    if (project.example_name && run.tool === "autoform_project_run") {
      project.kind = "example_project";
      project.label = project.example_name;
      return compactCurrentProjectForContext(project);
    }
    if (run.tool === "autoform_start_ui" && !String(run.status || "").includes("blocked")) {
      return compactCurrentProjectForContext({
        kind: "new_project",
        label: "新建工程入口",
        last_tool: run.tool,
        last_tool_status: run.status,
        source: "tool_result",
      });
    }
  }
  return undefined;
}

function compactCurrentProjectForContext(project) {
  if (!project || typeof project !== "object") {
    return undefined;
  }
  const kind = String(project.kind || "").trim();
  const workingProject = String(project.working_project || "").trim();
  const afdPath = String(project.afd_path || "").trim();
  const exampleName = String(project.example_name || "").trim();
  const runDir = String(project.run_dir || "").trim();
  const sourceGeometryPath = String(project.source_geometry_path || "").trim();
  const outputAfdPath = String(project.output_afd_path || "").trim();
  const evidenceDir = String(project.evidence_dir || "").trim();
  const cadMeasurementResult = project.cad_measurement_result && typeof project.cad_measurement_result === "object"
    ? project.cad_measurement_result
    : undefined;
  const filenameDimensionCandidate = project.filename_dimension_candidate && typeof project.filename_dimension_candidate === "object"
    ? project.filename_dimension_candidate
    : undefined;
  const label = String(project.label || workingProject || outputAfdPath || afdPath || exampleName || runDir || sourceGeometryPath || "").trim();
  if (!kind && !label && !workingProject && !afdPath && !exampleName && !runDir && !sourceGeometryPath && !outputAfdPath && !evidenceDir && !cadMeasurementResult) {
    return undefined;
  }
  return {
    schema_version: "autoform.current_project.v1",
    kind: kind || (workingProject || afdPath || outputAfdPath ? "afd_project" : exampleName ? "example_project" : "project_reference"),
    label,
    example_name: exampleName,
    afd_path: afdPath || outputAfdPath,
    working_project: workingProject,
    run_dir: runDir,
    source_geometry_path: sourceGeometryPath,
    output_afd_path: outputAfdPath,
    evidence_dir: evidenceDir,
    cad_measurement_result: cadMeasurementResult,
    filename_dimension_candidate: filenameDimensionCandidate,
    last_tool: String(project.last_tool || "").trim(),
    last_tool_status: String(project.last_tool_status || "").trim(),
    gui_pid: project.gui_pid === undefined || project.gui_pid === null ? undefined : project.gui_pid,
    source: String(project.source || "frontend").trim(),
    updated_at: String(project.updated_at || new Date().toISOString()),
  };
}

function extractMaterialCardFromReply(reply) {
  const runtime = reply.runtime || {};
  const queryCard = runtime.materialDatabaseQuery?.material_card;
  if (queryCard && typeof queryCard === "object") {
    return queryCard;
  }
  const materialResponse = runtime.materialUserResponse;
  if (materialResponse && typeof materialResponse === "object") {
    return {
      object_type: "MaterialCard",
      grade: materialResponse.material_grade,
      material_temper: materialResponse.material_temper,
      selected_material_source: materialResponse.selected_material_source,
      confirmation_status: materialResponse.status,
    };
  }
  const prepCard = runtime.preparationArtifacts?.materialCard;
  return prepCard && typeof prepCard === "object" ? prepCard : {};
}

function mergeMaterialContext(previous, current) {
  const base = previous && typeof previous === "object" ? previous : {};
  const next = current && typeof current === "object" ? current : {};
  const merged = { ...base, ...next };
  const previousCandidates = Array.isArray(base.local_autoform_material_candidates) ? base.local_autoform_material_candidates : [];
  const nextCandidates = Array.isArray(next.local_autoform_material_candidates) ? next.local_autoform_material_candidates : [];
  const candidates = nextCandidates.length ? nextCandidates : previousCandidates;
  if (candidates.length) {
    merged.local_autoform_material_candidates = candidates.slice(0, 8);
  }
  return compactMaterialCardForContext(merged);
}

function compactMaterialCardForContext(materialCard) {
  if (!materialCard || typeof materialCard !== "object") {
    return {};
  }
  const candidates = Array.isArray(materialCard.local_autoform_material_candidates)
    ? materialCard.local_autoform_material_candidates
    : [];
  return Object.fromEntries(
    Object.entries({
      object_type: materialCard.object_type,
      task_id: materialCard.task_id,
      material_id: materialCard.material_id,
      grade: materialCard.grade,
      material_temper: materialCard.material_temper,
      confirmation_status: materialCard.confirmation_status,
      selected_material_source: materialCard.selected_material_source,
      curve_source_ref: materialCard.curve_source_ref,
      local_autoform_material_candidates: candidates.slice(0, 8).map((candidate) => ({
        name: candidate.name,
        path: candidate.path,
        extension: candidate.extension,
        source_type: candidate.source_type,
        file_size_bytes: candidate.file_size_bytes,
        last_modified: candidate.last_modified,
      })),
    }).filter(([, value]) => value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && !value.length)),
  );
}

function compactSharedContextPolicy(policy) {
  if (!policy || typeof policy !== "object") {
    return undefined;
  }
  return {
    object_type: policy.object_type,
    policy_id: policy.policy_id,
    active_view_level: policy.active_view_level,
    compression_strategy: policy.compression_strategy,
    write_policy: policy.write_policy,
  };
}

function buildLocalExecutionContext() {
  syncLocalExecutionFromDom();
  const enabled = Boolean(appState.localExecution.enabled);
  const projectOperation = normalizeProjectOperation(appState.localExecution.projectOperation);
  return {
    enabled,
    approved: enabled,
    scope: "mcp_gateway",
    projectOperation,
    exampleName: projectOperation === "example_project" ? appState.localExecution.exampleName : "",
    mode: "kinematic",
  };
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

function syncLocalExecutionFromDom() {
  const selected = String(elements.demoExample?.value || "new_project");
  const projectOperation = normalizeProjectOperation(selected);
  appState.localExecution = {
    enabled: Boolean(elements.localExecution?.checked),
    scope: "mcp_gateway",
    projectOperation,
    exampleName: projectOperation === "example_project" ? selected : "",
  };
}

function normalizeProjectOperation(value) {
  const raw = String(value || "").trim();
  if (raw === "new_project") {
    return "new_project";
  }
  if (raw === "existing_project") {
    return "existing_project";
  }
  return "example_project";
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
  appState.api.baseUrl = appState.apiConfig.baseUrl || "provider default";
  renderAll();
}

function appendTerminal(line) {
  const time = new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
  appState.terminalLines.push(`[${time}] ${line}`);
  if (appState.terminalLines.length > 220) {
    appState.terminalLines = appState.terminalLines.slice(-220);
  }
  renderTerminal();
}

function appendUserMessage(prompt) {
  const text = String(prompt || "").trim();
  if (!text) {
    return;
  }
  const message = {
    source: "user",
    agent_id: "user",
    speaker: "用户输入",
    text,
    created_at: new Date().toISOString(),
  };
  const key = dialogMessageKey(message);
  if (appState.currentTurnMessageKeys.has(key)) {
    return;
  }
  appState.currentTurnMessageKeys.add(key);
  appState.agentMessages.push(message);
  trimProjectDialogHistory();
  renderAgentDialog();
}

function appendAgentMessage(message) {
  const agentId = String(message?.agent_id || message?.agentId || "center_agent");
  const text = String(message?.text || message?.message || "").trim();
  if (!text) {
    return;
  }
  const nextMessage = {
    source: "agent",
    agent_id: agentId,
    speaker: String(message?.speaker || agentLabel(agentId)),
    text,
    created_at: String(message?.created_at || new Date().toISOString()),
    details: normalizeDialogDetails(message?.details),
  };
  const key = dialogMessageKey(nextMessage);
  if (appState.currentTurnMessageKeys.has(key)) {
    return;
  }
  appState.currentTurnMessageKeys.add(key);
  appState.agentMessages.push(nextMessage);
  trimProjectDialogHistory();
  renderAgentDialog();
}

function dialogMessageKey(message) {
  return [
    String(message?.source || "agent"),
    String(message?.agent_id || ""),
    String(message?.speaker || ""),
    String(message?.text || "").replace(/\s+/g, " ").trim(),
  ].join("|");
}

function normalizeDialogDetails(details) {
  if (!Array.isArray(details)) {
    return [];
  }
  return details
    .map((detail) => ({
      type: String(detail?.type || "detail"),
      agent_id: String(detail?.agent_id || detail?.agentId || ""),
      speaker: String(detail?.speaker || agentLabel(detail?.agent_id || detail?.agentId || "")),
      text: String(detail?.text || detail?.message || "").trim(),
    }))
    .filter((detail) => detail.text)
    .slice(0, 16);
}

function trimProjectDialogHistory() {
  if (appState.agentMessages.length > 160) {
    appState.agentMessages = appState.agentMessages.slice(-160);
  }
}

function compactProjectHistoryForContext(messages) {
  if (!Array.isArray(messages)) {
    return [];
  }
  return messages.slice(-24).map((message, index) => ({
    index,
    source: message.source === "user" ? "user" : "agent",
    agent_id: String(message.agent_id || ""),
    speaker: String(message.speaker || ""),
    text: String(message.text || "").slice(0, 500),
    created_at: String(message.created_at || ""),
  }));
}

function appendUserInputRequest(payload) {
  const questions = Array.isArray(payload?.questions) ? payload.questions : [];
  if (!questions.length) {
    return;
  }
  for (const question of questions) {
    const text = String(question?.text || "").trim();
    if (!text) {
      continue;
    }
    appendAgentMessage({
      agent_id: "center_agent",
      speaker: "中心Agent",
      text: `请用户补充：${text}`,
    });
  }
}

function renderSummary() {
  elements.summaryRun.textContent = appState.summary.run;
  elements.summaryTask.textContent = appState.summary.task;
  elements.summaryStage.textContent = appState.summary.stage;
  elements.summaryRoute.textContent = appState.summary.route;
  elements.summaryEvidence.textContent = String(appState.summary.evidence);
  elements.summaryPatch.textContent = String(appState.summary.patch);
  elements.summaryKey.textContent = appState.apiConfig.apiKey ? "页面会话 key 已输入" : appState.summary.key;
  elements.summaryToken.textContent = String(appState.summary.token);
}

function renderGraph() {
  const nodeEntries = Object.entries(appState.graph.nodes);
  elements.agentGraph.replaceChildren(
    ...nodeEntries.map(([agentId, state]) => {
      const node = document.createElement("div");
      node.className = `agent-node is-${state}`;
      node.dataset.agentId = agentId;
      node.innerHTML = `<strong>${agentLabel(agentId)}</strong><span>${agentStateLabel(state)}</span>`;
      return node;
    }),
  );

  if (!appState.graph.edges.length) {
    const empty = document.createElement("div");
    empty.className = "edge-item";
    empty.textContent = "no transfer";
    elements.edgeList.replaceChildren(empty);
    return;
  }

  elements.edgeList.replaceChildren(
    ...appState.graph.edges.map((edge) => {
      const item = document.createElement("div");
      item.className = `edge-item is-${edge.state}`;
      item.textContent = `${agentLabel(edge.source_agent)} -> ${agentLabel(edge.target_agent)} / ${edge.state}`;
      return item;
    }),
  );
}

function renderTerminal() {
  const output = elements.terminalOutput;
  const previousScrollTop = output.scrollTop;
  const previousBottomGap = output.scrollHeight - output.clientHeight - previousScrollTop;
  const shouldFollowTail = previousBottomGap <= 24;

  output.textContent = appState.terminalLines.join("\n");
  output.scrollTop = shouldFollowTail ? output.scrollHeight : previousScrollTop;
}

function renderAgentDialog() {
  if (!elements.agentDialog) {
    return;
  }
  const messages = appState.agentMessages.length
    ? appState.agentMessages
    : [
        {
          speaker: "中心Agent",
          text: "等待中心Agent接收任务。",
        },
      ];
  const previousScrollTop = elements.agentDialog.scrollTop;
  const previousBottomGap = elements.agentDialog.scrollHeight - elements.agentDialog.clientHeight - previousScrollTop;
  const shouldFollowTail = previousBottomGap <= 24;
  elements.agentDialog.replaceChildren(
    ...messages.map((message) => {
      const item = document.createElement("div");
      item.className = `agent-message ${message.source === "user" ? "is-user" : "is-agent"}`;
      const speaker = document.createElement("div");
      speaker.className = "agent-speaker";
      speaker.textContent = message.speaker || agentLabel(message.agent_id);
      const text = document.createElement("div");
      text.className = "agent-message-text";
      text.textContent = message.text;
      item.append(speaker, text);
      const details = normalizeDialogDetails(message.details);
      if (details.length) {
        const detailBox = document.createElement("details");
        detailBox.className = "agent-message-details";
        const summary = document.createElement("summary");
        summary.textContent = "查看本轮 Agent 明细";
        detailBox.append(summary);
        for (const detail of details) {
          const detailItem = document.createElement("div");
          detailItem.className = `agent-message-detail-item detail-${detail.type}`;
          const detailSpeaker = document.createElement("strong");
          detailSpeaker.textContent = detail.speaker;
          const detailText = document.createElement("span");
          detailText.textContent = detail.text;
          detailItem.append(detailSpeaker, detailText);
          detailBox.append(detailItem);
        }
        item.append(detailBox);
      }
      return item;
    }),
  );
  elements.agentDialog.scrollTop = shouldFollowTail ? elements.agentDialog.scrollHeight : previousScrollTop;
}

function renderApiPanel() {
  elements.apiEndpoint.textContent = appState.endpoint;
  elements.apiRuntime.textContent = appState.api.runtime;
  elements.apiKey.textContent = appState.apiConfig.apiKey ? "页面会话 key 已输入" : appState.api.apiKey;
  elements.apiKeySource.textContent = appState.apiConfig.apiKey ? "request" : appState.api.apiKeySource;
  elements.apiKeyFingerprint.textContent = fingerprintLabel(appState.api.apiKeyFingerprint);
  elements.apiDirectCalled.textContent = appState.api.directApiCalled;
  elements.apiBaseUrl.textContent = appState.apiConfig.baseUrl || appState.api.baseUrl || "provider default";
  elements.apiInput.textContent = prettyJson(appState.lastPayload);
  elements.apiResponse.textContent = prettyJson(trimRuntimeResponse(appState.lastResponse));
}

function renderUsage() {
  elements.usageInput.textContent = String(appState.usage.input_tokens);
  elements.usageOutput.textContent = String(appState.usage.output_tokens);
  elements.usageCached.textContent = String(appState.usage.cached_tokens);
  elements.usageTotal.textContent = String(appState.usage.total_tokens);
}

function renderReplayControls() {
  elements.replayStatus.textContent = appState.replayStatus;
  elements.stepReplayButton.disabled = !appState.replayLoaded || appState.replayIndex >= appState.replayEvents.length;
  elements.runReplayButton.disabled = !appState.replayLoaded || appState.replayIndex >= appState.replayEvents.length;
  elements.resetReplayButton.disabled = !appState.replayLoaded;
}

function renderAll() {
  renderReplayControls();
  renderSummary();
  renderGraph();
  renderTerminal();
  renderAgentDialog();
  renderApiPanel();
  renderUsage();
}

function applyStartupOptions() {
  const options = new URLSearchParams(window.location.search);
  const endpoint = options.get("endpoint");
  if (endpoint) {
    appState.endpoint = endpoint;
  }
  appState.terminalLines = appState.terminalLines.map((line) =>
    line.startsWith("Local bridge: ") ? `Local bridge: ${appState.endpoint}` : line,
  );

  const fixture = options.get("fixture");
  if (fixture) {
    appState.fixtureUrl = fixture;
  }

  const provider = options.get("provider");
  if (provider && PROVIDER_PRESETS[provider]) {
    elements.providerSelect.value = provider;
    applyProviderPreset(true);
  }
}

function bindEvents() {
  elements.stepReplayButton.addEventListener("click", () => {
    stepReplay();
  });

  elements.runReplayButton.addEventListener("click", () => {
    runReplayToEnd();
  });

  elements.resetReplayButton.addEventListener("click", () => {
    resetReplayState();
    appState.replayStatus = `loaded ${appState.replayEvents.length} events`;
    renderAll();
  });

  elements.providerSelect.addEventListener("change", () => {
    applyProviderPreset(true);
  });

  for (const input of [elements.providerBaseUrl, elements.providerModel, elements.apiMode, elements.providerApiKey]) {
    const eventName = input.tagName === "SELECT" ? "change" : "input";
    input.addEventListener(eventName, () => {
      syncApiConfigFromDom();
      appState.summary.key = appState.apiConfig.apiKey ? "页面会话 key 已输入" : "未输入";
      appState.api.apiKey = appState.summary.key;
      appState.api.apiKeySource = appState.apiConfig.apiKey ? "request" : "none";
      appState.api.apiKeyFingerprint = appState.apiConfig.apiKey ? "等待后端响应" : "none";
      renderAll();
    });
  }

  for (const input of [elements.localExecution, elements.demoExample]) {
    input.addEventListener("change", () => {
      syncLocalExecutionFromDom();
      appendTerminal(
        `LOCAL execution=${appState.localExecution.enabled ? "enabled" : "disabled"} mcp_control=${appState.localExecution.enabled ? "approved" : "blocked"} scope=${appState.localExecution.scope} project_operation=${appState.localExecution.projectOperation} example_hint=${appState.localExecution.exampleName || "none"}`,
      );
      renderAll();
    });
  }

  elements.applyProviderPreset.addEventListener("click", () => {
    applyProviderPreset(true);
  });

  elements.testConnectionButton.addEventListener("click", async () => {
    elements.testConnectionButton.disabled = true;
    elements.testConnectionButton.textContent = "测试中";
    try {
      await bridge.sendPrompt("provider connection test", { connectionTest: true });
    } catch (error) {
      appendTerminal(`ERROR ${error.message}`);
    } finally {
      elements.testConnectionButton.disabled = false;
      elements.testConnectionButton.textContent = "测试连接";
    }
  });

  elements.clearApiKey.addEventListener("click", () => {
    elements.providerApiKey.value = "";
    syncApiConfigFromDom();
    appState.summary.key = "未输入";
    appState.api.apiKey = "未输入";
    appState.api.apiKeySource = "none";
    appState.api.apiKeyFingerprint = "none";
    appendTerminal("INFO cleared page session API key");
    renderAll();
  });

  elements.insertExampleButton.addEventListener("click", () => {
    elements.promptInput.value = "打开一个适合展示的示例工程";
    syncLocalExecutionFromDom();
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
      appendTerminal(`ERROR ${error.message}`);
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
  if (reply.object_type === "StageSummary") {
    return reply;
  }
  return {
    role: reply.role,
    text: reply.text,
    metrics: reply.metrics,
    runtime: reply.runtime,
    preview: reply.preview,
    pendingUserInput: compactPendingUserInputForDisplay(reply.pendingUserInput),
    centerPlan: compactCenterPlanForDisplay(reply.centerPlan),
    toolRuns: compactToolRunsForDisplay(reply.toolRuns),
    connectionTest: reply.connectionTest,
    usage: reply.usage,
    eventCount: Array.isArray(reply.events) ? reply.events.length : 0,
    eventTypes: Array.isArray(reply.events) ? reply.events.map((event) => event.type).slice(0, 16) : [],
  };
}

function compactPendingUserInputForDisplay(pendingUserInput) {
  if (!pendingUserInput || typeof pendingUserInput !== "object") {
    return undefined;
  }
  const questions = Array.isArray(pendingUserInput.questions) ? pendingUserInput.questions : [];
  return {
    request_id: pendingUserInput.request_id,
    task_id: pendingUserInput.task_id,
    source_agent: pendingUserInput.source_agent,
    target_agent: pendingUserInput.target_agent,
    status: pendingUserInput.status,
    reason: pendingUserInput.reason,
    questions: questions.map((question) => ({
      question_id: question.question_id,
      field_group: question.field_group,
      target_fields: question.target_fields,
      text: question.text,
      required: question.required,
      candidate_options: Array.isArray(question.candidate_options) ? question.candidate_options.slice(0, 6) : [],
    })),
  };
}

function compactToolRunsForDisplay(toolRuns) {
  if (!Array.isArray(toolRuns)) {
    return undefined;
  }
  return toolRuns.map((run) => {
    const result = run.result && typeof run.result === "object" ? run.result : {};
    const scriptPayload = result.result && typeof result.result === "object" ? result.result : {};
    const measurement = result.skill_id === "cad_measure_geometry_v1"
      ? scriptPayload
      : result.cad_measurement_result && typeof result.cad_measurement_result === "object"
        ? result.cad_measurement_result
        : {};
    const gui = result.gui_observation && typeof result.gui_observation === "object" ? result.gui_observation : {};
    const solverCase = firstSolverCase(result);
    const dimension = result.geometry_dimension_candidate && typeof result.geometry_dimension_candidate === "object"
      ? result.geometry_dimension_candidate
      : {};
    const dimensionCandidate = dimension.length !== undefined && dimension.width !== undefined && dimension.thickness !== undefined
      ? `${dimension.length}x${dimension.width}x${dimension.thickness} ${dimension.unit || ""}`.trim()
      : "";
    return {
      tool: run.tool,
      status: result.status || run.status,
      gatewayStatus: run.gatewayStatus,
      example: run.arguments?.example_name,
      working_project: result.working_project,
      output_afd_path: result.output_afd_path,
      source_geometry_path: measurement.source_geometry_path || result.source_geometry_path || run.arguments?.source_geometry_path || run.arguments?.params?.source_geometry_path,
      cad_measurement: measurement.status ? cadMeasurementSummary(measurement) : "",
      parser: measurement.parser,
      blocked_reason: measurement.blocked_reason,
      filename_candidate: measurement.filename_dimension_candidate ? dimensionObjectText(measurement.filename_dimension_candidate) : "",
      dimension_candidate: dimensionCandidate,
      run_dir: result.run_dir,
      evidence_dir: measurement.evidence_dir || result.evidence_dir,
      gui_pid: gui.pid,
      gui_launched: gui.launched,
      solver_returncode: solverCase?.returncode,
      simulation_successful: solverCase?.stdout_summary?.simulation_successful,
      error: run.error || measurement.failure_reason || measurement.blocked_reason || result.failure_reason || result.blocked_reason,
    };
  });
}

function redactPayloadForDisplay(value) {
  if (Array.isArray(value)) {
    return value.map((item) => redactPayloadForDisplay(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        shouldRedactDisplayKey(key) && item
          ? "[redacted]"
          : redactPayloadForDisplay(item),
      ]),
    );
  }
  return value;
}

function shouldRedactDisplayKey(key) {
  return /^(apiKey|api_key|apiKeyFingerprint|DeepSeek_V4_API|DEEPSEEK_API_KEY|CHAT_API_KEY|authorization)$/i.test(key);
}

function compactCenterPlanForDisplay(centerPlan) {
  if (!centerPlan || typeof centerPlan !== "object") {
    return undefined;
  }
  const contextView = centerPlan.context_view || {};
  return {
    schema_version: centerPlan.schema_version,
    status: centerPlan.status,
    task_id: centerPlan.task_card?.task_id,
    task_type: centerPlan.task_card?.task_type,
    context_id: contextView.context_id,
    view_level: contextView.view_level,
    context_scope: contextView.context_scope,
    selected_role_ids: contextView.selected_role_ids || [],
    dag_node_count: Array.isArray(centerPlan.task_dag) ? centerPlan.task_dag.length : 0,
    patch_review_status: centerPlan.patch_reviews?.[0]?.review_status,
    execution_boundary: centerPlan.execution_boundary,
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

function keyStatusLabel(runtime) {
  if (runtime.apiKeyConfigured === true) {
    return runtime.apiKeySource === "request" ? "页面会话 key 已输入" : "后端环境已配置";
  }
  if (appState.apiConfig.apiKey) {
    return "页面会话 key 已输入";
  }
  return "未输入";
}

function fingerprintLabel(value) {
  if (!value || value === "none") {
    return "none";
  }
  return "configured";
}

function providerLabel(provider) {
  return (PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.custom).label;
}

function agentLabel(agentId) {
  const graphAgentId = normalizeGraphAgentId(agentId) || String(agentId || "");
  return AGENT_LABELS[graphAgentId] || graphAgentId.replaceAll("_", " ");
}

function agentStateLabel(state) {
  return AGENT_STATE_LABELS[state] || state;
}

applyStartupOptions();
bindEvents();
renderAll();
loadFixtureFromInput();
