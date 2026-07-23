"""Tests for publish_to_dingtalk pure helpers."""

import pytest

from publish_to_dingtalk import (
    MCP_UPDATE_CHAR_LIMIT,
    build_href_to_data_uri_map,
    build_href_to_url_map,
    estimate_body_size,
    extract_upload_public_url,
    find_named_folder_node_id,
    find_weekly_doc_node_id,
    flatten_details_to_weekly_repo_links,
    iter_folder_nodes,
    parse_first_json_object,
    replace_markdown_image_hrefs,
    resolve_transport,
    split_at_local_images,
    split_markdown_chunks,
    strip_leading_duplicate_doc_title,
    weekly_report_repo_url,
)


def test_strip_leading_duplicate_doc_title_atx_and_blank():
    title = "【2026-05-17】AI Native 周报（预览版）"
    md = f"# {title}\n\n**收集周期**：\n"
    out = strip_leading_duplicate_doc_title(md, title)
    assert out == "**收集周期**：\n"


def test_strip_leading_duplicate_doc_title_whitespace_fuzzy():
    """钉钉/HTML 标题与 Markdown 仅空白差异时仍视为同一标题。"""
    md = "# 【2026-05-17】  AI Native   周报（预览版）\n\n正文\n"
    doc_title = "【2026-05-17】AI Native 周报（预览版）"
    out = strip_leading_duplicate_doc_title(md, doc_title)
    assert out == "正文\n"


def test_strip_leading_duplicate_doc_title_plain_line():
    out = strip_leading_duplicate_doc_title("周报标题\n\n下一段", "周报标题")
    assert out == "下一段"


def test_strip_leading_duplicate_doc_title_noop_when_differs():
    md = "# 其它标题\n\n正文\n"
    assert strip_leading_duplicate_doc_title(md, "【2026-05-17】周报") == md


def test_strip_leading_duplicate_doc_title_noop_empty_title():
    md = "# 标题\n"
    assert strip_leading_duplicate_doc_title(md, None) == md
    assert strip_leading_duplicate_doc_title(md, "") == md


def test_resolve_transport():
    assert resolve_transport(use_dws=True, use_mcp=True, mcp_servers=[{"k": "v"}]) == "dws"
    assert resolve_transport(use_dws=False, use_mcp=True, mcp_servers=[]) == "mcp"
    assert resolve_transport(use_dws=False, use_mcp=False, mcp_servers=[{"k": "v"}]) == "mcp"
    assert resolve_transport(use_dws=False, use_mcp=False, mcp_servers=[]) == "dws"


def test_parse_first_json_object_with_log_prefix():
    raw = "[INFO] hello\n{\"a\": 1, \"b\": 2}\n"
    assert parse_first_json_object(raw) == {"a": 1, "b": 2}


def test_parse_first_json_object_nested():
    s = 'prefix {"x": true}'
    assert parse_first_json_object(s) == {"x": True}


def test_parse_first_json_object_raises():
    with pytest.raises(ValueError):
        parse_first_json_object("no json here")


def test_iter_folder_nodes_top_level_nodes():
    payload = {
        "nodes": [
            {"nodeId": "a1", "name": "【2026-05-17】周报"},
            {"nodeId": "b2", "title": "other"},
        ]
    }
    assert len(iter_folder_nodes(payload)) == 2


def test_iter_folder_nodes_result_nodes():
    payload = {"result": {"nodes": [{"nodeId": "n", "fileName": "x.md"}]}}
    assert len(iter_folder_nodes(payload)) == 1


def test_find_weekly_doc_node_id():
    payload = {
        "nodes": [
            {"nodeId": "old", "name": "【2026-05-10】AI Native 周报"},
            {"nodeId": "nid", "title": "【2026-05-17】AI Native 周报（预览版）"},
        ]
    }
    assert find_weekly_doc_node_id(payload, "2026-05-17") == "nid"
    assert find_weekly_doc_node_id(payload, "2026-05-99") is None


