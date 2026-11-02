"""
让 LLM 根据锁定数据生成带 Chart.js 图表的完整 HTML 报表。

图表数字必须来自传入 JSON，禁止模型改分或编造 SKU。
"""

from __future__ import annotations

import json
import re
from typing import Any

from clients.llm_client import LlmClient

SYSTEM_PROMPT = """你是前端报表生成器。根据用户提供的 JSON（代码已算好的爆品候选）输出一整份完整 HTML5 文档。

硬性要求：
1. 只输出 HTML（可从 <!DOCTYPE html> 开始），不要 Markdown，不要用 ``` 包裹。
2. 所有 explosion_score、quality_risk_level、quality_rule_ids、rank、sku_id、标题必须与 JSON 完全一致，禁止改数、禁止增删候选。
3. 页面需包含：
   - 标题与元信息（task_id、snapshot_date、scoring_version、pool_size）
   - 分析结论（3～5 条可执行建议；高分高风险要写「先修再冲」）
   - 图表（使用 CDN 引入 Chart.js，不要用图片链接）：
     a) 横向/纵向柱状图：各 SKU 的 explosion_score
     b) 饼图或环形图：quality_risk_level 分布（NONE/LOW/MID/HIGH）
   - 候选明细表格（排名、SKU、标题、爆品分、风险、规则）
4. 图表数据必须从 JSON 的 candidates 原样写入 JS 数组，兼容现代浏览器。
5. 中文界面，样式简洁可读，可单文件离线打开（Chart.js 可用 jsDelivr CDN）。
6. 不要输出与数据无关的营销废话。
"""


def _strip_fences(text: str) -> str:
    """去掉模型可能包的 ```html 围栏。"""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:html|HTML)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _looks_like_html(text: str) -> bool:
    low = text.lower()
    return "<html" in low or "<!doctype html" in low


async def generate_report_html_with_llm(
    llm: LlmClient,
    locked_payload: dict[str, Any],
) -> str:
    """
    调用 LLM 生成完整 HTML。

    Args:
        llm: 已启用的客户端。
        locked_payload: 锁定的报表数据（含 candidates）。

    Returns:
        str: HTML 文档。

    Raises:
        RuntimeError: 调用失败或结果不像 HTML。
    """
    user = (
        "请根据下列锁定 JSON 生成完整 HTML 报表（含 Chart.js 图表要求见系统提示）：\n"
        + json.dumps(locked_payload, ensure_ascii=False, indent=2)
    )
    raw = await llm.chat(system=SYSTEM_PROMPT, user=user)
    html = _strip_fences(raw)
    if not _looks_like_html(html):
        raise RuntimeError("LLM response is not HTML")
    return html

