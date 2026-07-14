# Oracle Linux VM deployment

This guide deploys the read-only STDIO server on an OCI Compute instance and starts it from a
local Codex client through SSH. It does not expose an MCP network port.

## 1. OCI authorization

Place only the approved VM in an OCI dynamic group. A matching rule scoped to one instance is:

```text
instance.id = '<vm-instance-ocid>'
```

Grant the dynamic group read access to APM in the smallest practical compartment:

```text
Allow dynamic-group <dynamic-group-name> to read apm-domains in compartment <compartment-name>
```

Do not install an OCI user API key on the VM. Anyone who can access the VM may inherit the
instance-principal permissions, so restrict SSH access accordingly.

## 2. Runtime installation

Python 3.11 or newer is required. On Oracle Linux 9.4 or newer, install Python 3.12 explicitly:

```bash
sudo dnf install -y git python3.12 python3.12-pip
```

Clone the public repository after its visibility has been changed:

```bash
sudo mkdir -p /opt/oci-apm-mcp-server
sudo chown opc:opc /opt/oci-apm-mcp-server
git clone https://github.com/munyatam2001/oci-apm-mcp-server.git /opt/oci-apm-mcp-server
```

Install the server in an isolated environment:

```bash
cd /opt/oci-apm-mcp-server
python3.12 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install .
```

## 3. Runtime configuration

Create `/opt/oci-apm-mcp-server/runtime.env` without committing it:

```bash
export OCI_APM_AUTH_TYPE=instance_principal
export OCI_REGION='<oci-region>'
export OCI_APM_COMPARTMENT_ID='<apm-compartment-ocid>'
export OCI_APM_DOMAIN_ID='<apm-domain-ocid>'
export OCI_APM_ALLOW_SCOPE_OVERRIDE=false
export OCI_APM_ENABLE_EXPERT_QUERY=false
export OCI_APM_READ_ONLY=true
export OCI_APM_LOG_LEVEL=INFO
```

Protect the file:

```bash
chmod 600 /opt/oci-apm-mcp-server/runtime.env
```

The configured OCIDs are not credentials, but they still identify deployment scope and must
not be committed to the public repository.

## 4. Local Codex connection

Connect manually once to verify and retain the VM host key. Then add the server to the local
Codex configuration:

```toml
[mcp_servers.oci_apm]
command = "ssh"
args = [
  "-i", "/absolute/local/path/to/approved-vm-key",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=yes",
  "-o", "ServerAliveInterval=60",
  "-o", "ServerAliveCountMax=3",
  "opc@approved-hostname",
  "cd /opt/oci-apm-mcp-server && . ./runtime.env && exec ./venv/bin/oci-apm-mcp-server"
]
startup_timeout_sec = 30
tool_timeout_sec = 120
required = false
```

Restart the Codex client after changing its configuration.

## 5. Acceptance sequence

1. Call `get_current_context` and confirm instance-principal authentication and read-only mode.
2. Call `test_connection` against the configured test domain.
3. Call `list_apm_domains` or `get_apm_domain` and verify the intended compartment boundary.
4. Call `find_traces` over a narrow test window with a small row limit.
5. Retrieve one synthetic test trace and span.
6. Confirm expert queries remain disabled and the identity cannot mutate APM resources.

Do not use production telemetry for the first acceptance test.
