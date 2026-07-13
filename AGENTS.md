# Repository guidance

These rules apply to every change in this repository.

## Product boundary

- The first production release is read-only.
- Do not add OCI mutations without a dedicated design review and separate pull request.
- Never expose APM data-key values through MCP tools.
- Keep APM domain management out of the agent-facing surface unless explicitly approved.

## Dependencies and architecture

- Use the official Python `mcp` SDK. Do not add the separate third-party `fastmcp` package.
- Use the OCI Python SDK rather than shelling out to the OCI CLI.
- Keep MCP registration, business services, query builders, and OCI clients in separate modules.
- Keep natural-language interpretation out of OCI client adapters.
- Use typed models for all public tool inputs and outputs.
- Preserve one consistent response envelope across tools.

## Tool design

- Tool names must be task-oriented and unambiguous.
- Tool descriptions must state scope, cost/latency implications, defaults, limits, and whether the tool reads or changes state.
- Mark MCP tool annotations accurately. Mutating tools must never claim to be read-only.
- Default raw trace searches to a short time range and small result limit.
- Return pagination state and warnings; do not silently discard results.
- Distinguish `no_data`, `not_found`, `unauthorized`, `invalid_query`, `partial`, and backend failures.

## Security

- Never commit credentials, private keys, tokens, real OCIDs, or unsanitized OCI payloads.
- Test fixtures must be synthetic and must not resemble actual customer data.
- Redact configured sensitive attributes before logging or returning results.
- Logs go to stderr for STDIO transport. Stdout is reserved for MCP protocol messages.
- Do not recommend `StrictHostKeyChecking=no` in SSH examples.
- Read-only mode must be enforced by a central policy with a drift-detection test.

## Verification

- Tests must run without OCI credentials or network access.
- Every OCI SDK call must be behind an injectable adapter or client factory.
- Each tool requires schema tests, success tests, limit tests, and error-mapping tests.
- Security-sensitive changes require tests proving that secrets and denied attributes do not leak.
- Live OCI tests must be opt-in and excluded from the default CI job.

## Documentation

- Update `docs/TOOL_CATALOG.md` whenever a public tool changes.
- Update `docs/SECURITY.md` whenever permissions, data handling, transport, or mutation behavior changes.
- Record material design decisions in the relevant design document before implementation.
- Add user-visible changes to `CHANGELOG.md`.
