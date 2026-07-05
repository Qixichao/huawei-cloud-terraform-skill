#!/usr/bin/env python3
"""Standalone CLI for Huawei Cloud Terraform LLM Direct Skill.

This CLI has no dependency on Agent Runtime or FastAPI.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from llm_client import llm_client  # noqa: E402
from parse_plan import summarize_plan  # noqa: E402
from policy_check import scan_terraform_dir  # noqa: E402
from safe_writer import write_terraform_files  # noqa: E402
from terraform_runner import apply_saved_plan, run_terraform, save_command_result  # noqa: E402


DEFAULT_REQUIREMENTS: dict[str, Any] = {
    "project": {
        "name": None,
        "environment": "dev",
        "region": None,
        "provider_version": "~> 1.93",
    },
    "network": {
        "vpc_name": None,
        "vpc_cidr": None,
        "subnets": [],
    },
    "security_groups": [],
    "ecs": [],
    "rds": [],
    "obs": [],
    "notes": [],
}


def read_json(path: str | Path, default: Any | None = None) -> Any:
    p = Path(path)
    if not p.exists():
        if default is not None:
            return deepcopy(default)
        raise FileNotFoundError(str(path))
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def deep_merge(base: Any, update: Any) -> Any:
    if isinstance(base, dict) and isinstance(update, dict):
        merged = deepcopy(base)
        for k, v in update.items():
            if v is None:
                merged[k] = None
            elif k in merged:
                merged[k] = deep_merge(merged[k], v)
            else:
                merged[k] = deepcopy(v)
        return merged
    return deepcopy(update)


def load_prompt(name: str) -> str:
    return (SKILL_DIR / "prompts" / name).read_text(encoding="utf-8")


def render_prompt(template: str, values: dict[str, str]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def workspace_paths(workspace: str | Path) -> dict[str, Path]:
    w = Path(workspace)
    return {
        "workspace": w,
        "requirements": w / "requirements.json",
        "terraform": w / "terraform",
        "llm_response": w / "llm_terraform_response.json",
        "plan_json": w / "terraform" / "plan.json",
        "plan_summary": w / "terraform" / "plan_summary.json",
        "logs": w / "logs",
    }


def cmd_init_workspace(args: argparse.Namespace) -> int:
    paths = workspace_paths(args.workspace)
    if paths["workspace"].exists() and args.force:
        shutil.rmtree(paths["workspace"])
    paths["workspace"].mkdir(parents=True, exist_ok=True)
    paths["terraform"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)

    if args.from_example:
        example_path = SKILL_DIR / "examples" / args.from_example
        if not example_path.exists():
            raise FileNotFoundError(f"Example not found: {example_path}")
        requirements = read_json(example_path)
    else:
        requirements = deepcopy(DEFAULT_REQUIREMENTS)

    write_json(paths["requirements"], requirements)
    print(f"Workspace initialized: {paths['workspace']}")
    print(f"Requirements: {paths['requirements']}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    paths = workspace_paths(args.workspace)
    paths["workspace"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    current = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)

    prompt_template = load_prompt("requirements_extraction.md")
    user_content = render_prompt(
        prompt_template,
        {
            "CURRENT_REQUIREMENTS_JSON": json.dumps(current, ensure_ascii=False, indent=2),
            "USER_MESSAGE": args.message,
        },
    )
    messages = [
        {
            "role": "system",
            "content": "You extract Huawei Cloud Terraform requirements. Return JSON only.",
        },
        {"role": "user", "content": user_content},
    ]
    result = llm_client.chat_json(messages, temperature=args.temperature)
    write_json(paths["logs"] / "last_requirements_extraction.json", result)

    updated = result.get("updated_requirements", {})
    merged = deep_merge(current, updated)
    write_json(paths["requirements"], merged)

    print("Requirements updated:")
    print(json.dumps(merged, ensure_ascii=False, indent=2))

    missing = result.get("missing_fields") or []
    if missing:
        print("\nMissing fields:")
        for item in missing:
            if isinstance(item, dict):
                print(f"- {item.get('field')}: {item.get('question') or item.get('reason')}")
            else:
                print(f"- {item}")

    next_question = result.get("next_question")
    if next_question:
        print(f"\nNext question: {next_question}")

    risk_notes = result.get("risk_notes") or []
    if risk_notes:
        print("\nRisk notes:")
        for note in risk_notes:
            print(f"- {note}")

    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    paths = workspace_paths(args.workspace)
    requirements_path = Path(args.requirements) if args.requirements else paths["requirements"]
    requirements = read_json(requirements_path)
    terraform_dir = Path(args.terraform_dir) if args.terraform_dir else paths["terraform"]
    terraform_dir.mkdir(parents=True, exist_ok=True)

    prompt_template = load_prompt("terraform_file_generator.md")
    user_content = render_prompt(
        prompt_template,
        {"REQUIREMENTS_JSON": json.dumps(requirements, ensure_ascii=False, indent=2)},
    )
    messages = [
        {
            "role": "system",
            "content": "You generate Huawei Cloud Terraform files. Return JSON only with files[].",
        },
        {"role": "user", "content": user_content},
    ]

    result = llm_client.chat_json(messages, temperature=args.temperature)
    write_json(paths["llm_response"], result)
    written = write_terraform_files(result, terraform_dir)

    print("LLM-generated Terraform files written:")
    for p in written:
        print(f"- {p}")

    if result.get("assumptions"):
        print("\nAssumptions:")
        for item in result["assumptions"]:
            print(f"- {item}")

    if result.get("risk_notes"):
        print("\nRisk notes:")
        for item in result["risk_notes"]:
            print(f"- {item}")

    return 0


def cmd_write_from_response(args: argparse.Namespace) -> int:
    response = read_json(args.response)
    written = write_terraform_files(response, args.terraform_dir)
    for p in written:
        print(f"Wrote {p}")
    return 0


def cmd_policy_check(args: argparse.Namespace) -> int:
    violations = scan_terraform_dir(args.terraform_dir, args.policy)
    if violations:
        print("Policy check failed:")
        for v in violations:
            print(f"- {v}")
        return 2
    print("Policy check passed.")
    return 0


def cmd_terraform(args: argparse.Namespace) -> int:
    terraform_dir = Path(args.terraform_dir)
    terraform_dir.mkdir(parents=True, exist_ok=True)
    log_dir = terraform_dir.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.tf_command == "apply":
        requirements = read_json(terraform_dir.parent / "requirements.json", default={})
        env = requirements.get("project", {}).get("environment") if isinstance(requirements, dict) else None
        result = apply_saved_plan(terraform_dir, args.approval or "", environment=env)
    elif args.tf_command == "show-plan":
        result = run_terraform("show_plan_json", terraform_dir)
        if result["returncode"] == 0:
            plan_json_path = terraform_dir / "plan.json"
            plan_json_path.write_text(result["stdout"], encoding="utf-8")
            plan = json.loads(result["stdout"])
            summary = summarize_plan(plan)
            write_json(terraform_dir / "plan_summary.json", summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            save_command_result(result, log_dir / "terraform_show_plan_json.json")
            return 0
    else:
        mapping = {
            "fmt": "fmt",
            "init": "init",
            "validate": "validate",
            "plan": "plan",
            "output": "output_json",
        }
        result = run_terraform(mapping[args.tf_command], terraform_dir)

    save_command_result(result, log_dir / f"terraform_{args.tf_command}.json")
    if result["stdout"]:
        print(result["stdout"])
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr)
    return int(result["returncode"])


def cmd_review_plan(args: argparse.Namespace) -> int:
    summary = read_json(args.plan_summary)
    prompt_template = load_prompt("plan_reviewer.md")
    user_content = render_prompt(
        prompt_template,
        {"PLAN_SUMMARY_JSON": json.dumps(summary, ensure_ascii=False, indent=2)},
    )
    result_text = llm_client.chat(
        [
            {"role": "system", "content": "You review Terraform plan summaries in Chinese."},
            {"role": "user", "content": user_content},
        ],
        temperature=args.temperature,
    )
    print(result_text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Huawei Cloud Terraform LLM Direct Skill CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-workspace", help="Create a workspace and requirements.json")
    p.add_argument("--workspace", required=True)
    p.add_argument("--from-example")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init_workspace)

    p = sub.add_parser("chat", help="Update requirements through LLM-based conversation")
    p.add_argument("--workspace", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--temperature", type=float, default=0.1)
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("generate", help="Ask the LLM to directly generate Terraform files")
    p.add_argument("--workspace", required=True)
    p.add_argument("--requirements")
    p.add_argument("--terraform-dir")
    p.add_argument("--temperature", type=float, default=0.1)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("write-from-response", help="Write Terraform files from an existing LLM files JSON response")
    p.add_argument("--response", required=True)
    p.add_argument("--terraform-dir", required=True)
    p.set_defaults(func=cmd_write_from_response)

    p = sub.add_parser("policy-check", help="Run static policy checks")
    p.add_argument("--terraform-dir", required=True)
    p.add_argument("--policy", default=str(SKILL_DIR / "policies" / "security_policy.yaml"))
    p.set_defaults(func=cmd_policy_check)

    p = sub.add_parser("terraform", help="Run allowlisted Terraform commands")
    p.add_argument("tf_command", choices=["fmt", "init", "validate", "plan", "show-plan", "apply", "output"])
    p.add_argument("--terraform-dir", required=True)
    p.add_argument("--approval")
    p.set_defaults(func=cmd_terraform)

    p = sub.add_parser("review-plan", help="Ask LLM to explain a plan summary")
    p.add_argument("--plan-summary", required=True)
    p.add_argument("--temperature", type=float, default=0.1)
    p.set_defaults(func=cmd_review_plan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
