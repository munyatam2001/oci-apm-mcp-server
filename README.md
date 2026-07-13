# OCI APM MCP Server

A proposed Model Context Protocol (MCP) server for safe, structured access to Oracle Cloud Infrastructure Application Performance Monitoring (OCI APM).

> Status: Milestone 1 foundation. The executable MCP server exposes only two read-only tools: `get_current_context` and `test_connection`. Trace queries and OCI mutations are not implemented.

## Product goal

Enable MCP clients such as Codex to investigate application latency, errors, traces, spans, and synthetic monitor health without giving an agent unnecessary control over APM resources.

The initial release will be read-only and will prioritize:

- explicit scope and time windows;
- deterministic query construction for common investigations;
- bounded, paginated responses;
- consistent structured output;
- least-privilege OCI IAM;
- redaction of potentially sensitive trace attributes;
- complete offline testing before live OCI validation.

## Proposed capability areas

1. Connection and APM-domain discovery
2. Trace Explorer query and drill-down
3. Slow and failed transaction investigations
4. Availability Monitoring and synthetic results
5. Deterministic comparison and investigation workflows

Mutating operations, including creating or changing synthetic monitors, are deferred until the read-only server is stable and security-reviewed.

## Install and run

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Export the values needed for your deployment; the server does not automatically load `.env` files.

```bash
export OCI_APM_AUTH_TYPE=config_file
export OCI_CONFIG_PROFILE=DEFAULT
export OCI_REGION=ap-mumbai-1
export OCI_APM_DOMAIN_ID='your-test-domain-ocid'
export OCI_APM_READ_ONLY=true
oci-apm-mcp-server
```

The server uses STDIO, so stdout is reserved for MCP protocol messages. Application logs go to stderr.

## Current tools

| Tool | OCI call | Purpose |
|---|---|---|
| `get_current_context` | None | Show masked scope, auth mode, timeouts, version, and read-only state |
| `test_connection` | One | Get one configured APM domain or list at most one domain in a compartment |

Both tools are marked read-only, idempotent, and non-destructive in MCP metadata. `test_connection` allowlists returned domain fields and never requests APM data keys.

## Verify offline

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest --cov=oci_apm_mcp --cov-report=term-missing --cov-fail-under=90
python -m build
```

The default test suite uses fakes and requires no OCI credentials or network connection.

## Design principles

- Use the official Python `mcp` SDK and OCI Python SDK.
- Keep natural-language interpretation outside the OCI adapter.
- Prefer typed, task-oriented tools over one unrestricted assistant tool.
- Keep an expert raw-query tool, but validate and constrain it.
- Mark tools accurately as read-only or mutating for MCP client approvals.
- Never return, log, or store APM data-key values.
- Never commit real OCIDs, credentials, customer trace data, headers, SQL text, or user identifiers.
- Treat partial results, pagination, authorization failures, and no-data results as distinct states.

## Repository map

```text
.
├── .github/
│   ├── pull_request_template.md
│   └── workflows/tests.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CLIENT_SETUP.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── GITHUB_WORKFLOW.md
│   ├── IAM_SETUP.md
│   ├── REFERENCE_REVIEW.md
│   ├── SECURITY.md
│   └── TOOL_CATALOG.md
├── src/oci_apm_mcp/       # read-only MCP foundation
├── tests/                 # offline unit and contract tests
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── pyproject.toml
```

## Planned delivery sequence

- **M0 — design baseline:** documents, decisions, security model, and GitHub workflow.
- **M1 — server foundation:** configuration, authentication, client factory, health check, error envelope, and offline tests. Implemented locally.
- **M2 — trace read path:** APM-domain discovery, bounded trace queries, trace details, and span details.
- **M3 — investigations:** slow transactions, error transactions, time-window comparison, and next-step suggestions.
- **M4 — synthetic read path:** monitor discovery, monitor details, results, and health summary.
- **M5 — production hardening:** audit events, redaction validation, packaging, deployment, and live OCI acceptance tests.
- **M6 — optional writes:** separately reviewed synthetic-monitor and script mutations.

See [the development plan](docs/DEVELOPMENT_PLAN.md) for acceptance criteria.

## Official references

- [Oracle APM documentation](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/)
- [Oracle APM IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/apmpolicyreference.htm)
- [OCI Python SDK: APM Traces](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/apm_traces.html)
- [OCI Python SDK: APM Synthetics](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/apm_synthetics.html)
- [OCI Python SDK: APM Control Plane](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/apm_control_plane.html)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp/)

## Licensing

No license has been selected yet. Choose and add a license before publishing the repository or accepting external contributions.
