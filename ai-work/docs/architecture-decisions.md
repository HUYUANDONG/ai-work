# 架构决策与版本记录

未实际构建或未实际运行验证的条目必须标注。本文件随阶段推进更新。

R2 产品范围见 [requirements-v1.0.0.md](requirements-v1.0.0.md)。ADR-008 起为业务转向后的决策。

## 已选定的依赖版本（写入 POM，构建结果见阶段一编译记录）

| 组件 | 版本 | 来源 | 构建验证 |
|---|---|---|---|
| JDK | 21 | 需求 / 参考项目 | 本机 Maven 使用 JDK 21，`mvn clean verify` 通过 |
| Spring Boot | 3.2.2 | 参考项目 parent | `mvn clean verify` 通过 |
| Spring Cloud | 2023.0.0 | 参考项目 | `mvn clean verify` 通过 |
| Spring Cloud Alibaba | 2023.0.1.2 | 参考项目（修正需求原稿 2022.0.0.0） | `mvn clean verify` 通过 |
| Dubbo | 3.2.10 | 参考项目 | `mvn clean verify` 通过 |
| Lombok | 1.18.30 | 参考项目 | `mvn clean verify` 通过 |
| Hutool | 5.8.22 | 参考项目 | `mvn clean verify` 通过 |
| springdoc-openapi | 2.3.0 | 与 Spring Boot 3.2 配套，非参考项目 | `mvn clean verify` 通过 |

被 Spring Boot / Cloud / SCA BOM 管理的依赖（Gateway、LoadBalancer、Nacos、Actuator、Logback、Jackson）不在 POM 中手写版本。

## 阶段一刻意未引入

Redis、Redisson、Sa-Token、RocketMQ、OSS、Fastjson2、Guava、MapStruct、Sentinel。原因见需求 3.3 / 3.5。

MySQL / MyBatis-Plus 3.5.5 / Druid 1.2.20 / Flyway 已引入，由 `WB_MYSQL_ENABLED` 开关；默认 false，启动不连库。

## 决策

