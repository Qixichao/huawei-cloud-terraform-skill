#!/usr/bin/env python3
"""Parse terraform show -json output into a concise summary."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


def summarize_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
    """Classify Terraform resource actions and flag destructive operations."""
    summary: dict[str, Any] = {
        "create": [],
        "update": [],
        "delete": [],
        "replace": [],
        "no_op": [],
        "unknown": [],
        "counts": {},
        "risk_flags": [],
    }

    for change in plan_json.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        item = {
            "address": change.get("address"),
            "type": change.get("type"),
            "name": change.get("name"),
            "actions": actions,
        }

        if actions == ["create"]:
            summary["create"].append(item)
        elif actions == ["update"]:
            summary["update"].append(item)
        elif actions == ["delete"]:
            summary["delete"].append(item)
            summary["risk_flags"].append(f"Delete operation: {item['address']}")
        elif "delete" in actions and "create" in actions:
            summary["replace"].append(item)
            summary["risk_flags"].append(f"Replace operation: {item['address']}")
        elif actions == ["no-op"]:
            summary["no_op"].append(item)
        else:
            summary["unknown"].append(item)

    for key in ["create", "update", "delete", "replace", "no_op", "unknown"]:
        summary["counts"][key] = len(summary[key])

    LOGGER.info("Terraform plan summarized: counts=%s risks=%d", summary["counts"], len(summary["risk_flags"]))
    return summary


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--output", required=False)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    LOGGER.info("Parsing Terraform plan JSON: %s", args.plan_json)
    summary = summarize_plan(plan)
    output = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        LOGGER.info("Plan summary written: %s", args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
