# R5 Center Agent And MCP Gateway Progress

## Source Evidence

- Planning basis: `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`, timestamp checked as `2026-06-01 20:48:15`.
- Existing code basis: `autoform_agent/agent_system/contracts.py`, `autoform_agent/agent_system/orchestrator.py`, `autoform_agent/agent_system/registry.py`, `autoform_agent/agent_runtime.py`, `autoform_agent/runtime_events.py`, `autoform_agent/mcp_tools/`, `schemas/task_card.schema.json`, `schemas/context_patch.schema.json`, `schemas/ui_event_schema.json`.
- Test basis: `tests/test_agent_system.py`, `tests/test_agent_runtime.py`, `tests/test_http_bridge.py`.

## Built In This Turn

- Added `autoform_agent/agent_system/kernel.py`.
  - Builds an R5 `CenterAgentPlan` from one prompt.
  - Emits a schema-shaped `TaskCard`, deterministic task DAG, `ContextView`, candidate route `ContextPatch`, `ContextPatchReview` and `AuditEvent` records.
  - Validates candidate patches by task id, proposer role, target path, evidence refs, risk level and operation.
- Added `autoform_agent/agent_system/tool_gateway.py`.
  - Registers an Agent-facing whitelist over MCP same-source wrapper functions in `autoform_agent.mcp_tools`.
  - Lets `manager`, `center_agent`, `mcp_gateway` or the owning specialist agent request a tool.
  - Blocks controlled AutoForm actions such as `execute`, `open_gui`, screenshot verification or GUI execution unless the caller passes an explicit approval boundary.
- Updated `autoform_agent/agent_runtime.py`.
  - Normal prompt turns now build `centerPlan` before local fallback or direct provider calls.
  - Direct API tool-intent and final-answer messages include a compact `centerAgentPlan`.
  - Runtime tool catalog now includes `autoform_center_agent_plan`, `autoform_agent_tool_gateway_catalog` and `autoform_agent_mcp_gateway_call`.
  - `autoform_agent_mcp_gateway_call` calls the R5 gateway with `execution_approved=False`, so the model cannot grant itself AutoForm control.
- Updated `autoform_agent/runtime_events.py`.
  - Runtime replies containing `centerPlan` now emit `task_card_created`, `route_decision`, `context_view_built`, `context_patch_proposed` and `patch_reviewed` before the ordinary runtime status events.
- Updated CLI.
  - Added `python -m autoform_agent.cli agent-center-plan "..."` for direct R5 inspection.
- Updated docs.
  - `docs/multi_agent_architecture.md` now documents `kernel.py`, `tool_gateway.py`, the center plan command and the MCP same-source gateway rule.
  - `docs/beginner_onboarding_zh.md` now includes `agent-center-plan` and explains that internal Agent MCP reuse goes through `AgentToolGateway`.
- Updated frontend R5 event display.
  - `frontend/app.js` now handles `context_view_built`, marks route roles, and draws route edges from R5 events.
  - `frontend/styles.css` adds a planned-node state.
  - `frontend/index.html` now uses the `20260602-r5-center` resource version to avoid stale browser assets.

## Deliberately Deferred

- R5 does not grant the model direct permission to execute AutoForm GUI clicks, screenshots, project opening or solver runs.
- Browser frontend still consumes backend `RunEvent`; it does not directly connect to MCP stdio.
- Persistent audit log storage is not yet added. The current `AuditEvent` records are returned in `centerPlan` and can be promoted to a file-backed log in a later step.
- Specialist agents remain deterministic roles plus gateway access policy. Full per-agent model prompts and independent memory/state loops remain later work.

## Checks Run

```powershell
python -m pytest tests\test_agent_system.py tests\test_agent_runtime.py tests\test_http_bridge.py -q --basetemp=tmp\pytest_r5_core
```

Result: `19 passed`.

```powershell
python -m pytest frontend\tests tests\test_agent_system.py tests\test_agent_runtime.py tests\test_http_bridge.py -q --basetemp=tmp\pytest_r5_frontend_core
```

Result: `21 passed`.

```powershell
python -m pytest -q --basetemp=tmp\pytest_r5_full
```

Result: `146 passed`.

After adding the direct API gateway-control guard test:

```powershell
python -m pytest -q --basetemp=tmp\pytest_r5_full_v2
```

Result: `147 passed`.

```powershell
python -m pytest frontend\tests tests\test_agent_system.py tests\test_agent_runtime.py -q --basetemp=tmp\pytest_r5_final_quick
```

Result: `18 passed`.

HTTP asset check for `http://127.0.0.1:8786/frontend/index.html?bridge=http&v=r5-final`: `styles.css?v=20260602-r5-center` and `app.js?v=20260602-r5-center` were both present.

```powershell
python -m autoform_agent.cli public-release-scan
```

Result: `safe_to_publish: true`, `finding_count: 0`, `.env` not present in the repository root.

Forbidden phrasing, placeholder and legacy Agents SDK scan across `autoform_agent`, `tests`, `docs`, `README.md`, `DEVELOPERS.md`, `frontend`, `handoff`, `schemas`, `policy` and `backend`: no matches.

```powershell
python -m autoform_agent.cli agent-turn "请用一句话确认R5中心Agent计划已经生成，并说明当前是否需要真实控制AutoForm。" --conversation-id cli-r5-live-direct-api
```

