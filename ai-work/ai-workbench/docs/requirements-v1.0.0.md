# AI 商家运营工作台 V1.0.0 — 项目架构与代码生成总需求（修订稿 R1）

> 本文是在原始需求基础上的合并修订稿，供评审使用。
> 中间件版本与引入方式参照内部参考项目（以下简称"参考项目"）中已经一起运行过的组合；
> 待对接的电商系统是另一套系统，其接口、认证和注册中心信息尚未提供，均列入第十九章"待确认信息"。

## 修订摘要（相对原始需求）

| 编号 | 修订内容 | 原因 |
|---|---|---|
| R1-01 | 本仓库只包含 Java 部分；Vue 3 前端与 Python Agent 服务各自独立建仓 | 范围收敛 |
| R1-02 | Spring Cloud Alibaba 版本由 2022.0.0.0 改为 2023.0.1.2 | 2022.0.0.0 对应 Spring Cloud 2022.0.x，与 2023.0.0 不配套；参考项目实际使用 2023.0.1.2 |
| R1-03 | RocketMQ 版本明确为 `rocketmq-spring-boot-starter` 2.3.1 + `rocketmq-client` 5.3.0（Remoting 协议），但 V1.0.0 不引入，见 R1-15 | 与参考项目一致 |
| R1-04 | "MyBatis 3.0.3"更正为 `mybatis-spring-boot-starter` 3.0.3 | 3.0.3 是 Starter 版本，不是 MyBatis 核心版本 |
| R1-05 | 新增"配置与环境管理"章节 | 地址集中管理、密钥不入库、按环境区分 |
| R1-06 | `ai_task` 增加 `lease_token`、`cancel_requested_at` 字段 | 防止旧 Worker 覆盖新结果；协作式取消 |
| R1-07 | 新增任务状态转换表 | 原文只有状态列表，缺少合法转换定义 |
| R1-08 | 审批增加内容摘要、过期时间、拒绝语义 | 保证"批准的内容 = 执行的内容" |
| R1-09 | 外部操作增加 `UNKNOWN` 状态与核对流程；幂等键跨执行尝试保持稳定 | 超时后结果不确定 |
| R1-10 | 正式业务副作用只能由 Java 执行，Python 不直连电商系统 | 权限、幂等、审计集中管控 |
| R1-11 | Java ↔ Python 接口按调用方向拆分，契约文档放在本仓库 | Python 独立建仓，需要单一契约来源 |
| R1-12 | 数据库迁移工具确定为 Flyway | 原文为二选一 |
| R1-13 | 阶段四改为"业务集成框架"，具体业务工作流按后续需求逐个接入 | 不一次性实现全部业务 |
| R1-14 | 阶段一 Dubbo 验收口径改为"本地注册与启动"，不声称已与电商系统互通 | 电商系统信息未提供 |
| R1-15 | 任务派发改为拉取模式：Python Worker 调用 Java 领取接口，MySQL 任务表充当队列；V1.0.0 不引入 RocketMQ 和 Outbox 投递器，`ai_outbox` 表不建；`ai_task` 增加 `priority`、`available_at`、`next_action` 字段 | Python 的 RocketMQ 5.x 官方客户端依赖集群部署 Proxy；任务正确性本就由领取接口和租约保证，消息只起通知作用 |
| R1-16 | RocketMQ + Outbox 重新定位为"系统间事件通知"扩展，出现真实消费方时再引入 | 一对多分发、跨系统解耦才是消息队列的长期价值 |
| R1-17 | 正式操作增加不可回头点、`PENDING` 超时转 `UNKNOWN`、取消生效条件、`has_external_effect` 标记和四层防重复设计；E-03 改为前置条件 | 请求已发出后任务被取消或接管时，避免结果丢失和重复发送 |
| R1-18 | 电商系统不做重复判定：正式操作按"天然幂等 / 非幂等有核对键 / 非幂等无核对键"分类处理；创建商品以商品编号作为核对键；操作记录增加 `idempotency_kind`、`reconcile_key`、`target_id` | 已确认电商系统不支持幂等键，需由工作台自行核对结果 |
| R1-19 | 所有正式操作默认先由发起人人工确认再发送；素材采用"宁可重复"策略并增加内容级去重（12.7）；素材任务以"已提交审核"为成功，审核状态实时查询 | 发送前拦住错误内容和重复提交；素材有电商系统人工审核兜底 |
| R1-20 | 新增第十三章"健壮性设计"（资源隔离与上限、数据库时间、`READ COMMITTED`、超时预算、依赖故障行为、运行指标）；新增 10.4 版本演进与 12.8 人工处理入口；`ai_task` 增加 `workflow_version`、`deadline_at`；原第十三至十八章顺延为第十四至十九章 | 补齐资源耗尽、时钟偏差、版本升级、依赖故障和人工处理等场景 |

---

## 一、项目目标与基本原则

建设一个面向商家的 AI 运营工作台。整体由三个独立仓库组成：

| 仓库 | 技术栈 | 本文范围 |
|---|---|---|
| 前端 | Vue 3 + TypeScript | 不在本仓库，只约定 HTTP / SSE 接口 |
| Java 后端（本仓库） | Spring Boot 3.2.2 | **本文主体** |
| Python Agent | FastAPI + LangGraph | 不在本仓库，只约定内部 API 契约 |

V1.0.0 用于内部使用，目标是稳定、可运行、可扩展的核心业务系统，不追求一次性建设完整的微服务治理、限流、评测和数据分析平台。

业务方向（具体工作流在后续迭代中逐个定义，V1.0.0 先建设承载它们的框架）：

- AI 多轮对话和流式输出。
- AI 商品创建、编辑、字段补全和校验。
- 调用电商系统执行商品上架等正式操作。
- 营销文章文案、图片、排版生成；预览、草稿和正式发布。
- 人工审批、任务状态查询和执行结果追踪。
- 为营销活动、运营分析和更多 Agent 工具预留扩展能力。

### 1.1 核心原则

1. 电商系统是商品、SKU、库存、价格、正式上架和发布状态的权威来源。
2. 工作台不建第二套权威商品库，只保存会话、草稿、任务、审批、执行和审计数据。
3. Java 是工作台业务任务状态的唯一权威方。Python 不直接写 `ai_task`。
4. Python 负责 Agent 工作流、模型调用、工具编排和 LangGraph 状态恢复。
5. **所有正式业务副作用（上架、发布等）只能由 Java 执行。** Python 工具通过 Java 内部 API 发起，Java 负责权限、幂等、审批校验和操作记录，再通过 Dubbo 或适配器调用电商系统。
6. Java 与 Java 之间优先使用 Dubbo RPC。
7. Java 与 Python 之间使用受保护的内部 HTTP API。后台长任务采用拉取模式：Python Worker 主动向 Java 领取任务，MySQL 任务表充当队列，领取接口是任务执行的唯一入口。
8. Gateway 与 Workbench Service 独立部署。
9. Workbench Service 采用模块化单体，不为形式拆分微服务。
10. 暂不实现 Sentinel 限流、Agent 评测平台和自动扩缩容。
11. 即使内部使用，任务幂等、权限校验、异常处理、并发领取保护和故障恢复仍是 V1.0.0 的必要能力。

---

## 二、总体架构

```text
Vue 3 + TypeScript（独立仓库）
        |
        | HTTP / SSE
        v
ai-workbench-gateway（Spring Cloud Gateway，WebFlux）
        |
        | HTTP（lb://ai-workbench-service，Nacos 服务发现）
        v
ai-workbench-service（Spring Boot 3.2.2，模块化单体）
        |
        +---- Dubbo RPC ----------> 电商系统（待确认）
        |
        +---- 内部 HTTP API ----> Python Agent API（独立仓库：流式对话等）
        |
        +<--- 内部 HTTP API ----- Python Worker（独立仓库：领取任务、心跳、回调）
        |
        +---- MySQL（工作台独立库 ai_workbench，任务表兼作任务队列）
        +---- Redis（按需）
        +---- Alibaba Cloud OSS（图片、文件、大结果，按需）
```

### 2.1 流式对话链路

浏览器 → Gateway → Workbench Service → Python Agent API 的流式接口。

- Workbench 负责鉴权、会话归属校验，以及用户消息和最终助手消息的落库。
- Gateway 对流式路由关闭响应缓冲，并单独设置较长的空闲超时，避免流式输出被截断。
- 用户中途断开时，Workbench 将已生成内容标记为"不完整"并落库，不丢弃。
- V1.0.0 不支持断线续传（`Last-Event-ID`），断线后前端重新拉取历史消息。

### 2.2 通信协议

| 链路 | 协议 |
|---|---|
| 浏览器 → Gateway | HTTP/HTTPS、SSE |
| Gateway → Workbench Service | HTTP，Nacos 服务发现 + Spring Cloud LoadBalancer |
| Java → Java（电商系统） | Dubbo RPC |
| Java ↔ Python | 内部 HTTP API |
| 后台异步任务 | Python Worker 通过内部 HTTP API 拉取（见第九章） |
| 系统间事件通知 | RocketMQ（后续扩展，V1.0.0 不实现） |
| 大文件、图片 | OSS 直传或受控上传 |

