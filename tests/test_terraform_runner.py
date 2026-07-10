import tempfile
import unittest
from pathlib import Path

from scripts.terraform_runner import validate_terraform_dir


class TerraformRunnerTests(unittest.TestCase):
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
