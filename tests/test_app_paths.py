import unittest
from pathlib import Path
from unittest.mock import patch

from src.paths import application_root


class ApplicationPathsTests(unittest.TestCase):
    def test_source_run_uses_project_root(self):
        expected = Path(__file__).resolve().parent.parent

        self.assertEqual(application_root(), expected)

    def test_packaged_run_uses_executable_directory(self):
        with patch("src.paths.sys.frozen", True, create=True), patch(
            "src.paths.sys.executable", r"C:\release\StockAgent.exe"
        ):
            self.assertEqual(application_root(), Path(r"C:\release"))


if __name__ == "__main__":
    unittest.main()