Gateway 不改造为 Dubbo 路由器。

---

## 三、技术栈与版本基线

### 3.1 原则

1. 中间件版本与引入方式参照参考项目，参考项目中已一起运行的组合视为首选。
2. 被 Spring Boot / Spring Cloud / Spring Cloud Alibaba BOM 管理的依赖不手动指定版本。
3. 只引入当前确实需要的组件，不为沿用清单而引入。
4. 最终版本以本仓库实际构建结果为准，验证结果记录在 `docs/architecture-decisions.md`。未实际验证的项目必须标注"未验证"。

### 3.2 V1.0.0 采用的组件

| 组件 | 版本 | 引入方式 | 引入阶段 |
|---|---|---|---|
| JDK | 21 | — | 一 |
| Spring Boot | 3.2.2 | `spring-boot-starter-parent` 继承 | 一 |
| Spring Cloud | 2023.0.0 | `spring-cloud-dependencies` BOM 导入 | 一 |
| Spring Cloud Alibaba | 2023.0.1.2 | `spring-cloud-alibaba-dependencies` BOM 导入 | 一 |
| Spring Cloud Gateway | BOM 管理 | `spring-cloud-starter-gateway` | 一 |
| Spring Cloud LoadBalancer | BOM 管理 | `spring-cloud-starter-loadbalancer` | 一 |
| Nacos 服务发现 | BOM 管理 | `spring-cloud-starter-alibaba-nacos-discovery` | 一 |
| Nacos 配置中心 | BOM 管理 | `spring-cloud-starter-alibaba-nacos-config`，通过 `spring.config.import: optional:nacos:` 加载，不使用 bootstrap | 一（可选） |
| Apache Dubbo | 3.2.10 | `dubbo-spring-boot-starter` + 注册中心扩展（参考项目为 `dubbo-registry-nacos`，实际以电商系统为准） | 一 |
| MySQL 驱动 | 8.0.27 | `mysql:mysql-connector-java`（与参考项目一致） | 二 |
| MyBatis-Plus | 3.5.5 | `mybatis-plus-spring-boot3-starter` | 二 |
| Druid | 1.2.20 | 与参考项目一致，`spring.datasource.type=com.alibaba.druid.pool.DruidDataSource`（见 3.4 注意事项） | 二 |
| Flyway | BOM 管理 | `flyway-core` + `flyway-mysql` | 二 |
| Lombok | 1.18.30 | 编译期注解处理器 | 一 |
| Hutool | 5.8.22 | `hutool-all`，仅用于通用工具，业务逻辑不依赖 | 一 |
| Fastjson2 | 2.0.42 | 仅在确有需要时使用；Web 层 JSON 统一用 Jackson | 按需 |
| Logback | BOM 管理（1.4.14） | Spring Boot 默认 | 一 |
| Actuator | BOM 管理 | `spring-boot-starter-actuator` | 一 |
| OpenAPI 文档 | springdoc-openapi 2.x（具体版本构建时确定） | Service 用 webmvc-ui；Gateway 不暴露 | 一 |

### 3.3 条件引入的组件

| 组件 | 版本 | 引入条件 |
|---|---|---|
| Sa-Token | 1.37.0 | 仅当电商系统认证采用 Sa-Token 或可兼容时引入。引入方式参照参考项目：Gateway 用 `sa-token-reactor-spring-boot3-starter`（排除 `spring-boot-starter-web`），Service 用 `sa-token-spring-boot3-starter`，会话存储用 `sa-token-redis-jackson` + `commons-pool2` |
| Redis | BOM 管理 | `spring-boot-starter-data-redis`，在认证会话、共享状态等确有需要时引入 |
| Redisson | 3.24.3 | `redisson-spring-boot-starter`，仅在需要分布式锁时引入。V1.0.0 的任务并发控制使用数据库条件更新，不依赖分布式锁 |
| Alibaba Cloud OSS | 3.15.1 | `aliyun-sdk-oss`，在图片、文件业务接入时引入 |
| MapStruct | 1.5.5.Final | 如使用，API 与注解处理器统一为同一版本（参考项目两者版本不一致，不沿用） |
| Guava | 32.1.3-jre | 仅在确有需要时引入 |
| RocketMQ | starter 2.3.1 / client 5.3.0 | 仅在启用系统间事件通知时引入（见 9.6）。引入方式参照参考项目：`rocketmq-spring-boot-starter` 2.3.1，`dependencyManagement` 中将 `rocketmq-client` 固定为 5.3.0，Remoting 协议直连 NameServer；只由 Java 收发 |

### 3.4 构建时需要验证的事项

| 事项 | 说明 |
|---|---|
| Druid 连接池参数绑定 | 参考项目把 `initial-size`、`max-active` 等直接写在 `spring.datasource` 下，使用原生 Druid jar 时这些参数不一定会绑定到 Druid 上。工作台需要验证参数实际生效，必要时改用 `druid-spring-boot-3-starter` 1.2.20 或显式绑定 |
| MyBatis-Plus 单 Starter | 参考项目同时引入了 `mybatis-spring-boot-starter` 3.0.3，工作台只引入 MyBatis-Plus Starter；如构建出现缺失，再按参考项目补齐 |
| Dubbo 与 JDK 21 | 序列化方式需与电商系统一致；如为 hessian2，可能需要 `--add-opens` 启动参数 |
| `SKIP LOCKED` 领取 | 需在实际 MySQL 版本上验证 `SELECT ... FOR UPDATE SKIP LOCKED`（MySQL 8.0.1 起支持）与 MyBatis-Plus 的配合，以及并发领取不重复 |

### 3.5 不引入的组件

| 组件 | 原因 |
|---|---|
| Sentinel（含 Gateway 适配） | V1.0.0 暂缓限流熔断 |
| Seata | 不把 Agent 长流程放入分布式事务 |
| XXL-Job | 使用轻量的进程内调度 + 数据库条件更新完成巡检 |
| JetCache | 当前无多级缓存需求 |
| ShardingSphere（及其要求的 snakeyaml 降级） | 不分库分表 |
| Elasticsearch / Kibana / Logstash | 暂缓日志与检索平台 |
| Canal | 无 CDC 需求 |
| RocketMQ（V1.0.0） | 任务派发采用拉取模式，当前没有消息消费方；作为事件通知扩展保留在 3.3 |
| Spring Cloud Stream RocketMQ | 将来引入 RocketMQ 时也只保留 Starter 一种接入方式 |
| dynamic-tp | 暂缓线程池治理 |

参考项目中以下写法不沿用：手动锁定 `spring-web` 6.1.3（BOM 已管理）、Spring Milestone 仓库、与整体版本不一致的 `spring-cloud-alibaba-sentinel-gateway` 2023.0.3.3。

---

## 四、配置与环境管理

1. **地址集中管理。** 沿用参考项目的做法：在公共模块中提供一个集中的地址配置文件（例如 `wb-base.yml`，前缀 `wb.*`），各应用通过 `spring.config.import` 引入。
2. **密钥不入库。** 数据库密码、Redis 密码、OSS AccessKey、内部服务签名密钥一律通过环境变量注入，例如 `${WB_MYSQL_PASSWORD}`，配置文件中不写默认值。
3. **按环境区分。** 使用 `local`、`dev`、`prod` 三个 Profile。Redis SSL、连接池大小等因环境而异的配置放在对应 Profile 中。
4. **环境变量模板。** 提供 `.env.example`，列出全部变量及说明，不含真实值。
5. **Nacos 命名空间。** 工作台自身的服务注册与配置使用独立命名空间；Dubbo 注册所在的命名空间与分组以电商系统为准。
6. **数据库独立。** 工作台使用独立库（建议 `ai_workbench`），不与电商系统共用库。

---

## 五、Maven 多模块结构

```text
ai-merchant-workbench/
├── pom.xml
├── README.md
├── .env.example
├── docs/
│   ├── requirements-v1.0.0.md          本文
│   ├── architecture.md
│   ├── architecture-decisions.md
│   ├── database-design.md
│   ├── api-design.md                   对前端的 HTTP / SSE 接口
│   ├── internal-api-contract.md        Java ↔ Python 内部 API 契约（带版本号）
│   ├── task-dispatch-design.md         拉取派发、租约与恢复设计
│   ├── dubbo-design.md
│   ├── security-design.md
│   ├── deployment.md
│   └── failure-recovery.md
├── ai-workbench-common/
│   ├── ai-workbench-common-core/        常量、错误码、分页、ID、通用类型（无 Web 依赖）
│   ├── ai-workbench-common-web/         Servlet：统一响应、全局异常、参数校验
│   ├── ai-workbench-common-security/    用户上下文、可信身份、内部服务签名、资源归属抽象
│   └── ai-workbench-common-logging/     MDC、Trace ID、脱敏
├── ai-workbench-gateway/
└── ai-workbench-service/
```