Result: live direct API path returned `directApiCalled: true`, `centerAgentStatus: ready`, `centerPlanSchema: autoform.center_agent.r5.v1`, first events `user_input_received`, `task_card_created`, `route_decision`, `context_view_built`, `context_patch_proposed`, `patch_reviewed`, `agent_node_started`, and `usageTotal: 3614`. The PowerShell pipe displayed Chinese answer text as question marks because of console encoding, while the JSON structure was valid.

```powershell
python -m autoform_agent.cli agent-center-plan "请让中心 Agent 通过 MCP 检查 AutoForm 状态并规划打开结果工程" --conversation-id cli-r5-check
```

Result: returned `CenterAgentPlan` with schema `autoform.center_agent.r5.v1`, 5 DAG nodes, `approved_low_risk` route patch review, and gateway tools including `autoform_project_run`, `autoform_result_open_latest`, `autoform_result_set_view` and `autoform_status_snapshot`.

## Reusable Method

R5 should keep one rule: all Agent initiated AutoForm capability calls pass through a gateway policy object before reaching implementation functions. That policy records owner agent, risk level, source wrapper, default arguments, controlled arguments and approval requirements. This makes CLI, MCP, HTTP runtime and future specialist agents reuse the same business functions while retaining one enforcement point for AutoForm control.

## R0 To R5 Acceptance Closure

- Added explicit `context_id`, `view_level=C0` and `context_scope` fields to R5 `ContextView` so the center Agent context layer is visible in CLI, HTTP runtime replies and frontend `RunEvent` payloads.
- Added a P0 acceptance test that checks the physical R0 to R5 artifacts, builds a center Agent plan, confirms MCP gateway tool visibility, and verifies fallback runtime events reach `task_card_created`, `route_decision`, `context_view_built`, `context_patch_proposed` and `patch_reviewed`.
- Updated `backend/README.md` from planning language to source-backed implementation language for R4 and R5.

The value of this closure is that R5 is no longer only a set of isolated modules. It now has a repeatable acceptance chain from repository scaffold, schema and fixture artifacts to runtime events and Agent gateway policy. Future work can add specialist model loops or persistent audit storage while preserving the same C0 context and gateway boundary.

During final full-test closure, one pre-existing V1.1 result-review acceptance gap surfaced. `play_forming_animation()` now returns `inconclusive` for visual validation cases where before and after screenshots cannot be compared safely, including changed target-window geometry. `result_gui_evidence()` also counts `confirmed` GUI evidence statuses as observed evidence, which keeps the animation evidence summary aligned with the current `guarded_click_profile_confirmed_for_autocomp_r13` record.

## Final R0 To R5 Verification

```powershell
python -m pytest tests\test_p0_contracts.py tests\test_agent_system.py tests\test_agent_runtime.py -q --basetemp=tmp\pytest_r5_acceptance_focus
```

Result: `22 passed`.

```powershell
python -m pytest -q --basetemp=tmp\pytest_r5_final_full_clean
```

Final result after the result-review acceptance fix: `151 passed`.

```powershell
python -m autoform_agent.cli public-release-scan
```

Result: `safe_to_publish: true`, `finding_count: 0`, `.env` not present in the repository root.

Forbidden phrasing, placeholder, obsolete usage-module reference and legacy Agents SDK scan across `autoform_agent`, `tests`, `docs`, `README.md`, `DEVELOPERS.md`, `frontend`, `handoff`, `schemas`, `policy` and `backend`: no matches.

Live DeepSeek direct API test using `DeepSeek_V4_API` returned `directApiCalled: true`, `directApiCallCount: 2`, `centerAgentStatus: ready`, `centerPlanSchema: autoform.center_agent.r5.v1`, `contextViewLevel: C0`, first events `user_input_received`, `task_card_created`, `route_decision`, `context_view_built`, `context_patch_proposed`, `patch_reviewed`, `agent_node_started`, and `usageTotal: 3495`. The test output intentionally omitted the raw key, key fingerprint and assistant answer text.

## Browser Demo Follow-up

The Codex in-app browser was opened at `http://127.0.0.1:8786/frontend/index.html?bridge=http&endpoint=http%3A%2F%2F127.0.0.1%3A4318%2Fapi%2Fagent&v=r5-visible-centerplan-no-fingerprint` after starting a fresh HTTP bridge on port `4318`.

The first browser run showed that an older bridge process on port `4317` could still answer requests without the visible R5 `centerPlan` contract. The demo was moved to the fresh bridge, and `frontend/app.js` was updated so the runtime response panel keeps a compact R5 `centerPlan` summary and `eventTypes` while continuing to hide raw API keys. The visible key fingerprint field now shows `configured` rather than a concrete hash.

Browser verification result on the fresh bridge:

- `directCalled: true`
- `keySource: environment:DeepSeek_V4_API`
- `centerPlan.schema_version: autoform.center_agent.r5.v1`
- `centerPlan.view_level: C0`
- `centerPlan.context_scope: center_agent_to_selected_roles`
- `selected_role_ids: manager, mcp_gateway`
- `patch_review_status: approved_low_risk`
- R5 event types: `user_input_received`, `task_card_created`, `route_decision`, `context_view_built`, `context_patch_proposed`, `patch_reviewed`, `agent_node_started`, `command_line`, `token_usage_snapshot`, `stage_summary`.

```powershell
python -m pytest frontend\tests tests\test_agent_runtime.py tests\test_agent_system.py tests\test_p0_contracts.py -q --basetemp=tmp\pytest_r5_browser_display_final
```

Result: `24 passed`.
