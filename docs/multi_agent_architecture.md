# AutoForm Agent 多 Agent 项目结构预留说明

本文档说明本项目后续扩展为完整 AutoForm 多 Agent 系统时的文件区域、接口契约和维护边界。本文依据当前仓库中的 `autoform_agent/agent_runtime.py`、`autoform_agent/agent_system/`、`autoform_agent/mcp_server.py`、`autoform_agent/mcp_tools/`、`autoform_agent/cli.py`、`DEVELOPERS.md` 和 `docs/api_runtime_call_chain.md` 编写。

## 一、总体定位

当前项目已经具备三类入口：CLI、可选 MCP server、以及本地 HTTP bridge 调用的 Python 后端运行时。多 Agent 项目区域位于：

```text
autoform_agent/agent_system/
```

该目录保存多 Agent 系统的稳定契约、默认角色注册表、R5 中心 Agent 内核和 Agent 工具网关。MCP 既是外部 host 调用工具的 gateway 入口，也作为内部 Agent 复用 MCP 同源工具的受控边界；具体 MCP wrapper 继续放在 `autoform_agent/mcp_tools/`。R6 至 R11 的低风险准备链路由 `autoform_agent/preparation_agents.py` 承担，包含需求分诊、几何数据、RAG 证据、材料候选、工艺候选、低风险脚本和端到端回放。

## 二、已预留文件

`autoform_agent/agent_system/contracts.py` 定义共享数据结构：

- `AgentRoleSpec`：描述一个 Agent 角色的 id、显示名称、职责、源码依据、默认工具和可交接目标。
- `AgentSystemRequest`：描述一次多 Agent turn 的输入，包括 prompt、显式请求角色和调用上下文。
- `AgentSystemPlan`：描述路由预览结果，包括已选角色、未知角色、执行模式、说明和集成点。

`autoform_agent/agent_system/registry.py` 定义默认角色注册表。当前登记 15 个角色：

| Role id | 用途 | 依据文件 |
| --- | --- | --- |
| `manager` | 理解用户目标、分派专业 Agent、汇总证据和最终答复 | `autoform_agent/agent_runtime.py`、`docs/api_runtime_call_chain.md` |
| `installation` | 安装发现、环境快照、队列状态、日志和诊断包计划 | `paths.py`、`diagnostics.py`、`config.py`、`queue.py` |
| `project_workflow` | 工程解析、示例工程、GUI 打开和可复现运行链路 | `project_workflow.py`、`process.py`、`inventory.py` |
| `solver` | 求解器、后处理、批量探测和显式执行边界 | `solver.py`、`tests/test_solver.py` |
| `result_review` | GUI 后处理路线、结果栏目、视角、视角取证、动画和截图证据 | `result_viewer.py`、`gui_automation.py`、`mcp_tools/gui.py`、`tests/test_result_viewer.py` |
| `quicklink` | QuickLink bridge、导出解析和规范化结构 | `quicklink.py`、`quicklink_bridge.py`、`tests/test_quicklink.py` |
| `materials` | 材料文件检查、安装、备份和去重 | `materials.py`、`tests/test_materials.py` |
| `demand_triage_agent` | 需求分诊、缺失项和后续专业 Agent 路由 | `preparation_agents.py`、`tests/test_preparation_agents.py` |
| `geometry_data_agent` | PartCard、DataChecklist、CandidateValue 和候选补丁 | `preparation_agents.py`、`tests/test_preparation_agents.py` |
| `rag_evidence_agent` | source registry、最小检索评测和 EvidenceBundle | `preparation_agents.py`、`source_registry.csv`、`eval_queries.jsonl` |
| `material_agent` | MaterialCard、MaterialGapList、MaterialPatch 和 ReviewRequest | `preparation_agents.py`、`tests/test_preparation_agents.py` |
| `process_planning_agent` | ProcessPlanCard、OperationRoute、ParameterCandidate 和 SimulationPlan | `preparation_agents.py`、`tests/test_preparation_agents.py` |
| `script_agent` | L0 至 L2 低风险脚本登记、运行记录和失败摘要 | `preparation_agents.py`、`script_registry.yaml` |
| `reporting` | 结果证据、报告模板、发布检查和交付包计划 | `results.py`、`report.py`、`release.py`、`safety.py` |
| `mcp_gateway` | 外部 MCP host 请求和内部 Agent 工具意图与 MCP 同源工具层之间的映射 | `mcp_server.py`、`mcp_tools/__init__.py`、`agent_system/tool_gateway.py`、`tests/test_mcp_tools.py` |

