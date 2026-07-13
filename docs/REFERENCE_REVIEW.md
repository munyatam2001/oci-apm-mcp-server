# Reference MCP review

## Purpose

This design was informed by read-only inspection of two existing OCI Observability and Management MCP projects:

- an OCI Monitoring MCP prototype;
- an OCI Log Analytics MCP implementation.

No source files were copied into this repository. The review identifies patterns to reuse and risks to avoid.

## OCI Monitoring MCP

### Patterns to retain

- Official `mcp` Python SDK with the SDK-provided `FastMCP` helper.
- Deterministic query builders for supported monitoring flows.
- Clarification before ambiguous execution.
- Separation between interpretation, execution adapters, models, and artifacts.
- Structured responses containing summaries, tables, charts, details, warnings, and artifacts.
- Instance-principal authentication with OCI config-file fallback.
- Product requirements and technical requirements written before implementation.

### Patterns to improve

- Replace the single broad assistant tool with composable, typed tools.
- Keep context explicit in tool inputs or server configuration; avoid hidden mutable conversational state.
- Start with more comprehensive offline tests and CI.
- Treat artifacts as a later capability, not a requirement for the first trace-query release.
- Centralize security policy, redaction, pagination, and error mapping from the beginning.

## OCI Log Analytics MCP

### Patterns to retain

- Dedicated authentication and OCI client layers.
- Explicit JSON schemas and task-oriented tool names.
- Read-only enforcement through one central classification policy.
- Drift-detection tests ensuring every registered tool is classified.
- Audit records, rate limiting, bounded queries, pagination, and partial-result handling.
- Confirmation workflows for mutating actions.
- Extensive synthetic fixtures and offline tests.
- GitHub Actions and repository-convention tests.
- Separation between primitive tools and deterministic investigation workflows.

### Patterns to simplify or avoid

- Do not begin with a very large tool catalogue; ship coherent slices.
- Do not mix notifications, reporting, dashboards, user memory, and mutations into the initial APM release.
- Do not recommend disabling SSH host-key verification.
- Do not use a reusable user-entered confirmation secret as the primary safety model. Prefer MCP approval metadata, server read-only mode, preview/execute separation, and OCI IAM.
- Do not write unredacted debug payloads to a user home directory.
- Do not let read tools create hidden persistent state.

## Resulting design position

The APM MCP will combine the Monitoring prototype's deterministic product design with the Log Analytics project's production guardrails. It will remain smaller than the Log Analytics surface and will expose the OCI APM API boundaries directly enough to be predictable and testable.
