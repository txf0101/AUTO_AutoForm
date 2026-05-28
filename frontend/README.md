# AutoForm Agent Console Frontend

这是 AutoForm Agent Runtime 的本地控制台页面。页面只保留四个区域：用户输入、状态总结、类 cmd 的状态报告和输出、API 输入以及 API 使用情况。用户 prompt 会从页面进入 HTTP bridge，再由 Python 后端 `autoform_agent.agent_runtime` 负责 OpenAI Agents SDK 调用和 AutoForm 工具选择。前端页面承担输入、API 运行时配置和结果显示职责。

## 启动方式

在项目根目录执行：

```powershell
python -m http.server 8765 --directory frontend
```

然后打开：

```text
http://127.0.0.1:8765
```

如需让页面进入真实 HTTP 通信路径，另开一个终端启动本地适配器：

```powershell
python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317
```

页面发送 prompt 后会访问 `http://127.0.0.1:4317/api/agent`。当前适配器调用的是本项目的 AutoForm Agent API runtime，并返回页面可以渲染的状态摘要、终端式日志和 API 使用信息。

使用项目根目录的 `start_autoform_agent.ps1` 或 `start_autoform_agent.cmd` 打开页面时，启动器会访问：

```text
http://127.0.0.1:8765/index.html?bridge=http
```

应用运行时链路使用 `python -m autoform_agent.http_bridge --host 127.0.0.1 --port 4317` 接收页面 prompt，再调用 `autoform_agent.agent_runtime`。MCP 工具层只作为可选外部集成入口保留。源码依据见根目录 [README.md](../README.md) 和 [docs/api_runtime_call_chain.md](../docs/api_runtime_call_chain.md)。

## API 配置

第四个区域提供 provider、Base URL、模型、Agents SDK API 模式和 API key 输入。默认预设为 DeepSeek：

```text
Provider: DeepSeek
Base URL: https://api.deepseek.com
Model: deepseek-v4-flash
Agents SDK API: chat_completions
```

这些默认值依据 DeepSeek 官方 API quick start 和本项目 `.env.example`。OpenAI Agents SDK API 模式依据本机 `openai-agents` 包源码中的 `set_default_openai_api(api: Literal["chat_completions", "responses"])`。

API key 有两种用法：

1. 推荐方式是在项目根目录复制 `.env.example` 为 `.env`，再把 IT 提供的 key 写到 `OPENAI_API_KEY`。`.gitignore` 已忽略 `.env` 和 `.env.*`，保留 `.env.example`。
2. 临时方式是在页面 API 区域粘贴 key。前端会把 key 随本次 `/api/agent` 请求发送给本机 HTTP bridge，请求展示区会显示 `[redacted]`，页面不会写入 `.env` 或浏览器持久存储。

如果后续使用别家的 OpenAI-compatible endpoint，选择 `OpenAI-compatible`，填写该服务商的 Base URL、模型名和 API 模式即可。只支持 Chat Completions 的服务商通常应选择 `chat_completions`；OpenAI 官方模型默认使用 `responses`。

## 目录说明

- `index.html`：四区块页面结构，包含用户输入、状态总结、终端输出和 API 使用情况。
- `styles.css`：工程控制台样式，采用浅色面板、清晰边框和等宽终端输出。
- `app.js`：交互逻辑，包含 prompt 发送、运行时响应渲染、终端式日志追加、API payload 展示和 API key 脱敏。
- `tests/smoke-test.mjs`：无依赖烟雾测试，检查关键 DOM 节点、脚本入口和维护注释是否存在。
- `tests/smoke_test.py`：Python 版本的静态烟雾测试，用于 Windows 环境无法运行 `node.exe` 时的替代检查。

## 维护原则

新增 UI 功能时，先确认它是否仍属于四个区域之一。若需要新增状态，应优先放入状态总结、终端输出或 API 使用情况区块，避免重新引入复杂导航、装饰性预览或多余面板。

API key 只能保存在 `.env` 或页面内存中。前端和后端响应都不应显示明文 key，测试中也只能使用虚构值。
