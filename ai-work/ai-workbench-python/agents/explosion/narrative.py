"""
运营可读的爆品结论：思考过程 + 推荐商品 + 趋势。

前端当前只展示对话 `reply`，不接思考 SSE，所以把可见步骤写进 summary。
思考过程必须引用 Java/运营字段证据（销售额、订单、UV、转化等），让人信服结论。
"""

from __future__ import annotations

from typing import Any

_BUCKET_LABEL = {
    "PUSH": "本周可主推",
    "FIX_THEN_PUSH": "先修再冲",
    "WATCH": "观察一周",
    "DROP": "暂不主推",
}


def build_operator_report(
    candidates: list[dict[str, Any]],
    *,
    goal_mode: str,
    slots: int,
    plan: dict[str, Any],
    features: dict[str, Any] | None = None,
    thinking_events: list[dict[str, Any]] | None = None,
    task_input: dict[str, Any] | None = None,
    advise_context: dict[str, Any] | None = None,
    advise_llm_text: str | None = None,
    offer_advise: bool = False,
    advice_offer_question: str | None = None,
) -> str:
    """
    生成用户可见的分析正文。

    Args:
        candidates: 已打分、会签后的候选。
        goal_mode: GMV / PROFIT / CLEARANCE。
        slots: 本周槽位上限。
        plan: 会签计划。
        features: 特征查询结果（含 snapshot_date / mock）。
        thinking_events: Worker 已上报的思考事件。
        task_input: 任务输入。
        advise_context: 建议阶段板块/大盘辅源。
        advise_llm_text: LLM（或模板）写好的投放建议正文；有则优先生效。
        offer_advise: True 时不写投放段，文末询问是否要建议。
        advice_offer_question: 询问句；默认见 intent.ADVICE_OFFER_QUESTION。

    Returns:
        str: 多段中文结论。
    """
    feats = features or {}
    inp = task_input or {}
    events = thinking_events or []
    advise = advise_context or {}
    focus = [c for c in candidates if c.get("in_focus_slot")]
    ranked = list(candidates)
    source_note = _source_note(feats, ranked)
    window = int(inp.get("time_window_days") or 30)
    pool = int(feats.get("row_count") or feats.get("pool_size") or len(ranked))

    has_llm_advise = bool(advise_llm_text and str(advise_llm_text).strip())
    # 询问或 LLM 建议已覆盖投放段时，思考过程不再重复模板板块句
    thinking_advise = {} if offer_advise or has_llm_advise else advise
    parts: list[str] = [
        _thinking_block(
            events,
            candidates=ranked,
            focus=focus,
            advise=thinking_advise,
            snapshot_date=str(feats.get("snapshot_date") or ""),
            pool=pool,
            plan=plan,
            source_note=source_note,
            goal_mode=goal_mode,
            window_days=window,
        ),
        _recommend_block(ranked, focus=focus, goal_mode=goal_mode, slots=slots),
    ]
    if offer_advise:
        q = (advice_offer_question or "").strip()
        if not q:
            from agents.chat.intent import ADVICE_OFFER_QUESTION

            q = ADVICE_OFFER_QUESTION
        parts.append(q)
    elif has_llm_advise:
        parts.append(str(advise_llm_text).strip())
    else:
        parts.append(_placement_block(advise))
    parts.append(_trend_block(ranked, window_days=window))
    return "\n\n".join(p for p in parts if p).strip()


