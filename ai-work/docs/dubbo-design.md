# Dubbo 设计（只读，V1 R2）

电商系统是另一套系统。工作台 V1 **只消费只读接口**，不调用创建商品、上架、改价、提交素材。阶段一只完成工作台自身的 Dubbo 客户端注册，**不伪造生产接口**。

完整业务背景见 [requirements-v1.0.0.md](requirements-v1.0.0.md)。特征字段见 [data-contract.md](data-contract.md)。

## 当前配置

- 组件：`dubbo-spring-boot-starter` 3.2.10 + `dubbo-registry-nacos` 3.2.10
- 协议：`dubbo`
- 端口：随机（`-1`）
- 消费方：`check: false`；只读可配置有限重试；超时默认 3000 ms，批量拉数接口单独加大
- 注册：`nacos://${WB_NACOS_SERVER_ADDR}`，电商侧 namespace / group 由 `WB_DUBBO_NACOS_*` 覆盖

## 代码边界

`EcommerceAdapter` V1 能力应是只读聚合，而不是写操作：

| 方法（占位名） | 用途 | 状态 |
|---|---|---|
| `isConfigured()` | 是否已对接真实注册中心 | 保留 |
| `listOnSaleSkus` | 在售 SKU 列表与基础资料 | 待 E-02 |
| `listInventory` | 可售库存 | 待 E-02 |
| `listSalesStats` | 销售汇总（按 SKU、按日或可聚合的订单） | 待 E-02 |
| `listTrafficStats` | 曝光 / 点击 | 待 E-02 |
| `listConversionStats` | 转化 | 待 E-02 |
| `listCost` | 成本 / 供货价 | 待 E-02 |
| `listAfterSalesStats` | 退货、退款、评价 | 待 E-02 |
| `listPrices` | 当前售价 | 待 E-02 |

已确认业务侧这些数据域都有，统计为查库，规模约 2000 SKU、日订单约 30。**接口名、入参、是否已有日表仍未提供**，因此不在本仓编写假的生产 RPC。

local profile 用内存模拟上述只读数据，供快照与 Agent 联调。非 local 且未配置真实 Dubbo 时，快照刷新失败并返回明确错误，不要静默空列表。

**删除 V1 范围：** `createProduct`、上架、改价、提交素材。旧占位若还在代码里，阶段四改为只读前删掉或标废弃。

## 适配原则

1. RPC DTO 独立于工作台快照实体；在 `insight/snapshot` 里映射成契约字段。
2. 优先用电商已有汇总；只有明细时由 Java 按 `stat_date` 聚合后写入快照，不把明细长期堆在工作台。
3. 日订单约 30，按订单明细现场聚合可接受，但仍落快照，保证两个 Agent 读同一截止日。
4. 不在 Adapter 内打分。

## 待补充（阻塞真实对接，不阻塞文档）

| 编号 | 事项 |
|---|---|
| E-01 | 注册中心地址、namespace / group、协议、序列化 |
| E-02 | 上表各只读 API 的 jar 或文档、是否日汇总、时间口径 |
| E-04 | 与 Dubbo 无关，但认证未定则无法在非 local 调通 |

确认后在 `integration/ecommerce` 按真实 API jar 封装。
