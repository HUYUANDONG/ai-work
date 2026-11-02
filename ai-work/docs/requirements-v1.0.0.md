# AI 爆品运营工作台 V1.0.0 — 总需求（R2）

> 本文是 V1.0.0 的唯一需求权威稿。R2 将业务从「商品创建 / 上架 / 素材发布」改为「对话驱动的爆品作战清单 + 爆品质检」。
> 工程框架（Gateway、任务领取、租约、内部 API）沿用 R1；正式写回电商整章降为暂缓。
> R2-14 起将爆品从「纯筛选榜」升级为「目标驱动作战清单 + 任务内 multi-agent 会签」（约 3 个月完善第一版）。
>
> 相关文档：
> - [architecture.md](architecture.md) — 当前骨架
> - [frontend-api-contract.md](frontend-api-contract.md) — 浏览器 → Gateway 对话契约
> - [architecture-decisions.md](architecture-decisions.md) — 决策与版本
> - [dubbo-design.md](dubbo-design.md) — 只读 Dubbo 边界
> - [data-contract.md](data-contract.md) — 快照特征与报告契约
> - [agents/harness.md](agents/harness.md) — Agent Harness 与多 Agent
> - [agents/chat-agent.md](agents/chat-agent.md) — 对话入口：意图闸门与缺参引导
> - [agents/explosion-agent.md](agents/explosion-agent.md)
> - [agents/quality-agent.md](agents/quality-agent.md)

## 修订摘要（R2）

| 编号 | 修订 | 原因 |
|---|---|---|
| R2-01 | 删除 V1 商品创建、上架、改价、素材提交等正式写操作 | 电商系统已有商品管理；工作台只做分析与建议 |
| R2-02 | Python 侧为一套 Harness + 对话入口 + Explosion / Quality；**不做跨任务全局指挥**；任务类型代码路由 | 仅两个 `task_type`；全局 LLM 派活易误路由 |
| R2-03 | 入口只做对话，不做独立「跑一次」按钮和定时日报 | 先验证对话工作流 |
| R2-04 | Java 只出快照 / 特征；Python 用代码算正式分和规则命中；LLM 只分析 Top N / 会签 | 调权重与 Agent 一起改；LLM 不算账 |
| R2-05 | 爆品与质检共用快照和规则 ID，结果必须交叉打标 | 避免「爆品 92 分」与「严重缺货」互不相认 |
| R2-06 | 质检 V1 做 P0 + P1；P2（主图/详情视觉、推广 ROI）延后 | 对应数据已存在且能用代码判定 |
| R2-07 | 对象为自营单店；身份以现有 `userId` 为准 | 非多商家平台 |
| R2-08 | Checkpoint 使用独立 PostgreSQL，与工作台 MySQL 分离 | LangGraph 官方 Checkpointer；多 Worker 可恢复；Explosion `plan` 可恢复 |
| R2-09 | 原第十二章正式操作保护整体暂缓；`ai_operation_record` / `ai_task_approval` 不建 | V1 无写回 |
| R2-10 | 规模按约 2000 个在售 SKU、日订单约 30 单、统计查库设计，不引入数仓 | 数据量小，避免过度设计 |
| R2-11 | 评分与规则是 Harness 上的代码库，不是 Agent | LLM 不算正式分 |
| R2-12 | 正式口径以 30 天对比前 30 天为主；所有分项和规则设最低样本门槛并做平滑；流量信号权重高于销量增速 | 单 SKU 订单稀疏，7 天增速和小样本比率基本是噪声 |
| R2-13 | 对话 Agent 可只读本会话报告，回答追问并取上次 sku_ids；报告带 Python 生成的 `summary` | 追问是对话入口的主要价值 |
| R2-14 | 爆品交付升级为作战清单：`goal_mode`、`focus_slots`、`action_bucket`；Explosion 任务内 multi-agent 会签（指挥 + 信号/风控/策略）与可修订计划（有上限） | 贴合真实运营；有信号 ≠ 该投入；3 个月完善第一版必达 |
| R2-15 | 对话 Agent 必须结构化意图分类；`OUT_OF_SCOPE` 阻断无关请求；时间窗等缺参默认 30 天（及 GMV/槽位 5）并告知，少追问 | 避免乱建任务；降低运营使用门槛；口径与 data-contract 一致 |

