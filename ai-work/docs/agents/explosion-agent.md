# 爆品作战 Agent（V1.0.0）

配套 [requirements-v1.0.0.md](../requirements-v1.0.0.md)、[data-contract.md](../data-contract.md)、[harness.md](harness.md)、[chat-agent.md](chat-agent.md)。

本文件描述 **Explosion 专家**：在同一套 Harness 上跑的 **任务内 multi-agent 会签**，不是独立服务，也不是全局「指挥所有专家」的中台。

对外仍是一个 `EXPLOSION` 任务。用户不会分别叫「信号 Agent」「风控 Agent」。

## 1. 产品定义

从自营店约 2000 个在售 SKU 中，按 **运营目标 + 注意力槽位**，产出一份 **本周可执行的作战清单**（不是纯排行榜）。

只通过对话触发。不做新品选品、不写回电商。

| 维度 | 约定 |
|---|---|
| 正式口径 | 近 30 天对比前 30 天；90 天补充；7 天只展示不进正式分 |
| 候选池 | 代码打分排序后的 Top N（默认 20，上限 50）再进入会签 |
| 槽位 `focus_slots` | 默认 5，上限 10；「本周重点冲 / 先修再冲」合计不超过槽位 |
| 目标模式 `goal_mode` | `GMV` / `PROFIT` / `CLEARANCE`（对话澄清或默认 `GMV`） |

质检（Quality）负责「问题与证据」的完整报告；Explosion 负责「在目标下把注意力与动作分出去」。二者共用规则 ID 与交叉打标，不重复造第二套库存/利润算法。

## 2. 与质检的分工

| | Explosion（本 Agent） | Quality |
|---|---|---|
| 主问 | 这周盯谁、能不能冲、怎么冲 | 这品/这批有什么问题、证据是什么 |
| 约束 | 代码 `attach_quality` + 风控会签意见 | P0+P1 规则全量解释 |
| 交付 | 动作分型作战清单 + summary | 问题清单 + 质量/运营分 |
| 何时只跑一个 | 「筛爆品 / 本周重点」→ 只跑 Explosion | 「质检某 SKU / 全店亏本断货」→ 只跑 Quality |
| 何时再开 Quality | 用户要「这批的完整质检报告」 | — |

「爆但断货 / 爆但亏本」在 Explosion 内必须落到动作分型（如 `FIX_THEN_PUSH` / `DROP`），不能只报高分。

## 3. 硬指标（代码分，权威）

店铺日订单约 30 单，单 SKU 订单稀疏。**流量信号权重高于销量增速**；分项先过样本门槛（见 [data-contract.md](../data-contract.md)）。

| 分项 | 原始字段 | 默认权重倾向 | 不满足门槛 / 无数据 |
|---|---|---|---|
| 流量增长 | `clicks_30d` vs `clicks_prev_30d`，平滑 | 高 | 跳过，记入 `skipped_items` |
| 点击率、转化率 | 曝光、点击、点击成交，向店铺均值收缩 | 高 | 跳过 |
| 销售规模 | `gmv_30d`、`orders_30d` | 中 | 跳过 |
| 销售增速 | `gmv_30d` vs `gmv_prev_30d`，平滑 | 中低 | `LOW_SAMPLE` 跳过 |
| 毛利 | `price`、`cost` | 中；`PROFIT` 模式下提高 | 跳过并标注 |
| 库存可支撑 | `stock_qty`、`units_30d` | 低（主要用于风险）；`CLEARANCE` 下积压信号可加权 | 跳过 |

店内同类目对比可作弱分项。不使用外部竞品，不叫「市场竞争力」。

总分只在参与分项上归一。权重、门槛、平滑与 Agent 同仓；变更 bump `scoring_version`。  
**禁止 LLM 口算或改写 `explosion_score`。**

目标模式 **不改变** 代码分的计算公式（避免同一 SKU 多口径分数）；模式只影响：策略会签的动作偏好、槽位内取舍、summary 话术。若需模式专用排序，另出 `mode_rank` 展示字段，正式分仍用 `explosion_score`。