### 5.1 模块约束

1. **Gateway 基于 WebFlux，不能依赖任何 Servlet 相关模块。** `common-web` 只给 Service 使用；`common-security` 和 `common-logging` 中与 Servlet 相关的部分（Filter、拦截器）与响应式部分分开放置，或由各应用自行实现。
2. 响应式环境下 MDC 不会自动随线程传递，Gateway 的 Trace ID 通过 Reactor Context 或 Micrometer context-propagation 传递，并写入转发请求头。
3. 公共模块不得反向依赖业务模块，禁止循环依赖。
4. 不为形式创建空模块或无实际价值的抽象。原始需求中的 `common-messaging` 在 V1.0.0 没有使用方，暂不创建，启用事件通知时再加。

### 5.2 Workbench Service 内部模块

```text
conversation/      会话与消息、流式对话转发
task/              任务、状态机、领取派发、租约、重试、巡检
approval/          人工审批
workspace/         草稿与工作区内容
integration/
  ecommerce/       电商系统适配器（Dubbo）
  agent/           Python Agent API 客户端
execution/         执行尝试（ai_run）记录
operation/         正式业务操作网关与审计
internal/          面向 Python 的内部 API
observability/     日志、指标、健康检查
```

每个模块按实际复杂度划分 Controller、Service、Domain、Repository/Mapper、DTO、Converter，不强行套满所有分层。

---

## 六、Dubbo RPC 设计

### 6.1 基本要求

1. 先调查电商系统的 Dubbo 版本、注册中心、协议、序列化、接口契约和治理规范，优先兼容其现有体系。
2. 参考项目的接入方式（`dubbo-spring-boot-starter` + Nacos 注册、`dubbo` 协议、消费方 `check: false`）作为默认模板，与电商系统不一致时以电商系统为准。
3. 电商系统接口未明确前，只定义 `integration/ecommerce` 下的 Adapter 契约和待补充清单，**不伪造生产接口**。

### 6.2 调用规范

1. RPC 接口与实现分离；RPC DTO 独立于数据库实体。
2. 统一配置连接和调用超时（默认参考项目的 3000 ms，按接口单独调整）。
3. **有副作用的调用（上架、发布等）`retries=0`**，由业务层基于幂等键决定是否重试；只读查询可配置有限重试。
4. 调用结果统一归类为四种：成功、业务失败、服务不可用（确定未执行）、结果不确定（超时等）。"结果不确定"必须进入第十二章的核对流程。
5. 关键调用记录 Trace ID、请求关联 ID、耗时和结果分类。

---

## 七、认证、权限与安全

### 7.1 认证接入

1. 复用电商系统的登录认证，不自建登录系统。
2. 认证方式待确认（见第十九章）。代码中通过 `AuthAdapter` 抽象隔离：
   - 如果电商系统使用 Sa-Token：按 3.3 中参考项目的方式接入，共享其会话存储。
   - 如果是其他方式（JWT、Session 等）：实现对应的适配器。
3. Gateway 完成登录校验后，将可信身份写入内部请求头，并对外部传入的同名请求头先行清除，防止伪造。
4. Service 只信任 Gateway 写入的身份（或自行通过同一认证组件解析），不信任前端提交的 `user_id`、`tenant_id`、`merchant_id`。

### 7.2 身份模型

- 工作台记录稳定的 `user_id`；`tenant_id`、`merchant_id` 设为可空字段，其含义与取值来源在确认电商系统身份模型后确定。
- 不复制密码，不在任务数据中持久化原始登录 Token。
- 异步任务执行正式操作时，使用任务创建时记录的身份上下文（`user_id` 等），并在执行前重新校验权限。

### 7.3 资源归属

会话、消息、任务、审批、操作记录的查询和变更都必须校验归属。归属校验在 Service 层统一实现，不依赖前端传参。

### 7.4 内部服务认证（Java ↔ Python）

- 使用 HMAC-SHA256 签名：请求头携带服务标识、时间戳、随机数和签名；时间窗口 5 分钟，随机数短期去重。
- 密钥通过环境变量注入，两个方向使用不同密钥。
- 内部 API 不经过对外 Gateway，只在内网暴露。

---

## 八、数据库与核心数据模型

### 8.1 通用约定

- MySQL 8.0，字符集 `utf8mb4`，排序规则 `utf8mb4_0900_ai_ci`，时间统一按 UTC 存储。
- 迁移工具：Flyway，脚本放在 `ai-workbench-service/src/main/resources/db/migration`。
- 主键使用 `BIGINT`；对外暴露和跨系统传递的标识（`task_id`、`run_id`、`approval_id`、`operation_id` 等）使用独立的字符串标识并建唯一索引。生成方式在阶段二确定（候选：Hutool Snowflake，workerId 通过配置分配）。
- 大对象（模型完整输出、图片、长文）存 OSS，业务表只存引用。

### 8.2 表清单

| 表 | 用途 |
|---|---|
| `ai_conversation` | 会话 |
| `ai_message` | 消息（含流式中断标记） |
| `ai_task` | 业务任务 |
| `ai_run` | 每次执行尝试 |
| `ai_task_approval` | 人工审批 |
| `ai_operation_record` | 外部正式操作记录（兼作正式操作的幂等记录） |

原始需求中的 `ai_outbox` 在 V1.0.0 不建表，其设计保留在 9.6 作为事件通知扩展。内部 API 回调的幂等由任务状态、`run_id` 和 `lease_token` 保证（见 10.1），不单独建幂等表。

### 8.3 `ai_task`

在原始字段基础上增加：

| 字段 | 说明 |
|---|---|
| `task_id` | 对外业务标识，唯一 |
| `lease_token` | 每次领取任务时重新生成。Python 的心跳和所有结果回调都必须携带，Java 用条件更新校验，不匹配即拒绝，防止旧 Worker 覆盖新结果 |
| `cancel_requested_at` | 取消请求时间，非空表示已请求取消（协作式取消） |
| `idempotency_key` | 创建任务的幂等键（用户 + 客户端请求号），唯一 |
| `input_ref` | 任务输入引用 |
| `priority` | 领取优先级，数值越大越优先，默认 0 |
| `available_at` | 最早可被领取的时间。新建任务为创建时间；进入 `RETRY_WAIT` 时设为退避后的时间 |
| `next_action` | Worker 领取后应执行的动作：`START`（从头开始）或 `RESUME`（按 `thread_id` 从 Checkpoint 恢复） |
| `workflow_version` | 任务创建时确定的 Python 工作流版本。领取时只分配给声明支持该版本的 Worker（见 10.4） |
| `deadline_at` | 任务总时限，默认创建后 48 小时（按任务类型可配置）。超过即转为 `FAILED`（错误码 `TASK_DEADLINE_EXCEEDED`），避免在重试、恢复、核对之间无限拖延；仍有在途操作时，按 8.4 取消生效条件等核对完成后再转换 |
| `has_external_effect` | 是否已产生外部副作用（任一正式操作 `SUCCEEDED` 时置为 1）。任务被取消或失败时，前端据此提示用户"已有操作生效"，并展示对应操作记录 |

其余字段沿用原始需求：`id, task_type, task_status, user_id, tenant_id, merchant_id, conversation_id, thread_id, current_run_id, progress, current_step, result_ref, error_code, error_message, attempt_count, max_attempts, lease_owner, lease_expires_at, last_heartbeat_at, version, created_at, updated_at, started_at, finished_at`。

关键索引：
- `(task_status, task_type, priority, available_at)`：领取任务。
- `(task_status, lease_expires_at)`：租约过期巡检。
- `(task_status, deadline_at)`：任务总时限巡检。
- `(user_id, created_at)`：用户任务列表。
- `(task_status, updated_at)`：归档与清理。

### 8.4 任务状态与转换

| 当前状态 | 目标状态 | 触发 |
|---|---|---|
| `QUEUED` | `RUNNING` | Worker 领取成功（生成新的 `run_id` 和 `lease_token`，`attempt_count` 加 1） |
| `QUEUED` | `CANCELLED` | 用户取消 |
| `RUNNING` | `SUCCEEDED` | Worker 上报成功（令牌校验通过） |
| `RUNNING` | `WAITING_APPROVAL` | Worker 上报需要审批（Checkpoint 已保存） |
| `RUNNING` | `RETRY_WAIT` | 可重试失败，且 `attempt_count < max_attempts`；按退避策略设置 `available_at` |
| `RUNNING` | `FAILED` | 不可重试失败，或重试次数耗尽 |
| `RUNNING` | `CANCELLED` | 已请求取消，且 Worker 确认停止或租约过期（需满足下方"取消生效条件"） |
| `RUNNING` | `RETRY_WAIT` / `FAILED` | 租约过期巡检（按剩余次数判断） |
| `RUNNING` | `RETRY_WAIT` | 已请求取消、租约过期，但存在在途操作；等待核对巡检完成取消（已请求取消的任务不会被领取） |
| `RETRY_WAIT` | `RUNNING` | `available_at` 已到，Worker 直接领取（不需要中间调度步骤） |
| `RETRY_WAIT` | `CANCELLED` | 用户取消，或核对巡检确认在途操作已有确定结果（需满足"取消生效条件"） |
| `WAITING_APPROVAL` | `QUEUED` | 审批通过，`next_action` 置为 `RESUME`，等待 Worker 领取 |
| `WAITING_APPROVAL` | `CANCELLED` | 审批拒绝、审批过期或用户取消（`error_code` 区分原因） |
| 任一非终态 | `FAILED` | 超过 `deadline_at`（错误码 `TASK_DEADLINE_EXCEEDED`，需满足"取消生效条件"中关于在途操作的同样要求） |

