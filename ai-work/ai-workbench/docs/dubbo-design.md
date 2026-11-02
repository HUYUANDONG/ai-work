# Dubbo 设计（阶段一占位）

电商系统是另一套系统，接口、注册中心、序列化均未确认。阶段一只完成工作台自身的 Dubbo 客户端集成和注册配置，**不伪造生产接口**。

## 当前配置

- 组件：`dubbo-spring-boot-starter` 3.2.10 + `dubbo-registry-nacos` 3.2.10
- 协议：`dubbo`
- 端口：随机（`-1`）
- 消费方：`check: false`，`retries: 0`，超时默认 3000 ms
- 注册：`nacos://${WB_NACOS_SERVER_ADDR}`，namespace / group 由 `WB_DUBBO_NACOS_*` 覆盖

## 代码边界

`EcommerceAdapter` 目前提供 `isConfigured()`、`createProduct`、`findByProductNumber`。local profile 使用内存模拟；非 local 未接入真实 Dubbo 时拒绝副作用调用。上架、改价、提交素材等方法待 E-02 确认后再加。

## 待补充契约（第十九章）

| 编号 | 事项 |
|---|---|
| E-01 | Dubbo 版本、注册中心地址、namespace / group、协议、序列化 |
| E-02 | 商品创建 / 编辑 / 上架 / 查询、文章或素材发布的 API |
| E-03 | 商品编号全局唯一、可按编号查询；创建接口重复编号错误码；素材提交是否同步返回素材 ID；查询是否读主库 |

确认后在 `integration/ecommerce` 下按真实 API jar 增加调用封装，RPC DTO 独立于工作台数据库实体。
