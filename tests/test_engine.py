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

"""Unit tests for the reconciliation engine."""

from datetime import date
from decimal import Decimal

import pytest

from reconcile_mcp import engine

# --- Coercion ---------------------------------------------------------------


def test_to_decimal_variants():
    assert engine._to_decimal(None) is None
    assert engine._to_decimal("") is None
    assert engine._to_decimal(Decimal("1.5")) == Decimal("1.5")
    assert engine._to_decimal(2) == Decimal("2")
    assert engine._to_decimal(0.1) == Decimal("0.1")
    assert engine._to_decimal("3.25") == Decimal("3.25")
    assert engine._to_decimal("not-a-number") is None


def test_to_date_variants():
    assert engine._to_date(None) is None
    assert engine._to_date("") is None
    assert engine._to_date(date(2026, 3, 2)) == date(2026, 3, 2)
    assert engine._to_date("2026-03-02T10:00:00") == date(2026, 3, 2)
    assert engine._to_date("nonsense") is None


def test_to_item_requires_id_and_amount():
    with pytest.raises(ValueError, match="non-empty 'id'"):
        engine.to_item({"amount": "10"})
    with pytest.raises(ValueError, match="non-numeric 'amount'"):
        engine.to_item({"id": "X", "amount": "abc"})


def test_to_item_full_and_fallbacks():
    item = engine.to_item(
        {
            "id": "A1",
            "amount": "100.00",
            "currency": "eur",
            "value_date": "2026-03-02",
            "counterparty": "Acme",
            "reference": "INV1",
            "counterparty_account": "DE00",
        }
    )
    assert item.currency == "EUR"
    assert item.value_date == date(2026, 3, 2)
    assert item.account == "DE00"
    # 'date' key preferred over 'value_date'; 'account' preferred over the
    # counterparty_account fallback.
    item2 = engine.to_item(
        {"id": "A2", "amount": 1, "date": "2026-01-01", "account": "GB00"}
    )
    assert item2.value_date == date(2026, 1, 1)
    assert item2.account == "GB00"


# --- Options ----------------------------------------------------------------


def test_options_from_dict_defaults_and_overrides():
    assert engine.Options.from_dict(None).currency_strict is True
    opts = engine.Options.from_dict(
        {
            "abs_tol": "0.05",
            "rel_tol": "0.01",
            "date_window_days": 3,
            "high_threshold": 0.9,
            "review_threshold": 0.6,
            "currency_strict": False,
            "enable_one_to_many": False,
            "max_combination": 4,
        }
    )
    assert opts.abs_tol == Decimal("0.05")
    assert opts.currency_strict is False
    assert opts.max_combination == 4


def test_options_invalid_tolerance_falls_back_to_zero():
    opts = engine.Options.from_dict({"abs_tol": "junk", "rel_tol": ""})
    assert opts.abs_tol == Decimal(0)
    assert opts.rel_tol == Decimal(0)


# --- Signal scoring ---------------------------------------------------------


def _item(**kw):
    base = {"id": "x", "amount": Decimal("100")}
    base.update(kw)
    return engine.Item(**base)


def test_reference_similarity():
    o = engine.Options()
    assert (
        engine.reference_similarity(_item(reference=""), _item(id="")) == 0.0
    )
    # exact overlap
    assert (
        engine.reference_similarity(
            _item(reference="INV-1"), _item(reference="inv1")
        )
        == 1.0
    )
    # containment, both >= 6 chars (distinct ids so only the reference counts)
    assert (
        engine.reference_similarity(
            _item(id="p", reference="ABCDEFGH"),
            _item(id="q", reference="XXABCDEFGHYY"),
        )
        == 0.8
    )
    # no overlap
    assert (
        engine.reference_similarity(
            _item(id="p", reference="AAAAAA"),
            _item(id="q", reference="BBBBBB"),
        )
        == 0.0
    )
    assert o  # touch


def test_amount_similarity_exact_close_and_zero():
    o = engine.Options()
    s, d, within = engine.amount_similarity(
        _item(amount=Decimal("100")), _item(amount=Decimal("100")), o
    )
    assert within and s == 1.0 and d == 0
    # close but outside tolerance -> decayed signal, overpaid delta
    s, d, within = engine.amount_similarity(
        _item(amount=Decimal("100")), _item(amount=Decimal("110")), o
    )
    assert not within and 0 < s < 1 and d == Decimal("10")
    # expected zero, non-zero delta -> zero signal via the ref==0 guard
    s, d, within = engine.amount_similarity(
        _item(amount=Decimal("0")), _item(amount=Decimal("5")), o
    )
    assert s == 0.0 and not within
    # huge miss -> signal floored at 0
    s, _, _ = engine.amount_similarity(
        _item(amount=Decimal("10")), _item(amount=Decimal("100")), o
    )
    assert s == 0.0


