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

"""Explainable reconciliation engine for ISO 20022 cash flows.

The engine matches *expected* payments (what you instructed or anticipated --
typically derived from ``pain.001`` credit transfers) against *observed*
entries (what actually booked on the account -- typically derived from a
``camt.053`` statement). It is intentionally decoupled from any parsing
library: every function operates on small canonical dictionaries, so the core
logic is pure, deterministic and fully unit-testable without XML fixtures.

Design goals, in order:

1. **Explainability.** Every match carries a ``reasons`` list and a numeric
   ``score`` so a human (or an agent surfacing to a human) can see *why* two
   records were paired -- a hard requirement in finance.
2. **Determinism.** No randomness and a total tiebreak order, so the same
   inputs always yield the same output (safe to cache, safe to diff).
3. **Money-safe arithmetic.** Amounts are coerced to :class:`~decimal.Decimal`;
   floats never participate in equality or summation.

Match shapes produced:

* ``exact``          -- one expected <-> one observed, amount equal.
* ``amount_mismatch``-- one expected <-> one observed, strong reference but the
  amounts differ (short/over payment); the delta is reported.
* ``probable``       -- one expected <-> one observed above the review
  threshold but below high confidence; flagged for a human.
* ``one_to_many``    -- one expected settled by several observed entries
  (instalments / split settlement) summing to it within tolerance.
* ``many_to_one``    -- several expected covered by one observed entry (a lump
  or batch credit) summing to it within tolerance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import Any

# --- Tunable defaults -------------------------------------------------------
# Signal weights for the one-to-one score. They sum to 1.0 so a perfect match
# on every present signal scores 1.0.
_W_REFERENCE = Decimal("0.45")
_W_AMOUNT = Decimal("0.35")
_W_DATE = Decimal("0.10")
_W_NAME = Decimal("0.10")

# Default classification thresholds (overridable via Options).
_DEFAULT_HIGH = 0.80  # >= this and amount exact -> confident match
_DEFAULT_REVIEW = 0.55  # >= this -> candidate worth surfacing
# Amount tolerance: a pair is "amount equal" if within the greater of an
# absolute minor-unit tolerance and a relative fraction of the expected value.
_DEFAULT_ABS_TOL = Decimal("0.00")
_DEFAULT_REL_TOL = Decimal("0.00")
_DEFAULT_DATE_WINDOW = 5  # days either side still counts, with linear decay
# Upper bound on how many observed entries may combine to settle one expected
# (and vice versa). Keeps subset-sum tractable and matches reality: split
# settlements and batch credits are small.
_MAX_COMBINATION = 6


@dataclass(frozen=True)
class Options:
    """Reconciliation tunables. All fields have sensible finance defaults."""

    abs_tol: Decimal = _DEFAULT_ABS_TOL
    rel_tol: Decimal = _DEFAULT_REL_TOL
    date_window_days: int = _DEFAULT_DATE_WINDOW
    high_threshold: float = _DEFAULT_HIGH
    review_threshold: float = _DEFAULT_REVIEW
    currency_strict: bool = True
    enable_one_to_many: bool = True
    max_combination: int = _MAX_COMBINATION

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Options:
        """Build Options from a loose dict, ignoring unknown keys.

        Numeric tolerances accept int/float/str and are coerced to Decimal so
        callers (and JSON) never introduce binary-float rounding.
        """
        data = data or {}
        opts = cls()
        return cls(
            abs_tol=_to_decimal(data.get("abs_tol", opts.abs_tol))
            or Decimal(0),
            rel_tol=_to_decimal(data.get("rel_tol", opts.rel_tol))
            or Decimal(0),
            date_window_days=int(
                data.get("date_window_days", opts.date_window_days)
            ),
            high_threshold=float(
                data.get("high_threshold", opts.high_threshold)
            ),
            review_threshold=float(
                data.get("review_threshold", opts.review_threshold)
            ),
            currency_strict=bool(
                data.get("currency_strict", opts.currency_strict)
            ),
            enable_one_to_many=bool(
                data.get("enable_one_to_many", opts.enable_one_to_many)
            ),
            max_combination=int(
                data.get("max_combination", opts.max_combination)
            ),
        )


@dataclass(frozen=True)
class Item:
    """A canonical cash record -- either an expected payment or an entry.

    Only ``id`` and ``amount`` are truly required; the rest sharpen matching
    when present and are simply treated as "unknown" (neutral) when absent.
    """

    id: str
    amount: Decimal
    currency: str = ""
    value_date: date | None = None
    counterparty: str = ""
    reference: str = ""
    account: str = ""


@dataclass
class Candidate:
    """A scored expected<->observed pairing considered during assignment."""

    expected: Item
    observed: Item
    score: float
    reasons: list[str] = field(default_factory=list)
    amount_delta: Decimal = Decimal(0)


# --- Coercion helpers -------------------------------------------------------


def _to_decimal(value: Any) -> Decimal | None:
    """Coerce int/float/str/Decimal to Decimal; return None if not a number.

    Floats are routed through ``str`` so ``0.1`` becomes ``Decimal("0.1")``
    rather than the binary-expansion noise of ``Decimal(0.1)``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(value: Any) -> date | None:
    """Parse an ISO-8601 date (or datetime prefix) to a date; None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def to_item(raw: dict[str, Any]) -> Item:
    """Build an :class:`Item` from a loose dict.

    Raises :class:`ValueError` if ``id`` or a parseable ``amount`` is missing --
    those two are the minimum needed to reconcile anything.
    """
    ident = raw.get("id")
    if ident in (None, ""):
        raise ValueError("each record needs a non-empty 'id'")
    amount = _to_decimal(raw.get("amount"))
    if amount is None:
        raise ValueError(
            f"record {ident!r} has a missing or non-numeric 'amount'"
        )
    return Item(
        id=str(ident),
        amount=amount,
        currency=str(raw.get("currency", "") or "").upper(),
        value_date=_to_date(raw.get("date") or raw.get("value_date")),
        counterparty=str(raw.get("counterparty", "") or ""),
        reference=str(raw.get("reference", "") or ""),
        account=str(
            raw.get("account", "") or raw.get("counterparty_account", "")
        ),
    )


# --- Signal scoring ---------------------------------------------------------

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _normalize_ref(text: str) -> str:
    """Uppercase-fold a reference to bare alphanumerics for robust equality."""
    return _NON_ALNUM.sub("", text.lower())


def _tokenize(text: str) -> set[str]:
    """Split a name into a set of lowercased alphanumeric tokens."""
    return {t for t in _NON_ALNUM.sub(" ", text.lower()).split() if t}


def reference_similarity(expected: Item, observed: Item) -> float:
    """Score reference/id agreement between two records in ``[0, 1]``.

    Considers each side's explicit ``reference`` and its ``id`` (an end-to-end
    id often appears verbatim inside the statement entry's remittance text).
    """
    left = {_normalize_ref(expected.reference), _normalize_ref(expected.id)}
    right = {_normalize_ref(observed.reference), _normalize_ref(observed.id)}
    left.discard("")
    right.discard("")
    if not left or not right:
        return 0.0
    if left & right:
        return 1.0
    # Containment (one reference embedded in the other's free-text), but only
    # for tokens long enough that the overlap is meaningful, not incidental.
    for a in left:
        for b in right:
            if len(a) >= 6 and len(b) >= 6 and (a in b or b in a):
                return 0.8
    return 0.0


def amount_similarity(
    expected: Item, observed: Item, opts: Options
) -> tuple[float, Decimal, bool]:
    """Return ``(signal, delta, within_tolerance)`` for two amounts.

    ``delta`` is ``observed - expected`` (positive = overpaid). ``signal`` is
    1.0 when within tolerance and decays linearly to 0 across one further
    expected-magnitude of difference.
    """
    delta = observed.amount - expected.amount
    magnitude = abs(delta)
    tol = max(opts.abs_tol, (opts.rel_tol * abs(expected.amount)))
    if magnitude <= tol:
        return 1.0, delta, True
    # Linear decay: at |delta| == |expected| (a 100% miss) the signal is 0.
    ref = abs(expected.amount)
    if ref == 0:
        return 0.0, delta, False
    signal = 1.0 - float(magnitude / ref)
    return (signal if signal > 0 else 0.0), delta, False


def date_similarity(expected: Item, observed: Item, opts: Options) -> float:
    """Score date proximity in ``[0, 1]``; neutral 0.5 if either is unknown."""
    if expected.value_date is None or observed.value_date is None:
        return 0.5
    distance = abs((observed.value_date - expected.value_date).days)
    if opts.date_window_days <= 0:
        return 1.0 if distance == 0 else 0.0
    if distance > opts.date_window_days:
        return 0.0
    return 1.0 - (distance / opts.date_window_days)


def name_similarity(expected: Item, observed: Item) -> float:
    """Jaccard token overlap of counterparty names; 0.5 if either is unknown."""
    left = _tokenize(expected.counterparty)
    right = _tokenize(observed.counterparty)
    if not left or not right:
        return 0.5
    return len(left & right) / len(left | right)


def score_pair(
    expected: Item, observed: Item, opts: Options
) -> Candidate | None:
    """Score one expected<->observed pair.

    Returns a :class:`Candidate`, or ``None`` when the pair is disqualified
    outright (currency clash under strict mode) so it never competes for
    assignment.
    """
    reasons: list[str] = []
    if (
        opts.currency_strict
        and expected.currency
        and observed.currency
        and expected.currency != observed.currency
    ):
        return None

    ref = reference_similarity(expected, observed)
    amt, delta, within = amount_similarity(expected, observed, opts)
    dat = date_similarity(expected, observed, opts)
    nam = name_similarity(expected, observed)

    if ref >= 1.0:
        reasons.append("reference exact")
    elif ref > 0:
        reasons.append("reference partial")
    if within:
        reasons.append("amount exact")
    elif amt > 0:
        reasons.append(f"amount close (delta {delta})")
    if expected.value_date and observed.value_date:
        distance = abs((observed.value_date - expected.value_date).days)
        reasons.append(f"date +/-{distance}d")
    if nam >= 1.0:
        reasons.append("counterparty exact")
    elif _tokenize(expected.counterparty) & _tokenize(observed.counterparty):
        reasons.append("counterparty partial")

    score = float(
        _W_REFERENCE * Decimal(str(ref))
        + _W_AMOUNT * Decimal(str(amt))
        + _W_DATE * Decimal(str(dat))
        + _W_NAME * Decimal(str(nam))
    )
    return Candidate(
        expected=expected,
        observed=observed,
        score=round(score, 4),
        reasons=reasons,
        amount_delta=delta,
    )


def _confidence(score: float, opts: Options) -> str:
    """Bucket a score into high/medium/low for human-facing display."""
    if score >= opts.high_threshold:
        return "high"
    if score >= opts.review_threshold:
        return "medium"
    return "low"


# --- Assignment -------------------------------------------------------------


def _one_to_one(
    expected: list[Item], observed: list[Item], opts: Options
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    """Greedy highest-score-first one-to-one assignment.

    Returns ``(matches, used_expected_ids, used_observed_ids)``. Greedy (not
    optimal Hungarian) is a deliberate trade: it is simpler, deterministic and
    its decisions are individually explainable, which matters more here than
    squeezing out a marginally higher global score.
    """
    candidates: list[Candidate] = []
    for exp in expected:
        for obs in observed:
            cand = score_pair(exp, obs, opts)
            if cand is not None and cand.score >= opts.review_threshold:
                candidates.append(cand)
    # Total order: score desc, then ids asc for full determinism.
    candidates.sort(key=lambda c: (-c.score, c.expected.id, c.observed.id))

    used_exp: set[str] = set()
    used_obs: set[str] = set()
    matches: list[dict[str, Any]] = []
    for cand in candidates:
        if cand.expected.id in used_exp or cand.observed.id in used_obs:
            continue
        used_exp.add(cand.expected.id)
        used_obs.add(cand.observed.id)
        within = "amount exact" in cand.reasons
        if within and cand.score >= opts.high_threshold:
            kind = "exact"
        elif "reference exact" in cand.reasons and not within:
            kind = "amount_mismatch"
        else:
            kind = "probable"
        matches.append(
            {
                "type": kind,
                "expected": [cand.expected.id],
                "observed": [cand.observed.id],
                "score": cand.score,
                "confidence": _confidence(cand.score, opts),
                "amount_expected": str(cand.expected.amount),
                "amount_observed": str(cand.observed.amount),
                "amount_delta": str(cand.amount_delta),
                "currency": cand.expected.currency or cand.observed.currency,
                "reasons": cand.reasons,
            }
        )
    return matches, used_exp, used_obs


def _subset_sum(
    target: Decimal, parts: list[Item], opts: Options
) -> list[Item] | None:
    """Smallest combination of >=2 ``parts`` whose amounts sum to ``target``.

    Bounded at ``opts.max_combination`` members. Deterministic: combinations
    are generated in index order and the first size-k hit (parts pre-sorted by
    id) wins. Tolerance mirrors the one-to-one amount rule.
    """
    tol = max(opts.abs_tol, opts.rel_tol * abs(target))
    limit = min(opts.max_combination, len(parts))
    for size in range(2, limit + 1):
        for combo in combinations(parts, size):
            total = sum((p.amount for p in combo), Decimal(0))
            if abs(total - target) <= tol:
                return list(combo)
    return None


def _one_to_many(
    expected: list[Item],
    observed: list[Item],
    used_exp: set[str],
    used_obs: set[str],
    opts: Options,
) -> list[dict[str, Any]]:
    """Match residuals where one record equals a sum of several on the far side.

    Runs both directions: one expected settled by many observed
    (``one_to_many``) and many expected covered by one observed
    (``many_to_one``). Records consumed here are added to ``used_*`` in place.
    """
    matches: list[dict[str, Any]] = []
    rem_exp = sorted(
        (e for e in expected if e.id not in used_exp), key=lambda i: i.id
    )
    rem_obs = sorted(
        (o for o in observed if o.id not in used_obs), key=lambda i: i.id
    )

    # One expected <- many observed. rem_exp is already free of one-to-one
    # matches and each expected is visited once, so no per-item used-guard is
    # needed here (unlike the observed side below, which rem_obs may have had
    # entries consumed from by the loop above).
    for exp in rem_exp:
        pool = [
            o
            for o in rem_obs
            if o.id not in used_obs and _currency_ok(exp, o, opts)
        ]
        combo = _subset_sum(exp.amount, pool, opts)
        if combo is None:
            continue
        used_exp.add(exp.id)
        for o in combo:
            used_obs.add(o.id)
        matches.append(_combo_match("one_to_many", [exp], combo, opts))

    # Many expected -> one observed.
    for obs in rem_obs:
        if obs.id in used_obs:
            continue
        pool = [
            e
            for e in rem_exp
            if e.id not in used_exp and _currency_ok(e, obs, opts)
        ]
        combo = _subset_sum(obs.amount, pool, opts)
        if combo is None:
            continue
        used_obs.add(obs.id)
        for e in combo:
            used_exp.add(e.id)
        matches.append(_combo_match("many_to_one", combo, [obs], opts))
    return matches


def _currency_ok(expected: Item, observed: Item, opts: Options) -> bool:
    """Whether two records may combine given the currency-strict setting."""
    if not opts.currency_strict:
        return True
    if not expected.currency or not observed.currency:
        return True
    return expected.currency == observed.currency


def _combo_match(
    kind: str, exp_side: list[Item], obs_side: list[Item], opts: Options
) -> dict[str, Any]:
    """Assemble a one-to-many / many-to-one match record."""
    exp_total = sum((i.amount for i in exp_side), Decimal(0))
    obs_total = sum((i.amount for i in obs_side), Decimal(0))
    currency = ""
    for i in (*exp_side, *obs_side):
        if i.currency:
            currency = i.currency
            break
    n = len(obs_side) if kind == "one_to_many" else len(exp_side)
    return {
        "type": kind,
        "expected": [i.id for i in exp_side],
        "observed": [i.id for i in obs_side],
        "score": 1.0,
        "confidence": "high",
        "amount_expected": str(exp_total),
        "amount_observed": str(obs_total),
        "amount_delta": str(obs_total - exp_total),
        "currency": currency,
        "reasons": [f"amount sum of {n} entries"],
    }


def reconcile(
    expected_raw: list[dict[str, Any]],
    observed_raw: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile expected payments against observed statement entries.

    Args:
        expected_raw: canonical dicts for anticipated payments (from pain.001).
        observed_raw: canonical dicts for booked entries (from camt.053).
        options: optional tunables (see :class:`Options`).

    Returns:
        A JSON-serializable report: ``summary``, ``matches``,
        ``unmatched_expected`` and ``unmatched_observed``.

    Raises:
        ValueError: if any record lacks an ``id`` or a numeric ``amount``.
    """
    opts = Options.from_dict(options)
    expected = [to_item(r) for r in expected_raw]
    observed = [to_item(r) for r in observed_raw]

    matches, used_exp, used_obs = _one_to_one(expected, observed, opts)
    if opts.enable_one_to_many:
        matches += _one_to_many(expected, observed, used_exp, used_obs, opts)

    unmatched_exp = [e.id for e in expected if e.id not in used_exp]
    unmatched_obs = [o.id for o in observed if o.id not in used_obs]

    by_type: dict[str, int] = {}
    for m in matches:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1

    return {
        "summary": {
            "expected_count": len(expected),
            "observed_count": len(observed),
            "matched_expected": len(used_exp),
            "matched_observed": len(used_obs),
            "unmatched_expected": len(unmatched_exp),
            "unmatched_observed": len(unmatched_obs),
            "matches_by_type": by_type,
            "fully_reconciled": not unmatched_exp and not unmatched_obs,
        },
        "matches": matches,
        "unmatched_expected": unmatched_exp,
        "unmatched_observed": unmatched_obs,
    }


def explain_pair(
    expected_raw: dict[str, Any],
    observed_raw: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a single expected/observed pair and explain the signals.

    A tuning aid: shows the per-signal breakdown and the resulting score even
    for a pair that would fall below the review threshold in a full run.
    """
    opts = Options.from_dict(options)
    exp = to_item(expected_raw)
    obs = to_item(observed_raw)
    ref = reference_similarity(exp, obs)
    amt, delta, within = amount_similarity(exp, obs, opts)
    dat = date_similarity(exp, obs, opts)
    nam = name_similarity(exp, obs)
    cand = score_pair(exp, obs, opts)
    score = cand.score if cand is not None else 0.0
    return {
        "score": score,
        "confidence": _confidence(score, opts),
        "disqualified": cand is None,
        "signals": {
            "reference": round(ref, 4),
            "amount": round(amt, 4),
            "date": round(dat, 4),
            "name": round(nam, 4),
        },
        "amount_delta": str(delta),
        "within_amount_tolerance": within,
        "reasons": cand.reasons if cand is not None else ["currency mismatch"],
    }
