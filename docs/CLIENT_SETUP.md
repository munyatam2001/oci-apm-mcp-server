# MCP client setup

> These examples are design placeholders. The `oci-apm-mcp-server` executable does not exist until Milestone 1.

## 1. Local STDIO

STDIO will be the first supported transport.

After installation, the expected Codex command will be:

```bash
codex mcp add oci-apm --env OCI_APM_AUTH_TYPE=config_file --env OCI_CONFIG_PROFILE=DEFAULT -- oci-apm-mcp-server
```

Equivalent project-scoped Codex configuration:

```toml
[mcp_servers.oci_apm]
command = "/absolute/path/to/venv/bin/oci-apm-mcp-server"
env_vars = ["OCI_APM_AUTH_TYPE", "OCI_CONFIG_FILE", "OCI_CONFIG_PROFILE", "OCI_REGION", "OCI_APM_COMPARTMENT_ID", "OCI_APM_DOMAIN_ID"]
startup_timeout_sec = 15
tool_timeout_sec = 90
required = false
default_tools_approval_mode = "writes"
```

The final implementation will document exact variable names and defaults. Credentials and private-key contents will never be placed directly in MCP configuration.

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

Names remain provisional until Milestone 1:

| Variable | Purpose |
|---|---|
| `OCI_APM_AUTH_TYPE` | `config_file`, `instance_principal`, or `resource_principal` |
| `OCI_CONFIG_FILE` | Local OCI config path |
| `OCI_CONFIG_PROFILE` | OCI config profile |
| `OCI_REGION` | Effective OCI region |
| `OCI_APM_COMPARTMENT_ID` | Default bounded compartment |
| `OCI_APM_DOMAIN_ID` | Default APM domain |
| `OCI_APM_READ_ONLY` | Must default to true |
| `OCI_APM_LOG_LEVEL` | Application log level without payload logging |

## 6. Client verification

After Milestone 1:

1. Start the MCP server.
2. Confirm the client lists `test_connection` and `get_current_context` only.
3. Call `get_current_context` and verify masked scope and read-only status.
4. Call `test_connection` against a test compartment/domain.
5. Confirm no credentials or raw OCI configuration appear in the result or logs.
