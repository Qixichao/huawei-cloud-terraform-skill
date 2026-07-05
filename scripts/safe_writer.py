#!/usr/bin/env python3
"""Safe writer for LLM-generated Terraform files."""
from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_SUFFIXES = {".tf", ".example", ".md"}
ALLOWED_EXACT_SUFFIXES = {".tf", ".md"}
ALLOWED_SPECIAL_ENDINGS = (".tfvars.example",)
BLOCKED_NAMES = {".env", "terraform.tfvars", "credentials", "id_rsa"}


class SafeWriteError(ValueError):
    pass


def is_allowed_filename(path: str) -> bool:
    p = Path(path)
    if p.name in BLOCKED_NAMES:
        return False
    if p.suffix in ALLOWED_EXACT_SUFFIXES:
        return True
    return any(path.endswith(ending) for ending in ALLOWED_SPECIAL_ENDINGS)


def normalize_relative_path(path: str) -> Path:
    if not path or path.strip() == "":
        raise SafeWriteError("Empty file path")

    p = Path(path)
    if p.is_absolute():
        raise SafeWriteError(f"Absolute paths are not allowed: {path}")

    if ".." in p.parts:
        raise SafeWriteError(f"Path traversal is not allowed: {path}")

    if not is_allowed_filename(path):
        raise SafeWriteError(f"File extension or file name is not allowed: {path}")

    return p


def write_terraform_files(files_response: dict[str, Any], terraform_dir: str | Path) -> list[Path]:
    files = files_response.get("files")
    if not isinstance(files, list) or not files:
        raise SafeWriteError("Response must contain a non-empty 'files' list")

    if len(files) > 40:
        raise SafeWriteError("Too many files in LLM response; max is 40")

    terraform_dir = Path(terraform_dir)
    terraform_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for item in files:
        if not isinstance(item, dict):
            raise SafeWriteError("Each file item must be an object")
        rel_path = normalize_relative_path(str(item.get("path", "")))
        content = item.get("content")
        if not isinstance(content, str):
            raise SafeWriteError(f"File content must be string: {rel_path}")
        if len(content.encode("utf-8")) > 200000:
            raise SafeWriteError(f"File too large: {rel_path}")

        target = terraform_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(target)

    return written
