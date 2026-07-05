#!/usr/bin/env python3
"""Minimal OpenAI-compatible LLM client for the standalone skill."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "infra-llm")
        self.api_key = os.getenv("LLM_API_KEY", "dummy")
        self.timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        # Most OpenAI-compatible servers support this. If yours does not, set LLM_JSON_MODE=false.
        if os.getenv("LLM_JSON_MODE", "true").lower() == "true":
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMClientError(f"Failed to call LLM endpoint {self.base_url}: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMClientError(f"LLM returned HTTP {resp.status_code}: {resp.text[:1000]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected LLM response shape: {data}") from exc

    def chat_json(self, messages: list[dict[str, str]], temperature: float = 0.1) -> dict[str, Any]:
        text = self.chat(messages, temperature=temperature)
        return parse_json_from_text(text)


def parse_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise LLMClientError(f"LLM did not return valid JSON: {text[:1000]}")


llm_client = LLMClient()
