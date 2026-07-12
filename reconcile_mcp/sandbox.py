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

"""Sandbox / test-mode fixtures for reconciliation.

Finance tools are useless to evaluate without data, and real cash data is the
last thing anyone wants to paste into a new integration. Following Stripe's
test-mode pattern, this module ships deterministic scenarios so an agent (or a
bank kicking the tyres) can run the full ``reconcile`` flow end-to-end with
zero setup and zero real data -- every scenario is hand-built to demonstrate
exactly one outcome so the behaviour is predictable and teachable.

This module is deliberately self-contained (no I/O, no clock, no randomness)
so it can be lifted verbatim into sibling servers as they adopt the same
test-mode contract.

Magic references
----------------
Beyond the canned scenarios, a handful of *magic* reference strings carry
documented, deterministic meaning when you build your own fixtures -- the
reconciliation analogue of Stripe's magic card numbers. See
:data:`MAGIC_REFERENCES`.
"""

from __future__ import annotations

from typing import Any

# Reference strings with documented sandbox behaviour. These are conventions
# for hand-built fixtures, surfaced so agents can construct predictable tests.
MAGIC_REFERENCES: dict[str, str] = {
    "SANDBOX-EXACT": "Pairs one-to-one with an observed entry of equal amount.",
    "SANDBOX-SHORT": "Observed side books less than expected (short payment).",
    "SANDBOX-SPLIT": "Expected settled by several smaller observed entries.",
    "SANDBOX-NEVER": "Never matches anything; always stays unmatched.",
}


def _expected(
    ident: str,
    amount: str,
    currency: str = "EUR",
    date: str = "2026-03-02",
    counterparty: str = "",
    reference: str = "",
) -> dict[str, Any]:
    """Build one canonical *expected* record (a pain.001-style instruction)."""
    return {
        "id": ident,
        "amount": amount,
        "currency": currency,
        "date": date,
        "counterparty": counterparty,
        "reference": reference or ident,
    }


def _observed(
    ident: str,
    amount: str,
    currency: str = "EUR",
    date: str = "2026-03-02",
    counterparty: str = "",
    reference: str = "",
) -> dict[str, Any]:
    """Build one canonical *observed* record (a camt.053-style booked entry)."""
    return {
        "id": ident,
        "amount": amount,
        "currency": currency,
        "date": date,
        "counterparty": counterparty,
        "reference": reference,
        "credit_debit": "CRDT",
    }


# Each scenario is a self-describing bundle: what it demonstrates plus the two
# input lists. Kept small and legible so the expected outcome is obvious.
SCENARIOS: dict[str, dict[str, Any]] = {
    "clean_match": {
        "description": (
            "Three invoices, three exact credits with matching references -- "
            "a fully reconciled statement."
        ),
        "demonstrates": "exact",
        "expected": [
            _expected("INV-1001", "1200.00", counterparty="Acme Ltd"),
            _expected("INV-1002", "845.50", counterparty="Globex SA"),
            _expected("INV-1003", "300.00", counterparty="Initech"),
        ],
        "observed": [
            _observed(
                "ENT-01",
                "1200.00",
                counterparty="ACME LTD",
                reference="INV-1001",
            ),
            _observed(
                "ENT-02",
                "845.50",
                counterparty="GLOBEX SA",
                reference="INV-1002",
            ),
            _observed(
                "ENT-03",
                "300.00",
                counterparty="INITECH",
                reference="INV-1003",
            ),
        ],
    },
    "short_payment": {
        "description": (
            "Debtor pays 50.00 less than invoiced but quotes the reference -- "
            "matched on reference, amount delta reported."
        ),
        "demonstrates": "amount_mismatch",
        "expected": [
            _expected("INV-2001", "1000.00", counterparty="Umbrella Corp"),
        ],
        "observed": [
            _observed(
                "ENT-11",
                "950.00",
                counterparty="UMBRELLA CORP",
                reference="INV-2001",
            ),
        ],
    },
    "split_settlement": {
        "description": (
            "One 3000.00 invoice settled in three instalments -- one expected "
            "to many observed."
        ),
        "demonstrates": "one_to_many",
        "expected": [
            _expected("INV-3001", "3000.00", counterparty="Stark Industries"),
        ],
        "observed": [
            _observed("ENT-21", "1000.00", counterparty="STARK IND"),
            _observed("ENT-22", "1000.00", counterparty="STARK IND"),
            _observed("ENT-23", "1000.00", counterparty="STARK IND"),
        ],
    },
    "batch_credit": {
        "description": (
            "A payout aggregator sends one 1500.00 lump covering three "
            "expected receivables -- many expected to one observed."
        ),
        "demonstrates": "many_to_one",
        "expected": [
            _expected("PO-4001", "500.00", counterparty="Wonka"),
            _expected("PO-4002", "500.00", counterparty="Wonka"),
            _expected("PO-4003", "500.00", counterparty="Wonka"),
        ],
        "observed": [
            _observed("ENT-31", "1500.00", counterparty="WONKA PAYOUTS"),
        ],
    },
    "fx_mismatch": {
        "description": (
            "Same amount and reference but the entry booked in USD, not the "
            "expected EUR -- disqualified under strict currency, left "
            "unmatched."
        ),
        "demonstrates": "unmatched",
        "expected": [
            _expected("INV-5001", "750.00", currency="EUR"),
        ],
        "observed": [
            _observed(
                "ENT-41",
                "750.00",
                currency="USD",
                reference="INV-5001",
            ),
        ],
    },
    "month_end": {
        "description": (
            "A realistic mixed close: one clean match, one short payment, one "
            "split settlement and one unexpected credit."
        ),
        "demonstrates": "mixed",
        "expected": [
            _expected("INV-6001", "2200.00", counterparty="Hooli"),
            _expected("INV-6002", "999.99", counterparty="Pied Piper"),
            _expected("INV-6003", "4500.00", counterparty="Aviato"),
        ],
        "observed": [
            _observed(
                "ENT-51",
                "2200.00",
                counterparty="HOOLI INC",
                reference="INV-6001",
            ),
            _observed(
                "ENT-52",
                "900.00",
                counterparty="PIED PIPER",
                reference="INV-6002",
            ),
            _observed("ENT-53", "2500.00", counterparty="AVIATO"),
            _observed("ENT-54", "2000.00", counterparty="AVIATO"),
            _observed(
                "ENT-55",
                "125.00",
                counterparty="UNKNOWN SENDER",
                reference="REFUND",
            ),
        ],
    },
}


def list_scenarios() -> list[dict[str, str]]:
    """Return every sandbox scenario's name, description and demonstrated type."""
    return [
        {
            "name": name,
            "demonstrates": body["demonstrates"],
            "description": body["description"],
        }
        for name, body in SCENARIOS.items()
    ]


def load_scenario(name: str) -> dict[str, Any]:
    """Return the ``expected``/``observed`` inputs for one named scenario.

    Raises:
        ValueError: if ``name`` is not a known scenario.
    """
    body = SCENARIOS.get(name)
    if body is None:
        known = ", ".join(sorted(SCENARIOS))
        raise ValueError(
            f"unknown sandbox scenario {name!r}; try one of: {known}"
        )
    return {
        "name": name,
        "description": body["description"],
        "demonstrates": body["demonstrates"],
        "expected": [dict(r) for r in body["expected"]],
        "observed": [dict(r) for r in body["observed"]],
    }
