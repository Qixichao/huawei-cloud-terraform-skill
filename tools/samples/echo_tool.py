"""A no-op sample Python tool.

This is not a Huawei Cloud business tool. It exists only to prove that the
registry, selector, executor, CLI, and Web UI plumbing are working.
"""
from __future__ import annotations

from typing import Any

from tools.base import ToolContext, ToolResult


def run(context: ToolContext, parameters: dict[str, Any]) -> ToolResult:
    return ToolResult(
        ok=True,
        tool_name="sample_echo",
        dry_run=context.dry_run,
        message="Sample echo tool executed. Replace this with a real Huawei Cloud Python tool.",
        data={
            "workspace": str(context.workspace),
            "environment": context.requirements.get("project", {}).get("environment"),
            "region": context.requirements.get("project", {}).get("region"),
            "received_parameters": parameters,
        },
        warnings=["This is a framework placeholder, not a production cloud operation."],
    )
