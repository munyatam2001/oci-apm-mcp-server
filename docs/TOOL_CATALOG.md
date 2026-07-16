# Tool catalogue

## 1. Catalogue rules

This document is the public contract. M1 and M2 tools are implemented; later milestone sections remain planned.

Each tool will return the common response envelope defined in `ARCHITECTURE.md`. Tool-specific content is placed in `data`. Every result includes explicit scope, timing, warnings, pagination, and partial-result metadata when applicable.

Time inputs use RFC 3339 UTC timestamps. Convenience durations may be accepted, but the normalized absolute window must be returned.

## 2. Release slices

### M1 foundation

#### `test_connection`

Purpose: validate signer creation and make the smallest safe APM read required to confirm connectivity.

Inputs:

- optional `region`;
- optional configured `apm_domain_id`.

Returns authentication mode, effective region, permission checks, and safe troubleshooting guidance. It must not return credential fields.

Classification: read-only, idempotent.

#### `get_current_context`

Purpose: show effective startup configuration relevant to tool execution.

Returns region, compartment OCID in masked form, APM domain OCID in masked form, auth mode, read-only state, and configured limits.

Classification: read-only, idempotent, no OCI call required.

### M2 trace read path

Status: implemented in version 0.2.0. Live calls remain opt-in and must use a non-production test domain first.

#### `list_apm_domains`

Purpose: list accessible APM domains in one configured compartment.

Inputs:

- `compartment_id` when not fixed by deployment configuration;
- optional `display_name` filter;
- `limit` and `page`.

Default limit: 50. Maximum: 200.

Classification: read-only, idempotent.

#### `get_apm_domain`

Purpose: retrieve safe metadata for one APM domain.

Inputs: `apm_domain_id`.

The normalized result must exclude data-key values. If the OCI model includes unrelated sensitive configuration in the future, the response schema must remain allowlist-based.

Classification: read-only, idempotent.

#### `list_apm_quick_picks`

Purpose: list Oracle-provided predefined Trace Explorer queries for the selected APM domain.

Inputs: `apm_domain_id`, `limit`, and `page`.

Classification: read-only, idempotent.

#### `find_traces`

Purpose: find traces through a deterministic builder without requiring APM query syntax.

Proposed inputs:

- `apm_domain_id`;
- `start_time`, `end_time`;
- optional `service_name`, `operation_name`, `status`, `error_type`;
- optional `minimum_duration_ms`;
- optional `trace_id`;
- `sort_by`: `start_time`, `duration`, or `error_count`;
- `sort_order`: `asc` or `desc`;
- `limit` and `page`.

Defaults: last hour, duration descending, 50 rows. Maximum raw window: 24 hours. Maximum rows: 200.

Returns a summary-safe trace representation: trace ID, service, operation, start/end, duration, status, error count, span count, and redaction/truncation metadata.

Classification: read-only, idempotent.

#### `run_trace_query`

Purpose: expert escape hatch for OCI APM Defined Query Syntax.

Inputs:

- `apm_domain_id`;
- explicit `start_time`, `end_time`;
- `query`;
- `limit` and `page`.

The server validates query length, window, limit, and supported query category. It returns selected/aggregated fields rather than arbitrary internal OCI objects.

This tool is registered but disabled by default. Set `OCI_APM_ENABLE_EXPERT_QUERY=true` only for an approved deployment. Sensitive fields and `BETWEEN` clauses remain blocked.

Default limit: 50. Maximum: 500 for aggregated results and 200 for raw results. Maximum window: 7 days for aggregate queries, 24 hours for raw queries.

Classification: read-only, idempotent, potentially expensive.

#### `get_trace`

Purpose: retrieve one trace and its normalized spans.

Inputs:

- `apm_domain_id`;
- `trace_id`;
- optional trace start window when required for disambiguation;
- `include_span_attributes` defaulting to `false`;
- `max_spans` defaulting to 100 and capped at 500.

Sensitive attributes remain redacted. The response states omitted span and attribute counts.

Classification: read-only, idempotent, sensitive-data capable.

#### `get_span`