补充说明：`result_review` 角色的默认工具包括 `autoform_gui_control_demo`、`autoform_result_gui_evidence`、`autoform_result_blockers` 和 `autoform_result_view_evidence`，用于读取 R12 基础可见窗口控制演示边界、本机 GUI 控件证据、证据文件存在性、V1.1 卡点、V1.2 延后项、推荐对策、需要用户协助的事项、AutoForm R13 视角菜单名和视角切换前后截图计划。

`autoform_agent/agent_system/orchestrator.py` 提供 `plan_agent_system_turn()`。该函数当前只做确定性路由预览，返回结构化 JSON，便于测试和文档核对。后续接入真实多 Agent 执行器时，应保持该函数的输入输出契约稳定。

`autoform_agent/agent_system/kernel.py` 提供 `build_center_agent_plan()` 和 `validate_context_patch()`。该内核会为一次 prompt 生成 `TaskCard`、任务 DAG、标记为 `C0` 的中心上下文视图、候选 `ContextPatch`、补丁审查结果和 `AuditEvent`。它满足 R5 对中心 Agent、Task DAG、Agent Router、Context View Builder、ContextPatch Validator 和 AuditEvent 的最低可执行契约要求。

`autoform_agent/agent_system/tool_gateway.py` 提供 `AgentToolGateway`。该网关把中心 Agent 或专业子 Agent 的工具意图映射到 `autoform_agent.mcp_tools` 中的 MCP 同源 wrapper，并统一检查调用角色、工具白名单、受控参数和显式批准状态。R5 默认允许只读和规划工具；涉及 AutoForm 窗口控制、截图、打开工程或真实求解的参数会返回 `blocked_requires_approval`。

## 三、命令行检查入口

查看当前角色注册表：

```powershell
python -m autoform_agent.cli agent-roles
```

预览一次多 Agent 路由：

```powershell
python -m autoform_agent.cli agent-system-plan "请检查 QuickLink 导出并规划求解结果报告"
```

显式指定角色：

```powershell
python -m autoform_agent.cli agent-system-plan "请整理材料库" --role materials
```

构建 R5 中心 Agent 计划：

```powershell
python -m autoform_agent.cli agent-center-plan "请让中心 Agent 通过 MCP 检查 AutoForm 状态并规划打开结果工程"
```

上述命令只读取本仓库内的角色定义和 MCP 同源工具策略，不执行 AutoForm 求解器，不调用外部模型。

检查 R6 至 R11 低风险准备链路：

```powershell
python -m autoform_agent.cli prepare-triage "DC04 板厚 1.0 mm 低风险准备"
python -m autoform_agent.cli prepare-evidence "材料 工艺 低风险 权限"
python -m autoform_agent.cli prepare-script-run skill_readiness_echo --param task_id=task_r11_prepare_demo --param evidence_bundle_id=evidence_rag_minimal_autoform_prepare
python -m autoform_agent.cli prepare-r11-replay "低风险准备：DC04，板厚 1.0 mm，先形成候选材料、工艺和脚本检查，不执行真实求解。"
```

前端工作台可用 `?fixture=../fixtures/r11_low_risk_prepare_events.jsonl` 加载 R11 回放 fixture。

## 四、后续扩展规则

新增 Agent 角色时，先在对应业务模块中补充可测试函数，再在 `autoform_agent/agent_system/registry.py` 增加 `AgentRoleSpec`。每个角色必须填写 `source_files`，并且这些路径应能在当前仓库中找到。

新增真实多 Agent 执行器时，建议先复用 `build_center_agent_plan()` 的输出对象，再按需要扩展独立运行模块，例如 `autoform_agent/agent_system/runtime.py`。该模块应接收 `AgentSystemRequest`，读取 `AgentRoleRegistry`，并返回 `AgentSystemPlan` 或后续扩展后的结果对象。执行器可以调用 `autoform_agent.agent_runtime`、`AgentToolGateway` 或业务模块函数，但应保留 dry run、受控参数和显式批准状态。