def test_amount_similarity_within_relative_tolerance():
    o = engine.Options(rel_tol=Decimal("0.05"))
    s, d, within = engine.amount_similarity(
        _item(amount=Decimal("100")), _item(amount=Decimal("104")), o
    )
    assert within and s == 1.0


def test_date_similarity():
    o = engine.Options(date_window_days=4)
    # unknown -> neutral
    assert engine.date_similarity(_item(), _item(), o) == 0.5
    a = _item(value_date=date(2026, 3, 2))
    b = _item(value_date=date(2026, 3, 4))
    assert engine.date_similarity(a, b, o) == pytest.approx(0.5)
    # beyond window
    c = _item(value_date=date(2026, 3, 20))
    assert engine.date_similarity(a, c, o) == 0.0
    # window<=0: exact only
    z = engine.Options(date_window_days=0)
    assert engine.date_similarity(a, a, z) == 1.0
    assert engine.date_similarity(a, b, z) == 0.0


def test_name_similarity():
    assert engine.name_similarity(_item(), _item()) == 0.5
    assert (
        engine.name_similarity(
            _item(counterparty="Acme Ltd"), _item(counterparty="acme ltd")
        )
        == 1.0
    )
    assert engine.name_similarity(
        _item(counterparty="Acme Ltd"), _item(counterparty="Acme Corp")
    ) == pytest.approx(1 / 3)


def test_score_pair_currency_clash_disqualifies():
    o = engine.Options()
    assert (
        engine.score_pair(_item(currency="EUR"), _item(currency="USD"), o)
        is None
    )


def test_score_pair_reasons_cover_every_branch():
    o = engine.Options(date_window_days=5)
    # reference partial (containment), amount close, date present, name partial
    cand = engine.score_pair(
        _item(
            id="p",
            reference="ABCDEFGH",
            amount=Decimal("100"),
            value_date=date(2026, 3, 2),
            counterparty="Acme Ltd",
        ),
        _item(
            id="q",
            reference="ZZABCDEFGHZZ",
            amount=Decimal("110"),
            value_date=date(2026, 3, 3),
            counterparty="Acme Corp",
        ),
        o,
    )
    assert "reference partial" in cand.reasons
    assert any(r.startswith("amount close") for r in cand.reasons)
    assert any(r.startswith("date +/-") for r in cand.reasons)
    assert "counterparty partial" in cand.reasons
    # reference exact + amount exact + counterparty exact
    cand2 = engine.score_pair(
        _item(reference="INV1", amount=Decimal("50"), counterparty="Acme"),
        _item(reference="INV1", amount=Decimal("50"), counterparty="Acme"),
        o,
    )
    assert "reference exact" in cand2.reasons
    assert "amount exact" in cand2.reasons
    assert "counterparty exact" in cand2.reasons
    # No dates on either side leaves the date signal neutral (0.5), so a
    # perfect reference+amount+name match caps at 0.95, not 1.0.
    assert cand2.score == 0.95


def test_confidence_buckets():
    o = engine.Options()
    assert engine._confidence(0.95, o) == "high"
    assert engine._confidence(0.6, o) == "medium"
    assert engine._confidence(0.1, o) == "low"


# --- Assignment: full reconcile ---------------------------------------------


def test_reconcile_exact_match():
    report = engine.reconcile(
        [
            {
                "id": "INV1",
                "amount": "100",
                "currency": "EUR",
                "reference": "INV1",
            }
        ],
        [
            {
                "id": "E1",
                "amount": "100",
                "currency": "EUR",
                "reference": "INV1",
            }
        ],
    )
    assert report["summary"]["fully_reconciled"] is True
    assert report["matches"][0]["type"] == "exact"


def test_reconcile_amount_mismatch():
    report = engine.reconcile(
        [{"id": "INV2", "amount": "1000", "reference": "INV2"}],
        [{"id": "E2", "amount": "950", "reference": "INV2"}],
    )
    m = report["matches"][0]
    assert m["type"] == "amount_mismatch"
    assert m["amount_delta"] == "-50"


def test_reconcile_probable_match():
    # Amount exact + counterparty exact + same-day, but no reference: the score
    # clears review yet stays below high, so it is a probable (not exact) match.
    report = engine.reconcile(
        [
            {
                "id": "P",
                "amount": "100",
                "counterparty": "Acme",
                "date": "2026-03-02",
            }
        ],
        [
            {
                "id": "Q",
                "amount": "100",
                "counterparty": "Acme",
                "date": "2026-03-02",
            }
        ],
    )
    assert report["matches"][0]["type"] == "probable"


