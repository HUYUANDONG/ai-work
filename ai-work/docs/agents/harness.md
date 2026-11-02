# Agent Harness（V1.0.0）

配套 [requirements-v1.0.0.md](../requirements-v1.0.0.md)、[explosion-agent.md](explosion-agent.md)、[quality-agent.md](quality-agent.md)。

## 结论

- **本仓「Harness」目录**：薄配套（`AppRuntime`、代码路由、`langgraph` Checkpointer），**不是**独立 Agent 中台产品。
- **专家任务编排用 LangGraph**：Explosion / Quality 均为 `StateGraph`（条件边做会签 `REVISE`）；默认 `MemorySaver`，可配 Postgres Checkpoint。
- **要**：共用模型、Tool、权限、Checkpoint、Worker、`scoring/`。
- **任务类型路由仍用代码**：对话入口输出 `task_type`，Worker 按类型进专家图；**不做**跨专家的全局指挥 Agent。
- **Explosion 任务内是 multi-agent**：信号/风控/策略会签 + 指挥裁决修订；正式分与规则命中仍是代码。
- **Quality**：LangGraph 线性图（规则 + LLM 解释）。
- 专家之间 **不互相直接调用**；组合需求优先 Explosion 内会签，完整质检再由 Chat 建 `QUALITY`。
- Chat 入口仍手写意图分支（短请求）；长任务图才上 LangGraph。

## 1. Harness 仍然有好处

没有 Harness，Explosion 与 Quality 会各接一套模型、Java 客户端和 Checkpoint。

V1 的 Harness 是 Python 仓内薄运行时，不是 Agent 中台。

| 要 | 不要 |
|---|---|
| 一份 Tool / 权限 / Checkpoint / Worker | 按专家拆 Python 进程 |
| 一份 `scoring/` | 让 LLM 算正式分或当唯一分数来源 |
| 对话入口闲聊、澄清、读报告追问 | 对话 Agent 自己拉 2000 SKU 分析 |
| Explosion 内会签与计划状态机 | 全局指挥 LLM 现场串调多个 `task_type` |

## 2. 两层「指挥」不要混淆

| 层 | V1 有没有 | 职责 |
|---|---|---|
| 对话入口 Chat | 有 | 说话、澄清、`NEED_TASK(task_type, input)`、读报告追问 |
| 跨任务全局指挥 | **无** | 不根据一步结果再派另一个 Java `task_type`（除非用户明确要求，由 Chat 建新任务） |
| Explosion 内作战指挥 | **有** | 目标/槽位、会签计划、`REVISE/FINISH`、汇总作战清单 |

用户说「筛爆品并标出不能硬冲的」→ **一次 `EXPLOSION`**（内含风控会签）即可。  
用户说「这批再出完整质检报告」→ Chat 建 `QUALITY`，不是 Explosion 指挥去调 Quality Tool。

独立全局指挥层仅在这些情况值得加（V1 不做，可进后续）：

- 专家 `task_type` ≥ 3，且经常要跨任务动态规划
- 要根据上一个 **已落库报告** 自动决定下一个任务类型且交叉/会签覆盖不了
- 专家会互相否决且无法在单任务 reduce 内解决

## 3. V1 实际结构

```text
用户对话
    │
    v
  对话 Agent（入口：说话、澄清、输出 task_type + input）
    │
    v
  Java 创建 ai_task（权威）
    │
    v
  Worker + Harness 代码路由
    │
    +-- EXPLOSION --> Explosion 图
    │                 代码：load → filter → score → quality 标签 → Top N
    │                 multi：指挥 plan → Signal∥Risk → Strategy → reduce
    │                        → plan_decide（可 REVISE，有上限）→ summary → upsert
    │
    +-- QUALITY   --> Quality 图
                      代码规则 + attach_explosion → LLM 解释 → upsert
```

对话 Agent 的意图闸门、缺参默认与无关阻断见 [chat-agent.md](chat-agent.md)。  
缺 `time_window_days` / `goal_mode` / `focus_slots` 时 **默认 30 / GMV / 5 并告知**，不默认连环追问。  
它 **禁止** 自己算分、禁止在一次对话 HTTP 内连跑两个专家图；`OUT_OF_SCOPE` 禁止建任务与读报告。

对话 Agent 只读工具：`get_conversation_reports`（Java `GET /internal/conversations/{conversationId}/reports`），仅追问或取上次 sku 时用。

## 4. Explosion multi 与 Quality 的关系

| 用户意图 | 路由 |
|---|---|
| 筛爆品、潜力、本周盯谁、冲 GMV/毛利/清仓 | `EXPLOSION` |
| 质检某 SKU、亏本断货清单、问题证据 | `QUALITY` |
| 筛爆品且只要风险标签+动作分型 | 只 `EXPLOSION` |
| 基于爆品名单要完整质检报告 | 先有报告，再 `QUALITY` + sku_ids |
| 闲聊、口径、追问上一次结果 | 不建任务 / 读报告 |
| 与爆品/质检无关 | `OUT_OF_SCOPE`，拒绝并引导，不建任务 |

## 5. Harness 能力与目录

1. Model Provider  
2. Tool：专家用 `query_features`、两类报告 upsert；对话只用 `get_conversation_reports`；本地 `scoring/`  
3. 代码路由：`task_type` → 专家图  
4. Checkpoint：独立 PostgreSQL（Explosion 的 `plan` 与会签中间态落在这里）  
5. 权限：无写电商 Tool  
6. Worker 领取 / 心跳 / complete  
7. 观测：agent 名（含 `campaign` / `signal` / `risk` / `strategy`）、tool、`task_id` / `run_id` / `trace_id`、`plan.revision`

```text
ai-workbench-python/
├── harness/                运行时，含按 task_type 路由
├── agents/
│   ├── chat/               对话入口，不是全局指挥
│   ├── explosion/          任务内 multi-agent（指挥 + 会签）
│   └── quality/
├── scoring/
└── app/
```

专家与入口细则见 [chat-agent.md](chat-agent.md)、[explosion-agent.md](explosion-agent.md)、[quality-agent.md](quality-agent.md)。

## 6. 三个月交付对齐（完善第一版）

| 里程碑（建议） | 内容 |
|---|---|
| M1 | 特征、scoring、交叉打标、报告 upsert、Chat 意图闸门与默认填参 |
| M2 | Explosion 会签三角色并行/两段式 + reduce + 动作分型与槽位 |
| M3 | 计划状态机（REVISE 上限）、观测与降级、Quality 深挖闭环 |

全局跨任务指挥不在三个月必达范围；契约上 Chat 的 `input` 已带 `goal_mode` / `focus_slots`，便于以后扩展。
