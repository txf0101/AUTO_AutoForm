# 2026-06-02 R13至R20 DOCX计划追加复盘

## 修改对象

- 目标文件：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`。
- 写入前时间戳：`2026-06-01 20:48:15`。
- 写入后时间戳：`2026-06-02 23:04:44`。
- 写入前备份：`tmp/docx_checks/AutoForm_multi_agent_vibecoding_plan_before_r13_r20_append.docx`。
- 写入脚本：`tmp/docx_checks/append_r13_r20_plan.py`。

## 追加内容

- 在文档末尾追加 `8. R13至R20后续开发计划和资料读取要求`。
- 新增 R13 至 R20 表格：
  - R13：企业数据接口契约。
  - R14：数据接入与清洗。
  - R15：结构化工艺知识卡。
  - R16：工艺 RAG 检索和证据包。
  - R17：工艺规划 Agent 使用企业证据生成候选。
  - R18：实时执行器骨架。
  - R19：可用的实时多 Agent 执行器。
  - R20：企业工艺数据接入后的完整执行器。
- 新增后续开发强制资料读取规则：涉及需求、架构、代码、测试、README、入门文档、复盘或交付物时，先阅读 `VC开发文档/Auto_Autoform思路整理` 中与任务相关的 DOCX 文件，并在交付说明或复盘中写明路径、时间戳、采用结论和仍需验证的问题。
- 新增资料依据表，记录用户 2026-06-02 补充指令、目标 DOCX、资料目录扫描结果、RAG 工艺数据库文档、工艺规划 Agent 文档和 `docs/multi_agent_architecture.md`。

## 项目协作约束

已同步修改根目录 `AGENTS.md`，把后续开发前读取资料目录相关 DOCX 的要求写入项目协作约束。该规则的价值在于把一次性口头要求转为后续 agent 会自动读取的项目规则，减少后续任务对资料边界和依据来源的重复确认。

## 检查结果

- 资料目录扫描：`tmp/docx_checks/autoform_thinking_docx_scan_summary.txt`，共扫描 13 个 DOCX。
- DOCX 结构抽取：`tmp/docx_checks/autoform_multi_agent_plan_after_text.txt`，抽取到 34 个段落和 8 张表。
- 关键内容确认：抽取文本包含 R13 至 R20、`2026-06-02`、`Auto_Autoform`、`Vibecoding` 和 `docs/multi_agent_architecture.md`。
- 表述规则检查：用户禁止的先否定再肯定句式和异常占位扫描均为 0。
- 字体 XML 检查：`w:eastAsia="Times New Roman"`、`w:ascii="Songti SC"`、`w:ascii="Heiti SC"`、`w:hAnsi="Songti SC"`、`w:hAnsi="Heiti SC"` 均为 0；文档中存在 `Songti SC`、`Heiti SC` 和 `Times New Roman` 绑定。
- 版式渲染检查：本机存在 `pdftoppm`，但未发现 `soffice` 命令。Word COM 注册表项存在，本轮尝试导出 PDF 120 秒未完成，已清理本次启动的后台 Word 进程，未生成 PDF 页面图。因此本轮已经完成文本结构和字体 XML 检查，分页、表格宽度和最终版式仍需在可正常渲染 Word 的环境中复核。

## 方法论沉淀

本次修订把 R13 至 R20 从后续口头路线转成可验收的开发表格，并把资料读取要求写入 DOCX 和 `AGENTS.md` 两个层面。这样后续开发先进入资料依据，再进入实现和验证，能够把企业工艺知识、RAG 证据、候选状态和实时执行边界分层推进。它形成的核心资产包括：阶段化验收表、资料读取规则、结构抽取记录、字体检查记录和版式风险记录。