`SUCCEEDED`、`FAILED`、`CANCELLED` 为终态，不可再转换。

**取消生效条件**：任务只有在不存在 `PENDING` 或 `UNKNOWN` 状态的操作记录时，才能转入 `CANCELLED`。不满足时：

- 记录 `cancel_requested_at`，任务保持当前状态，不会再被领取，也不能再发起新的正式操作。
- 由第十二章的核对巡检在在途操作有确定结果后完成取消。
- 取消前已成功的操作不会被撤回，`has_external_effect` 标记为 1。V1.0.0 不做自动补偿，补偿由用户作为新的正式操作发起（同样需要审批与幂等键）。

实现要求：

- 状态转换集中在状态机组件中，非法转换抛出明确异常。
- 每次转换使用条件更新：`WHERE task_id=? AND task_status=? AND version=?`，Worker 回调另加 `current_run_id=? AND lease_token=?`；影响行数为 0 时按并发冲突处理。
- 运行中取消为协作式：设置 `cancel_requested_at`，Worker 在下一次心跳的响应中获知并停止。

### 8.5 `ai_run`

沿用原始字段：`run_id, task_id, thread_id, attempt_no, model_name, model_version, prompt_version, workflow_version, tool_version, start_time, end_time, duration_ms, input_tokens, output_tokens, run_status, error_code, error_message, trace_id`。唯一约束：`(task_id, attempt_no)`。

### 8.6 `ai_task_approval`

| 字段 | 说明 |
|---|---|
| `approval_id` | 唯一标识 |
| `task_id`、`run_id`、`thread_id` | 关联 |
| `approval_type` | 审批类型（如商品上架、文章发布） |
| `content_ref` | 待审内容引用 |
| `content_digest` | 待审内容的 SHA-256 摘要。执行正式操作前比对，不一致则拒绝执行 |
| `requester_id`、`approver_id` | 发起人、审批人 |
| `approval_status` | `PENDING` / `APPROVED` / `REJECTED` / `EXPIRED` / `CANCELLED` |
| `decision_comment` | 审批意见 |
| `expires_at`、`decided_at` | 过期时间、决定时间 |
| `version`、`created_at`、`updated_at` | — |

同一任务同一时刻最多一条 `PENDING` 审批（用生成列 + 唯一索引实现）。

**发送前人工确认规则（V1.0.0）：**

| 事项 | 规则 |
|---|---|
| 适用范围 | **所有正式操作默认必须先人工确认再发送**，包括创建商品、上架下架、改价、提交素材。后续可按操作类型配置放开低风险操作 |
| 确认人 | V1.0.0 由任务发起人本人确认；需要第二人复核的操作类型，后续按类型单独配置 |
| 确认内容 | 向用户展示即将发送的完整内容；确认时记录 `content_digest`，发送前比对，不一致则拒绝发送 |
| 批量确认 | 一次生成多个商品或素材时支持批量确认，但每一项分别生成审批记录、内容摘要和操作记录，可逐项拒绝 |
| 过期 | 默认 24 小时未处理即过期，任务取消（可配置，见 B-02） |

人工确认发生在发送之前，只能拦住错误内容和重复提交，不能解决"已发送但结果不确定"的问题，后者仍按 12.6 处理。

### 8.7 `ai_operation_record`

在原始字段基础上：

- `operation_status`：
  - `PENDING`：已占位，调用进行中。
  - `SUCCEEDED`：电商系统确认成功。
  - `FAILED`：确定失败，由 `failure_type` 区分 `NOT_EXECUTED`（确定未执行，例如服务不可用、连接被拒绝）与 `BUSINESS_REJECTED`（电商系统业务拒绝）。
  - `UNKNOWN`：结果不确定，例如调用超时，或 `PENDING` 超时未更新（见第十二章）。
- **`idempotency_key` 由 `task_id + 业务步骤标识` 生成，跨执行尝试保持不变**，不能用 `run_id` 生成，否则重试时会产生重复副作用。唯一约束：`(operation_type, idempotency_key)`。
- `external_request_id`：传给电商系统的请求号，仅用于日志追踪。电商系统不做重复判定（见 E-03）。
- `idempotency_kind`：操作分类，由操作类型决定（见 12.6）：`NATURAL`（天然幂等）、`RECONCILABLE`（非幂等，有核对键）、`DUPLICATE_TOLERANT`（非幂等，重复可接受）、`MANUAL`（非幂等，无核对键）。
- `dedupe_key`：内容级去重用的生成列，带唯一索引（见 12.7）。
- `reconcile_key`：非幂等操作用于核对结果的业务唯一值，例如创建商品时的商品编号。首次发送前确定并落库，此后不得更改。
- `target_id`：电商系统返回或核对查到的对象 ID。
- 增加 `failure_type`、`approval_id`、`content_digest`、`sent_at`、`send_count`、`reconcile_count`、`next_reconcile_at`。
- 索引：`(operation_type, reconcile_key)`，用于核对与排障。

### 8.8 数据保留与清理

| 数据 | 默认保留策略（可配置） |
|---|---|
| `ai_task` 已结束任务 | 90 天后归档或清理，保持任务表小而热，避免拖慢领取查询 |
| `ai_run` | 180 天 |
| `ai_operation_record` | 长期保留（审计） |
| 会话与消息 | 待业务确认 |

清理任务分批删除，单批限量，避免长事务和锁等待。所有列表查询必须分页，禁止无界查询。

---

## 九、任务派发（拉取模式）

### 9.1 选型理由

- 任务能否执行、由谁执行，始终由 Java 的领取接口和租约决定。消息队列在派发链路中只能起"通知有新任务"的作用，不承担正确性。
- Agent 任务耗时长，并发上限受模型调用限额约束，MySQL 任务表足以承担队列职责。
- 拉取模式天然带背压：Worker 有空闲才领取，Python 不可用时任务留在表中，恢复后继续处理。
- Python 无需 RocketMQ 客户端，规避了 5.x 官方客户端依赖集群 Proxy 的问题。

### 9.2 领取流程

1. Worker 调用领取接口，携带 `worker_id`、可处理的 `task_type` 列表、支持的 `workflow_version` 列表和本次最多领取数量（默认 1）。
2. Java 在一个本地事务内（隔离级别 `READ COMMITTED`，见 13.2）：
   - 查询 `task_status IN ('QUEUED','RETRY_WAIT') AND available_at <= 数据库当前时间`，且 `task_type`、`workflow_version` 与 Worker 声明匹配，按 `priority DESC, available_at ASC` 排序，使用 `FOR UPDATE SKIP LOCKED` 锁定。
   - 将任务转为 `RUNNING`，生成 `run_id` 和 `lease_token`，写入 `lease_owner`、`lease_expires_at`，`attempt_count` 加 1。
   - 插入 `ai_run` 记录。
3. 返回 `task_id`、`thread_id`、`run_id`、`lease_token`、租约到期时间、`next_action`、任务输入引用。
4. 没有可领取的任务时，接口最长等待一段时间（长轮询，默认 20 秒，期间按短间隔重查）后返回空；Worker 收到空结果后立即发起下一次领取。等待期间**不持有数据库连接和事务**，每次重查都是独立的短事务；请求处理使用虚拟线程（见 13.1）。
5. 已请求取消的任务不会被领取。

### 9.3 Worker 侧约定（写入契约文档，由 Python 仓库实现）

- 每个 Worker 进程的并发数可配置，只在有空闲槽位时领取。
- 领取后按心跳间隔续约，心跳失败（令牌不匹配或任务已终止）时立即停止执行。
- `next_action=RESUME` 但该 `thread_id` 不存在 Checkpoint 时（例如首次执行在保存前崩溃），按 `START` 处理。
- 收到停止信号（进程关闭）时不再领取新任务，正在执行的任务尽量在租约内完成；来不及完成的由租约过期机制回收。

### 9.4 Java 侧巡检

使用 Spring 进程内定时任务，多实例同时运行，依靠条件更新保证重复执行无副作用：

