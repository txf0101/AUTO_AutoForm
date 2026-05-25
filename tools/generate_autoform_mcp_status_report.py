from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


WORKSPACE = Path(r"F:\【项目和任务】\EIT\2026\AUTO_AutoForm")
OUTPUT_PATH = WORKSPACE / "output" / "doc" / "AutoForm_MCP项目状态与1.0发布差距汇报_20260525.docx"


def main() -> None:
    """Create the Word report requested for the AutoForm MCP status briefing."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    configure_document(document)
    add_title(document)
    add_basis_section(document)
    add_command_scope_section(document)
    add_example_project_section(document)
    add_open_source_comparison_section(document)
    add_next_work_section(document)
    add_version_distance_section(document)
    add_appendix_section(document)

    document.save(OUTPUT_PATH)
    print(OUTPUT_PATH)


def configure_document(document: Document) -> None:
    """Apply a compact landscape layout so wide evidence tables remain readable."""
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.35)
    section.bottom_margin = Cm(1.35)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)

    for style_name, size, bold in [
        ("Normal", 9, False),
        ("Title", 18, True),
        ("Heading 1", 13, True),
        ("Heading 2", 11, True),
    ]:
        style = document.styles[style_name]
        style.font.name = "宋体"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        style.font.size = Pt(size)
        style.font.bold = bold


def add_title(document: Document) -> None:
    """Add the report title and a short scope statement."""
    title = document.add_heading("AutoForm MCP 项目状态与 1.0 发布差距汇报", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("面向当前 AutoForm Agent 工作区与本机 AutoForm Forming R13 环境")
    run.bold = True

    add_paragraph(
        document,
        "本文重新梳理当前 MCP 项目的可接收指令范围、官方示例工程的自然语言到脚本再到软件操作链路、"
        "后续待实现功能，以及相对于公开 Abaqus MCP 项目的工程差距。本文不沿用旧文档结构，旧文档仅作为历史材料留存。",
    )
    add_paragraph(
        document,
        "报告日期：2026-05-25。报告中的 AutoForm 事实优先来自本机安装目录、ProgramData、当前工作区源码、"
        "MCP 工具返回值和测试输出。公开项目对比来自 Cai-aa/abaqus-mcp 的 GitHub README 与 GitHub API 元数据。",
    )


def add_basis_section(document: Document) -> None:
    """Record concrete evidence so the briefing can be traced back to files or commands."""
    document.add_heading("一、资料来源与判定边界", level=1)
    add_paragraph(
        document,
        "本次汇报采用证据优先的口径。凡涉及软件路径、版本、工具数量、测试结果和外部项目能力，均在下表列出依据。"
        "对于尚未完成真实执行或缺少官方接口说明的内容，本文使用“待验证”或“工程估计”标注。",
    )

    rows = [
        [
            "B1",
            "本机 AutoForm 安装发现",
            "MCP 工具 autoform_discover_installation 返回 AutoForm Forming R13，版本 13.0.1.02，安装日期 20260519，安装目录为 D:\\Program Files\\AutoForm\\AFplus\\R13F。",
        ],
        [
            "B2",
            "本机 AutoForm 示例工程",
            "MCP 工具 autoform_list_example_projects 返回 7 个官方 .afd 示例：AutoComp_R13、PhaseChange_R13、Sigma_R13、Solver_R13、Thermo_R13、Triboform_R13、Trim_R13。",
        ],
        [
            "B3",
            "当前 MCP 工具入口",
            "autoform_agent\\mcp_server.py 中共有 67 个 @mcp.tool() 入口，入口覆盖安装、工程、QuickLink、材料、队列、求解器、报告、AF_API 和帮助主题。",
        ],
        [
            "B4",
            "当前 CLI 入口",
            "autoform_agent\\cli.py 中共有 68 个 subparsers.add_parser 入口，CLI 与 MCP 共享底层模块，便于在自然语言工具调用之外进行复核。",
        ],
        [
            "B5",
            "当前测试结果",
            "在 TEMP 与 TMP 指向工作区 tmp\\pytest_runtime，并显式设置 --basetemp tmp\\pytest_basetemp_current 后执行 C:\\Users\\Tang Xufeng\\.conda\\envs\\afagent\\python.exe -m pytest -q，结果为 57 passed in 1.01s。",
        ],
        [
            "B6",
            "模块覆盖矩阵",
            "autoform_agent\\coverage.py 与 autoform_module_coverage_matrix 返回当前已实现模块，其中 Simulation jobs 状态为 implemented-specs-kinematic-and-full-execution。",
        ],
        [
            "B7",
            "示例工程摘要",
            "autoform_get_afd_project_summary 对 7 个官方示例输出项目名、材料、厚度、DieFace 使用状态和插件使用候选字段；该函数明确说明字段来自 .afd 可读片段，需要用 QuickLink 或官方导出交叉验证。",
        ],
        [
            "B8",
            "公开参照项目",
            "Cai-aa/abaqus-mcp README 说明其 v4.0 支持 Abaqus/CAE 内部插件、文件式 IPC、execute_script、get_model_info、list_jobs、submit_job、get_odb_info、get_viewport_image 和 abaqus://status 资源。",
        ],
        [
            "B9",
            "公开项目元数据",
            "GitHub API 于本轮返回 Cai-aa/abaqus-mcp 为公开 Python 项目，MIT License，默认分支 main，141 stars，17 forks，仓库更新时间 2026-05-24T17:12:38Z。",
        ],
    ]
    add_table(document, ["编号", "依据类别", "具体依据"], rows, [1.6, 5.0, 19.8])


def add_command_scope_section(document: Document) -> None:
    """Describe what instructions the MCP project can currently accept."""
    document.add_heading("二、当前可接收指令范围", level=1)
    add_paragraph(
        document,
        "当前项目已经从“本机 AutoForm 事实读取”扩展到“命令计划、受控执行、日志和结果线索解析”。"
        "从面向汇报的角度，可把能力分为环境、工程、仿真、数据、治理和发布辅助六类。"
    )

    document.add_heading("2.1 总览表", level=2)
    overview_rows = [
        [
            "环境与安装发现",
            "查找本机 AutoForm 版本、安装目录、bin、材料库、脚本目录、帮助链接和 package_info。",
            "已实现，只读稳定",
            "B1、B3、B6",
        ],
        [
            "工程文件识别",
            "列出官方示例工程，读取 .afd 文件事实，抽取可读片段，形成候选工程摘要。",
            "已实现索引级读取",
            "B2、B7",
        ],
        [
            "图形界面与工程打开",
            "生成或执行 AutoForm Forming 启动命令，生成或执行 AFFormingUI.exe -file 工程打开命令。",
            "已实现预演与受控执行入口",
            "README、process.py、mcp_server.py",
        ],
        [
            "求解器与作业",
            "生成 AFFormingJob 检查命令，生成 AFFormingSolver 运动学检查与默认完整求解命令，支持批量探测和日志摘要。",
            "已实现规格、计划和部分真实执行证据",
            "B6、solver.py、tests\\test_solver.py",
        ],
        [
            "QuickLink 数据桥接",
            "安装 QuickLink 桥接脚本，收集 AutoForm 传出的 QuickLink archive，解析 XML、ProcessPlan、Evaluation、DieFace 和几何引用。",
            "已实现桥接和只读解析",
            "quicklink.py、quicklink_bridge.py、B6",
        ],
        [
            "材料库治理",
            "安装材料、列出材料库、查找重复材料、生成备份计划、检查 .mat 和 .mtb、执行 .mat 到 .mtb 转换。",
            "已实现，写入动作默认预演",
            "materials.py、commands.py、tests\\test_materials.py",
        ],
        [
            "队列与远程计算",
            "读取队列配置、远程主机配置、日志配置，检查队列进程，生成 AFQueueClient 与 LSF wrapper 命令计划。",
            "已实现只读和探测级能力",
            "config.py、queue.py、B6",
        ],
        [
            "诊断与日志",
            "收集近期日志，解析 GUI 工程打开事件，生成诊断包计划，输出环境快照。",
            "已实现只读和预演级能力",
            "diagnostics.py、B6",
        ],
        [
            "报告与 Office 线索",
            "清点 AFReportMSOffice、报告模板、Office proxy 标记和 GUI 报告事件，生成报告命令预览。",
            "已实现证据清点和命令预览",
            "report.py、B6",
        ],
        [
            "AF_API 二次开发",
            "列出 friction、heattransfer、oneelementpost 样例模块，检查 C 编译环境，生成 starter 文件计划和编译命令预览。",
            "已实现模板和预览，当前编译器缺失",
            "af_api.py、autoform_check_af_api_build_env",
        ],
        [
            "帮助主题与能力覆盖",
            "读取 helpLinks.cfg，按关键词筛选帮助主题，把 GUI 主题映射到 Agent 能力域。",
            "已实现索引级能力",
            "coverage.py、inventory.py",
        ],
        [
            "本地前端演示",
            "启动 HTTP bridge 与静态前端，展示状态、操作流和本地只读能力。",
            "已实现本地预览，真实 Codex 会话接入仍需后续接口",
            "frontend\\README.md、http_bridge.py",
        ],
    ]
    add_table(document, ["能力域", "可接收的自然语言指令范围", "成熟度", "依据"], overview_rows, [4.0, 13.5, 5.0, 4.0])

    document.add_heading("2.2 细分条目表", level=2)
    detail_rows = [
        [
            "安装与环境",
            "autoform_discover_installation、autoform_list_executables、autoform_environment_snapshot",
            "“看看这台机器有没有 AutoForm”、“当前版本是什么”、“把环境快照给我”。",
            "可直接用于汇报和诊断，输出结构化 JSON。",
        ],
        [
            "工程文件",
            "autoform_list_example_projects、autoform_inspect_afd、autoform_get_afd_readable_index、autoform_get_afd_project_summary",
            "“列出示例工程”、“这个 .afd 是什么项目”、“抽一下工程名和材料”。",
            "当前摘要是候选字段，正式技术结论建议再用 QuickLink 导出交叉验证。",
        ],
        [
            "GUI 操作",
            "autoform_start_ui、autoform_open_afd",
            "“打开 AutoForm”、“打开 Solver_R13 工程”。",
            "MCP 默认 dry_run=True；真实 GUI 启动会产生外部进程。",
        ],
        [
            "作业与求解器",
            "autoform_forming_job_check_plan、autoform_forming_solver_kinematic_plan、autoform_forming_solver_full_plan、autoform_forming_solver_kinematic_batch_probe、autoform_forming_solver_full_batch_probe、autoform_solver_log_events",
            "“给这个工程做运动学检查”、“给这几个工程批量求解”、“把失败日志摘要出来”。",
            "已经有 7 个官方示例批量运动学探测证据，以及 3 个官方示例默认完整求解返回码 0 的记录。",
        ],
        [
            "QuickLink",
            "autoform_install_quicklink_bridge、autoform_list_quicklink_exports、autoform_parse_quicklink_xml、autoform_get_quicklink_process_plan、autoform_get_quicklink_evaluation、autoform_get_quicklink_die_face、autoform_compare_quicklink_exports",
            "“把 QuickLink 导出收集起来”、“解析 ProcessPlan”、“比较两次导出差异”。",
            "适合做 AutoForm 数据出口。下一步需要更多带结果值的真实导出样本。",
        ],
        [
            "材料",
            "autoform_install_materials、autoform_list_material_libraries、autoform_find_duplicate_material_files、autoform_material_library_backup_plan、autoform_inspect_material_file、autoform_mat_to_mtb_convert",
            "“安装材料库”、“查重复材料”、“把这个 .mat 转成 .mtb”。",
            "写入材料库和转换执行均需要显式确认或 execute=True。",
        ],
        [
            "队列与远程",
            "autoform_get_queue_config、autoform_get_remote_hosts、autoform_queue_health_check、autoform_queue_client_probe、autoform_lsf_command_plan",
            "“读一下队列配置”、“生成 LSF 提交命令”、“检查队列进程”。",
            "当前可读本机 Queue1 和 localhost 远程主机配置；生产集群需现场验证。",
        ],
        [
            "报告与结果线索",
            "autoform_report_inventory、autoform_report_log_events、autoform_report_ms_office_plan、autoform_postsolve_plan",
            "“查报告模板”、“从日志里找导出动作”、“预演 Office 报告命令”。",
            "已经能定位报告模板、Office 代理标记和日志事件；结果读取和报告真实导出仍需补齐。",
        ],
        [
            "AF_API",
            "autoform_list_af_api_modules、autoform_check_af_api_build_env、autoform_af_api_template_plan、autoform_af_api_build_preview",
            "“给我生成摩擦子程序模板”、“检查能不能编译用户传热模块”。",
            "当前本机 cl、icl、gcc 均未发现，AF_HOME_LIB 也未设置。",
        ],
    ]
    add_table(document, ["细分范围", "主要 MCP 工具", "可接收表达", "说明"], detail_rows, [3.6, 8.2, 7.6, 7.0])


def add_example_project_section(document: Document) -> None:
    """Summarize how far each official example project can be driven."""
    document.add_heading("三、官方示例工程的实现程度", level=1)
    add_paragraph(
        document,
        "本节按“自然语言、脚本化、软件操作”三个层次描述 7 个官方示例工程。"
        "自然语言层指用户可直接下达的意图；脚本化层指当前 CLI 或 MCP 已能形成的结构化命令；"
        "软件操作层指已经进入 AutoForm 命令、GUI 或求解器的程度。",
    )

    rows = [
        [
            "AutoComp_R13.afd",
            "AutoForm Forming R13 AutoComp Test File；材料 DC04，厚度 1.0000 mm；候选信息显示 DieFace 未使用，TriboForm 使用。",
            "可询问工程摘要、材料、厚度、插件使用线索；可请求打开工程和运动学检查。",
            "可用 open-afd、afd-project-summary、forming-solver-kinematic-batch。",
            "已纳入 7 个官方示例批量运动学探测证据；默认完整求解尚未单独完成本轮确认。",
        ],
        [
            "PhaseChange_R13.afd",
            "AutoForm Forming R13 PhaseChange Plug-in Test File；材料 22MnB5，厚度 1.0000 mm；DieFace 使用。",
            "可询问热成形或相变插件相关示例的工程摘要；可请求运动学检查和默认完整求解。",
            "可用 open-afd、afd-project-summary、forming-solver-kinematic-plan、forming-solver-full-plan。",
            "已记录为 3 个默认完整求解返回码 0 的官方示例之一；PhaseChange 对 AF_HOME_LIB 较敏感，后续应固化环境变量设置。",
        ],
        [
            "Sigma_R13.afd",
            "AutoForm Forming R13 Sigma Test File；材料 DX54D，厚度 1.0000 mm；DieFace 使用。",
            "可询问 Sigma 示例的材料、特征和可读字段；可请求运动学检查。",
            "可用 open-afd、afd-project-summary、forming-solver-kinematic-batch。",
            "已纳入 7 个官方示例批量运动学探测证据；默认完整求解仍需补充执行记录。",
        ],
        [
            "Solver_R13.afd",
            "AutoForm Forming R13 Solver Test File；材料 DC04，厚度 1.0000 mm；DieFace 使用。",
            "可作为当前主展示样例：读取摘要、打开 GUI、预演作业检查、执行运动学检查和默认完整求解。",
            "可用 open-afd、forming-job-check-plan、forming-solver-kinematic-plan、forming-solver-full-plan、solver-log-events。",
            "已记录 Solver_R13 运动学检查返回码 0，并属于 3 个默认完整求解返回码 0 的官方示例。它适合作为 1.0 演示主线。",
        ],
        [
            "Thermo_R13.afd",
            "AutoForm Forming R13 Thermo Plug-In Test File；材料 DX57-GI_Vegter+thermo_0.4-0.8，厚度 1.0000 mm；DieFace 使用。",
            "可询问热耦合示例摘要；可请求运动学检查。",
            "可用 open-afd、afd-project-summary、forming-solver-kinematic-batch。",
            "已纳入 7 个官方示例批量运动学探测证据；热相关完整求解和结果解释仍需单独验证。",
        ],
        [
            "Triboform_R13.afd",
            "AutoForm Forming R13 TriboForm Plug-In Test File；材料 DX54D，厚度 1.0000 mm；DieFace 使用，TriboForm 使用。",
            "可询问摩擦插件示例摘要；可请求运动学检查。",
            "可用 open-afd、afd-project-summary、forming-solver-kinematic-batch。",
            "已纳入 7 个官方示例批量运动学探测证据；TriboForm 相关完整求解和许可证边界仍需补证。",
        ],
        [
            "Trim_R13.afd",
            "AutoForm Forming R13 Trim Test File；材料 DX54D，厚度 1.0000 mm；DieFace 使用。",
            "可询问修边示例摘要；可请求运动学检查和默认完整求解。",
            "可用 open-afd、forming-solver-kinematic-plan、forming-solver-full-plan。",
            "已记录为 3 个默认完整求解返回码 0 的官方示例之一，适合作为 Solver_R13 之外的第二条演示链路。",
        ],
    ]
    add_table(document, ["示例工程", "当前可读摘要", "自然语言层", "脚本化层", "软件操作层"], rows, [3.2, 7.4, 5.5, 5.4, 5.0])

    add_paragraph(
        document,
        "总体判断：当前已经能把用户的常见汇报型指令转换为结构化 MCP 或 CLI 调用，并能对官方示例完成读取、打开、命令计划和部分求解。"
        "尚需补齐的关键环节集中在结果对象读取、报告自动导出、作业生命周期管理和 AutoForm 内部对象级操作。",
    )


def add_open_source_comparison_section(document: Document) -> None:
    """Compare current AutoForm MCP work with Cai-aa/abaqus-mcp as a public reference."""
    document.add_heading("四、与公开 MCP 项目的差距", level=1)
    add_paragraph(
        document,
        "公开项目 Cai-aa/abaqus-mcp 可作为当前阶段的明确参照。其 README 将架构描述为外部 FastMCP server 与 Abaqus/CAE 内部插件之间的文件式 IPC，"
        "并提供模型信息读取、脚本执行、作业提交、ODB 读取、视口截图和状态资源。下表基于该 README 与本项目当前源码状态形成对比。",
    )

    rows = [
        [
            "软件内插件或常驻代理",
            "Abaqus 侧有 abaqus_mcp_plugin.py，可在 Abaqus/CAE 内运行并消费命令文件。",
            "当前主要是外部 CLI/MCP，加上 QuickLink Export 脚本桥接；尚未形成 AutoForm 内部常驻代理。",
            "需要寻找 AutoForm 官方支持的常驻脚本、插件、宏或事件入口；若官方未提供，应把 1.0 边界限定为外部工具加导出桥接。",
        ],
        [
            "通用脚本执行",
            "提供 execute_script，可把 Python 脚本送入 Abaqus/CAE 执行。",
            "当前无等价的 AutoForm 内部通用脚本执行能力；已有能力是受控命令计划、QuickLink 收集和专用工具。",
            "需确认 AutoForm 是否有安全可控的脚本宿主。缺少官方依据时，应保持专用工具白名单。",
        ],
        [
            "模型对象信息",
            "提供 get_model_info，README 列出 parts、materials、steps、loads、BCs、interactions、assembly instances。",
            "当前可通过 .afd 可读片段和 QuickLink archive 读取候选工程字段与导出 XML 段落。",
            "需把 QuickLink 字段扩展成稳定对象模型，并为材料、工艺、工具、边界、评价区建立结构化 schema。",
        ],
        [
            "作业生命周期",
            "提供 list_jobs 和 submit_job，并等待作业完成。",
            "当前已有 AFFormingJob 检查计划、AFFormingSolver 运动学和完整求解计划、批量探测、日志解析。",
            "还需 list jobs、submit、status、cancel、失败分类、队列位置和结果目录归档的完整闭环。",
        ],
        [
            "结果文件读取",
            "提供 get_odb_info，用只读方式打开 ODB 并返回 steps、frames、instances 等元数据。",
            "当前没有 AutoForm 结果文件的等价结构化读取；只有 solver 标准输出摘要、日志事件和 QuickLink 导出解析。",
            "需确认 AutoForm 结果数据的可导出格式，优先以 QuickLink、报告模板、Office 导出和日志指针建立结果读取路径。",
        ],
        [
            "视图与图片",
            "提供 get_viewport_image，返回 Abaqus viewport screenshot 的 base64 图像。",
            "当前没有 AutoForm 视口截图工具；报告模板和 QuickLink 图像查看器线索已被 report_inventory 发现。",
            "1.0 至少应提供一种可复现的结果图导出或截图路径，并记录分辨率、视图名和文件位置。",
        ],
        [
            "实时状态资源",
            "提供 abaqus://status MCP resource，status.json 每 2 秒更新心跳。",
            "当前没有 MCP resource；已有 environment_snapshot、queue_health、日志读取等工具。",
            "需要增加 autoform://status 或等价资源，统一返回版本、路径、端口、进程、最近操作和错误。",
        ],
        [
            "日志与过期命令清理",
            "README 记录统一日志 mcp.log、status.json、commands、results 和 stale command cleanup。",
            "当前有 launcher 日志、诊断包计划和 GUI 日志解析；缺少统一 MCP home、命令队列和过期清理策略。",
            "需要定义 AutoForm Agent home 目录、操作日志、命令审计、结果归档和清理规则。",
        ],
        [
            "用户安装与菜单",
            "提供 Abaqus 插件菜单 start、stop、status，以及 .mcp.json 配置示例。",
            "当前有 start_autoform_agent.ps1、cmd 启动器、Codex MCP 配置模板和本地前端。",
            "还需整理为发布包，提供一键安装、依赖检查、卸载说明和普通用户路径适配。",
        ],
        [
            "开源发布成熟度",
            "GitHub API 显示 Cai-aa/abaqus-mcp 是 MIT License 公开项目，有 stars、forks、issues 和清晰 README。",
            "当前项目仍是本地工作区形态，pyproject 版本为 0.1.0，尚未形成公开 release、许可、贡献说明和跨机安装验证。",
            "1.0 之前需补齐 license、release notes、快速开始、最小示例、故障排查和隐私安全说明。",
        ],
    ]
    add_table(document, ["对比维度", "Cai-aa/abaqus-mcp", "当前 AutoForm MCP", "应补能力"], rows, [3.4, 7.4, 7.4, 8.0])


def add_next_work_section(document: Document) -> None:
    """List unfinished work in an order that supports a 1.0 release."""
    document.add_heading("五、后续功能与未完成部分", level=1)
    rows = [
        [
            "P0",
            "状态资源和健康检查",
            "增加 autoform://status 或等价 MCP resource；返回版本、安装路径、AutoForm 进程、最近日志、队列状态和错误摘要。",
            "对齐公开 MCP 项目的可观测性，降低用户不知道工具是否正常运行的风险。",
        ],
        [
            "P0",
            "作业生命周期闭环",
            "在现有 forming_job_check_plan 和 solver probe 基础上补齐 submit、status、cancel、wait、logs、archive。",
            "1.0 用户最关心从工程到计算结果的可复现流程。",
        ],
        [
            "P0",
            "结果读取和报告导出",
            "以 QuickLink、AFReportMSOffice、报告模板和 GUI 日志为入口，形成结果值、图像和 Office 报告的最小可复现导出。",
            "当前能求解部分示例，但报告链路还没有形成稳定交付物。",
        ],
        [
            "P0",
            "发布包与安装流程",
            "补齐 license、依赖声明、版本号策略、安装脚本、卸载说明、Codex 配置写入说明和普通用户路径检查。",
            "从本地演示进入可供他人使用的版本需要完整安装体验。",
        ],
        [
            "P1",
            "QuickLink schema 化",
            "把 ProcessPlan、Evaluation、DieFace、Blank、ProjectData 等 XML 段落映射为稳定字段，并增加差异报告。",
            "把可读导出变成可比较、可汇报的数据结构。",
        ],
        [
            "P1",
            "示例工程基准集",
            "为 7 个官方示例建立基准：摘要、运动学检查、默认求解、结果导出、日志摘要和失败判定。",
            "演示材料和回归测试需要固定基线。",
        ],
        [
            "P1",
            "权限和回滚",
            "对 ProgramData 写入、材料库安装、QuickLink 脚本安装、材料库备份和清理动作增加确认、备份、回滚和审计记录。",
            "公开版本会运行在更多机器上，写入动作需要清晰边界。",
        ],
        [
            "P1",
            "前端与 Codex 会话接入",
            "把当前 HTTP bridge 从只读状态展示扩展为真实会话操作，明确前端、MCP server 和 Codex host 的职责。",
            "汇报演示可以先保留本地预览，公开版本需要清楚的连接模型。",
        ],
        [
            "P2",
            "AutoForm 内部扩展路径调研",
            "继续查证 AutoForm 是否支持常驻脚本、插件菜单或受控内部自动化接口。",
            "这决定能否接近 Abaqus MCP 的 execute_script 和 viewport 能力。",
        ],
        [
            "P2",
            "跨版本和跨机器适配",
            "支持多版本发现、显式配置覆盖、许可服务器诊断、编译器诊断和非标准安装路径。",
            "公开用户环境差异较大，当前证据主要来自一台 R13 机器。",
        ],
    ]
    add_table(document, ["优先级", "功能项", "待实现内容", "原因"], rows, [1.8, 5.2, 13.2, 6.4])


def add_version_distance_section(document: Document) -> None:
    """Give a pragmatic estimate of distance to a public 1.0 release."""
    document.add_heading("六、距离可公开使用的 1.0 版本还有多远", level=1)
    add_paragraph(
        document,
        "从当前证据看，本项目已经达到“内部演示和受控本机使用”阶段。它有 67 个 MCP 工具入口、68 个 CLI 入口、57 个测试用例通过，"
        "并且已经形成 AutoForm 安装发现、材料治理、QuickLink 收集、示例工程读取、求解器计划和部分真实求解证据。"
    )
    add_paragraph(
        document,
        "面向公开 1.0，建议把目标限定为：用户能安装、能检查环境、能打开示例工程、能完成 Solver_R13 主线演示、"
        "能收集 QuickLink、能执行材料治理、能生成最小结果报告，并能在失败时获得清楚的日志和下一步动作。"
    )

    rows = [
        [
            "当前阶段",
            "0.1.0 原型到内部演示阶段",
            "pyproject.toml 版本为 0.1.0；测试通过；AutoForm R13 本机链路清楚；示例工程已经形成读取与部分求解证据。",
        ],
        [
            "1.0 核心门槛",
            "可安装、可复现、可诊断、可回滚",
            "需要统一状态资源、发布包、最小示例、作业闭环、结果导出、错误分类和用户文档。",
        ],
        [
            "工程估计",
            "约 4 至 6 周全职开发量",
            "该估计基于当前缺口表。若只做内部汇报版，1 至 2 周可形成稳定演示包；若面向外部用户，需要额外补齐安装、状态、结果和文档。",
        ],
        [
            "发布建议",
            "先发布 0.5 内测包，再进入 1.0 候选版",
            "0.5 聚焦 Solver_R13、Trim_R13、PhaseChange_R13 三条链路；1.0 候选版补齐状态资源、报告导出和安装文档。",
        ],
        [
            "主要风险",
            "AutoForm 内部对象接口和结果视图能力仍需官方依据",
            "若找不到官方常驻脚本或视图导出接口，1.0 应明确采用外部命令和 QuickLink 导出作为稳定边界。",
        ],
    ]
    add_table(document, ["判断项", "结论", "依据或说明"], rows, [3.2, 6.6, 16.6])


def add_appendix_section(document: Document) -> None:
    """Add concrete command examples and source URLs for the speaker."""
    document.add_heading("七、汇报可用命令示例与引用链接", level=1)
    command_rows = [
        ["发现安装", r"python -m autoform_agent.cli discover"],
        ["列出示例工程", r"python -m autoform_agent.cli example-projects"],
        ["读取工程摘要", r"python -m autoform_agent.cli afd-project-summary C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd"],
        ["预演打开工程", r"python -m autoform_agent.cli open-afd C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd --dry-run"],
        ["生成运动学检查命令", r"python -m autoform_agent.cli forming-solver-kinematic-plan C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd --threads 1"],
        ["生成默认完整求解命令", r"python -m autoform_agent.cli forming-solver-full-plan C:\ProgramData\AutoForm\AFplus\R13F\test\Solver_R13.afd --threads 1"],
        ["列出 QuickLink 导出", r"python -m autoform_agent.cli quicklink-list --workspace F:\【项目和任务】\EIT\2026\AUTO_AutoForm"],
        ["列出材料库", r"python -m autoform_agent.cli material-libraries"],
        ["运行测试", r"$env:TEMP='F:\【项目和任务】\EIT\2026\AUTO_AutoForm\tmp\pytest_runtime'; $env:TMP=$env:TEMP; C:\Users\Tang Xufeng\.conda\envs\afagent\python.exe -m pytest -q --basetemp tmp\pytest_basetemp_current"],
    ]
    add_table(document, ["用途", "命令"], command_rows, [5.0, 21.5])

    source_rows = [
        ["本项目 README", r"README.md"],
        ["本项目开发者指南", r"DEVELOPERS.md"],
        ["MCP 工具入口", r"autoform_agent\mcp_server.py"],
        ["模块覆盖矩阵", r"autoform_agent\coverage.py"],
        ["示例工程摘要实现", r"autoform_agent\inventory.py"],
        ["求解器实现", r"autoform_agent\solver.py"],
        ["QuickLink 实现", r"autoform_agent\quicklink.py"],
        ["Cai-aa/abaqus-mcp README", "https://raw.githubusercontent.com/Cai-aa/abaqus-mcp/main/README.md"],
        ["Cai-aa/abaqus-mcp GitHub API", "https://api.github.com/repos/Cai-aa/abaqus-mcp"],
    ]
    add_table(document, ["引用对象", "位置"], source_rows, [6.0, 20.5])


def add_paragraph(document: Document, text: str) -> None:
    """Add a paragraph with the spacing used throughout the report."""
    paragraph = document.add_paragraph(text)
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.15


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths_cm: list[float]) -> None:
    """Create a styled table with fixed column widths for consistent Word layout."""
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False

    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = header
        set_cell_width(cell, widths_cm[index])
        shade_cell(cell, "D9EAF7")
        make_cell_bold(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = value
            set_cell_width(cells[index], widths_cm[index])
            cells[index].vertical_alignment = WD_ALIGN_VERTICAL.TOP
            for paragraph in cells[index].paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.05
                for run in paragraph.runs:
                    run.font.size = Pt(8)
                    if looks_like_code(value):
                        run.font.name = "Consolas"
                        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    document.add_paragraph()


def set_cell_width(cell, width_cm: float) -> None:
    """Write an explicit Word table-cell width in twentieths of a point."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.first_child_found_in("w:tcW")
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_cm * 567)))
    tc_w.set(qn("w:type"), "dxa")


def shade_cell(cell, fill: str) -> None:
    """Apply a simple background fill to a header cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def make_cell_bold(cell) -> None:
    """Make every run in a header cell bold and dark."""
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x1F, 0x1F, 0x1F)


def looks_like_code(value: str) -> bool:
    """Detect cells that contain command text or paths and benefit from a monospace font."""
    markers = ["\\", ".py", ".afd", ".exe", ".cmd", "python -m", "--", "autoform_", "http"]
    return any(marker in value for marker in markers)


if __name__ == "__main__":
    main()
