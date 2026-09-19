<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Getting support

Thanks for using reconcile-mcp. Here's the fastest way to get help, by need.

## Questions & how-to

- **Read first:** the [README](README.md), [`docs/index.md`](docs/index.md)
  (what the tools answer and how cost grows with record count), and the
  runnable [`examples/`](examples/) walkthrough. For the message formats on
  either side of a match, see
  [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp) and
  [`camt053-mcp`](https://github.com/sebastienrousseau/camt053-mcp).
- **Still stuck?** Open a question issue at
  <https://github.com/sebastienrousseau/reconcile-mcp/issues/new>. Include
  your Python version, the `reconcile-mcp` version
  (`reconcile-mcp --version`), your MCP client (Claude Desktop / IDE /
  agent), the transport you run, and a minimal reproducer.

## Bugs

Open a bug report at
<https://github.com/sebastienrousseau/reconcile-mcp/issues/new> with a
minimal reproducer, the tool name, the arguments, and the full result or
error payload. A failing pair of record sets (with sensitive values
redacted) helps enormously; `explain_match` on the pair you expected to
match is the fastest way to show what went wrong.

## Feature requests

Open a feature request at
<https://github.com/sebastienrousseau/reconcile-mcp/issues/new>. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the extension points and
[ROADMAP.md](ROADMAP.md) for what's planned. The open problem that most
needs work is the growth of the one-to-one matcher on messy data; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Security

**Do not** open public issues for vulnerabilities. Follow the private
disclosure process in [SECURITY.md](SECURITY.md).

## Contributing & maintaining

See [CONTRIBUTING.md](CONTRIBUTING.md) and [GOVERNANCE.md](GOVERNANCE.md).

## Supported versions

Fixes land on the latest release line. See [SECURITY.md](SECURITY.md) for
the supported-version policy. reconcile-mcp requires Python 3.10+.