| 巡检 | 默认间隔 | 动作 |
|---|---|---|
| 租约过期回收 | 15 秒 | 见第十一章 |
| 审批过期 | 60 秒 | `PENDING` 且已过期的审批置为 `EXPIRED`，任务置为 `CANCELLED` |
| 任务总时限 | 60 秒 | 超过 `deadline_at` 的非终态任务转为 `FAILED`（见 8.3） |
| 无匹配 Worker | 5 分钟 | 可领取但长时间没有 Worker 支持其 `workflow_version` 的任务，记录告警日志；到达 `deadline_at` 后按总时限处理 |
| 孤儿文件清理 | 每天 | 清理上传到 OSS 但未被任何记录引用、且超过保留期的文件（启用 OSS 后） |
| 外部操作核对 | 30 秒 | 见第十二章 |
| 数据清理 | 每天 | 见 8.8 |

### 9.5 规模演进

拉取模式在以下情况需要重新评估：任务吞吐达到每秒数百以上，或 Worker 数量超过几十个、轮询对数据库产生明显压力，或出现无法直接访问 Java 内部接口的 Worker。

演进方式：增加一条"有新任务"的提醒消息，Worker 收到后立即调用领取接口。**领取接口仍是唯一执行入口**，可靠性设计不变。

### 9.6 事件通知扩展（V1.0.0 不实现）

当出现真实的消费方时（例如向其他系统发布"商品已上架""文章已发布""任务已完成"，或订阅电商系统的商品变更事件），按以下设计引入：

1. 复用现有 RocketMQ 集群，版本与引入方式见 3.3；使用工作台独立的 Topic 和 Consumer Group。
2. 只由 Java 收发消息，Python 不接入 RocketMQ。
3. 采用 MySQL Outbox + 普通消息，不叠加事务消息。业务状态变更与 Outbox 记录在同一个本地事务内提交。
4. `ai_outbox` 字段沿用原始需求：`event_id, aggregate_id, event_type, payload, status, retry_count, next_retry_at, last_error, created_at, sent_at`，增加 `topic`、`tag`、`trace_id`；状态为 `PENDING` / `SENT` / `FAILED`。
5. 投递器多实例下使用 `SELECT ... FOR UPDATE SKIP LOCKED` 分批抢占，失败按指数退避重试，超过上限标记 `FAILED`。
6. 统一消息信封：`event_id`、`event_type`、`schema_version`、`aggregate_id`、`trace_id`、`occurred_at`、`payload`。
7. 消费方必须幂等，届时增加消费幂等表与 `common-messaging` 模块。

---

## 十、Java ↔ Python 内部契约

契约文档放在本仓库 `docs/internal-api-contract.md`，带版本号，作为两个仓库的唯一约定来源。

### 10.1 Java 提供、Python 调用

| 接口 | 说明 |
|---|---|
| 领取任务 | 长轮询，见 9.2；返回 `run_id`、`lease_token`、租约到期时间、`next_action`、任务输入引用 |
| 心跳 | 续约；响应中携带是否已请求取消 |
| 上报进度 | 进度、当前步骤 |
| 上报成功 | 结果引用、Token 用量、执行元数据 |
| 上报失败 | 错误码、是否可重试、是否可从 Checkpoint 恢复（决定重试时的 `next_action`） |
| 进入等待审批 | 审批类型、待审内容引用与摘要；Checkpoint 必须已保存 |
| 执行正式操作 | 例如商品上架、文章发布；Java 校验令牌、权限、审批与内容摘要、幂等后调用电商系统 |

除领取任务外，所有回调必须携带 `task_id`、`run_id`、`lease_token`。幂等规则：

- 令牌不匹配或任务已被其他执行尝试接管：返回明确的"租约失效"错误码，Worker 必须停止执行。
- 同一 `run_id` 重复上报成功、失败或进入等待审批：任务已处于对应状态时直接返回首次处理结果，不重复转换。
- 执行正式操作的幂等由 `ai_operation_record` 的 `(operation_type, idempotency_key)` 保证。

"执行正式操作"接口的返回结果：

| 返回 | 含义 | Worker 的处理 |
|---|---|---|
| `SUCCEEDED` | 成功（可能是首次执行，也可能是之前已成功的记录） | 继续工作流 |
| `BUSINESS_REJECTED` | 电商系统业务拒绝 | 按不可重试失败上报，或由工作流自行处理 |
| `IN_PROGRESS` | 同一操作在途或结果待核对 | 按可重试失败上报（错误码 `OPERATION_IN_PROGRESS`），任务进入 `RETRY_WAIT`，退避后从 Checkpoint 恢复再次请求 |
| `UNAVAILABLE` | 确定未执行（服务不可用） | 按可重试失败上报 |
| `CANCEL_REQUESTED` | 任务已请求取消，拒绝发起新操作 | 停止执行 |
| `LEASE_INVALID` | 租约令牌失效 | 停止执行 |

### 10.2 Python 提供、Java 调用

| 接口 | 说明 |
|---|---|
| 流式对话 | SSE |
| 取消通知 | 可选，用于加速停止正在执行的任务；不调用时 Worker 也会在下一次心跳获知。尽力而为，最终以 Java 状态为准 |
| 查询状态 | 排障用 |

审批恢复不需要单独接口：审批通过后任务回到 `QUEUED` 且 `next_action=RESUME`，由 Worker 领取后按 `thread_id` 恢复。

### 10.3 标识规范

| 标识 | 含义 | 生成方 |
|---|---|---|
| `task_id` | 业务任务 | Java |
| `thread_id` | LangGraph 工作流线程 | Java 创建任务时生成，Python 使用 |
| `run_id` | 一次执行尝试 | Java 在领取时生成 |
| `lease_token` | 租约令牌 | Java 在领取时生成 |
| `worker_id` | Worker 进程标识，写入 `lease_owner` | Python 启动时生成 |
| `event_id` | 消息事件（9.6 事件通知扩展启用后使用） | Java（Outbox） |
| `operation_id` | 外部副作用操作 | Java |
| `request_id` | HTTP 请求 | 调用方 |
| `trace_id` | 调用链路 | 入口生成，全链路传递 |

这些标识不得混用。

### 10.4 版本演进与兼容

**工作流版本（防止旧 Checkpoint 无法恢复）：**

一个任务可能在等待确认状态停留 24 小时，期间 Python 可能已发布新版本、工作流结构已改变。

1. 任务创建时写入 `workflow_version`（由 Java 按任务类型的当前版本配置确定）。
2. Worker 领取时声明自己支持的版本列表，Java 只分配匹配的任务。
3. Python 发布不兼容的新工作流版本时，保留能处理旧版本的 Worker，直到旧版本任务全部结束；或在契约中声明旧版本可迁移到新版本。
4. 没有任何 Worker 支持的旧版本任务，到达 `deadline_at` 后转为 `FAILED`，错误码 `WORKFLOW_VERSION_UNSUPPORTED`，原因明确展示给用户。

**接口契约版本（滚动发布）：**

1. 内部 API 路径或请求头带契约版本号；Java 至少同时兼容当前版本和上一个版本，Python 同理。
2. 新增字段只能是可选字段；删除或改变字段语义必须升级版本号。
3. 发布顺序：先发布兼容新旧两个版本的一方，再发布另一方。

**数据库迁移：**

按"先加后删"编写迁移脚本，保证新旧版本的 Java 可以同时运行：先新增列和表（可空或带默认值），代码切换完成后，再在下一个版本中删除旧列。多实例同时启动时由 Flyway 的锁保证迁移只执行一次。

---

## 十一、任务可靠性

1. **领取并发保护**：领取使用 `FOR UPDATE SKIP LOCKED` 加条件更新，同一任务只有一个 Worker 能领到；多个 Java 实例同时处理领取请求也不会重复派发。
2. **租约与心跳**：默认租约 60 秒，心跳间隔 20 秒（可配置）。
3. **租约过期回收**：巡检扫描 `RUNNING` 且 `lease_expires_at` 已过期的任务：已请求取消的，满足 8.4"取消生效条件"时转为 `CANCELLED`，存在在途操作时转为 `RETRY_WAIT` 等待核对；否则按剩余次数转为 `RETRY_WAIT`（`available_at` 按退避设置，`next_action` 为 `RESUME`，由 Worker 从最近的 Checkpoint 继续）或 `FAILED`。同时将对应 `ai_run` 标记为超时。多实例下依赖条件更新，重复执行无副作用。
4. **旧 Worker 防护**：租约过期不代表旧 Worker 已停止。旧 Worker 的回调因 `lease_token` 不匹配被拒绝；旧 Worker 发起正式操作时同样校验令牌，并由幂等键兜底。
5. **失败分类**：可重试（超时、服务不可用、限流）与不可重试（参数错误、权限不足、业务拒绝）。
6. **有限重试**：指数退避，次数上限由 `max_attempts` 控制。
7. **人工审批**：Python 保存 Checkpoint → 上报进入等待审批 → Java 置 `WAITING_APPROVAL` 并释放租约 → Worker 结束本次执行，槽位释放 → 用户审批 → Java 校验身份、归属、权限与过期时间 → 任务回到 `QUEUED` 且 `next_action=RESUME` → Worker 领取后按 `thread_id` 恢复。Worker 不允许占着槽位等待用户操作。
8. **Worker 崩溃**：不需要额外处理，心跳停止后由租约过期回收，任务重新进入可领取状态。
9. **Java 实例故障**：任务状态全部在 MySQL 中，任一 Java 实例都能处理领取和回调；Worker 调用失败时按退避重试，租约内恢复则无影响。
10. **Seata 边界**：不把 Agent 长流程放入分布式事务。