R1 中仍有效的工程决策：三仓库、拉取派发、租约 fencing、HMAC 内部 API、Flyway、虚拟线程、超时预算、不引入 Sentinel / Seata / RocketMQ 派发。

---

## 一、目标与原则

面向自营店运营人员，通过对话发现潜力爆品、形成本周作战清单、诊断商品与经营问题，输出可执行建议。工作台不是第二套商品中心。

### 1.1 V1 做什么

一套 Harness，对外两个任务类型 + 对话入口（详见 [agents/harness.md](agents/harness.md)）。  
**没有跨任务全局指挥 Agent。** Explosion **任务内**有作战指挥与会签 multi-agent。

| 角色 | 做什么 | 主交付 |
|---|---|---|
| 对话 Agent | 意图闸门（含无关阻断）、缺参默认/一轮澄清、输出 `NEED_TASK`；可读本会话报告追问；自己不算分 | 短回复、拒绝并引导、追问解答或「已开始分析」 |
| Explosion | 约 2000 在售 SKU → 代码打分 + 质检标签 → Top N 上 **信号/风控/策略会签** → 按目标与槽位出作战清单 | 动作分型名单、规则分、风险、会签要点、summary |
| Quality | 对指定商品或筛选结果做 P0 + P1 检查 | 质量分、运营分、问题清单、风险等级、证据、建议 |

触发方式：仅对话。例如「按冲 GMV 筛潜力品，这周盯 5 个并标出不能硬冲的」「质检一下 SKU-123」「这批候选再做完整质检」。

### 1.2 V1 明确不做

- 商品 / SKU / 库存管理、Excel 导入、上架下架、改价、写回电商
- 新品选品（尚未上市的品类推荐）
- 独立筛选页、定时日报、预警推送
- 主图 / 详情视觉质检、广告 ROI、流量来源结构（P2）
- 人工审批、正式操作幂等、自动补货 / 自动下架

### 1.3 原则

1. 电商系统是商品、库存、价格、订单、流量、售后、成本的权威来源。工作台只存会话、任务、快照副本、评分结果和报告。
2. Java 是任务状态和已交付报告的权威方。Python 不写 `ai_task`，不直连电商库。
3. 特征由 Java 按日（或任务开始时）固化为快照。正式分和规则命中由 Python **代码**计算，放在 Harness 的 `scoring/`，权重与 Agent 同仓库迭代。
4. LLM 只做意图理解、归因、理由、风险叙述和建议。禁止用模型口算指标或作为正式分的唯一来源。评分函数不是 Agent。
5. 无某维数据时该规则跳过，报告标注「未计入」。禁止模型编造数值。
6. 所有正式副作用仍只能由 Java 执行——V1 没有这类操作。
7. 后台长任务由 Python Worker 向 Java 领取；MySQL 任务表兼队列。
8. Gateway 与 Workbench Service 独立部署；Service 为模块化单体。
9. 登录复用电商系统，记录其 `userId`。能登录即可使用全部 Agent；任务与报告按 `user_id` 隔离。
10. Python 只部署一套 Harness（API 进程 + Worker 进程共用代码）。V1 用代码按 `task_type` 路由到专家图。跨任务全局指挥仅在 `task_type` ≥3 且需跨任务动态规划时再加；**Explosion 内会签与计划修订是 V1 必达**，不算全局指挥层。

---

## 二、总体架构

三个独立仓库：前端（Vue 3，不在本仓）、Java 本仓、Python Harness 仓。

```text
Vue 3 对话界面
        |
        | HTTP / SSE
        v
ai-workbench-gateway
        |
        v
ai-workbench-service          ← Workbench（任务与数据权威）
        |
        +---- Dubbo 只读 --------> 电商系统
        +---- 内部 HTTP ---------> Python Harness API（对话 Agent）
        +<--- 内部 HTTP --------- Python Harness Worker（跑专家 Agent）
        |
        +---- MySQL（ai_workbench：会话、任务、快照、报告）
        +---- PostgreSQL（仅 Harness Checkpoint，独立实例）
        +---- Redis（仅当认证会话需要时）
```

Workbench 不是 Harness。Harness 也不代替任务表。

对话与后台任务不要混成一套状态：

