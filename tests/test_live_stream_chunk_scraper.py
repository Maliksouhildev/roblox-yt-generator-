#!/usr/bin/env python3
"""Comprehensive unit tests for scripts/live_stream_chunk_scraper.py."""

from datetime import datetime, timezone
import json
import math
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import live_stream_chunk_scraper as scraper


class TestScraperConstantsAndCommands(unittest.TestCase):
    def test_constants_and_two_tier_pools(self):
        self.assertEqual(scraper.LOCK_EXPIRE_SEC, 1500)
        self.assertEqual(scraper.MIN_LIVE_BUFFER_SEC, 0)
        self.assertEqual(scraper.CHUNK_SEC, 3000)
        self.assertEqual(scraper.PROBE_WORKERS, 8)
        self.assertEqual(scraper.PROBE_TIMEOUT_SEC, 6)
        self.assertEqual(scraper.DVR_FETCH_TIMEOUT_SEC, 180)
        self.assertEqual(scraper.LIVE_EDGE_RECORD_SEC, 180)

        expected_yt = {
            "@DarkViperAU", "@LazarBeam", "@Loserfruit", "@Muselk",
            "@TypicalGamer", "@IShowSpeed", "@CaseOh_", "@penguinz0",
            "@Valkyrae", "@TimTheTatman", "@DrDisRespect", "@Sykkuno",
        }
        self.assertEqual(set(scraper.VIP_YT_HANDLES), expected_yt)
        self.assertEqual(len(scraper.LIVE_YT_POOL), 12)
        self.assertEqual(len(scraper.VOD_FALLBACK_POOL), 12)

        expected_tw = {"kaicenat", "xqc", "jynxzi", "caseoh_", "lirik", "summit1g", "tarik"}
        self.assertEqual(set(scraper.VIP_TWITCH_HANDLES), expected_tw)
        self.assertEqual(scraper.TIER2_SEARCH_QUERY, "ytsearch15:GTA 6 live gameplay")

    def test_fmt_hhmmss_and_sanitize(self):
        self.assertEqual(scraper.fmt_hhmmss(0), "00:00:00")
        self.assertEqual(scraper.fmt_hhmmss(3600), "01:00:00")
        self.assertEqual(scraper.fmt_hhmmss(7265), "02:01:05")
        self.assertEqual(scraper.fmt_hhmmss(-10), "00:00:00")
        self.assertEqual(scraper.sanitize_slug("@DarkViperAU"), "DarkViperAU")
        self.assertEqual(scraper.sanitize_slug("   ", "fallback"), "fallback")

    def test_build_commands_yt_live_twitch_and_vod(self):
        now = 1_795_000_000.0
        # Live >= 30 mins (2400s) -> --live-from-start -N 8 with 180s SIGINT cap & NO live_chat
        yt_meta_aged = {
            "url": "https://www.youtube.com/watch?v=abc12345678",
            "id": "abc12345678",
            "is_live": True,
            "extractor": "youtube",
            "release_timestamp": now - 2400,
        }
        with mock.patch("time.time", return_value=now):
            cmds = scraper.build_download_commands(
                yt_meta_aged, 3600, 7200, "/files/inputs/TypicalGamer_abc12345678_chunk2"
            )
        self.assertEqual(len(cmds), 2)
        dvr_cmd, ff_cmd = cmds
        self.assertEqual(dvr_cmd[:6], ["timeout", "-s", "INT", "-k", "30", "180"])
        self.assertIn("--live-from-start", dvr_cmd)
        self.assertIn("-N", dvr_cmd)
        self.assertEqual(dvr_cmd[dvr_cmd.index("-N") + 1], "8")
        self.assertNotIn("--write-subs", dvr_cmd)
        self.assertNotIn("live_chat", dvr_cmd)
        self.assertIn("--write-info-json", dvr_cmd)
        self.assertIn("--merge-output-format", dvr_cmd)
        self.assertIn("mp4", dvr_cmd)
        self.assertTrue(any("raw_live_%(id)s.%(ext)s" in a for a in dvr_cmd))

        # Fresh / unknown elapsed_live_sec -> 180s fast live-edge capture WITHOUT --live-from-start
        yt_meta_fresh = {
            "url": "https://www.youtube.com/watch?v=fresh123",
            "id": "fresh123",
            "is_live": True,
            "extractor": "youtube",
            "release_timestamp": now - 600,
        }
        with mock.patch("time.time", return_value=now):
            edge_cmd = scraper.build_yt_live_dvr_command(yt_meta_fresh, "/files/temp/raw_live_%(id)s.%(ext)s")
        self.assertEqual(edge_cmd[:6], ["timeout", "-s", "INT", "-k", "30", "180"])
        self.assertNotIn("--live-from-start", edge_cmd)
        self.assertIn("-N", edge_cmd)
        self.assertNotIn("--write-subs", edge_cmd)

        self.assertEqual(ff_cmd[0], "ffmpeg")
        self.assertIn("-ss", ff_cmd)
        self.assertEqual(ff_cmd[ff_cmd.index("-ss") + 1], "3600")
        self.assertEqual(ff_cmd[ff_cmd.index("-t") + 1], "3600")
        self.assertIn("-avoid_negative_ts", ff_cmd)
        self.assertIn("make_zero", ff_cmd)

        tw_meta = {
            "url": "https://www.twitch.tv/kaicenat",
            "id": "tw999",
            "is_live": True,
            "extractor": "twitchstream",
        }
        tw_cmds = scraper.build_download_commands(
            tw_meta, 0, 3600, "/files/inputs/kaicenat_tw999_chunk1"
        )
        self.assertEqual(len(tw_cmds), 1)
        self.assertEqual(tw_cmds[0][:6], ["timeout", "-s", "INT", "-k", "30", "180"])
        self.assertIn("-N", tw_cmds[0])
        self.assertNotIn("--write-subs", tw_cmds[0])
        self.assertIn("best[height<=1080]/best", tw_cmds[0])

        vod_meta = {
            "url": "https://www.youtube.com/watch?v=vod_123",
            "id": "vod_123",
            "is_live": False,
            "extractor": "youtube",
        }
        vod_cmds = scraper.build_download_commands(
            vod_meta, 0, 3600, "/files/inputs/CaseOh__vod_123_chunk1"
        )
        self.assertEqual(len(vod_cmds), 2)
        vod_dl = " ".join(vod_cmds[0])
        self.assertIn("duration <= 36000", vod_dl)
        self.assertIn("--write-subs", vod_cmds[0])
        self.assertIn("live_chat", vod_cmds[0])
        self.assertIn("-N", vod_cmds[0])
        self.assertIn("--socket-timeout", vod_cmds[0])
        self.assertIn("/files/temp/vod_vod_123.%(ext)s", vod_dl.replace("\\", "/"))


