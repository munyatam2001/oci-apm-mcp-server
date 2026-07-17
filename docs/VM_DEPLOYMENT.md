# Install on Oracle Linux and connect Codex through SSH

This guide takes a new user from an empty OCI Compute instance to a working OCI APM MCP
connection in Codex. The recommended deployment uses:

```text
Codex on a laptop
        |
        | SSH on port 22
        v
Oracle Linux VM
        |
        | OCI Python SDK with instance-principal authentication
        v
OCI Application Performance Monitoring APIs
```

The MCP server is not exposed on a network port. Codex starts it remotely through SSH and
communicates over STDIO. When Codex disconnects, the remote MCP process exits.

## 1. What you need

- an OCI Compute VM running Oracle Linux 9.4 or newer;
- SSH access to the VM;
- an OCI APM domain and its region;
- the APM compartment OCID and domain OCID;
- permission to create an OCI dynamic group and IAM policy;
- Codex Desktop, Codex CLI, or the Codex IDE extension on the laptop; and
- Python 3.11 or newer on the VM (Python 3.12 is recommended).

The VM needs outbound access to OCI service APIs. It needs no inbound MCP port: SSH is the
only inbound connection in this design.

## 2. Authorize the VM with an instance principal

Instance principals let software on a Compute instance call OCI APIs without installing an OCI
user API key. OCI creates and rotates the instance credentials.

### 2.1 Copy the VM OCID

In the OCI Console, open **Compute**, select the instance, and copy its OCID.

### 2.2 Create a narrowly scoped dynamic group

In **Identity & Security**, open the appropriate identity domain, select **Dynamic Groups**, and
create a group such as `oci-apm-mcp-vm`.

Scope membership to the exact VM:

```text
instance.id = '<vm-instance-ocid>'
```

### 2.3 Grant read-only APM access

Create an IAM policy in the appropriate parent compartment:

```text
Allow dynamic-group oci-apm-mcp-vm to read apm-domains in compartment <apm-compartment-name>
```

For a named identity domain, the subject may need the domain-qualified form:

```text
Allow dynamic-group '<identity-domain-name>'/'oci-apm-mcp-vm' to read apm-domains in compartment <apm-compartment-name>
```

Keep the policy at compartment scope. Do not grant `manage all-resources` or
`manage apm-domains` to this read-only deployment. Allow several minutes for a new dynamic
group or policy to propagate.

> **Light moment:** least privilege is like packing for a short trip: take what you need, not
> the entire house.

Anyone who can access the VM may inherit its instance-principal permissions. Restrict SSH
access to approved users and networks. See Oracle's
[instance-principal guidance](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm)
and this project's [IAM setup](IAM_SETUP.md).

## 3. Install the server on Oracle Linux

Connect to the VM:

```bash
ssh -i /absolute/path/to/private-key opc@<vm-hostname-or-ip>
```

Check the operating system:

```bash
cat /etc/oracle-release
```

### 3.1 Install Git and Python 3.12

```bash
sudo dnf install -y git python3.12 python3.12-pip
python3.12 --version
git --version
```

Oracle Linux can keep its unversioned `python3` command on Python 3.9, so invoke
`python3.12` explicitly.

> **Light moment:** Python 3.9 is a respectable citizen; this project simply needs a slightly
> newer passport.

### 3.2 Clone the public repository

```bash
sudo mkdir -p /opt/oci-apm-mcp-server
sudo chown opc:opc /opt/oci-apm-mcp-server
git clone https://github.com/munyatam2001/oci-apm-mcp-server.git /opt/oci-apm-mcp-server
cd /opt/oci-apm-mcp-server
```

For a production-controlled installation, prefer a reviewed release tag once formal releases
are available. Until then, install the reviewed `main` branch.

### 3.3 Create an isolated Python environment

```bash
python3.12 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install .
```

Confirm the package and executable:

```bash
venv/bin/python -m pip show oci-apm-mcp-server
ls -l venv/bin/oci-apm-mcp-server
```

## 4. Configure the deployment

Store deployment configuration under the Git-ignored `runtime/` directory:

```bash
cd /opt/oci-apm-mcp-server
mkdir -p runtime
chmod 700 runtime
vi runtime/apm.env
```

Add the following values:

