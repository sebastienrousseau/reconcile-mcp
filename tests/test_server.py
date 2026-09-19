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
import json

import pytest

pytest.importorskip("mcp")

import reconcile_mcp._mcp_compat as compat  # noqa: E402
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
    "match_names_probabilistic",
    "match_amounts_with_fx_drift",
    "reconcile_many_to_many",
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
    assert compat.server_version(srv.server) == __version__


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


def test_match_names_probabilistic_tool_happy_and_error():
    ok = srv.match_names_probabilistic("ACME Corp", "ACME Corporation Inc")
    assert ok["is_match"] is True
    err = srv.match_names_probabilistic("a", "b", threshold=2.0)
    assert "error" in err


def test_match_amounts_with_fx_drift_tool_happy_and_error():
    ok = srv.match_amounts_with_fx_drift(100.0, "USD", 92.50, "EUR", 1.08)
    assert ok["is_match"] is True
    err = srv.match_amounts_with_fx_drift(100.0, "USD", 92.5, "EUR", 0.0)
    assert "error" in err


def test_reconcile_many_to_many_tool_happy_and_error():
    invoices = [{"id": f"INV{i}", "amount": str(2**i)} for i in range(6)]
    # 4 + 32 == INV2 + INV5 sums to the deposit; superincreasing amounts make
    # that the only subset that can hit 36.
    ok = srv.reconcile_many_to_many([{"id": "DEP1", "amount": "36"}], invoices)
    assert ok["matches"][0]["invoices"] == ["INV2", "INV5"]
    err = srv.reconcile_many_to_many([{"id": "bad"}], invoices)
    assert "error" in err


def test_reconcile_workflow_prompt_registered():
    names = {p.name for p in srv.server._prompt_manager.list_prompts()}
    assert "reconcile_workflow" in names


def test_reconcile_workflow_prompt_generic_branch():
    out = srv.reconcile_workflow()
    assert "normalize_pain001" in out
    assert "normalize_camt053" in out
    assert "reconcile" in out
    assert "explain_match" in out
    assert "list_sandbox_scenarios" in out


def test_reconcile_workflow_prompt_scenario_branch():
    out = srv.reconcile_workflow("clean_match")
    assert "run_sandbox_scenario" in out
    assert "'clean_match'" in out
    assert "load_sandbox_scenario" in out


def test_sandbox_scenarios_resource_registered():
    uris = {str(r.uri) for r in srv.server._resource_manager.list_resources()}
    assert "reconcile://sandbox-scenarios" in uris


def test_sandbox_scenario_template_registered():
    templates = {
        t.uri_template for t in srv.server._resource_manager.list_templates()
    }
    assert "reconcile://sandbox/{scenario_id}" in templates


def test_sandbox_scenarios_resource_body():
    out = json.loads(srv.sandbox_scenarios_resource())
    assert any(s["name"] == "clean_match" for s in out["scenarios"])
    assert "SANDBOX-EXACT" in out["magic_references"]


def test_sandbox_scenario_resource_happy():
    out = json.loads(srv.sandbox_scenario_resource("clean_match"))
    assert out["name"] == "clean_match"
    assert out["expected"] and out["observed"]


def test_sandbox_scenario_resource_error():
    out = json.loads(srv.sandbox_scenario_resource("nope"))
    assert "error" in out


def test_main_runs_server(monkeypatch):
    """``main([])`` delegates to the server's ``run`` over stdio."""
    called = {}
    monkeypatch.setattr(
        srv.server, "run", lambda: called.setdefault("ran", True)
    )
    srv.main([])
    assert called["ran"] is True
