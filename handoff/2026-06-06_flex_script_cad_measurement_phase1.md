# 2026-06-06 柔性脚本与 CAD 几何实测第一阶段交接

## 开发前资料核对

| 资料 | 开发前时间戳 | 采用结论 |
| --- | --- | --- |
| `VC开发文档/Auto_Autoform思路整理/04_柔性脚本L0至L4详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 按 L0/L1 建立 Script Agent、Script Executor、稳定库、sandbox、运行记录和入库边界。 |
| `VC开发文档/Auto_Autoform思路整理/02_项目中心Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | 中心 Agent 继续负责审批、证据、风险等级和稳定库写入边界。 |
| `VC开发文档/Auto_Autoform思路整理/02_上下文信息结构体详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | Runtime 与前端只传递结构化 `current_project`、工具结果和候选值，不把候选尺寸混入实测结果。 |
| `VC开发文档/Auto_Autoform思路整理/03_几何与数据Agent详细架构计划与任务目标.docx` | `2026-06-01 18:14:07` | CAD 尺寸链路需要证据目录、解析器记录、失败原因和候选值区分。 |
| `VC开发文档/Auto_Autoform思路整理/06_Agent开发规划_01_中心Agent.docx` | `2026-06-04 18:03:39` | 低风险脚本执行可以进入网关白名单，GUI、工程写入、求解和报告发布仍走原审批工具。 |

开发前同步核对了关键源码：`script_registry.yaml` 为 `2026-06-05 15:39:30`，`autoform_agent/preparation_agents.py` 为 `2026-06-05 15:41:45`，`autoform_agent/cli.py` 为 `2026-06-06 00:37:21`，`autoform_agent/agent_runtime.py` 为 `2026-06-06 20:27:20`，`autoform_agent/geometry_import_workflow.py` 为 `2026-06-06 20:25:14`，`frontend/app.js` 为 `2026-06-06 20:25:55`，`docs/api_runtime_call_chain.md` 为 `2026-06-06 20:31:05`，`docs/beginner_onboarding_zh.md` 为 `2026-06-06 20:31:28`。

## 本轮实现

- 新增 `autoform_agent/flex_scripts/` 包：契约、registry、runner、executor、sandbox、validators、script_agent 和 cad_measurement 已拆分。
- 新增稳定库 `flex_script_library/skills/cad_measure_geometry_v1/`，版本 `v1` 的入口脚本固定调用内置 CAD 测量函数。
- 新增 schema：`skill_card_schema.json`、`script_run_record_schema.json`、`cad_measurement_result_schema.json`、`script_validation_report_schema.json`，并更新 `schemas/index.md`。
- CLI 新增 `script-list`、`script-run`、`script-fork`、`script-new`、`script-patch`、`script-validate`、`script-promote`、`cad-measure-geometry`。
- MCP 只新增 `autoform_script_catalog` 和 `autoform_script_run`，工具总数由 113 更新为 115。fork、新建、patch、validate 和 promote 暂不暴露为 MCP 工具。
- `AgentToolGateway` 增加脚本工具白名单。catalog 为只读低风险；run 只允许 registry 中 L0/L1 稳定脚本。
- Runtime 增加“长宽厚”询问分支，优先读取 `current_project.source_geometry_path`，再解析 prompt 中的 CAD 路径。完成结果按实测回答；blocked 结果返回缺少解析器、证据目录和文件名候选值说明。
- `frontend/app.js` 展示 `cad_measurement_result`、parser、bbox、length、width、thickness、blocked reason、evidence_dir 和 filename candidate，并把候选值按候选字段传回上下文。
- 顺手修复 HTTP bridge 契约测试：`检查当前工程` 已进入本地工程咨询分支，响应文本保留 `conversationId`，测试断言同步为 `autoform_project_consultation`。

## 真实 STEP 验证

输入文件：`C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP`

开发前确认：文件存在，时间戳 `2026-06-05 22:23:09`，SHA256 为 `A39F00808A959190E99BCF4BBB6D892B02CF376C178ADAC13F3FB10DCED6B292`。

执行命令：

```powershell
python -m autoform_agent cad-measure-geometry --source-geometry-path "C:\Users\Tang Xufeng\Desktop\薄板30-40-3.STEP" --length-unit mm
```

结果：`ScriptRunRecord.status=blocked`，`result.parser=probe_only`，`length/width/thickness=null`，`filename_dimension_candidate={length:30,width:40,thickness:3,unit:mm}`。parser probe 中 `FreeCADCmd`、`FreeCAD`、`OCP`、`OCC`、`meshio`、`trimesh` 均为 unavailable，AutoForm 内部读取器未登记。

证据路径：

- `output/script_runs/20260606_214955_682568_cad_measure_geometry_v1_436c3d8c1372/evidence`
- `output/cad_measurements/20260606_214955_852197_30-40-3/cad_measurement_result.json`

## 验证命令

```powershell
python -m py_compile autoform_agent\flex_scripts\__init__.py autoform_agent\flex_scripts\contracts.py autoform_agent\flex_scripts\registry.py autoform_agent\flex_scripts\validators.py autoform_agent\flex_scripts\cad_measurement.py autoform_agent\flex_scripts\runner.py autoform_agent\flex_scripts\executor.py autoform_agent\flex_scripts\sandbox.py autoform_agent\flex_scripts\script_agent.py autoform_agent\cli.py autoform_agent\mcp_tools\scripts.py autoform_agent\mcp_tools\__init__.py autoform_agent\agent_system\tool_gateway.py autoform_agent\agent_runtime.py flex_script_library\skills\cad_measure_geometry_v1\versions\v1\cad_measure_geometry.py
```

结果：通过。

```powershell
python -m pytest -q tests/test_flex_scripts.py tests/test_mcp_tools.py tests/test_agent_system.py tests/test_agent_runtime.py tests/test_geometry_import_workflow.py frontend/tests/smoke_test.py
```

结果：`79 passed, 1 skipped in 22.77s`。

```powershell
python -m pytest -q
```

结果：`319 passed, 1 skipped in 30.82s`。

```powershell
node frontend\tests\smoke-test.mjs
```

结果：`frontend smoke test passed`。

## 剩余风险和后续边界

- STEP、IGES 的真实几何测量仍依赖 FreeCAD、OCP/OCC、meshio 或 AutoForm 内部读取能力接入。当前 blocked 结果是可复核输出，不能推导真实长宽厚。
- Promote 当前只根据审批记录文件存在与否决定是否写入新版本目录。后续 L2 需要把中心 Agent 审批事件、风险等级、测试报告和版本记录绑定成不可混淆的入库证据。
- Sandbox 已拦截路径越界和稳定脚本原地覆盖，但还没有更细的资源限制、依赖白名单和脚本静态安全审计。L2 应补超时策略、依赖来源记录、危险 API 扫描和样例输入回放。
- Frontend 当前做了静态 smoke，未做浏览器截图级验证。本轮没有启动前端服务或 GUI，原因是改动集中在文本字段展示和上下文压缩，已由 Python 与 Node smoke 覆盖基础钩子。

## 方法沉淀

本轮把“脚本可生成”拆成稳定库、sandbox、执行器、验证器和运行记录五个可复核环节。模型可以提出脚本修改，但写入位置、执行入口、结果证据和入库动作都受控。CAD 实测链路保留 blocked 语义，使缺少解析器时仍能形成可追溯记录，同时避免把文件名候选值包装成实测数据。这个结构的核心价值在于：后续任意脚本都能沿同一套 SkillCard、ScriptRunRecord、ValidationReport 和 promotion request 累积，而不是依赖一次性命令输出。
