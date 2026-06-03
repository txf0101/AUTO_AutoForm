# 2026-06-01 R4 凭据边界复盘

## 依据

- 主计划 R4 要求后端事件网关、凭据边界、API Key 掩码、连接测试和 `RunUsageAccumulator`。
- `policy/permission_matrix.md` 要求明文 key 不进入日志、fixture、StageSummary 或前端持久化。
- `frontend/README.md` 和 `docs/api_runtime_call_chain.md` 记录了页面临时 key 与后端 runtime 的通信路径。

## 本轮完成

1. 新增 `autoform_agent/credentials.py`，提供短指纹、请求密钥提取、文本脱敏和 JSON 结构脱敏。
2. `autoform_agent/http_bridge.py` 在 responder 正常响应、错误响应和异常响应上执行兜底脱敏。
3. `autoform_agent/agent_runtime.py` 的 runtime 响应新增 `apiKeyFingerprint`，并用共享脱敏函数清理 provider 异常。
4. `frontend/` 的凭据边界面板新增 Key Fingerprint 字段，页面仍只展示来源、状态、短指纹和 `[redacted]`。
5. 新增和扩展回归测试，覆盖嵌套 `runtimeConfig.apiKey`、responder 回显、responder 异常和 runtime 响应。
6. 修正脱敏规则，允许 `apiKeyFingerprint`、`apiKeySource` 和 `apiKeyConfigured` 这类状态字段通过 HTTP bridge，明文 `apiKey` 仍统一脱敏。
7. 新增 `autoform_agent/runtime_events.py` 和 `autoform_agent/provider_connection.py`，把后端响应转换为 `RunEvent`，并把 provider usage 聚合为 `TokenUsageSnapshot`。
8. 支持 `DeepSeek_V4_API` 作为 DeepSeek 专用环境变量来源；输出只显示 `environment:DeepSeek_V4_API` 和短指纹。
9. 前端凭据边界面板新增“测试连接”按钮，显式触发 `ConnectionTestStatus`，默认 prompt 不自动消耗 provider token。

## 本轮验证

- `python -m pytest -q --basetemp=tmp\pytest_r4_events_full2`：133 passed，1 skipped。
- `python -m autoform_agent.cli public-release-scan`：safe_to_publish 为 true，finding_count 为 0。
- 浏览器用临时假 key 走 `frontend/index.html?bridge=http` 到本机 HTTP bridge：页面文本、请求展示、响应展示、终端面板和控制台日志均未出现明文；Key Fingerprint 显示为 `sha256:` 短指纹；验证后已清空页面 key 输入。
- 截图证据保存于 `C:\Users\Tang Xufeng\AppData\Local\Temp\autoform-r4-credential-boundary.png`。
- `python -m autoform_agent.cli agent-connection-test --provider deepseek --conversation-id cli-deepseek-connection`：读取 `DeepSeek_V4_API`，连接测试通过，HTTP 200，latencyMs 为 1685，生成 `TokenUsageSnapshot`，总用量 15 tokens。
- 浏览器点击“测试连接”：读取 `environment:DeepSeek_V4_API`，连接测试通过，HTTP 200，生成 5 个 `RunEvent`，页面 token 总用量为 15，页面文本、终端面板和控制台日志均未出现明文 key。截图证据保存于 `C:\Users\Tang Xufeng\AppData\Local\Temp\autoform-r4-deepseek-connection.png`。

## 2026-06-02 直接 API 路线修正

- 用户明确要求不要继续采用旧运行时思路，运行时改为直接调用 DeepSeek API 或兼容 chat completions 的 HTTP 接口。
- `autoform_agent/agent_runtime.py` 取消旧可用性字段，统一输出 `directApiCalled`、`directApiAvailable`、`apiMode=chat_completions` 和 `autoform-direct-api-runtime`。
- `autoform_agent/provider_connection.py` 新增 `call_provider_chat_completion`，连接测试和真实运行共享同一个 HTTP 调用入口，错误响应继续走脱敏边界。
- 前端将状态字段改为 API Call，页面只显示 key 来源、配置状态和短指纹，不持久化明文 key。
- `python -m pytest -q --basetemp=tmp\pytest_direct_api_full`：135 passed。
- `python -m autoform_agent.cli public-release-scan`：safe_to_publish 为 true，finding_count 为 0。
- `python -m autoform_agent.cli agent-turn "用一句话确认 AutoForm Agent 直接 API runtime 可用，并引用本机工具入口数量。" --conversation-id cli-direct-api-smoke`：读取 `environment:DeepSeek_V4_API`，`directApiCalled=true`，总用量 1111 tokens，输出未出现明文 key。
- in-app browser 打开 `http://127.0.0.1:8786/frontend/index.html?bridge=http` 后发送 prompt：页面显示 `directApiCalled=true`，key 来源为 `environment:DeepSeek_V4_API`，token 总用量为 1417；页面文本和控制台日志未命中原始 key 模式，页面无旧运行时文案。
- 本轮尝试使用 in-app browser 截图时 `Page.captureScreenshot` 超时；备用 Playwright 路径因打包 Node 环境缺少 `playwright-core` 未生成截图。功能验证依据采用 DOM、日志、CLI 输出和 HTTP health 检查。

## 用户提供真实 key 时的操作口径

真实 key 不应发在聊天里。优先让用户在本地页面的 password 输入框粘贴，或写入本机 `.env` 的 `DeepSeek_V4_API`。测试报告只记录来源、是否配置、短指纹和调用结果，不记录明文 key。截图前应确认页面没有明文 key 文本；当前页面的 key 输入为 password 字段，展示区只显示 `[redacted]`。

## 剩余 R4 工作

- 将 R4 网关接入后续中心 Agent 的真实路由对象。
- 继续把工具意图协议接入更多业务能力时，先在 `build_runtime_tool_catalog()` 与 `_runtime_tool_registry()` 中同步登记工具名、参数边界和测试覆盖。

## 2026-06-02 工具意图协议落地

- `autoform_agent/agent_runtime.py` 新增 `autoform.direct_tool_intent.v1` 协议。普通 prompt 先调用 DeepSeek 或兼容 `chat/completions` 的 provider 生成工具意图 JSON，再由 Python 后端执行白名单工具，最后把工具结果交给 provider 生成中文回答。
- 白名单执行器 `_execute_runtime_tool_intents()` 会拒绝未知工具名，AFD 工具要求 `.afd` 路径，`autoform_project_run_plan` 固定为计划模式，`autoform_computer_use_probe` 固定不截图。
- 工具运行结果会通过 `redact_secret_data()` 处理并限制长度；响应新增 `toolRuns`、`directApiCallCount`、`toolIntentProtocol`、`toolIntentStatus`、`toolIntentCount` 和 `toolRunCount`，`TokenUsageSnapshot` 聚合两次 direct API 调用。
- 验证依据：`python -m pytest tests\test_agent_runtime.py tests\test_provider_connection.py tests\test_http_bridge.py tests\test_runtime_events.py frontend\tests -q --basetemp=tmp\pytest_deepseek_tool_intent_targeted` 返回 17 passed；旧 SDK 相关关键词扫描无命中。
