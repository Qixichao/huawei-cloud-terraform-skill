#!/usr/bin/env python3
"""Validate the minimal Huawei Cloud Terraform Skill package."""
from __future__ import annotations

import logging
import py_compile
from pathlib import Path


LOGGER = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).resolve().parents[1]
REQUIRED = [
    "SKILL.md",
    "requirements.txt",
    "agents/openai.yaml",
    "references/workflow.md",
    "references/huawei-provider.md",
    "schemas/requirements.schema.json",
    "schemas/plan_summary.schema.json",
    "schemas/change_set.schema.json",
    "policies/security_policy.yaml",
    "policies/command_allowlist.yaml",
    "scripts/policy_check.py",
    "scripts/terraform_runner.py",
    "scripts/parse_plan.py",
    "scripts/workspace_lib.py",
    "scripts/workspace_cli.py",
    "scripts/change_set.py",
    "scripts/state_reader.py",
    "scripts/terraform_cli.py",
]

FORBIDDEN_DIRS = ["templates"]
FORBIDDEN_FILES = ["*.j2"]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    LOGGER.info("Skill package validation started: %s", SKILL_DIR)
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

    for py in (SKILL_DIR / "scripts").glob("*.py"):
        LOGGER.debug("Compiling Python script: %s", py)
        py_compile.compile(str(py), doraise=True)

    LOGGER.info("Skill package validation complete")
    print("Skill package validation passed.")
    print("Minimal deterministic Terraform Skill structure found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