1. 对话流：Gateway → Java → Harness API 上的对话 Agent（SSE）。Java 落用户消息；需要长分析时 Java 创建 `ai_task` 并先回复「已开始」。
2. 任务流：Worker 按 `task_type` **代码路由**：
   - `EXPLOSION`：拉特征 → `scoring/` → 质检标签 → Top N → **任务内会签（指挥计划 + 信号/风控/策略）** → 作战清单 upsert → complete
   - `QUALITY`：拉特征 → 规则命中 → LLM 解释问题清单 → upsert → complete
3. 任务进度 V1 以 Java 为准，前端轮询或等对话完成消息。不做任务进度 SSE。

### 2.1 对话如何落到任务

1. 用户发消息，Java 鉴权、校验会话归属、落库。
2. Java 调用 Harness 对话接口，由 **对话 Agent** 处理：结构化意图（含 `OUT_OF_SCOPE` 阻断）、缺参默认或一轮澄清、`NEED_TASK(task_type, input)`。细则见 [agents/chat-agent.md](agents/chat-agent.md)。这是入口，不是跨任务指挥层。
3. 需要专家时由 **Java** 创建一条任务（幂等键 = 用户 + 会话 + 规范化输入，**含 Chat 填入的默认**如 `time_window_days=30`），`task_type` 为 `EXPLOSION` 或 `QUALITY` 之一。立即 SSE 告知已开始，不在对话 HTTP 里跑完整分析。组合「筛选并看约束 / 本周作战」默认只跑 Explosion（会签含风控与动作分型），不连派两个专家。无关请求不得建任务。
4. Worker 领取后按 `task_type` 代码路由。完成后 Java 把报告里的 `summary`（Python 生成）写入 `ai_message`，前端按报告渲染表格（爆品表需支持 `action_bucket` / 槽位列）。
5. `META` / 纯闲聊 / `OUT_OF_SCOPE` / `CLARIFY` 不创建任务。
6. 对已有结果的追问（为什么是先修再冲、某项数值、去掉某类再看）由对话 Agent 读取本会话报告直接回答，不创建任务。需要基于上次结果再跑（如「这批再质检」或「换成保毛利重排槽位」）时，从报告取 sku_ids 或新 `goal_mode` 作为新任务输入。
7. 用户未指定时间窗时：Chat **默认近 30 天**并在回复中告知；不因缺天数阻塞。非法窗口（如只要「昨天」正式榜）须澄清或拒绝，不得建错误口径任务。

---

## 三、技术栈与版本

沿用 R1 已验证组合。被 BOM 管理的依赖不手写版本。只引入当前需要的组件。

### 3.1 V1 采用

| 组件 | 版本 | 阶段 |
|---|---|---|
| JDK | 21 | 一 |
| Spring Boot | 3.2.2 | 一 |
| Spring Cloud | 2023.0.0 | 一 |
| Spring Cloud Alibaba | 2023.0.1.2 | 一 |
| Spring Cloud Gateway / LoadBalancer | BOM | 一 |
| Nacos 发现 | BOM | 一 |
| Apache Dubbo | 3.2.10 | 一 |
| MySQL 驱动 | 8.0.27 | 二 |
| MyBatis-Plus | 3.5.5 | 二 |
| Druid | 1.2.20 | 二 |
| Flyway | BOM | 二 |
| Lombok | 1.18.30 | 一 |
| Hutool | 5.8.22 | 一 |
| springdoc-openapi | 2.3.0 | 一 |
| Actuator / Logback | BOM | 一 |

Python 仓（不在本仓）：Python 3.12、FastAPI、**Agent Harness**（LangGraph 作执行引擎）、官方 Postgres Checkpointer、对话入口 + Explosion（任务内会签 multi-agent）/ Quality。V1 无跨任务全局指挥 Agent。

### 3.2 条件引入

| 组件 | 条件 |
|---|---|
| Sa-Token 1.37.0 + Redis | 确认与电商共享登录态时引入 |
| Nacos 配置中心 | 需要远程配置时再开 |
| OSS | V1 不引入 |
| RocketMQ | V1 不引入 |

### 3.3 不引入

Sentinel、Seata、XXL-Job、Elasticsearch、Canal、ShardingSphere、独立规则引擎、数仓、为 Checkpoint 以外的用途新建 PostgreSQL 业务库。

只读 Dubbo 允许有限重试；若将来有写操作，该接口 `retries=0`。

