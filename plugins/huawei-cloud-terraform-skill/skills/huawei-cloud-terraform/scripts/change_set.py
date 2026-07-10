#!/usr/bin/env python3
"""Preview and atomically apply safe Terraform file change sets."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .workspace_lib import read_json, workspace_paths, write_json
except ImportError:
    from workspace_lib import read_json, workspace_paths, write_json


PROTECTED_PARTS = {".terraform", "terraform.tfstate", "terraform.tfstate.backup", ".terraform.lock.hcl", "tfplan", "plan.json", ".skill-plan.json"}
ALLOWED_EXACT_SUFFIXES = {".tf", ".md"}
ALLOWED_SPECIAL_ENDINGS = (".tfvars.example",)
BLOCKED_NAMES = {".env", "terraform.tfvars", "credentials", "id_rsa"}


def normalize_relative_path(value: str) -> Path:
    path = Path(value)
    if not value.strip() or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {value}")
    if path.name in BLOCKED_NAMES:
        raise ValueError(f"Blocked file name: {value}")
    if path.suffix not in ALLOWED_EXACT_SUFFIXES and not value.endswith(ALLOWED_SPECIAL_ENDINGS):
        raise ValueError(f"Unsupported Terraform file path: {value}")
    return path


def validate_path(value: str) -> Path:
    path = normalize_relative_path(value)
    if any(part in PROTECTED_PARTS or part.startswith("terraform.tfstate") for part in path.parts):
        raise ValueError(f"Protected Terraform path: {value}")
    return path


def apply_change_set(workspace: str, document: dict, dry_run: bool, allow_delete: bool) -> dict:
    paths = workspace_paths(workspace)
    terraform_dir = paths["terraform"]
    terraform_dir.mkdir(parents=True, exist_ok=True)
    managed = set(read_json(paths["manifest"], default={"files": []}).get("files", []))
    writes = document.get("files_to_write", [])
    deletes = document.get("files_to_delete", [])
    if not isinstance(writes, list) or not isinstance(deletes, list):
        raise ValueError("files_to_write and files_to_delete must be arrays")

    prepared_writes: list[tuple[Path, str]] = []
    for item in writes:
        relative = validate_path(str(item.get("path", "")))
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError(f"Content must be a string: {relative}")
        prepared_writes.append((relative, content.rstrip() + "\n"))

    prepared_deletes = [validate_path(str(value)) for value in deletes]
    unmanaged = [path.as_posix() for path in prepared_deletes if path.as_posix() not in managed]
    if unmanaged:
        raise ValueError(f"Refusing to delete files not owned by the Skill: {unmanaged}")
    if prepared_deletes and not allow_delete:
        raise ValueError("File deletion requires --allow-delete")

    result = {
        "ok": True, "dry_run": dry_run, "workspace": workspace,
        "reason": document.get("reason", ""),
        "files_to_write": [path.as_posix() for path, _ in prepared_writes],
        "files_to_delete": [path.as_posix() for path in prepared_deletes],
    }
    if dry_run:
        return result

    backup_dir = paths["workspace"] / "snapshots" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for relative in [path for path, _ in prepared_writes] + prepared_deletes:
        source = terraform_dir / relative
        if source.exists():
            destination = backup_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())

    for relative, content in prepared_writes:
        target = terraform_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        managed.add(relative.as_posix())
    for relative in prepared_deletes:
        target = terraform_dir / relative
        if target.exists():
            target.unlink()
        managed.discard(relative.as_posix())
    write_json(paths["manifest"], {"files": sorted(managed)})
    result["backup"] = str(backup_dir) if backup_dir.exists() else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a reviewed Terraform file change set")
    parser.add_argument("command", choices=["apply"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--change-set", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-delete", action="store_true")
    args = parser.parse_args()
    document = json.loads(Path(args.change_set).read_text(encoding="utf-8"))
    print(json.dumps(apply_change_set(args.workspace, document, args.dry_run, args.allow_delete), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