```bash
export OCI_APM_AUTH_TYPE=instance_principal
export OCI_REGION='<oci-region>'
export OCI_APM_COMPARTMENT_ID='<apm-compartment-ocid>'
export OCI_APM_DOMAIN_ID='<apm-domain-ocid>'

export OCI_APM_ALLOW_SCOPE_OVERRIDE=false
export OCI_APM_ENABLE_EXPERT_QUERY=false
export OCI_APM_READ_ONLY=true
export OCI_APM_LOG_LEVEL=INFO

export OCI_APM_CONNECT_TIMEOUT_SECONDS=10
export OCI_APM_READ_TIMEOUT_SECONDS=60
```

Protect the file:

```bash
chmod 600 /opt/oci-apm-mcp-server/runtime/apm.env
```

The OCIDs identify deployment scope and must not be committed to the public repository. Do not
place OCI user private keys, passwords, tokens, or APM data keys in this file.

Keep these safety settings unless a separate design and security review approves a change:

```bash
export OCI_APM_ALLOW_SCOPE_OVERRIDE=false
export OCI_APM_ENABLE_EXPERT_QUERY=false
export OCI_APM_READ_ONLY=true
```

## 5. Smoke-test the remote executable

On the VM:

```bash
cd /opt/oci-apm-mcp-server
. ./runtime/apm.env
./venv/bin/oci-apm-mcp-server
```

The process should wait quietly for MCP messages on STDIN. Press `Ctrl+C` after confirming that
no startup exception appears.

> **Light moment:** if the server waits silently, it is not ghosting you; it is listening on
> STDIN.

Ordinary application logs belong on STDERR. STDOUT is reserved for MCP protocol messages, so
shell profiles and launcher commands must not print banners or environment values.

## 6. Prepare SSH on the Codex laptop

Protect the private key:

```bash
chmod 600 /absolute/path/to/private-key
```

Connect manually once:

```bash
ssh -i /absolute/path/to/private-key opc@<vm-hostname-or-ip>
```

Verify the displayed fingerprint belongs to the intended VM before accepting it. This records
the server key in `~/.ssh/known_hosts`.

Then verify non-interactive SSH:

```bash
ssh \
  -i /absolute/path/to/private-key \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  opc@<vm-hostname-or-ip> \
  "echo SSH connection successful"
```

Do not use `StrictHostKeyChecking=no`. A convenient connection to the wrong host is still a
connection to the wrong host.

## 7. Add the server to Codex

Codex Desktop, Codex CLI, and the IDE extension share MCP configuration on the same host.
The default file is `~/.codex/config.toml`.

### 7.1 Configure with the Codex interface

1. Open **Settings** and select **MCP servers**.
2. Select **Add server**.
3. Name it `oci_apm`.
4. Choose **STDIO**.
5. Set the command to `ssh`.
6. Add each item below as a separate argument:

```text
-i
/absolute/path/to/private-key
-o
BatchMode=yes
-o
StrictHostKeyChecking=yes
-o
ServerAliveInterval=60
-o
ServerAliveCountMax=3
opc@<vm-hostname-or-ip>
cd /opt/oci-apm-mcp-server && . ./runtime/apm.env && exec ./venv/bin/oci-apm-mcp-server
```

The final remote command, beginning with `cd` and ending with `mcp-server`, is one argument.
Leave the local working directory and environment-variable fields empty. Use a 30-second
startup timeout and a 120-second tool timeout. Save and restart Codex.

