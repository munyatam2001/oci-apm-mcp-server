# Security policy

## Supported versions

Security fixes are applied to the latest commit on `main`. The project has not yet published
a stable release series.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability, exposed credential, or sensitive
telemetry disclosure. Use GitHub's private vulnerability reporting feature from the
repository's **Security** tab after it is enabled for the public repository.

If private reporting is not available, contact the repository owner through the GitHub
profile without including exploit details, credentials, customer identifiers, or telemetry in
the initial message.

Include the affected commit or version, impact, reproduction steps using synthetic data, and
any proposed remediation. Never include real OCI credentials, OCIDs, or APM payloads.

## Deployment responsibility

Operators are responsible for applying least-privilege OCI IAM policies, restricting access
to instance-principal hosts, protecting SSH credentials, and reviewing trace data handling
before production use. See `docs/SECURITY.md` for the implementation security model.
