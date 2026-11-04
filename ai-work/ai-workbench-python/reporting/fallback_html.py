"""
无 LLM 时的降级 HTML：同样用 Chart.js + 锁定 JSON，保证可下载可打开。
"""

from __future__ import annotations

import html
import json
from typing import Any


def render_fallback_html(locked_payload: dict[str, Any]) -> str:
    """
    模板 HTML（Chart.js CDN），数据来自 locked_payload。

    Args:
        locked_payload: 与给 LLM 相同的锁定数据。

    Returns:
        str: 完整 HTML。
    """
    candidates = locked_payload.get("candidates") or []
    labels = [str(c.get("sku_id") or "") for c in candidates]
    scores = [float(c.get("explosion_score") or 0) for c in candidates]
    risk_counts: dict[str, int] = {}
    for c in candidates:
        k = str(c.get("quality_risk_level") or "NONE")
        risk_counts[k] = risk_counts.get(k, 0) + 1

    rows = []
    for c in candidates:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(c.get('rank', '')))}</td>"
            f"<td>{html.escape(str(c.get('sku_id', '')))}</td>"
            f"<td>{html.escape(str(c.get('title', '')))}</td>"
            f"<td>{html.escape(str(c.get('explosion_score', '')))}</td>"
            f"<td>{html.escape(str(c.get('quality_risk_level', '')))}</td>"
            f"<td>{html.escape(str(c.get('action_bucket', '')))}</td>"
            f"<td>{html.escape(', '.join(c.get('quality_rule_ids') or []))}</td>"
            "</tr>"
        )

    labels_js = json.dumps(labels, ensure_ascii=False)
    scores_js = json.dumps(scores)
    risk_labels_js = json.dumps(list(risk_counts.keys()), ensure_ascii=False)
    risk_values_js = json.dumps(list(risk_counts.values()))

    bucket_label = {
        "PUSH": "本周可主推",
        "FIX_THEN_PUSH": "先修再冲",
        "WATCH": "观察一周",
        "DROP": "暂不主推",
    }
    tips = []
    for c in candidates[:8]:
        risk = c.get("quality_risk_level") or "NONE"
        bucket = str(c.get("action_bucket") or "WATCH")
        title = html.escape(str(c.get("title") or c.get("sku_id") or ""))
        slot = "进槽" if c.get("in_focus_slot") else "未进槽"
        action = html.escape(str(c.get("primary_action") or bucket_label.get(bucket, bucket)))
        tips.append(
            f"<li><strong>#{c.get('rank')} {title}</strong>"
            f"（{html.escape(str(c.get('sku_id')))}）："
            f"分 {html.escape(str(c.get('explosion_score')))}，风险 {html.escape(str(risk))}，"
            f"{html.escape(bucket_label.get(bucket, bucket))}（{slot}）。{action}</li>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>爆品分析报表 {html.escape(str(locked_payload.get('task_id', '')))}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f1f5f9; }}
    .meta {{ color: #64748b; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>爆品分析报表</h1>
    <p class="meta">
      task_id={html.escape(str(locked_payload.get('task_id')))} ·
      snapshot={html.escape(str(locked_payload.get('snapshot_date')))} ·
      scoring={html.escape(str(locked_payload.get('scoring_version')))} ·
      pool={html.escape(str(locked_payload.get('pool_size')))} ·
      分析来源=template（未调用 LLM）
    </p>
  </div>
  <div class="card">
    <h2>本周结论</h2>
    <ul>{''.join(tips)}</ul>
    <p class="meta">配置 WB_LLM_API_KEY 后可由大模型生成更完整的页面叙事与排版。</p>
  </div>
  <div class="card">
    <h2>图表</h2>
    <div class="grid">
      <div><canvas id="scoreChart"></canvas></div>
      <div><canvas id="riskChart"></canvas></div>
    </div>
  </div>
  <div class="card">
    <h2>候选明细</h2>
    <table>
      <thead><tr><th>排名</th><th>SKU</th><th>标题</th><th>爆品分</th><th>风险</th><th>动作</th><th>规则</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
  <script>
    const labels = {labels_js};
    const scores = {scores_js};
    const riskLabels = {risk_labels_js};
    const riskValues = {risk_values_js};
    new Chart(document.getElementById('scoreChart'), {{
      type: 'bar',
      data: {{ labels, datasets: [{{ label: 'explosion_score', data: scores, backgroundColor: '#3B82F6' }}] }},
      options: {{ indexAxis: 'y', scales: {{ x: {{ min: 0, max: 100 }} }} }}
    }});
    new Chart(document.getElementById('riskChart'), {{
      type: 'doughnut',
      data: {{ labels: riskLabels, datasets: [{{ data: riskValues, backgroundColor: ['#94A3B8','#38BDF8','#FBBF24','#F87171'] }}] }}
    }});
  </script>
</body>
</html>
"""

