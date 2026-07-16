# Development plan

## Delivery policy

Each milestone is a separate reviewable branch and pull request. No live OCI call is added without offline tests and documented IAM impact.

## M0 — design baseline

Deliverables:

- architecture and service boundaries;
- security and redaction model;
- least-privilege IAM guidance;
- tool catalogue and release slices;
- client setup design;
- GitHub workflow and repository conventions.

Exit criteria:

- documents agree on read-only scope;
- no credentials, real identifiers, or customer payloads;
- no executable OCI integration;
- stakeholder review completed before implementation.

## M1 — server foundation

Status: complete and merged; live test-domain validation remains opt-in.

Deliverables:

- official MCP SDK dependency and executable entry point;
- STDIO server with `instructions` guidance;
- typed settings and environment validation;
- config-file, instance-principal, and resource-principal signer factory;
- lazy OCI client factory;
- common response/error envelope;
- central tool classification and read-only guard;
- `get_current_context` and `test_connection`;
- lint, type-check, test, build, and secret-scan CI.

Tests:

- no-network startup and tool registration;
- signer selection with mocks;
- stdout protocol hygiene;
- tool classification drift test;
- error redaction;
- context masking;
- authentication and authorization error mapping.

Exit criteria:

- all tests run without OCI credentials;
- only two foundation tools are registered;
- package builds reproducibly;
- read-only is true by default.

## M2 — trace read path

Status: complete, merged, and live-validated against an approved non-production domain.

Deliverables:

- APM-domain list/get service;
- quick-pick list service;
- deterministic trace query builder;
- bounded expert query service;
- trace and span detail normalization;
- pagination and Oracle request IDs;
- redaction and payload limits.

Tests:

- query-builder golden tests;
- exact SDK request construction with mocks;
- pagination and truncation;
- no-data versus not-found;
- malformed query and invalid window;
- 401, 403, 404, 429, timeout, and 5xx mapping;
- sensitive attribute redaction.

Live acceptance tests, opt-in only:

- list a known test APM domain;
- run one small aggregate query;
- retrieve one synthetic test trace and span;
- verify the deployment identity cannot mutate APM.

The anonymized results are recorded in `M2_LIVE_ACCEPTANCE.md`. Server-layer mutation denial
passed; operators must continue to verify the deployed dynamic-group policy in OCI IAM.

## M3 — deterministic investigations

Status: complete and live-validated against an approved non-production domain.

Deliverables:

- latency investigation;
- error investigation;
- baseline/current comparison;
- fixed call budget and partial-substep reporting;
- deterministic next-step suggestions.

Exit criteria:

- workflows never exceed documented call and row budgets;
- conclusions link to trace/span evidence;
- partial failures remain usable and explicit;
- low-volume and zero-denominator comparisons are handled honestly.

Implementation budgets:

- latency: at most two OCI calls, up to 10 trace summaries, and up to 50 spans from one
  representative trace;
- errors: at most two OCI calls, a 50-trace search sample, up to 10 error-bearing summaries,
  and up to 50 spans from one representative trace;
- comparison: exactly two OCI calls and up to 50 newest trace summaries per window.

The anonymized validation results are recorded in `M3_LIVE_ACCEPTANCE.md`.

## M4 — synthetic read path

Status: monitor list/get and public vantage-point discovery are implemented in version 0.4.0;
opt-in live validation remains pending.

Deliverables:

- monitor list/get;
- public vantage-point list;
- bounded monitor execution result summaries;
- synthetic health summary after separate metric-path design.

The first M4 slice intentionally excludes `get_synthetic_monitor_result`. Oracle's endpoint
returns HAR, screenshots, console logs, network data, diagnostics, or script content directly;
fetching these artifacts merely to discard their contents would still expand the server's
sensitive-data and payload boundary. Result metadata requires a separately reviewed design.

Security gates:

- monitor secrets never appear;
- screenshots, HAR, console logs, network dumps, and script content remain excluded until separately designed;
- synthetic fixtures contain no real URLs or authentication material.

## M5 — production hardening

Deliverables:

- metadata-only audit events;
- documented retention and operations guidance;
- packaging and upgrade runbook;
- VM deployment guide;
- performance/load tests;
- compatibility matrix for supported MCP clients;
- security review and threat-model sign-off.

## M6 — optional writes

This milestone begins only after explicit approval.

Candidate scope:

- create/update/delete selected synthetic monitors;
- create/update/delete selected synthetic scripts.

Required first:

- separate write-enabled deployment identity;
- preview/execute protocol;
- short-lived operation-bound confirmation;
- idempotency/concurrency strategy;
- audit and rollback behavior;
- exhaustive denied-execution tests.

## Initial implementation backlog

1. Decide supported Python and dependency version ranges through a small compatibility spike.
2. Define typed response, warning, pagination, and error models.
3. Define configuration schema and masking rules.
4. Implement central tool registry/classification.
5. Implement signer and client factories with protocol interfaces.
6. Implement foundation tools and offline test harness.
7. Upgrade CI from the documentation gate to the full quality pipeline.

## Open decisions requiring stakeholder input

- Whether compartment selection is fixed at startup or discoverable at runtime.
- Approved sensitive-attribute policy and organization-specific redaction patterns.
- Whether expert raw query access is enabled by default.
- Maximum query windows and result limits after test-domain performance measurements.
