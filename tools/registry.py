"""Load and expose Python tool registry metadata."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SKILL_DIR = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_DIR / "tools" / "registry.yaml"


@dataclass
class ToolSpec:
    name: str
    display_name: str
    description: str
    module: str
    function: str = "run"
    enabled: bool = False
    allow_execute: bool = False
    category: str = "custom"
    input_schema: dict[str, Any] | None = None
    notes: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSpec":
        return cls(
            name=data["name"],
            display_name=data.get("display_name") or data["name"],
            description=data.get("description", ""),
            module=data.get("module", ""),
            function=data.get("function", "run"),
            enabled=bool(data.get("enabled", False)),
            allow_execute=bool(data.get("allow_execute", False)),
            category=data.get("category", "custom"),
            input_schema=data.get("input_schema") or {},
            notes=data.get("notes") or [],
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "allow_execute": self.allow_execute,
            "category": self.category,
            "input_schema": self.input_schema or {},
            "notes": self.notes or [],
        }


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else REGISTRY_PATH
    if not registry_path.exists():
        return {"version": 1, "default_dry_run": True, "tools": []}
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tools", [])
    data.setdefault("default_dry_run", True)
    return data


def list_tool_specs(path: str | Path | None = None, enabled_only: bool = False) -> list[ToolSpec]:
    data = load_registry(path)
    specs = [ToolSpec.from_dict(item) for item in data.get("tools", [])]
    if enabled_only:
        specs = [spec for spec in specs if spec.enabled]
    return specs


def get_tool_spec(name: str, path: str | Path | None = None) -> ToolSpec:
    for spec in list_tool_specs(path):
        if spec.name == name:
            return spec
    raise KeyError(f"Tool not found in registry: {name}")


def registry_for_llm(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return only safe metadata for LLM tool selection."""
    return [spec.public_dict() for spec in list_tool_specs(path, enabled_only=True)]
