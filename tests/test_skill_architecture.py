import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "huawei-cloud-terraform"
sys.path.insert(0, str(SKILL_ROOT))

from scripts.change_set import apply_change_set
from scripts.terraform_cli import configuration_digest
from scripts.workspace_cli import adopt, initialize, inspect


class SkillArchitectureTests(unittest.TestCase):
    def test_workspace_reinitialization_preserves_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("scripts.workspace_lib.WORKSPACES_DIR", Path(tmpdir)):
            initialize("demo")
            state = Path(tmpdir) / "demo" / "terraform" / "terraform.tfstate"
            state.write_text('{"version": 4}', encoding="utf-8")

            result = initialize("demo")

            self.assertTrue(result["preserved_existing_state"])
            self.assertTrue(state.exists())

    def test_change_set_requires_explicit_delete_and_preserves_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("scripts.workspace_lib.WORKSPACES_DIR", Path(tmpdir)):
            initialize("demo")
            document = {
                "reason": "create network",
                "files_to_write": [{"path": "network.tf", "content": "resource \"x\" \"y\" {}"}],
                "files_to_delete": [],
            }
            apply_change_set("demo", document, dry_run=False, allow_delete=False)
            state = Path(tmpdir) / "demo" / "terraform" / "terraform.tfstate"
            state.write_text('{"version": 4}', encoding="utf-8")
            delete = {"reason": "remove network", "files_to_write": [], "files_to_delete": ["network.tf"]}

            with self.assertRaisesRegex(ValueError, "--allow-delete"):
                apply_change_set("demo", delete, dry_run=False, allow_delete=False)
            apply_change_set("demo", delete, dry_run=False, allow_delete=True)

            self.assertTrue(state.exists())
            self.assertFalse((Path(tmpdir) / "demo" / "terraform" / "network.tf").exists())

    def test_inspect_reports_files_without_mutating_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("scripts.workspace_lib.WORKSPACES_DIR", Path(tmpdir)):
            initialize("demo")
            terraform = Path(tmpdir) / "demo" / "terraform"
            (terraform / "main.tf").write_text("terraform {}", encoding="utf-8")

            result = inspect("demo")

            self.assertEqual(result["terraform_files"], ["main.tf"])
            self.assertFalse(result["state"]["state_exists"])

    def test_legacy_file_requires_explicit_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("scripts.workspace_lib.WORKSPACES_DIR", Path(tmpdir)):
            initialize("demo")
            terraform = Path(tmpdir) / "demo" / "terraform"
            (terraform / "legacy.tf").write_text("terraform {}", encoding="utf-8")

            result = adopt("demo", ["legacy.tf"])

            self.assertEqual(result["managed_files"], ["legacy.tf"])

    def test_configuration_digest_changes_when_terraform_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            terraform = Path(tmpdir)
            source = terraform / "main.tf"
            source.write_text("terraform {}", encoding="utf-8")
            before = configuration_digest(terraform)
            source.write_text('resource "x" "y" {}', encoding="utf-8")
            self.assertNotEqual(before, configuration_digest(terraform))


if __name__ == "__main__":
    unittest.main()