## 4. Multi-agent 会签（任务内）

选品当初「筛选 / 趋势 / 评分」仍是 **代码流水线**。会签加在 Top N 之后，解决真实运营冲突：**有信号 ≠ 该投入 ≠ 本周动作**。

| 角色 | 实现 | 输入 | 输出（结构化） | 是否 Agent |
|---|---|---|---|---|
| 代码信号与规则 | `scoring/` + 质检规则 | 全量或过滤后特征 | `explosion_score`、breakdown、`quality_*` | 否 |
| 作战指挥 Campaign | LLM + 计划状态机 | 用户目标、槽位、上一步结果 | `plan` 修订、`CONTINUE/REVISE/FINISH` | **是** |
| 信号官 Signal | LLM | Top N 的分与趋势字段 | 归因、信号置信度、是否像真爆 | **是** |
| 风控官 Risk | LLM | Top N 的规则命中与样本 | 是否一票否决、先修项、严重度叙述 | **是** |
| 策略官 Strategy | LLM | 目标模式 + 信号/风控意见 + 槽位 | 动作分型、槽位分配、本周主动作 | **是** |

指挥 **只存在于 `EXPLOSION` 任务图内**，不替代对话入口对 `QUALITY` 的路由，也不直接创建第二条 Java 任务（除非对话明确要开 Quality，仍由 Chat → Java 建任务）。

### 4.1 动作分型（交付枚举）

| `action_bucket` | 含义 |
|---|---|
| `PUSH` | 可投入注意力/流量；风险可接受 |
| `FIX_THEN_PUSH` | 信号强但有硬约束（如缺货、微利），先修再冲 |
| `WATCH` | 样本不足或信号矛盾，观察，不占满槽位优先 |
| `DROP` | 不建议本周投入（硬否决或目标不符） |

`PUSH` + `FIX_THEN_PUSH` 进入「本周重点」时，数量 ≤ `focus_slots`。其余候选可保留在报告中但标记未进槽位。

### 4.2 会签意见 schema（各 LLM 必须遵守）

共同约束：

- 只能引用代码已给出的字段与 `rule_id`；禁止编造数值  
- 输出 JSON；解析失败则该角色重试一次，仍失败则指挥带降级标记继续（该角色意见标 `DEGRADED`）

**Signal**

```text
sku_id, signal_confidence (HIGH|MID|LOW), attribution (短文),
looks_like_breakout (bool), cited_fields[]
```

**Risk**

```text
sku_id, veto (bool), severity_view (NONE|LOW|MID|HIGH),
fix_first[] (rule_id 列表), rationale, cited_rule_ids[]
```

**Strategy**

```text
sku_id, action_bucket, primary_action (短文),
in_focus_slot (bool), rationale, goal_mode
```

指挥 Reduce：合并为行上的 `council` 快照 + 最终 `action_bucket`（策略为主；`Risk.veto=true` 时不得为 `PUSH`，至少降为 `FIX_THEN_PUSH` 或 `DROP`）。

## 5. Graph 与计划状态机

### 5.0 建议门闩（方案 B）

| 用户说法 | 行为 |
|---|---|
| 「近7天爆品」等未点名建议 | 打分+定槽后出榜单，**询问**是否要投放建议；不拉板块 |
| 「…并给建议 / 怎么投」 | `include_advise=true`：定槽 → 拉板块 → **LLM 写建议** |
| 榜单后回「要」 | 对话同步：读最近报告槽位 → 拉板块 → LLM；不重跑打分 |
| 榜单后回「不用」 | 结束，保留榜单 |

会签三角色默认仍走**规则**（`WB_COUNCIL_LLM_ENABLED=false`）；**投放建议叙事**才调 LLM。

### 5.1 主路径

```text
parse_intent / load_goal     目标模式、槽位、include_advise 等
load_features               一次 Java features/query（profile=score）
score_all / attach_quality / select_top_n
signal_risk → strategy → reduce_decide（规则会签为主）
    │ REVISE → 回到会签或仅重跑策略
    │ FINISH + include_advise=false → report（榜单 + 询问）
    │ FINISH + include_advise=true  → load_advise → write_advise(LLM) → report
summarize / upsert_report
```

