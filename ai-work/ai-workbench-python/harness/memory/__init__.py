"""
上下文与记忆（业界常见方案精简落地）：

- Token 预算与校准
- 确定性 Session Facts
- 分层记忆 rails（working / summary / archive / constraints）
- 行为级自修复（空输出 / 假完成）
- 进度感知熔断
"""

from harness.memory.facts import extract_report_facts, render_facts_block
from harness.memory.progress import ProgressBreaker
from harness.memory.rails import MemoryStore, SessionMemory
from harness.memory.repair import chat_with_repair, is_empty_output, is_fake_completion
from harness.memory.slim import slim_candidates_for_llm, slim_reports_for_llm
from harness.memory.tokens import TokenBudget, estimate_tokens

__all__ = [
    "TokenBudget",
    "estimate_tokens",
    "extract_report_facts",
    "render_facts_block",
    "MemoryStore",
    "SessionMemory",
    "chat_with_repair",
    "is_empty_output",
    "is_fake_completion",
    "ProgressBreaker",
    "slim_candidates_for_llm",
    "slim_reports_for_llm",
]
