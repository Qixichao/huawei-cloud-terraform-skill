# Huawei Cloud Automation LLM Direct WebUI Skill

This is a standalone Skill package. It provides:

1. LLM Direct Terraform generation.
2. Web UI for multi-turn requirements, Terraform file generation, policy check, plan, and apply gate.
3. Python Tool Framework for functions that cannot be implemented with Terraform.

It does **not** depend on the previous Agent Runtime.

## Why Python Tool Framework exists

Some operations cannot or should not be implemented as Terraform scripts, for example:

- Querying existing resources outside Terraform state.
- Running Huawei Cloud API prechecks.
- Doing migration helper actions.
- Processing files or inventories.
- Calling internal systems or CMDB.
- Running one-off validation workflows.

For these cases, the model should choose a registered Python tool instead of generating Terraform.

Current package only builds the framework. Real business tools and detailed tool parameter generation can be added later.

## Entry points

Web UI:

```bash
python scripts/web_server.py
```

Open:

```text
http://127.0.0.1:8080
```

Terraform CLI:

```bash
python scripts/skill_cli.py --help
```

Python Tool CLI:

```bash
python scripts/tools_cli.py --help
```

## Install

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure LLM

OpenAI official API:

```powershell
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-5.4-mini"
$env:LLM_API_KEY="your-openai-api-key"
```

vLLM / LiteLLM compatible API:

```powershell
$env:LLM_BASE_URL="http://localhost:8000/v1"
$env:LLM_MODEL="infra-llm"
$env:LLM_API_KEY="dummy"
```

## Configure Huawei Cloud credentials for Terraform

Do not write AK/SK into Terraform files. Set environment variables before starting the Web UI:

```powershell
$env:HW_ACCESS_KEY="your-ak"
$env:HW_SECRET_KEY="your-sk"
$env:HW_REGION_NAME="me-east-1"
```

Terraform child processes inherit these variables from `web_server.py`.

## Enable apply

Apply is blocked by default.

```powershell
$env:ALLOW_APPLY="true"
python scripts/web_server.py
```

The approval input must exactly equal:

```text
Confirm to execute apply
```

## Python Tool Framework

Tools are registered in:

```text
tools/registry.yaml
```

Framework files:

```text
tools/
├── base.py          # ToolContext / ToolResult
├── registry.py      # Load registry.yaml
├── executor.py      # Safe registered-tool executor
├── registry.yaml    # Tool metadata and allow flags
└── samples/
    └── echo_tool.py # Framework test tool only
```

LLM tool routing prompt:

```text
prompts/tool_selection.md
```

Tool selector:

```text
scripts/tool_selector.py
```

Tool CLI:

```text
scripts/tools_cli.py
```

## Tool CLI examples

List registered tools:

```bash
python scripts/tools_cli.py list
```

Ask the model to choose Terraform flow or Python tool:

```bash
python scripts/tools_cli.py select \
  --workspace ./workspaces/demo \
  --message "Check current workspace information and do a test with Python tools"
```

Run the sample tool:

```bash
python scripts/tools_cli.py run \
  --workspace ./workspaces/demo \
  --tool sample_echo \
  --params-json "{\"hello\": \"world\"}" \
  --dry-run
```

## Add a real Python tool later

1. Create a Python module under `tools/`, for example:

```text
tools/huaweicloud/resource_inventory.py
```

2. Implement:

```python
from tools.base import ToolContext, ToolResult


def run(context: ToolContext, parameters: dict) -> ToolResult:
    return ToolResult(
        ok=True,
        tool_name="huaweicloud_resource_inventory",
        dry_run=context.dry_run,
        message="inventory collected",
        data={},
    )
```

3. Register it in `tools/registry.yaml` and set:

```yaml
enabled: true
allow_execute: true
```

4. Restart the Web UI.

## Validate package

```bash
python scripts/validate_skill_package.py
```

Expected result:

```text
Skill package validation passed.
No templates/ directory and no .j2 files found.
Python tool framework files found.
```

## Production notes

Before production use, add:

- RBAC for Web UI users.
- Secret manager integration instead of local environment variables.
- Tool-level permission model.
- Audit logs for all tool calls.
- Approval workflow for risky Python tools.
- Real Huawei Cloud SDK tools.