推荐默认边：**信号 ∥ 风控 → 策略 → reduce → plan_decide**，保证策略看到风控 veto，又保留并行度。

### 5.2 动态修订（完善「看完 A 再调 B」）

`plan` 存在 LangGraph state（Checkpoint），字段建议：

```text
goal_mode, focus_slots,
steps[],          # 如 SIGNAL_RISK_PARALLEL | STRATEGY | REDUCE
revision,         # 已修订次数
max_revisions,    # 默认 2
max_llm_rounds,   # 默认 3（会签大轮次数）
decision,         # CONTINUE | REVISE | FINISH
revision_reason
```

修订触发示例（写进指挥提示与单测）：

| 观察 | 动作 |
|---|---|
| Top N 中 `quality_risk_level=HIGH` 占比 > 30% | `REVISE`：强制策略偏 `FIX_THEN_PUSH`/`DROP`，summary 强调先修 |
| `Risk.veto` 数量 ≥ `focus_slots` | `REVISE`：仅重跑策略做取舍，或缩小 `PUSH` |
| `LOW_SAMPLE` / 信号 `LOW` 过多 | `REVISE`：提高 `WATCH` 比例，降低放量话术 |
| 用户目标与结果明显冲突（如 `PROFIT` 但微利仍大量 PUSH） | `REVISE`：纠正策略；超上限则 FINISH 并在 summary 声明降级 |

**上限**：`revision ≤ 2`，总会签大轮 ≤ 3；超出必须 `FINISH` 并 `plan_degraded=true`，禁止空转。

指挥 **禁止** 为了「再分析一下」拉全量 2000 行进 LLM；禁止改写代码分。

## 6. Tool（Python）

薄封装：

- `query_features(on_sale_only=true | filters)`
- `upsert_explosion_report(...)`

打分与规则是本地 `scoring/`，不是 Tool。不要为销售、流量、库存各写一个打 Java 的 Tool。

## 7. 报告交付（相对纯榜单的增强）

头：增加 `goal_mode`、`focus_slots`、`plan_degraded`、`council_version`（会签提示词/schema 版本，可与 `scoring_version` 分开）。

行：在原有分与风险之上增加：

- `action_bucket`、`primary_action`、`in_focus_slot`
- `signal_confidence`、`risk_veto`
- `council_excerpt`（可选 JSON：三角色要点）

`ai_reason` / `ai_risk` / `ai_suggestion` 由 reduce 后的最终话术填充，须与 `action_bucket` 一致。  
`summary`：本周重点列表 + 先修项 + 观察/剔除摘要 + 目标模式说明。

字段级契约见 [data-contract.md](../data-contract.md)。

## 8. 对话示例

用户：帮我按冲 GMV 筛最近 30 天有潜力的品，这周我只能盯 5 个，并标出不能硬冲的。

Java 创建 `EXPLOSION`，`input`含 `{ time_window: 30, goal_mode: GMV, focus_slots: 5, top_n: 20 }`。  
完成消息：`summary` + 表格（槽位内排序、`action_bucket`、规则分、风险、主动作）。

追问（对话 Agent 读报告，不新建任务）：

- 「为什么第 2 个是先修再冲？」→ 读 `quality_rule_ids`、`risk_veto`、`council_excerpt`
- 「换成保毛利再排一次槽位」→ 需重建任务（目标模式影响策略）；或 V1 允许同快照重跑 `EXPLOSION` 新幂等键
- 「这 5 个出完整质检报告」→ Chat 取 sku_ids，建 `QUALITY` 任务

## 9. 非目标（本专家内不做）

- 全局指挥去调度 Quality / 未来其它 `task_type`（仍由 Chat + Java）
- 新品选品、站外竞品、广告 ROI、主图视觉（P2）
- 自动改价、补货、投放写回
