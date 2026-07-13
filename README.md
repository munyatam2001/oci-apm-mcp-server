# OCI APM MCP Server

A proposed Model Context Protocol (MCP) server for safe, structured access to Oracle Cloud Infrastructure Application Performance Monitoring (OCI APM).

> Status: documentation-first design. This repository does not yet contain an executable MCP server and makes no OCI API calls.

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
│   └── workflows/docs.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CLIENT_SETUP.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── GITHUB_WORKFLOW.md
│   ├── IAM_SETUP.md
│   ├── REFERENCE_REVIEW.md
│   ├── SECURITY.md
│   └── TOOL_CATALOG.md
├── src/oci_apm_mcp/       # implementation begins in Milestone 1
├── tests/                 # offline tests begin in Milestone 1
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── pyproject.toml
```

## Planned delivery sequence

- **M0 — design baseline:** documents, decisions, security model, and GitHub workflow.
- **M1 — server foundation:** configuration, authentication, client factory, health check, error envelope, and offline tests.
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
