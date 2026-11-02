"""报表文件写入。"""

from __future__ import annotations

from pathlib import Path


def write_html_file(path: Path, content: str) -> Path:
    """
    写入 HTML 文件。

    Args:
        path: 目标路径。
        content: HTML 文本。

    Returns:
        Path: 写入后的路径。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path

