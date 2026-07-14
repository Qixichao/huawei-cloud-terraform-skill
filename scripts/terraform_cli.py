#!/usr/bin/env python3
"""JSON CLI for deterministic Terraform lifecycle operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging

try:
    from .parse_plan import summarize_plan
    from .policy_check import scan_terraform_dir
    from .terraform_runner import apply_saved_plan, run_terraform, save_command_result, validate_terraform_dir
    from .workspace_lib import read_json, workspace_paths, write_json
except ImportError:
    from parse_plan import summarize_plan
    from policy_check import scan_terraform_dir
    from terraform_runner import apply_saved_plan, run_terraform, save_command_result, validate_terraform_dir
    from workspace_lib import read_json, workspace_paths, write_json


LOGGER = logging.getLogger(__name__)


def configuration_digest(terraform_dir) -> str:
    """Hash managed Terraform source paths and contents for plan freshness checks."""
    digest = hashlib.sha256()
    for path in sorted(terraform_dir.rglob("*.tf")):
        digest.update(path.relative_to(terraform_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def execute(workspace: str, command: str, approval: str | None = None) -> dict:
    """Execute one deterministic Terraform lifecycle operation for a workspace."""
    LOGGER.info("Terraform lifecycle operation started: workspace=%s command=%s", workspace, command)
    paths = workspace_paths(workspace)
    paths["terraform"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    if command == "validate":
        result = validate_terraform_dir(paths["terraform"])
    elif command == "policy-check":
        violations = scan_terraform_dir(paths["terraform"])
        result = {"ok": not violations, "violations": violations}
    elif command == "plan":
        plan = run_terraform("plan", paths["terraform"])
        result = {"ok": plan["returncode"] == 0, "plan": plan}
        if result["ok"]:
            shown = run_terraform("show_plan_json", paths["terraform"])
            result["show"] = shown
            result["ok"] = shown["returncode"] == 0
            if result["ok"]:
                summary = summarize_plan(json.loads(shown["stdout"]))
                write_json(paths["plan_summary"], summary)
                write_json(paths["terraform"] / ".skill-plan.json", {"configuration_digest": configuration_digest(paths["terraform"]), "summary": summary})
                result["summary"] = summary
    elif command == "apply":
        requirements = read_json(paths["requirements"], default={})
        environment = requirements.get("project", {}).get("environment") if isinstance(requirements, dict) else None
        metadata_path = paths["terraform"] / ".skill-plan.json"
        metadata = read_json(metadata_path, default={})
        # Bind apply to the exact Terraform sources that produced the reviewed plan.
        if metadata.get("configuration_digest") != configuration_digest(paths["terraform"]):
            raise RuntimeError("Apply blocked: Terraform files changed after the reviewed plan; create and review a fresh plan")
        applied = apply_saved_plan(paths["terraform"], approval or "", environment=environment)
        result = {"ok": applied["returncode"] == 0, "apply": applied}
    else:
        command_name = {"fmt": "fmt", "init": "init"}[command]
        command_result = run_terraform(command_name, paths["terraform"])
        result = {"ok": command_result["returncode"] == 0, "result": command_result}
    save_command_result(result, paths["logs"] / f"terraform_{command}.json")
    LOGGER.info("Terraform lifecycle operation finished: workspace=%s command=%s ok=%s", workspace, command, result.get("ok"))
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Deterministic Terraform lifecycle CLI")
    parser.add_argument("command", choices=["fmt", "init", "validate", "policy-check", "plan", "apply"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--approval")
    args = parser.parse_args()
    result = execute(args.workspace, args.command, args.approval)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
