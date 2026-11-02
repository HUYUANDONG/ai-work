# 架构说明

完整需求见 [requirements-v1.0.0.md](requirements-v1.0.0.md)。本文区分 **R2 目标结构** 和 **阶段一已落地骨架**。

## 目标运行时（R2）

```text
浏览器（对话）
  │ HTTP / SSE
  ▼
ai-workbench-gateway
  │ 清身份头 → AuthAdapter → 可信身份 + Trace ID
  ▼
ai-workbench-service
  ├── conversation / task / insight（快照、报告）
  ├── Dubbo 只读 → 电商（商品、库存、销售、流量、成本、售后）
  ├── HTTP → Python Harness API（对话 Agent：意图闸门、缺参默认/澄清、建任务、读报告追问）
  └── HTTP ← Python Harness Worker
        ├── 代码路由 task_type → Explosion | Quality
        ├── Explosion：代码打分 + 任务内 multi（指挥/信号/风控/策略会签）→ 作战清单报告
        └── Quality：代码规则 + LLM 解释 → 质检报告
  ├── MySQL ai_workbench
  └── （Python 使用）独立 PostgreSQL Checkpoint（含 Explosion plan 状态）
```

职责：Java 是 Workbench；Python 是一套 Harness。  
V1：**无跨任务全局指挥**；对话入口 + 代码路由。**Explosion 任务内**有作战指挥与会签 multi-agent。详见 [agents/harness.md](agents/harness.md)、[agents/explosion-agent.md](agents/explosion-agent.md)。

Python 仓目录分层（Controller / Service 心智）见 [python-package-layout.md](python-package-layout.md)。

## 阶段一已落地

```text
浏览器
  │ HTTP / SSE
  ▼
ai-workbench-gateway   Spring Cloud Gateway + Nacos 发现
  │ 清除客户端身份头 → 认证适配 → 写入可信身份头 + Trace ID
  ▼
ai-workbench-service   Spring Boot 模块化单体
  │
  ├── Dubbo 注册到 Nacos（尚未消费电商只读接口）
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
5. V1 自营单店，不要求请求携带商家 ID。

## 中间件（阶段一已配置）

- Nacos：服务发现默认开启，配置中心默认关闭。
- Dubbo 3.2.10：注册到 Nacos，`check=false`。只读可重试；写操作 V1 不提供。
- Actuator：`health` / `info` / `metrics`。
- 虚拟线程：Gateway 与 Service 均开启。
- 超时预算：启动时校验外层大于内层。

## 阶段一未接入

MySQL、Flyway、Redis、Sa-Token、Checkpoint PostgreSQL、OSS、电商真实只读 Dubbo、Python Agent。
