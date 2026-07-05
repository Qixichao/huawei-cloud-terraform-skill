"""Base types for Python tools.

Business tools should accept a ToolContext and a parameters dict, then return ToolResult.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolContext:
    workspace: Path
    skill_dir: Path
    requirements: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True
    user_id: str | None = None


@dataclass
class ToolResult:
    ok: bool
    tool_name: str
    dry_run: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool_name": self.tool_name,
            "dry_run": self.dry_run,
            "message": self.message,
            "data": self.data,
            "warnings": self.warnings,
            "errors": self.errors,
        }
