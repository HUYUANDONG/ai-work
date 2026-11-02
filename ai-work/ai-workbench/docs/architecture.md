# 架构说明（阶段一）

完整需求见 [requirements-v1.0.0.md](requirements-v1.0.0.md)。本文只描述当前已落地的骨架。

## 运行时结构

```text
浏览器
  │ HTTP / SSE
  ▼
ai-workbench-gateway   Spring Cloud Gateway + Nacos 发现
  │ 清除客户端身份头 → 认证适配 → 写入可信身份头 + Trace ID
  ▼
ai-workbench-service   Spring Boot 模块化单体
  │
  ├── Dubbo 注册到 Nacos（尚未消费电商接口）
  └── 内部 HTTP（阶段二起对接 Python）
```

## 公共模块边界

| 模块 | 可被谁依赖 | 约束 |
|---|---|---|
| common-core | Gateway、Service | 无 Web 依赖 |
| common-logging | Gateway、Service | 无 Servlet / WebFlux 依赖 |
| common-security | Gateway、Service | 无 Servlet / WebFlux 依赖 |
| common-web | 仅 Service | Servlet 全局异常与过滤器 |

## 身份传递

1. Gateway 入口清除 `X-Wb-User-Id`、`X-Wb-Tenant-Id`、`X-Wb-Merchant-Id`、时间戳和签名头。
2. `AuthAdapter` 解析登录态。local 读取 `X-Wb-Dev-User`；其他环境在电商认证接入前视为未登录。
3. Gateway 写入可信身份头；若配置了 `WB_INTERNAL_IDENTITY_SECRET` 则附加 HMAC 签名。
4. Service 校验签名（或 local 允许无签名）后写入 `IdentityContext`。

## 中间件（阶段一已配置）

- Nacos：服务发现默认开启，配置中心默认关闭。
- Dubbo 3.2.10：注册到 Nacos，`check=false`，有副作用调用 `retries=0`。
- Actuator：`health` / `info` / `metrics`。
- 虚拟线程：Gateway 与 Service 均开启。
- 超时预算：启动时校验外层大于内层。

## 阶段一未接入

MySQL、Flyway、Redis、Sa-Token、RocketMQ、OSS、电商真实 Dubbo 接口、Python Agent。
