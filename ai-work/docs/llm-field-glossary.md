# LLM 字段词典（电商运营数据接口）

来源：电商后台「运营数据」页实际列表字段（`vue-admin-template` → `marketing-manage`），经 `outfit-admin/reportStat/*` 返回。  
**给模型读数、写建议时用本词典；禁止编造未出现的字段，禁止把空值当 0。**

通用约定：

| 约定 | 说明 |
|---|---|
| 列表结构 | 成功时业务体多为 `{ list, total }`；也可能直接是数组 |
| 时间筛 | 查询常用 `startTime` / `endTime`，格式 `yyyy-MM-dd HH:mm:ss` |
| 分页 | `pageNum`、`pageSize` |
| 金额/计数 | 页面未标注「分」；按运营后台展示数值理解，**不要擅自换算单位** |
| 口径混用 | 同一行里可能同时有「实时」销售与「昨日」流量，不可当成同一窗口 |
| 缺字段 | JSON 缺 key 或值为 `null` → 标注未知，勿当 0 |

---

## 1. 商品销量（爆品主源）

- 路径：`POST outfit-admin/reportStat/goodsStatList`
- 页面：日商品销量 `GoodsStatList`

| 字段 | 含义 | LLM 注意 |
|---|---|---|
| `goodsId` | 商品 ID | 选品主键 |
| `goodsName` | 商品名称 | 文案可用 |
| `goodsFirstPic` | 商品主图 URL | 仅展示，不作销量依据 |
| `goodsLink` | 商品链接 | 可引用，勿改写 |
| `goodsBrandId` | 品牌 ID | |
| `gbName` | 品牌名称 | |
| `supBrandName` | 供应商名称 | |
| `orderSales` | 销售额（**实时**） | 爆品排序优先依据之一 |
| `orderNumbers` | 订单数（**实时**） | 爆品排序优先依据之一 |
| `orderPays` | 支付用户数（**实时**） | |
| `goodsPv` | 商品 PV（**昨日**） | 与实时销售额窗口不同 |
| `goodsUv` | 商品 UV（**昨日**） | 同上 |
| `ratePer` | 转化率 | 页面展示值；勿自行用错误窗口重算后当真 |
| `statDay` | 统计日/时间 | 多日查询时可能一行一日；需按 `goodsId` 聚合时先加总销售字段 |

**筛选建议（给模型的规则语言）：**  
优先看 `orderSales` / `orderNumbers`；流量只作辅助；昨日 PV/UV 高但实时订单低 → 可写「有流量待转化」，不要直接判爆。

---

## 2. 日板块流量（投放位辅源）

- 路径：`POST outfit-admin/reportStat/dailyPlateList`
- 页面：日板块流量 `DailyPlateList`

| 字段 | 含义 | LLM 注意 |
|---|---|---|
| `statField` | 板块编号 | 投放位置 ID |
| `statFieldName` | 板块名称 | 建议文案里用名称 |
| `selfPv` | 板块 PV | |
| `selfUv` | 板块 UV | |
| `orderSales` | 板块销售额 | 与商品销量不是同一粒度 |
| `orderNumbers` | 板块订单数 | |
| `statDay` | 时间 | |

**用途：** 回答「爆品更适合放哪块」——用板块流量/转化强弱做**位置建议**。  
**不能：** 从本接口推出具体 `goodsId`；也推不出「某商品已挂在哪块」。

---

## 3. 日品牌销量（辅）

- 路径：`POST outfit-admin/reportStat/brandStatList`
- 页面：日品牌销量 `BrandStatList`

| 字段 | 含义 |
|---|---|
| `brandId` | 品牌 ID |
| `brandName` | 品牌名称 |
| `supplierId` | 供应商 ID |
| `supplierName` | 供应商名称 |
| `orderSales` | 销售额 |
| `grossProfit` | 平台毛利额 |
| `grossProfitRate` | 平台毛利率（%） |
| `orderNumbers` | 支付订单数 |
| `orderPays` | 支付用户数 |
| `refundAmount` | 退款额 |
| `refundNumbers` | 退款件数 |
| `orderSpu` | 动销 SPU 数 |
| `goodsSpu` | 总 SPU 数 |
| `statDay` | 时间 |

无商品 ID。只可做品牌冷热/毛利风险辅助，不能单独出爆品清单。

---

## 4. 日类目销量（辅）

- 路径：`POST outfit-admin/reportStat/categoryStatList`
- 页面：日类目销量 `CategoryStatList`

| 字段 | 含义 |
|---|---|
| `categoryId` | 类目 ID |
| `categoryName` | 类目名称 |
| `goodsSpu` | 商品（SPU）规模相关 |
| `orderSales` | 销售额 |
| `singlePrice` | 客单价 |
| `orderSpu` | 动销 SPU 数 |
| `statDay` | 时间 |

用于「哪种类目更热」；落到具体商品仍要回看商品销量接口。

---

## 5. 周关键词（文案辅）

- 路径：`POST outfit-admin/reportStat/weeklyDataList`
- 页面：周关键词 `WeeklyDataList`

| 字段 | 含义 |
|---|---|
| `statField` | 关键词 |
| `statValue` | PV |
| `statSecondValue` | UV |
| `statWeekly` | 统计时间段 |
| `statDay` | 统计执行日期 |

用于选题/标签；**不是**商品销量。

---

## 6. 日活动销量（辅）

- 路径：`POST outfit-admin/reportStat/activeStatList`
- 页面：日活动销量 `ActiveStatList`

| 字段 | 含义 |
|---|---|
| `activeType` | 活动类型 |
| `activeId` | 活动编号 |
| `activeName` | 活动名称 |
| `activeStartTime` | 活动开始时间 |
| `activeEndTime` | 活动结束时间 |
| `orderSales` | 销售额（实时） |
| `goodsNumbers` | 商品数（昨日） |
| `orderNumbers` | 订单数（实时） |
| `orderPays` | 支付用户数（昨日） |
| `activeCreateName` | 创建人 |
| `activeCreateTime` | 创建时间 |
| `statDay` | 统计时间 |

活动维度；不能直接当商品爆品列表。

---

## 7. 日流量数据（全站汇总，弱相关）

- 路径：`POST outfit-admin/reportStat/dailyDataList`
- 页面：日流量数据 `DailyDataList`

| 字段 | 含义 |
|---|---|
| `totalSales` | 总销量 |
| `orderNumbers` | 订单数 |
| `hpageUv` | 首页总 UV |
| `activeUv` | 活动总 UV |
| `activePv` | 活动总 PV |
| `spuUv` | 商品总 UV |
| `spuPv` | 商品总 PV |
| `conversionRate` | 转换率 |
| `statDay` | 时间 |

全店大盘，**无商品/板块明细**。只可作背景（大盘好/差），不可据此点名爆品。

---

## 8. 喂给模型时的最小用法

1. **选品**：只信任 §1 商品销量字段。  
2. **放哪**：用 §2 板块建议位置，并写明「未验证该品是否已在该板块」。  
3. **品牌/类目/活动/关键词**：辅助叙事，不得替代 §1。  
4. **禁止**：把 `goodsPv`/`goodsUv`（昨日）与 `orderSales`（实时）说成同一天口径；禁止发明 `explosion_score` 等本接口没有的字段。
