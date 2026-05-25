import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve("frontend");
const html = await readFile(resolve(root, "index.html"), "utf8");
const js = await readFile(resolve(root, "app.js"), "utf8");
const css = await readFile(resolve(root, "styles.css"), "utf8");

const requiredHtmlMarkers = [
  "data-app-shell",
  "data-new-conversation",
  "data-prompt-form",
  "data-message-list",
  "data-timeline",
  "data-bridge-mode",
];

const requiredJsMarkers = [
  "class AgentRuntimeBridge",
  "createConversation()",
  "async sendPrompt(prompt)",
  "simulateToolProgress",
  "renderTimeline",
  "bindEvents",
];

const requiredCssMarkers = [
  ".glass-panel",
  "backdrop-filter",
  ".preview-canvas",
  ".message-user",
  "@media (max-width: 780px)",
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

for (const marker of requiredCssMarkers) {
  assertIncludes(css, marker, "styles.css");
}

if ((js.match(/\/\*/g) || []).length < 2) {
  throw new Error("app.js should keep high-level explanatory comments for maintainers.");
}

console.log("frontend smoke test passed");
