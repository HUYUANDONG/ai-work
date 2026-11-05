# Python 包分层（对齐 Nest 心智）

FastAPI 没有官方 Nest 模块系统，本仓用目录约定等价分层。

| 本仓 | Nest 大致对应 | 职责 |
|---|---|---|
| `api/controllers` | Controller | HTTP 进出、状态码；不写业务 |
| `api/deps.py` | 构造注入 / providers | `Depends` 拿 Service / Runtime |
| `api/router.py` | AppModule 路由汇总 | `include_router` |
| `services/` | Service | 用例编排，调用 agents / clients |
| `schemas/` | DTO | Pydantic 请求响应 |
| `core/` | ConfigModule | 环境配置 |
| `agents/` | 领域 Feature（非 HTTP） | 对话编排、爆品叶子、质检图 |
| `harness/` | 运行时配套 | `AppRuntime`（共享依赖盒）、Checkpoint |
| `clients/` | Infrastructure HTTP | Java 内部 API |
| `tools/` | 薄适配 | query_features 等 |
| `scoring/` | 领域纯函数 | 打分 / 规则 |
| `db/` | Infrastructure DB | Checkpoint |
| `app/main.py` | main.ts | **只** `create_app()` |

依赖方向（不要反向）：

```text
controllers → services → agents / scoring / tools → clients / db
                ↘ schemas、core
```

启动：`uvicorn app.main:app`。营销和质检都在对话这一轮里做完。