新增外部 MCP 能力时，继续在 `autoform_agent/mcp_tools/` 中维护工具 wrapper，并同步更新 `mcp_gateway` 角色的 `source_files` 或 `default_tools`。如果该工具需要被中心 Agent 或子 Agent 调用，还应在 `AgentToolGateway` 中增加 `GatewayToolSpec`，写明 owner agent、风险等级、默认参数、受控参数和是否需要批准。

## 五、R13 至 R20 规划与验收标准

2026-06-02 R12 基础可见窗口控制演示已经形成独立关闭证据，详见 `handoff/2026-06-02_r12_closure_enterprise_rag_followups.md`。R12 之后的后续 R 按两组推进：R13 至 R17 单独作为企业工艺数据和工艺 RAG 组，R18 至 R20 单独作为实时多 Agent 执行器组。

R13 至 R17 固定为企业工艺数据和工艺 RAG 规划阶段。该阶段只允许生成结构化数据、证据包、候选卡片和候选补丁；进入正式工程字段、真实 AutoForm 求解或真实 GUI 操作时，仍然必须经过中心 Agent 审查、`ContextPatch` 审批和 `AgentToolGateway` 执行边界。

2026-06-03 起，R13 按“数据目录和来源白名单”模式启动。当前只登记来源元数据、企业数据接口契约、小批量清洗样本和校验函数；批量网页爬取、批量文件下载和自动入库暂不开放。对应物理资产为 `enterprise_data/`、`schemas/enterprise_data_contract.schema.json`、`schemas/enterprise_source_whitelist.schema.json`、`schemas/enterprise_ingestion_record.schema.json` 和 `autoform_agent/enterprise_data.py`。

2026-06-03 同日，R15 已补最小结构化知识卡契约。对应物理资产为 `schemas/process_knowledge_card.schema.json`、`enterprise_data/r15_process_knowledge_cards.sample.json`、`autoform_agent/process_knowledge.py` 和 `tests/test_process_knowledge_cards.py`。当前卡片均保持候选、人工确认或许可证复核状态，正式检索索引准入数量为 0；R16 只能在许可证、负责人、适用范围和证据评测补齐后使用这些卡片扩展 EvidenceBundle。

2026-06-03 同日，R16 已补最小工艺 RAG 检索和证据包闭环。对应物理资产为 `autoform_agent/process_rag.py`、`schemas/process_rag_evidence_bundle.schema.json`、`enterprise_data/r16_process_rag_eval_queries.jsonl`、`enterprise_data/r16_process_rag_evidence_bundle.sample.json`、`docs/retrieval_api.md` 和 `tests/test_process_rag.py`。当前检索支持文字、材料、板厚、工序、零件特征、产线、风险、来源、权限、审核状态和有效期过滤；输出仍保持 `review_status=candidate`、`human_review_status=required`，并阻断正式工程写入、真实求解和 GUI 控制。

2026-06-03 同日，R17 已补最小企业证据驱动工艺规划候选闭环。对应物理资产为 `autoform_agent/enterprise_process_planning.py`、`schemas/enterprise_process_planning_result.schema.json`、`enterprise_data/r17_enterprise_process_plan_candidate.sample.json`、`docs/enterprise_process_planning.md` 和 `tests/test_enterprise_process_planning.py`。当前输出包含候选 `ProcessPlanCard`、候选 `ContextPatch` 和 `ReviewRequest`，保持 `will_submit_solver=false`、`will_control_gui=false`；证据冲突、缺材料曲线、缺产线适用范围和人工拒绝均会阻断合并或进入回滚记录。

2026-06-03 同日，R18 已补最小实时执行器骨架。对应物理资产为 `autoform_agent/agent_system/runtime.py`、`schemas/realtime_executor_run.schema.json`、`fixtures/r18_realtime_executor_events.jsonl`、`docs/realtime_executor.md` 和 `tests/test_agent_system_runtime.py`。当前执行器接收 `AgentSystemRequest` 或中心计划，按 DAG 逐步输出 `RunEvent`，支持成功、失败、暂停、恢复、人工确认等待和事件顺序校验；执行边界保持 `will_submit_solver=false`、`will_control_gui=false`。

