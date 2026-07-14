# GitHub workflow

## Repository recommendation

- Name: `oci-apm-mcp-server`
- Visibility: private until the public-release checklist is complete.
- Default branch: `main`.
- No direct pushes to `main` after the design baseline.
- Require pull requests and passing CI before merge.
- Prefer squash merge for one coherent change per pull request.

## Initial branch sequence

1. `docs/design-baseline`
2. `feat/server-foundation`
3. `feat/trace-read-path`
4. `feat/investigation-workflows`
5. `feat/synthetic-read-path`
6. `chore/production-hardening`

Mutations must use separate branches and pull requests after explicit approval.

## Recommended protections

- Require at least one reviewer.
- Dismiss stale approvals when new commits are pushed.
- Require conversation resolution.
- Require status checks.
- Block force pushes and branch deletion on `main`.
- Enable secret scanning and push protection where available.
- Enable dependency alerts after runtime dependencies are introduced.

## CI evolution

### Design phase

- required-document checks;
- common credential-file rejection.

### Implementation phase

- Ruff lint/format check;
- mypy strict type checking;
- pytest with coverage;
- package build;
- secret scanning;
- dependency review on pull requests;
- optional CodeQL if repository policy supports it.

Live OCI tests must never run on ordinary pull requests. They require a protected environment, non-production APM domain, restricted identity, and explicit manual approval.

## Commit plan

Recommended initial history:

1. `docs: establish OCI APM MCP design baseline`
2. `build: add MCP server foundation and offline CI`
3. `feat: add bounded APM trace discovery`
4. `feat: add trace and span drill-down`
5. `feat: add deterministic APM investigations`
6. `feat: add synthetic monitoring read tools`

## Repository creation checklist

- [x] Confirm GitHub owner: `munyatam2001`.
- [x] Confirm private initial visibility and planned public visibility.
- [x] Choose Apache License 2.0.
- [x] Confirm repository name.
- [x] Create the remote and review the complete Git history.
- [x] Add the remote and merge the design baseline through M2.
- [ ] Configure branch protection and security features.
- [ ] Record the first tagged design baseline after approval.

## Public-release checklist

- [x] Review the current tree and complete Git history for credentials, real OCIDs, customer
  telemetry, and proprietary payloads.
- [x] Add an open-source license, contribution terms, an independence disclaimer, and a
  security-reporting policy.
- [x] Add automated dependency update configuration.
- [x] Document public cloning without placing GitHub or OCI credentials in deployment files.
- [ ] Confirm organizational or employer approval to publish, when applicable.
- [ ] Review GitHub Actions logs before the visibility change; public repositories expose the
  existing workflow history.
- [ ] Change repository visibility only after this checklist is approved.
- [ ] Enable private vulnerability reporting, secret scanning, push protection, Dependabot
  alerts, and branch protection immediately after the repository becomes public.
- [ ] Verify anonymous HTTPS clone from a clean environment.

## Sensitive data rules

Never place the following in issues, pull requests, CI logs, or repository files:

- OCI private keys, fingerprints, tokens, or config contents;
- real APM data keys;
- complete OCIDs from production;
- raw trace/span payloads;
- customer URLs, SQL, headers, cookies, user IDs, or stack traces;
- synthetic scripts or parameters containing authentication material.