### 7.2 Configure with `config.toml`

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.oci_apm]
command = "ssh"
args = [
  "-i", "/absolute/path/to/private-key",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=yes",
  "-o", "ServerAliveInterval=60",
  "-o", "ServerAliveCountMax=3",
  "opc@<vm-hostname-or-ip>",
  "cd /opt/oci-apm-mcp-server && . ./runtime/apm.env && exec ./venv/bin/oci-apm-mcp-server"
]
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled = true
required = false
default_tools_approval_mode = "writes"
```

Use the absolute local key path, such as `/Users/name/.ssh/oci_apm_vm.key`; do not rely on `~`
expansion inside the argument array. Restart Codex after saving.

See the official [Codex MCP documentation](https://developers.openai.com/codex/mcp) and this
project's [client setup](CLIENT_SETUP.md) for additional configuration modes.

## 8. Confirm the MCP connection

Open `/mcp` in Codex or inspect **Settings > MCP servers**. The `oci_apm` server should be
enabled and expose the tools documented in [TOOL_CATALOG.md](TOOL_CATALOG.md).

An `Auth unsupported` label is normal for this STDIO setup. SSH authenticates the laptop to the
VM, and the instance principal authenticates the VM to OCI; MCP OAuth has no paperwork left to
do.

Run these acceptance prompts in order:

```text
Using oci_apm, call get_current_context. Confirm the server version,
authentication type, region, read-only state, and registered tool count.
```

```text
Using oci_apm, call test_connection and explain the result.
```

```text
Using oci_apm, call get_apm_domain for the configured domain.
Return only safe domain metadata.
```

```text
Using oci_apm, call find_traces over the last 24 hours.
Limit to 10 traces, sort by duration descending, and do not request attributes.
```

```text
Using oci_apm, call investigate_latency over the last 24 hours.
Return the five slowest traces and summarize representative evidence.
Do not claim a root cause.
```

```text
Using oci_apm, call investigate_errors over the last 24 hours.
Return up to five error-bearing traces and summarize representative error spans.
```

```text
Using oci_apm, call list_synthetic_monitors with limit=10.
```

```text
Using oci_apm, call list_public_vantage_points with limit=10.
Return only name, display name, city, and country.
```

Confirm that the context reports instance-principal authentication, the intended region and
masked scope, read-only mode, disabled scope overrides, and disabled expert queries.

## 9. How normal operation works

The MCP server does not need a permanent system service. For each connection:

1. Codex starts the local `ssh` command.
2. SSH connects to the VM.
3. The remote command loads `runtime/apm.env`.
4. The MCP executable starts.
5. Codex and the server communicate over SSH STDIO.
6. The process exits when Codex disconnects.

The VM only needs to remain running, SSH-reachable, authorized by its dynamic group, and able to
reach OCI APIs.

## 10. Upgrade an existing installation

Connect to the VM and inspect local state before updating:

```bash
cd /opt/oci-apm-mcp-server
git status --short
```

Do not overwrite unexpected local changes. With a clean working tree:

```bash
git pull --ff-only origin main
venv/bin/python -m pip install --upgrade .
venv/bin/python -m pip show oci-apm-mcp-server
```

Restart Codex, then call `get_current_context` to confirm the new version and tool count. The
`runtime/apm.env` file remains untouched because the entire `runtime/` directory is ignored by
Git.

## 11. Troubleshooting

### The MCP server is disabled or fails to start

Run the exact remote launcher from the laptop:

```bash
ssh \
  -i /absolute/path/to/private-key \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  opc@<vm-hostname-or-ip> \
  "cd /opt/oci-apm-mcp-server && . ./runtime/apm.env && exec ./venv/bin/oci-apm-mcp-server"
```

If it waits silently, the process probably started successfully. Press `Ctrl+C`.

### `Permission denied (publickey)`

Check the SSH username, private key, key permissions, VM NSG/security-list rules, and installed
public key. The key file should normally have mode `600`.

### Host-key verification failed

Confirm whether the VM was rebuilt or its address changed. Do not disable checking. After
verifying the new fingerprint, remove only the obsolete entry:

```bash
ssh-keygen -R <vm-hostname-or-ip>
```

Connect manually and validate the replacement fingerprint.

### OCI authorization failed

Check the VM OCID in the dynamic-group rule, the identity-domain-qualified group name if used,
policy placement, APM compartment, region, domain OCID, and IAM propagation time.

### No traces were returned

Confirm that APM agents or the Browser Agent are sending telemetry, application activity exists,
the configured region/domain is correct, and the query window covers that activity. A valid
`no_data` result is not an installation failure.

> **Light moment:** the MCP can investigate traffic, but it cannot observe a request that never
> happened. Interpretive dance support remains on the distant roadmap.

### Startup timed out

Increase `startup_timeout_sec` to `60`. The first instance-principal and OCI client initialization
can take longer than later calls.

### Protocol or JSON errors

Remove banners, debug `echo` commands, and environment dumps from the remote shell startup path.
STDOUT must contain only MCP protocol messages; logs belong on STDERR.

## 12. Security checklist

- [ ] The dynamic group contains only the approved VM.
- [ ] IAM grants `read apm-domains` only in the intended compartment.
- [ ] No OCI user private key is installed on the VM.
- [ ] SSH is restricted to approved users and source networks.
- [ ] The SSH host key was verified and retained.
- [ ] `runtime/apm.env` is mode `600` and contains no credentials.
- [ ] Scope override and expert query remain disabled.
- [ ] Read-only mode remains enabled.
- [ ] No MCP network port is publicly exposed.
- [ ] Initial acceptance uses non-production telemetry.

## 13. Stop using the server

Disable or remove the `oci_apm` entry in Codex. To revoke OCI access, remove the VM from the
dynamic group or remove the dynamic group's APM policy. Remove the installation only after
confirming that `/opt/oci-apm-mcp-server` is dedicated to this server and contains no material
that must be retained.
