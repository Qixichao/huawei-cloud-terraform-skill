#!/usr/bin/env python3
"""LLM-based Python tool selector.

This module does not execute tools. It only asks the model to decide whether the
request should use Terraform flow, Python tool flow, or clarification.
"""
from __future__ import annotations

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

from llm_client import llm_client  # noqa: E402
from tools.registry import registry_for_llm  # noqa: E402


def load_prompt(name: str) -> str:
    return (SKILL_DIR / "prompts" / name).read_text(encoding="utf-8")


def render_prompt(template: str, values: dict[str, str]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def select_tool(
    user_message: str,
    requirements: dict[str, Any] | None = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    prompt_template = load_prompt("tool_selection.md")
    user_content = render_prompt(
        prompt_template,
        {
            "CURRENT_REQUIREMENTS_JSON": json.dumps(requirements or {}, ensure_ascii=False, indent=2),
            "TOOLS_REGISTRY_JSON": json.dumps(registry_for_llm(), ensure_ascii=False, indent=2),
            "USER_MESSAGE": user_message,
        },
    )
    result = llm_client.chat_json(
        [
            {
                "role": "system",
                "content": "You select the correct route or Python tool for Huawei Cloud automation. Return JSON only.",
            },
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
    )
    result.setdefault("parameters", {})
    result.setdefault("missing_fields", [])
    result.setdefault("safety_notes", [])
    return result
