"""
跨会话长期记忆的读写约定。

系统记忆（全站事实）和运营画像（个人筛选偏好）由 Java 落在 ai_long_memory，
本模块只负责合并进本轮筛选，以及写成给模型看的短前缀。
"""

from __future__ import annotations

from typing import Any

from scoring.math_utils import num
from scoring.user_filters import FILTER_KEYS, describe_rank_filters


def filters_from_profile(profile: dict[str, Any] | None) -> dict[str, float]:
    """
    从运营画像里取出排序门槛。

    Args:
        profile: Java 下发的 user_profile，值是字符串。

    Returns:
        dict: 合法的 margin_min / rate_per_min / gmv_30d_min / orders_30d_min。
    """
    out: dict[str, float] = {}
    for key in FILTER_KEYS:
        value = num((profile or {}).get(key))
        if value is None or value < 0:
            continue
        if key == "margin_min" and value > 1:
            value = value / 100.0
        out[key] = float(value)
    return out


def merge_rank_filters(
    profile_filters: dict[str, float] | None,
    turn_filters: dict[str, float] | None,
) -> dict[str, float]:
    """
    画像打底，本句话里的门槛覆盖同名字段。

    Args:
        profile_filters: 跨会话偏好。
        turn_filters: 本轮 LLM 抽出的条件。

    Returns:
        dict: 本轮实际用于过滤的门槛。
    """
    merged = dict(profile_filters or {})
    merged.update(dict(turn_filters or {}))
    return merged


def patch_from_filters(turn_filters: dict[str, float] | None) -> dict[str, str]:
    """
    本轮新说出的门槛，回写画像。没说的键不写，避免清掉旧偏好。

    Args:
        turn_filters: 本轮抽出的条件。

    Returns:
        dict: 字符串值，便于 Java 落库。
    """
    out: dict[str, str] = {}
    for key, value in (turn_filters or {}).items():
        if key not in FILTER_KEYS:
            continue
        if key == "margin_min":
            text = f"{float(value):.4f}".rstrip("0").rstrip(".")
        else:
            text = f"{float(value):g}"
        out[key] = text
    return out


def render_memory_preface(system_memory: dict[str, Any] | None) -> str:
    """
    系统事实前缀，拼进解读 / 建议 / 文案的系统提示。

    Args:
        system_memory: Java 下发的系统记忆。

    Returns:
        str: 无事实时为空串。
    """
    line = str((system_memory or {}).get("business_line") or "").strip()
    if not line:
        return ""
    return f"系统事实：{line}。解读、建议和文案要贴合该品类，不要写成其他行业。"


def prompt_with_memory(base: str, preface: str) -> str:
    """有系统事实时加在系统提示最前面。"""
    text = (preface or "").strip()
    if not text:
        return base
    return f"{text}\n\n{base}"


def filter_note(filters: dict[str, float] | None, *, from_profile: bool) -> str:
    """给运营看的过滤说明；来自画像时点明是长期偏好。"""
    note = describe_rank_filters(filters)
    if note and from_profile:
        return "沿用你的长期偏好。" + note
    return note