---

## 十二、正式业务操作保护

请求一旦发给电商系统就无法撤回。因此本章的原则是：设定明确的不可回头点；已发出的请求必须追到确定结果；重复发送由多层幂等兜底。

所有正式副作用通过 `operation` 模块统一执行。由于调用方是 Java，Python Worker 暂停、崩溃或租约过期都不会中断已经发出的调用。

### 12.1 执行流程

1. 校验任务归属和用户业务权限（执行前重新校验，不复用创建时的结论）。
2. 校验该操作的人工确认状态为 `APPROVED` 且内容摘要一致（V1.0.0 所有正式操作都需要确认，见 8.6）。
3. 按 `(operation_type, idempotency_key)` 查询已有操作记录，按 12.2 处理。
4. 没有记录时，**在同一个本地事务内**：校验租约令牌有效、任务未请求取消；非幂等操作校验 `reconcile_key` 已确定（例如商品编号，且已包含在审批内容摘要中）；需要内容级去重的操作类型按 12.7 检查；然后插入 `PENDING` 记录占位。唯一约束保证并发请求只有一个能占位成功。**插入成功即为不可回头点**，此后的取消请求不能阻止本次调用。
5. 提交事务后调用电商系统（Dubbo `retries=0`），按第六章的四种结果分类更新记录：成功 → `SUCCEEDED`；业务拒绝 → `FAILED/BUSINESS_REJECTED`；确定未执行 → `FAILED/NOT_EXECUTED`；超时等不确定 → `UNKNOWN`。
6. 成功时将任务的 `has_external_effect` 置为 1。

### 12.2 已有记录的处理

| 已有记录 | 处理 |
|---|---|
| `SUCCEEDED` | 直接返回已保存的结果，不再发送 |
| `PENDING` | 返回 `IN_PROGRESS` |
| `UNKNOWN` | 返回 `IN_PROGRESS`，等待核对 |
| `FAILED/NOT_EXECUTED` | 重新校验令牌与取消状态后，用同一个幂等键、同一个 `reconcile_key` 再次发送（`send_count` 加 1，有上限） |
| `FAILED/BUSINESS_REJECTED` | 直接返回失败，不自动重发 |

### 12.3 结果核对巡检

1. `PENDING` 超过"调用超时时间 + 余量"仍未更新的记录，视为 `UNKNOWN`。这覆盖了 Java 发出请求后、记录结果前进程崩溃的情况。
2. `UNKNOWN` 记录按 `next_reconcile_at` 处理，规则因操作类型而异，见 12.6。退避间隔递增，超过次数上限转人工处理。
3. 无法自动确认结果的非幂等操作，只能转人工处理，**不得自动重发**。人工处理时，用户在电商系统核实后回到工作台标记成功（填写对象 ID）或未执行。
4. 记录有确定结果后，检查所属任务：已请求取消且不再有在途操作的，完成取消（见 8.4）。

### 12.4 防重复发送的四层保护

| 层 | 机制 | 防住的情况 |
|---|---|---|
| 框架层 | 有副作用的 Dubbo 接口 `retries=0` | 框架自动重试 |
| Java 层 | 先占位后调用，`(operation_type, idempotency_key)` 唯一约束 | 并发请求、Worker 接管后重复执行 |
| 幂等键设计 | 任务标识 + 业务步骤，跨执行尝试不变 | 重试或恢复后换新键 |
| 结果核对层 | 电商系统不做重复判定；天然幂等操作允许重发，非幂等操作用业务唯一值（如商品编号）查询核对，见 12.6 | Java 发送后、记录前崩溃；超时后的重发 |

前三层覆盖工作台内部产生的全部重复。"请求已到达电商系统、Java 却不知道结果"的窗口由结果核对层处理；某类非幂等操作没有可用的核对方式时，结果不确定只能转人工，因此每类操作接入前都要先确定其分类与核对方式。

### 12.5 取消与补偿

- 已请求取消的任务，不能再发起新的正式操作（12.1 第 4 步拦截）。
- 取消前已成功的操作不会被撤回；任务标记 `has_external_effect`，前端展示对应操作记录。
- V1.0.0 不做自动补偿。反向操作因业务而异且自身也可能失败，由用户作为新的正式操作发起，同样经过审批、幂等和操作记录。各类操作的补偿方式见 B-05。

### 12.6 操作分类与结果核对

电商系统不做重复判定，因此每类正式操作接入前必须确定分类和核对方式，登记在操作类型配置中：

| 分类 | 例子 | 结果不确定（`UNKNOWN`）时的处理 |
|---|---|---|
| 天然幂等（`NATURAL`） | 上架或下架已有商品、把价格设为某个值、覆盖更新文案 | 允许用相同参数自动重发，以重发的结果为准 |
| 非幂等，有核对键（`RECONCILABLE`） | 创建商品（核对键：商品编号） | 按核对键查询，见下文 |
| 非幂等，重复可接受（`DUPLICATE_TOLERANT`） | 提交素材（电商系统有人工审核兜底） | 自动重发一次，见下文 |
| 非幂等，无核对键（`MANUAL`） | 其他无可查询唯一值的创建类操作、累加类操作 | 转人工处理，不得自动重发 |

能改成天然幂等的操作优先改造，例如"库存加 10"改为"库存设为 N"。

**创建商品的核对规则（核对键为商品编号）：**

1. 商品编号在首次发送前确定，写入 `reconcile_key`，并包含在审批内容摘要中；重试、恢复和重发都使用同一个编号，不得重新生成。
2. 结果不确定时，按商品编号查询电商系统：
   - 查到商品，且关键特征（名称、价格等，具体字段在业务接入时确定）与本次请求一致：判定成功，记录 `target_id`。
   - 查到商品，但关键特征不一致：说明编号已被其他商品占用，转人工处理。
   - 查不到：在查询数据实时可见的前提下，判定未执行（`FAILED/NOT_EXECUTED`），允许重发；数据可能延迟可见时，等待一个延迟窗口后再查，仍查不到才判定未执行。
3. 电商系统对商品编号有全局唯一约束。重发时若返回"编号已存在"，不按业务失败处理，而是转入第 2 步核对。
4. 首次发送前，也先按编号查询一次：编号已被占用时直接返回业务失败，提示用户更换编号，避免与已有商品冲突。

商品编号全局唯一、可按编号查询已确认；按编号查询的数据是否实时可见待确认（E-03），确认前"查不到"一律等待延迟窗口后再判定。

**提交素材的处理规则：**

电商系统对素材没有任何唯一限制，但素材提交后需要电商系统人工审核才会生效。重复提交的后果只是审核队列多一条，可由审核人员驳回，因此素材采用"宁可重复"的策略：

1. 发送前由用户人工确认（8.6），并经过工作台内容级去重（12.7）。
2. 素材类调用使用较长的超时时间，不做框架自动重试；Java 优雅关闭时等待在途调用完成。
3. 结果不确定时，自动重发一次（`send_count` 上限为 2）；重发仍不确定则转人工处理。
4. 极端情况下产生的重复素材，由电商系统审核时驳回。
5. **提交成功即任务成功**。操作记录 `SUCCEEDED` 表示"已提交审核"，界面显示"已提交，待审核"，不显示"已发布"。
6. 审核结果不纳入任务状态机。用户查看时，按 `target_id`（素材 ID）实时查询电商系统的审核状态并展示，工作台不保存审核状态。将来如需"审核通过后自动执行下一步"，再单独设计。

### 12.7 内容级去重

用于防住用户重复点击、AI 在不同任务中生成相同内容等"同一内容被重复提交"的情况，与幂等键（防同一操作重复执行）互补。

1. 对启用去重的操作类型（V1.0.0：提交素材），按"归属主体 + 操作类型 + 内容摘要"去重。归属主体在电商系统身份模型确认前使用 `user_id`（见 E-05）。内容摘要覆盖文案、图片文件哈希和关键属性，具体字段在业务接入时确定。
2. 只有 `PENDING`、`UNKNOWN`、`SUCCEEDED` 状态的操作记录参与去重，失败的记录不阻止再次提交。
3. 实现：`ai_operation_record` 增加生成列 `dedupe_key`（上述状态时为去重值，否则为 NULL），并建唯一索引，由数据库保证并发下也不会重复。
4. 生成确认请求时先预检：发现重复则在确认界面展示已有的操作记录，默认不允许确认。用户明确选择"仍要提交"时，审批记录标记允许重复，对应操作记录不参与去重（`dedupe_key` 为 NULL），并留痕。
5. 发送时由唯一索引做最终保证。预检之后才出现的并发重复，返回业务失败（错误码 `DUPLICATE_CONTENT`），不发送。

### 12.8 人工处理入口