class TestLock25MinExpiry(unittest.TestCase):
    def test_lock_acquire_25m_auto_expiry_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = os.path.join(tmp, "live_chunk_scraper.lock")
            self.assertTrue(scraper.acquire_lock(lock_file))
            self.assertTrue(os.path.exists(lock_file))

            # Active alive PID < 1500s rejects takeover
            self.assertFalse(scraper.acquire_lock(lock_file))

            # 1400s old (< 1500s) with alive PID still rejects takeover
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump({"pid": os.getpid(), "started_epoch": time.time() - 1400}, f)
            self.assertFalse(scraper.acquire_lock(lock_file))

            # 1501s old (>= 25 mins = 1500s) with alive PID auto-expires and allows takeover
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump({"pid": os.getpid(), "started_epoch": time.time() - 1501}, f)
            self.assertTrue(scraper.acquire_lock(lock_file))
            new_info = scraper.load_json(lock_file, {})
            self.assertLess(time.time() - new_info["started_epoch"], 5.0)

            scraper.release_lock(lock_file)
            self.assertFalse(os.path.exists(lock_file))

            # Dead PID lock can also be taken over immediately
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump({"pid": 999999, "started_epoch": time.time() - 10}, f)
            self.assertTrue(scraper.acquire_lock(lock_file))
            scraper.release_lock(lock_file)


