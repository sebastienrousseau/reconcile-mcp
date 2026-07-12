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

"""Tests for the pain.001 / camt.053 adapters."""

import pytest

from reconcile_mcp import adapters


def test_from_pain001_list_and_field_mapping():
    rows = adapters.from_pain001(
        [
            {
                "end_to_end_id": "E2E-1",
                "instructed_amount": "100.00",
                "instructed_currency": "EUR",
                "creditor_name": "Acme",
                "requested_execution_date": "2026-03-02",
                "remittance_information": "INV-1",
            }
        ]
    )
    assert rows[0]["id"] == "E2E-1"
    assert rows[0]["amount"] == "100.00"
    assert rows[0]["currency"] == "EUR"
    assert rows[0]["counterparty"] == "Acme"
    assert rows[0]["reference"] == "INV-1"


def test_from_pain001_wrapping_dict():
    rows = adapters.from_pain001(
        {"transactions": [{"id": "T1", "amount": "5"}]}
    )
    assert rows[0]["id"] == "T1"


def test_from_camt053_entries_and_debtor_fallback():
    rows = adapters.from_camt053(
        {
            "entries": [
                {
                    "entry_reference": "ENT-1",
                    "amount": "250.00",
                    "currency": "EUR",
                    "debtor_name": "Payer Co",
                    "booking_date": "2026-03-02",
                }
            ]
        }
    )
    assert rows[0]["id"] == "ENT-1"
    # counterparty falls back to debtor_name when no creditor is present.
    assert rows[0]["counterparty"] == "Payer Co"


def test_missing_id_gets_synthesised():
    rows = adapters.from_camt053([{"amount": "1"}])
    assert rows[0]["id"] == "CAMT-0"
    rows2 = adapters.from_pain001([{"amount": "1"}])
    assert rows2[0]["id"] == "PAIN-0"


def test_unwrap_errors():
    with pytest.raises(ValueError, match="expected a list under"):
        adapters.from_pain001({"nope": []})
    with pytest.raises(ValueError, match="must be a list of records"):
        adapters.from_camt053("a string")


def test_unwrap_skips_non_dicts():
    rows = adapters.from_pain001([{"id": "ok", "amount": "1"}, 42, "x"])
    assert len(rows) == 1
    assert rows[0]["id"] == "ok"
