# AutoForm 多 Agent P0 仓库骨架

## 资料依据

- 主计划文档：`VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx`，当前确认时间戳为 `2026-06-01 20:48:15`。
- 主计划表 1 将 R0 至 R5 标记为 P0；表 5 将 R0 至 R3列为立即开工项。
- 当前仓库已有后端源码目录 `autoform_agent/`、前端目录 `apps/workbench/`、文档目录 `docs/` 和测试目录 `tests/`。

## P0 固定目录

```text
autoform_agent/                 现有 Python 业务实现和后端运行时
autoform_agent/agent_system/    现有多 Agent 角色预留层
backend/                        P0 事件网关、凭据边界和后端接口说明区域
apps/workbench/                       R3 静态工作台和本地事件回放区域
schemas/                        R2 核心 JSON schema
fixtures/                       R2 可回放样例事件
policy/                         R1 权限矩阵和高风险动作边界
evals/                          回放用例和后续评测问题
docs/                           项目说明、旧页面隔离和上下文边界文档
handoff/                        阶段总结、复盘和交接记录
tests/                          契约、fixture、后端和前端检查
tools/                          辅助脚本
VC开发文档/                     用户提供的规划资料和 DOCX 溯源材料
```

## P0 开发顺序

1. R0：先隔离旧页面，只把旧页面作为问题来源和迁移参考。
2. R1：固定目录、命名、权限和全局契约。
3. R2：固定 `RunEvent`、`TaskCard`、`ContextPatch`、`EvidenceBundle` 和 `TokenUsageSnapshot`，再写可回放 fixtures。
4. R3：用 fixtures 驱动黑白静态 UI，包含用户输入、状态总结、Agent 图谱、命令输出、API Key 状态和 token 面板。
5. R4：在后端增加事件网关、凭据边界和用量聚合。
6. R5：接入中心 Agent、上下文视图、补丁审查和审计事件。

## 冻结规则

- P0 schema 的必填字段只能通过显式迁移追加或放宽，不能无记录删除。
- fixtures 中的事件类型、Agent id 和对象 id 前缀作为 R3 至 R5 联调依据。
- 专业 Agent 在 R6 之后才能真实接入；P0 阶段只保留接口、样例和拒绝越权的检查。
- AutoForm 真实求解、后处理、优化和正式报告生成属于 R12 预留范围；P0 只能使用 dry run 或模拟事件。
