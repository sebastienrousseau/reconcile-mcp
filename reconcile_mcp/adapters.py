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

"""Adapters from parsed ISO 20022 structures to canonical reconcile records.

These bridge the *rest* of the suite into the engine. ``pain.001`` records
(produced by the ``pain001`` library / ``pain001-mcp``) become the *expected*
side; ``camt.053`` entries (produced by ``camt053`` / ``camt053-mcp``) become
the *observed* side. This is the "you own both sides of the match" story made
literal.

The adapters are intentionally *tolerant*: they read from several likely key
spellings and quietly skip fields that are absent, so they keep working across
minor shape changes in the upstream libraries and accept either a whole parsed
document or a bare list of transactions/entries. They never import those
libraries -- they operate purely on the dict/JSON the tools already emit.
"""

from __future__ import annotations

from typing import Any

# Ordered key fallbacks for each canonical field. First present, non-empty
# value wins. Covers the common spellings across the suite's parsers.
_AMOUNT_KEYS = (
    "amount",
    "instructed_amount",
    "instd_amt",
    "interbank_settlement_amount",
    "amt",
)
_CURRENCY_KEYS = (
    "currency",
    "instructed_currency",
    "interbank_settlement_currency",
    "ccy",
)
_REFERENCE_KEYS = (
    "reference",
    "remittance_information",
    "rmt_inf",
    "unstructured",
    "end_to_end_id",
    "e2e_id",
)
_DATE_KEYS = (
    "date",
    "value_date",
    "booking_date",
    "requested_execution_date",
    "interbank_settlement_date",
    "val_dt",
    "bookg_dt",
)


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first present, non-empty value among ``keys``."""
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _unwrap(document: Any, list_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Coerce a document-or-list into a list of record dicts.

    Accepts a bare list, or a dict wrapping the records under any of
    ``list_keys`` (e.g. ``{"transactions": [...]}``). Raises ValueError on
    anything else so bad input fails loudly rather than reconciling nothing.
    """
    if isinstance(document, list):
        return [r for r in document if isinstance(r, dict)]
    if isinstance(document, dict):
        for key in list_keys:
            value = document.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
        raise ValueError(
            f"expected a list under one of {list_keys}, found keys "
            f"{sorted(document)}"
        )
    raise ValueError("document must be a list of records or a wrapping dict")


def _canonical(
    record: dict[str, Any], index: int, id_keys: tuple[str, ...], prefix: str
) -> dict[str, Any]:
    """Map one upstream record to a canonical reconcile dict."""
    ident = _first(record, id_keys)
    if ident in (None, ""):
        ident = f"{prefix}-{index}"
    counterparty = (
        _first(record, ("counterparty", "creditor_name", "cdtr_nm"))
        or _first(record, ("debtor_name", "dbtr_nm", "related_party"))
        or ""
    )
    return {
        "id": str(ident),
        "amount": _first(record, _AMOUNT_KEYS),
        "currency": _first(record, _CURRENCY_KEYS) or "",
        "date": _first(record, _DATE_KEYS) or "",
        "counterparty": counterparty,
        "reference": _first(record, _REFERENCE_KEYS) or "",
    }


def from_pain001(document: Any) -> list[dict[str, Any]]:
    """Adapt parsed ``pain.001`` payment instructions to *expected* records.

    Args:
        document: a list of transaction dicts, or a dict wrapping them under
            ``transactions`` / ``payments`` / ``records``.

    Returns:
        Canonical expected records ready for :func:`engine.reconcile`.
    """
    rows = _unwrap(document, ("transactions", "payments", "records"))
    return [
        _canonical(
            r, i, ("end_to_end_id", "e2e_id", "id", "instruction_id"), "PAIN"
        )
        for i, r in enumerate(rows)
    ]


def from_camt053(document: Any) -> list[dict[str, Any]]:
    """Adapt parsed ``camt.053`` statement entries to *observed* records.

    Args:
        document: a list of entry dicts, or a dict wrapping them under
            ``entries`` / ``transactions`` / ``statements``.

    Returns:
        Canonical observed records ready for :func:`engine.reconcile`.
    """
    rows = _unwrap(document, ("entries", "transactions", "statements"))
    return [
        _canonical(
            r,
            i,
            ("id", "entry_reference", "acct_svcr_ref", "ntry_ref"),
            "CAMT",
        )
        for i, r in enumerate(rows)
    ]