def test_extract_upload_public_url_doc_url():
    j = {"success": True, "docUrl": "https://alidocs.dingtalk.com/i/nodes/abc"}
    assert extract_upload_public_url(j) == "https://alidocs.dingtalk.com/i/nodes/abc"


def test_extract_upload_public_url_priority():
    j = {
        "docUrl": "https://alidocs.dingtalk.com/a",
        "downloadUrl": "https://cdn.example.com/b.png",
    }
    assert extract_upload_public_url(j) == "https://cdn.example.com/b.png"


def test_find_named_folder_node_id():
    payload = {
        "nodes": [
            {"nodeId": "f1", "name": "周报配图-2026-05-17", "nodeType": "folder"},
            {"nodeId": "x", "name": "周报配图-2026-05-17", "nodeType": "file"},
        ]
    }
    assert find_named_folder_node_id(payload, "周报配图-2026-05-17") == "f1"


def test_build_href_to_data_uri_map(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    images = [{"href": "rel/a.png", "path": str(png)}]
    m = build_href_to_data_uri_map(images)
    assert "rel/a.png" in m
    assert m["rel/a.png"].startswith("data:image/png;base64,")


def test_build_href_to_url_map():
    images = [{"href": "a.png", "path": "/x/a.png"}, {"href": "b.png", "path": "/x/b.png"}]
    uploads = [
        {"success": True, "docUrl": "https://alidocs.dingtalk.com/a"},
        {"success": True, "docUrl": "https://alidocs.dingtalk.com/b"},
    ]
    m = build_href_to_url_map(images, uploads)
    assert m == {"a.png": "https://alidocs.dingtalk.com/a", "b.png": "https://alidocs.dingtalk.com/b"}


def test_build_href_to_url_map_prefers_download_url():
    images = [{"href": "a.png", "path": "/x/a.png"}]
    uploads = [
        {
            "success": True,
            "docUrl": "https://alidocs.dingtalk.com/doc",
            "downloadUrl": "https://cdn.example.com/a.png",
        }
    ]
    assert build_href_to_url_map(images, uploads)["a.png"] == "https://cdn.example.com/a.png"


def test_build_href_to_url_map_length_mismatch():
    with pytest.raises(ValueError):
        build_href_to_url_map([{"href": "a", "path": "p"}], [])


def test_replace_markdown_image_hrefs():
    md = "![t](token-metrics/a.png)\n![m](token-metrics/b.png)"
    m = {
        "token-metrics/b.png": "https://u/b",
        "token-metrics/a.png": "https://u/a",
    }
    got = replace_markdown_image_hrefs(md, m)
    assert "https://u/a" in got and "https://u/b" in got
    assert "token-metrics/" not in got


def test_weekly_report_repo_url():
    u = weekly_report_repo_url("2026-05-10")
    assert u.endswith("/weekly/2026-05-10/weekly-report.md")
    assert "code.alibaba-inc.com" in u


def test_flatten_details_to_weekly_repo_links():
    end = "2026-05-10"
    want = weekly_report_repo_url(end)
    md = """intro

<details>
<summary>更多动态（共 8 篇）</summary>

* **hidden**

</details>

tail"""
    out = flatten_details_to_weekly_repo_links(md, end)
    assert "<details" not in out.lower()
    assert "* **hidden**" not in out
    assert f"[更多动态（共 8 篇）]({want})" in out
    assert "intro" in out and "tail" in out


def test_flatten_details_case_insensitive_and_no_summary():
    end = "2026-01-01"
    want = weekly_report_repo_url(end)
    md = "<DETAILS>\n<p>only body</p>\n</DETAILS>"
    out = flatten_details_to_weekly_repo_links(md, end)
    assert f"[查看完整内容]({want})" == out


def test_flatten_details_escapes_brackets_in_summary_label():
    end = "2026-01-01"
    want = weekly_report_repo_url(end)
    md = "<details><summary>a [b] c</summary>\nx\n</details>"
    out = flatten_details_to_weekly_repo_links(md, end)
    assert f"[a \\[b\\] c]({want})" in out


def test_estimate_body_size_no_images(tmp_path):
    assert estimate_body_size(markdown="hello", images=[]) == 5


def test_estimate_body_size_with_one_image(tmp_path):
    png = tmp_path / "x.png"
    png.write_bytes(b"\x00" * 100)  # 100 bytes
    images = [{"href": "x.png", "path": str(png)}]
    # markdown 5 + data URI prefix (~20) + base64 (~136) = ~161
    got = estimate_body_size(markdown="hello", images=images)
    assert got > 150  # at least the image contribution


def test_estimate_body_size_nonexistent_file_skipped(tmp_path):
    images = [{"href": "missing.png", "path": str(tmp_path / "does_not_exist.png")}]
    assert estimate_body_size(markdown="hello", images=images) == 5


def test_estimate_body_size_missing_path_skipped(tmp_path):
    images = [{"href": "a.png", "path": ""}]
    assert estimate_body_size(markdown="hello", images=images) == 5


def test_estimate_body_size_multiple_images(tmp_path):
    img1 = tmp_path / "a.png"
    img2 = tmp_path / "b.png"
    img1.write_bytes(b"\x00" * 1000)
    img2.write_bytes(b"\x00" * 2000)
    images = [
        {"href": "a.png", "path": str(img1)},
        {"href": "b.png", "path": str(img2)},
    ]
    got = estimate_body_size(markdown="hello", images=images)
    # Two images: ~1360 + ~2688 base64 chars + 2x prefix + 5 markdown
    assert got > 4000


def test_mcp_update_char_limit_reasonable():
    """MCP 限制应在合理范围内（>5k 且 <50k）。"""
    assert 5_000 < MCP_UPDATE_CHAR_LIMIT < 50_000


def test_split_markdown_chunks_under_limit():
    md = "short text"
    assert split_markdown_chunks(md, 100) == [md]


def test_split_markdown_chunks_exact_limit():
    md = "a\nb\nc"
    assert split_markdown_chunks(md, len(md)) == [md]


def test_split_markdown_chunks_splits_at_line_boundary():
    lines = [f"line-{i}: " + "x" * 40 for i in range(10)]
    md = "\n".join(lines)
    chunks = split_markdown_chunks(md, 200)
    assert len(chunks) >= 2
    reassembled = "\n".join(chunks)
    assert reassembled == md


def test_split_markdown_chunks_preserves_image_positions():
    parts = [
        "# Title\n\nIntro text here.",
        "![chart](https://example.com/img1.png)",
        "More text after image.",
        "![chart2](https://example.com/img2.png)",
        "Final paragraph.",
    ]
    md = "\n".join(parts)
    chunks = split_markdown_chunks(md, 80)
    reassembled = "\n".join(chunks)
    assert reassembled == md
    assert "![chart]" in reassembled
    assert "![chart2]" in reassembled


def test_split_at_local_images_basic():
    md = "text1\n![a](local.png)\ntext2\n![b](remote.png)\ntext3"
    segs = split_at_local_images(md, {"local.png"})
    assert segs == ["text1\n", ("a", "local.png"), "\ntext2\n![b](remote.png)\ntext3"]


def test_split_at_local_images_multiple():
    md = "intro\n![x](a.png)\nmid\n![y](b.png)\nend"
    segs = split_at_local_images(md, {"a.png", "b.png"})
    assert len(segs) == 5
    assert segs[0] == "intro\n"
    assert segs[1] == ("x", "a.png")
    assert segs[2] == "\nmid\n"
    assert segs[3] == ("y", "b.png")
    assert segs[4] == "\nend"


def test_split_at_local_images_no_match():
    md = "no images here"
    segs = split_at_local_images(md, {"x.png"})
    assert segs == ["no images here"]


def test_split_at_local_images_empty_hrefs():
    md = "![a](x.png)"
    segs = split_at_local_images(md, set())
    assert segs == ["![a](x.png)"]
