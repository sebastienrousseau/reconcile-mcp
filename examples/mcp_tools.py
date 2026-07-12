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

"""Runnable examples for the reconcile-mcp tools.

Run with ``python examples/mcp_tools.py`` after ``pip install -e .``. These
call the tool functions directly (the same functions the MCP server exposes)
so you can see the shapes without an MCP client.
"""

import json

from reconcile_mcp import server


def main() -> None:
    """Demonstrate the sandbox, an ad-hoc reconcile, and a single-pair explain."""
    # 1. One-call sandbox run -- no data needed.
    print("== run_sandbox_scenario('split_settlement') ==")
    print(json.dumps(server.run_sandbox_scenario("split_settlement")["summary"]))

    # 2. Reconcile your own records.
    print("\n== reconcile (short payment) ==")
    report = server.reconcile(
        expected=[
            {"id": "INV-9", "amount": 500.00, "currency": "EUR", "reference": "INV-9"}
        ],
        observed=[
            {"id": "E-9", "amount": 480.00, "currency": "EUR", "reference": "INV-9"}
        ],
    )
    print(json.dumps(report["matches"][0]))

    # 3. Explain why one pair scores the way it does.
    print("\n== explain_match ==")
    detail = server.explain_match(
        {"id": "INV-9", "amount": 500.00, "reference": "INV-9"},
        {"id": "E-9", "amount": 480.00, "reference": "INV-9"},
    )
    print(json.dumps(detail))


if __name__ == "__main__":
    main()