def _source_note(features: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    """说明数据来源，避免把联调 fixture 当成店内真实商品。"""
    source = str(features.get("source") or "")
    if source == "goodsStatList":
        return (
            "数据口径：`goodsStatList` 的销售额/订单为实时窗口聚合；"
            "PV/UV 为昨日流量；`ratePer` 为页面转化率展示值，勿与实时销售混成同一天。"
        )
    if features.get("mock") is True or source == "fixture":
        return "当前特征来自 Java 联调快照（示例 SKU），尚未拉到电商 `goodsStatList`。"
    skus = [str(c.get("sku_id") or "") for c in candidates]
    if skus and all(s.startswith("SKU-00") for s in skus):
        return "当前特征来自 Java 联调快照（示例 SKU），尚未拉到电商实时报表。"
    return "特征来自 Java 商品快照。"


def _thinking_block(
    events: list[dict[str, Any]],
    *,
    candidates: list[dict[str, Any]],
    focus: list[dict[str, Any]],
    advise: dict[str, Any],
    snapshot_date: str,
    pool: int,
    plan: dict[str, Any],
    source_note: str,
    goal_mode: str,
    window_days: int,
) -> str:
    """
    用运营字段证据写思考过程，而不是只罗列「正在打分」。
    """
    lines = ["**思考过程**"]
    step = 1
    lines.append(
        f"{step}. 拉取在售商品销量特征，共 {pool} 条"
        f"（快照日 {snapshot_date or '未知'}，目标 {goal_mode}，关注近 {window_days} 天口径说明）。"
    )
    step += 1

    evidence_items = list(focus) if focus else list(candidates[:5])
    if not evidence_items and candidates:
        evidence_items = candidates[:3]
    if evidence_items:
        lines.append(f"{step}. 对照销量与流量证据（优先看销售额/订单，流量与转化作辅助）：")
        for item in evidence_items[:5]:
            lines.append(f"   - {_evidence_bullet(item)}")
        step += 1

    if focus:
        reasons = []
        for item in focus[:5]:
            name = str(item.get("title") or item.get("sku_id") or "")
            score = item.get("explosion_score")
            bucket = _BUCKET_LABEL.get(str(item.get("action_bucket") or ""), "观察")
            risk = item.get("quality_risk_level") or "NONE"
            rules = "、".join(str(x) for x in (item.get("quality_rule_ids") or [])[:3])
            bit = f"「{name}」分 {score} → {bucket}（风险 {risk}"
            if rules:
                bit += f"，规则 {rules}"
            bit += "）"
            reasons.append(bit)
        lines.append(
            f"{step}. 据此代码打分并会签定槽（会签源见轮次 "
            f"{plan.get('llm_round') or 1}）：" + "；".join(reasons) + "。"
        )
        step += 1
    else:
        lines.append(
            f"{step}. 本轮未形成进槽款：高分不足或风险约束过严，"
            f"会签 {plan.get('llm_round') or 1} 轮后仍以观察为主。"
        )
        step += 1

    plates = list(advise.get("plates") or [])
    if plates:
        top = plates[0]
        top_name = str(top.get("stat_field_name") or top.get("stat_field") or "头部板块")
        lines.append(
            f"{step}. 投放建议依据日板块流量：流量最高的是「{top_name}」"
            f"（UV {top.get('self_uv')}，板块销售额 {top.get('order_sales')}，"
            f"订单 {top.get('order_numbers')}）；"
            "未验证进槽款是否已挂该板块，仅作位置试投参考。"
        )
        step += 1
    elif str(advise.get("source") or "") in {"no_credentials", "error"}:
        lines.append(
            f"{step}. 本轮未能补拉日板块流量（{advise.get('source')}），"
            "选品结论仍以上述销量证据为准。"
        )
        step += 1

    # 可选：把关键阶段标题压缩成一行，避免淹没证据
    visible = [e for e in events if e.get("visible", True) and e.get("title")]
    if visible:
        titles = " → ".join(str(e.get("title") or "").strip() for e in visible[:6] if e.get("title"))
        if titles:
            lines.append(f"{step}. 流水线步骤：{titles}。")

    lines.append(source_note)
    return "\n".join(lines)


def _evidence_bullet(item: dict[str, Any]) -> str:
    """单条商品的证据句：销售额、订单、UV/PV、转化。"""
    name = str(item.get("title") or item.get("sku_id") or "未命名商品").strip()
    sku = item.get("sku_id")
    metrics = _metrics(item)
    yuan = str(metrics.get("amount_unit") or "") == "yuan" or metrics.get("orderSales") is not None
    gmv = _money(metrics.get("gmv_30d"), yuan=yuan)
    orders = metrics.get("orders_30d")
    uv = metrics.get("clicks_30d")
    pv = metrics.get("impressions_30d")
    pays = metrics.get("paid_orders_from_clicks_30d")
    rate = _rate_text(metrics)
    gmv_g = _growth(item, "gmv_30d", "gmv_prev_30d")

    bits = [f"「{name}」（{sku}）"]
    if gmv != "未知":
        growth = f"，较前窗 {gmv_g:+.0%}" if gmv_g is not None else ""
        bits.append(f"窗口销售额约 {gmv}{growth}")
    if orders is not None:
        bits.append(f"订单 {orders}")
    if uv is not None:
        bits.append(f"昨日 UV {uv}")
    if pv is not None:
        bits.append(f"昨日 PV {pv}")
    if rate:
        bits.append(rate)
    elif pays is not None and uv not in (None, 0, 0.0):
        try:
            approx = float(pays) / float(uv) * 100.0
            bits.append(f"支付用户/UV 约 {approx:.2f}%（由 orderPays÷goodsUv 估算，非页面 ratePer）")
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    score = item.get("explosion_score")
    if score is not None:
        bits.append(f"代码分 {score}")
    return "；".join(bits)


def _rate_text(metrics: dict[str, Any]) -> str:
    """优先用页面 ratePer。"""
    rate = metrics.get("rate_per")
    if rate is None:
        rate = metrics.get("ratePer")
    if rate is None:
        return ""
    try:
        val = float(rate)
    except (TypeError, ValueError):
        return ""
    return f"页面转化率 {val:g}%"


def _recommend_block(
    candidates: list[dict[str, Any]],
    *,
    focus: list[dict[str, Any]],
    goal_mode: str,
    slots: int,
) -> str:
    lines = [
        f"**本周推荐**（目标 {goal_mode}，槽位上限 {slots}，进槽 {len(focus)} 个）",
    ]
    shown: set[str] = set()
    order = list(focus) + [c for c in candidates if not c.get("in_focus_slot")]
    if not order:
        return "\n".join(lines + ["暂无可用候选。"])

    for idx, item in enumerate(order[:8], start=1):
        sku = str(item.get("sku_id") or "?")
        if sku in shown:
            continue
        shown.add(sku)
        lines.append(_sku_card(idx, item))
    return "\n".join(lines)


def _sku_card(idx: int, item: dict[str, Any]) -> str:
    name = str(item.get("title") or item.get("goodsName") or "").strip() or "未命名商品"
    sku = item.get("sku_id")
    score = item.get("explosion_score")
    risk = item.get("quality_risk_level") or "NONE"
    bucket = str(item.get("action_bucket") or "WATCH")
    label = _BUCKET_LABEL.get(bucket, bucket)
    rules = "、".join(str(x) for x in (item.get("quality_rule_ids") or [])[:4]) or "无"
    slot = "进槽" if item.get("in_focus_slot") else "未进槽"
    action = str(item.get("primary_action") or "").strip()
    head = (
        f"{idx}. **{name}**（{sku}）· 分 {score} · 风险 {risk} · {label}（{slot}）"
    )
    bits = [_metric_line(item), f"规则：{rules}"]
    if action:
        bits.append(action)
    return head + "\n   " + "；".join(bits)


def placement_block_fallback(advise: dict[str, Any]) -> str:
    """
    模板投放建议（LLM 不可用或失败时的降级）。

    Args:
        advise: features/advise 响应。

    Returns:
        str: 建议段落；无板块数据则空串或错误说明。
    """
    return _placement_block(advise)


def _placement_block(advise: dict[str, Any]) -> str:
    """
    用日板块流量写投放位置建议（未验证商品是否已挂该板块）。

    Args:
        advise: features/advise 响应。

    Returns:
        str: 建议段落；无板块数据则空串。
    """
    plates = list(advise.get("plates") or [])
    if not plates:
        source = str(advise.get("source") or "")
        if source in {"no_credentials", "error"}:
            return (
                "**投放建议**\n"
                f"- 未能拉取日板块流量（{source}："
                f"{advise.get('message') or '无详情'}），本轮只给选品结论。"
            )
        return ""
    lines = [
        "**投放建议**（来自日板块流量；未验证该品是否已挂对应板块）",
    ]
    for plate in plates[:5]:
        name = str(plate.get("stat_field_name") or plate.get("stat_field") or "未命名板块")
        uv = plate.get("self_uv")
        sales = plate.get("order_sales")
        orders = plate.get("order_numbers")
        lines.append(
            f"- {name}：UV {uv}，销售额 {sales}，订单 {orders}"
        )
    top = plates[0]
    top_name = str(top.get("stat_field_name") or top.get("stat_field") or "头部板块")
    lines.append(
        f"- 进槽款可优先试投「{top_name}」附近高流量位，观察转化后再加码。"
    )
    store = advise.get("store") if isinstance(advise.get("store"), dict) else {}
    if store:
        lines.append(
            f"- 大盘背景：首页 UV {store.get('hpage_uv')}，"
            f"转化率 {store.get('conversion_rate')}（仅背景，不点名爆品）。"
        )
    return "\n".join(lines)


def _trend_block(candidates: list[dict[str, Any]], *, window_days: int) -> str:
    if not candidates:
        return ""
    rising: list[str] = []
    constrained: list[str] = []
    for item in candidates[:6]:
        name = str(item.get("title") or item.get("sku_id") or "")
        gmv_g = _growth(item, "gmv_30d", "gmv_prev_30d")
        click_g = _growth(item, "clicks_30d", "clicks_prev_30d")
        if gmv_g is not None and gmv_g >= 0.3:
            rising.append(f"{name} 销售额 {gmv_g:+.0%}")
        if click_g is not None and click_g >= 0.3:
            rising.append(f"{name} 点击 {click_g:+.0%}")
        rules = set(item.get("quality_rule_ids") or [])
        if rules.intersection({"STOCK_LOW", "PROFIT_LOW", "PROFIT_NEGATIVE"}):
            constrained.append(f"{name}（{'/'.join(sorted(rules))}）")

    lines = [f"**趋势**（正式分按 30 天快照；你指定的 {window_days} 天窗口只作口径说明）"]
    if rising:
        lines.append("- 走强：" + "；".join(rising[:6]) + "。")
    else:
        lines.append("- 头部未见稳定的高增长，避免把小样本跳变当成爆款。")
    if constrained:
        lines.append("- 约束：" + "；".join(constrained[:4]) + "，有信号也不宜硬推。")
    top = candidates[0]
    lines.append(
        f"- 代码分最高是「{top.get('title') or top.get('sku_id')}」"
        f"（{top.get('explosion_score')} 分），"
        "未到 70 分通常不进入主推，先小步测曝光。"
    )
    return "\n".join(lines)


def _metric_line(item: dict[str, Any]) -> str:
    metrics = _metrics(item)
    yuan = str(metrics.get("amount_unit") or "") == "yuan" or metrics.get("orderSales") is not None
    gmv = _money(metrics.get("gmv_30d"), yuan=yuan)
    gmv_prev = _money(metrics.get("gmv_prev_30d"), yuan=yuan)
    gmv_g = _growth(item, "gmv_30d", "gmv_prev_30d")
    clicks = metrics.get("clicks_30d")
    clicks_prev = metrics.get("clicks_prev_30d")
    click_g = _growth(item, "clicks_30d", "clicks_prev_30d")
    orders = metrics.get("orders_30d")
    parts = []
    if gmv != "未知":
        growth = f"，较前窗 {gmv_g:+.0%}" if gmv_g is not None else f"，前窗 {gmv_prev}"
        parts.append(f"窗口销售额约 {gmv}{growth}")
    if orders is not None:
        parts.append(f"订单 {orders}")
    if clicks is not None:
        cg = f"，{click_g:+.0%}" if click_g is not None else ""
        prev = f"（前窗 {clicks_prev}）" if clicks_prev is not None else ""
        parts.append(f"昨日 UV {clicks}{prev}{cg}")
    rate = _rate_text(metrics)
    if rate:
        parts.append(rate)
    return "；".join(parts) or "快照销售字段不足，未写具体金额"


def _metrics(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("metrics")
    if isinstance(raw, dict) and raw:
        return raw
    excerpt = item.get("feature_excerpt")
    if isinstance(excerpt, dict) and excerpt:
        return excerpt
    # 兼容 Java score 投影直接落在行上的字段
    keys = (
        "gmv_30d",
        "gmv_prev_30d",
        "orders_30d",
        "orders_prev_30d",
        "clicks_30d",
        "clicks_prev_30d",
        "impressions_30d",
        "impressions_prev_30d",
        "paid_orders_from_clicks_30d",
        "rate_per",
        "ratePer",
        "amount_unit",
        "orderSales",
    )
    return {k: item.get(k) for k in keys if item.get(k) is not None}


def _growth(item: dict[str, Any], curr_key: str, prev_key: str) -> float | None:
    breakdown = item.get("score_breakdown") or {}
    if curr_key == "gmv_30d":
        raw = (breakdown.get("sales_growth") or {}).get("raw_growth")
        if isinstance(raw, (int, float)):
            return float(raw)
    if curr_key == "clicks_30d":
        raw = (breakdown.get("traffic_growth") or {}).get("raw_growth")
        if isinstance(raw, (int, float)):
            return float(raw)
    metrics = _metrics(item)
    curr = metrics.get(curr_key)
    prev = metrics.get(prev_key)
    try:
        if curr is None or prev is None:
            return None
        prev_f = float(prev)
        if prev_f == 0:
            return None
        return (float(curr) - prev_f) / abs(prev_f)
    except (TypeError, ValueError):
        return None


def _money(value: Any, *, yuan: bool = False) -> str:
    """运营接口金额按元；内部快照默认按分。"""
    if value is None:
        return "未知"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "未知"
    if not yuan:
        amount = amount / 100.0
    if amount >= 100:
        return f"{amount:,.0f} 元"
    return f"{amount:,.2f} 元"
