# 快照特征与报告契约（V1.0.0）

配套 [requirements-v1.0.0.md](requirements-v1.0.0.md)。Java 产出特征，Python 代码算分，报告回写 Java。

规模前提：约 2000 个在售 SKU，日订单约 30，统计查库。一次 `features/query` 可返回全部在售特征。

## 0. 样本量前提（影响所有口径）

日订单约 30 单，平均每个 SKU 30 天不到 0.5 单；即使按二八分布，头部 SKU 每周也只有 1 单左右。因此：

- **正式口径以 30 天为主窗口，对比前 30 天；90 天作补充。** 7 天窗口只作展示参考，不进正式分、不触发规则。
- **每个分项和每条规则都有最低样本门槛**，不满足时跳过并标注 `LOW_SAMPLE`，不按 0 或 100% 计算。
- **增速和比率做平滑**，避免「0 单到 1 单」这类跳变排进榜首。
- **流量（曝光、点击）数量级远大于订单，作为「潜力」的主要先行信号。**

门槛和平滑参数属于评分口径，放在 Python `scoring/` 配置中，随 `scoring_version` 变更。Java 只提供原始窗口值。

## 1. 快照 `ai_product_metric_snapshot`

唯一键：`(sku_id, stat_date)`。`stat_date` 为统计截止日期（UTC 日期）。金额用分（整数）或 `DECIMAL(18,4)`，同一仓库内统一。

| 字段 | 含义 | 主用来源 |
|---|---|---|
| `sku_id` / `product_id` | SKU、商品 ID | 商品 |
| `title` / `category_id` | 标题、类目 | 商品 |
| `on_sale` | 是否在售 | 商品 |
| `price` / `cost` | 当前售价、成本 | 价格、成本 |
| `stock_qty` | 可售库存 | 库存 |
| `stock_value` | 库存金额 = `stock_qty × cost`；无成本则空 | 库存 + 成本 |
| `last_sale_date` | 最近一次成交日期；从未成交则空 | 销售 |
| `orders_7d` / `orders_30d` / `orders_prev_30d` / `orders_90d` | 订单数（样本门槛按订单数判断） | 销售 |
| `units_7d` / `units_30d` / `units_prev_30d` / `units_90d` | 件数 | 销售 |
| `gmv_7d` / `gmv_30d` / `gmv_prev_30d` / `gmv_90d` | 销售额 | 销售 |
| `impressions_30d` / `impressions_prev_30d` | 曝光 | 流量 |
| `clicks_30d` / `clicks_prev_30d` | 点击 | 流量 |
| `paid_orders_from_clicks_30d` | 来自点击的成交订单数，用于转化 | 转化 |
| `return_orders_90d` / `refund_orders_90d` | 退货、退款订单数（90 天，样本更稳） | 售后 |
| `review_score` / `review_count` | 评价均分、评价数 | 售后 |
| `refreshed_at` | 快照写入时间 | — |

约束：

- Java 只写**原始计数和金额**，不写增速、比率、`explosion_score`、`risk_level`。
- CTR、CVR、毛利率、退货率、可售天数等比率由 Python 按门槛和平滑规则计算，保证口径只有一份。
- 缺数据保持 `NULL`，Python 跳过并标注 `NO_DATA`。

## 2. 样本门槛与平滑（Python `scoring/` 默认值，可配置）

| 指标 | 计算 | 默认门槛（不满足则 `LOW_SAMPLE`） |
|---|---|---|
| 销售增速 | `(gmv_30d + α) / (gmv_prev_30d + α) - 1`，α 默认取店内 SKU 月均 GMV | `orders_30d + orders_prev_30d ≥ 5` |
| 流量增速 | `(clicks_30d + β) / (clicks_prev_30d + β) - 1` | `clicks_30d + clicks_prev_30d ≥ 50` |
| CTR | `(clicks_30d + a) / (impressions_30d + b)`，向店铺均值收缩 | `impressions_30d ≥ 500` |
| CVR | `(paid_orders_from_clicks_30d + a) / (clicks_30d + b)`，向店铺均值收缩 | `clicks_30d ≥ 50` |
| 毛利率 | `(price - cost) / price` | 有 `cost` 即可 |
| 退货率 / 退款率 | `return_orders_90d / orders_90d` | `orders_90d ≥ 10` |
| 可售天数 | `stock_qty / (units_30d / 30)` | `orders_30d ≥ 3`，否则不算可售天数 |
| 评价分 | 按评价数向店铺均值收缩 | `review_count ≥ 5` |

