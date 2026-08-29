<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Contributing

Thanks for looking. This server matches expected payments against observed
ones and explains its decisions.

## Before you open a pull request

```sh
pip install -e ".[dev]"
pytest                                       # tests plus the coverage gate
ruff check reconcile_mcp/ tests/ examples/ benches/
black --check reconcile_mcp/ tests/ examples/ benches/
mypy reconcile_mcp/
python benches/bench_reconcile.py --quick    # the benchmark still runs
```

`pytest` fails below **100% branch coverage**.

## The open problem

`reconcile` collapses on realistic data — a measured growth exponent near
**4.4** once several kinds of discrepancy are present at once, which is the
normal case rather than a stress case. 200 records takes over a minute.
`reconcile_many_to_many`, the harder problem, stays flat.

That is the most valuable thing anyone could work on here. If you take it
on:

- `benches/bench_reconcile.py --deep` is the measurement to move; report the
  exponent before and after, not the milliseconds.
- Keep `explain_match` honest. A faster matcher that can no longer say *why*
  it paired two records is a worse tool, not a better one.
- Add a test at a size that would have caught the regression, not only at
  fixture size. Every existing test passes today at this exponent.

## Benchmarks

`benches/` measures growth, not speed. It asserts no threshold — wall-clock
is not comparable between machines — but CI runs `--quick` so a benchmark
that stops compiling fails the build rather than rotting.

## The shared conformance file

`tests/test_suite_conformance.py` is generated from one canonical copy
shared across all 32 repositories in the suite. **Do not edit it here.** A
local edit fails `test_this_file_is_the_canonical_copy` by design.

## Versioning

**Versions increment by 0.0.1.** `0.1.0` follows `0.0.999`.

The version lives in `pyproject.toml` and `reconcile_mcp/__init__.py`.
Change both and add a `CHANGELOG.md` entry.

## Licence

Apache-2.0 OR MIT, at your option.