本文多处"转人工"统一通过以下管理接口处理（V1.0.0 提供接口，管理界面由前端仓库按需实现）：

| 入口 | 能力 |
|---|---|
| 待确认操作 | 列出 `UNKNOWN` 超过核对上限、以及 `MANUAL` 类结果不确定的操作记录；人工标记"成功"（必须填写电商系统对象 ID）或"未执行" |
| 卡住的任务 | 列出长时间处于非终态的任务（阈值可配置）；查看任务、执行尝试和操作记录；强制取消（仍受 8.4 取消生效条件约束） |
| 失败任务 | 列出重试耗尽或超过总时限的失败任务；人工重新提交为新任务（新的 `task_id`，引用原任务），不复活原任务 |

要求：

- 人工处理权限独立于普通使用权限，具体角色待电商系统权限模型确认（E-05）。
- 每次人工处理写入操作审计：处理人、时间、处理前后状态、填写的对象 ID 和处理说明。
- 人工标记"未执行"后，不自动重发；是否重新发起由用户决定，并重新经过确认流程。
- 人工处理同样使用条件更新，防止与核对巡检同时修改同一记录。

---

## 十三、健壮性设计

### 13.1 资源隔离与上限

1. **虚拟线程**：Service 开启 Java 21 虚拟线程（`spring.threads.virtual.enabled=true`），避免长轮询领取和流式对话占满平台线程。构建时验证所用 MySQL 驱动、Druid、Dubbo 在虚拟线程下没有严重的线程固定（pinning）问题，结果记入 `architecture-decisions.md`。
2. **数据库连接不随等待占用**：长轮询、流式转发、调用电商系统和 Python 期间都不持有数据库连接或事务；事务只包裹数据库读写本身。
3. **并发与数量上限**（默认值可配置）：

| 上限 | 默认值 | 超出时 |
|---|---|---|
| 每用户同时打开的流式对话 | 3 | 拒绝新连接，错误码 `TOO_MANY_STREAMS` |
| 单实例流式对话总数 | 500 | 拒绝新连接 |
| 每用户排队与运行中的任务数 | 20 | 拒绝创建，错误码 `TOO_MANY_TASKS` |
| 单实例同时调用电商系统的并发数 | 50 | 快速失败，按"确定未执行"处理 |
| 请求体大小 | 1 MB | 拒绝 |
| 单条消息长度 | 待业务确定 | 拒绝 |
| 回调载荷大小 | 256 KB | 拒绝；更大的结果先写 OSS，回调只传引用 |

4. **电商系统故障隔离**：正式操作使用独立的并发上限（上表）。最近一段时间连续失败达到阈值时进入"快速失败"状态，一段时间内新的正式操作直接按"确定未执行"返回，不实际发起调用，过后放行少量请求试探恢复。这是轻量的进程内实现，不引入 Sentinel。核对巡检在电商系统故障期间同样退避，不持续施压。

### 13.2 时间与并发

1. **统一使用数据库时间**：`lease_expires_at`、`available_at`、`deadline_at`、`expires_at` 等一律由 MySQL `NOW(3)` 计算和比较，不使用各 Java 实例的本地时钟。Python 只使用返回的租约时长，不自行计算到期时刻。
2. **事务隔离级别**：Service 统一使用 `READ COMMITTED`，避免领取时范围查询加 `SKIP LOCKED` 产生间隙锁、锁等待和死锁。
3. **冲突重试**：数据库死锁、锁等待超时、乐观锁冲突，在服务内部自动重试，最多 3 次并加随机抖动；仍失败则向调用方返回可重试错误。
4. **用户侧操作的幂等**：创建任务通过 `idempotency_key` 去重；确认、拒绝、取消通过条件更新保证重复点击只生效一次，重复请求返回当前状态。
5. **退避与抖动**：Worker 的领取、心跳、回调重试，以及 Java 的巡检退避，统一采用指数退避加随机抖动，避免故障恢复瞬间所有请求同时涌入。

### 13.3 超时预算

外层超时必须大于内层，避免外层已放弃、内层仍在执行，凭空制造结果不确定。默认值如下（可配置，但必须保持大小关系）：

| 层 | 默认超时 | 说明 |
|---|---|---|
| Python 调用"执行正式操作"的 HTTP 超时 | 40 秒 | 最外层 |
| Java 执行正式操作的总时限 | 30 秒 | 含校验、占位、调用、落库 |
| 调用电商系统（创建类、提交素材） | 20 秒 | 有副作用，放宽超时以降低结果不确定 |
| 调用电商系统（查询、天然幂等操作） | 3 秒 | 与参考项目默认值一致 |
| Gateway 普通路由 | 30 秒 | 流式路由单独配置 |
| Gateway 流式路由空闲超时 | 120 秒 | 两次数据之间的最长间隔 |
| 领取长轮询 | 20 秒 | Python 侧 HTTP 超时应大于此值（建议 30 秒） |

Java 执行正式操作超过总时限时，记录为 `UNKNOWN`（已发出）或 `FAILED/NOT_EXECUTED`（未发出），不会把未完成的调用当作失败。

### 13.4 依赖故障时的行为

| 故障 | 行为 |
|---|---|
| MySQL 不可用 | 接口快速返回 503（错误码 `SERVICE_UNAVAILABLE`）；巡检本轮跳过；健康检查报告异常 |
| Java 全部不可用 | Worker 的心跳和回调在租约期内带退避重试；距上次成功心跳超过租约时长仍无法联系 Java 时，Worker 主动停止当前任务，不再调用模型。正式操作必须经过 Java，因此不会产生副作用 |
| 认证依赖（如 Redis）不可用 | Gateway 拒绝需要登录的请求并返回明确错误，不放行；内部 API 使用签名认证，不受影响 |
| 电商系统不可用 | 见 13.1 第 4 条 |
| OSS 不可用 | 需要写入 OSS 的结果上报失败，按可重试失败处理；必须先写 OSS 成功再上报任务成功 |
| Python Agent API 不可用 | 流式对话返回明确错误；后台任务不受影响（留在任务表中等待领取） |

**反复导致 Worker 崩溃的任务**：领取时 `attempt_count` 即加 1，Worker 崩溃后由租约过期回收，重试次数耗尽后自动转为 `FAILED`，不会无限循环。Worker 应在本地日志中记录正在执行的 `task_id` 和 `run_id`，便于排查崩溃原因。

**OSS 孤儿文件**：上传成功但未被任何记录引用的文件，由每日巡检在保留期后清理（9.4）。

### 13.5 运行指标

不部署 Prometheus 也通过 Actuator 的 `metrics` 端点暴露以下指标（Micrometer），出现异常时能第一时间发现；以后接入 Prometheus 只需开启端点：

| 指标 | 用途 |
|---|---|
| 各状态任务数；可领取任务中最早一条的等待时长 | 判断 Worker 是否不足或停摆 |
| 租约过期回收次数 | 判断 Worker 是否频繁崩溃 |
| `UNKNOWN` 操作数；待人工处理的操作数与任务数 | 判断是否需要人工介入 |
| 调用电商系统的次数、失败率、耗时分布；快速失败状态 | 判断电商系统健康度 |
| 领取请求数与空返回比例 | 调整轮询参数 |
| 流式对话当前连接数 | 判断是否接近上限 |

---

## 十四、日志与排障

V1.0.0 必须实现：

- 统一异常处理与错误码。
- 结构化日志（JSON 输出可按环境开启）。
- MDC 与 Trace ID：Gateway 生成或透传，Service 写入 MDC，传递给 Dubbo 调用和内部 HTTP 调用；任务创建时记录 `trace_id`，领取时返回给 Worker，使异步执行与发起请求能够关联。
- 敏感数据脱敏：密码、Token、API Key、手机号等。不记录完整模型上下文，只记录长度、摘要或引用。
- 任务状态变更、执行耗时日志。
- Dubbo 调用异常与超时日志。
- 任务领取、租约续约失败、租约过期回收、审批过期和外部操作核对日志。
- Actuator 健康检查：`health`（含数据库、Nacos，按需包含 Redis）、`info`；`prometheus` 端点可选。
- 优雅关闭：`server.shutdown=graceful`；关闭时停止巡检任务，进行中的长轮询领取请求立即返回空结果，等待其他进行中的请求在超时内完成。

后续可接入 OpenTelemetry、Elasticsearch、Kibana、Logstash，V1.0.0 不部署。

---

## 十五、暂缓的能力

1. Sentinel 限流、熔断和动态规则管理。
2. Agent 自动评测平台、评测数据集、评分与版本对比。
3. Token 成本分析平台。
4. 租户级全局限流与配额中心。
5. XXL-Job 独立调度。
6. dynamic-tp 动态线程池。
7. Elasticsearch、Kibana、Logstash 日志平台。
8. Canal 数据变更订阅。
9. Sharding-JDBC 分库分表。
10. Kubernetes 与自动扩缩容。
11. 复杂多 Agent 协作平台。
12. SSE 断线续传。
13. RocketMQ 事件通知与 Outbox 投递器（设计见 9.6）。