2026-06-03 同日，R19 已补可用实时多 Agent 执行器的最小工具联动切片。对应物理资产为 `autoform_agent/agent_system/runtime.py`、`schemas/realtime_multi_agent_executor_run.schema.json`、`fixtures/r19_realtime_multi_agent_executor_events.jsonl`、`frontend/app.js`、`docs/realtime_executor.md` 和 `tests/test_agent_system_runtime.py`。当前执行器能把节点工具意图交给 `AgentToolGateway`，保留工具名、参数摘要、审批状态、结果摘要和错误边界；前端能消费 `tool_requested`、`tool_completed`、`tool_blocked` 和审批事件，图谱状态来自事件流。

2026-06-03 同日，R20 已补企业工艺数据接入后的完整执行器闭环。对应物理资产为 `autoform_agent/enterprise_process_executor.py`、`schemas/enterprise_process_executor_run.schema.json`、`enterprise_data/r20_enterprise_process_executor_run.sample.json`、`fixtures/r20_enterprise_process_executor_events.jsonl`、`docs/enterprise_process_executor.md` 和 `tests/test_enterprise_process_executor.py`。当前执行器把 R16 `EvidenceBundle`、R17 候选工艺规划、中心补丁审查、人工确认、R19 工具事件、结果证据包和报告草案串为 `EnterpriseProcessExecutorRun`；默认保持 `will_submit_solver=false`、`will_control_gui=false` 和报告草案不发布正式工程结论。测试覆盖成功闭环、无企业数据、证据冲突、人工拒绝、执行审批缺失和前端回放 fixture。

| 阶段 | 目标 | 必交物 | 严格验收标准 | 禁止通过条件 |
| --- | --- | --- | --- | --- |
| R13 | 企业数据接口契约 | `schemas/enterprise_data_contract.schema.json`、`docs/enterprise_data_contract.md`、企业数据字段字典、权限和保密等级表、示例数据包 | 明确定义企业要交付的材料、几何、工艺路线、参数窗口、历史案例、质量规则、版本、权限、保密等级、适用范围和限制；每个字段都有类型、单位、必填规则、来源、负责人、版本和脱敏要求；新增测试必须验证有效样例、缺字段、非法权限、过期版本和保密等级违规 | 只有自然语言说明；字段缺少单位或版本；无法区分可自动建议、仅展示和必须人工确认的数据；样例数据含明文密钥、客户敏感名称或无来源字段 |
| R14 | 数据接入与清洗 | `autoform_agent/enterprise_data.py`、统一索引构建函数、CSV/JSONL/QuickLink/材料文件/历史报告/工艺表单解析入口、清洗报告 | 支持 CSV、JSONL、QuickLink 导出、材料文件、历史报告和工艺表单进入统一索引；每条记录保留来源、哈希、版本、清洗状态、错误摘要和回滚信息；测试覆盖格式有效、格式损坏、单位转换、重复记录、缺来源、权限过滤和脱敏 | 只支持单一格式；清洗过程丢失来源或版本；错误数据静默进入索引；权限不合格数据可被 RAG 检索到 |
| R15 | 结构化工艺知识卡 | `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase`、`QualityCriteria` 的 schema、生成函数和样例 fixture | 企业数据必须能转换为结构化卡片；每张卡片包含 `evidence_refs`、`source_id`、`version`、`applicability`、`limitation`、`review_status` 和 `owner`；测试覆盖材料曲线、工序路线、参数窗口、历史案例、质量阈值、冲突字段和人工确认状态 | 卡片缺少证据引用；参数没有单位或窗口边界；历史案例不能追溯到来源；质量规则直接给出工程结论且无阈值依据 |
| R16 | 工艺 RAG 检索和证据包 | 企业索引检索器、过滤器、排序解释、`EvidenceBundle` 扩展、检索评测集 | 检索必须同时支持文字、材料牌号、板厚、零件族、工序、产线、缺陷类型、版本、权限和适用范围过滤；`EvidenceBundle` 必须列出命中的来源、过滤条件、排序理由、适用边界、限制、置信度和人工复核状态；评测覆盖命中、未命中、权限过滤、版本过滤、冲突证据和低置信度返回 | 只做关键词匹配；检索结果无法解释排序；越权资料进入证据包；证据包缺少适用范围或限制；低置信度结果被当作可合并结论 |
| R17 | 工艺规划 Agent 使用企业证据生成候选 | 企业证据驱动的 `ProcessPlanCard`、`ContextPatch`、人工确认请求、R17 端到端 fixture 和测试 | `process_planning_agent` 必须使用 R16 `EvidenceBundle` 生成候选 `ProcessPlanCard` 和候选 `ContextPatch`；输出必须保持 `review_status=needs_human_confirmation` 或等效候选状态；中心 Agent 必须审查候选补丁，人工确认后才允许进入正式工程状态；测试覆盖证据充足、证据冲突、缺材料曲线、缺产线适用范围、人工拒绝和回滚 | 工艺规划直接写正式状态；缺少 `ContextPatch`；证据不足时仍输出高置信度候选；人工确认前允许求解或 GUI 执行 |

