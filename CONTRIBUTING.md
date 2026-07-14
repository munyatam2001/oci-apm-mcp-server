# Contributing

The project is under active development. Changes should remain small, reviewable, and tied to
a documented milestone. By submitting a contribution, you agree that it is licensed under the
Apache License 2.0.

## Before opening a pull request

1. Read `AGENTS.md` and the relevant design documents.
2. Confirm that the change does not expand the approved OCI permission boundary.
3. Add or update offline tests for every behavior change.
4. Confirm that no real OCI identifiers, credentials, or trace payloads are present.
5. Update the tool catalogue and changelog when public behavior changes.

## Branches and commits

- Branch from `main` using `docs/`, `feat/`, `fix/`, `test/`, or `chore/` prefixes.
- Keep commits focused and use imperative summaries.
- Do not mix broad formatting changes with functional changes.
- Do not commit generated artifacts, local configuration, or credentials.

## Pull requests

Pull requests must describe:

- the user outcome;
- the tools or components affected;
- OCI permissions required;
- data-handling implications;
- tests performed;
- rollback considerations.

OCI mutations require a dedicated design review and must not be bundled into a read-only feature pull request.

Report suspected vulnerabilities through the private process described in `SECURITY.md`, not
through a public issue.
