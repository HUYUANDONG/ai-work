# 爆品质检 Agent（V1.0.0）

配套 [requirements-v1.0.0.md](../requirements-v1.0.0.md)、[data-contract.md](../data-contract.md)、[harness.md](harness.md)。

本文件只描述 **Quality 专家策略**。它跑在同一套 Agent Harness 上，不是独立服务。

## 1. 范围

检查商品本身质量与运营表现，输出问题、证据和建议。只通过对话触发。不写回电商。不做 P2（主图 / 详情视觉、推广 ROI、流量来源结构）。

## 2. 和「库存、利润」拆法的对应

质检当初也是按检查项拆的，同样不要做成一堆 Agent。

| 你记得 / 后来补的项 | 现在 | 谁做 |
|---|---|---|
| 库存 | P0 `STOCK_LOW` / `STOCK_OVER` | 代码规则 |
| 利润 | P0 `PROFIT_LOW` / `PROFIT_NEGATIVE` | 代码规则 |
| 价格、趋势 | P0 | 代码规则 |
| 退货、评价、转化 | P1 | 代码规则 |
| 问题解读和建议 | 只对命中项 | LLM |

对外仍是一个 `QUALITY` 任务。

## 3. 维度

### P0（必做）

| 主题 | 规则 ID 示例 |
|---|---|
| 库存健康 | `STOCK_LOW`、`STOCK_OVER` |
| 利润风险 | `PROFIT_LOW`、`PROFIT_NEGATIVE` |
| 价格异常 | `PRICE_BELOW_COST`、`PRICE_CATEGORY_OUTLIER` |
| 销售趋势 | `SALES_DOWN` |

### P1（V1 做，电商侧已有数据）

| 主题 | 规则 ID 示例 |
|---|---|
| 退货 / 退款 | `RETURN_HIGH`、`REFUND_HIGH` |
| 评价 | `REVIEW_LOW` |
| 曝光 / 点击 / 转化 | `CTR_LOW`、`CVR_LOW`、`TRAFFIC_HIGH_CVR_LOW` |

无某列数据或样本不够：该规则进入 `skipped_rules`（原因 `NO_DATA` 或 `LOW_SAMPLE`），不由模型补数。门槛见 [data-contract.md](../data-contract.md) 第 2 节，例如退货率要求 90 天订单不少于 10 单。

注意两条容易误报的规则：

- `STOCK_OVER` 按库存金额和最近成交距今天数判断，不按「近期卖得少」判断。否则在当前订单量下大半个店都会被标积压。
- `RETURN_HIGH` / `REFUND_HIGH` 用 90 天窗口，2 单退 1 单这种情况一律 `LOW_SAMPLE`。

## 4. Graph

```text
parse_intent          解析 SKU 列表、类目、或「全店问题品」
load_features         指定 SKU 则批量查询（≤50）；「全店」则拉全量特征后只把规则命中的 SKU 截到 50 再分析
rule_check            Python 代码命中 P0/P1，计算 quality_score、ops_score、risk_level
attach_explosion      同一套爆品评分函数，写入 explosion_score
explain_issues        LLM 只对有问题的 SKU 写证据解读和建议，引用 sample_size
summarize             生成 summary，作为完成消息正文
upsert_report
```

全店质检禁止把 2000 个 SKU 送进 LLM。代码先过滤，模型只看问题清单。

## 5. 与爆品交叉

- 每条质检结果带 `explosion_score`
- 若该 SKU 同时是「高爆品分 + 高质检风险」，`ai_comment` 必须点明冲突（例如爆但缺货、爆但亏本）
- 规则 ID 与爆品 Agent 完全相同
- **分工**：Explosion 用同一套规则做标签 + 风控会签，产出 `action_bucket` 作战清单；Quality 产出问题清单与证据。用户只要「本周盯谁、能不能硬冲」→ 跑 Explosion 即可；要「完整质检报告」→ 再开本专家（见 [explosion-agent.md](explosion-agent.md)）

## 6. Tool

- `query_features(sku_ids | on_sale_only)`
- `upsert_quality_report(...)`

规则函数本地运行，不是 Tool。

## 7. 评分含义

| 分 | 谁算 | 含义 |
|---|---|---|
| `quality_score` | 代码 | 商品质量：评价、退货退款等 P1 + 负向利润/价格 |
| `ops_score` | 代码 | 运营质量：流量、转化、趋势、库存结构 |
| `risk_level` | 代码 | 由最高严重度规则决定 |
| `ai_comment` | LLM | 解释和建议，不是分数来源 |

阈值在 Python 配置，bump `scoring_version`。

## 8. 对话示例

- 「质检一下 SKU-123」→ 单品 P0+P1 全报告  
- 「看看哪些品在亏本或快断货」→ 全量规则过滤，只解释命中项  
- 「这 20 个候选有没有质量问题」→ 对话 Agent 从本会话最近的爆品报告取出 sku_ids，新建 `QUALITY` 任务，批量 ≤50  
- 「SKU-123 的退货率是多少算高？」→ 对话 Agent 读已有质检报告里的 `actual` / `threshold` / `sample_size` 直接回答  
