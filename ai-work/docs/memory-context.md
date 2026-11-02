# 上下文与记忆（业界常见方案落地）

参考 ADM 等本地 Agent 的优点，用**开源业界常见做法**在本仓实现精简版（未复制未开源 `admAgent` 代码）。

## 模块

路径：`ai-workbench-python/harness/memory/`

| 能力 | 文件 | 做法 |
|---|---|---|
| Token 预算 | `tokens.py` | CJK≈1、其它≈4 字/token；`guard_ratio` 输入守卫；可用真实 `prompt_tokens` 校准 |
| Session Facts | `facts.py` | **代码**从报告抽 SKU/分/桶/风险，禁止模型编数 |
| 分层记忆 | `rails.py` | working / summary / archive 指针 / constraints（可 supersede 推翻） |
| 确定性压缩 | `rails.compact_working` | 留尾部、旧轮折叠进 summary（不做 summary-of-summary 二次压糊） |
| 载荷瘦身 | `slim.py` | 会签/追问 JSON 按预算截断 |
| 自修复 | `repair.py` | 空输出重试、假完成 nudge（不是 critic LLM） |
| 进度熔断 | `progress.py` | 指纹有进展则重置；连续空转 TRIPPED |

## 接到哪里

- Chat `FOLLOWUP`：Facts + 分层记忆组装 prompt + `chat_with_repair`
- Chat `SKU_DEEP`：`chat_with_repair`
- Explosion 会签：`slim_candidates_for_llm`；修订环用 `ProgressBreaker`
- 配置：`WB_LLM_CONTEXT_WINDOW` / `WB_LLM_RESERVE_OUTPUT` / `WB_CHAT_WORKING_KEEP_LAST`

## 明确不做（避免照搬 ADM 重资产）

- 整仓 git undo
- 两次 LLM 的超长分层摘要流水线
- write-only、无法推翻的项目记忆
- 第二套「幻觉反思」大模型
