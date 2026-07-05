#!/usr/bin/env python3
"""Web UI server for the Huawei Cloud Terraform LLM Direct Skill.

This server is standalone. It does not depend on the previous Agent Runtime.
It exposes a local browser UI and API wrappers around the same Skill scripts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from llm_client import llm_client  # noqa: E402
from parse_plan import summarize_plan  # noqa: E402
from policy_check import scan_terraform_dir  # noqa: E402
from safe_writer import write_terraform_files  # noqa: E402
from skill_cli import (  # noqa: E402
    DEFAULT_REQUIREMENTS,
    deep_merge,
    load_prompt,
    read_json,
    render_prompt,
    write_json,
    workspace_paths,
)
from terraform_runner import apply_saved_plan, run_terraform, save_command_result  # noqa: E402
from tool_selector import select_tool  # noqa: E402
from tools.executor import execute_tool  # noqa: E402
from tools.registry import list_tool_specs, registry_for_llm  # noqa: E402

WEB_DIR = SKILL_DIR / "web"
STATIC_DIR = WEB_DIR / "static"
WORKSPACES_DIR = SKILL_DIR / "workspaces"
WORKSPACE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

app = FastAPI(title="Huawei Cloud Terraform LLM Direct Skill Web UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class InitWorkspaceRequest(BaseModel):
    workspace: str = Field(default="demo", description="Workspace name under ./workspaces")
    from_example: str | None = Field(default=None, description="Example requirements JSON filename")
    force: bool = False


class ChatRequest(BaseModel):
    workspace: str = "demo"
    message: str
    temperature: float = 0.1


class GenerateRequest(BaseModel):
    workspace: str = "demo"
    temperature: float = 0.1


class PolicyRequest(BaseModel):
    workspace: str = "demo"


class TerraformRequest(BaseModel):
    workspace: str = "demo"
    command: str
    approval: str | None = None


class FileWriteRequest(BaseModel):
    workspace: str = "demo"
    path: str
    content: str


class FileReadRequest(BaseModel):
    workspace: str = "demo"
    path: str


class RequirementsSaveRequest(BaseModel):
    workspace: str = "demo"
    requirements: dict[str, Any]


class ReviewPlanRequest(BaseModel):
    workspace: str = "demo"
    temperature: float = 0.1


class ToolSelectRequest(BaseModel):
    workspace: str = "demo"
    message: str
    temperature: float = 0.1


class ToolRunRequest(BaseModel):
    workspace: str = "demo"
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


def safe_workspace_root(workspace: str) -> Path:
    workspace = workspace.strip() or "demo"
    if not WORKSPACE_RE.match(workspace):
        raise HTTPException(status_code=400, detail="Invalid workspace name. Use letters, numbers, dot, dash, underscore only.")
    root = (WORKSPACES_DIR / workspace).resolve()
    base = WORKSPACES_DIR.resolve()
    if base not in root.parents and root != base:
        raise HTTPException(status_code=400, detail="Invalid workspace path")
    return root


def get_paths(workspace: str) -> dict[str, Path]:
    return workspace_paths(safe_workspace_root(workspace))


def json_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail=str(exc))


def safe_file_path(workspace: str, rel_path: str) -> Path:
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    if not rel_path or ".." in Path(rel_path).parts:
        raise HTTPException(status_code=400, detail="Invalid file path")
    terraform_dir = get_paths(workspace)["terraform"].resolve()
    target = (terraform_dir / rel_path).resolve()
    if terraform_dir not in target.parents and target != terraform_dir:
        raise HTTPException(status_code=400, detail="File path outside Terraform directory")
    allowed_suffixes = {".tf", ".tfvars", ".md", ".json", ".txt"}
    if target.suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail=f"File suffix not allowed: {target.suffix}")
    return target


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "skill_dir": str(SKILL_DIR),
        "llm_base_url": os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
        "llm_model": os.getenv("LLM_MODEL", "infra-llm"),
        "allow_apply": os.getenv("ALLOW_APPLY", "false"),
        "allow_prod_apply": os.getenv("ALLOW_PROD_APPLY", "false"),
        "python_tools": {
            "registered": len(list_tool_specs()),
            "enabled": len(list_tool_specs(enabled_only=True)),
        },
        "huaweicloud_auth": {
            "HW_ACCESS_KEY": "set" if os.getenv("HW_ACCESS_KEY") else "missing",
            "HW_SECRET_KEY": "set" if os.getenv("HW_SECRET_KEY") else "missing",
            "HW_REGION_NAME": os.getenv("HW_REGION_NAME", "missing"),
        },
    }


@app.get("/api/examples")
def examples() -> dict[str, Any]:
    return {"examples": sorted([p.name for p in (SKILL_DIR / "examples").glob("*.json")])}


@app.post("/api/workspace/init")
def init_workspace(req: InitWorkspaceRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        if paths["workspace"].exists() and req.force:
            shutil.rmtree(paths["workspace"])
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["terraform"].mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)

        if req.from_example:
            example_path = SKILL_DIR / "examples" / req.from_example
            if not example_path.exists():
                raise HTTPException(status_code=404, detail=f"Example not found: {req.from_example}")
            requirements = read_json(example_path)
        else:
            requirements = deepcopy(DEFAULT_REQUIREMENTS)
        write_json(paths["requirements"], requirements)
        return {"ok": True, "workspace": req.workspace, "requirements": requirements}
    except HTTPException:
        raise
    except Exception as exc:
        raise json_error(exc)


@app.get("/api/workspace/{workspace}/requirements")
def get_requirements(workspace: str) -> dict[str, Any]:
    try:
        paths = get_paths(workspace)
        data = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
        return {"requirements": data}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/workspace/requirements")
def save_requirements(req: RequirementsSaveRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["terraform"].mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        write_json(paths["requirements"], req.requirements)
        return {"ok": True, "requirements": req.requirements}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["terraform"].mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        current = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
        prompt_template = load_prompt("requirements_extraction.md")
        user_content = render_prompt(
            prompt_template,
            {
                "CURRENT_REQUIREMENTS_JSON": json.dumps(current, ensure_ascii=False, indent=2),
                "USER_MESSAGE": req.message,
            },
        )
        result = llm_client.chat_json(
            [
                {"role": "system", "content": "You extract Huawei Cloud Terraform requirements. Return JSON only."},
                {"role": "user", "content": user_content},
            ],
            temperature=req.temperature,
        )
        write_json(paths["logs"] / "last_requirements_extraction.json", result)
        updated = result.get("updated_requirements", {})
        merged = deep_merge(current, updated)
        write_json(paths["requirements"], merged)
        return {
            "ok": True,
            "requirements": merged,
            "missing_fields": result.get("missing_fields", []),
            "next_question": result.get("next_question"),
            "risk_notes": result.get("risk_notes", []),
            "raw": result,
        }
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/generate")
def generate(req: GenerateRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        requirements = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
        terraform_dir = paths["terraform"]
        terraform_dir.mkdir(parents=True, exist_ok=True)
        prompt_template = load_prompt("terraform_file_generator.md")
        user_content = render_prompt(
            prompt_template,
            {"REQUIREMENTS_JSON": json.dumps(requirements, ensure_ascii=False, indent=2)},
        )
        result = llm_client.chat_json(
            [
                {"role": "system", "content": "You generate Huawei Cloud Terraform files. Return JSON only with files[]."},
                {"role": "user", "content": user_content},
            ],
            temperature=req.temperature,
        )
        write_json(paths["llm_response"], result)
        written = write_terraform_files(result, terraform_dir)
        return {
            "ok": True,
            "written": [str(Path(p).relative_to(terraform_dir)) if Path(p).is_absolute() else str(p) for p in written],
            "assumptions": result.get("assumptions", []),
            "risk_notes": result.get("risk_notes", []),
            "raw": result,
        }
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/generate/example")
def generate_from_example(req: PolicyRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        terraform_dir = paths["terraform"]
        terraform_dir.mkdir(parents=True, exist_ok=True)
        response = read_json(SKILL_DIR / "examples" / "terraform_files_response.example.json")
        written = write_terraform_files(response, terraform_dir)
        return {"ok": True, "written": [str(Path(p).relative_to(terraform_dir)) if Path(p).is_absolute() else str(p) for p in written]}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/policy-check")
def policy_check(req: PolicyRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        violations = scan_terraform_dir(paths["terraform"], str(SKILL_DIR / "policies" / "security_policy.yaml"))
        out = {"ok": not bool(violations), "violations": violations}
        write_json(paths["logs"] / "policy_check.json", out)
        return out
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/terraform")
def terraform(req: TerraformRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        terraform_dir = paths["terraform"]
        terraform_dir.mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        if req.command == "apply":
            requirements = read_json(paths["requirements"], default={})
            env = requirements.get("project", {}).get("environment") if isinstance(requirements, dict) else None
            result = apply_saved_plan(terraform_dir, req.approval or "", environment=env)
        elif req.command == "show-plan":
            result = run_terraform("show_plan_json", terraform_dir)
            if result["returncode"] == 0:
                (terraform_dir / "plan.json").write_text(result["stdout"], encoding="utf-8")
                summary = summarize_plan(json.loads(result["stdout"]))
                write_json(terraform_dir / "plan_summary.json", summary)
                save_command_result(result, paths["logs"] / "terraform_show_plan_json.json")
                return {"ok": True, "result": result, "summary": summary}
        else:
            mapping = {"fmt": "fmt", "init": "init", "validate": "validate", "plan": "plan", "output": "output_json"}
            if req.command not in mapping:
                raise HTTPException(status_code=400, detail=f"Unsupported terraform command: {req.command}")
            result = run_terraform(mapping[req.command], terraform_dir)
        save_command_result(result, paths["logs"] / f"terraform_{req.command}.json")
        return {"ok": result.get("returncode") == 0, "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise json_error(exc)



@app.get("/api/tools")
def tools_list() -> dict[str, Any]:
    try:
        return {
            "tools": [spec.public_dict() for spec in list_tool_specs()],
            "enabled_tools": registry_for_llm(),
        }
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/tools/select")
def tools_select(req: ToolSelectRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        requirements = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
        result = select_tool(req.message, requirements=requirements, temperature=req.temperature)
        write_json(paths["logs"] / "last_tool_selection.json", result)
        return {"ok": True, "selection": result}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/tools/run")
def tools_run(req: ToolRunRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        requirements = read_json(paths["requirements"], default=DEFAULT_REQUIREMENTS)
        result = execute_tool(
            req.tool_name,
            req.parameters,
            workspace=paths["workspace"],
            skill_dir=SKILL_DIR,
            requirements=requirements,
            dry_run=req.dry_run,
        )
        write_json(paths["logs"] / f"tool_{req.tool_name}.json", result)
        return {"ok": bool(result.get("ok")), "result": result}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/review-plan")
def review_plan(req: ReviewPlanRequest) -> dict[str, Any]:
    try:
        paths = get_paths(req.workspace)
        summary_path = paths["terraform"] / "plan_summary.json"
        if not summary_path.exists():
            raise HTTPException(status_code=404, detail="plan_summary.json not found. Run show-plan first.")
        summary = read_json(summary_path)
        prompt_template = load_prompt("plan_reviewer.md")
        user_content = render_prompt(prompt_template, {"PLAN_SUMMARY_JSON": json.dumps(summary, ensure_ascii=False, indent=2)})
        review = llm_client.chat(
            [
                {"role": "system", "content": "You review Terraform plan summaries."},
                {"role": "user", "content": user_content},
            ],
            temperature=req.temperature,
        )
        (paths["logs"] / "plan_review.md").write_text(review, encoding="utf-8")
        return {"ok": True, "review": review}
    except HTTPException:
        raise
    except Exception as exc:
        raise json_error(exc)


@app.get("/api/workspace/{workspace}/files")
def list_files(workspace: str) -> dict[str, Any]:
    try:
        terraform_dir = get_paths(workspace)["terraform"]
        terraform_dir.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []
        for p in sorted(terraform_dir.rglob("*")):
            if p.is_file():
                rel = p.relative_to(terraform_dir).as_posix()
                if p.suffix in {".tf", ".tfvars", ".md", ".json", ".txt"}:
                    files.append({"path": rel, "size": p.stat().st_size})
        return {"files": files}
    except Exception as exc:
        raise json_error(exc)


@app.post("/api/file/read")
def read_file(req: FileReadRequest) -> dict[str, Any]:
    try:
        p = safe_file_path(req.workspace, req.path)
        if not p.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return {"path": req.path, "content": p.read_text(encoding="utf-8")}
    except HTTPException:
        raise
    except Exception as exc:
        raise json_error(exc)



@app.post("/api/file/write")
def write_file(req: FileWriteRequest) -> dict[str, Any]:
    try:
        p = safe_file_path(req.workspace, req.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(req.content, encoding="utf-8")
        return {"ok": True, "path": req.path, "size": p.stat().st_size}
    except HTTPException:
        raise
    except Exception as exc:
        raise json_error(exc)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8080"))
    uvicorn.run("web_server:app", host=host, port=port, reload=True, app_dir=str(SCRIPT_DIR))
