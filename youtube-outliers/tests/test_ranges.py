import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import outliers
from scripts.lib import scoring
from tests.test_cli import NOW, TRACKED, typical

PROFILE = "# Brand profile\n\n## My channel\n[FILL]\n\n## Report range\n{}\n\n## Title style\n- Clear\n"


class RangeResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CONTENT_HOME"] = self.tmp.name
        self.brand = Path(self.tmp.name) / "b" / "brand"
        (self.brand / "tracked-accounts").mkdir(parents=True)
        (self.brand / "tracked-accounts" / "youtube.md").write_text(TRACKED)

    def tearDown(self):
        os.environ.pop("CONTENT_HOME", None)
        self.tmp.cleanup()

    def write_profile(self, value):
        (self.brand / "profile.md").write_text(PROFILE.format(value))

    def test_default_is_week_without_profile(self):
        self.assertEqual(outliers.resolve_range("b"), ("week", "This week", 7))

    def test_profile_range_is_used(self):
        self.write_profile("6months")
        self.assertEqual(outliers.resolve_range("b"), ("6months", "6 months", 180))

    def test_unknown_profile_value_falls_back_to_default(self):
        self.write_profile("forever")
        self.assertEqual(outliers.resolve_range("b")[0], "week")

    def test_range_flag_beats_profile_and_days_beats_both(self):
        self.write_profile("6months")
        self.assertEqual(outliers.resolve_range("b", "month"), ("month", "This month", 30))
        self.assertEqual(outliers.resolve_range("b", "month", 45), ("45days", "Last 45 days", 45))

    def test_days_outside_limits_raise(self):
        for days in (6, 181):
            with self.assertRaises(ValueError):
                outliers.resolve_range("b", None, days)

    def test_main_uses_profile_range(self):
        self.write_profile("3months")
        seen = {}

        def fake_run(brand, now, api_key, max_results, days, range_name, fetch_fn):
            seen.update(days=days, range_name=range_name, max_results=max_results)
            return {"brand": brand, "candidates": [], "skipped": [], "days": days,
                    "paths": {"md": "m", "json": "j"}}
        with mock.patch("scripts.outliers.load_api_key", return_value="k"), \
                mock.patch("scripts.outliers.run", side_effect=fake_run), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(outliers.main(["run", "b"]), 0)
        self.assertEqual(seen, {"days": 90, "range_name": "3months", "max_results": 60})
        self.assertIn("Range: 3 months (90 days)", out.getvalue())


class ByRangeTests(unittest.TestCase):
    def cands(self):
        return [{"id": i, "age_days": a, "score": s, "views": 1000} for i, a, s in
                [("w", 3, 4.0), ("m", 20, 9.0), ("q", 80, 3.0), ("h", 170, 20.0)]]

    def test_ranges_nest_and_stop_at_days(self):
        out = scoring.by_range(self.cands(), 180)
        self.assertEqual({k: v["count"] for k, v in out.items()}, {"week": 1, "month": 2, "3months": 3, "6months": 4})
        self.assertEqual(out["6months"]["top"], ["h", "m", "w"])
        self.assertEqual(list(scoring.by_range(self.cands(), 30)), ["week", "month"])
        self.assertEqual(out["month"]["label"], "This month")

    def test_run_payload_has_audit_and_coverage(self):
        tmp = tempfile.TemporaryDirectory()
        os.environ["CONTENT_HOME"] = tmp.name
        try:
            t = Path(tmp.name) / "b" / "brand" / "tracked-accounts"
            t.mkdir(parents=True)
            t.joinpath("youtube.md").write_text("| Handle | Category | Notes |\n|---|---|---|\n| @slow | AI | |\n")

            def slow(handle, api_key):  # one upload a month for 30 months
                return [typical(handle, f"s{i}", 15 + i * 30) for i in range(29)] + [typical(handle, "hit", 100, 6)]
            with contextlib.redirect_stderr(io.StringIO()):
                out = outliers.run("b", NOW, "k", days=180, range_name="6months", fetch_fn=slow)
            self.assertEqual([c["id"] for c in out["candidates"]], ["hit"])
            self.assertEqual(out["candidates"][0]["range"], "6months")
            self.assertEqual(out["by_range"]["6months"]["count"], 1)
            self.assertEqual(out["by_range"]["week"]["count"], 0)
            self.assertEqual(out["skipped"], [])  # 30 months of uploads cover 6 months fine
            self.assertGreater(out["coverage"]["@slow"], 180)
        finally:
            os.environ.pop("CONTENT_HOME", None)
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
