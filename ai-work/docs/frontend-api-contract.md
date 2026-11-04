# 前端 → Java 对外 API（对话）

配套 [architecture.md](architecture.md)、[internal-api-contract.md](internal-api-contract.md)、[agents/chat-agent.md](agents/chat-agent.md)。

浏览器**不直连 Python**。对话只打 Gateway，由 Java 转发 `POST /internal/chat`。

```text
Vue 3（ai-workbench-web）
  │ POST JSON，local 头 X-Wb-Dev-User
  ▼
ai-workbench-gateway   :8081
  │ 清身份头 → AuthAdapter → 可信 X-Wb-User-Id
  ▼
ai-workbench-service   :8080
  │ POST /api/v1/agent/chat → ChatBridgeService
  ▼
Python Agent           :8001
  POST /internal/chat
```

## 1. 联调地址（局域网 IP）

以各仓 `.env` 为准，下表为当前联调机：

| 服务 | 环境变量 | 当前值 |
|---|---|---|
| 前端请求 Gateway | `VITE_WORKBENCH_API_BASE` | `http://192.168.50.175:8081` |
| Gateway → Service | `WB_SERVICE_URI` | `http://192.168.50.175:8080` |
| Java → Python | `WB_AGENT_PYTHON_BASE_URL` | `http://192.168.50.157:8001` |
| Python → Java 内部接口 | `WB_JAVA_BASE_URL` | `http://192.168.50.175:8080` |

Python 必须 `--host 0.0.0.0 --port 8001`，只绑 `127.0.0.1` 时 Java 跨机访问会 503。

改 `.env` 后 **必须重启** 对应进程；Java 的 `WB_AGENT_PYTHON_BASE_URL` 启动时写入 Bean，不会热更新。

## 2. 身份（local）

| 段 | 头 | 说明 |
|---|---|---|
| 浏览器 → Gateway | `X-Wb-Dev-User` | 电商登录后的 `userId`。Gateway `local` profile 用它当身份 |
| Gateway → Service | `X-Wb-User-Id` 等 | Gateway 写入；客户端伪造的同名头会被清掉 |
| Java ↔ Python | `X-Workbench-Caller: java\|python` | 内部契约，前端不要带 |

登录仍走电商 `outfit-admin`。工作台不自建账号。

## 3. 对话 `POST /api/v1/agent/chat`

- Content-Type：`application/json; charset=utf-8`
- 超时：前端 60s；Gateway 默认 30s；Java→Python 40s
- 请求体 **snake_case**（与 Python `ChatRequest` 一致）。camelCase 会被 Python 422，Java 表现为 `Python Agent 不可用`

**请求**

```json
{
  "conversation_id": "c-1",
  "user_id": "u-1",
  "message": "近7天爆品",
  "history": [
    { "role": "user", "content": "上一轮用户" },
    { "role": "assistant", "content": "上一轮回复" }
  ],
  "active_task_id": null,
  "queue_message": false
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `conversation_id` | 是 | 前端会话 ID（本期列表仍在浏览器 localStorage） |
| `user_id` | 是 | 与 `X-Wb-Dev-User` 同一电商用户 |
| `message` | 是 | 本轮原文 |
| `history` | 否 | 最近若干轮 `{role, content}`，不含本轮 `message` |
| `active_task_id` | 否 | 本会话进行中的长任务 |
| `queue_message` | 否 | 默认 `false` |

**成功响应**（Servlet `ApiResult`，外层 camelCase，`data` 内 snake_case）

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "成功",
  "data": {
    "intent": "CLARIFY",
    "reply": "...",
    "need_task": null,
    "clarify_pending": true,
    "queue_ack": null,
    "ui_hints": null
  },
  "traceId": "..."
}
```

`data` 字段含义见 [internal-api-contract.md](internal-api-contract.md) §2.1。前端展示 `reply`；`need_task` 由 Java 入队，本期页面只展示回复文本。

**失败**

| HTTP | code | 常见原因 |
|---|---|---|
| 401 | `UNAUTHORIZED` | 未带 `X-Wb-Dev-User` |
| 503 | `SERVICE_UNAVAILABLE` | Python 未启动、IP/端口不对、或 `/internal/chat` 非 2xx |

## 4. 本期前端未接

| 能力 | Java 路径 | 说明 |
|---|---|---|
| 新建/列会话 | `/api/v1/conversations/*` | `wb_conversation` 窗口列表；对话正文/LTM 槽位在 `ai_message` + `ai_conversation.session_state_json`（需 `WB_MYSQL_ENABLED=true`） |
| 对话记忆 | ChatBridge 内 | STM：最近 8 轮；LTM：last_intent / last_task / advice_offer_pending；无向量 |
| 思考流 SSE | `/api/v1/conversations/{id}/stream` | 事件：`ready` / `thinking` / `llm_delta` / `reply` / `task_done` / `done`；对话页已接 |
| 一键发圈 | — | **已暂时砍掉**（对话判 OUT_OF_SCOPE） |
| 上架商品 / product-drafts | `/api/v1/product-drafts/*` | **已暂时砍掉**（返回 `WORKSPACE_FEATURE_TEMPORARILY_CUT` / HTTP 410） |

## 5. 探活

```text
GET http://192.168.50.175:8081/api/v1/system/ping
Header: X-Wb-Dev-User: <userId>
```
