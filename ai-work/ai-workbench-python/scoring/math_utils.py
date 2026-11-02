"""评分用的小工具：安全取数、平滑增速、向均值收缩。"""

from __future__ import annotations

from typing import Any


def num(value: Any, default: float | None = None) -> float | None:
    """
    把字段转成 float；None / 缺失返回 default。

    Args:
        value: 原始值。
        default: 缺失时的默认。

    Returns:
        float | None: 数值或 default。
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def smoothed_growth(curr: float, prev: float, alpha: float) -> float:
    """
    (curr+α)/(prev+α) - 1。

    Args:
        curr: 当前窗口。
        prev: 对比窗口。
        alpha: 平滑量。

    Returns:
        float: 增速。
    """
    return (curr + alpha) / (prev + alpha) - 1.0


def shrink_to_mean(rate: float, n: float, prior_rate: float, prior_n: float) -> float:
    """
    样本少时向 prior 收缩。

    Args:
        rate: 自身比率。
        n: 自身样本量。
        prior_rate: 店铺/先验比率。
        prior_n: 先验伪计数。

    Returns:
        float: 收缩后比率。
    """
    return (rate * n + prior_rate * prior_n) / (n + prior_n)


def clamp01(x: float) -> float:
    """限制到 [0, 1]。"""
    return max(0.0, min(1.0, x))


def growth_to_unit(growth: float, *, pos_cap: float = 2.0, neg_cap: float = -0.8) -> float:
    """
    把增速映射到约 [0,1]，便于加权。

    正增长：0→0.5，pos_cap→1；负增长：0→0.5，neg_cap→0。
    """
    if growth >= 0:
        return 0.5 + 0.5 * clamp01(growth / pos_cap)
    return 0.5 * clamp01(1.0 - growth / neg_cap)

