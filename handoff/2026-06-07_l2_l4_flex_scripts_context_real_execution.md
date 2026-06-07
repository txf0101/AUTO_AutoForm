# 2026-06-07 L2-L4 柔性脚本、执行上下文与真实执行交接

## 本轮目标

本轮围绕柔性脚本 L2 硬化、L3/L4 真实 AutoForm 执行和跨轮上下文连续性展开。验收重点放在两类证据上：脚本生产、验证、审批、运行和入库记录是否可追溯；用户多轮 prompt 在审批阻断、批准续接、实测追问和真实执行失败后是否仍能引用同一工程、脚本和证据目录。

## 开发前已读资料

| 资料 | 时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 柔性脚本要形成 Script Agent、Script Executor、稳定脚本库、sandbox、运行记录和 SkillCard 沉淀链路。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 中心 Agent 管审批、风险等级、ContextPatch 和证据目录，真实写入和求解继续走网关。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 跨轮上下文需要结构化传递当前工程、审批状态、补丁、证据和最近工具结果。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | CAD 尺寸必须区分实测结果和文件名候选值，解析器缺失时保留 blocked 证据。 |
| `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_01_中心Agent.docx` | `2026-06-04 18:03:39` | 高风险动作需要可序列化审批对象，批准后应按原任务续接。 |

## 主要改动

- 新增 `autoform_agent/flex_scripts/dependencies.py`、`security.py`、`approvals.py`，补齐依赖探测、静态安全审计和审批记录校验。
- 扩展 ScriptRunRecord：记录 dependency report、static audit、输入文件 hash、资源限制、approval record、sandbox dir、stdout/stderr 截断和 validation report。
- 扩展 sandbox promote：审批记录必须匹配 `sandbox_id`、`skill_id`、`approved_by` 和当前 `validation_report_hash`；通过后写入新的 `versions/<vN>/`，不覆盖已有版本。
- 扩展 `cad_measure_geometry_v1`：新增 `cad-parser-probe`，支持 parser `auto`、`stl_builtin`、`cadquery`、`freecadcmd`。STL 继续用内置 bbox；STEP 可在 CadQuery/OCP 或 FreeCADCmd 可用时实测。
- 新增 `execution_context` 合并与压缩：runtime、CLI `agent-turn` 和前端 `conversationContext` 都保留当前工程、待审批动作、可续接动作、已批准动作、脚本运行记录、上下文补丁、证据目录和最近工具结果。
- 前端 `frontend/app.js` 展示审批状态、可续接动作、CAD parser、bbox、blocked reason、filename candidate、最近脚本运行和证据目录。
- 新增 schema：`script_static_audit_schema.json`、`script_dependency_report_schema.json`、`script_approval_record_schema.json`、`execution_context_schema.json`，并更新 `schemas/index.md`。

## 真实环境结果

