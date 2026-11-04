# 对话入口 Agent（V1.0.0）

配套 [requirements-v1.0.0.md](../requirements-v1.0.0.md)、[harness.md](harness.md)、[internal-api-contract.md](../internal-api-contract.md)、[frontend-api-contract.md](../frontend-api-contract.md)。

Vue 对话页只调 Java `POST /api/v1/agent/chat`（经 Gateway），不调 Python `/internal/chat`。

## 1. 范围

| 做 | 不做 |
|---|---|
| 意图闸门、缺参默认、`NEED_TASK` | 拉全店 SKU 做筛选 |
| **SKU_DEEP**：上来就问单品 → 查 Java 单品特征 → 建议 | 口算正式分 |
| **FOLLOWUP**：读本会话报告作答 | 跨用户读报告 |
| 质检 / 爆品长任务交给 Java+Worker | 一次 HTTP 内连跑两个专家 |

**Tools**

- `get_conversation_reports`（FOLLOWUP / 取上次 sku）
- `get_product_features`（SKU_DEEP，单品；禁止循环扫店）

## 2. 意图与路由（业界分层）

```text
规则门闩（取消/暂停、「要/不用」建议确认）
    → 决策模型（短状态机 + 近 4 轮截断对话）
    → 规则叠加（补参继承、SKU 深挖关键词）
    → NEED_TASK / 同步工具 / 澄清
```

决策**不**吃整份爆品报告；只吃 `session_state`：

| 字段 | 含义 |
|---|---|
| `phase` | `IDLE` / `AWAITING_CLARIFY` / `AWAITING_ADVISE_CONFIRM` / `TASK_RUNNING` |
| `last_intent` | 上一任务类型 |
| `last_task` | 时间窗 / goal_mode / focus_slots / include_advise |
| `flags` | advice_offer_pending 等 |

贵步骤（投放建议 LLM）在确认后再跑，与路由分离。

| `intent` | 建任务 | Tool |
|---|---|---|
| `EXPLOSION` | `NEED_TASK(EXPLOSION)` | 否 |
| `QUALITY` | `NEED_TASK(QUALITY)` | 取上次 sku 时可读报告 |
| `SKU_DEEP` | 否（本请求内答完） | 单品特征 |
| `FOLLOWUP` | 否 | 读报告；榜单后确认建议也走同步建议 |
| `QUEUED` | 否 | 长任务进行中：追问入队，或取消/暂停已请求 |
| `META` / `OUT_OF_SCOPE` / `CLARIFY` | 否 | 否 |

长任务进行中 Java 带 `active_task_id`。追问默认排队，结束后由 Java 按序再调 Chat。详情见 [internal-api-contract.md](../internal-api-contract.md) §1.5。  
对话记忆（业界 STM + 结构化 LTM，无 RAG）：

| 层 | 存哪 | 内容 |
|---|---|---|
| STM | `ai_message` 最近 8 轮 + 进程热缓存 | 原文短窗 |
| LTM 槽位 | `ai_conversation.session_state_json` | last_intent / last_task / active_task / advice_offer_pending |
| 外置 | 报告表 | 大结果按 task_id 取 |

需 `WB_MYSQL_ENABLED=true`；关闭时退化为进程内存。Vue 仍可带 history，服务端有库时以 DB 为准。

## 3. 示例

- 「帮我分析 SKU-001」→ `SKU_DEEP`（无需先出名单）
- 「按近 30 天冲 GMV 给我 5 个重点」→ `EXPLOSION` + `NEED_TASK`
- 「质检 SKU-002」→ `QUALITY` + `NEED_TASK`
- 「为什么第 2 个是先修再冲？」→ `FOLLOWUP`

## 4. 结构化输出

```json
{
  "intent": "SKU_DEEP",
  "reply": "...",
  "need_task": null,
  "clarify_pending": false
}
```

长任务完成后，Java 把 Worker `result_meta.download` 推给前端展示下载按钮。

