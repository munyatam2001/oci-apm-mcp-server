# Security model

## 1. Security objective

Allow useful APM investigation while minimizing the chance that an MCP client can expose sensitive telemetry, run unbounded queries, or change OCI resources.

## 2. Trust boundaries

- The MCP client and model are untrusted callers.
- Tool arguments are untrusted input.
- Trace/span attributes and logs are potentially sensitive data.
- OCI credentials and signers must remain inside the server process.
- OCI APIs and network responses are external dependencies.
- A remote MCP transport creates a separate authentication and network boundary.

## 3. Data classification

APM data may contain:

- service and host names;
- URLs and query parameters;
- HTTP headers;
- user, tenant, session, request, or trace identifiers;
- database names and SQL text;
- exception messages and stack traces;
- custom span attributes;
- synthetic scripts and authentication configuration.

All trace content is confidential by default. The server must minimize, filter, and redact before returning or logging it.

## 4. Non-negotiable controls

- Default server mode is read-only.
- Central tool classification controls every registered tool.
- A drift test fails if a tool lacks a classification.
- APM data-key values are never retrieved for ordinary operations and never exposed.
- Raw tool arguments and OCI payloads are not written to debug logs.
- Stdout is reserved for the MCP protocol under STDIO.
- OCI SDK calls use explicit timeouts and bounded retries.
- Tool results use row, span, attribute, and payload-size limits.
- Result metadata states when truncation or redaction occurred.
- Errors retain Oracle request IDs but remove credentials and sensitive payload content.

## 5. Query guardrails

Proposed defaults, subject to validation during Milestone 2:

| Query class | Default window | Maximum window | Default rows | Maximum rows |
|---|---:|---:|---:|---:|
| Raw trace rows | 1 hour | 24 hours | 50 | 200 |
| Aggregated trace query | 1 hour | 7 days | 50 | 500 |
| Investigation workflow | 1 hour | 24 hours | bounded internally | no raw expansion beyond 200 |
| Synthetic monitor listing | n/a | n/a | 50 | 200 |

Broadening past a maximum must produce a structured validation response; the server must not silently clamp a user request without warning.

The raw query tool must reject excessive query length, missing time bounds, unsupported query categories, and any syntax classified as mutating by future API evolution.

## 6. Redaction policy

The implementation will combine:

1. a safe attribute allowlist for summary tools;
2. configurable deny patterns for expert detail tools;
3. value-level patterns for tokens, authorization headers, cookies, passwords, private keys, email addresses, and other organization-approved sensitive data;
4. maximum string lengths and maximum attributes per span;
5. clear `redacted_fields` and `truncated_fields` metadata.

Default-denied names should include, case-insensitively:

- `authorization`, `proxy-authorization`, `cookie`, `set-cookie`;
- `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`;
- `private_key`, `client_secret`, `session`;
- synthetic script parameters marked secret.

SQL text, stack traces, logs, request bodies, response bodies, and custom attributes require explicit tool support and separate limits.

## 7. Authentication

Supported signer types:

- OCI config-file signer for local development;
- instance principal for an OCI Compute deployment;
- resource principal for a future OCI Functions or similar deployment.

Credentials are never accepted as MCP tool arguments. Configuration selects an auth mode at process startup.

## 8. Authorization

The read-only release should receive only `read apm-domains` within the smallest practical compartment. Tenancy-wide discovery is optional and should be disabled by default.

Future synthetic-monitor writes require a separate deployment identity with `use apm-domains`; they should not be enabled merely by changing a tool argument.

## 9. Mutation safety

When mutations are introduced, all of the following are required:

- separate server feature flag disabled by default;
- accurate MCP mutation annotations;
- central read-only guard;
- preview and execute stages;
- short-lived, operation-bound confirmation token;
- optimistic concurrency or idempotency protection where supported;
- metadata-only audit record;
- separate tests proving no mutation occurs during preview or denied execution.

Deleting APM domains and generating/removing APM data keys remain out of scope.

## 10. Transport security

### STDIO

- Preferred for the first release.
- Local process permissions protect configuration and credentials.
- Remote SSH configurations must verify host keys.

### Streamable HTTP

Before enabling:

- TLS is mandatory outside localhost;
- authentication must be defined and tested;
- network exposure must be restricted;
- forwarded headers and origins must be validated;
- rate limiting and request-size limits must be enforced;
- health endpoints must reveal no configuration or identity details.

## 11. Audit policy

Audit events may contain:

- timestamp, tool name, outcome, duration;
- calling user/session pseudonym when available;
- region and hashed or truncated resource identifier;
- OCI request ID;
- row count, redaction count, and partial-result flags.

Audit events must not contain raw trace/span payloads, query results, headers, SQL, secrets, or data keys.

## 12. Security verification

Required tests include:

- every tool is classified;
- all mutations are blocked in read-only mode;
- forbidden attributes and value patterns are redacted;
- redaction also applies to errors, warnings, logs, and audit records;
- max windows, rows, attributes, and payload sizes are enforced before OCI execution where possible;
- OCI errors do not leak request bodies or credentials;
- fixtures contain no credential-like data or real OCID patterns;
- STDIO logs never write to stdout.
