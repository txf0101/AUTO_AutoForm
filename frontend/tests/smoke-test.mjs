/*
这个脚本用 Node.js 检查前端静态页面的基本结构。它像一次快速开门检查，确认关键文件和页面元素还在。

This script uses Node.js to check the basic structure of the static frontend page. It is a quick door-open check that confirms key files and page elements still exist.
*/

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve("frontend");
const html = await readFile(resolve(root, "index.html"), "utf8");
const js = await readFile(resolve(root, "app.js"), "utf8");
const css = await readFile(resolve(root, "styles.css"), "utf8");

const requiredHtmlMarkers = [
  "data-app-shell",
  "data-prompt-form",
  "data-status-summary",
  "data-step-replay",
  "data-run-replay",
  "data-agent-graph",
  "data-edge-list",
  "data-agent-dialog",
  "data-terminal-output",
  "data-api-input",
  "data-api-response",
  "data-provider-select",
  "data-provider-api-key",
  "data-local-execution",
  "data-demo-example",
  "工程操作",
  "新建工程",
  "已有工程（请在Prompt里面告知项目地址）",
  "data-test-connection",
  "data-api-mode",
  "data-api-runtime",
  "data-api-direct-called",
  "data-api-key-fingerprint",
  "data-usage-total",
];

const requiredJsMarkers = [
  "class AgentRuntimeBridge",
  "async sendPrompt(prompt, options = {})",
  "loadFixtureFromInput",
  "parseJsonl",
  "stepReplay",
  "runReplayToEnd",
  "applyRunEvent",
  "AGENT_NODE_ALIASES",
  "normalizeGraphAgentId",
  "normalizeAgentState",
  "context_view_built",
  "tool_requested",
  "tool_completed",
  "tool_blocked",
  "approval_required",
  "agent_message",
  "user_input_requested",
  "edge_transfer",
  "toolLabel",
  "buildRuntimeConfigForRequest",
  "buildLocalExecutionContext",
  "normalizeProjectOperation",
  "current_project",
  "autoform_import_geometry_to_new_project",
  "source_geometry_path",
  "output_afd_path",
  "evidence_dir",
  "projectOperation",
  "new_project",
  "buildDialogTurnMessage",
  "extractCurrentProjectFromReply",
  "agent-message-details",
  "appendToolRunDetails",
  "compactToolRunsForDisplay",
  "appendUserMessage",
  "compactProjectHistoryForContext",
  "appendUserInputRequest",
  "compactPendingUserInputForDisplay",
  "applyRuntimeReply",
  "redactPayloadForDisplay",
  "renderGraph",
  "appendAgentMessage",
  "renderAgentDialog",
  "renderTerminal",
  "previousBottomGap",
  "shouldFollowTail",
  "renderApiPanel",
  "renderUsage",
  "bindEvents",
];

const requiredAgentLabels = [
  "中心Agent",
  "需求与工艺规划Agent",
  "几何与数据Agent",
  "材料Agent",
  "工艺设置Agent",
  "求解执行Agent",
  "后处理Agent",
  "诊断与优化Agent",
  "报告整理Agent",
];

const requiredCssMarkers = [
  ".workbench-panel",
  ".status-summary",
  ".agent-graph",
  ".agent-dialog",
  ".agent-message",
  ".agent-message.is-user",
  ".agent-message.is-agent",
  ".terminal-output",
  ".agent-node.is-planned",
  ".agent-node.is-running",
  ".agent-node.is-blocked",
  ".agent-node.is-waiting_for_human",
  "overscroll-behavior: contain",
  "scrollbar-gutter: stable",
  ".execution-options",
  ".checkbox-field",
  ".api-config-grid",
  ".api-grid",
  ".usage-grid",
  "@media (max-width: 980px)",
];

function assertIncludes(source, marker, label) {
  if (!source.includes(marker)) {
    throw new Error(`${label} is missing required marker: ${marker}`);
  }
}

for (const marker of requiredHtmlMarkers) {
  assertIncludes(html, marker, "index.html");
}

for (const marker of requiredJsMarkers) {
  assertIncludes(js, marker, "app.js");
}

for (const marker of requiredAgentLabels) {
  assertIncludes(js, marker, "app.js");
}

for (const marker of requiredCssMarkers) {
  assertIncludes(css, marker, "styles.css");
}

if ((js.match(/\/\*/g) || []).length < 2) {
  throw new Error("app.js should keep high-level explanatory comments for maintainers.");
}

console.log("frontend smoke test passed");