R18 至 R20 才进入实时多 Agent 执行器阶段。执行器阶段必须复用 R13 至 R17 的企业数据契约和证据包，不允许绕过企业数据权限、候选补丁审查或真实执行审批边界。

| 阶段 | 目标 | 必交物 | 严格验收标准 | 禁止通过条件 |
| --- | --- | --- | --- | --- |
| R18 | 实时执行器骨架 | `autoform_agent/agent_system/runtime.py`、`schemas/realtime_executor_run.schema.json`、`fixtures/r18_realtime_executor_events.jsonl`、运行状态机、事件流、暂停和恢复接口、执行器测试 | 执行器能接收 `AgentSystemRequest`，读取中心计划，按 DAG 调度确定性专业 Agent，逐步输出 `RunEvent`；支持 `planned`、`running`、`waiting_for_human`、`blocked`、`completed` 和 `paused` 等状态；测试覆盖成功、失败、暂停、恢复、人工确认等待和事件顺序 | 只返回最终 JSON；没有逐步事件流；失败无法定位到节点；人工确认等待被跳过 |
| R19 | 可用的实时多 Agent 执行器 | 专业 Agent 调度、工具意图执行、`AgentToolGateway` 审批联动、前端实时状态显示、R19 工具事件 fixture 和测试 | 中心 Agent 能调度专业 Agent 并把工具意图交给网关；每次工具调用保留工具名、参数摘要、审批状态、结果摘要和错误边界；前端图谱状态来自 `RunEvent`；测试覆盖工具成功、审批阻断、权限不足和前端事件消费 | 模型可直接调用非白名单工具；前端只显示静态节点；工具失败只给笼统文本；真实 AutoForm 控制缺少显式审批 |
| R20 | 企业工艺数据接入后的完整执行器 | 企业工艺 RAG、实时多 Agent 执行器、候选工艺规划、结果审阅和报告草案的闭环演示 | 能从企业数据输入开始，经 RAG 检索、材料候选、工艺候选、中心审查、人工确认、受控 AutoForm 执行规划、结果证据和报告草案形成一条可复核链路；所有关键输出都有 `source_refs`、`evidence_refs`、版本、权限、候选状态和审计事件；端到端测试必须覆盖无企业数据、证据冲突、人工拒绝、执行审批缺失和成功闭环 | 企业资料未接入仍宣称完整；候选状态和正式状态混用；真实求解、GUI 操作或报告结论绕过审批；无法从最终结果追溯到企业数据来源 |

## 六、检查要求

多 Agent 相关修改后至少运行：

```powershell
python -m pytest tests\test_agent_system.py tests\test_agent_runtime.py tests\test_mcp_tools.py -q
```

R13 至 R20 相关修改还必须补充并运行对应阶段的专项测试。测试文件命名应能看出阶段和责任模块，例如 `tests/test_enterprise_data_contract.py`、`tests/test_enterprise_data_ingestion.py`、`tests/test_process_knowledge_cards.py`、`tests/test_process_rag.py`、`tests/test_enterprise_process_planning.py` 或 `tests/test_agent_system_runtime.py`。

如果修改影响 CLI、文档或共享契约，还应运行：

```powershell
python -m pytest -q
```
