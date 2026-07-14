#!/usr/bin/env python3
"""Allowlisted Terraform command runner."""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


LOGGER = logging.getLogger(__name__)

COMMAND_POLICY = Path(__file__).resolve().parents[1] / "policies" / "command_allowlist.yaml"


class TerraformRunnerError(RuntimeError):
    """Raised when an operation violates the Terraform execution policy."""

    pass


def load_commands() -> dict[str, list[str]]:
    """Load fixed argument arrays; callers cannot construct arbitrary shell commands."""
    data = yaml.safe_load(COMMAND_POLICY.read_text(encoding="utf-8"))
    return data["allowed_terraform_commands"]


def run_terraform(command_name: str, terraform_dir: str | Path, timeout: int = 1800) -> dict[str, Any]:
    """Run one allowlisted Terraform command without invoking a shell."""
    terraform_dir = Path(terraform_dir)
    commands = load_commands()
    if command_name not in commands:
        raise TerraformRunnerError(f"Command is not allowlisted: {command_name}")

    cmd = commands[command_name]
    LOGGER.info("Terraform command started: name=%s directory=%s", command_name, terraform_dir)
    result = subprocess.run(
        cmd,
        cwd=str(terraform_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    LOGGER.info("Terraform command finished: name=%s returncode=%d", command_name, result.returncode)
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def validate_terraform_dir(terraform_dir: str | Path, timeout: int = 1800) -> dict[str, Any]:
    """Initialize providers and validate the Terraform configuration."""
    terraform_dir = Path(terraform_dir)
    init_result = run_terraform("init", terraform_dir, timeout=timeout)
    validate_result = run_terraform("validate", terraform_dir, timeout=timeout)
    return {
        "ok": init_result["returncode"] == 0 and validate_result["returncode"] == 0,
        "init": init_result,
        "validate": validate_result,
    }


def apply_saved_plan(terraform_dir: str | Path, approval: str, environment: str | None = None) -> dict[str, Any]:
    """Apply only an existing plan after exact approval and production checks."""
    required = os.getenv("REQUIRED_APPLY_APPROVAL", "Confirm to execute apply")
    if approval != required:
        raise TerraformRunnerError(f"Apply blocked: approval must exactly equal '{required}'")

    if (environment or "").lower() == "prod" and os.getenv("ALLOW_PROD_APPLY", "false").lower() != "true":
        raise TerraformRunnerError("Production apply blocked: set ALLOW_PROD_APPLY=true to enable prod apply")

    terraform_dir = Path(terraform_dir)
    if not (terraform_dir / "tfplan").is_file():
        raise TerraformRunnerError("Apply blocked: no reviewed tfplan exists; run a fresh plan first")

    # Never log the approval text or inherited cloud credentials.
    LOGGER.info("Applying reviewed Terraform plan: directory=%s environment=%s", terraform_dir, environment or "unspecified")
    return run_terraform("apply_saved_plan", terraform_dir)


def save_command_result(result: dict[str, Any], output_path: str | Path) -> None:
    """Persist the complete command result for diagnostics outside model output."""
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.debug("Terraform command result saved: %s", output_path)