class TestDiscoveryFilteringRankingAndBuffer(unittest.TestCase):
    def test_gta6_and_vip_time_window_filtering(self):
        before_noon_cet = datetime(2026, 11, 18, 10, 30, 0, tzinfo=timezone.utc).timestamp()
        after_noon_cet = datetime(2026, 11, 18, 11, 15, 0, tzinfo=timezone.utc).timestamp()

        vip_generic_live = {
            "id": "v1",
            "title": "HUGE STREAM TODAY",
            "uploader_id": "@IShowSpeed",
            "is_live": True,
        }
        vip_twitch_gta6_desc = {
            "id": "tw1",
            "title": "xQc (live)",
            "description": "LIVE GTA 6 LAUNCH DAY IN LEONIDA",
            "uploader_id": "xqc",
            "is_live": True,
        }
        non_vip_roblox = {
            "id": "r1",
            "title": "Roblox Doors Update Live!",
            "uploader_id": "@RandomRobloxer",
            "is_live": True,
        }
        vip_non_gta6_vod = {
            "id": "old1",
            "title": "The Last Drive Of GTA Online",
            "uploader_id": "@DarkViperAU",
            "is_live": False,
            "duration": 6731,
        }
        non_vip_vice_city_vod = {
            "id": "vc1",
            "title": "Exploring Vice City Free Roam!",
            "uploader_id": "@MrDalekJD",
            "is_live": False,
            "duration": 3800,
        }
        too_short_clip = {
            "id": "short1",
            "title": "GTA 6 8 Minute Gameplay Preview",
            "uploader_id": "@Random",
            "is_live": False,
            "duration": 480,
        }
        upcoming_stream = {
            "id": "up1",
            "title": "GTA 6 Premiere Waiting Room",
            "uploader_id": "@TypicalGamer",
            "is_live": False,
            "live_status": "is_upcoming",
        }

        self.assertFalse(scraper.is_eligible_candidate(vip_generic_live, before_noon_cet))
        self.assertTrue(scraper.is_eligible_candidate(vip_generic_live, after_noon_cet))
        self.assertTrue(scraper.is_eligible_candidate(vip_twitch_gta6_desc, before_noon_cet))
        self.assertFalse(scraper.is_eligible_candidate(non_vip_roblox, after_noon_cet))
        self.assertFalse(scraper.is_eligible_candidate(vip_non_gta6_vod, after_noon_cet))
        self.assertTrue(scraper.is_eligible_candidate(non_vip_vice_city_vod, before_noon_cet))
        self.assertFalse(scraper.is_eligible_candidate(too_short_clip, after_noon_cet))
        self.assertFalse(scraper.is_eligible_candidate(upcoming_stream, after_noon_cet))

    def test_ranking_score_formula_and_chunk_penalty(self):
        vip = {
            "id": "vip1",
            "title": "GTA 6 Live",
            "uploader_id": "@DarkViperAU",
            "is_live": True,
            "concurrent_viewers": 9999,
        }
        non_vip = {
            "id": "nv1",
            "title": "Grand Theft Auto VI Gameplay",
            "uploader_id": "@Other",
            "is_live": True,
            "concurrent_view_count": 99999,
        }
        negative_or_none = {
            "id": "neg1",
            "title": "GTA 6",
            "uploader_id": "@Zero",
            "concurrent_viewers": None,
            "view_count": -50,
        }

        # VIP with 9999 viewers, 0 chunks: 50 + log10(10000)*15 = 110.0
        self.assertAlmostEqual(scraper.score_candidate(vip, {}), 110.0, places=3)
        # Non-VIP with 99999 viewers, 0 chunks: 0 + log10(100000)*15 = 75.0
        self.assertAlmostEqual(scraper.score_candidate(non_vip, {}), 75.0, places=3)
        # Guard negative / None viewer counts -> log10(1)*15 = 0.0
        self.assertEqual(scraper.score_candidate(negative_or_none, {}), 0.0)

        # After 2 chunks taken from vip1: 110 - 50 = 60.0 -> non-VIP (75.0) now wins!
        state = {"vip1": {"chunks_downloaded": 2, "chunk_idx": 3, "last_end_sec": 7200}}
        self.assertAlmostEqual(scraper.score_candidate(vip, state), 60.0, places=3)

        now = 1_795_000_000.0
        vip["release_timestamp"] = now - 10000
        non_vip["release_timestamp"] = now - 3000
        sel, wait_s = scraper.select_best_candidate([vip, non_vip], state, now, allow_wait=True)
        self.assertEqual(sel["id"], "nv1")
        self.assertEqual(wait_s, 0)

    def test_zero_wait_immediate_live_capture_and_ranking(self):
        now = 1_795_000_000.0
        fresh = {
            "id": "fresh1",
            "title": "GTA 6 Live",
            "uploader_id": "@TypicalGamer",
            "is_live": True,
            "release_timestamp": now - 900,  # 15m old -> ready immediately, zero wait!
            "concurrent_view_count": 20000,
        }
        ready = {
            "id": "ready1",
            "title": "GTA 6 Live",
            "uploader_id": "@DarkViperAU",
            "is_live": True,
            "release_timestamp": now - 3000,
            "concurrent_view_count": 15000,
        }
        vod = {
            "id": "vod1",
            "title": "GTA 6 Full Gameplay VOD",
            "uploader_id": "@LazarBeam",
            "is_live": False,
            "view_count": 50000,
            "duration": 7200,
        }

        # Fresh live stream (15m old) is captured immediately with 0 wait
        sel, wait_s = scraper.select_best_candidate([fresh], {}, now, allow_wait=True)
        self.assertEqual(sel["id"], "fresh1")
        self.assertEqual(wait_s, 0)

        # Higher-viewer live VIP beats lower-viewer live VIP immediately
        sel_r, wait_r = scraper.select_best_candidate([fresh, ready], {}, now, allow_wait=True)
        self.assertEqual(sel_r["id"], "fresh1")
        self.assertEqual(wait_r, 0)

        # Live stream ready immediately even when VOD exists
        sel_vod, wait_vod = scraper.select_best_candidate([fresh, vod], {}, now, allow_wait=True)
        self.assertEqual(sel_vod["id"], "fresh1")
        self.assertEqual(wait_vod, 0)

        # YouTube stream missing release_timestamp must NOT fail or wait
        yt_no_rel = {
            "id": "yt_norel",
            "url": "https://www.youtube.com/watch?v=yt_norel",
            "title": "GTA 6 Live",
            "uploader_id": "@TypicalGamer",
            "extractor": "youtube",
            "is_live": True,
            "release_timestamp": 0.0,
            "timestamp": now - 50000,
        }
        buf, wait_u = scraper.compute_live_buffer_status(yt_no_rel, {}, now)
        self.assertEqual(wait_u, 0)

    def test_two_tier_discovery_dedup_and_completed_skip(self):
        with mock.patch.object(scraper, "probe_stream") as m_probe, \
             mock.patch.object(scraper, "discover_flat_playlist") as m_flat:

            def fake_probe(url, timeout_sec=15):
                if "@DarkViperAU/live" in url:
                    return {
                        "id": "dv_live",
                        "url": "https://www.youtube.com/watch?v=dv_live",
                        "title": "GTA 6 Launch",
                        "uploader_id": "@DarkViperAU",
                        "is_live": True,
                        "concurrent_view_count": 30000,
                    }
                if "watch?v=dv_vod_new" in url:
                    return {
                        "id": "dv_vod_new",
                        "url": url,
                        "title": "GTA 6 Part 1",
                        "uploader_id": "@DarkViperAU",
                        "is_live": False,
                        "view_count": 100000,
                        "duration": 7200,
                    }
                if "watch?v=tier2_live" in url:
                    return {
                        "id": "tier2_live",
                        "url": url,
                        "title": "GTA 6 Live Gameplay",
                        "uploader_id": "@Tier2Streamer",
                        "is_live": True,
                        "concurrent_view_count": 5000,
                    }
                return None

            def fake_flat(q, playlist_items=None, timeout_sec=15):
                if "@DarkViperAU/streams" in q:
                    return [
                        {"id": "dv_live", "url": "https://www.youtube.com/watch?v=dv_live", "live_status": "is_live"},
                        {"id": "dv_vod_done", "url": "https://www.youtube.com/watch?v=dv_vod_done", "live_status": "was_live", "duration": 4000},
                        {"id": "dv_vod_new", "url": "https://www.youtube.com/watch?v=dv_vod_new", "live_status": "was_live", "duration": 7200},
                    ]
                if q == scraper.TIER2_SEARCH_QUERY:
                    return [
                        {"id": "dv_live", "url": "https://www.youtube.com/watch?v=dv_live", "live_status": "is_live"},
                        {"id": "tier2_live", "url": "https://www.youtube.com/watch?v=tier2_live", "live_status": "is_live"},
                    ]
                return []

            m_probe.side_effect = fake_probe
            m_flat.side_effect = fake_flat

            state = {"dv_vod_done": {"completed": True, "last_end_sec": 4000}}
            res = scraper.discover_and_probe_candidates(
                state=state,
                yt_live_urls=["https://www.youtube.com/@DarkViperAU/live"],
                yt_vod_urls=["https://www.youtube.com/@DarkViperAU/streams"],
                twitch_urls=[],
                search_query=scraper.TIER2_SEARCH_QUERY,
            )
            ids = {r["id"] for r in res}
            self.assertEqual(ids, {"dv_live", "dv_vod_new", "tier2_live"})
            # dv_live was only probed once via /live, never re-probed from /streams or ytsearch15
            probed_urls = [call.args[0] for call in m_probe.call_args_list]
            self.assertEqual(probed_urls.count("https://www.youtube.com/watch?v=dv_live"), 0)


