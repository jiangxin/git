"""Tests for dingtalk_doc_mcp config normalization (no network)."""

import json
from pathlib import Path

import pytest

import dingtalk_doc_mcp as m


def test_normalize_base_url_and_key():
    s = m.normalize_mcp_server_entry(
        {"name": "a", "base_url": "https://mcp-gw.dingtalk.com/server/x", "key": "k1"}
    )
    assert s["base_url"] == "https://mcp-gw.dingtalk.com/server/x"
    assert s["key"] == "k1"


def test_normalize_split_url_and_key():
    s = m.normalize_mcp_server_entry(
        {
            "name": "default",
            "url": "https://mcp-gw.dingtalk.com/server/abc123",
            "key": "secret",
        }
    )
    assert s["base_url"] == "https://mcp-gw.dingtalk.com/server/abc123"
    assert s["key"] == "secret"


def test_normalize_full_mcp_url_with_query():
    s = m.normalize_mcp_server_entry(
        {
            "name": "x",
            "url": "https://mcp-gw.dingtalk.com/server/abc?key=qqq",
        }
    )
    assert s["base_url"] == "https://mcp-gw.dingtalk.com/server/abc"
    assert s["key"] == "qqq"


def test_normalize_rejects_invalid():
    with pytest.raises(ValueError):
        m.normalize_mcp_server_entry({"url": "https://example.com/foo"})


def test_load_mcp_servers_from_file(tmp_path):
    cfg = tmp_path / "servers.json"
    cfg.write_text(
        json.dumps(
            {
                "mcp_servers": [
                    {
                        "name": "default",
                        "url": "https://mcp-gw.dingtalk.com/server/sid",
                        "key": "kk",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    servers = m.load_mcp_servers(cfg)
    assert len(servers) == 1
    assert servers[0]["key"] == "kk"


def test_extract_node_id():
    assert m.extract_node_id("EpGBa2Lm8aZxe5myCE5qpajGWgN7R35y") == "EpGBa2Lm8aZxe5myCE5qpajGWgN7R35y"
    assert (
        m.extract_node_id("https://alidocs.dingtalk.com/i/nodes/EpGBa2Lm8aZxe5myCE5qpajGWgN7R35y")
        == "EpGBa2Lm8aZxe5myCE5qpajGWgN7R35y"
    )


def test_extract_node_id_from_doc_result():
    assert m.extract_node_id_from_doc_result({"nodeId": "n1"}) == "n1"
    assert m.extract_node_id_from_doc_result({"dentryUuid": "d2"}) == "d2"
    assert m.extract_node_id_from_doc_result({}) == ""
