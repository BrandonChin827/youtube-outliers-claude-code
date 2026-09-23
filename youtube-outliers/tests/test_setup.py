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
from scripts.lib import tracked as tracked_lib  # noqa: E402


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

    def test_add_channels_appends_new_handles_only(self):
        with tempfile.TemporaryDirectory() as d:
            _, tracked, _ = setup.create_brand(Path(d), "my-channel")
            tracked.write_text(tracked.read_text() + "| @existing | AI | keep me |\n")
            added = setup.add_channels(tracked, "@Existing, newone, https://www.youtube.com/@third, @newone")
            self.assertEqual(added, ["@newone", "@third"])
            text = tracked.read_text()
            self.assertIn("| @existing | AI | keep me |", text)
            self.assertEqual(text.count("@newone"), 1)
            handles = [row["handle"] for row in tracked_lib.load_tracked(tracked)]
            self.assertEqual(handles, ["@existing", "@newone", "@third"])

    def test_add_channels_rejects_unsafe_handles(self):
        with tempfile.TemporaryDirectory() as d:
            _, tracked, _ = setup.create_brand(Path(d), "my-channel")
            before = tracked.read_text()
            with self.assertRaises(ValueError):
                setup.add_channels(tracked, "good, bad|handle")
            self.assertEqual(tracked.read_text(), before)

    def test_add_channels_blank_input_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _, tracked, _ = setup.create_brand(Path(d), "my-channel")
            before = tracked.read_text()
            self.assertEqual(setup.add_channels(tracked, "  "), [])
            self.assertEqual(tracked.read_text(), before)

    def test_fill_profile_fills_answers_and_keeps_blanks(self):
        with tempfile.TemporaryDirectory() as d:
            profile, _, _ = setup.create_brand(Path(d), "my-channel")
            setup.fill_profile(profile, {"channel": "", "content": "Budget cooking now, weeknight meals next."})
            text = profile.read_text()
            self.assertIn("## My channel\n[FILL]\n", text)
            self.assertIn("going forward.\nBudget cooking now, weeknight meals next.\n", text)

    def test_notion_page_id_accepts_links_and_ids(self):
        page = "3e33d58fa61281269869e845e7e89ab7"
        dashed = "3e33d58f-a612-8126-9869-e845e7e89ab7"
        self.assertEqual(setup.notion_page_id(f"https://www.notion.so/My-Page-{page}"), dashed)
        self.assertEqual(setup.notion_page_id(f"https://app.notion.com/p/Research-{page}?pvs=4"), dashed)
        self.assertEqual(setup.notion_page_id(dashed), dashed)
        self.assertEqual(setup.notion_page_id("not a page"), "")

    def test_interactive_walks_beginner_through_setup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / "cfg" / ".env"
            answers = iter(["my-channel", "@nateherk, nicksaraev", "@mychannel", "Budget cooking videos.", "no"])
            output = StringIO()
            with mock.patch.object(setup.env, "ENV_PATH", config), \
                 mock.patch.object(setup.env, "DEFAULT_CONTENT_HOME", root / "content"), \
                 mock.patch.dict(os.environ, {}, clear=False), \
                 mock.patch("builtins.input", lambda prompt="": next(answers)), \
                 mock.patch.object(setup.getpass, "getpass", return_value="secret-key-xyz"), \
                 redirect_stdout(output):
                os.environ.pop("CONTENT_HOME", None)
                code = setup.interactive()
            text = output.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Step 1 of 5", text)
            self.assertIn("Step 5 of 5", text)
            self.assertIn("/youtube-outliers my-channel", text)
            self.assertNotIn("secret-key-xyz", text)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
            brand = root / "content" / "my-channel" / "brand"
            handles = [r["handle"] for r in tracked_lib.load_tracked(brand / "tracked-accounts" / "youtube.md")]
            self.assertEqual(handles, ["@nateherk", "@nicksaraev"])
            self.assertIn("## My channel\n@mychannel\n", (brand / "profile.md").read_text())

    def test_validate_brand_rejects_paths(self):
        for value in ("../secret", "My Channel", "/tmp/x", "a_b"):
            with self.assertRaises(ValueError):
                setup.validate_brand(value)


if __name__ == "__main__":
    unittest.main()