class TestLiveChatSlicingAndChunkLifecycle(unittest.TestCase):
    def test_slice_live_chat_json_offsetting_and_en_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "vod_abc.en.live_chat.json")
            dst = os.path.join(tmp, "Creator_abc_chunk2.live_chat.json")
            lines = [
                # Before chunk [3600, 7200] -> dropped
                {
                    "replayChatItemAction": {
                        "videoOffsetTimeMsec": "-5000",
                        "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": "early"}]}}}}}],
                    }
                },
                {
                    "replayChatItemAction": {
                        "videoOffsetTimeMsec": "3599000",
                        "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": "chunk1"}]}}}}}],
                    }
                },
                # Inside chunk [3600, 7200] -> kept and shifted by -3600000 ms
                {
                    "replayChatItemAction": {
                        "videoOffsetTimeMsec": "3650000",
                        "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": "WASTED!"}]}}}}}],
                    }
                },
                # Top-level videoOffsetTimeMsec style
                {
                    "replayChatItemAction": {"actions": []},
                    "videoOffsetTimeMsec": "5400000",
                },
                # timestampUsec-only relative microsecond style (4000s = 4_000_000_000 usec)
                {
                    "replayChatItemAction": {
                        "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"timestampUsec": "4000000000", "message": {"runs": [{"text": "rel ts"}]}}}}}],
                    }
                },
                # After chunk -> dropped
                {
                    "replayChatItemAction": {
                        "videoOffsetTimeMsec": "7201000",
                        "actions": [],
                    }
                },
            ]
            with open(src, "w", encoding="utf-8") as f:
                for row in lines:
                    f.write(json.dumps(row) + "\n")

            written = scraper.slice_live_chat_json(src, dst, 3600, 7200)
            self.assertEqual(written, 3)

            with open(dst, "r", encoding="utf-8") as f:
                out_rows = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(out_rows[0]["replayChatItemAction"]["videoOffsetTimeMsec"], "50000")
            self.assertEqual(out_rows[1]["videoOffsetTimeMsec"], "1800000")
            self.assertEqual(out_rows[2]["replayChatItemAction"]["videoOffsetTimeMsec"], "400000")
            self.assertEqual(
                out_rows[2]["replayChatItemAction"]["actions"][0]["addChatItemAction"]["item"]["liveChatTextMessageRenderer"]["timestampUsec"],
                "400000000",
            )

    def test_vod_reuse_chunk1_keep_and_chunk2_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs_dir = os.path.join(tmp, "inputs")
            temp_dir = os.path.join(tmp, "temp")
            state_path = os.path.join(temp_dir, "live_chunks_state.json")
            os.makedirs(inputs_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)

            vod_meta = {
                "id": "vod7200",
                "url": "https://www.youtube.com/watch?v=vod7200",
                "title": "GTA 6 Full Launch Stream",
                "uploader_id": "@DarkViperAU",
                "extractor": "youtube",
                "is_live": False,
                "view_count": 250000,
                "duration": 7200.0,
            }

            yt_calls = []

            def fake_subprocess_run(cmd, *args, **kwargs):
                if "ffmpeg" in cmd[0]:
                    out_mp4 = cmd[-1]
                    with open(out_mp4, "wb") as f:
                        f.write(b"MP4_CHUNK" * 20)
                    return mock.Mock(returncode=0, stdout="", stderr="")
                yt_calls.append(cmd)
                vod_mp4 = os.path.join(temp_dir, "vod_vod7200.mp4")
                vod_info = os.path.join(temp_dir, "vod_vod7200.info.json")
                vod_chat = os.path.join(temp_dir, "vod_vod7200.en.live_chat.json")
                with open(vod_mp4, "wb") as f:
                    f.write(b"FULL_VOD" * 20)
                with open(vod_info, "w", encoding="utf-8") as f:
                    json.dump({"id": "vod7200", "uploader_id": "@DarkViperAU"}, f)
                with open(vod_chat, "w", encoding="utf-8") as f:
                    f.write(json.dumps({"replayChatItemAction": {"videoOffsetTimeMsec": "100000", "actions": []}}) + "\n")
                    f.write(json.dumps({"replayChatItemAction": {"videoOffsetTimeMsec": "4000000", "actions": []}}) + "\n")
                return mock.Mock(returncode=0, stdout="", stderr="")

            def fake_probe_dur(path):
                if path.endswith("vod_vod7200.mp4"):
                    return 7200.0
                return 3600.0

            with mock.patch.multiple(
                scraper,
                INPUTS_DIR=inputs_dir,
                TEMP_DIR=temp_dir,
                STATE_PATH=state_path,
                CHUNK_SEC=3600,
                MIN_VALID_BYTES=10,
                MIN_VALID_DUR_SEC=600.0,
            ), \
                 mock.patch.object(scraper, "discover_and_probe_candidates", return_value=[vod_meta]), \
                 mock.patch.object(scraper, "probe_duration", side_effect=fake_probe_dur), \
                 mock.patch("subprocess.run", side_effect=fake_subprocess_run):

                # Chunk 1: downloads VOD once, slices [0, 3600], KEEPS temp VOD
                res1 = scraper.run_scraper(dry_run=False, no_wait=True)
                self.assertEqual(res1["status"], "downloaded")
                self.assertEqual(res1["chunk_idx"], 1)
                self.assertEqual(res1["start_offset"], 0)
                self.assertEqual(res1["end_offset"], 3600)
                self.assertFalse(res1["vod_cleaned"])
                self.assertEqual(len(yt_calls), 1)
                self.assertTrue(os.path.exists(os.path.join(temp_dir, "vod_vod7200.mp4")))
                self.assertTrue(os.path.exists(os.path.join(inputs_dir, "DarkViperAU_vod7200_chunk1.mp4")))
                self.assertTrue(os.path.exists(os.path.join(inputs_dir, "DarkViperAU_vod7200_chunk1.info.json")))
                chat1_path = os.path.join(inputs_dir, "DarkViperAU_vod7200_chunk1.live_chat.json")
                self.assertTrue(os.path.exists(chat1_path))
                with open(chat1_path, "r", encoding="utf-8") as f:
                    c1_lines = [json.loads(x) for x in f if x.strip()]
                self.assertEqual(len(c1_lines), 1)
                self.assertEqual(c1_lines[0]["replayChatItemAction"]["videoOffsetTimeMsec"], "100000")

                # Chunk 2: REUSES temp VOD (yt_calls stays 1!), slices [3600, 7200], DELETES temp VOD
                res2 = scraper.run_scraper(dry_run=False, no_wait=True)
                self.assertEqual(res2["status"], "downloaded")
                self.assertEqual(res2["chunk_idx"], 2)
                self.assertEqual(res2["start_offset"], 3600)
                self.assertEqual(res2["end_offset"], 7200)
                self.assertTrue(res2["vod_cleaned"])
                self.assertEqual(len(yt_calls), 1)
                self.assertFalse(os.path.exists(os.path.join(temp_dir, "vod_vod7200.mp4")))
                chat2_path = os.path.join(inputs_dir, "DarkViperAU_vod7200_chunk2.live_chat.json")
                with open(chat2_path, "r", encoding="utf-8") as f:
                    c2_lines = [json.loads(x) for x in f if x.strip()]
                self.assertEqual(len(c2_lines), 1)
                self.assertEqual(c2_lines[0]["replayChatItemAction"]["videoOffsetTimeMsec"], "400000")

                st = scraper.load_json(state_path, {})
                self.assertTrue(st["vod7200"]["completed"])
                self.assertEqual(st["vod7200"]["chunks_downloaded"], 2)
                self.assertEqual(st["vod7200"]["chunk_idx"], 3)

    def test_no_sleep_immediate_live_capture_and_probe_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs_dir = os.path.join(tmp, "inputs")
            temp_dir = os.path.join(tmp, "temp")
            state_path = os.path.join(temp_dir, "live_chunks_state.json")
            lock_path = os.path.join(temp_dir, "live_chunk_scraper.lock")
            os.makedirs(inputs_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)

            base_now = 1_795_000_000.0
            stream_start = base_now - 1200.0  # 20m live -> grabs immediately without sleeping!
            live_meta = {
                "id": "live1",
                "url": "https://www.youtube.com/watch?v=live1",
                "title": "GTA 6 Live Stream",
                "uploader_id": "@TypicalGamer",
                "extractor": "youtube",
                "is_live": True,
                "release_timestamp": stream_start,
                "concurrent_view_count": 40000,
            }

            sleep_calls = []

            def fake_subproc(cmd, *args, **kwargs):
                if "ffmpeg" in cmd[0]:
                    with open(cmd[-1], "wb") as f:
                        f.write(b"CHUNK" * 20)
                else:
                    raw_mp4 = os.path.join(temp_dir, "raw_live_live1.mp4")
                    raw_info = os.path.join(temp_dir, "raw_live_live1.info.json")
                    with open(raw_mp4, "wb") as f:
                        f.write(b"RAW" * 20)
                    with open(raw_info, "w", encoding="utf-8") as f:
                        json.dump({"id": "live1"}, f)
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch.multiple(
                scraper,
                INPUTS_DIR=inputs_dir,
                TEMP_DIR=temp_dir,
                STATE_PATH=state_path,
                LOCK_PATH=lock_path,
                MIN_VALID_BYTES=10,
                MIN_VALID_DUR_SEC=600.0,
            ), \
                 mock.patch.object(scraper, "discover_and_probe_candidates", return_value=[live_meta]), \
                 mock.patch.object(scraper, "probe_duration", return_value=1200.0), \
                 mock.patch("time.time", return_value=base_now), \
                 mock.patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)), \
                 mock.patch("subprocess.run", side_effect=fake_subproc):

                # --probe-only must NOT sleep, NOT download, NOT touch lockfile
                probe_res = scraper.run_scraper(probe_only=True)
                self.assertEqual(probe_res["status"], "probe_only")
                self.assertEqual(probe_res["wait_needed_sec"], 0)
                self.assertEqual(probe_res["selected"]["id"], "live1")
                self.assertEqual(sleep_calls, [])
                self.assertFalse(os.path.exists(lock_path))

                # Full run grabs 20m live-edge immediately with zero sleep and cleans raw_live_*
                run_res = scraper.run_scraper(dry_run=False, no_wait=False, probe_only=False)
                self.assertEqual(sleep_calls, [])
                self.assertEqual(run_res["status"], "downloaded")
                self.assertEqual(run_res["chunk_idx"], 1)
                self.assertEqual(run_res["end_offset"], 1200)
                self.assertFalse(os.path.exists(os.path.join(temp_dir, "raw_live_live1.mp4")))
                self.assertTrue(os.path.exists(os.path.join(inputs_dir, "TypicalGamer_live1_chunk1.mp4")))
                self.assertTrue(os.path.exists(os.path.join(inputs_dir, "TypicalGamer_live1_chunk1.info.json")))

    def test_no_commentary_and_cooldown_fast_live_first_fallback(self):
        now = 1_795_000_000.0
        # 1) [No Commentary] streams must be filtered out; VIP high-score VOD beats low-viewer non-VIP live
        silent_live = {
            "id": "silent1",
            "title": "GTA 6 - 100% Walkthrough Part 5 [No Commentary]",
            "uploader_id": "@GTASeriesVideos",
            "is_live": True,
            "release_timestamp": now - 4000,
            "concurrent_view_count": 5000,
        }
        small_live = {
            "id": "small1",
            "title": "GTA 6 Live",
            "uploader_id": "@SmallStreamer",
            "is_live": True,
            "release_timestamp": now - 4000,
            "concurrent_view_count": 1200,
        }
        vip_vod = {
            "id": "vip_vod1",
            "title": "BEATING GTA 6 FINAL MISSION",
            "uploader_id": "@IShowSpeed",
            "is_live": False,
            "view_count": 10_000_000,
            "duration": 7200,
        }
        self.assertFalse(scraper.is_eligible_candidate(silent_live, now))
        sel, wait_s = scraper.select_best_candidate([silent_live, small_live, vip_vod], {}, now, allow_wait=True)
        self.assertEqual(sel["id"], "vip_vod1")
        self.assertEqual(wait_s, 0)

        # 2) fast_live_first must NOT early-return when the only live candidate is in failed_until cooldown
        cooldown_live = {
            "id": "cd_live",
            "title": "GTA 6 Live",
            "uploader_id": "@IShowSpeed",
            "is_live": True,
            "release_timestamp": now - 4000,
            "concurrent_view_count": 50000,
        }
        state = {"cd_live": {"failed_until": now + 1800}, "done_live": {"completed": True}}
        done_live = {**cooldown_live, "id": "done_live"}
        self.assertIsNone(scraper.select_best_candidate([done_live], state, now, allow_wait=False)[0])
        with mock.patch.object(scraper, "probe_stream", side_effect=lambda u, *a: cooldown_live if "IShowSpeed" in u else None), \
             mock.patch.object(scraper, "discover_flat_playlist", return_value=[]):
            cands = scraper.discover_and_probe_candidates(
                state=state,
                yt_live_urls=["https://www.youtube.com/@IShowSpeed/live"],
                yt_vod_urls=[],
                twitch_urls=[],
                search_query=None,
                fast_live_first=True,
            )
            # Only cd_live came back from live pass, and VOD fallback ran cleanly (not skipped blindly)
            self.assertEqual(len(cands), 1)
            self.assertIsNone(scraper.select_best_candidate(cands, state, now, allow_wait=False)[0])

        # 3) _count_fresh_input_chunks excludes stems listed in exhausted_vods.txt
        with tempfile.TemporaryDirectory() as tmp:
            inputs_dir = os.path.join(tmp, "inputs")
            temp_dir = os.path.join(tmp, "temp")
            os.makedirs(inputs_dir)
            os.makedirs(temp_dir)
            with open(os.path.join(inputs_dir, "Exhausted_abc_chunk1.mp4"), "wb") as f:
                f.write(b"x" * 100)
            with open(os.path.join(inputs_dir, "Fresh_def_chunk1.mp4"), "wb") as f:
                f.write(b"x" * 100)
            with open(os.path.join(temp_dir, "exhausted_vods.txt"), "w", encoding="utf-8") as f:
                f.write("Exhausted_abc_chunk1\n")
            with mock.patch.multiple(scraper, INPUTS_DIR=inputs_dir, TEMP_DIR=temp_dir, MIN_VALID_BYTES=10):
                self.assertEqual(scraper._count_fresh_input_chunks(), 1)


if __name__ == "__main__":
    unittest.main()
