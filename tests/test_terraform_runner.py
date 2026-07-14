import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.terraform_runner import apply_saved_plan, validate_terraform_dir


class TerraformRunnerTests(unittest.TestCase):
    def test_apply_does_not_require_allow_apply_environment_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            terraform_dir = Path(tmpdir)
            (terraform_dir / "tfplan").touch()
            expected = {"returncode": 0, "stdout": "", "stderr": ""}

            with patch.dict("os.environ", {}, clear=True), patch(
                "scripts.terraform_runner.run_terraform", return_value=expected
            ) as run_terraform:
                result = apply_saved_plan(
                    terraform_dir,
                    "Confirm to execute apply",
                    environment="dev",
                )

            self.assertEqual(result, expected)
            run_terraform.assert_called_once_with("apply_saved_plan", terraform_dir)

    def test_validate_terraform_dir_reports_invalid_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            terraform_dir = Path(tmpdir)
            (terraform_dir / "main.tf").write_text(
                'resource "foo" "bar" {}\n',
                encoding="utf-8",
            )

            result = validate_terraform_dir(terraform_dir, timeout=180)

            self.assertFalse(result["ok"])
            self.assertNotEqual(result["validate"]["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
