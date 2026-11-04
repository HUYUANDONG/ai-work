# Agent Harness（V1.0.0）

配套 [requirements-v1.0.0.md](../requirements-v1.0.0.md)、[explosion-agent.md](explosion-agent.md)、[quality-agent.md](quality-agent.md)。

## 结论

- **对话主路径 = OpsSupervisor**：决策 → 拉数 → 规则推荐∥库存 → **ExplosionAgent** → 问建议/文案。
- **正式分**：`scoring/` 死规则；**爆品 Agent** 只解读 + 有限进槽重排（不改 `explosion_score`）。
- **已移除** Signal / Risk / Strategy 三会签；Worker Explosion 图同步为 `score → explosion → advise? → report`。
- Chat 入口薄：闸门 + 记忆 → `OpsSupervisor.handle_turn`。

## 0. Ops 流水线

```text
用户「近7天爆品」
  → Decision → DataTask(features)
  → Recommend(scoring) ∥ Inventory
  → ExplosionAgent（LLM 解读 + 有限进槽；失败模板）
  → 问建议 → AdviseAgent
  → 问文案 → CopyAgent（写文案 + LLM 合规）
```

| 设计点 | 选择 |
|---|---|
| 排序权威 | scoring 规则分 |
| 爆品 Agent | 解读 + 焦点微调；禁止改分、禁止榜外捞人 |
| 会签 | **删除** |
| 建议/文案 | 用户确认后再跑 LLM |

## 1. 目录（按 Agent）

```text
agents/
├── supervisor/          workbench.py + ops.py
├── decision/ data_task/ recommend/ inventory/
├── explosion/           agent.py + LangGraph（graph/nodes/…）
├── advise/ copy/
├── quality_explain/ sku_deep/ followup/
├── chat/                入口
└── quality/             质检图
```

## 2. Worker Explosion 图

```text
load_features → score → explosion → (include_advise? advise → report : report)
```
