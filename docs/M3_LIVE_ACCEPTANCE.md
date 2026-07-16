# Milestone 3 live acceptance

## Scope

The M3 deterministic investigation workflows were validated on 2026-07-17 against an
approved non-production OCI APM domain. The server used an OCI Compute instance principal
and an SSH-connected local Codex client. No credentials, complete OCIDs, trace or span
identifiers, domain names, application routes, customer payloads, or screenshots are retained
in this report.

## Results

| Check | Outcome | Notes |
|---|---|---|
| Latency workflow | Passed | A 24-hour search returned five duration-ranked trace summaries and one representative trace. |
| Latency call budget | Passed | One bounded search and one representative trace read were used. |
| Latency evidence | Passed | Longest-span timing was returned without attributes, logs, or a root-cause claim. |
| Error workflow | Passed | Error-bearing traces were selected from a bounded 50-trace sample. |
| Overall-success edge case | Passed | Span-level errors remained visible when the parent trace reported overall success. |
| Error call budget | Passed | One bounded search and one representative trace read were used. |
| Error evidence | Passed | Error-span relationships and timing were reported without unsupported causal claims. |
| Window comparison | Passed | Two explicit, equal 24-hour windows were compared with at most 50 newest traces per window. |
| Empty-window handling | Passed | Missing observations produced unavailable rates and duration statistics rather than invented values. |
| Zero-denominator handling | Passed | Percentage deltas from a zero baseline remained explicitly unavailable. |
| Sample-cap handling | Passed | A sample reaching its 50-trace cap was identified as a bounded sample, not a population aggregate. |
| Low-volume warning | Passed | A window with fewer than ten returned traces produced a caution. |
| Read-only enforcement | Passed | All three workflows composed existing read operations and exposed no mutation path. |

## Operational conclusions

- The latency and error workflows remained within their fixed two-call budgets.
- Error investigation correctly evaluates span-error counts rather than relying only on the
  overall trace status.
- Comparison metrics describe bounded newest-trace samples. They must not be interpreted as
  full-window traffic or population-level latency and error rates.
- Empty samples, zero denominators, and capped samples are valid operational outcomes and are
  surfaced explicitly.
- Timing, overlap, hierarchy, and error markers provide investigation evidence but do not by
  themselves establish root cause.

## Remaining operational control

Live validation confirms the server-layer behavior, not the complete OCI tenancy policy.
Operators remain responsible for least-privilege dynamic-group policies, SSH host access, and
confidential handling of trace identifiers and application operation names.
