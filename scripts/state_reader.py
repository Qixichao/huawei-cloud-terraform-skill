#!/usr/bin/env python3
"""Read Terraform state addresses without modifying state."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


def list_state_addresses(terraform_dir: str | Path, timeout: int = 60) -> dict[str, Any]:
    """List state addresses using Terraform's read-only state command."""
    directory = Path(terraform_dir)
    state = directory / "terraform.tfstate"
    if not state.exists():
        LOGGER.info("Terraform state not found: directory=%s", directory)
        return {"ok": True, "state_exists": False, "addresses": []}
    LOGGER.info("Reading Terraform state addresses: directory=%s", directory)
    result = subprocess.run(
        ["terraform", "state", "list", "-state=terraform.tfstate"],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    addresses = [line for line in result.stdout.splitlines() if line.strip()]
    LOGGER.info("Terraform state read: returncode=%d addresses=%d", result.returncode, len(addresses))
    return {
        "ok": result.returncode == 0,
        "state_exists": True,
        "addresses": addresses,
        "returncode": result.returncode,
        "stderr": result.stderr,
    }
