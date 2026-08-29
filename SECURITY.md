<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.0.4   | :white_check_mark: |
| < 0.0.4 | :x:               |

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/sebastienrousseau/reconcile-mcp/security/advisories/new).
Please do not open a public issue for a security problem.

## Availability is the risk here

This server does not move money and holds no credentials. Its realistic
failure mode is not disclosure but **denial of service**, and it is
reachable from ordinary input.

`reconcile` is quadratic on clean data (exponent ~2.0) and, on data
carrying several kinds of discrepancy at once, degrades to a measured
exponent of about **4.4**. 200 records takes about **69 seconds**, and the
slope is still rising at that point.
See `docs/index.md` and `benches/bench_reconcile.py`.

**A caller can therefore make this server unresponsive with a few hundred
records** — not a malformed payload, just a slightly messy ledger of
ordinary size. If you expose these tools to untrusted input:

- cap the record count per call;
- run reconciliation with a timeout and a bounded worker, not on a request
  thread;
- prefer `reconcile_many_to_many`, which at 200 mixed records costs about
  396 ms against 69 s for the one-to-one path.

This is recorded rather than fixed. Treat it as a known limit.

## Input handling

Records are plain dictionaries; nothing is executed, deserialised into
objects, or read from disk on the caller's behalf. Sandbox scenarios ship
with the package and are read from it, not fetched.
