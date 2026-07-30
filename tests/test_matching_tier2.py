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

"""Known-answer tests for the Tier-2 matching engine (caps 21-23)."""

import pytest

from reconcile_mcp import engine

# --- Cap 21: Jaro-Winkler name matching -------------------------------------


def test_jaro_winkler_matches_legal_suffix_drift():
    out = engine.match_names_probabilistic("ACME Corp", "ACME Corporation Inc")
    # Known Jaro-Winkler value for this pair is ~0.89, comfortably >= 0.85.
    assert out["similarity_score"] >= 0.85
    assert out["is_match"] is True


def test_jaro_winkler_rejects_unrelated_names():
    out = engine.match_names_probabilistic("ACME Corp", "Globex Industries")
    assert out["similarity_score"] < 0.85
    assert out["is_match"] is False


def test_jaro_winkler_invalid_threshold_raises():
    with pytest.raises(ValueError, match=r"threshold must be within"):
        engine.match_names_probabilistic("a", "b", threshold=1.5)


# --- Cap 22: FX-aware amount matching ---------------------------------------


def test_fx_drift_within_tolerance_matches():
    # 100 USD converted to EUR at 1.08 USD/EUR is 92.59, ~0.1% from 92.50 EUR.
    out = engine.match_amounts_with_fx_drift(100.0, "USD", 92.50, "EUR", 1.08)
    assert out["converted_amount"] == "92.59"
    assert out["difference_pct"] < 1.0
    assert out["is_match"] is True


def test_fx_drift_outside_tolerance_rejects():
    out = engine.match_amounts_with_fx_drift(100.0, "USD", 50.0, "EUR", 1.08)
    assert out["difference_pct"] > 1.0
    assert out["is_match"] is False


def test_fx_drift_non_positive_rate_raises():
    with pytest.raises(ValueError, match="fx_rate must be positive"):
        engine.match_amounts_with_fx_drift(100.0, "USD", 92.5, "EUR", 0.0)


# --- Cap 23: many-to-many subset-sum reconciliation -------------------------


def _superincreasing_invoices(count: int) -> list[dict[str, str]]:
    """Powers of two make every subset sum unique (binary encoding)."""
    return [{"id": f"INV{i}", "amount": str(2**i)} for i in range(count)]


def test_ilp_finds_the_unique_three_invoice_subset():
    invoices = _superincreasing_invoices(10)
    # 8 + 64 + 256 == 328 -> INV3, INV6, INV8, the only subset that hits 328.
    out = engine.reconcile_many_to_many(
        [{"id": "DEP1", "amount": "328"}], invoices
    )
    assert len(out["matches"]) == 1
    match = out["matches"][0]
    assert match["statement"] == "DEP1"
    assert match["invoices"] == ["INV3", "INV6", "INV8"]
    assert match["invoices_total"] == "328"
    assert match["residual"] == "0"
    assert out["unmatched_statements"] == []
    # The seven invoices not in the winning subset stay unmatched.
    assert set(out["unmatched_invoices"]) == {
        "INV0",
        "INV1",
        "INV2",
        "INV4",
        "INV5",
        "INV7",
        "INV9",
    }


def test_ilp_impossible_target_is_unmatched():
    invoices = _superincreasing_invoices(10)
    out = engine.reconcile_many_to_many(
        [{"id": "DEP1", "amount": "1000000"}], invoices
    )
    assert out["matches"] == []
    assert out["unmatched_statements"] == ["DEP1"]
    assert len(out["unmatched_invoices"]) == 10


def test_ilp_empty_invoice_pool_is_unmatched():
    out = engine.reconcile_many_to_many([{"id": "DEP1", "amount": "5"}], [])
    assert out["matches"] == []
    assert out["unmatched_statements"] == ["DEP1"]
    assert out["unmatched_invoices"] == []


def test_ilp_bad_record_raises():
    with pytest.raises(ValueError):
        engine.reconcile_many_to_many([{"id": "DEP1"}], [])


def test_ilp_graceful_fallback_when_scipy_missing(monkeypatch):
    def _boom():
        raise ImportError("no scipy here")

    monkeypatch.setattr(engine, "_import_ilp", _boom)
    out = engine.reconcile_many_to_many(
        [{"id": "DEP1", "amount": "5"}],
        [{"id": "INV0", "amount": "5"}],
    )
    assert out == {
        "error": "ILP solver unavailable; pip install reconcile-mcp[ilp]"
    }
