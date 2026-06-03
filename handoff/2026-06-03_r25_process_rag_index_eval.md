# R25 process RAG candidate index retrieval evaluation

## 本轮结论

本轮完成 R25 候选索引检索评测门禁。R25 在 R24 `ProcessRagCandidateIndexSnapshot` 上增加小样本检索评测集和评测报告，验证候选索引在不写正式索引、不计算 embedding、不训练神经网络、不批量采集的前提下，能否按结构化过滤和关键词评分返回可解释命中。

本轮还修复了 3 个候选卡 `card_id` 冲突。冲突来自 `enterprise_data/r21_public_process_chain_cards.candidate.json` 与 `enterprise_data/r21_nist_pdr_process_chain_cards.candidate.json` 的 NIST PDR process-chain 候选卡同名编号。修复后，R24 快照中 37 个 `card_id` 和 37 个 `entry_id` 均唯一。

## 已读 DOCX 与采用结论

读取方式：使用 `python-docx` 只读抽取段落和文件时间戳，未改写 DOCX。

| 路径 | 时间戳 | 采用结论 | 仍需验证 |
| --- | ---: | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06+08:00` | 中心 Agent 负责入口、任务图、状态治理和质量门控，专业 Agent 输出 RAG 等候选产物。R25 保持候选检索评测输出，不进入正式工程状态。 | R25 报告接入中心 Agent 审计事件的字段映射仍需后续补齐。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | RAG 输出作为证据候选、参数候选和规则候选，进入正式状态前需要 ContextPatch、规则校验、仿真验证或人工确认。R25 只评测候选索引召回和排序解释。 | PostgreSQL、pgvector、对象存储和 OpenSearch 选型仍需工程确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 正式字段只能通过 ContextPatch 改变，补丁需要目标路径、候选值、证据、风险、影响和回滚方式。R25 不生成 ContextPatch。 | 检索命中到 ContextPatch 候选字段的映射仍需验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_材料Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 材料 Agent 输出 MaterialCard、EvidenceBundle、MaterialPatch 和 ReviewRequest。R25 保留材料相关候选命中的证据与人工复核门禁。 | 材料曲线进入正式索引的 owner 和许可门禁仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 几何与数据 Agent 可以请求 RAG 形成候选建议，正式写回需要用户或责任工程师确认。R25 只提供可解释候选检索命中。 | CAD、零件族和测量数据的脱敏索引字段仍需确认。 |
| `VC开发文档/Auto_Autoform思路整理/03_需求与工艺判定Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 路由策略需要说明何时交给 RAG、材料、几何、工艺或人工节点。R25 增加权限过滤失败样例，支持路由门禁判断。 | 低置信证据的判定阈值仍需更大评测集支持。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07+08:00` | 工艺规划 Agent 读取 EvidenceBundle 生成候选路线、参数和仿真计划；RAG 召回按材料、缺陷、工具、案例和跨阶段方案分配不同检索配方。R25 先验证候选索引排序解释。 | R25 命中结果转 R16 EvidenceBundle 后的排序阈值仍需后续评测。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230+08:00` | 所有材料、工艺和脚本建议保持候选状态，正式写入必须经过 ContextPatch、Validator、证据检查和人工确认策略。R25 将该边界写入 blocked_actions。 | 正式索引的审批责任矩阵仍需补齐。 |

## 新增与更新资产

| 文件 | SHA256 | 用途 |
| --- | --- | --- |
| `autoform_agent/process_rag_index_eval.py` | 由 git 管理 | R25 候选索引检索、评测和报告校验函数。 |
| `enterprise_data/r25_process_rag_index_eval_queries.jsonl` | `6b18ab044e428415b6eabcf54e107c1a040ba7cc9771b3e386d875495240fad2` | 6 条候选索引评测查询。 |
| `enterprise_data/r25_process_rag_index_eval_report.sample.json` | `339764a740e1d7aad063ae4921b7a7730fc8c02e1c81be6fbff1847148a83c3c` | R25 评测报告样例。 |
| `schemas/process_rag_index_eval_report.schema.json` | `32e3d083eab7d889296bef9c03ace3eea602845397e293b2de978b68cb7f5db2` | R25 评测报告 schema。 |
| `enterprise_data/r24_process_rag_candidate_index.sample.json` | `137eec0699517450bf640a97d9b6caf9db11a34e2479d1999dfd7916debaa441` | 修复重复卡 ID 后重建的 R24 候选索引快照。 |
| `docs/enterprise_rag_index.md` | `2725e13c17ecbcfb57cf43c0bda7645a87606b9539711881fbc75b56920afe78` | 增加 R25 候选检索评测说明。 |

