import importlib.util
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()