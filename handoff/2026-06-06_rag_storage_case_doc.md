# RAG 实际存储案例汇报文档复盘

## 本轮目标

为当前汇报准备一个可直接展示的 RAG 存储案例文档。文档需要选择当前工程中的典型来源文件，对比源文件、候选知识卡、RAG 候选索引入口和检索返回，说明数据从源记录进入库内后的处理过程和对应关系。

## 已读资料与采用结论

| 资料 | 时间戳 | 采用结论 | 仍需验证 |
| --- | ---: | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/01_项目总览与系统架构.docx` | `2026-06-01T18:14:06` | 中心 Agent 负责质量门控，专业 Agent 输出 RAG、材料、几何和工艺候选产物。 | 候选索引接入中心 Agent 审计事件仍需联调。 |
| `VC开发文档/Auto_Autoform思路整理/02_RAG工艺数据库详细架构计划与任务目标.docx` | `2026-06-01T18:14:07` | RAG 输出为证据候选、参数候选和规则候选，正式状态前需要 ContextPatch、规则校验、仿真验证或人工确认。 | 正式数据库、向量库和对象存储选型仍需工程确认。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01T18:14:07` | 长文本、CAD、PDF 正文和历史对话以引用保留，正式字段变更由 ContextPatch 管理。 | 索引命中到 ContextPatch 字段的映射仍需验收。 |
| `VC开发文档/Auto_Autoform思路整理/03_工艺规划Agent详细架构计划与任务目标.docx` | `2026-06-01T18:14:07` | 工艺规划 Agent 读取 EvidenceBundle 后生成候选路线、参数和仿真计划。 | RAG 命中转工艺规划候选卡的排序阈值仍需评测。 |
| `VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx` | `2026-06-02T23:04:44.570230` | R13 至 R17 作为企业数据和工艺 RAG 阶段，材料和工艺建议保持候选状态。 | 正式索引审批责任矩阵仍需补齐。 |
| `handoff/2026-06-03_r15_process_knowledge_cards.md` | 当前仓库文件 | R15 将清洗数据转为可审计、可复建、可阻断的候选知识对象。 | 后续真实企业数据仍需补 owner、许可、产线、质量阈值和材料曲线。 |
| `handoff/2026-06-03_r16_process_rag_evidence_bundle.md` | 当前仓库文件 | R16 把候选知识卡推进为可查询、可解释、可评测的 EvidenceBundle。 | R17 及后续阶段仍需保持人工确认门禁。 |
| `handoff/2026-06-03_r24_process_rag_candidate_index.md` | 当前仓库文件 | R24 生成 37 条候选入口，四层索引视图包含结构化过滤、关键词、向量计划和证据图。 | 正式索引写入需要 owner、许可证、保密和适用范围复核。 |
| `handoff/2026-06-03_r25_process_rag_index_eval.md` | 当前仓库文件 | R25 增加候选索引评测门禁，DC04/D-20 查询样例为 pass。 | 扩量后仍需复用唯一键、权限过滤和回源检查。 |

## 案例选择

推荐使用 `data/rag/enterprise/r14_small_batch_samples.jsonl` 的 DC04/D-20 小样本。该文件只有两条 JSONL 记录，分别对应材料属性和工艺路线，字段足够短，适合投影展示；进入 RAG 后覆盖 MaterialCard、OperationRoute、ParameterWindow 和 ProcessCase 四类对象，链路能连接 R15、R16、R24 和 R25。

该案例的价值在于把“源记录是什么”“库里存成什么”“检索时怎样命中”连成同一条证据链。相比公开网页元数据样例，它更贴近 AutoForm 工艺准备语境；相比更大的 NIST 元数据样例，它更适合在汇报现场逐字段讲清楚。

## 生成资产

| 文件 | 作用 |
| --- | --- |
| `output/doc/AutoForm_RAG实际存储案例_DC04_D20_20260606_210953.docx` | 最终汇报 DOCX，包含 53 个段落、8 张表、2 张流程与映射配图。 |
| `tmp/build_rag_storage_case_doc.py` | 文档与图片生成脚本。 |
| `tmp/check_rag_storage_case_doc.py` | 文本结构、禁止句式和关键字段检查脚本。 |
| `tmp/rag_storage_case_doc/rag_storage_flow.png` | 源文件到候选索引和检索返回流程图。 |
| `tmp/rag_storage_case_doc/rag_storage_mapping.png` | 源记录、知识卡、索引入口和门禁状态映射图。 |
| `tmp/docx_checks/AutoForm_RAG_storage_case_DC04_D20_text.txt` | DOCX 文本和表格抽取结果。 |

## 核查记录

- 文本结构检查：`paragraph_count=53`，`table_count=8`，关键字段无缺失。
- 表述检查：禁止句式和异常占位命中数为 0。
- 字体 XML 检查：`wrong_font_binding_count=0`；中文正文绑定为 `宋体`，中文标题绑定为 `黑体`，西文与数字绑定为 `Times New Roman` 或代码段 `Consolas`。
- 图片检查：DOCX 内含 2 张图片；两张 PNG 均非空，人工视觉抽查未见明显重叠。
- RAG 证据检查：R24 快照校验 `status=pass`、`entry_count=37`、`formal_index_allowed_count=0`、`embedding_status=not_built`、`training_status=not_started`。
- 版式渲染检查：本机有 Word COM 16.0 和 `pdftoppm`，缺少 `soffice`/`libreoffice`。Word COM 导出 PDF 超过 120 秒未完成，未取得 PDF 页面图；已结束本轮启动的隐藏 Word 进程，保留用户此前打开的 Word 窗口。最终版式仍需在 Word 或可稳定渲染 DOCX 的环境中复核。

## 价值判断

本轮文档把工程内可复用的 RAG 方法压缩成一个小案例：来源登记、清洗、哈希、候选卡、候选索引、证据图、检索 trace 和评测门禁都落在真实文件上。汇报时可以直接展示库内 JSON 字段，说明当前系统的核心能力是证据链治理和候选状态管控；向量库、embedding 和正式工程写入仍处于门禁之后。

该材料的差异化在于把普通问答式 RAG 容易省略的权限、许可、哈希和人工确认字段显式呈现。后续换成合作企业信封、AutoForm 公开页元数据或 NIST 元数据时，可以沿用相同讲法，只替换源文件、卡片类型和评测查询。
