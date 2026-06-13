# R15 结构化工艺知识卡复盘

## 已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | RAG 数据库需要卡片 schema、来源、版本、适用条件、许可状态和 EvidenceBundle 回挂；材料、规则、案例和证据卡都要保留来源和审核状态。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | MaterialCard 需要材料牌号、板厚、曲线引用、FLC、r 值、n 值、来源和审核状态，高风险材料字段要求人工确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 工艺规划 Agent 读取 MaterialCard 与 EvidenceBundle，输出 OperationRoute、ParameterCandidate 和 SimulationPlan 候选；关键建议必须保留证据、适用条件和待验证项。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02 23:04:44` | R15 必须交付 ProcessKnowledgeCard schema、知识卡生成器、校验器和企业案例转换 fixture；测试覆盖字段完整性、证据缺失、适用范围冲突和过期知识卡。 |
| `docs/multi_agent_architecture.md` | 当前仓库文件 | R15 对象范围为 `MaterialCard`、`OperationRoute`、`ParameterWindow`、`ProcessCase` 和 `QualityCriteria`，每张卡需要 `evidence_refs`、`source_id`、`version`、`applicability`、`limitation`、`review_status` 和 `owner`。 |

## 本轮交付

| 文件 | 作用 |
| --- | --- |
| `schemas/process_knowledge_card.schema.json` | R15 `ProcessKnowledgeCard` schema，覆盖来源、证据、版本、适用范围、参数窗口、质量风险和人工确认字段。 |
| `autoform_agent/process_knowledge.py` | R15 知识卡生成器和校验器，可从 R14 清洗记录生成候选卡，并判断正式检索索引准入状态。 |
| `data/rag/enterprise/r15_process_knowledge_cards.sample.json` | R15 样例 fixture，包含 6 张卡，覆盖五类卡片对象。 |
| `tests/test_process_knowledge_cards.py` | R15 专项测试，覆盖生成复现、字段完整性、材料曲线、参数窗口、质量阈值、证据缺失、适用范围冲突、过期卡和 arXiv 许可证门禁。 |
| `card_schema.yaml`、`schemas/index.md`、`data/rag/enterprise/README.md`、`docs/enterprise_data_contract.md`、`docs/beginner_onboarding_zh.md`、`docs/multi_agent_architecture.md` | 同步新增 R15 资产说明和后续 R16 边界。 |

## 关键判断

R15 的价值在于把已清洗数据转化为可审计、可复建、可阻断的候选知识对象。当前内部样本只包含 DC04、1.0 mm 和 D-20 工序片段，不能支撑正式工艺参数结论；因此本轮所有卡片的正式检索索引准入数保持为 0。这样做可以让 R16 检索先依赖明确的证据、单位、适用范围和审核状态，再考虑排序、过滤和证据包扩展。

arXiv 单条元数据样本已经通过 R14 清洗，但 license 字段为空。本轮把它转换为 `ProcessCase` 类型的目录用途卡，并标记 `needs_license_review` 与 `catalog_only`。该卡可以测试公开元数据如何被追溯和阻断，不能作为企业工艺建议或参数窗口的正式依据。

## 验证记录

- `python -m pytest tests\test_process_knowledge_cards.py -q`：10 passed。
- `python -m pytest tests\test_process_knowledge_cards.py tests\test_enterprise_data_contract.py -q`：21 passed。
- `python -m pytest -q --basetemp tmp\pytest_r15_full`：189 passed。
- `python -m autoform_agent.cli public-release-scan`：`safe_to_publish=true`，`finding_count=0`。
- 本轮触碰文件执行 `git diff --check -- <R15 paths>`：通过。
- 全局 `git diff --check` 仍报告既有改动 `apps/workbench/styles.css:475` 与 `start_autoform_agent.ps1:327` 的 EOF 空行问题；这两个文件不在本轮 R15 修改范围。

## 后续建议

1. R16 启动前补企业问题集和检索评测，先围绕材料牌号、板厚、工序、质量风险、权限和版本过滤构造黄金样例。
2. 公开来源继续逐条做许可证复核，许可证缺失的卡片只能保留目录用途。
3. 企业内部数据接入时优先补真实材料曲线、产线适用范围、质量阈值和负责人确认记录，再把 `review_status` 推进到可检索状态。
