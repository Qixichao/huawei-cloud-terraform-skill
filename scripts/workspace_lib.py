#!/usr/bin/env python3
"""Shared deterministic workspace helpers."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
WORKSPACES_DIR = SKILL_DIR / "workspaces"
WORKSPACE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
DEFAULT_REQUIREMENTS: dict[str, Any] = {
    "project": {"name": None, "environment": "dev", "region": None, "provider_version": "~> 1.93"},
    "network": {"vpc_name": None, "vpc_cidr": None, "subnets": []},
    "security_groups": [], "ecs": [], "rds": [], "obs": [], "notes": [],
}


def workspace_root(name: str) -> Path:
    name = name.strip()
    if not WORKSPACE_RE.fullmatch(name):
        raise ValueError("Workspace must contain only letters, numbers, dot, dash, or underscore")
    return WORKSPACES_DIR / name


def workspace_paths(name: str) -> dict[str, Path]:
    root = workspace_root(name)
    return {
        "workspace": root,
        "requirements": root / "requirements.json",
        "terraform": root / "terraform",
        "logs": root / "logs",
        "manifest": root / "terraform" / ".skill-managed-files.json",
        "plan_summary": root / "terraform" / "plan_summary.json",
    }


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return deepcopy(default)
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