---

## 四、配置与环境

1. 地址集中在 `wb-base.yml`（`wb.*`），各应用 `spring.config.import` 引入。
2. 密钥走环境变量，配置文件不写默认密码。含 MySQL、Postgres Checkpoint、内部签名、模型 Key。
3. Profile：`local` / `dev` / `prod`。
4. 提供 `.env.example`。
5. 工作台 Nacos 命名空间默认 `ai_workbench`，与电商隔离；Dubbo 消费电商的 namespace / group 另配。
6. 工作台 MySQL 独立库 `ai_workbench`。Checkpoint PostgreSQL 独立实例 / 独立库，Flyway 不管理该库。

---

## 五、Java 模块

Maven 结构保持 R1：`common-*`、`ai-workbench-gateway`、`ai-workbench-service`。Gateway 不依赖 Servlet 模块。

Service 内部按包划分，不拆微服务。V1 只建有代码的包：

```text
conversation/     会话、消息、对话转发、意图结果落任务
task/             任务状态机、领取、租约、重试、巡检
insight/
  snapshot/       从电商拉数，写快照
  feature/        对外特征批量 API
  report/         报告 upsert 与查询
integration/
  ecommerce/      只读 Dubbo 适配
  agent/          Python 客户端
internal/         供 Python 调用的内部 API
observability/
```

评分公式、质检规则、权重配置放 Python 仓 `scoring/`（Harness 本地库，与 Agent 同发）。Java 不实现正式分。Java 必须保存回传的分数、规则命中和 `scoring_version`。

不要为 analytics / scoring / quality 各建空模块。

---

## 六、电商只读集成

1. 先对齐 Dubbo 版本、注册中心、协议、序列化，**不伪造生产接口**。
2. V1 只封装只读能力：商品资料、库存、销售、流量、转化、价格、类目、成本 / 毛利、售后（退货退款、评价）。
3. 已确认：上述数据域在电商侧都有；统计方式为查库；规模约 2000 SKU、日订单约 30。
4. 接口路径、DTO、是否已有日汇总仍待电商提供 API jar / 文档（见第十七章）。未提供前 Adapter 只保留契约和 local 模拟。
5. 工作台不把订单明细当长期事实库。需要趋势时由 Java 写成快照特征。

调用分类：成功 / 业务失败 / 确定未执行 / 结果不确定。V1 只读，结果不确定按可重试失败处理，不进入写操作核对流程。

---

## 七、认证与内部安全

1. 不自建登录。`AuthAdapter` 隔离；local 用 `X-Wb-Dev-User`。电商认证细节未提供前，非 local 视为未登录。
2. Gateway 清除外部身份头，写入可信 `user_id`。Service 不信任前端传的用户 ID。
3. `merchant_id` / `tenant_id` 可空预留。V1 自营单店，数据范围 = 该店在售，不在请求里让用户传商家 ID。
4. Java ↔ Python：HMAC-SHA256，服务标识 + 时间戳 + nonce，5 分钟窗口，双向不同密钥，仅内网。
5. 不能把浏览器登录 Token 当作 Python 的服务身份。

---

## 八、数据模型

MySQL 8.0，`utf8mb4`，时间 UTC，Flyway 迁移。主键 `BIGINT`；对外 `task_id`、`run_id`、`report_id` 用字符串唯一键。

### 8.1 表

| 表 | 用途 |
|---|---|
| `ai_conversation` | 会话 |
| `ai_message` | 消息（含流式中断标记、关联 `task_id`） |
| `ai_task` | 业务任务（兼队列） |
| `ai_run` | 每次执行尝试 |
| `ai_product_metric_snapshot` | 按 SKU + 统计日的特征快照 |
| `ai_explosion_analysis` | 爆品筛选报告头（按 `task_id` 唯一） |
| `ai_explosion_item` | 爆品候选行 |
| `ai_quality_report` | 质检报告头（按 `task_id` 唯一） |
| `ai_quality_issue` | 质检问题行 |

不建：`ai_outbox`、`ai_task_approval`、`ai_operation_record`、独立证据表（证据 JSON 放问题行）。

LangGraph Checkpoint 只在独立 PostgreSQL，表由 Checkpointer 自管，不与上述表混合。

### 8.2 `ai_task` 关键字段