「向店铺均值收缩」指样本少时结果更接近全店平均，样本多时接近自身真实值，避免小样本 SKU 走极端。

## 3. 批量特征查询（按阶段投影）

Agent 分三阶段取数：**选品打分 → 轻量会签 →（可选）建议补数**。Java 按 `profile` 投影字段，禁止一次吐运营原始全字段。

任务入参 `include_advise`（默认 `false`，方案 B）：

- `false`：只出榜单与销量证据，文末询问是否写投放建议；**不**调 `/features/advise`。
- `true`（用户首句已明确要建议，或确认「要」后带新窗口重跑）：定槽后再调 advise，用 **LLM** 写投放建议（失败则模板降级）。
- 用户仅回复「要」：对话同步拉 advise + LLM，不重跑全店打分。

### 3.1 选品 / 打分：`POST /internal/features/query`

请求：`stat_date`（默认当天）、`on_sale_only`（默认 true）、可选 `category_id`、`sku_ids`（质检批量，上限 50）、`user_id`、`time_window_days`、`profile`（默认 `score`）。

`profile=score` 响应：

- 信封：`snapshot_date` / `row_count` / `source` / `amount_unit`（元，挂响应级，不在每行重复）
- `items[]` **只含**：

| 字段 | 说明 |
|---|---|
| `sku_id` / `title` / `brand` | 身份；`title` 截断约 36 字；不上 `supplier_brand` |
| `on_sale` | 是否在售 |
| `gmv_30d` / `gmv_prev_30d` / `orders_30d` / `orders_prev_30d` | 销售窗口（整型） |
| `impressions_30d` / `impressions_prev_30d` / `clicks_30d` / `clicks_prev_30d` | 流量窗口（对应 goodsPv/goodsUv，整型） |
| `paid_orders_from_clicks_30d` | 支付用户数窗口（orderPays） |
| `rate_per` | 页面转化率展示值（ratePer，两位小数，不作多日加总） |

**不上送**：`goodsFirstPic`、`goodsLink`、`supBrandName`、原始 `goodsPv`/`goodsUv`/`orderSales` 别名堆、每行 `amount_unit`/`source`、板块/大盘。

约束：

- 筛选任务应 `on_sale_only=true` 且不传 2000 个 sku_ids。
- **禁止**在 `load_features` 拉 `dailyPlateList` / `dailyDataList`。
- 禁止在筛选流程里循环调用单 SKU 接口。
- 单次响应约 2000 行可接受；超过 5000 行时再分页（当前规模不必做）。

### 3.2 建议补数：`POST /internal/features/advise`

仅在 `include_advise=true` 或用户确认要建议后调用。请求：`user_id`、可选 `sku_ids`（槽位内，通常 ≤5，作上下文标注）、可选 `days`（默认 7）。

响应：

| 字段 | 说明 |
|---|---|
| `plates[]` | `dailyPlateList` 精简：`stat_field` `stat_field_name` `self_pv` `self_uv` `order_sales` `order_numbers` |
| `store` | 可选 `dailyDataList` 一行摘要：`total_sales` `order_numbers` `hpage_uv` `spu_uv` `conversion_rate` `stat_day` |
| `sku_ids` | 回显请求槽位 |
| `source` | `dailyPlateList` / `no_credentials` / `error` |

用途：写「放哪块」建议；**不能**从板块推出具体商品是否已挂该板块。大盘只作背景一句，不可点名爆品。

## 4. 规则 ID（两端共用）

Python 代码命中后写入报告。Java 不做判定，但必须原样存储和展示。

| 规则 ID | 档 | 典型条件（阈值在 Python 配置，可改） |
|---|---|---|
| `STOCK_LOW` | P0 | 在售且 `stock_qty = 0` 但近 30 天有点击；或满足门槛时可售天数低于阈值 |
| `STOCK_OVER` | P0 | `stock_value` 高于阈值，且 `last_sale_date` 距今超过 N 天（按库存金额和库龄判断，不是「卖得少就算积压」） |
| `PROFIT_LOW` | P0 | 毛利率低于阈值 |
| `PROFIT_NEGATIVE` | P0 | 毛利为负 |
| `PRICE_BELOW_COST` | P0 | `price < cost` |
| `PRICE_CATEGORY_OUTLIER` | P0 | 相对店内同类目价格分位过高或过低（同类目 SKU 少于 5 个时跳过） |
| `SALES_DOWN` | P0 | 满足销售增速门槛，且平滑后增速低于阈值 |
| `RETURN_HIGH` | P1 | 满足门槛，退货率高于阈值或类目分位 |
| `REFUND_HIGH` | P1 | 同上，按退款率 |
| `REVIEW_LOW` | P1 | 满足门槛，平滑后评价分低于阈值 |
| `CTR_LOW` | P1 | 满足门槛，平滑后 CTR 过低 |
| `CVR_LOW` | P1 | 满足门槛，平滑后 CVR 过低 |
| `TRAFFIC_HIGH_CVR_LOW` | P1 | 点击处于店内前列，但平滑后 CVR 过低 |

