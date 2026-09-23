import importlib.util
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


INSTALL_PATH = Path(__file__).resolve().parent / "install.py"
SPEC = importlib.util.spec_from_file_location("youtube_outliers_install", INSTALL_PATH)
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)


class InstallTests(unittest.TestCase):
    def test_install_copies_skill_and_backs_up_previous_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source"
            target = root / "skills" / "youtube-outliers"
            source.mkdir()
            (source / "SKILL.md").write_text("new")
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("old")
            backup = install.copy_skill(source, target)
            self.assertEqual((target / "SKILL.md").read_text(), "new")
            self.assertEqual((backup / "SKILL.md").read_text(), "old")
            # Backups live outside the skills folder so Claude doesn't load them as a second skill.
            self.assertEqual(backup.parent, root / "skill-backups")
            self.assertEqual([p.name for p in (root / "skills").iterdir()], ["youtube-outliers"])

    def test_main_runs_setup_wizard_after_install(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "skills" / "youtube-outliers"
            with mock.patch.object(install, "run_setup", return_value=0) as run_setup, redirect_stdout(StringIO()):
                code = install.main(["--target", str(target)])
            self.assertEqual(code, 0)
            self.assertTrue((target / "SKILL.md").exists())
            run_setup.assert_called_once_with(target)

    def test_main_no_setup_skips_wizard(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "skills" / "youtube-outliers"
            with mock.patch.object(install, "run_setup") as run_setup, redirect_stdout(StringIO()):
                code = install.main(["--target", str(target), "--no-setup"])
            self.assertEqual(code, 0)
            run_setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()