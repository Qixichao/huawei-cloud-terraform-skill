#!/usr/bin/env python3
"""Static policy checker for generated Terraform files."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "policies" / "security_policy.yaml"


class PolicyViolation(RuntimeError):
    pass


def load_policy(path: str | Path = DEFAULT_POLICY) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def scan_terraform_dir(terraform_dir: str | Path, policy_path: str | Path = DEFAULT_POLICY) -> list[str]:
    terraform_dir = Path(terraform_dir)
    policy = load_policy(policy_path)
    violations: list[str] = []

    tf_files = list(terraform_dir.rglob("*.tf")) + list(terraform_dir.rglob("*.tfvars")) + list(terraform_dir.rglob("*.tfvars.example"))
    for file_path in tf_files:
        rel = file_path.relative_to(terraform_dir)
        text = file_path.read_text(encoding="utf-8", errors="ignore")

        for pattern in policy.get("secret_patterns", []):
            if re.search(pattern, text):
                violations.append(f"{rel}: possible hardcoded secret matched pattern {pattern}")

        lower_text = text.lower()
        for term in policy.get("blocked_terms", []):
            if term.lower() in lower_text:
                violations.append(f"{rel}: blocked term found: {term}")

        for cidr in policy.get("blocked_public_ingress", {}).get("cidrs", []):
            if cidr in text:
                for port in policy.get("blocked_public_ingress", {}).get("ports", []):
                    port_patterns = [
                        rf"\bport\s*=\s*{port}\b",
                        rf"\bfrom_port\s*=\s*{port}\b",
                        rf"\bto_port\s*=\s*{port}\b",
                        rf"\bports?\s*=\s*\[?\s*{port}\b",
                    ]
                    if any(re.search(p, text) for p in port_patterns):
                        violations.append(f"{rel}: public CIDR {cidr} with high-risk port {port}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Run static policy checks on Terraform files.")
    parser.add_argument("--terraform-dir", required=True)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    violations = scan_terraform_dir(args.terraform_dir, args.policy)
    if violations:
        print("Policy check failed:")
        for v in violations:
            print(f"- {v}")
        return 2

    print("Policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
