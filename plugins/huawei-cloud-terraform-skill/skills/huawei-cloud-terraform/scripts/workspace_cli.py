#!/usr/bin/env python3
"""Initialize and inspect Huawei Cloud Terraform workspaces."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .state_reader import list_state_addresses
    from .workspace_lib import DEFAULT_REQUIREMENTS, read_json, workspace_paths, write_json
except ImportError:
    from state_reader import list_state_addresses
    from workspace_lib import DEFAULT_REQUIREMENTS, read_json, workspace_paths, write_json


def adopt(name: str, files: list[str]) -> dict:
    paths = workspace_paths(name)
    terraform_dir = paths["terraform"].resolve()
    managed = set(read_json(paths["manifest"], default={"files": []}).get("files", []))
    adopted: list[str] = []
    for value in files:
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".tf":
            raise ValueError(f"Only relative existing .tf files can be adopted: {value}")
        target = (terraform_dir / relative).resolve()
        if terraform_dir not in target.parents or not target.is_file():
            raise ValueError(f"Terraform file does not exist: {value}")
        managed.add(relative.as_posix())
        adopted.append(relative.as_posix())
    write_json(paths["manifest"], {"files": sorted(managed)})
    return {"ok": True, "workspace": name, "adopted": adopted, "managed_files": sorted(managed)}


def initialize(name: str) -> dict:
    paths = workspace_paths(name)
    existed = paths["workspace"].exists()
    paths["terraform"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    if not paths["requirements"].exists():
        write_json(paths["requirements"], DEFAULT_REQUIREMENTS)
    return {"ok": True, "workspace": name, "created": not existed, "preserved_existing_state": existed}


def inspect(name: str) -> dict:
    paths = workspace_paths(name)
    terraform_files = sorted(path.relative_to(paths["terraform"]).as_posix() for path in paths["terraform"].rglob("*.tf")) if paths["terraform"].exists() else []
    managed = read_json(paths["manifest"], default={"files": []})
    return {
        "ok": True,
        "workspace": name,
        "exists": paths["workspace"].exists(),
        "requirements": read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS),
        "terraform_files": terraform_files,
        "managed_files": managed.get("files", []),
        "state": list_state_addresses(paths["terraform"]),
        "plan_summary": read_json(paths["plan_summary"], default=None) if paths["plan_summary"].exists() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Terraform workspace operations")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "inspect"):
        item = sub.add_parser(command)
        item.add_argument("--workspace", required=True)
    adopt_parser = sub.add_parser("adopt")
    adopt_parser.add_argument("--workspace", required=True)
    adopt_parser.add_argument("--files", nargs="+", required=True)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.workspace)
    elif args.command == "inspect":
        result = inspect(args.workspace)
    else:
        result = adopt(args.workspace, args.files)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
