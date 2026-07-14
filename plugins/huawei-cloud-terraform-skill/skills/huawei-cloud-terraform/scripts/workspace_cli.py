#!/usr/bin/env python3
"""Initialize and inspect Huawei Cloud Terraform workspaces."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

try:
    from .state_reader import list_state_addresses
    from .workspace_lib import DEFAULT_REQUIREMENTS, read_json, workspace_paths, write_json
except ImportError:
    from state_reader import list_state_addresses
    from workspace_lib import DEFAULT_REQUIREMENTS, read_json, workspace_paths, write_json


LOGGER = logging.getLogger(__name__)


def adopt(name: str, files: list[str]) -> dict:
    """Register existing relative ``.tf`` files as managed by the Skill."""
    LOGGER.info("Adopting Terraform files: workspace=%s count=%d", name, len(files))
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
    LOGGER.info("Terraform files adopted: workspace=%s adopted=%d", name, len(adopted))
    return {"ok": True, "workspace": name, "adopted": adopted, "managed_files": sorted(managed)}


def initialize(name: str) -> dict:
    """Create workspace directories without overwriting existing state or requirements."""
    LOGGER.info("Initializing workspace: %s", name)
    paths = workspace_paths(name)
    existed = paths["workspace"].exists()
    paths["terraform"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    if not paths["requirements"].exists():
        write_json(paths["requirements"], DEFAULT_REQUIREMENTS)
        LOGGER.info("Created default requirements: workspace=%s", name)
    LOGGER.info("Workspace ready: workspace=%s existed=%s", name, existed)
    return {"ok": True, "workspace": name, "created": not existed, "preserved_existing_state": existed}


def inspect(name: str) -> dict:
    """Return requirements, managed files, state addresses, and plan metadata."""
    LOGGER.info("Inspecting workspace: %s", name)
    paths = workspace_paths(name)
    terraform_files = sorted(path.relative_to(paths["terraform"]).as_posix() for path in paths["terraform"].rglob("*.tf")) if paths["terraform"].exists() else []
    managed = read_json(paths["manifest"], default={"files": []})
    result = {
        "ok": True,
        "workspace": name,
        "exists": paths["workspace"].exists(),
        "requirements": read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS),
        "terraform_files": terraform_files,
        "managed_files": managed.get("files", []),
        "state": list_state_addresses(paths["terraform"]),
        "plan_summary": read_json(paths["plan_summary"], default=None) if paths["plan_summary"].exists() else None,
    }
    LOGGER.info(
        "Workspace inspected: workspace=%s terraform_files=%d managed_files=%d state_addresses=%d",
        name,
        len(terraform_files),
        len(result["managed_files"]),
        len(result["state"].get("addresses", [])),
    )
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Deterministic Terraform workspace operations")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "inspect"):
        item = sub.add_parser(command)
        item.add_argument("--workspace", required=True)
    adopt_parser = sub.add_parser("adopt")
    adopt_parser.add_argument("--workspace", required=True)
    adopt_parser.add_argument("--files", nargs="+", required=True)
    args = parser.parse_args()
    LOGGER.info("Workspace command started: command=%s workspace=%s", args.command, args.workspace)
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
