#!/usr/bin/env python3
"""Allowlisted Terraform command runner."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


COMMAND_POLICY = Path(__file__).resolve().parents[1] / "policies" / "command_allowlist.yaml"


class TerraformRunnerError(RuntimeError):
    pass


def load_commands() -> dict[str, list[str]]:
    data = yaml.safe_load(COMMAND_POLICY.read_text(encoding="utf-8"))
    return data["allowed_terraform_commands"]


def run_terraform(command_name: str, terraform_dir: str | Path, timeout: int = 1800) -> dict[str, Any]:
    terraform_dir = Path(terraform_dir)
    commands = load_commands()
    if command_name not in commands:
        raise TerraformRunnerError(f"Command is not allowlisted: {command_name}")

    cmd = commands[command_name]
    result = subprocess.run(
        cmd,
        cwd=str(terraform_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def apply_saved_plan(terraform_dir: str | Path, approval: str, environment: str | None = None) -> dict[str, Any]:
    required = os.getenv("REQUIRED_APPLY_APPROVAL", "Confirm to execute apply")
    if approval != required:
        raise TerraformRunnerError(f"Apply blocked: approval must exactly equal '{required}'")

    if os.getenv("ALLOW_APPLY", "false").lower() != "true":
        raise TerraformRunnerError("Apply blocked: set ALLOW_APPLY=true to enable apply")

    if (environment or "").lower() == "prod" and os.getenv("ALLOW_PROD_APPLY", "false").lower() != "true":
        raise TerraformRunnerError("Production apply blocked: set ALLOW_PROD_APPLY=true to enable prod apply")

    tfplan = Path(terraform_dir) / "tfplan"
    if not tfplan.exists():
        raise TerraformRunnerError("Apply blocked: saved plan file 'tfplan' not found")

    return run_terraform("apply_saved_plan", terraform_dir)


def save_command_result(result: dict[str, Any], output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