暂缓功能只保留必要的接口边界和扩展说明，不创建空模块、空接口，不将未实现的功能描述为已完成。

---

## 十六、分阶段开发计划

不一次性生成全部代码。每个阶段完成后编译、测试、报告真实结果，确认后再进入下一阶段。

### 阶段一：工程骨架

内容：Maven 多模块、Gateway、Workbench Service、公共模块、统一异常与参数校验、认证适配接口、日志与 Trace ID、Actuator（含 13.5 指标框架）、OpenAPI、Dubbo 基础集成、虚拟线程配置、请求体大小限制、超时预算配置项（13.3）、README 与架构文档、`architecture-decisions.md`（记录版本与验证结果）。

验收：
- 依赖解析正常，`mvn clean verify` 通过。
- Gateway 与 Service 能在本地启动，健康检查正常。
- Gateway 能把请求转发到 Service，Trace ID 贯通。
- Dubbo 在本地 Nacos 上完成注册与启动。**不声称已与电商系统互通**，互通在阶段四验证。
- 虚拟线程已生效；线程固定问题的检查结果记入 `architecture-decisions.md`（未检查的如实标注）。

### 阶段二：基础设施

内容：MySQL 连接（`READ COMMITTED` 隔离级别）、Flyway 迁移、核心表、内部 API 签名认证（7.4）与契约版本号（10.4）、内部 API 契约文档 `internal-api-contract.md` 与派发设计文档 `task-dispatch-design.md`（供 Python 仓库对接）。

验收：数据库能通过迁移脚本从空库初始化；内部 API 对缺失签名、签名错误、时间戳过期、随机数重放的请求均能拒绝。

### 阶段三：任务可靠性

内容：任务创建/查询/取消、状态机、领取接口（含长轮询与工作流版本匹配）、心跳与回调、失败分类与有限重试、任务总时限、Java 侧巡检（9.4）、人工确认、操作记录与幂等、正式操作保护框架、人工处理接口（12.8）、并发与数量上限、电商系统快速失败（13.1）、冲突自动重试（13.2）。

验收：以下场景均有对应处理和测试——多个 Worker 并发领取不重复、Worker 崩溃后租约过期回收并重新领取、旧 Worker 迟到回调被拒绝、同一回调重复上报、审批等待与恢复、审批过期、运行中取消、外部调用超时进入 `UNKNOWN`、操作在途时取消（取消延后生效）、新 Worker 接管后重复请求同一操作（不重复发送）、`PENDING` 超时转 `UNKNOWN` 后核对、四类操作在结果不确定时分别按 12.6 处理、内容级去重在并发下不重复、任务超过总时限、无匹配工作流版本的任务不被领取、长轮询期间不占用数据库连接、超过数量上限被拒绝、电商系统连续失败后进入快速失败并恢复、人工标记操作结果（电商系统用模拟实现）。

### 阶段四：业务集成框架

内容：
- Python Agent API 客户端：流式对话转发、取消通知（10.2）。
- "执行正式操作"内部接口与电商系统 Dubbo 适配器：电商系统信息到位后接入；未到位时只保留 Adapter 契约和待补充清单。
- 流式对话转发与消息落库。
- OSS 接入（有图片、文件业务时）。

具体业务工作流（商品创建与上架、营销文章生成与发布等）不在本阶段一次性实现，**按后续需求逐个接入**，每个业务单独评审接口契约、审批规则和幂等键设计。

### 阶段五：部署与验证

内容：Dockerfile、本地开发配置、`.env.example`、单元与集成测试、故障恢复测试、启动/部署/排障文档。

验证场景：数据库故障、并发领取、重复回调、模型超时（通过模拟 Python 回调）、第三方接口失败、Worker 崩溃、Java 实例重启、服务优雅关闭，以及 13.4 表中各依赖故障的行为、新旧版本 Java 同时运行（滚动发布）。依赖真实中间件的测试需要本地或测试环境可用，无法执行的场景如实标注。

---

## 十七、测试策略

- 单元测试：状态机转换、幂等判断、签名校验、重试退避计算、快速失败状态切换、超时预算大小关系校验（启动时校验配置，不满足则拒绝启动）。
- 集成测试：Mapper 与迁移脚本、`SKIP LOCKED` 并发领取、条件更新并发、租约过期回收。需要 MySQL 时优先使用 Testcontainers（要求本地 Docker），不可用时使用指定的测试库，并在报告中说明。
- 外部系统（电商系统、Python、模型）在测试中用模拟实现替代，不访问真实生产接口。

---

## 十八、最终交付要求

1. 实际创建工程文件，不只输出架构说明。
2. Maven 多模块可编译。
3. 关键模块有真实代码，不以 TODO 或空方法冒充完成。
4. 数据库表有真实迁移脚本。
5. 任务状态机、领取派发、幂等、租约、审批和权限机制有实现和测试。
6. 不编造未知的外部业务接口。
7. 记录实际使用的依赖版本和兼容性验证结果。
8. 提供启动、测试和部署说明。
9. 明确列出已完成、未完成、外部依赖和待补充信息。
10. 未实际测试的功能不声称已通过验证。
11. 先执行阶段一，报告真实的编译和测试结果，确认后再继续。

---

## 十九、待确认信息

### 19.1 电商系统（阶段四前必须提供）

| 编号 | 事项 |
|---|---|
| E-01 | Dubbo 版本、注册中心类型与地址、命名空间与分组、协议、序列化方式 |
| E-02 | 商品创建、编辑、上架、查询，文章发布等接口的 API jar 或接口文档 |
| E-03 | **已确认**：电商系统不做重复判定，不支持幂等键。创建商品需要填写商品编号，作为核对键（12.6）；商品编号**全局唯一**；**有按商品编号查询商品的接口**。素材类操作在电商系统侧没有任何唯一限制，提交后需电商系统人工审核；**能按素材 ID 查询审核状态**。**仍需确认**：① 按编号查询读的是主库还是有延迟的数据源（如搜索引擎），延迟大约多久；② 商品编号重复时，创建接口返回的错误码或异常类型；③ 提交素材接口是否同步返回素材 ID |
| E-04 | 认证方式（Token / Session / Sa-Token / JWT），登录态存储位置，工作台 Gateway 如何校验 |
| E-05 | 用户、商家、租户标识的含义与获取方式；权限模型与资源归属规则 |
| E-06 | Token 失效与续期机制；跨域与 Cookie 策略 |

### 19.2 基础设施（阶段二前提供）

| 编号 | 事项 |
|---|---|
| I-01 | 工作台使用的 MySQL 实例与库名 |
| I-02 | Nacos 地址与工作台使用的命名空间；是否使用 Nacos 配置中心 |
| I-03 | RocketMQ NameServer 地址、是否开启 ACL、Topic 由谁创建（启用 9.6 事件通知时才需要，V1.0.0 不需要） |
| I-04 | 是否需要 Redis；如需要，实例地址与是否启用 SSL |
| I-05 | OSS Bucket 与访问方式（阶段四按需） |

### 19.3 Python 仓库相关（影响跨仓库约定）

| 编号 | 事项 |
|---|---|
| P-01 | LangGraph Checkpoint 存储：LangGraph 官方支持 Postgres、SQLite，MySQL 只有社区实现。需在 Postgres、社区 MySQL 实现、Redis 中选定 |
| P-02 | Worker 部署规模：进程数与每进程并发数、各任务类型的模型调用限额，用于确定轮询间隔、租约时长和 `max_attempts` 默认值 |
| P-03 | Python 运行版本：建议 3.12（本机为 3.15，部分依赖可能尚无预编译包） |

已决定（R1-15）：任务派发采用拉取模式，Python 不接入 RocketMQ。

### 19.4 业务规则（对应业务接入时确认）

| 编号 | 事项 |
|---|---|
| B-01 | **已确认**：V1.0.0 由任务发起人本人确认；需要第二人复核的操作类型后续单独配置 |
| B-02 | 确认默认过期时间：暂定 24 小时，待确认 |
| B-03 | 会话与消息的保留期限 |
| B-04 | 各业务工作流的输入、输出、审批节点与幂等键设计 |
| B-05 | 各类正式操作的补偿方式（例如上架对应下架、发布对应撤回），以及补偿是否需要审批 |
| B-06 | 各类正式操作的分类（`NATURAL` / `RECONCILABLE` / `DUPLICATE_TOLERANT` / `MANUAL`），以及核对或去重时比对哪些关键特征。已定：创建商品为 `RECONCILABLE`，提交素材为 `DUPLICATE_TOLERANT` |
| B-07 | 商品编号由谁确定：用户填写、AI 按商家编码规则生成，还是工作台按规则生成；生成后是否允许用户在审批前修改 |
| B-08 | **已确认**：素材采用"宁可重复"策略，结果不确定时自动重发一次；工作台做内容级去重；提交成功即任务成功，审核状态实时查询（12.6、12.7）。待定：内容摘要具体覆盖哪些字段 |
