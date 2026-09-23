import json
import unittest
from pathlib import Path
from unittest import mock

from scripts.lib import fetch

FIXTURE = Path(__file__).parent / "fixtures" / "channel_videos_sample.json"


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())

    def test_normalize_keeps_full_iso_date_and_fields(self):
        vids = fetch.normalize_channel_response("@nateherk", self.data)
        v = next(x for x in vids if x["id"] == "vid_recent")
        self.assertEqual(v["published_at"], "2026-09-18T05:00:25-07:00")
        self.assertEqual(v["views"], 148000)
        self.assertEqual(v["length_seconds"], 900)
        self.assertEqual(v["channel"], "@nateherk")
        self.assertTrue(v["thumbnail"].startswith("https://"))
        self.assertFalse(v["is_live"])

    def test_normalize_flags_streams_from_badges(self):
        vids = fetch.normalize_channel_response("@nateherk", self.data)
        v = next(x for x in vids if x["id"] == "vid_stream")
        self.assertTrue(v["is_live"])

    def test_normalize_skips_videos_without_date_or_views(self):
        data = {"videos": [{"id": "x", "title": "no date", "url": "u", "viewCountInt": 5}]}
        self.assertEqual(fetch.normalize_channel_response("@h", data), [])

    def test_fetch_channel_videos_calls_endpoint(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value=self.data) as m:
            vids = fetch.fetch_channel_videos("@nateherk", "key")
        m.assert_called_once_with(
            "/v1/youtube/channel-videos", {"handle": "@nateherk", "sort": "latest"}, "key"
        )
        self.assertEqual(len(vids), 4)

    def test_fetch_channel_videos_returns_empty_on_none(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value=None):
            self.assertEqual(fetch.fetch_channel_videos("@x", "key"), [])

    def test_fetch_transcript_prefers_text_field(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value={"transcript_only_text": "hello world"}):
            self.assertEqual(fetch.fetch_transcript("https://youtube.com/watch?v=a", "key"), "hello world")

    def test_fetch_transcript_joins_segments(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value={"transcript": [{"text": "a"}, {"text": "b"}]}):
            self.assertEqual(fetch.fetch_transcript("u", "key"), "a b")

    def test_normalize_tolerates_non_list_badges(self):
        data = {
            "videos": [
                {
                    "id": "vid_int_badge",
                    "title": "Video with int badge",
                    "url": "https://youtube.com/watch?v=vid_int_badge",
                    "publishDate": "2026-09-18T05:00:25-07:00",
                    "viewCountInt": 1000,
                    "lengthSeconds": 100,
                    "thumbnail": "https://i.ytimg.com/vi/vid_int_badge/hqdefault.jpg",
                    "badges": 5,
                }
            ]
        }
        vids = fetch.normalize_channel_response("@test", data)
        self.assertEqual(len(vids), 1)
        v = vids[0]
        self.assertEqual(v["id"], "vid_int_badge")
        self.assertFalse(v["is_live"])

    def test_normalize_string_badge_flags_live(self):
        data = {
            "videos": [
                {
                    "id": "vid_string_badge",
                    "title": "Video with string badge",
                    "url": "https://youtube.com/watch?v=vid_string_badge",
                    "publishDate": "2026-09-18T05:00:25-07:00",
                    "viewCountInt": 1000,
                    "lengthSeconds": 100,
                    "thumbnail": "https://i.ytimg.com/vi/vid_string_badge/hqdefault.jpg",
                    "badges": "Streamed",
                }
            ]
        }
        vids = fetch.normalize_channel_response("@test", data)
        self.assertEqual(len(vids), 1)
        v = vids[0]
        self.assertEqual(v["id"], "vid_string_badge")
        self.assertTrue(v["is_live"])

    def test_normalize_drops_unparseable_date(self):
        data = {"videos": [{"id": "x", "title": "bad date", "url": "u",
                             "publishDate": "2 days ago", "viewCountInt": 5000}]}
        self.assertEqual(fetch.normalize_channel_response("@h", data), [])

    def test_normalize_accepts_z_suffix_and_naive(self):
        data = {"videos": [
            {"id": "z", "title": "z suffix", "url": "u",
             "publishDate": "2026-09-18T05:00:25Z", "viewCountInt": 1000},
            {"id": "naive", "title": "naive", "url": "u",
             "publishDate": "2026-09-18T05:00:25", "viewCountInt": 1000},
        ]}
        vids = fetch.normalize_channel_response("@h", data)
        self.assertEqual(len(vids), 2)
        by_id = {v["id"]: v for v in vids}
        self.assertTrue(by_id["z"]["published_at"].endswith("+00:00"))
        self.assertTrue(by_id["naive"]["published_at"].endswith("+00:00"))

    def test_normalize_keeps_zero_views_and_drops_non_numeric(self):
        data = {"videos": [
            {"id": "zero", "title": "zero views", "url": "u",
             "publishDate": "2026-09-18T05:00:25-07:00", "viewCountInt": 0},
            {"id": "bad", "title": "bad views", "url": "u",
             "publishDate": "2026-09-18T05:00:25-07:00", "viewCountInt": "1,234"},
        ]}
        vids = fetch.normalize_channel_response("@h", data)
        self.assertEqual(len(vids), 1)
        self.assertEqual(vids[0]["id"], "zero")
        self.assertEqual(vids[0]["views"], 0)

    def test_normalize_missing_length_and_url(self):
        data = {"videos": [{"id": "novid", "title": "no length or url",
                             "publishDate": "2026-09-18T05:00:25-07:00", "viewCountInt": 1000}]}
        vids = fetch.normalize_channel_response("@h", data)
        self.assertEqual(len(vids), 1)
        v = vids[0]
        self.assertEqual(v["length_seconds"], 0)
        self.assertEqual(v["url"], "https://www.youtube.com/watch?v=novid")


    def test_fetch_transcript_requests_english(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value={"transcript_only_text": "hello there"}) as m:
            self.assertEqual(fetch.fetch_transcript("u", "key"), "hello there")
        m.assert_called_once_with("/v1/youtube/video/transcript", {"url": "u", "language": "en"}, "key")

    def test_fetch_transcript_falls_back_when_language_missing(self):
        replies = [{"transcript_only_text": None, "transcript": None}, {"transcript_only_text": "hola"}]
        with mock.patch("scripts.lib.fetch.sc_get", side_effect=replies) as m:
            self.assertEqual(fetch.fetch_transcript("u", "key"), "hola")
        self.assertEqual(m.call_args_list[1], mock.call("/v1/youtube/video/transcript", {"url": "u"}, "key"))

    def test_fetch_transcript_any_language_makes_one_call(self):
        with mock.patch("scripts.lib.fetch.sc_get", return_value={"transcript_only_text": "x"}) as m:
            fetch.fetch_transcript("u", "key", language=None)
        m.assert_called_once_with("/v1/youtube/video/transcript", {"url": "u"}, "key")


if __name__ == "__main__":
    unittest.main()
