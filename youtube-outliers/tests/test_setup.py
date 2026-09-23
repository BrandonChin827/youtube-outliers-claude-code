import importlib.util
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


SETUP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "setup.py"
SPEC = importlib.util.spec_from_file_location("youtube_outliers_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_write_values_is_private_and_never_prints_secret(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            secret = "private-test-key"
            output = StringIO()
            with redirect_stdout(output):
                setup.write_values(path, {"SCRAPECREATORS_API_KEY": secret, "CONTENT_HOME": "/tmp/content"})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertIn(secret, path.read_text())
            self.assertNotIn(secret, output.getvalue())

    def test_create_brand_does_not_overwrite_existing_profile(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profile, tracked, notion = setup.create_brand(root, "my-channel")
            profile.write_text("custom\n")
            setup.create_brand(root, "my-channel")
            self.assertEqual(profile.read_text(), "custom\n")
            self.assertTrue(tracked.exists())
            self.assertFalse(notion.exists())

    def test_check_reports_status_without_secret_value(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / ".env"
            secret = "never-print-me"
            setup.write_values(config, {"SCRAPECREATORS_API_KEY": secret, "CONTENT_HOME": str(root / "content")})
            setup.create_brand(root / "content", "my-channel")
            tracked = root / "content" / "my-channel" / "brand" / "tracked-accounts" / "youtube.md"
            tracked.write_text("| Handle | Category | Notes |\n|---|---|---|\n| @example | AI | test |\n")
            output = StringIO()
            with mock.patch.object(setup.env, "ENV_PATH", config), \
                 mock.patch.object(setup.env, "FALLBACK_ENV_PATHS", ()), \
                 mock.patch.dict(os.environ, {"CONTENT_HOME": str(root / "content"), "SCRAPECREATORS_API_KEY": secret}, clear=False), \
                 redirect_stdout(output):
                code = setup.check("my-channel")
            self.assertEqual(code, 0)
            self.assertNotIn(secret, output.getvalue())
            self.assertIn("configured", output.getvalue())

    def test_validate_brand_rejects_paths(self):
        for value in ("../secret", "My Channel", "/tmp/x", "a_b"):
            with self.assertRaises(ValueError):
                setup.validate_brand(value)


if __name__ == "__main__":
    unittest.main()