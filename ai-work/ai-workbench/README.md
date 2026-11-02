# AI 商家运营工作台

面向商家的 AI 运营工作台 Java 后端。Vue 3 前端与 Python Agent 服务各自独立建仓。

当前进度：阶段一工程骨架（中间件与公共能力已配置，业务未实现）。

需求说明见 [docs/requirements-v1.0.0.md](docs/requirements-v1.0.0.md)。

## 模块

```text
ai-merchant-workbench
├── ai-workbench-common
│   ├── ai-workbench-common-core        错误码、分页、超时预算、集中地址配置
│   ├── ai-workbench-common-web         Servlet 统一响应与全局异常（Gateway 不得依赖）
│   ├── ai-workbench-common-security    认证适配、可信身份头、内部签名
│   └── ai-workbench-common-logging     Trace ID、MDC、日志脱敏
├── ai-workbench-gateway                Spring Cloud Gateway
└── ai-workbench-service                模块化单体业务服务
```

## 环境要求

- JDK 21
- Maven 3.9+
- 可选：Nacos 2.x（默认 `127.0.0.1:8848`）。没有 Nacos 时见下方直连方式

## 编译

```bash
mvn clean verify
```

阶段一不连接 MySQL。按当前约定先不由本仓库启动进程，由你在本地启动并反馈报错。

## 本地启动

1. 在仓库根目录复制环境文件（只需做一次）：

```powershell
cd d:\code\ai_workbenth
copy .env.example .env
```

Gateway 和 Service 启动时会自动从仓库根目录加载 `.env`，**不用在 IDEA Run Configuration 里填 Environment**。操作系统里已经存在的环境变量优先，不会被 `.env` 覆盖。

2. 默认 profile 为 `local`。
3. 启动顺序建议：Nacos → `ai-workbench-service` → `ai-workbench-gateway`。IDEA 里直接 Run 两个 `*Application` 即可。

```bash
mvn -pl ai-workbench-service -am spring-boot:run
mvn -pl ai-workbench-gateway -am spring-boot:run
```

- Gateway：`http://127.0.0.1:8081`
- Service：`http://127.0.0.1:8080`
- 探活（需带开发身份头）：`GET http://127.0.0.1:8081/api/v1/system/ping`，请求头 `X-Wb-Dev-User: demo-user`
- 健康检查（无需登录）：`GET http://127.0.0.1:8081/actuator/health`
- OpenAPI（直连 Service，不经 Gateway）：`http://127.0.0.1:8080/swagger-ui.html`

### 无 Nacos 时

把根目录 `.env` 改成：

```text
WB_NACOS_DISCOVERY_ENABLED=false
WB_DUBBO_REGISTRY=N/A
WB_SERVICE_URI=http://127.0.0.1:8080
```

然后照常在 IDEA 里启动，不必再配运行参数。

## 认证说明

电商系统登录方式尚未确认。`local` 使用 `X-Wb-Dev-User` 作为开发身份；`dev` / `prod` 在接入真实认证前会将业务请求视为未登录。

Gateway 会清除客户端提交的 `X-Wb-User-Id` 等身份头，认证成功后再写入带可选 HMAC 签名的可信头。Service 只信任这些头。

## 阶段一未包含

- MySQL / Flyway / MyBatis-Plus / Druid
- Redis / Sa-Token / RocketMQ
- 任务、审批、正式操作等业务
- Python / 前端仓库
