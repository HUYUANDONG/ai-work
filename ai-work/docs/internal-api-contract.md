# Java ↔ Python 内部 API 契约（V1）

配套 [data-contract.md](data-contract.md)、[agents/chat-agent.md](agents/chat-agent.md)。  
本文是 **Java 实现清单**：路径、字段、错误码、mock 行为。HMAC 本期不做，仅要求服务身份头。

**版本**：`workflow_version = explosion-quality-1.0.0`  
**服务身份头**（双向）：`X-Workbench-Caller: java|python`

---

## 0. 约定

| 项 | 约定 |
|---|---|
| Base | Java：`WB_JAVA_BASE_URL`；Python：由 Java 配置 |
| Content-Type | `application/json; charset=utf-8` |
| 金额 | 分（整数）或统一 DECIMAL；同一仓库一致 |
| 空值 | JSON `null`；禁止用 0 冒充缺数 |
| 幂等 | 报告 `PUT` 按 `task_id` 整份覆盖 |

**通用错误**

| HTTP | body |
|---|---|
| 400 | `{"code":"BAD_REQUEST","message":"..."}` |
| 404 | `{"code":"NOT_FOUND","message":"..."}` |
| 409 | `{"code":"CONFLICT","message":"..."}`（租约冲突等） |
| 503 | `{"code":"SNAPSHOT_UNAVAILABLE","message":"..."}` |

---

## 1. Java 提供 · Python 调用

### 1.1 批量特征 `POST /internal/features/query`

**请求**