`task_id, task_type, task_status, user_id, merchant_id, conversation_id, thread_id, current_run_id, lease_token, lease_owner, lease_expires_at, last_heartbeat_at, cancel_requested_at, idempotency_key, input_ref, priority, available_at, next_action, workflow_version, deadline_at, scoring_version, result_ref, error_code, error_message, attempt_count, max_attempts, version, created_at, updated_at, started_at, finished_at`。

- `task_type`：`EXPLOSION` / `QUALITY`
- `next_action`：`START` / `RESUME`
- `deadline_at`：默认创建后 2 小时（分析任务短于原 48 小时）
- `input_ref`：OSS 不做时可用 JSON 列，但单行避免无界大数组；全量 2000 SKU 列表不要塞进任务行，筛选用条件而不是 ID 清单

领取索引：`(task_status, task_type, priority, available_at)`。

### 8.3 任务状态

```text
QUEUED → RUNNING → SUCCEEDED | FAILED | RETRY_WAIT | CANCELLED
RETRY_WAIT → RUNNING | CANCELLED
```

`WAITING_APPROVAL` V1 不启用。终态不可再转。状态机集中校验；条件更新带 `version`，Worker 回调加 `current_run_id + lease_token`。

取消为协作式：写 `cancel_requested_at`，心跳响应告知 Worker 停止。V1 无在途写操作，取消不必等外部核对。

### 8.4 快照

唯一键 `(sku_id, stat_date)`。字段见 [data-contract.md](data-contract.md)。任务开始时若当日快照缺失或过期，Java 先刷新再给 Python。2000 SKU 查库全量刷新可接受；用进程内定时任务即可，不引入 XXL-Job。

### 8.5 报告

同一 `task_id` **upsert**，重试不得插入第二份成功报告。明细行先删后插或按 `task_id + sku_id` 覆盖。报告必须带 `scoring_version`、`snapshot_date`、`user_id`、`conversation_id`、`summary`。

---

## 九、任务派发

与 R1 相同：Worker 声明 `task_type` + `workflow_version`，Java `FOR UPDATE SKIP LOCKED` 领取，生成 `run_id` 与 `lease_token`。无任务时长轮询（默认 20 秒），等待期间不占连接。

租约默认 60 秒，心跳 20 秒。过期回收后 `next_action=RESUME`。旧 Worker 令牌不匹配则拒绝。有限重试 + 指数退避。`deadline_at` 超时转 `FAILED`。

V1 建议 1 个 Worker 进程、并发 2～3。Checkpoint 仍用独立 Postgres，便于以后加机器。

巡检：租约回收、任务总时限、无匹配 Worker 告警、过期快照刷新、已结束任务清理。不巡检外部写操作。

RocketMQ 仅在未来有真实跨系统事件时再引入，不替代领取接口。

---

## 十、Java ↔ Python 契约

契约文档后续落 `docs/internal-api-contract.md`，带版本号。V1 方向如下。

### 10.1 Java 提供、Python 调用

| 接口 | 说明 |
|---|---|
| 领取 / 心跳 / 进度 / 成功 / 失败 | 与 R1 相同；成功回调前必须已 upsert 报告 |
| `POST /internal/features/query` | 按条件批量返回快照特征，**禁止**逐 SKU 循环打资料接口。V1 允许一次返回全部在售（约 2000 行） |
| `GET /internal/products/{skuId}/features` | 单品深挖 |
| `PUT /internal/tasks/{taskId}/explosion-report` | 爆品报告 upsert |
| `PUT /internal/tasks/{taskId}/quality-report` | 质检报告 upsert |
| `GET /internal/conversations/{conversationId}/reports` | 对话 Agent 读取本会话最近报告；Java 校验会话归属于请求携带的 `user_id` |

不提供「执行正式操作」。不提供逐个 `GET /products/{id}/profile` 作为筛选主路径。

### 10.2 Python 提供、Java 调用

| 接口 | 说明 |
|---|---|
| 对话 SSE | 对话 Agent；短回复；需要长任务时返回 `NEED_TASK(task_type, input)`，不在该请求内跑完筛选 / 质检 |
| 取消通知 | 可选，加速停止 |
| 查询状态 | 排障 |

### 10.3 一致性

