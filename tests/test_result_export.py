"""结果导出功能测试（2.1.13 验收第 6 条：导出结果文件并重新下载）。

先测纯函数行为（导出目录规范 + Markdown 写入），再测幂等性。
"""
from __future__ import annotations

from app.domains.result.export import write_export_markdown


def test_write_export_markdown_creates_file_under_exports_dir(tmp_path):
    path = write_export_markdown(
        tmp_path, user_id="u1", conversation_id="c1", result_id="r123",
        markdown="# 经营归因分析\n\n结论：信息流点击下滑主因为素材更换。",
    )

    assert path == tmp_path / "u1" / "c1" / "attribution_r123.md"
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == "# 经营归因分析\n\n结论：信息流点击下滑主因为素材更换。"


def test_write_export_markdown_is_idempotent(tmp_path):
    p1 = write_export_markdown(tmp_path, "u1", "c1", "r1", "版本一")
    p2 = write_export_markdown(tmp_path, "u1", "c1", "r1", "版本二")

    assert p1 == p2
    assert p2.read_text(encoding="utf-8") == "版本二"


def test_write_export_markdown_creates_parent_dirs(tmp_path):
    path = write_export_markdown(
        tmp_path / "exports", "u-001", "c-002", "r-003", "content"
    )
    assert path.parent == tmp_path / "exports" / "u-001" / "c-002"
    assert path.is_file()
