#!/usr/bin/env python3
"""Unit and structural verification tests for GTA 6 Viral Shorts Engine (Peak + 3x3 Vision Edition)."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gta6_peak_storyboard_builder as peak_builder  # noqa: E402
import gta6_vision_director as vision_director  # noqa: E402
import edl_auditor  # noqa: E402


class TestGta6WorkflowStructure(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "workflows", "gta6_vision_shorts_workflow.json"), "r", encoding="utf-8") as f:
            self.wf = json.load(f)
        with open(os.path.join(ROOT, "workflows", "workflow.json"), "r", encoding="utf-8") as f:
            self.orig_wf = json.load(f)
        self.nodes_by_name = {n["name"]: n for n in self.wf["nodes"]}
        self.conns = self.wf["connections"]

    def test_identity_and_original_workflow_untouched(self):
        self.assertEqual(self.wf["id"], "Gta6VisionShortsV1")
        self.assertEqual(self.wf["name"], "GTA 6 Viral Shorts Engine (Peak + 3x3 Vision Edition)")
        self.assertEqual(self.orig_wf["id"], "D2hITsyjP5dVsqBZ")
        self.assertEqual(self.orig_wf["name"], "YouTube Short Automation (Bypassed Version)")
        orig_names = {n["name"] for n in self.orig_wf["nodes"]}
        self.assertIn("Scout Loop", orig_names)
        self.assertIn("Context Merge Agent", orig_names)

    def test_scout_and_context_merge_eliminated(self):
        forbidden = {
            "1. Prepare Scout Prompt",
            "Scout Loop",
            "Scout Accumulate",
            "2. Basic LLM Chain (Scout)",
            "3. Prepare Director Prompt",
            "4. Basic LLM Chain (Director)",
            "Context Merge Agent",
            "Context Merge Fallback",
            "Context Merge Mistral Fallback",
            "Wait Before Merge",
            "IF: Merge OK?",
        }
        present = set(self.nodes_by_name.keys())
        self.assertEqual(set(), forbidden.intersection(present))

    def test_required_gta6_nodes_and_wiring(self):
        required = {
            "GTA 6 Sandbox: Test Vision Script & EDL",
            "GTA 6 Load Cached Telemetry",
            "Save Global Summary JSON",
            "Run GTA6 Peak & Storyboard Builder",
            "Run GTA6 Vision Director",
            "5. Split Clips",
            "6. Extract Viral Segments",
            "DRY_RUN_SCRIPT_ONLY",
            "Create Subtitle Binary",
            "Write Sidecar JSON",
        }
        self.assertTrue(required.issubset(set(self.nodes_by_name.keys())))

        # Sandbox branch wiring
        self.assertEqual(
            self.conns["GTA 6 Sandbox: Test Vision Script & EDL"]["main"][0][0]["node"],
            "GTA 6 Load Cached Telemetry",
        )
        self.assertEqual(
            self.conns["GTA 6 Load Cached Telemetry"]["main"][0][0]["node"],
            "Run GTA6 Peak & Storyboard Builder",
        )
        self.assertEqual(
            self.conns["Run GTA6 Peak & Storyboard Builder"]["main"][0][0]["node"],
            "Run GTA6 Vision Director",
        )
        self.assertEqual(
            self.conns["Run GTA6 Vision Director"]["main"][0][0]["node"],
            "5. Split Clips",
        )
        # Get Meme List bypasses Context Merge straight into Create Subtitle Binary
        self.assertEqual(
            self.conns["Get Meme List"]["main"][0][0]["node"],
            "Create Subtitle Binary",
        )

        # No broken edges anywhere
        valid = set(self.nodes_by_name.keys())
        for src, ctype_map in self.conns.items():
            self.assertIn(src, valid)
            for branches in ctype_map.values():
                for br in branches:
                    for edge in br:
                        self.assertIn(edge["node"], valid)

        # No runtime Context Merge Agent string references in downstream render nodes
        csb_js = self.nodes_by_name["Create Subtitle Binary"]["parameters"]["jsCode"]
        sidecar_cmd = self.nodes_by_name["Write Sidecar JSON"]["parameters"]["command"]
        self.assertNotIn("getLoopNodeJson('Context Merge Agent'", csb_js)
        self.assertNotIn("getNode('Context Merge Agent')", sidecar_cmd)

    def test_part3_gta6_launch_playbook_upgrades(self):
        self.assertIn("Resolve Creator Handle", self.nodes_by_name)
        prs_js = self.nodes_by_name["Pick Random Streamer"]["parameters"]["jsCode"]
        for handle in ("TypicalGamer", "DarkViperAU", "LazarBeam", "Jynxzi", "CaseOh_"):
            self.assertIn(handle.lower(), prs_js.lower())

        fd_cmd = self.nodes_by_name["Fallback Download"]["parameters"]["command"]
        self.assertIn("duration <= 36000", fd_cmd)
        self.assertIn("--write-info-json", fd_cmd)
        self.assertIn("--sub-langs live_chat", fd_cmd)

        for wname in ("3. Groq Whisper", "3. Groq Whisper Fallback", "7d. Get Subtitles (SRT)"):
            params = self.nodes_by_name[wname]["parameters"]["bodyParameters"]["parameters"]
            prompt_val = next(p["value"] for p in params if p["name"] == "prompt")
            self.assertIn("Leonida", prompt_val)
            self.assertIn("Vice City", prompt_val)

        csb_js = self.nodes_by_name["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertIn("const subY = 1010;", csb_js)
        self.assertIn("WASTED", csb_js)
        self.assertIn("$`", csb_js)

        ws_cmd = self.nodes_by_name["Write Sidecar JSON"]["parameters"]["command"]
        self.assertIn("scoreboard.csv", ws_cmd)
        self.assertIn("youtube_shorts", ws_cmd)
        self.assertIn("comment_bait_question", ws_cmd)
        self.assertIn("SPOILER", ws_cmd)


class TestGta6PeakAndVisionLogic(unittest.TestCase):
    def test_peak_separation_and_speaker_tagging(self):
        # 2400s VOD -> min spacing = 90s; test 120s and 50s gaps + intro & housekeeping guard
        raw_bins = {t: {"db": -30.0, "z_db": 0.0, "spec_boost": 0.0, "audio_score": 0.0} for t in range(2400)}
        # Intro peak at t=8 should be ignored; real peaks at t=200, t=250 (too close to 200), t=400, t=700
        raw_bins[8] = {"db": -5.0, "z_db": 6.0, "spec_boost": 0.8, "audio_score": 9.0}
        raw_bins[200] = {"db": -8.0, "z_db": 4.5, "spec_boost": 0.5, "audio_score": 6.75}
        raw_bins[250] = {"db": -9.0, "z_db": 4.2, "spec_boost": 0.4, "audio_score": 5.88}
        raw_bins[400] = {"db": -10.0, "z_db": 3.8, "spec_boost": 0.4, "audio_score": 5.32}
        raw_bins[700] = {"db": -10.5, "z_db": 3.5, "spec_boost": 0.3, "audio_score": 4.55}
        # Silent streamer mic during NPC dialogue around t=395
        for sec in range(392, 398):
            raw_bins[sec] = {"db": -38.0, "z_db": 0.0, "spec_boost": 0.0, "audio_score": 0.0}

        audio_info = {"median_db": -28.0, "std_db": 5.0, "raw_bins": raw_bins}
        # Chat peak at t=205.5 aligns with event at t=200.0 (lag +5.5s)
        chat_info = peak_builder.compute_chat_lag_map(
            {"clusters": [{"peak_time": 205.5, "z_score": 4.0, "laugh_ratio": 0.5, "sample_messages": ["AYO WASTED 💀", "CLIP IT"]}]},
            2400,
        )
        face_info = {"enabled": False, "med_mouth": 0.0, "scores": {}, "mouth_by_sec": {}}
        sentences = [
            {"start": 165.0, "end": 172.0, "text": "Bro we are in a five star chase right now!", "word_count": 9, "is_viewer_voice": False, "tags": []},
            {"start": 195.0, "end": 203.0, "text": "No way that car just launched across Leonida!", "word_count": 8, "is_viewer_voice": False, "tags": []},
            {"start": 392.0, "end": 397.0, "text": "Hey buddy get out of the lane!", "word_count": 7, "is_viewer_voice": False, "tags": []},
            {"start": 398.0, "end": 403.0, "text": "Did the NPC just rob my truck?!", "word_count": 7, "is_viewer_voice": False, "tags": []},
        ]
        tagged = peak_builder.tag_speaker_roles(sentences, audio_info, face_info)
        self.assertEqual(tagged[1]["speaker_tag"], "[STREAMER]")
        self.assertEqual(tagged[2]["speaker_tag"], "[NPC_OR_OTHER_VOICE]")

        cands = peak_builder.extract_top_candidates(2400.0, tagged, audio_info, chat_info, face_info, top_k=4)
        peaks = [c["peak_time"] for c in cands]
        self.assertNotIn(8.0, peaks)
        self.assertIn(200.0, peaks)
        self.assertNotIn(250.0, peaks)  # Within 90s of 200s
        self.assertGreater(cands[0]["z_chat_lagged"], 3.0)
        # Sentence at 165.0 overlaps w_start (200-32=168.0) and snaps cleanly outward to 165.0!
        self.assertEqual(cands[0]["window_start"], 165.0)

    def test_vision_director_normalization_and_bracket_strip(self):
        cands = [{
            "candidate_id": "cand_1",
            "window_start": 100.0,
            "window_end": 150.0,
            "peak_time": 135.0,
            "raw_text": "Look at that Gator jumping the highway barrier!",
            "transcript_lines": ["[02:10.0 | [STREAMER]] Look at that Gator jumping!"],
        }]
        memes = ["vine-boom-sound-effect_KT89XIq.mp3"]
        fb = vision_director.deterministic_candidate_fallback(cands, memes)
        self.assertFalse(fb["clips"][0]["climax_quote"].startswith("]"))

        parsed = {
            "clips": [{
                "candidate_id": "cand_1",
                "title": "Gator Highway Chaos",
                "narrative_archetype": "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
                "hook_caption": "VIRAL MOMENT",  # Banned -> must be replaced!
                "climax_quote": "Look at that Gator jumping!",
                "segments": [
                    {"start": 102.0, "end": 118.0, "role": "SETUP"},
                    {"start": 122.0, "end": 140.0, "role": "PAYOFF"},
                    {"start": 900.0, "end": 920.0, "role": "EXTRA"},  # >2 segs dropped
                ],
                "memes": [{"timestamp": 12.0, "file": "nonexistent.mp3"}],
            }]
        }
        norm = vision_director.normalize_director_clips(parsed, cands, memes)
        cl = norm["clips"][0]
        self.assertEqual(len(cl["segments"]), 2)
        self.assertNotEqual(cl["hook_caption"], "VIRAL MOMENT")
        self.assertEqual(cl["memes"][0]["file"], "vine-boom-sound-effect_KT89XIq.mp3")

        # NSFW shield filters out unsafe clips
        nsfw_parsed = {"clips": [{"candidate_id": "cand_1", "is_nsfw_or_unsafe": True, "hook_caption": "BAD CLIP", "segments": [{"start": 102.0, "end": 135.0}]}]}
        fb_nsfw = vision_director.normalize_director_clips(nsfw_parsed, cands, memes)
        self.assertEqual(fb_nsfw["clips"][0]["is_nsfw_or_unsafe"], False)

    def test_auditor_part1_loophole_closures(self):
        words = [
            {"word": "First", "start": 10.0, "end": 10.4},
            {"word": "sentence.", "start": 10.5, "end": 11.0},
            {"word": "I", "start": 12.0, "end": 12.1},
            {"word": "went...", "start": 12.2, "end": 12.5},
            {"word": "Guys,", "start": 12.6, "end": 12.9},
            {"word": "kind", "start": 13.0, "end": 13.3},
            {"word": "over.", "start": 25.0, "end": 25.5},
            {"word": "Second", "start": 90.0, "end": 90.4},
            {"word": "kind", "start": 90.5, "end": 90.8},
            {"word": "done.", "start": 115.0, "end": 115.5},
        ]
        w_starts = [w["start"] for w in words]
        clip_bad = {
            "clip_number": 1,
            "title": "Bad Loophole Clip",
            "narrative_archetype": "HUBRIS_WAGER_WASTED_KARMA",
            "final_top_hook_caption": "ARE WE GOING TO",  # Dangling TO
            "assembled_spoken_script": "I went... Guys, kind over. Second kind done.",
            "cause_and_effect_setup": "",  # Missing setup -> -15 pts
            "edl_segments": [
                {"segment_order": 0, "start": 12.0, "end": 26.0, "duration": 14.0, "spoken_text": "I went... Guys, kind over.", "signal_tags_in_window": []},
                {"segment_order": 1, "start": 90.0, "end": 116.0, "duration": 26.0, "spoken_text": "Second kind done.", "signal_tags_in_window": []},
            ],
        }
        rep = edl_auditor.score_clip(clip_bad, words, w_starts, [], {"game": "GTA 6"}, entity_df={}, total_sents=100)
        self.assertIn("MISSING_CAUSE_AND_EFFECT_SETUP", rep["flags"])
        self.assertIn("DANGLING_HOOK_END", rep["flags"])
        self.assertIn("DANGLING_ELLIPSIS_OPENER", rep["flags"])
        self.assertIn("FLAT_NO_MULTIMODAL_SIGNAL", rep["flags"])


if __name__ == "__main__":
    unittest.main()
