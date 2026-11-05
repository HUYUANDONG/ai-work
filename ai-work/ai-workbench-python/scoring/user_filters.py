"""
运营口语筛选条件 → 排序字段。

LLM 只负责把「利润三成以上、转化率 5% 以上」抽成数字；
比较、丢弃、排序仍由代码做。缺字段不算达标。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from scoring.math_utils import num

logger = logging.getLogger(__name__)

# 与 scoring 行上的字段对齐。未提到的键不要出现。
FILTER_KEYS = ("margin_min", "rate_per_min", "gmv_30d_min", "orders_30d_min")

_HINTS = (
    "利润",
    "毛利",
    "转化",
    "以上",
    "不低于",
    "至少",
    "大于",
    "超过",
    "高于",
    "不少于",
)

_SYSTEM = """你是电商选品条件解析器。把运营原话里的筛选下限抽成 JSON，不要解释。
只允许这些键，没提到的必须是 null，禁止猜测：
- margin_min：毛利/利润率下限，写成 0~1 的小数。例：30%、百分之三十、三成 → 0.3
- rate_per_min：页面转化率下限，与接口 ratePer 同一刻度（百分数数值，不是 0~1）。例：5%、5个点 → 5；0.5% → 0.5
- gmv_30d_min：窗口销售额下限，纯数字
- orders_30d_min：订单数下限，纯数字
没有筛选条件时四个键都是 null。必须输出 JSON 对象。"""


def message_has_rank_constraint(message: str) -> bool:
    """
    原话里是否像在加筛选门槛。

    没有这些说法就不调 LLM。
    """
    text = (message or "").strip()
    if not text:
        return False
    return any(k in text for k in _HINTS)


def parse_rank_filter_json(raw: str) -> dict[str, float]:
    """
    解析 LLM 返回的筛选 JSON。

    Args:
        raw: 模型正文，允许包一层 markdown。

    Returns:
        dict: 只保留合法正数门槛；空表示不加条件。
    """
    text = (raw or "").strip()
    if not text:
        return {}
    fenced = re.search(r"\{[\s\S]*\}", text)
    if fenced:
        text = fenced.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("rank filter JSON parse failed: %s", raw[:200])
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, float] = {}
    for key in FILTER_KEYS:
        value = num(data.get(key))
        if value is None or value < 0:
            continue
        if key == "margin_min" and value > 1:
            # 模型若把 30% 写成 30，收成 0.3
            value = value / 100.0
        out[key] = float(value)
    return out


def describe_rank_filters(filters: dict[str, float] | None) -> str:
    """把门槛翻成给运营看的一句中文。"""
    if not filters:
        return ""
    parts: list[str] = []
    margin = filters.get("margin_min")
    if margin is not None:
        parts.append(f"毛利≥{margin:.0%}")
    rate = filters.get("rate_per_min")
    if rate is not None:
        parts.append(f"页面转化率≥{rate:g}%")
    gmv = filters.get("gmv_30d_min")
    if gmv is not None:
        parts.append(f"窗口销售额≥{gmv:g}")
    orders = filters.get("orders_30d_min")
    if orders is not None:
        parts.append(f"订单≥{orders:g}")
    if not parts:
        return ""
    return "已按条件过滤：" + "，".join(parts) + "。缺字段的商品不算达标。"


def row_passes_filters(metrics: dict[str, Any], filters: dict[str, float] | None) -> bool:
    """
    打分后的硬过滤。

    门槛未给出则通过；给出了但该字段缺失，则不通过。
    """
    if not filters:
        return True
    margin_min = filters.get("margin_min")
    if margin_min is not None:
        margin = _margin(metrics)
        if margin is None or margin < margin_min:
            return False
    rate_min = filters.get("rate_per_min")
    if rate_min is not None:
        rate = num(metrics.get("rate_per"))
        if rate is None or rate < rate_min:
            return False
    gmv_min = filters.get("gmv_30d_min")
    if gmv_min is not None:
        gmv = num(metrics.get("gmv_30d"))
        if gmv is None or gmv < gmv_min:
            return False
    orders_min = filters.get("orders_30d_min")
    if orders_min is not None:
        orders = num(metrics.get("orders_30d"))
        if orders is None or orders < orders_min:
            return False
    return True


def _margin(metrics: dict[str, Any]) -> float | None:
    """售价、成本都有且售价为正时，返回 (price-cost)/price。"""
    price = num(metrics.get("price"))
    cost = num(metrics.get("cost"))
    if price is None or cost is None or price <= 0:
        return None
    return (price - cost) / price


async def extract_rank_filters(message: str, llm: Any | None) -> dict[str, float]:
    """
    有筛选说法时调 LLM 抽字段；否则返回空条件。

    Args:
        message: 用户原话。
        llm: ``LlmClient``；未配置或失败时不加条件。

    Returns:
        dict: ``margin_min`` / ``rate_per_min`` / ``gmv_30d_min`` / ``orders_30d_min``。
    """
    if not message_has_rank_constraint(message):
        return {}
    if llm is None or not getattr(llm, "enabled", False):
        return {}
    try:
        raw = await llm.chat(system=_SYSTEM, user=(message or "").strip(), json_mode=True)
    except Exception as exc:  # noqa: BLE001 — 抽条件失败不阻断榜单
        logger.warning("rank filter extract failed: %s", exc)
        return {}
    return parse_rank_filter_json(raw)
