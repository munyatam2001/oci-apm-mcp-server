# Architecture

## 1. Scope

The server provides MCP tools for reading and investigating OCI APM data. The first release covers APM-domain discovery, trace queries, trace/span details, and selected synthetic-monitor reads.

The first release does not create, update, or delete OCI resources.

## 2. System context

```text
MCP client
  -> MCP transport (STDIO initially; Streamable HTTP later)
    -> tool registration and policy layer
      -> typed application services
        -> deterministic query builders
          -> OCI SDK client adapters
            -> OCI APM APIs
```

Supporting cross-cutting components provide configuration, authentication, pagination, error normalization, redaction, audit metadata, and request timing.

## 3. OCI SDK boundaries

The implementation should mirror Oracle's service boundaries rather than creating one oversized client:

| Concern | OCI Python SDK client | Initial use |
|---|---|---|
| APM domains | `oci.apm_control_plane.ApmDomainClient` | List and get domains only |
| Trace queries | `oci.apm_traces.QueryClient` | Quick picks and bounded queries |
| Trace details | `oci.apm_traces.TraceClient` | Trace, span, and snapshot details |
| Synthetics | `oci.apm_synthetics.ApmSyntheticClient` | Allowlisted monitor and public-vantage-point reads |
| Identity | `oci.identity.IdentityClient` | Optional compartment discovery |

Client construction belongs in one injectable factory. Services receive narrow client protocols so tests never require the OCI SDK network path.

## 4. Proposed modules

| Module | Responsibility |
|---|---|
| `server.py` | MCP initialization, instructions, tool registration, transport selection |
| `config.py` | Validated environment/file configuration with safe defaults |
| `auth.py` | Config-file, instance-principal, and resource-principal signers |
| `client_factory.py` | Lazy, region-aware OCI client construction |
| `schemas.py` | Typed tool inputs, result envelope, pagination, warnings, errors |
| `errors.py` | OCI exception classification and safe user messages |
| `guardrails.py` | Read-only classification, limits, time-window policy, query validation |
| `sanitize.py` | Attribute allow/deny rules and secret/PII redaction |
| `pagination.py` | Consistent page-token and truncation behavior |
| `domain_service.py` | APM-domain and optional compartment discovery |
| `trace_query_builder.py` | Deterministic APM query construction |
| `trace_service.py` | Query execution and trace/span normalization |
| `synthetic_service.py` | Allowlisted synthetic monitor and public-vantage-point reads |
| `investigation_service.py` | Bounded multi-step diagnostic workflows |
| `audit.py` | Metadata-only audit events; no raw sensitive payloads |

## 5. Tool-layer policy

Primitive tools expose stable OCI concepts. Workflow tools orchestrate primitive services internally; they do not recursively call MCP tools.

Every tool must declare:

- read-only or mutating classification;
- idempotency characteristics;
- required scope;
- default and maximum time range;
- default and maximum result limit;
- pagination behavior;
- potential sensitive fields;
- expected latency and number of OCI calls.

The MCP server `instructions` field will state the global workflow: discover scope, ask for missing scope, prefer bounded investigation tools, avoid broad raw queries, and obtain approval before any future mutation.

## 6. Query strategy

Two trace-query paths are required:

1. **Deterministic path:** `find_traces` and investigation tools accept typed filters such as service, operation, status, minimum duration, and time window. A builder generates valid APM Defined Query Syntax.
2. **Expert path:** `run_trace_query` accepts query text but validates length, time range, row limit, and forbidden constructs before execution.

Natural language must never be sent directly to OCI as query text. The model selects a tool and structured arguments; the server owns final query construction.

## 7. Request lifecycle

1. Validate configuration and tool input.
2. Resolve explicit or configured region and APM domain.
3. Apply read-only and query guardrails before creating an OCI request.
4. Construct a deterministic query when applicable.
5. Call the narrow OCI client with a request ID and bounded timeout.
6. Normalize OCI models into stable project schemas.
7. Redact sensitive attributes.
8. Apply result limits and return pagination state.
9. Attach warnings, partial-result status, request timing, and suggested next steps.
10. Record metadata-only audit information.

## 8. Response envelope

```json
{
  "status": "success",
  "request_id": "oracle-request-id",
  "scope": {
    "region": "ap-mumbai-1",
    "apm_domain_id": "ocid1.apmdomain..."
  },
  "time_window": {
    "start": "2026-07-13T08:00:00Z",
    "end": "2026-07-13T09:00:00Z"
  },
  "data": {},
  "pagination": {
    "next_page": null,
    "truncated": false
  },
  "warnings": [],
  "next_steps": [],
  "partial": false,
  "timing_ms": 420
}
```

Valid status values should include `success`, `no_data`, `needs_clarification`, `invalid_request`, `unauthorized`, `not_found`, `rate_limited`, `partial`, and `error`.

## 9. State model

The initial server is stateless across calls except for immutable process configuration and bounded in-memory caches. It will not learn user preferences or persist query history.

Optional caches must:

- have short TTLs;
- key by tenancy, region, and APM domain;
- store only discovery metadata;
- never store trace payloads, headers, SQL, logs, or data keys.

## 10. Transport and deployment

STDIO is the first supported transport because it has the smallest exposed network surface. It can run locally or on an OCI VM reached through an SSH command that preserves MCP stdio.

Streamable HTTP is deferred until authentication, TLS, origin/network controls, health checks, and deployment ownership are defined. It must not be exposed as an unauthenticated public endpoint.

## 11. Failure model

OCI exceptions will be normalized without leaking request payloads or credentials:

- 400: invalid input or invalid query;
- 401: authentication failure;
- 403: authorization or compartment/APM-domain scope failure;
- 404: domain, trace, span, monitor, or execution not found;
- 409/412: future mutation conflict;
- 429: rate limited, with safe retry guidance;
- 5xx/timeouts: backend or network failure with Oracle request ID when available.

Empty results are not errors. Partial OCI responses must remain explicitly partial.
