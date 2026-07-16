# OCI IAM setup

## 1. Principle

Use the smallest identity and compartment scope that supports the enabled tools. The first release needs read access only.

Oracle groups APM permissions under the `apm-domains` resource type. Trace queries, trace/span retrieval, APM-domain reads, synthetic monitor reads, monitor-result reads, scripts, and vantage-point reads are covered by APM read permissions. Synthetic changes require APM update permissions.

Reference: [Oracle APM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/apmpolicyreference.htm).

## 2. Recommended read-only policy

For a human user group:

```text
Allow group <group-name> to read apm-domains in compartment <compartment-name>
```

For an OCI Compute dynamic group using instance principals:

```text
Allow dynamic-group <dynamic-group-name> to read apm-domains in compartment <compartment-name>
```

Use tenancy scope only when cross-compartment APM investigation is an explicit product requirement:

```text
Allow group <group-name> to read apm-domains in tenancy
```

Tenancy-wide scope is not the default recommendation.

## 3. Optional compartment discovery

If the server must list compartment names rather than requiring a configured compartment OCID, the identity may also require permission to inspect compartments:

```text
Allow group <group-name> to inspect compartments in tenancy
```

For an instance principal, replace `group` with `dynamic-group`.

This permission should be omitted when deployment configuration supplies the compartment and APM-domain OCIDs directly.

## 4. Optional OCI Monitoring metrics

APM agents and synthetic monitoring publish selected metrics into OCI Monitoring. If a later tool queries those metric namespaces, add only the Monitoring permissions required by that tool, for example:

```text
Allow group <group-name> to read metrics in compartment <compartment-name>
```

This is not required for the Trace Explorer, synthetic monitor, or public-vantage-point tools.

## 5. Future synthetic writes

Oracle maps synthetic monitor and script changes to APM update permissions. A future write-enabled deployment may require:

```text
Allow dynamic-group <write-dynamic-group> to use apm-domains in compartment <compartment-name>
```

Do not upgrade the read-only deployment identity in place. Prefer a separate deployment identity, explicit server feature flag, and separate approval policy.

## 6. Prohibited broad permissions

The MCP documentation and installers must not recommend:

- `manage all-resources`;
- `manage apm-domains` for the read-only release;
- data-key generation permissions for ordinary investigation;
- tenancy-wide access when one compartment is sufficient.

## 7. Authentication modes

### Local development

- Use an OCI config profile already managed by the user.
- Accept config path and profile name only through startup configuration.
- Do not copy private keys into the repository.

### OCI Compute

- Use instance principals.
- Place the instance in a narrowly scoped dynamic group.
- Do not install a user API private key on the VM.

### Resource principal

- Defer until the deployment platform is selected.
- Document platform-specific dynamic-group and policy requirements in a separate deployment guide.

## 8. Validation checklist

- [ ] The identity can list the intended APM domains.
- [ ] The identity can run a small bounded trace query.
- [ ] The identity can retrieve one test trace and span.
- [ ] The identity can list synthetic monitors if that capability is enabled.
- [ ] The identity cannot create, update, or delete monitors in the read-only environment.
- [ ] The identity cannot list or manipulate APM data keys.
- [ ] Access is restricted to the intended compartment whenever possible.