## ID 修复记录

| 原 `card_id` | 新 `card_id` | 文件 |
| --- | --- | --- |
| `pkc_r21_nist_pdr_process_chain_case_001` | `pkc_r21_nist_pdr_logistics_chain_case_001` | `enterprise_data/r21_nist_pdr_process_chain_cards.candidate.json` |
| `pkc_r21_nist_pdr_process_chain_case_002` | `pkc_r21_nist_pdr_logistics_chain_case_002` | `enterprise_data/r21_nist_pdr_process_chain_cards.candidate.json` |
| `pkc_r21_nist_pdr_process_chain_case_003` | `pkc_r21_nist_pdr_logistics_chain_case_003` | `enterprise_data/r21_nist_pdr_process_chain_cards.candidate.json` |

证据引用、`source_hash`、来源文件和清洗样本路径保持不变；本轮只修复候选卡键名冲突。

## 评测结果

R25 查询数为 6，全部通过，`average_recall_at_k=1.0`。

| 查询 | 预期命中 | 结果 |
| --- | --- | --- |
| `eval_r25_dc04_d20_blank_thickness` | R15 DC04 D-20 blank thickness 与 process case | pass |
| `eval_r25_partner_material_curve_gate` | 合作企业材料曲线输入门禁 | pass |
| `eval_r25_autoform_biw_process_chain` | AutoForm BiW assembly public page metadata | pass |
| `eval_r25_nist_manufacturing_cost_guide` | NIST Manufacturing Cost Guide metadata | pass |
| `eval_r25_nist_logistics_sysml_dels` | NIST DELS SysML logistics metadata | pass |
| `eval_r25_partner_permission_filtered` | P1 权限过滤合作企业 P3 输入 | pass |

R25 报告门禁：

- `duplicate_card_id_count=0`
- `duplicate_entry_id_count=0`
- `formal_index_allowed_count=0`
- `embedding_status=not_built`
- `training_status=not_started`

## 边界

本轮没有联网采集，没有下载 PDF、源文件、标准全文、付费内容或受保护文档，没有写入正式索引，没有计算 embedding，没有训练神经网络，没有触发求解器、GUI 控制或正式工程状态写入。

R25 `blocked_actions` 保留：

- `bulk_crawl`
- `bulk_download`
- `auto_ingest`
- `compute_embedding`
- `train_neural_index`
- `write_formal_index`
- `write_formal_engineering_state`
- `submit_solver`
- `control_gui`

## 后续门禁

1. R26 可把 R25 命中结果转换为 R16 EvidenceBundle 评测集，检查证据包字段、排序解释、冲突状态和人工复核字段。
2. 正式索引写入前，需要 owner、许可证、保密等级、适用范围、质量阈值和审批责任矩阵全部通过复核。
3. embedding 或神经网络索引应等待 R25/R26 评测暴露稳定误召回模式，并确认训练数据许可和模型版本治理。
4. 合作企业输入接口需要继续保留撤回、保密、缓存范围、责任人和协议状态字段。

## 价值判断

R25 的价值在于把“索引结构看起来完整”推进到“候选索引可被评测和审计”。本轮没有扩大数据量，而是先建立唯一键门禁、可解释排序、权限过滤失败样例和 hash 回链检查。后续数据量增加时，系统可以先用 R25 评测暴露重复键、误召回、权限过滤和证据缺失问题，再决定是否进入向量库和正式索引审批。这样沉淀的资产具有复用性：查询集、报告 schema、检索 trace 和 blocked_actions 可以反复用于后续来源扩量、合作企业输入和正式索引上线前审查。

## 新手入口检查

本轮没有修改启动方式、CLI、MCP 入口、前端入口、README 中的新手操作或目录结构。已检查 `docs/beginner_onboarding_zh.md`，无需同步调整。