def test_reconcile_one_to_many_split():
    report = engine.reconcile(
        [{"id": "INV3", "amount": "3000", "currency": "EUR"}],
        [
            {"id": "S1", "amount": "1000", "currency": "EUR"},
            {"id": "S2", "amount": "1000", "currency": "EUR"},
            {"id": "S3", "amount": "1000", "currency": "EUR"},
        ],
    )
    m = next(x for x in report["matches"] if x["type"] == "one_to_many")
    assert sorted(m["observed"]) == ["S1", "S2", "S3"]
    assert report["summary"]["fully_reconciled"] is True


def test_reconcile_many_to_one_batch():
    report = engine.reconcile(
        [
            {"id": "P1", "amount": "500", "currency": "EUR"},
            {"id": "P2", "amount": "500", "currency": "EUR"},
            {"id": "P3", "amount": "500", "currency": "EUR"},
        ],
        [{"id": "LUMP", "amount": "1500", "currency": "EUR"}],
    )
    m = next(x for x in report["matches"] if x["type"] == "many_to_one")
    assert sorted(m["expected"]) == ["P1", "P2", "P3"]


def test_reconcile_disabled_one_to_many_leaves_unmatched():
    report = engine.reconcile(
        [{"id": "INV3", "amount": "3000"}],
        [
            {"id": "S1", "amount": "1000"},
            {"id": "S2", "amount": "1000"},
            {"id": "S3", "amount": "1000"},
        ],
        {"enable_one_to_many": False},
    )
    assert report["summary"]["unmatched_expected"] == 1


def test_reconcile_currency_mismatch_unmatched():
    report = engine.reconcile(
        [
            {
                "id": "INV5",
                "amount": "750",
                "currency": "EUR",
                "reference": "INV5",
            }
        ],
        [
            {
                "id": "E5",
                "amount": "750",
                "currency": "USD",
                "reference": "INV5",
            }
        ],
    )
    assert report["unmatched_expected"] == ["INV5"]
    assert report["unmatched_observed"] == ["E5"]


def test_reconcile_non_strict_currency_allows_cross_ccy_combo():
    # With strict currency off, a blank/other currency may still combine.
    report = engine.reconcile(
        [{"id": "X", "amount": "300"}],
        [{"id": "a", "amount": "100"}, {"id": "b", "amount": "200"}],
        {"currency_strict": False},
    )
    assert any(m["type"] == "one_to_many" for m in report["matches"])


def test_one_to_one_skips_already_used_candidate():
    # Two observed entries both match one expected exactly; only the first
    # (deterministic tiebreak) is assigned, the second falls through to
    # unmatched rather than double-matching the same expected.
    report = engine.reconcile(
        [{"id": "INV", "amount": "100", "reference": "INV"}],
        [
            {"id": "E1", "amount": "100", "reference": "INV"},
            {"id": "E2", "amount": "100", "reference": "INV"},
        ],
        {"enable_one_to_many": False},
    )
    assert len(report["matches"]) == 1
    assert report["matches"][0]["observed"] == ["E1"]
    assert report["unmatched_observed"] == ["E2"]


def test_one_to_many_allows_missing_currency_under_strict():
    # Strict currency is on (default), but observed entries carry no currency;
    # they are still eligible to combine with a currency-bearing expected.
    report = engine.reconcile(
        [{"id": "X", "amount": "300", "currency": "EUR"}],
        [{"id": "a", "amount": "100"}, {"id": "b", "amount": "200"}],
    )
    assert any(m["type"] == "one_to_many" for m in report["matches"])


def test_subset_sum_no_solution_returns_none():
    opts = engine.Options()
    parts = [
        _item(id="a", amount=Decimal("7")),
        _item(id="b", amount=Decimal("9")),
    ]
    assert engine._subset_sum(Decimal("100"), parts, opts) is None


def test_combo_match_currency_from_first_available():
    opts = engine.Options()
    exp = [_item(id="e", amount=Decimal("300"), currency="")]
    obs = [
        _item(id="o1", amount=Decimal("100"), currency=""),
        _item(id="o2", amount=Decimal("200"), currency="GBP"),
    ]
    m = engine._combo_match("one_to_many", exp, obs, opts)
    assert m["currency"] == "GBP"


def test_explain_pair_disqualified_and_scored():
    dq = engine.explain_pair(
        {"id": "A", "amount": "1", "currency": "EUR"},
        {"id": "B", "amount": "1", "currency": "USD"},
    )
    assert dq["disqualified"] is True
    assert dq["reasons"] == ["currency mismatch"]
    ok = engine.explain_pair(
        {"id": "INV1", "amount": "100", "reference": "INV1"},
        {"id": "E1", "amount": "100", "reference": "INV1"},
    )
    assert ok["disqualified"] is False
    assert ok["signals"]["reference"] == 1.0