Purpose: retrieve one span within a trace.

Inputs: `apm_domain_id`, `trace_id`, `span_id`, and optional `include_attributes`.

Logs, request/response bodies, SQL text, and complete stack traces are excluded from the first implementation.

Every normalized span reports `logs_returned=false`. `logs_omitted=true` means source log
entries existed and were removed; `logs_omitted=false` means no source log entries were present.

Classification: read-only, idempotent, sensitive-data capable.

#### `get_trace_snapshot`

Purpose: retrieve summarized thread/trace snapshot data for advanced latency diagnosis.

Inputs: `apm_domain_id`, `trace_id`, optional `thread_id`, optional `snapshot_time`, and `summarized=true` by default.

Full snapshot expansion is deferred until payload size and stack-frame redaction are validated.

Classification: read-only, idempotent, potentially large.

### M3 investigation workflows

#### `investigate_latency`

Purpose: bounded first-pass analysis of slow services or operations.

Inputs: `apm_domain_id`, time window, optional service/operation, percentile or minimum duration, and `top_n` capped at 10.

Internal steps may compare service/operation latency, find representative slow traces, identify dominant spans, and propose evidence-based next steps. The workflow has a fixed OCI-call budget and reports partial substeps.

Classification: read-only, idempotent, multi-call.

#### `investigate_errors`

Purpose: bounded first-pass analysis of error traces.

Inputs: `apm_domain_id`, time window, optional service/operation/error type, and `top_n` capped at 10.

Returns error groups, affected services/operations, representative trace IDs, timing, and next steps. It does not claim root cause without supporting span evidence.

Classification: read-only, idempotent, multi-call.

#### `compare_trace_windows`

Purpose: compare the same deterministic trace aggregation across a current and baseline window.

Inputs: filters plus two explicit, equal or clearly documented windows.

Returns counts, latency/error deltas, denominator warnings, and confidence limitations. Division-by-zero and low-volume cases must be explicit.

Classification: read-only, idempotent, multi-call.

### M4 synthetic read path

#### `list_synthetic_monitors`

Purpose: list synthetic monitors in an APM domain.

Inputs: `apm_domain_id`, optional name/type/status filters, `limit`, and `page`.

The result excludes embedded secrets and secret parameter values.

Classification: read-only, idempotent.

#### `get_synthetic_monitor`

Purpose: retrieve safe configuration and status for one monitor.

Inputs: `apm_domain_id`, `monitor_id`.

Authentication values, client private keys, wallets, and secret script parameters are excluded.

Classification: read-only, idempotent, sensitive-configuration capable.

#### `get_synthetic_monitor_result`

Purpose: retrieve normalized output for one monitor execution.

Inputs: `apm_domain_id`, `monitor_id`, `execution_time`, `vantage_point`, and requested result type when required by Oracle's API.

Screenshots, HAR files, console logs, network details, and script content are not returned in the first implementation. Initially return execution metadata and bounded diagnostic summaries only.

Classification: read-only, idempotent, sensitive-data capable.

#### `list_public_vantage_points`

Purpose: list public APM vantage points available to the domain.

Inputs: `apm_domain_id`, optional capability filters, `limit`, and `page`.

Classification: read-only, idempotent.

#### `summarize_synthetic_health`

Purpose: summarize availability and latency for selected monitors over a bounded period.

This may combine APM synthetic configuration/result APIs with OCI Monitoring metrics only after the metric path is separately designed and permission-tested.

Classification: read-only, idempotent, multi-call.

## 3. Deferred mutations

The following are not part of the read-only release:

- `create_synthetic_monitor`;
- `update_synthetic_monitor`;
- `delete_synthetic_monitor`;
- `create_synthetic_script`;
- `update_synthetic_script`;
- `delete_synthetic_script`;
- scheduled-query management;
- APM configuration mutation.

APM-domain deletion and data-key generation/removal are explicitly excluded from the planned agent-facing surface.

## 4. Tool-count discipline

Only tools belonging to the active milestone should be registered. Documentation may describe future tools, but clients should not see placeholder or nonfunctional tools.