| 编号 | 决策 | 原因 |
|---|---|---|
| ADR-001 | 工作台 Nacos 命名空间默认 `ai_workbench`，与电商系统隔离 | 需求 4.5；电商 Dubbo namespace 待 E-01 确认后再改 `WB_DUBBO_NACOS_NAMESPACE` |
| ADR-002 | Nacos 配置中心默认关闭 | 阶段一以本地 yml 为准，避免无配置 DataId 导致启动失败 |
| ADR-003 | local 使用 `X-Wb-Dev-User` 作为开发身份 | 电商认证方式未确认（E-04），不自建登录系统 |
| ADR-004 | 身份头 HMAC 可选；local 允许无签名 | 降低本地启动门槛；dev/prod 必须配置 `WB_INTERNAL_IDENTITY_SECRET` |
| ADR-005 | Dubbo 默认 `retries=0` | 有副作用调用禁止框架自动重试 |
| ADR-006 | 虚拟线程默认开启 | 需求 13.1；线程固定（pinning）情况未做运行时检查 |
| ADR-007 | springdoc 仅挂在 Service | 需求：Gateway 不暴露 OpenAPI |
| ADR-008 | V1 不做商品写回，只做爆品筛选与质检 | 电商已有商品管理；R2 产品范围 |
| ADR-009 | 入口仅对话，不建筛选页和定时日报 | 先验证对话工作流 |
| ADR-010 | Java 只出快照特征；Python 代码算正式分；LLM 分析 Top N | 权重与 Agent 同仓迭代；LLM 不算账 |
| ADR-011 | 爆品与质检共用规则 ID，结果交叉打标 | 避免分数与风险互斥时无提示 |
| ADR-012 | 质检 V1 做 P0+P1，P2 延后 | 对应数据域已存在 |
| ADR-013 | 自营单店，身份以电商 userId 为准 | 非多商家 |
| ADR-014 | LangGraph Checkpoint 使用独立 PostgreSQL | 与 MySQL 业务库隔离；官方 Checkpointer |
| ADR-015 | 任务派发仍为 MySQL 领取，不用 RocketMQ | 长任务 + 租约 fencing；规模小 |
| ADR-016 | 按约 2000 SKU、日订单 30、查库设计，不引入数仓 | 避免分析平台级复杂度 |
| ADR-017 | 只读 Dubbo 允许有限重试；删除 V1 的 createProduct 等写接口占位 | R2 无正式副作用 |
| ADR-018 | 一套 Harness，不按业务拆 Python 进程 | 共用 Tool、评分库、Checkpoint |
| ADR-019 | V1 **不做跨任务全局指挥 Agent**；对话入口输出 `task_type`，代码路由到 Explosion / Quality | 仅两个 `task_type`；全局 LLM 派活易误路由。组合「筛爆品并看约束」由 Explosion 内会签覆盖，完整质检仍单独 `QUALITY` |
| ADR-020 | 正式口径 30 天对比前 30 天；样本门槛 + 平滑；流量权重高于销量增速；Java 只给原始计数，比率由 Python 算 | 日订单约 30，单 SKU 订单稀疏，小样本比率是噪声；口径只保留一份 |
| ADR-021 | 对话 Agent 只读本会话报告回答追问；报告带 Python 生成的 summary | 追问不应重跑任务；完成消息文案归 Python |
| ADR-022 | Explosion 交付「作战清单」：`goal_mode` + `focus_slots` + `action_bucket`，而非纯排行榜 | 真实运营要的是本周盯谁、怎么冲；与质检「问题证据」分工 |
| ADR-023 | Explosion 任务内 multi-agent：指挥 + Signal/Risk/Strategy 会签；代码分与规则命中仍权威；LLM 禁止口算分 | 有信号 ≠ 该投入；需要可冲突的意见与 veto；3 个月完善版必达 |
| ADR-024 | Explosion 内计划状态机可 `REVISE`，默认最多 2 次修订、3 轮会签，超时必须 FINISH 并降级标记 | 支持「看完 A 再调 B」又防止空转 |
| ADR-025 | 目标模式不改写 `explosion_score` 公式；只影响策略取舍与话术（可选展示 `mode_rank`） | 同一 SKU 正式分口径唯一，便于复盘 |
| ADR-026 | Chat 结构化意图；`OUT_OF_SCOPE` 硬阻断；时间窗缺省 30 天并告知，不因缺天数阻塞建任务；非法窗口须澄清/拒绝 | 降干扰与误派发；口径与小样本前提一致 |
| ADR-027 | 对话意图路由用 TypeSafe 官方 `typesafe-sdk` + Jev Choice（`jev-latest`）；代码保留默认参数与建任务门槛；关键词仅降级 | 有限选项+置信度优于关键词与开放式 LLM JSON |

ADR-005（默认 `retries=0`）对 **写操作** 仍有效。V1 无写操作；只读接口在 Adapter 上单独打开有限重试。

## 未验证项

| 项 | 状态 |
|---|---|
| 依赖能否完整解析并编译 | **已通过**（2026-10-29 `mvn clean verify`） |
| 应用在本机启动、健康检查、Gateway 转发、Trace 贯通 | **未验证**（按约定不由本次任务启动） |
| Dubbo 在本地 Nacos 注册 | **未验证** |
| 虚拟线程下 Dubbo / 未来 Druid / MySQL 驱动是否 pinning | **未验证** |
| Nacos 客户端与 Dubbo registry-nacos 传递依赖是否冲突 | 以编译为准，运行时未验证 |

## 阶段一编译记录

- 时间：2026-10-29
- 命令：`mvn clean verify`
- 结果：**通过**（exit 0），包含单元测试
- 备注：未启动 Gateway / Service，未连接 Nacos / MySQL。运行时验证项仍为未验证
