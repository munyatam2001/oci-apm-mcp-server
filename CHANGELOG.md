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

### Not yet implemented

- Trace, span, and synthetic-monitor operations.
- Any OCI mutation.
