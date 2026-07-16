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
- Ninety-six offline tests with more than 93% package coverage.
- Apache License 2.0 and public contribution/security-reporting guidance.
- Oracle Linux VM deployment guidance for instance-principal authentication and SSH STDIO.
- Dependabot configuration for Python packages and GitHub Actions.
- Reviewed public repository release with protected `main`, secret scanning, push protection,
  dependency security updates, and private vulnerability reporting.
- Anonymized M2 live-acceptance evidence for the SSH and instance-principal deployment path.
- Deterministic `investigate_latency` and `investigate_errors` workflows with a fixed two-call
  budget, representative trace evidence, and partial-result reporting.
- Deterministic `compare_trace_windows` workflow with two bounded newest-trace samples,
  explicit sample limitations, low-volume warnings, and zero-denominator handling.

### Changed

- Normalized spans now state `logs_returned=false` explicitly; `logs_omitted` only indicates
  whether source log entries existed and were removed.

### Not yet implemented

- Synthetic-monitor operations.
- Any OCI mutation.
