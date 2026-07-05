#!/usr/bin/env python3
"""Validate the standalone skill package structure."""
from __future__ import annotations

import py_compile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REQUIRED = [
    "SKILL.md",
    "skill.yaml",
    "README.md",
    "requirements.txt",
    "prompts/requirements_extraction.md",
    "prompts/terraform_file_generator.md",
    "prompts/validate_error_repair.md",
    "prompts/plan_reviewer.md",
    "schemas/requirements.schema.json",
    "schemas/terraform_files.schema.json",
    "schemas/plan_summary.schema.json",
    "policies/security_policy.yaml",
    "policies/command_allowlist.yaml",
    "policies/generation_policy.yaml",
    "scripts/skill_cli.py",
    "scripts/llm_client.py",
    "scripts/safe_writer.py",
    "scripts/policy_check.py",
    "scripts/terraform_runner.py",
    "scripts/parse_plan.py",
    "examples/requirements.dev.vpc-ecs-rds.json",
    "examples/terraform_files_response.example.json",
    "prompts/tool_selection.md",
    "schemas/tool_selection.schema.json",
    "schemas/tool_result.schema.json",
    "scripts/tool_selector.py",
    "scripts/tools_cli.py",
    "tools/base.py",
    "tools/registry.py",
    "tools/executor.py",
    "tools/registry.yaml",
    "tools/samples/echo_tool.py",
]

FORBIDDEN_DIRS = ["templates"]
FORBIDDEN_FILES = ["*.j2"]


def main() -> int:
    missing = [p for p in REQUIRED if not (SKILL_DIR / p).exists()]
    if missing:
        print("Missing required files:")
        for p in missing:
            print(f"- {p}")
        return 2

    for d in FORBIDDEN_DIRS:
        if (SKILL_DIR / d).exists():
            print(f"Forbidden directory exists: {d}")
            return 2

    for pattern in FORBIDDEN_FILES:
        found = list(SKILL_DIR.rglob(pattern))
        if found:
            print(f"Forbidden files found for pattern {pattern}:")
            for f in found:
                print(f"- {f.relative_to(SKILL_DIR)}")
            return 2

    for py in list((SKILL_DIR / "scripts").glob("*.py")) + list((SKILL_DIR / "tools").rglob("*.py")):
        py_compile.compile(str(py), doraise=True)

    print("Skill package validation passed.")
    print("No templates/ directory and no .j2 files found.")
    print("Python tool framework files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
