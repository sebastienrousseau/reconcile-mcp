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

"""Tests for the sandbox fixtures and that each demonstrates its outcome."""

import pytest

from reconcile_mcp import engine, sandbox


def test_list_scenarios_shape():
    rows = sandbox.list_scenarios()
    names = {r["name"] for r in rows}
    assert {"clean_match", "short_payment", "split_settlement"} <= names
    for row in rows:
        assert row["description"] and row["demonstrates"]


def test_load_scenario_unknown_raises():
    with pytest.raises(ValueError, match="unknown sandbox scenario"):
        sandbox.load_scenario("does_not_exist")


def test_load_scenario_returns_copies():
    a = sandbox.load_scenario("clean_match")
    a["expected"][0]["amount"] = "999999"
    b = sandbox.load_scenario("clean_match")
    assert b["expected"][0]["amount"] != "999999"


@pytest.mark.parametrize(
    "name,expected_type",
    [
        ("clean_match", "exact"),
        ("short_payment", "amount_mismatch"),
        ("split_settlement", "one_to_many"),
        ("batch_credit", "many_to_one"),
    ],
)
def test_each_scenario_demonstrates_its_type(name, expected_type):
    scenario = sandbox.load_scenario(name)
    report = engine.reconcile(scenario["expected"], scenario["observed"])
    types = {m["type"] for m in report["matches"]}
    assert expected_type in types


def test_fx_mismatch_scenario_stays_unmatched():
    scenario = sandbox.load_scenario("fx_mismatch")
    report = engine.reconcile(scenario["expected"], scenario["observed"])
    assert report["summary"]["unmatched_expected"] == 1
    assert report["summary"]["unmatched_observed"] == 1


def test_month_end_scenario_is_mixed():
    scenario = sandbox.load_scenario("month_end")
    report = engine.reconcile(scenario["expected"], scenario["observed"])
    types = {m["type"] for m in report["matches"]}
    # A clean match, a short payment and a split all appear together.
    assert {"exact", "amount_mismatch", "one_to_many"} <= types
    # The unexpected credit (ENT-55) has no expected counterpart.
    assert "ENT-55" in report["unmatched_observed"]


def test_magic_references_documented():
    assert "SANDBOX-EXACT" in sandbox.MAGIC_REFERENCES
    assert all(sandbox.MAGIC_REFERENCES.values())