```json
{
  "stat_date": "2026-10-31",
  "on_sale_only": true,
  "category_id": null,
  "sku_ids": null
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `stat_date` | 否 | 默认当天快照 |
| `on_sale_only` | 否 | 默认 `true` |
| `category_id` | 否 | 过滤类目 |
| `sku_ids` | 否 | 指定 SKU 列表；质检批量 **≤50** |

**响应**

```json
{
  "snapshot_date": "2026-10-31",
  "row_count": 2,
  "items": [ { "sku_id": "SKU-001", "...": "见 data-contract 快照字段" } ]
}
```

字段全集见 [data-contract.md](data-contract.md) §1。Java **只返回原始计数/金额**，不算分。

**Mock（Python `WB_JAVA_MOCK_FEATURES=true`）**：读 `fixtures/mock_features.json` 并过滤。

---

### 1.2 单品特征 `GET /internal/products/{skuId}/features`

**Query**：`stat_date` 可选。

**响应**

```json
{
  "snapshot_date": "2026-10-31",
  "item": { "sku_id": "SKU-001", "...": "同快照行" }
}
```

404：SKU 不存在或无快照。

**用途**：Chat `SKU_DEEP`（可上来就问，不建长任务）。

---

### 1.3 会话报告 `GET /internal/conversations/{conversationId}/reports`

**Query**：`user_id`（必填，校验归属）、`limit`（默认 3）。

**响应**

```json
{
  "conversation_id": "c-1",
  "reports": [
    {
      "task_id": "t-1",
      "task_type": "EXPLOSION",
      "created_at": "2026-11-01T12:00:00Z",
      "header": { "summary": "...", "scoring_version": "..." },
      "items": [ { "sku_id": "SKU-001", "rank": 1, "explosion_score": 82.1 } ]
    }
  ]
}
```

只读；跨用户必须 403/404。

---

### 1.4 领任务 `POST /internal/tasks/claim`

**请求**

```json
{
  "task_types": ["EXPLOSION", "QUALITY"],
  "workflow_version": "explosion-quality-1.0.0",
  "worker_id": "py-worker-1"
}
```

**响应（有任务）**

```json
{
  "task_id": "t-1",
  "run_id": "r-1",
  "task_type": "EXPLOSION",
  "lease_token": "lease-abc",
  "lease_seconds": 60,
  "conversation_id": "c-1",
  "user_id": "u-1",
  "input": {
    "time_window_days": 30,
    "goal_mode": "GMV",
    "focus_slots": 5,
    "top_n": 20,
    "on_sale_only": true,
    "sku_ids": null,
    "category_id": null
  }
}
```

**无任务**：HTTP 204 或 `null` body（Python 客户端两者都接受）。

---

### 1.5 思考过程 / 心跳（可暂停取消）/ 完成 / 失败

#### 思考事件 `POST /internal/tasks/{taskId}/progress`

Python 每完成一个可见步骤上报；**Java 经会话 SSE 推给前端**（展示思考过程）。

```json
{
  "lease_token": "lease-abc",
  "event": {
    "seq": 3,
    "stage": "signal_risk_done",
    "title": "信号/风控意见已出",
    "detail": "否决 2 个",
    "data": { "veto_count": 2 },
    "visible": true,
    "at": "2026-11-01T12:00:00Z"
  }
}
```

常见 `stage`：`load_features` / `scoring` / `council_round` / `signal_risk` / `strategy` / `campaign_decide` / `revise` / `report_html` / `done` / `paused` / `cancelled`。

#### 心跳 `POST /internal/tasks/{taskId}/heartbeat`

**请求**

```json
{ "lease_token": "lease-abc", "progress": "council_round_2" }
```

**响应（Java → Python）**

```json
{
  "cancel_requested": false,
  "cancel_reason": "",
  "pause_requested": false,
  "pause_reason": "",
  "queue_depth": 2
}
```

| 标志 | 行为 |
|---|---|
| `cancel_requested` | Worker 在当前步骤检查点停止，任务 `CANCELLED` |
| `pause_requested` | 当前步骤结束后停止，任务 `PAUSED`（V1 不自动 resume；用户可再开任务或由 Java 重放） |
| `queue_depth` | 本会话追问排队条数（展示用） |

用户点「取消/暂停」：前端 → Java 写 `cancel_requested_at` / `pause_requested_at`；不必等 Python 专用取消 RPC。

#### 追问排队（Java 职责）

会话有 `RUNNING` 任务时：

1. 用户新消息默认 **入队**，不立刻建第二个同型任务  
2. Java 调 `POST /internal/chat` 时带 `active_task_id`，可选 `queue_message=true`  
3. Python 回 `intent=QUEUED` + `queue_ack`；前端展示「已排队」  
4. 任务结束后 Java **按序弹出队列**再调 Chat（或直接建任务）

#### 完成 / 失败

`POST /internal/tasks/{taskId}/complete`

```json
{
  "lease_token": "lease-abc",
  "summary": "给用户的完成短文（可与报告 header.summary 一致）",
  "result_meta": {
    "download": {
      "available": true,
      "url": "/internal/dev/reports/{task_id}",
      "method": "GET",
      "filename": "explosion-report-{task_id}.html",
      "content_type": "text/html; charset=utf-8"
    }
  }
}
```

> 正式环境下载 URL 由 Java 换成对外网关路径；Python 在 `result_meta.download` 里给出约定字段，前端按 `available` 展示按钮。

`POST /internal/tasks/{taskId}/fail`

```json
{ "lease_token": "lease-abc", "error_code": "NO_FEATURES", "message": "..." }
```

租约不匹配 → 409。

---

### 1.6 爆品报告 `PUT /internal/tasks/{taskId}/explosion-report`

```json
{
  "header": {
    "task_id": "t-1",
    "snapshot_date": "2026-10-31",
    "scoring_version": "explosion-1.0.0",
    "council_version": "council-rules-1.0.0",
    "time_window_days": 30,
    "top_n": 20,
    "item_count": 5,
    "goal_mode": "GMV",
    "focus_slots": 5,
    "plan_degraded": false,
    "focus_count": 3,
    "summary": "..."
  },
  "items": [
    {
      "sku_id": "SKU-001",
      "rank": 1,
      "mode_rank": 1,
      "explosion_score": 82.1,
      "score_breakdown": {},
      "skipped_items": [],
      "quality_risk_level": "NONE",
      "quality_rule_ids": [],
      "feature_excerpt": {},
      "action_bucket": "PUSH",
      "primary_action": "加大曝光",
      "in_focus_slot": true,
      "signal_confidence": "HIGH",
      "risk_veto": false,
      "council_excerpt": null,
      "ai_reason": "...",
      "ai_risk": "...",
      "ai_suggestion": "..."
    }
  ]
}
```

`explosion_score` 仅 Python 代码产生。同一 `task_id` 覆盖。

---

### 1.7 质检报告 `PUT /internal/tasks/{taskId}/quality-report`

```json
{
  "header": {
    "task_id": "t-1",
    "snapshot_date": "2026-10-31",
    "scoring_version": "explosion-1.0.0",
    "sku_count": 3,
    "high_risk_count": 1,
    "summary": "..."
  },
  "items": [
    {
      "sku_id": "SKU-002",
      "quality_score": 70,
      "ops_score": 55,
      "risk_level": "HIGH",
      "explosion_score": 88,
      "explosion_candidate": true,
      "issues": [
        {
          "rule_id": "STOCK_LOW",
          "severity": "HIGH",
          "actual": 2,
          "threshold": 5,
          "sample_size": 12,
          "evidence": "stock_qty=2",
          "ai_comment": "先补货再冲量"
        }
      ],
      "skipped_rules": []
    }
  ]
}
```

---

## 2. Python 提供 · Java 调用

### 2.1 对话 `POST /internal/chat`

**请求**

```json
{
  "conversation_id": "c-1",
  "user_id": "u-1",
  "message": "帮我分析 SKU-001",
  "history": [],
  "active_task_id": null,
  "queue_message": false
}
```

**响应**

```json
{
  "intent": "EXPLOSION",
  "reply": "...",
  "need_task": { "task_type": "EXPLOSION", "input": {} },
  "clarify_pending": false,
  "queue_ack": null,
  "ui_hints": {
    "show_thinking": true,
    "allow_pause": true,
    "allow_cancel": true,
    "queue_followups": true
  }
}
```

| intent | need_task | 说明 |
|---|---|---|
| `EXPLOSION` / `QUALITY` | 有 | Java 建长任务；前端开思考流 + 暂停/取消 |
| `SKU_DEEP` | null | 同步单品建议 |
| `FOLLOWUP` | null | 读本会话报告 |
| `QUEUED` | null | 任务进行中追问已排队，或取消/暂停已请求 |
| `META` / `OUT_OF_SCOPE` / `CLARIFY` | null | — |

任务进行中 Java 应把 progress 事件 SSE 给前端；完成后推 `result_meta.download`。

---

### 2.2 本地联调（可不进 Java）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/internal/dev/run-explosion` | 跑爆品流水线 |
| POST | `/internal/dev/run-quality` | 跑质检流水线 |
| POST | `/internal/dev/sku-deep` | 单品深挖 |
| POST | `/internal/dev/enqueue-task` | mock 入队供 Worker claim |
| GET | `/internal/dev/reports/{task_id}` | 下载 HTML |

---

## 3. 实现对照

| 能力 | Python | Java（ai_workbenth） |
|---|---|---|
| 特征 query / 单品 | `clients/java_client.py` → `tools/features.py` | `internalapi/feature/*` |
| 任务 claim / progress / heartbeat / complete / fail | `java_client` | `internalapi/task/*` |
| 入队（对话 need_task） | mock: `enqueue_mock_task` | `POST /internal/tasks/enqueue`；`ChatBridgeService` |
| 报告 upsert / 会话读取 | `tools/reports.py` | `internalapi/report/*` |
| 对话 | `POST /internal/chat` | `AgentApiClient` → `POST /api/v1/agent/chat` |
| Worker | `app/worker.py` | — |

联调：Java 起 8080；Python `WB_JAVA_MOCK_FEATURES=false`、`WB_JAVA_BASE_URL=http://127.0.0.1:8080`；请求头 `X-Workbench-Caller: python|java`。
