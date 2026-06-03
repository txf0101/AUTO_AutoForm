# 2026-06-02 R0 至 R11 逐层核查报告

> 本报告记录补齐 R6 至 R11 之前的逐层核查结果。补齐后的验收结论见 `handoff/2026-06-02_r6_r11_completion.md`。

## 核查依据

- 主计划 DOCX：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，本轮读取时间戳为 `2026-06-01 20:48:15`。
- 主计划表 1 和表 4 给出 R0 至 R11 的交付物与验收口径。
- 仓库证据来自当前文件、测试、fixture、CLI 输出和发布扫描。

## 总体结论

R0 至 R5 已经具备可执行验收链，可以按 P0 完成状态看待。R6 至 R11 尚未达到主计划验收定义，目前主要处于命名、权限、角色和低风险 fixture 预留状态。R12 基础可见窗口控制演示切片属于在 R5 网关边界上的受控预留演示，不能代表 R6 至 R11 已完成。

## 逐层结果

| 轮次 | 主计划目标 | 当前状态 | 核查依据 |
| --- | --- | --- | --- |
| R0 | 旧页面隔离与污染源清理 | 通过 | `docs/deprecated_ui_inventory.md`、`docs/ui_context_boundary.md` 存在；旧页面标记扫描只在隔离清单命中 |
| R1 | 项目骨架和全局契约 | 通过 | `repo_scaffold.md`、`naming_policy.md`、`schemas/index.md`、`policy/permission_matrix.md` 和 P0 目录存在 |
| R2 | 事件、状态和样例数据 | 通过 | `schemas/ui_event_schema.json`、`TaskCard`、`ContextPatch`、`EvidenceBundle`、`TokenUsageSnapshot` 和 `fixtures/run_events_demo.jsonl` 存在；fixture 顺序测试通过 |
| R3 | 黑白静态 UI 与本地回放 | 通过 | `frontend/tests` pytest 通过；Node smoke test 返回 `frontend smoke test passed` |
| R4 | 后端事件网关与凭据边界 | 通过 | 凭据、HTTP bridge、runtime events、provider connection 聚焦测试通过；发布扫描无泄漏 |
| R5 | 中心 Agent 与上下文内核 | 通过 | `agent-center-plan` 返回 `TaskCard`、`C0 ContextView`、MCP Gateway 边界；R5 聚焦测试通过 |
| R6 | 需求判定与几何数据 Agent | 未完成 | `DemandTriageCard` 只出现在 P0 fixture 的 requested outputs；`MissingInfoChecklist` 无命中；`PartCard`、`DataChecklist`、`CandidateValue` 只在命名和权限文档中出现 |
| R7 | 来源登记、RAG 最小检索与证据包 | 未完成 | `source_registry.csv`、`card_schema.yaml`、`eval_queries.jsonl` 不存在；当前只有 P0 `EvidenceBundle` schema 和 fixture |
| R8 | 材料 Agent | 未完成 | `MaterialCard`、`MaterialGapList`、`MaterialPatch`、`ReviewRequest` 只在命名或权限文档中出现，无独立 Agent、schema 和验收测试 |
| R9 | 工艺规划 Agent | 未完成 | `ProcessPlanCard`、`ParameterCandidate`、`SimulationPlan` 只在权限文档中出现；`OperationRoute` 无命中 |
| R10 | 柔性脚本 L0 至 L2 | 未完成 | `script_registry.yaml` 不存在；`SkillCard`、`ScriptRunRecord`、`FailureSummary` 只在命名或权限文档中出现 |
| R11 | 低风险端到端回放 | 未完成 | `evals/e2e_prepare_case.json` 存在，P0 fixture 有 `StageSummary`；`handoff/ui_prepare_report.md` 不存在，fixture 不包含材料 Agent 和工艺规划 Agent 的完整事件闭环 |

## 命令证据

```powershell
python -m pytest tests\test_p0_contracts.py -q --basetemp=tmp\pytest_verify_r0_r2_p0_contracts
```

结果：`6 passed`。

```powershell
python -m pytest frontend\tests -q --basetemp=tmp\pytest_verify_r3_frontend
```

结果：`2 passed`。

```powershell
node frontend\tests\smoke-test.mjs
```

结果：`frontend smoke test passed`。

```powershell
python -m pytest tests\test_credentials.py tests\test_http_bridge.py tests\test_runtime_events.py tests\test_provider_connection.py -q --basetemp=tmp\pytest_verify_r4_credentials_events
```

结果：`11 passed`。

```powershell
python -m pytest tests\test_agent_system.py tests\test_agent_runtime.py -q --basetemp=tmp\pytest_verify_r5_center_agent
```

结果：`17 passed`。

```powershell
python -m pytest -q --basetemp=tmp\pytest_verify_r0_r12_full
```

结果：`156 passed`。

```powershell
python -m autoform_agent.cli public-release-scan
```

结果：`safe_to_publish=true`，`finding_count=0`。

## 当前判断

R12 之前不能整体标记为完成。工程上已经完成的是 R0 至 R5 的基础治理、事件、UI、凭据边界和中心 Agent 网关。R6 至 R11 是后续主线，需要依次补专业 Agent、RAG 来源登记、材料 Agent、工艺规划 Agent、低风险脚本和完整端到端回放。

## 建议顺序

1. 先补 R6：实现 `DemandTriageCard`、`MissingInfoChecklist`、`PartCard`、`DataChecklist` 和 `CandidateValue`，并新增缺字段、异常单位和完整样例测试。
2. 再补 R7：建立 `source_registry.csv`、`card_schema.yaml`、`eval_queries.jsonl` 和可重复 EvidenceBundle 检索评测。
3. R8 与 R9 必须绑定 R7 的证据包输出，避免无来源候选进入材料和工艺建议。
4. R10 只做 L0 至 L2 低风险脚本，先建 `script_registry.yaml`、`ConsoleLine` 和失败摘要测试。
5. R11 用一条低风险端到端 fixture 串起 UI、中心、需求、几何、RAG、材料、工艺和脚本事件，再生成 `handoff/ui_prepare_report.md`。
