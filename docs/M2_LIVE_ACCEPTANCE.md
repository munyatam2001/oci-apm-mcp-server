# Milestone 2 live acceptance

## Scope

The M2 read path was validated on 2026-07-16 against an approved non-production OCI APM
domain. The deployment used an OCI Compute instance principal and an SSH-connected local
Codex client. No credentials, complete OCIDs, trace identifiers, domain names, application
routes, customer payloads, or screenshots are retained in this report.

## Results

| Check | Outcome | Notes |
|---|---|---|
| MCP startup over SSH STDIO | Passed | The client registered all ten M2 tools. |
| Safe current context | Passed | Instance-principal auth and fixed read-only scope were reported; identifiers were masked. |
| APM domain connection | Passed | The configured non-production domain was reachable and active. |
| Quick Pick listing | Passed (`no_data`) | The domain had no configured Quick Picks; the result was explicit and non-failing. |
| Narrow trace search | Passed (`no_data`) | A short window returned no traces without truncation or warnings. |
| Bounded trace search | Passed | A wider window with a ten-row limit returned summary-only trace results. |
| Trace retrieval | Passed | A selected trace returned all available spans under the requested cap with attributes excluded. |
| Span retrieval | Passed | A selected span returned safe timing, relationship, kind, and error metadata. |
| Error-path retrieval | Passed | Span-level errors were preserved even when the parent trace reported an overall success status. |
| Snapshot retrieval | Passed (`no_data`) | No snapshot data existed; raw stack, thread, and snapshot-detail values remained excluded. |
| Read-only server enforcement | Passed | The registry exposed no mutation tools; scope override and expert query features remained disabled. |

## Observations carried into M3

- Overall trace status is not sufficient for error investigation. Workflows must also evaluate
  trace error counts and span-level error markers.
- `no_data` from a short window, Quick Picks, or snapshots is a valid operational outcome and
  must not be reported as a backend failure.
- Investigation workflows should start with a narrow window and expand only when the response
  is empty and the caller's approved scope allows it.
- Timing and error markers support evidence statements, but they do not establish root cause
  without additional safe attributes or logs.

## Remaining operational control

The MCP server cannot mutate OCI resources and the documented deployment policy grants only
`read apm-domains`. Operators remain responsible for verifying the deployed dynamic-group
policy in OCI IAM and restricting SSH access to the instance-principal host.
