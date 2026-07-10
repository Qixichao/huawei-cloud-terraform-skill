#!/usr/bin/env python3
"""Read Terraform state addresses without modifying state."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def list_state_addresses(terraform_dir: str | Path, timeout: int = 60) -> dict[str, Any]:
    directory = Path(terraform_dir)
    state = directory / "terraform.tfstate"
    if not state.exists():
        return {"ok": True, "state_exists": False, "addresses": []}
    result = subprocess.run(
        ["terraform", "state", "list", "-state=terraform.tfstate"],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    return {
        "ok": result.returncode == 0,
        "state_exists": True,
        "addresses": [line for line in result.stdout.splitlines() if line.strip()],
        "returncode": result.returncode,
        "stderr": result.stderr,
    }