1. 报告先写入 Java，再 complete。Checkpoint 不是交付物。
2. 分数与规则命中随报告落库，按 `task_id` 覆盖。
3. `RESUME` 但 Checkpoint 不存在 → `START`，打日志。
4. 同一 `run_id` 重复 complete 返回首次结果。
5. 任务创建时写入 `workflow_version`；领取只分配给声明支持该版本的 Worker。

---

## 十一、特征、评分、规则

这是 V1 的核心分层，替代原「正式操作保护」章。

```text
电商查库 → Java 快照特征 → Python 代码算分/规则命中 → Top N 会签 LLM（指挥/信号/风控/策略）→ 作战清单报告
```

| 层 | 谁 | 做什么 |
|---|---|---|
| 特征 | Java | 原始计数与金额：订单、件数、GMV（7/30/前 30/90 天）、曝光、点击、点击成交、退货退款订单、评价、价格、成本、库存、最近成交日 |
| 正式分与命中 | Python 代码 | 增速与比率（带门槛和平滑）、爆品加权分、质检问题、风险等级；权重与阈值与 Agent 同仓 |
| 会签与作战 | Explosion 内多 LLM | 目标/槽位计划、归因、风控 veto、动作分型；须标明是 AI 意见；**不得**改写正式分 |
| 质检解读 | Quality LLM | 问题证据与建议（批量 ≤50） |

Python 爆品主路径：一次拉取特征 → 内存对最多约 2000 行打分排序并挂质检标签 → **只把 Top N（默认 20，上限 50）送入会签** → 产出 `action_bucket` 与槽位分配。质检批量上限 50；全店质检必须先筛再检，禁止 2000 条全部进模型。

爆品硬指标：流量增长、点击率与转化率、销售规模、销售增速、毛利、库存可支撑天数。竞争力 V1 只做店内同类目对比，不叫市场竞争力。  
作战增强（R2-14）：`goal_mode`（`GMV`/`PROFIT`/`CLEARANCE`）、`focus_slots`（默认 5）、`action_bucket`（`PUSH`/`FIX_THEN_PUSH`/`WATCH`/`DROP`）。目标模式不改写 `explosion_score` 公式。计划修订默认最多 2 次、会签大轮最多 3 次。细则见 [agents/explosion-agent.md](agents/explosion-agent.md)。

**样本量约束（R2-12）**：日订单约 30 单，单 SKU 订单稀疏。正式口径以 30 天对比前 30 天为主，90 天补充，7 天只展示。每个分项和规则都有最低样本门槛，不满足标 `LOW_SAMPLE` 并跳过，不按 0 或 100% 计算；增速和比率做平滑；流量信号权重高于销量增速。细则见 [data-contract.md](data-contract.md) 第 0、2 节。

两个专家必须交叉：

- 爆品每一行带质检风险等级和命中的规则 ID（缺货、亏本、退货异常等），以及会签后的动作分型
- 质检每一行带爆品规则分或「是否进入当次爆品候选」
- 规则 ID 两端相同，例如 `STOCK_LOW`、`PROFIT_LOW`、`RETURN_HIGH`

公式与阈值的权威文件在 Python 仓，Java 报告只存结果、`scoring_version` 与 `council_version`。

---

## 十二、健壮性（摘要）

完整数值沿用 R1 第十三章中仍适用的部分，调整如下：

- 虚拟线程开启；长轮询与调电商期间不持有数据库事务。
- 每用户同时流式对话默认 3；每用户排队 + 运行中任务默认 10（分析任务比上架更轻，但对话是唯一入口，需防连刷）。
- 时间一律用 MySQL `NOW(3)` 比较租约与截止时间。
- 隔离级别 `READ COMMITTED`。
- Python 调特征查询的超时要大于 Java 查电商 + 写快照；外层大于内层，启动时校验。
- 电商只读连续失败时进程内快速失败，避免打满。
- Checkpoint Postgres 不可用：新任务可 `START` 跑完，但不能 `RESUME`；应告警。不可改写 MySQL 冒充 Checkpoint。
- 指标：可领取任务等待时长、租约回收次数、快照刷新耗时、任务成功率、LLM 调用次数（按角色：campaign/signal/risk/strategy）、计划修订次数、`plan_degraded` 率（Python 回传）。

---

## 十三、暂缓

