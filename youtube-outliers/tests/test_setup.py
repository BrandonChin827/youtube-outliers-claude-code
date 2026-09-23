import importlib.util
import io
import json
import os
import stat
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


SETUP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "setup.py"
SPEC = importlib.util.spec_from_file_location("youtube_outliers_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)
from scripts.lib import tracked as tracked_lib  # noqa: E402


@contextmanager
def sandbox(key=None):
    """Point config and content at a temp folder. Yields (root, content_home)."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        env_vars = {"CONTENT_HOME": str(root / "content")}
        with mock.patch.object(setup.env, "ENV_PATH", root / "cfg" / ".env"), \
             mock.patch.object(setup.env, "FALLBACK_ENV_PATHS", ()), \
             mock.patch.dict(os.environ, env_vars, clear=False):
            os.environ.pop("SCRAPECREATORS_API_KEY", None)
            if key:
                os.environ["SCRAPECREATORS_API_KEY"] = key
            yield root, root / "content"


def run(argv):
    out = StringIO()
    with redirect_stdout(out):
        code = setup.main(argv)
    return code, out.getvalue()


class KeyTests(unittest.TestCase):
    def test_popup_key_saved_privately_and_never_printed(self):
        with sandbox() as (root, _), \
             mock.patch.object(setup, "popup_key", return_value="secret-key-xyz"), \
             mock.patch.object(setup, "verify_key", return_value="valid"):
            code, out = run(["key"])
            config = root / "cfg" / ".env"
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("saved:"))
            self.assertNotIn("secret-key-xyz", out)
            self.assertIn("secret-key-xyz", config.read_text())
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(config.parent.stat().st_mode), 0o700)

    def test_rejected_key_is_not_saved(self):
        with sandbox() as (root, _), \
             mock.patch.object(setup, "popup_key", return_value="typo"), \
             mock.patch.object(setup, "verify_key", return_value="invalid"):
            code, out = run(["key"])
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("rejected:"))
            self.assertFalse((root / "cfg" / ".env").exists())

    def test_cancelled_popup(self):
        with sandbox(), mock.patch.object(setup, "popup_key", return_value=""):
            code, out = run(["key"])
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("cancelled:"))

    def test_unreachable_check_still_saves(self):
        with sandbox() as (root, _), \
             mock.patch.object(setup, "popup_key", return_value="k"), \
             mock.patch.object(setup, "verify_key", return_value="unknown"):
            code, out = run(["key"])
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("saved-unverified:"))

    def test_no_popup_and_no_terminal_asks_for_terminal(self):
        with sandbox(), mock.patch.object(setup, "popup_key", return_value=None), \
             mock.patch.object(setup.sys.stdin, "isatty", return_value=False):
            code, out = run(["key"])
            self.assertEqual(code, 2)
            self.assertTrue(out.startswith("needs-terminal:"))
            self.assertIn("key --terminal", out)

    def test_terminal_mode_uses_hidden_prompt(self):
        with sandbox(), mock.patch.object(setup, "popup_key", side_effect=AssertionError("no popup")), \
             mock.patch.object(setup.sys.stdin, "isatty", return_value=True), \
             mock.patch.object(setup.getpass, "getpass", return_value="k"), \
             mock.patch.object(setup, "verify_key", return_value="valid"):
            code, out = run(["key", "--terminal"])
            self.assertEqual(code, 0)

    def test_popup_cancel_and_failure(self):
        cancelled = mock.Mock(returncode=1, stderr="execution error: User canceled. (-128)", stdout="")
        broken = mock.Mock(returncode=1, stderr="some other error", stdout="")
        ok = mock.Mock(returncode=0, stderr="", stdout="abc123\n")
        with mock.patch.object(setup.sys, "platform", "darwin"), \
             mock.patch.object(setup.shutil, "which", return_value="/usr/bin/osascript"):
            for result, expected in ((cancelled, ""), (broken, None), (ok, "abc123")):
                with mock.patch.object(setup.subprocess, "run", return_value=result):
                    self.assertEqual(setup.popup_key(), expected)
        with mock.patch.object(setup.sys, "platform", "linux"):
            self.assertIsNone(setup.popup_key())


class BrandTests(unittest.TestCase):
    def test_brand_named_after_channel_with_profile_and_competitors(self):
        with sandbox() as (_, content):
            code, out = run(["brand", "--channel", "https://www.youtube.com/@BrandonBuildsOnline/videos",
                             "--about", "AI for beginners.",
                             "--add", "@nateherk, https://youtube.com/@nicksaraev, @BrandonBuildsOnline"])
            info = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(info["name"], "brandonbuildsonline")
            self.assertEqual(info["handles"], ["@nateherk", "@nicksaraev"])
            self.assertTrue(info["skipped_own_channel"])
            profile = (content / "brandonbuildsonline" / "brand" / "profile.md").read_text()
            self.assertIn("## My channel\nhttps://www.youtube.com/@BrandonBuildsOnline\n", profile)
            self.assertIn("## My content\nAI for beginners.\n", profile)
            self.assertIn("## Title style", profile)

    def test_no_channel_uses_default_name(self):
        with sandbox():
            code, out = run(["brand", "--channel", "none", "--about", "Cooking."])
            info = json.loads(out)
            self.assertEqual(info["name"], "my-channel")
            self.assertEqual(info["channel"], "No channel yet")

    def test_update_adds_removes_and_still_skips_own_channel(self):
        with sandbox():
            run(["brand", "--channel", "@me", "--add", "@a, @b"])
            code, out = run(["brand", "--name", "me", "--add", "@c, @me, @A", "--remove", "b"])
            info = json.loads(out)
            self.assertEqual(info["handles"], ["@a", "@c"])
            self.assertEqual(info["added"], ["@c"])
            self.assertEqual(info["removed"], 1)
            self.assertTrue(info["skipped_own_channel"])

    def test_update_about_replaces_section(self):
        with sandbox():
            run(["brand", "--channel", "@me", "--about", "Old."])
            code, out = run(["brand", "--name", "me", "--about", "New."])
            profile = Path(json.loads(out)["profile_path"]).read_text()
            self.assertIn("## My content\nNew.\n", profile)
            self.assertNotIn("Old.", profile)

    def test_notion_page_from_link(self):
        page = "3e33d58fa61281269869e845e7e89ab7"
        with sandbox():
            code, out = run(["brand", "--channel", "@me", "--notion-page", f"https://www.notion.so/Research-{page}?pvs=4"])
            self.assertEqual(json.loads(out)["notion_page"], "3e33d58f-a612-8126-9869-e845e7e89ab7")

    def test_bad_inputs_fail_cleanly(self):
        with sandbox(), mock.patch("sys.stderr", new_callable=StringIO) as err:
            self.assertEqual(run(["brand", "--channel", "@me", "--add", "bad|handle"])[0], 1)
            self.assertEqual(run(["brand", "--channel", "@me", "--notion-page", "not a page"])[0], 1)
            self.assertEqual(run(["brand", "--about", "x"])[0], 1)
            self.assertIn("error:", err.getvalue())

    def test_existing_profile_sections_are_kept(self):
        with sandbox() as (_, content):
            profile = content / "old" / "brand" / "profile.md"
            profile.parent.mkdir(parents=True)
            profile.write_text("# Brand\n\n## Audience\nBuilders.\n\n## Pillars\n- AI\n")
            run(["brand", "--name", "old", "--channel", "@old"])
            text = profile.read_text()
            self.assertIn("## Audience\nBuilders.", text)
            self.assertIn("## My channel\nhttps://www.youtube.com/@old", text)

    def test_slugify(self):
        self.assertEqual(setup.slugify("  My Channel!! "), "my-channel")
        self.assertEqual(setup.slugify("../etc"), "etc")
        self.assertEqual(setup.slugify("!!!"), "")

    def test_validate_brand_rejects_paths(self):
        for value in ("../secret", "My Channel", "/tmp/x", "a_b"):
            with self.assertRaises(ValueError):
                setup.validate_brand(value)


class VerifyHandlesTests(unittest.TestCase):
    def test_reports_existing_missing_and_unknown(self):
        def opener(req, timeout):
            if "@real" in req.full_url:
                return io.BytesIO(b'<meta property="og:title" content="Real &amp; Co">')
            if "@gone" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
            raise urllib.error.URLError("offline")
        results = setup.verify_handles("@real, youtube.com/@gone, flaky", opener=opener)
        self.assertEqual(results, [
            {"handle": "@real", "exists": True, "name": "Real & Co"},
            {"handle": "@gone", "exists": False, "name": ""},
            {"handle": "@flaky", "exists": None, "name": ""},
        ])


class StatusTests(unittest.TestCase):
    def test_next_step_walks_through_setup(self):
        with sandbox():
            self.assertEqual(setup.status()["next_step"], "key")
        with sandbox(key="k"):
            self.assertEqual(setup.status()["next_step"], "about")
            run(["brand", "--channel", "@me", "--about", "x"])
            self.assertEqual(setup.status()["next_step"], "competitors")
            run(["brand", "--name", "me", "--add", "@a"])
            info = setup.status()
            self.assertEqual(info["next_step"], "ready")
            self.assertEqual([b["name"] for b in info["brands"]], ["me"])

    def test_status_never_prints_key_or_calls_network(self):
        with sandbox(key="never-print-me"), \
             mock.patch.object(setup, "verify_key", side_effect=AssertionError("network")):
            code, out = run(["status"])
            self.assertEqual(code, 0)
            self.assertNotIn("never-print-me", out)
            self.assertEqual(json.loads(out)["key"], "configured")

    def test_legacy_check(self):
        with sandbox(key="never-print-me"):
            run(["brand", "--channel", "@me", "--add", "@a"])
            code, out = run(["--check", "--brand", "me"])
            self.assertEqual(code, 0)
            self.assertIn("Setup check passed.", out)
            self.assertNotIn("never-print-me", out)

    def test_write_values_keeps_existing_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            setup.write_values(path, {"SCRAPECREATORS_API_KEY": "a", "CONTENT_HOME": "/c"})
            setup.write_values(path, {"SCRAPECREATORS_API_KEY": "b"})
            self.assertEqual(setup.read_values(path), {"SCRAPECREATORS_API_KEY": "b", "CONTENT_HOME": "/c"})


if __name__ == "__main__":
    unittest.main()
