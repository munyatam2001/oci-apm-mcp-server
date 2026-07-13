# Changelog

All notable changes to this project will be documented here.

## Unreleased

### Added

- Documentation-first repository baseline.
- Proposed architecture, security model, IAM model, tool catalogue, client setup, and delivery plan.
- GitHub contribution and pull-request conventions.
- Stable MCP v1 server foundation using STDIO.
- Immutable, validated startup configuration with masked context output.
- Config-file, instance-principal, and resource-principal authentication providers.
- Lazy OCI APM control-plane client construction with explicit timeouts.
- Read-only `get_current_context` and `test_connection` tools.
- MCP read-only/idempotent/non-destructive annotations and policy drift checks.
- Safe OCI error normalization and allowlisted APM-domain output.
- Offline unit and registration tests plus Python 3.11/3.12 CI.
- Milestone 2 APM-domain list/get and Trace Explorer Quick Pick tools.
- Deterministic `find_traces` query construction with typed filters and escaping.
- Expert `run_trace_query`, disabled by default and constrained by syntax, field, time, and row policies.
- Normalized `get_trace` and `get_span` tools with bounded, redacted optional attributes.
- Summarized `get_trace_snapshot` output without raw stack frames or thread details.
- Pagination, normalized UTC windows, no-data responses, and Oracle request IDs.
- Eighty-six offline tests with more than 95% package coverage.

### Not yet implemented

- Synthetic-monitor operations and deterministic multi-call investigations.
- Any OCI mutation.