- 写回电商、审批、操作幂等、内容去重
- 新品选品、定时日报、独立筛选页、任务进度 SSE
- **跨任务全局指挥 Agent**（自动连续派 Explosion→Quality 等）
- 推荐效果回测（V1.1）：利用按天积累的快照，检查推荐 SKU 在之后 2～4 周是否真的增长，用来校准权重
- 质检 P2、独立规则后台、RocketMQ、OSS
- Sentinel、评测平台、分库分表、K8s 自动扩缩容
- 多商家、管理员查看他人报告

---

## 十四、分期（对齐约 3 个月完善第一版）

### 阶段一：工程骨架（已进行）

Gateway、Service、公共模块、Dubbo 客户端注册、虚拟线程、超时预算、文档。验收：`mvn clean verify`。不声称已与电商互通。

### 阶段二：基础设施

MySQL + Flyway 核心表（含爆品报告作战字段）、内部签名、Checkpoint Postgres 连接信息（由 Python 使用）、契约草稿。

### 阶段三：任务可靠性

领取、心跳、租约、取消、重试、deadline、巡检。用模拟 Worker 验收，不依赖真实模型。

### 阶段四：数据与评分闭环（约对应 M1）

- 只读 Adapter + 快照刷新 + `features/query`
- `scoring/` + 交叉打标 + 报告 upsert 骨架
- 对话 Agent：意图闸门（含 `OUT_OF_SCOPE`）、默认 `time_window_days=30` / `goal_mode=GMV` / `focus_slots=5`、路由 `EXPLOSION` / `QUALITY`
- local 可模拟 2000 SKU 特征

### 阶段五：Explosion 会签 multi-agent（约对应 M2）

- LangGraph：信号 ∥ 风控 → 策略 → reduce
- `action_bucket` / 槽位 / `council_excerpt` 落库
- 角色级观测与单角色降级

### 阶段六：计划状态机 + Quality 闭环 + 加固（约对应 M3）

- `plan` 可 `REVISE`（上限 2）与 `plan_degraded`
- 「这批完整质检」从爆品报告取 sku_ids 建 `QUALITY`
- Dockerfile、故障：Worker 崩溃恢复、fencing、重复 complete、快照缺失、LLM 超时、Checkpoint 不可用、会签空转打满上限

---

## 十五、测试

- Java：状态机、领取并发、快照 upsert、报告按 task_id 覆盖、签名、超时预算启动校验。
- Python：评分函数纯单测（同一快照分数稳定）、规则命中、Top N 截断、`NO_DATA` / `LOW_SAMPLE` 跳过、平滑后 0 单到 1 单不会排进增速榜首。
- 契约：禁止筛选路径逐 SKU 调用。
- 外部电商与模型用模拟。

---

## 十六、交付

与 R1 第十八章相同：真实工程、可编译、关键路径有实现和测试、不编造未知电商接口、未验证不声称通过。先完成当前阶段再进入下一阶段。

---

## 十七、已拍板 vs 先不管

### 已拍板

见文首 R2-01～R2-13，以及：对话入口、自营单店、P0+P1、交叉打标、Java 特征 / Python 代码分 / LLM 分析、独立 Postgres Checkpoint、B1 数据域都有、B2 规模与查库。

### 采用默认、本期不展开

| 项 | 默认 |
|---|---|
| 时间窗 | 近 30 天对比前 30 天，90 天补充；7 天只展示 |
| Top N | 默认 20，上限 50 |
| 质检批量 | 上限 50 |
| 规则配置 | Python 仓配置文件，不做管理后台 |
| 前端 | 独立仓；V1 对话里渲染列表和问题，不单独做筛选工作台首页 |
| Redis / OSS | 认证需要才上 Redis；不上 OSS |
| Worker | 1 进程，并发 2～3 |
| 权限 | 登录即可用；按 userId 隔离 |

### 待外部提供（不阻塞改文档，阻塞阶段四真实对接）

| 编号 | 事项 |
|---|---|
| E-01 | Dubbo 注册中心、namespace、group、协议、序列化 |
| E-02 | 各只读接口 API jar / 文档、是否已有日汇总表 |
| E-04 | 认证方式、Gateway 如何校验登录态 |
| I-01 | 工作台 MySQL |
| I-06 | Checkpoint PostgreSQL |
| I-04 | Redis 是否因 Sa-Token 需要 |
| P-04 | 模型供应商与调用方式 |
