# 旧页面隔离清单

## 资料依据

- 主计划文档：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，R0 要求旧页面隔离与污染源清理。
- 当前旧页面来源：`apps/workbench/index.html`、`apps/workbench/app.js`、`apps/workbench/styles.css`、`apps/workbench/README.md`。
- 当前运行链路说明来源：`docs/api_runtime_call_chain.md`。

## 旧页面定位

当前 `apps/workbench/` 页面是既有 Agent runtime 控制台，页面标题为 `AutoForm Agent Console`，主要服务本地 HTTP bridge 和单次 prompt 调用。R3 之后的新工作台需要以 typed `RunEvent`、Agent 图谱、状态摘要、命令输出、凭据状态和 token 用量快照为中心。

## 可复用内容

| 来源 | 可复用点 | 使用边界 |
| --- | --- | --- |
| `apps/workbench/index.html` | 用户输入、API endpoint 输入、API Key 输入和运行时响应展示的基本区域 | 只复用交互意图，不能直接继承旧状态字段 |
| `apps/workbench/app.js` | 临时 API key 不写入仓库、请求前脱敏、响应后渲染的做法 | 需要迁移到 `RunEvent` 回放和 typed stores |
| `apps/workbench/styles.css` | 黑白灰为主、紧凑工作台布局、移动端折叠规则 | R3 需增加 Agent 图谱和 token 面板 |
| `apps/workbench/README.md` | HTTP bridge 的启动和页面定位说明 | 新 UI 文档要同步说明 fixtures 回放入口 |

## 污染源

| 污染源 | 风险 | P0 处理 |
| --- | --- | --- |
| `four-panel-console` 页面上下文 | 会把新工作台限制为旧四区结构 | 只允许出现在本隔离清单或旧页面说明 |
| 旧 prompt 驱动字段 | 会绕过 `TaskCard` 和 `RunEvent` | 新 fixtures 必须先生成 `TaskCard` |
| 旧 runtime response 直渲染 | 会绕过事件顺序、Agent 节点和连接状态 | R3 前端按 `run_events_demo.jsonl` 回放 |
| API Key 状态与普通 UI 状态混放 | 可能造成凭据状态泄漏到日志或摘要 | R4 引入 `credential_gateway` 和掩码状态 |
| 单 Agent 输出假设 | 会提前固化专业 Agent 直接写状态 | R5 前专业 Agent 输出保持候选或模拟 |

## 隔离规则

- 新 `schemas/`、`fixtures/`、`policy/` 和 `evals/` 不使用旧页面状态名。
- 旧页面字段只能作为迁移参考，不进入新 `ContextPatch` 目标路径。
- R3 前端若继续复用现有文件，必须先把状态来源改为 `RunEvent` 回放。
- R4 后端网关只能向前端输出掩码凭据状态和 `TokenUsageSnapshot`，不能输出明文 key。

## 截图状态

本轮先完成源码级隔离清单和污染源列表。R3 视觉验收时需要启动当前旧页面与新静态工作台，分别保存桌面宽度和窄屏宽度截图，用于比对是否仍继承旧页面状态假设。