- 解析器探测：初始 `cad-parser-probe` 未找到 CadQuery/OCP、FreeCADCmd、FreeCAD、meshio、trimesh。随后执行 `python -m pip install cadquery`，安装后 `cadquery 2.7.0` 和 `OCP` 可导入，FreeCADCmd 与 FreeCAD 仍未发现。
- 依赖风险：CadQuery 安装一度把用户 site 的 `numpy` 升级到 `2.4.6`，随后降回 `numpy 1.26.4`，CadQuery 仍可导入；`pip` 仍提示 `nlopt 2.10.0 requires numpy<3,>=2`。后续若要正式锁定 CAD parser 环境，应独立虚拟环境或约束文件验收。
- 真实 STEP：`C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP` 存在，SHA256 为 `a39f00808a959190e99bcf4bbb6d892b02cf376c178adac13f3fb10dced6b292`。
- CAD 实测：`python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm --parser auto` 返回 `status=completed`、`parser=cadquery`、bbox dimensions `[400, 3, 300]`、`length=400`、`width=300`、`thickness=3`。证据位于 `output/cad_measurements/20260607_133101_817210_30-40-3/` 和 `output/script_runs/20260607_133101_665465_cad_measure_geometry_v1_958efb3e1bb2/`。
- Runtime CAD 追问：`output/frontend_prompt_tests/runtime_cad_context_reuse_test.jsonl` 记录第一轮 `tool_run_count=1`，第二轮问“刚才那个薄板厚度是多少”时 `tool_run_count=0`，回答复用同一 `cad_measurement_result`。
- 真实导入审批续接：`output/frontend_prompt_tests/runtime_import_approval_reuse_real.jsonl` 记录未批准时返回 `pendingApproval` 和 `resumableAction`，批准后真实导入完成，生成 `output/geometry_import_projects/20260607_133918_薄板30-40-3/薄板30-40-3.afd`。
- 真实导入失败样本：`output/frontend_prompt_tests/runtime_import_approval_reuse_real_compact.jsonl` 记录另一轮批准续接命中了多窗口或焦点不稳定问题，工具步骤完成到保存后返回 `blocked`，原因是 `AutoForm did not create the requested .afd output file.`，证据位于 `output/geometry_import_projects/20260607_134201_薄板30-40-3/evidence`。
- 真实求解：`python -m autoform_agent project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output/project_runs --execute --timeout 120` 返回求解器 `returncode=0`，stdout summary 中 `simulation_successful=true`，证据位于 `output/project_runs/20260607_134351_Solver_R13_kinematic`。

## 验证命令

```powershell
python -m py_compile autoform_agent/flex_scripts/contracts.py autoform_agent/flex_scripts/dependencies.py autoform_agent/flex_scripts/security.py autoform_agent/flex_scripts/approvals.py autoform_agent/flex_scripts/validators.py autoform_agent/flex_scripts/sandbox.py autoform_agent/flex_scripts/runner.py autoform_agent/flex_scripts/script_agent.py autoform_agent/flex_scripts/cad_measurement.py autoform_agent/cli.py autoform_agent/agent_runtime.py
python -m pytest -q
node frontend/tests/smoke-test.mjs
python -m autoform_agent cad-parser-probe
python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm --parser auto
python -m autoform_agent project-run --example Solver_R13 --mode kinematic --threads 1 --output-root output/project_runs --execute --timeout 120
```

验证结果：`python -m pytest -q` 为 `327 passed, 1 skipped`；Node 前端 smoke 通过；真实 STEP 已由 CadQuery 实测；真实 `.afd` 导入存在成功证据和一条 blocked 复现证据；官方 `Solver_R13` 运动学求解完成。

## 剩余风险

- CadQuery/OCP 目前安装在用户 Python 环境，仍有 `nlopt` 与 `numpy` 版本提示。后续 L3/L4 若需要稳定生产环境，应建立独立虚拟环境、锁定依赖并把 `cad-parser-probe` 纳入启动健康检查。
- FreeCADCmd 未发现，FreeCAD 路径探测仍停留在 probe 层。若后续要覆盖复杂 STEP/IGES 或装配体，建议增加 FreeCADCmd 外部执行脚本和示例几何回归。
- 真实导入在多 AutoForm 窗口并存时有焦点和保存目标不稳定风险。已有证据显示同一 STEP 可以成功写出 `.afd`，也能复现保存后未生成目标文件的 blocked 状态；后续应强化窗口锁定、保存路径确认和导入完成判定。
- L4 求解本轮用 CLI `project-run --execute` 完成，runtime 审批续接语义已覆盖导入链路。后续若要网页端直接批准求解，应增加专门的多轮 prompt 用例，把 `autoform_project_run execute=true` 的 pending、approved、result evidence 全链路写入 JSONL。

## 下一阶段边界

- L2 后续可增加更细的 AST 审计规则、依赖白名单和 sandbox artifact diff。
- L3 应优先解决 AutoForm GUI 多窗口目标锁定、保存对话框路径校验和截图证据质量。
- L4 应把官方样例求解、用户工程求解、失败恢复、result_package 汇总和前端追问联成固定回归。
