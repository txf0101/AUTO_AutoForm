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
    exampleName: "Solver_R13",
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
    if (localExecution.approved) {
      payload.agentToolExecutionApproved = true;
    }

    this.state.lastPayload = redactPayloadForDisplay(payload);
    renderApiPanel();
    appendTerminal(`USER> ${prompt}`);
    appendTerminal(
      `CONFIG provider=${runtimeConfig.provider} model=${runtimeConfig.model || "(provider default)"} api_mode=${runtimeConfig.apiMode} key=${runtimeConfig.apiKey ? "request" : "env-or-missing"}`,
    );
    appendTerminal(
      `LOCAL execution=${localExecution.approved ? "approved" : "disabled"} autoform_control=${localExecution.approved ? "approved" : "blocked"} example=${localExecution.exampleName} mode=${localExecution.mode}`,
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

function applyRunEvent(event) {
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
      applyRunEvent(event);
    }
  } else {
    for (const step of reply.timeline || []) {
      appendTerminal(`STEP ${step.state}: ${step.title} - ${step.detail}`);
    }
  }
  appendToolRunDetails(reply.toolRuns);
  appendTerminal(`AGENT> ${reply.text || "(empty response)"}`);

  renderAll();
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
    } else if (result.run_dir) {
      appendTerminal(`RUN_DIR ${result.run_dir}`);
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

function buildLocalExecutionContext() {
  syncLocalExecutionFromDom();
  const enabled = Boolean(appState.localExecution.enabled);
  return {
    enabled,
    approved: enabled,
    exampleName: appState.localExecution.exampleName || "Solver_R13",
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
  appState.localExecution = {
    enabled: Boolean(elements.localExecution?.checked),
    exampleName: elements.demoExample?.value || "Solver_R13",
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
        `LOCAL execution=${appState.localExecution.enabled ? "enabled" : "disabled"} autoform_control=${appState.localExecution.enabled ? "approved" : "blocked"} example=${appState.localExecution.exampleName}`,
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
    centerPlan: compactCenterPlanForDisplay(reply.centerPlan),
    toolRuns: compactToolRunsForDisplay(reply.toolRuns),
    connectionTest: reply.connectionTest,
    usage: reply.usage,
    eventCount: Array.isArray(reply.events) ? reply.events.length : 0,
    eventTypes: Array.isArray(reply.events) ? reply.events.map((event) => event.type).slice(0, 16) : [],
  };
}

function compactToolRunsForDisplay(toolRuns) {
  if (!Array.isArray(toolRuns)) {
    return undefined;
  }
  return toolRuns.map((run) => {
    const result = run.result && typeof run.result === "object" ? run.result : {};
    const gui = result.gui_observation && typeof result.gui_observation === "object" ? result.gui_observation : {};
    const solverCase = firstSolverCase(result);
    return {
      tool: run.tool,
      status: run.status,
      gatewayStatus: run.gatewayStatus,
      example: run.arguments?.example_name,
      working_project: result.working_project,
      run_dir: result.run_dir,
      gui_pid: gui.pid,
      gui_launched: gui.launched,
      solver_returncode: solverCase?.returncode,
      simulation_successful: solverCase?.stdout_summary?.simulation_successful,
      error: run.error,
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
