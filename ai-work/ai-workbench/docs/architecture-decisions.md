# 架构决策与版本记录

未实际构建或未实际运行验证的条目必须标注。本文件随阶段推进更新。

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
