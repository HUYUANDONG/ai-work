"""
正式评分与质检规则库（代码，非 Agent）。

从营销特征挖 SKU：filter → score → 挂质检标 → Top N。
"""

from scoring.action_bucket import assign_action_buckets
from scoring.config import SCORING_VERSION
from scoring.explosion import score_sku
from scoring.pipeline import filter_marketing_candidates, rank_candidates
from scoring.quality import check_sku

__all__ = [
    "SCORING_VERSION",
    "score_sku",
    "check_sku",
    "filter_marketing_candidates",
    "rank_candidates",
    "assign_action_buckets",
]
