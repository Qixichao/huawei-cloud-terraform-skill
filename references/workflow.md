# Workspace lifecycle

## Existing workspace inspection

Always inspect before changing files. Treat `terraform.tfstate` as authoritative for managed resource addresses and the managed-file manifest as authoritative for files this Skill may delete.

For a legacy workspace without a manifest, explicitly review and adopt existing `.tf` files with `workspace_cli.py adopt`. Adoption grants the Skill permission to update or explicitly delete those files; it does not modify their contents.

## Requirement operations

Give each resource a stable `logical_id`. Use `operation: upsert` for creation or modification and `operation: delete` only for explicit deletion. When updating a resource array, retain every unchanged item in the canonical requirements document.

## Change-set contract

Use `schemas/change_set.schema.json`. Include full contents for every file being written. Put obsolete managed paths in `files_to_delete`; omission never means deletion. Preview before applying. Require the user to approve file deletions or destructive plan actions.

## Verification sequence

Run `fmt`, `init`, `validate`, policy check, and `plan` in that order. A plan command must create a new `tfplan`; summarize that exact plan immediately. Do not reuse an earlier plan after files change.

## Apply

Apply only the saved plan that was just reviewed. Require the configured approval phrase from the user and environment gates. Never synthesize approval from intent classification.
The deterministic CLI records a digest of all `.tf` files with the saved plan and blocks apply if any configuration file changed afterward.
