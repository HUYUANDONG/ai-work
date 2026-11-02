"""报表：LLM 生成带 Chart.js 的 HTML；无 Key 时模板降级；供前端下载。"""

from reporting.builder import build_download_contract, build_explosion_report

__all__ = ["build_explosion_report", "build_download_contract"]

