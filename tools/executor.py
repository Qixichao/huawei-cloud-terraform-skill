"""Safe Python tool executor.

This executor deliberately supports only registry-defined Python functions.
No shell command execution is provided here.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from tools.base import ToolContext, ToolResult
from tools.registry import get_tool_spec


class ToolExecutionError(RuntimeError):
    pass


def execute_tool(
    tool_name: str,
    parameters: dict[str, Any] | None,
    workspace: str | Path,
    skill_dir: str | Path,
    requirements: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    spec = get_tool_spec(tool_name)
    if not spec.enabled:
        raise ToolExecutionError(f"Tool is disabled: {tool_name}")
    if not spec.allow_execute:
        raise ToolExecutionError(f"Tool execution is not allowed by registry: {tool_name}")
    if not spec.module:
        raise ToolExecutionError(f"Tool module is not configured: {tool_name}")

    # Only import from local tools.* modules. This avoids arbitrary import paths.
    if not spec.module.startswith("tools."):
        raise ToolExecutionError(f"Tool module must start with 'tools.': {spec.module}")

    module = importlib.import_module(spec.module)
    fn = getattr(module, spec.function, None)
    if fn is None:
        raise ToolExecutionError(f"Function '{spec.function}' not found in module '{spec.module}'")

    context = ToolContext(
        workspace=Path(workspace),
        skill_dir=Path(skill_dir),
        requirements=requirements or {},
        dry_run=dry_run,
    )
    result = fn(context, parameters or {})
    if isinstance(result, ToolResult):
        return result.to_dict()
    if isinstance(result, dict):
        result.setdefault("tool_name", tool_name)
        result.setdefault("dry_run", dry_run)
        result.setdefault("ok", True)
        result.setdefault("message", "Tool returned a raw dict.")
        return result
    raise ToolExecutionError(f"Tool returned unsupported type: {type(result)!r}")
