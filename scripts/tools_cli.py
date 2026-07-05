#!/usr/bin/env python3
"""CLI for the Python Tool Framework."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from skill_cli import DEFAULT_REQUIREMENTS, read_json, write_json, workspace_paths  # noqa: E402
from tool_selector import select_tool  # noqa: E402
from tools.executor import execute_tool  # noqa: E402
from tools.registry import list_tool_specs, registry_for_llm  # noqa: E402


def cmd_list(args: argparse.Namespace) -> int:
    tools = [spec.public_dict() for spec in list_tool_specs(enabled_only=args.enabled_only)]
    print(json.dumps({"tools": tools}, ensure_ascii=False, indent=2))
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    paths = workspace_paths(args.workspace)
    requirements = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
    result = select_tool(args.message, requirements=requirements, temperature=args.temperature)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    write_json(paths["logs"] / "last_tool_selection.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def load_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_file:
        return read_json(args.params_file, default={})
    if args.params_json:
        return json.loads(args.params_json)
    return {}


def cmd_run(args: argparse.Namespace) -> int:
    paths = workspace_paths(args.workspace)
    requirements = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
    params = load_params(args)
    result = execute_tool(
        args.tool,
        params,
        workspace=paths["workspace"],
        skill_dir=SKILL_DIR,
        requirements=requirements,
        dry_run=args.dry_run,
    )
    paths["logs"].mkdir(parents=True, exist_ok=True)
    write_json(paths["logs"] / f"tool_{args.tool}.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Python tool framework CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List registered Python tools")
    p_list.add_argument("--enabled-only", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_select = sub.add_parser("select", help="Ask LLM to select Terraform flow or a Python tool")
    p_select.add_argument("--workspace", default="./workspaces/demo")
    p_select.add_argument("--message", required=True)
    p_select.add_argument("--temperature", type=float, default=0.1)
    p_select.set_defaults(func=cmd_select)

    p_run = sub.add_parser("run", help="Run a registered Python tool")
    p_run.add_argument("--workspace", default="./workspaces/demo")
    p_run.add_argument("--tool", required=True)
    p_run.add_argument("--params-json", default="{}")
    p_run.add_argument("--params-file")
    p_run.add_argument("--dry-run", action="store_true", default=True)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
