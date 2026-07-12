# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the reconcile MCP server tool surface."""

import asyncio

import pytest

pytest.importorskip("mcp")

import reconcile_mcp.server as srv  # noqa: E402
from reconcile_mcp import __version__  # noqa: E402

EXPECTED_TOOLS = {
    "reconcile",
    "explain_match",
    "normalize_pain001",
    "normalize_camt053",
    "list_sandbox_scenarios",
    "load_sandbox_scenario",
    "run_sandbox_scenario",
}


def _registered_tool_names() -> set[str]:
    manager = getattr(srv.server, "_tool_manager", None)
    if manager is not None and hasattr(manager, "list_tools"):
        return {tool.name for tool in manager.list_tools()}
    tools = asyncio.run(srv.server.list_tools())  # pragma: no cover
    return {tool.name for tool in tools}  # pragma: no cover


def test_all_tools_registered():
    assert _registered_tool_names() == EXPECTED_TOOLS


def test_server_version_override():
    assert srv.server._mcp_server.version == __version__


def test_reconcile_tool_happy_and_error():
    ok = srv.reconcile(
        [{"id": "INV1", "amount": "100", "reference": "INV1"}],
        [{"id": "E1", "amount": "100", "reference": "INV1"}],
    )
    assert ok["matches"][0]["type"] == "exact"
    err = srv.reconcile([{"id": "bad"}], [])
    assert "error" in err


def test_explain_match_tool_happy_and_error():
    ok = srv.explain_match(
        {"id": "INV1", "amount": "100", "reference": "INV1"},
        {"id": "E1", "amount": "100", "reference": "INV1"},
    )
    assert ok["signals"]["reference"] == 1.0
    err = srv.explain_match({"id": "x"}, {"id": "y", "amount": "1"})
    assert "error" in err


def test_normalize_pain001_tool_happy_and_error():
    ok = srv.normalize_pain001([{"end_to_end_id": "E", "amount": "1"}])
    assert ok["expected"][0]["id"] == "E"
    err = srv.normalize_pain001("bad")
    assert "error" in err


def test_normalize_camt053_tool_happy_and_error():
    ok = srv.normalize_camt053([{"id": "N", "amount": "1"}])
    assert ok["observed"][0]["id"] == "N"
    err = srv.normalize_camt053({"nope": 1})
    assert "error" in err


def test_list_sandbox_scenarios_tool():
    out = srv.list_sandbox_scenarios()
    assert any(s["name"] == "clean_match" for s in out["scenarios"])
    assert "SANDBOX-EXACT" in out["magic_references"]


def test_load_sandbox_scenario_tool_happy_and_error():
    ok = srv.load_sandbox_scenario("clean_match")
    assert ok["expected"] and ok["observed"]
    err = srv.load_sandbox_scenario("nope")
    assert "error" in err


def test_run_sandbox_scenario_tool_happy_and_error():
    ok = srv.run_sandbox_scenario("clean_match")
    assert ok["summary"]["fully_reconciled"] is True
    assert ok["scenario"]["name"] == "clean_match"
    err = srv.run_sandbox_scenario("nope")
    assert "error" in err


def test_main_runs_server(monkeypatch):
    called = {}
    monkeypatch.setattr(
        srv.server, "run", lambda: called.setdefault("ran", True)
    )
    srv.main()
    assert called["ran"] is True
