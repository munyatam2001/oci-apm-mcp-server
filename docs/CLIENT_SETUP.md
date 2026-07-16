# MCP client setup

> The first Milestone 4 executable exposes sixteen read-only context, domain, query, trace,
> span, investigation, synthetic-monitor, and public-vantage-point tools.

## 1. Local STDIO

STDIO will be the first supported transport.

After installation, add it to Codex with:

```bash
codex mcp add oci-apm --env OCI_APM_AUTH_TYPE=config_file --env OCI_CONFIG_PROFILE=DEFAULT -- oci-apm-mcp-server
```

Equivalent project-scoped Codex configuration:

```toml
[mcp_servers.oci_apm]
command = "/absolute/path/to/venv/bin/oci-apm-mcp-server"
env_vars = ["OCI_APM_AUTH_TYPE", "OCI_CONFIG_FILE", "OCI_CONFIG_PROFILE", "OCI_REGION", "OCI_APM_COMPARTMENT_ID", "OCI_APM_DOMAIN_ID", "OCI_APM_ENABLE_EXPERT_QUERY"]
startup_timeout_sec = 15
tool_timeout_sec = 90
required = false
default_tools_approval_mode = "writes"
```

Credentials and private-key contents must never be placed directly in MCP configuration.

## 2. OCI VM through SSH STDIO

An OCI VM deployment should use instance principals. A local MCP client may start the remote process through SSH:

```toml
[mcp_servers.oci_apm]
command = "ssh"
args = [
  "-i", "/absolute/path/to/approved-key",
  "-o", "ServerAliveInterval=60",
  "-o", "ServerAliveCountMax=3",
  "opc@approved-hostname",
  "cd /opt/oci-apm-mcp-server && . venv/bin/activate && exec oci-apm-mcp-server"
]
startup_timeout_sec = 20
tool_timeout_sec = 120
```

Requirements:

- verify and retain the server host key;
- do not use `StrictHostKeyChecking=no`;
- restrict the SSH key and OS account;
- use instance principals rather than copying OCI user API keys to the VM;
- keep MCP logs on stderr and protocol messages on stdout.

## 3. Streamable HTTP

Streamable HTTP is deferred. It will require a deployment design covering TLS, authentication, authorization, request limits, network exposure, health checks, and operational ownership.

It must not be published as an unauthenticated public endpoint.

## 4. Configuration precedence

Proposed precedence, highest first:

1. explicit startup environment;
2. explicitly selected server configuration file;
3. safe built-in defaults.

MCP tool arguments do not change authentication mode or credential location.

## 5. Expected startup variables

Supported startup variables:

| Variable | Purpose |
|---|---|
| `OCI_APM_AUTH_TYPE` | `config_file`, `instance_principal`, or `resource_principal` |
| `OCI_CONFIG_FILE` | Local OCI config path |
| `OCI_CONFIG_PROFILE` | OCI config profile |
| `OCI_REGION` | Effective OCI region |
| `OCI_APM_COMPARTMENT_ID` | Default bounded compartment |
| `OCI_APM_DOMAIN_ID` | Default APM domain |
| `OCI_APM_ALLOW_SCOPE_OVERRIDE` | Permit tool arguments to replace configured scope; defaults false |
| `OCI_APM_ENABLE_EXPERT_QUERY` | Enable validated `run_trace_query`; defaults false |
| `OCI_APM_READ_ONLY` | Must default to true |
| `OCI_APM_LOG_LEVEL` | Application log level without payload logging |

## 6. Client verification

1. Start the MCP server.
2. Confirm the client lists the sixteen implemented tools documented in `TOOL_CATALOG.md`.
3. Call `get_current_context` and verify masked scope and read-only status.
4. Call `test_connection` against a test compartment/domain.
5. Run `find_traces` over a narrow test window, then retrieve one synthetic test trace/span.
6. Confirm no credentials, raw OCI configuration, logs, SQL, stack frames, or restricted attributes appear in results or logs.
