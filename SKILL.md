---
name: huawei-cloud-automation-llm-direct-webui
version: 0.2.0
description: Standalone Web UI Skill for Huawei Cloud automation. It supports LLM Direct Terraform generation plus a Python Tool Framework for operations that cannot be implemented by Terraform.
---

# Huawei Cloud Automation LLM Direct WebUI Skill

## Purpose

Use this Skill to automate Huawei Cloud work through two controlled paths:

1. **Terraform path**: the LLM extracts requirements and directly generates Terraform files. The Skill then writes files, runs policy checks, and gates `terraform plan/apply`.
2. **Python Tool path**: the LLM selects a registered Python tool when the user asks for a function that cannot be implemented cleanly with Terraform.

This Skill is standalone. It does not depend on the earlier Agent Runtime.

## Architecture

```text
User Web UI / CLI
  ↓
LLM intent and requirement understanding
  ↓
Route decision
  ├─ terraform_flow → generate .tf → policy-check → terraform fmt/init/validate/plan/apply gate
  └─ python_tool    → select registered tool → execute Python tool through registry/executor
```

## Terraform path

The LLM may generate Terraform files as JSON:

```json
{
  "files": [
    {"path": "provider.tf", "content": "..."},
    {"path": "main.tf", "content": "..."}
  ],
  "assumptions": [],
  "risk_notes": []
}
```

The Skill writes only safe file suffixes under the workspace Terraform directory and then allows controlled Terraform commands from `policies/command_allowlist.yaml`.

## Python Tool path

Python tools are registered in:

```text
tools/registry.yaml
```

Each real tool should be implemented as a local Python module under `tools/` and expose:

```python
def run(context: ToolContext, parameters: dict) -> ToolResult:
    ...
```

The first version only provides a `sample_echo` tool to prove the framework works. Business tools are intentionally not implemented yet.

## When to use Python tools

Use Python tools when the request requires:

- Huawei Cloud API operations not supported by Terraform.
- Inventory or discovery against existing resources.
- Precheck or migration helper logic.
- Data processing, validation, report generation, or custom workflow steps.
- External system integration.

## Do not do

- Do not invent unregistered tools.
- Do not execute Python tools outside the registry.
- Do not use shell execution inside the Python tool executor.
- Do not pass AK/SK through model prompts.
- Do not write AK/SK into generated Terraform files.
- Do not run `terraform apply` unless `ALLOW_APPLY=true` and the user provides the exact approval phrase.

## Security boundaries

- Terraform commands are allowlisted.
- Python tools are allowlisted through `tools/registry.yaml`.
- Disabled tools cannot run.
- Tools with `allow_execute: false` cannot run.
- The initial Python tool framework defaults to dry-run usage.
- Huawei Cloud credentials should be injected through environment variables or a future secret manager integration.

## Current status

This is a framework version. It includes:

- Web UI
- CLI
- Terraform LLM Direct flow
- Tool registry
- Tool selector prompt
- Python tool executor
- Sample echo tool

It does not yet include real Huawei Cloud Python business tools or generated tool parameters.
