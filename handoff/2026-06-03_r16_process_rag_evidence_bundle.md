# R16 工艺 RAG 检索和证据包复盘

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | R16 需要过滤字段、排序解释、证据打包和 EvidenceBundle，证据包必须保留来源、适用条件和限制。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | RAG 检索 Agent 写出 EvidenceBundle、retrieval_run 和失败样例；正式字段只能通过 ContextPatch 和审批改变。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 EvidenceBundle 生成候选路线、参数和仿真计划，每个关键建议带证据、适用条件和待验证项。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R16 必须交付企业工艺检索索引、EvidenceBundle、检索评测集和冲突证据标记规则；测试覆盖证据充足、冲突、权限不足、版本过期和无结果。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R16 检索必须支持文字、材料牌号、板厚、零件族、工序、产线、缺陷类型、版本、权限和适用范围过滤。 |

## 本轮交付

| 文件 | 作用 |
| --- | --- |
| `autoform_agent/process_rag.py` | R16 工艺 RAG 检索器和评测函数。 |
| `schemas/process_rag_evidence_bundle.schema.json` | R16 扩展 EvidenceBundle schema。 |
| `data/rag/enterprise/r16_process_rag_eval_queries.jsonl` | R16 检索评测集，覆盖命中、权限过滤、无结果、许可证门禁和过期版本。 |
| `data/rag/enterprise/r16_process_rag_evidence_bundle.sample.json` | R16 样例 EvidenceBundle，记录过滤、排序、命中卡片、排除原因和正式索引门禁。 |
| `tests/test_process_rag.py` | R16 专项测试，覆盖样例复建、权限、无结果、许可证、过期版本、参数窗口冲突和评测通过。 |
| `docs/retrieval_api.md` | R16 Python 入口、过滤字段、输出字段和执行边界说明。 |
| `card_schema.yaml`、`schemas/index.md`、`data/rag/enterprise/README.md`、`docs/enterprise_data_contract.md`、`docs/beginner_onboarding_zh.md`、`docs/multi_agent_architecture.md`、`source_registry.csv` | 同步 R16 资产和后续 R17 边界。 |

## 关键判断

R16 的价值在于把 R15 候选知识卡从静态样例推进为可查询、可解释、可评测的证据包。当前检索器不追求召回规模，优先建立过滤、排序解释、排除原因、权限、版本、许可证和冲突状态这些边界字段。这样做能让后续 R17 工艺规划 Agent 使用证据时知道每个候选值的来源、限制和复核状态。

当前样例 EvidenceBundle 命中 2 张卡，`formal_index_allowed_count=0`，`confidence=low`，`human_review_status=required`。这表示系统已经能组织证据，但企业负责人、许可证、真实材料曲线、真实产线范围和质量阈值仍未补齐，R17 只能生成候选工艺规划输入。

## 验证记录

- `python -m pytest tests\test_process_rag.py -q`：9 passed。
- `python -m pytest tests\test_enterprise_data_contract.py tests\test_process_knowledge_cards.py tests\test_process_rag.py -q`：30 passed。
- `python -m pytest -q --basetemp tmp\pytest_r16_full`：198 passed。
- `python -m autoform_agent.cli public-release-scan`：`safe_to_publish=true`，`finding_count=0`。
- 本轮 R16 触碰路径执行 `git diff --check -- <R16 paths>`：通过。
- 本轮 R16 触碰路径执行文本规则扫描：未命中禁止句式和异常占位。
- 全局 `git diff --check` 仍报告既有改动 `apps/workbench/styles.css:475` 与 `start_autoform_agent.ps1:327` 的 EOF 空行问题；这两个文件不在本轮 R16 修改范围。

## 后续建议

1. R17 先读取 R16 EvidenceBundle 生成候选 `ProcessPlanCard` 和候选 `ContextPatch`，保持人工确认门禁。
2. 补企业内部真实数据时，优先补能让 `formal_index_allowed_count` 从 0 增加的负责人确认、许可证、版本和适用范围字段。
3. 后续扩展检索时先加评测样例，再加召回逻辑，保证每个新增来源都能解释排序和排除原因。
