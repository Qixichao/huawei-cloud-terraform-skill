---
name: huawei-cloud-terraform
description: Create, inspect, update, validate, plan, review, and safely apply Huawei Cloud Terraform infrastructure through deterministic local tools. Use when Codex receives English or Chinese requests involving Huawei Cloud VPCs, subnets, security groups, ECS, RDS, OBS, infrastructure as code, Terraform changes, plan review, or controlled deployment. Also use when modifying or deleting resources already managed by a workspace; preserve Terraform resource addresses and state across turns.
---

# Huawei Cloud Terraform

Use Codex for intent recognition, requirements reasoning, Terraform authoring, and validation repair. Use bundled Python scripts only for deterministic workspace, file, policy, state, plan, and apply operations. Do not call another LLM from this Skill.

## Workflow

1. Determine whether the request creates a new workspace or changes an existing one.
2. Run `python scripts/workspace_cli.py inspect --workspace <name>` before editing.
3. For an existing workspace, read `requirements.json`, every managed `.tf` file, and the returned Terraform state addresses.
   If legacy `.tf` files exist but are not in `managed_files`, ask before adopting them, then run `python scripts/workspace_cli.py adopt --workspace <name> --files <paths...>`.
4. Read [references/workflow.md](references/workflow.md). For provider-specific authoring, also read [references/huawei-provider.md](references/huawei-provider.md).
5. Preserve existing Terraform resource addresses. Represent intended requirement changes with stable `logical_id` values and explicit `upsert` or `delete` operations.
6. Prepare a change-set JSON that lists complete `files_to_write` and explicit `files_to_delete` entries. Never infer deletion from an omitted file.
7. Preview it with `python scripts/change_set.py apply --workspace <name> --change-set <file> --dry-run`.
8. Apply the file change-set only after reviewing its preview. File deletion requires `--allow-delete`.
9. Run formatting, initialization, validation, policy check, and a fresh plan through `scripts/terraform_cli.py`.
10. Read the fresh plan summary. Clearly report create, update, delete, and replace counts. Require explicit user approval for destructive changes.
11. Run apply only when the user explicitly approves the exact fresh plan and the environment gates permit it.

## Safety rules

- Never delete or recreate a workspace to update resources.
- Never edit or delete `.tfstate`, `.terraform`, lock files, or saved plans through a change-set.
- Never automatically pass an approval phrase on the user's behalf.
- Never run apply before generating a new saved plan for the current configuration.
- Never treat an absent array item or omitted `.tf` file as deletion.
- Never hardcode credentials or secrets.
- Stop and ask before a plan containing delete or replace actions unless the user already explicitly requested those exact destructive changes.
- Do not import unmanaged cloud resources automatically. Explain that adoption requires a separately approved import workflow.

## Contracts

- Use [schemas/requirements.schema.json](schemas/requirements.schema.json) for canonical requirements with stable logical IDs.
- Use [schemas/change_set.schema.json](schemas/change_set.schema.json) for reviewed file changes.
- Use [schemas/plan_summary.schema.json](schemas/plan_summary.schema.json) when interpreting plan summaries.
