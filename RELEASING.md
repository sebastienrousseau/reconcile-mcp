<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Releasing reconcile-mcp

This document defines **what merits a release** and **how to cut one**,
so versions are deliberate rather than ad-hoc.

## Versioning scheme

reconcile-mcp is versioned on its own line. **Versions increment by
0.0.1**; `0.1.0` follows `0.0.999`. The scheduled `Release Consistency`
workflow (`scripts/check_suite_consistency.py`) compares the tree with
what is published on PyPI and fails when they disagree, so a version
bumped and never released is noticed rather than stranded.

## What merits a release

Cut a new version when there is user-visible change to ship - bug fixes,
security or dependency patches, new tools / resources / prompts, a
change to how matching scores or assigns, or documentation that ships in
the package.

Do **not** cut a release that contains only a version-number bump with
no functional, security, or documentation change.

## Pre-flight checklist

A release is ready only when **all** of the following hold on `main`:

1. The full gate is green: `pytest` (100% line+branch coverage),
   `ruff check`, `black --check`, `mypy reconcile_mcp/` and
   `python benches/bench_reconcile.py --quick`.
2. Every Dependabot / CodeQL / Scorecard alert is resolved or has a
   documented, expiring suppression.
3. `CHANGELOG.md` has a dated section for the new version describing the
   change set.
4. The version is identical in `pyproject.toml`,
   `reconcile_mcp/__init__.py`, `CHANGELOG.md`, `glama.json` and
   `server.json` (enforced by `scripts/verify_versions.py`, which the
   `Version sources agree` workflow runs). The Glama directory and the
   MCP registry read those two manifests; a release that forgets them
   shows an old version to every agent that browses for the server.
5. `SECURITY.md` and `CITATION.cff` name the new version.

## Cutting the release

1. Bump the version in `pyproject.toml`, `reconcile_mcp/__init__.py`,
   `glama.json`, `server.json`, `SECURITY.md` and `CITATION.cff`, and
   add the `CHANGELOG.md` section, in a single PR.
2. Merge the PR to `main` once CI is green.
3. Push a signed tag:

   ```bash
   git tag -s vX.Y.Z -m "reconcile-mcp vX.Y.Z" <merge-commit>
   git push origin vX.Y.Z
   ```

4. The tag triggers two workflows:
   - `release.yml` builds with Poetry, runs `twine check`, attaches a
     SLSA build provenance attestation, publishes to PyPI via OIDC
     trusted publishing (with PEP 740 attestations), signs every
     distribution keylessly with cosign, creates the GitHub release
     with generated notes, and attaches CycloneDX and SPDX SBOMs plus a
     licence manifest.
   - `publish-mcp.yml` stamps `server.json` from the tag, waits for
     PyPI to surface the version, and publishes to the MCP registry.

## After releasing

- Confirm the version is live on
  [PyPI](https://pypi.org/project/reconcile-mcp/) and the GitHub release
  is published (not draft).
- Verify a clean install: `pip install reconcile-mcp==X.Y.Z` and
  `reconcile-mcp --version`.
- Confirm the MCP registry and Glama show the new version.

## CI integrations

- **PyPI trusted publisher** (`release.yml`): configured at
  <https://pypi.org/manage/account/publishing/>. The publisher claim
  set is `repo:sebastienrousseau/reconcile-mcp:environment:pypi` with
  `workflow_ref` pointing at `.github/workflows/release.yml`.
- **MCP registry** (`publish-mcp.yml`): authenticates with the
  workflow's GitHub OIDC token; no secret to configure.
