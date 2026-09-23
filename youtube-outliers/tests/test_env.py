import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts.lib import env


class EnvTests(unittest.TestCase):
    def test_load_api_key_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("OTHER=1\nSCRAPECREATORS_API_KEY='abc123'\n")
            os.environ.pop("SCRAPECREATORS_API_KEY", None)
            self.assertEqual(env.load_api_key(p), "abc123")

    def test_env_var_wins_over_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("SCRAPECREATORS_API_KEY=fromfile\n")
            os.environ["SCRAPECREATORS_API_KEY"] = "fromenv"
            try:
                self.assertEqual(env.load_api_key(p), "fromenv")
            finally:
                os.environ.pop("SCRAPECREATORS_API_KEY", None)

    def test_key_can_use_explicit_fallback_path(self):
        with tempfile.TemporaryDirectory() as d:
            fallback = Path(d) / ".env"
            fallback.write_text("export SCRAPECREATORS_API_KEY=\"fromfallback\"\n")
            os.environ.pop("SCRAPECREATORS_API_KEY", None)
            with mock.patch.object(env, "FALLBACK_ENV_PATHS", (fallback,)):
                self.assertEqual(env.load_api_key(Path(d) / "missing.env"), "fromfallback")

    def test_brand_home_rejects_path_traversal(self):
        for brand in ("../secret", "/tmp/x", "a/b", "a_b", "My Channel"):
            with self.assertRaises(ValueError):
                env.brand_home(brand)

    def test_brand_home_uses_content_home(self):
        os.environ["CONTENT_HOME"] = "/tmp/ch"
        try:
            self.assertEqual(env.brand_home("brandonbuilds"), Path("/tmp/ch/brandonbuilds"))
        finally:
            os.environ.pop("CONTENT_HOME", None)


if __name__ == "__main__":
    unittest.main()