P2 不用这些 ID：`IMAGE_QUALITY`、`DETAIL_QUALITY`、`AD_ROI`。

未参与判定的规则写入报告 `skipped_rules`，原因只有两种：

- `NO_DATA`：电商没有该字段
- `LOW_SAMPLE`：有数据但样本不够

## 5. 爆品报告 upsert

`PUT /internal/tasks/{taskId}/explosion-report`

### 5.1 头

`task_id, snapshot_date, scoring_version, council_version, time_window_days, top_n, item_count, goal_mode, focus_slots, plan_degraded, focus_count, summary`

| 字段 | 说明 |
|---|---|
| `goal_mode` | `GMV` / `PROFIT` / `CLEARANCE` |
| `focus_slots` | 本周注意力槽位，默认 5，上限 10 |
| `plan_degraded` | 会签/计划修订触达上限或角色降级时为 true |
| `council_version` | 会签 schema/提示词版本，与 `scoring_version` 分立 |
| `focus_count` | 实际进入槽位（`in_focus_slot=true`）的行数 |
| `summary` | Python 生成；Java 直接作完成消息正文 |

### 5.2 行

`sku_id, rank, mode_rank, explosion_score, score_breakdown, skipped_items, quality_risk_level, quality_rule_ids, feature_excerpt, action_bucket, primary_action, in_focus_slot, signal_confidence, risk_veto, council_excerpt, ai_reason, ai_risk, ai_suggestion`

| 字段 | 说明 |
|---|---|
| `explosion_score` | **仅** Python 代码；LLM 不得改写 |
| `mode_rank` | 可选；目标模式下的展示序，非正式分 |
| `action_bucket` | `PUSH` / `FIX_THEN_PUSH` / `WATCH` / `DROP` |
| `primary_action` | 本周主动作短文 |
| `in_focus_slot` | 是否占用本周槽位；`PUSH`+`FIX_THEN_PUSH` 进槽合计 ≤ `focus_slots` |
| `signal_confidence` | `HIGH` / `MID` / `LOW`（会签） |
| `risk_veto` | bool；为 true 时 `action_bucket` 不得为 `PUSH` |
| `council_excerpt` | 可选 JSON，三角色要点快照 |
| `quality_risk_level` | `NONE / LOW / MID / HIGH`（代码规则） |
| `ai_*` | reduce 后最终话术；须与 `action_bucket` 一致；未进会签的行可空 |

`score_breakdown` 为各分项贡献分；`skipped_items` 列出因 `NO_DATA` / `LOW_SAMPLE` 未计入的分项。

同一 `task_id` 覆盖整份报告。

## 6. 质检报告 upsert

`PUT /internal/tasks/{taskId}/quality-report`

- 头：`task_id, snapshot_date, scoring_version, sku_count, high_risk_count, summary`
- 行：`sku_id, quality_score, ops_score, risk_level, explosion_score, explosion_candidate, issues[], skipped_rules[]`
- `issues[]`：`rule_id, severity, actual, threshold, sample_size, evidence, ai_comment`

`quality_score` / `ops_score` 为代码分。`explosion_score` 用同一套 Python 评分函数，保证交叉可比。  
`sample_size` 记录判定所用样本数（如 90 天订单数），方便运营判断结论可信度。  
`ai_comment` 仅对有问题或用户点名的 SKU 生成，批量不超过 50。

## 7. 报告读取（供对话 Agent 回答追问）

`GET /internal/conversations/{conversationId}/reports?limit=3`

返回本会话最近的报告（头 + 行）。Java 必须校验该会话属于本次对话请求携带的 `user_id`，不允许跨用户读取。只读，不触发任何计算。

## 8. 评分版本

Python 配置变更（权重、门槛、平滑参数、阈值）必须 bump `scoring_version`（例如 `explosion-1.2.0`）。报告和 `ai_task.scoring_version` 都记下，便于复盘「当时为什么是这个分」。
