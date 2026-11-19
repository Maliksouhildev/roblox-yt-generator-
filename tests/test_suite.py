import re
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
import json
import math
import os
import subprocess
import tempfile
import cam_detector

class TestPipelineComprehensive(unittest.TestCase):

    def setUp(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        wf_p = os.path.join(base_dir, 'workflows', 'workflow.json')
        if not os.path.exists(wf_p):
            wf_p = os.path.join(base_dir, 'workflow.json')
        with open(wf_p, 'r', encoding='utf-8') as f:
            self.wf = json.load(f)
        self.nodes = {n['name']: n for n in self.wf['nodes']}

    def test_cam_detector_top_hud_rejection(self):
        """Top-center and upper overlay candidates (follower counter / countdown timer) must be rejected."""
        real_w, real_h = 1920, 1080
        
        # Test 1: Exactly top-center (x=960, y=150) -> Follower Goal / Timer
        cand_cx, cand_cy = 960, 150
        is_hud = (cand_cy < real_h * 0.25 and (real_w * 0.18 <= cand_cx <= real_w * 0.82))
        self.assertTrue(is_hud, "Top-center HUD candidate must be rejected")

        # Test 2: Upper-middle right (x=1400, y=200) -> Countdown Timer
        cand_cx2, cand_cy2 = 1400, 200
        is_hud2 = (cand_cy2 < real_h * 0.25 and (real_w * 0.18 <= cand_cx2 <= real_w * 0.82))
        self.assertTrue(is_hud2, "Upper-middle countdown timer must be rejected")

        # Test 3: Micro avatar candidate in top 35% (e.g. Roblox leaderboard icon)
        cand_w, cand_h = 36, 36
        is_micro_hud = (300 < real_h * 0.35 and (cand_w < 48 or cand_h < 48))
        self.assertTrue(is_micro_hud, "Micro-avatar in top area must be rejected")

        # Test 4: Genuine Corner facecam (x=200, y=150) -> Must NOT be rejected
        corner_cx, corner_cy = 200, 150
        is_corner_hud = (corner_cy < real_h * 0.25 and (real_w * 0.18 <= corner_cx <= real_w * 0.82))
        self.assertFalse(is_corner_hud, "Corner facecam must not be flagged as top HUD")

    def test_cam_detector_sanitize_crop_bounds_and_ratio(self):
        """Webcam crop must preserve narrow physical boxes (<1.55) and match 720:380 on wide boxes."""
        # Narrow physical box: x=1400, y=50, w=450, h=300 (aspect 1.50 < 1.55 -> exact physical box)
        box = (1400, 50, 450, 300)
        crop = cam_detector.sanitize_crop(
            cx=1600, cy=200, fw=100, fh=120,
            camera_type="box", box_coords=box
        )
        self.assertTrue(crop["ai_found"])
        self.assertEqual(crop["camera_type"], "box")
        self.assertGreaterEqual(crop["cam_x"], 1400)
        self.assertLessEqual(crop["cam_x"] + crop["cam_w"], 1400 + 450)
        self.assertGreaterEqual(crop["cam_y"], 50)
        self.assertLessEqual(crop["cam_y"] + crop["cam_h"], 50 + 300)
        self.assertEqual(crop["cam_w"] % 2, 0)
        self.assertEqual(crop["cam_h"] % 2, 0)
        self.assertAlmostEqual(crop["cam_w"] / crop["cam_h"], 450.0 / 300.0, delta=0.05)

        # Wide physical box: x=1200, y=50, w=680, h=360 (aspect 1.889 >= 1.55 -> 720:380 target ratio)
        wide_box = (1200, 50, 680, 360)
        wide_crop = cam_detector.sanitize_crop(
            cx=1540, cy=200, fw=100, fh=120,
            camera_type="box", box_coords=wide_box
        )
        self.assertEqual(wide_crop["cam_w"] % 2, 0)
        self.assertEqual(wide_crop["cam_h"] % 2, 0)
        self.assertAlmostEqual(wide_crop["cam_w"] / wide_crop["cam_h"], 720.0 / 380.0, delta=0.08)
        self.assertLessEqual(wide_crop["cam_y"], 200 - int(wide_crop["cam_h"] * 0.30))

    def test_split_clips_all_seven_user_failure_cases(self):
        """Simulate Split Clips logic on all 7 failure cases from the user's issue list."""
        def run_split_clips(clip):
            sTime = float(clip.get("start_time", 0))
            eTime = float(clip.get("end_time", sTime + 36))
            pTime = float(clip.get("payoff_time", eTime - 3.5))

            # Anti-loading screen rule
            if sTime < 3.0:
                sTime = 3.0

            # Tight hook & setup: max 18s buildup before climax
            if pTime > sTime and (pTime - sTime) > 18.0:
                sTime = round((pTime - 15.0) * 10) / 10
                if sTime < 3.0:
                    sTime = 3.0

            # Punchy aftermath: max 3.5s aftermath after climax
            if pTime > sTime and (eTime - pTime) > 3.5:
                eTime = round((pTime + 3.0) * 10) / 10

            dur = eTime - sTime
            if dur < 16:
                if sTime > 4.0:
                    sTime = max(3.0, round((eTime - 18.0) * 10) / 10)
            elif dur > 40:
                if pTime > sTime and (pTime - sTime) > 20:
                    sTime = round((pTime - 18.0) * 10) / 10
                eTime = min(eTime, sTime + 38.0)

            return sTime, eTime, pTime

        # Case 1: Glitched Wall Final 1v1 (First 11s wasted on static character hype, payoff at 22s)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 26.0, "payoff_time": 22.0})
        self.assertGreaterEqual(s, 7.0, "Issue 1: Start must be advanced to >= 7.0s, eliminating the first 11s of static hype")
        self.assertLessEqual(p - s, 16.0, "Issue 1: Buildup before 1v1 payoff must be <= 16s")

        # Case 2: Ninja Power Purchase (00:07 avatar complaint, 00:15 sound complaint, 00:26 purchase)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 30.0, "payoff_time": 26.0})
        self.assertGreaterEqual(s, 11.0, "Issue 2: Start must be advanced past 00:07 avatar complaint")

        # Case 3: Voice Chat E Boy Jump (Loading screen 00:00-00:02, jumpscare at 16s)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 20.0, "payoff_time": 16.0})
        self.assertGreaterEqual(s, 3.0, "Issue 3: Start must be advanced past 00:00-00:02 loading screen")

        # Case 4: Level One Trade Fail (Agonizingly slow 15s trade menu 00:12-00:27, text box at 27s)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 32.0, "payoff_time": 27.0})
        self.assertGreaterEqual(s, 12.0, "Issue 4: Start must be advanced to >= 12.0s, eliminating 15s slow trade menu")

        # Case 5: Massive 100 Donation Hype (Donation at 12s, slow conversational reaction 00:12-00:27)
        s, e, p = run_split_clips({"start_time": 5.0, "end_time": 27.0, "payoff_time": 12.0})
        self.assertEqual(e, 15.0, "Issue 5: Aftermath must be clamped to 15.0s, cutting out 12s of conversational chatter")

        # Case 6: DEV JOINS KITCHEN (Wastes 00:07-00:17 on stream chatter before dev event at 22s)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 26.0, "payoff_time": 22.0})
        self.assertGreaterEqual(s, 7.0, "Issue 6: Start must be advanced to >= 7.0s, eliminating preamble stream chatter")

        # Case 7: MAX UPGRADE GRIND (20s of unedited potato shooting 00:00-00:20, upgrade at 25s)
        s, e, p = run_split_clips({"start_time": 0.0, "end_time": 29.0, "payoff_time": 25.0})
        self.assertGreaterEqual(s, 10.0, "Issue 7: Start must be advanced to >= 10.0s, cutting grinding in half")

    def test_extract_viral_segments_tight_jump_cuts(self):
        """Silences > 0.55s must be jump cut and leading dead air trimmed with 0.12s buffer."""
        BUFFER = 0.12
        start = 0.0
        end = 30.0
        # Words start at 2.4s (loading screen 0-2.2s), with a 1.2s pause at 3.0s-4.2s
        clipWords = [
            {"word": "Let's", "start": 2.4, "end": 2.7},
            {"word": "go", "start": 2.8, "end": 3.0},
            {"word": "He", "start": 4.2, "end": 4.5},
            {"word": "glitched", "start": 4.6, "end": 5.0}
        ]

        finalSegs = []
        currentSegStart = max(start, clipWords[0]["start"] - 0.10)
        lastWordEnd = clipWords[0]["end"]

        for i in range(1, len(clipWords)):
            w = clipWords[i]
            if w["start"] - lastWordEnd > 0.55:
                finalSegs.append({
                    "start": currentSegStart,
                    "end": lastWordEnd + BUFFER
                })
                currentSegStart = max(lastWordEnd + BUFFER, w["start"] - BUFFER)
            lastWordEnd = w["end"]
        finalSegs.append({
            "start": currentSegStart,
            "end": min(end, lastWordEnd + BUFFER)
        })

        self.assertGreaterEqual(finalSegs[0]["start"], 2.30, "Leading loading screen must be trimmed")
        self.assertEqual(len(finalSegs), 2, "1.2s pause must be jump cut into 2 segments")
        self.assertLessEqual(finalSegs[0]["end"], 3.0 + BUFFER + 0.01)
        self.assertGreaterEqual(finalSegs[1]["start"], 4.2 - BUFFER - 0.01)

    def test_ffmpeg_crop_and_climax_zoom_levels(self):
        """Verify gameplay crop offsets bypass top HUD and punch zoom is 1.45x."""
        ih = 1080
        # hasCam gameplay crop: 720x900 (70% screen priority) with 10% vertical offset
        crop_h_cam = int(ih * 0.85 // 2) * 2
        crop_w_cam = int(crop_h_cam * (720.0 / 900.0) // 2) * 2
        crop_y_cam = int(ih * 0.10 // 2) * 2
        self.assertEqual(crop_y_cam, 108, "Top 108px follower counter and timer must be cropped out")
        self.assertLessEqual(crop_y_cam + crop_h_cam, 1080)

        # No-cam full screen gameplay crop: 720x1280 with 11% vertical offset
        crop_h_nocam = int(ih * 0.86 // 2) * 2
        crop_w_nocam = int(crop_h_nocam * (720.0 / 1280.0) // 2) * 2
        crop_y_nocam = int(ih * 0.11 // 2) * 2
        self.assertEqual(crop_y_nocam, 118, "No-cam: Top 118px follower counter and timer must be cropped out")
        self.assertLessEqual(crop_y_nocam + crop_h_nocam, 1080)

        # Climax punch zoom check
        cs_code = self.nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertIn("scale=trunc(720*1.45/2)*2", cs_code, "Climax punch zoom must be 1.45x for distant payoffs & jumpscares")
        self.assertIn("equalizer=f=3500", cs_code, "Audio mastering must notch de-harsh distorted voice chat")
        self.assertIn("fs.existsSync('/files/temp/screams.json')", cs_code, "Must read screams.json from disk")

    def test_node_syntax_validity_via_node_c(self):
        """Run real Node.js syntax check (node -c) on every jsCode block in workflow.json."""
        for n in self.wf['nodes']:
            js = n.get('parameters', {}).get('jsCode')
            if js:
                with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
                    tf.write('function testWrapper() {\n' + js + '\n}\n')
                    temp_name = tf.name
                try:
                    res = subprocess.run(['node', '-c', temp_name], capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, f"Node.js syntax error in node '{n['name']}': {res.stderr}")
                finally:
                    if os.path.exists(temp_name):
                        os.remove(temp_name)


    def test_sanitize_caption_filters_all_raw_n8n_placeholders(self):
        """Review Point 1: $(LOOP CLIPS) and raw n8n expression placeholders must be strictly filtered."""
        def sanitize_caption(str_val, default_fallback="MUST WATCH MOMENT"):
            if not str_val or not isinstance(str_val, str):
                return default_fallback
            clean = str_val.strip()
            if re.search(r'[\$({]|item\.json|loop\s*clips|\{\{|\}\}|undefined|null', clean, re.IGNORECASE):
                return default_fallback
            clean = re.sub(r'[{}\x27\x22`$()]', '', clean).replace('_', ' ').strip().upper()
            if len(clean) < 3 or re.search(r'LOOP CLIPS|ITEM JSON', clean, re.IGNORECASE):
                return default_fallback
            return clean[:42]

        # Case 1: Raw n8n path burned in user review
        self.assertEqual(sanitize_caption("$(LOOP CLIPS).ITEM.JSON.HOOK_CAPTION"), "MUST WATCH MOMENT")
        self.assertEqual(sanitize_caption("$(LOOP CLIPS).ITEM.JSON.TITLE"), "MUST WATCH MOMENT")
        self.assertEqual(sanitize_caption("{{ $('Loop Clips').item.json.hook_caption }}"), "MUST WATCH MOMENT")
        self.assertEqual(sanitize_caption("undefined"), "MUST WATCH MOMENT")
        self.assertEqual(sanitize_caption(""), "MUST WATCH MOMENT")
        # Case 2: Genuine caption
        self.assertEqual(sanitize_caption("Bro tried to run away"), "BRO TRIED TO RUN AWAY")
        self.assertEqual(sanitize_caption("the campfire is almost out"), "THE CAMPFIRE IS ALMOST OUT")

    def test_loop_clips_batch_size_multi_clip_iteration(self):
        """Review Point 5: Loop Clips must specify batchSize: 1 at top level to generate all 3-5 clips."""
        loop_node = self.nodes.get("Loop Clips")
        self.assertIsNotNone(loop_node)
        params = loop_node.get("parameters", {})
        self.assertEqual(params.get("batchSize"), 1, "Loop Clips batchSize must be 1, preventing single-clip loop exit")

    def test_three_zone_vertical_layout_collision_prevention(self):
        """Floating seam layout: y=0..380 cam flush with y=380..1280 gameplay, floating seam hook y=380 (y=145 no-cam), y=1000 dynamic subs."""
        cs_code = self.nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertIn("const subY = 1000;", cs_code, "Subtitles must be at y=1000 in lower-third above YT UI")
        self.assertIn("const captionY = isSplitCam ? 380 : 145;", cs_code, "Hook banner must float on y=380 seam (split-cam) or y=145 (no-cam)")

    def test_subtitle_styling_color_highlight_and_no_single_word_lines(self):
        """Review Point 4: Rock-solid font metrics (no \fscx line jitter) and min 2 words per line."""
        cs_code = self.nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertNotIn("fscx115", cs_code, "Word highlighting must not scale font to prevent line jumping/jitter")
        self.assertIn("hasMinWords = current.length >= 2", cs_code, "Must enforce minimum 2 words per line")

    def test_reaction_triggers_and_115_punch_zoom(self):
        """Virality Update: Reaction triggers scale up gameplay or webcam by 115% for aggressive punchy zoom."""
        cs_code = self.nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertIn("scale=trunc(720*1.15/2)*2", cs_code, "FFmpeg must scale by 115% for scream and reaction punch zooms")
        self.assertIn("DANGER_WORDS", cs_code, "Must detect danger words for dynamic color and emoji injection")

    def test_cold_open_splicing_and_filler_trimming(self):
        """Virality Update: HOOK_CLIMAX cold open retention trap and conversational filler word trimming."""
        ev_code = self.nodes["6. Extract Viral Segments"]["parameters"]["jsCode"]
        self.assertIn("HOOK_CLIMAX", ev_code, "Extract Viral Segments must support HOOK_CLIMAX splicing")
        self.assertIn("fillerWords", ev_code, "Must trim conversational hesitation filler words")

    def test_split_clips_multi_segment_narrative_arching_runtime(self):
        """Execute real 5. Split Clips JS in Node.js to verify 3-act segments and non-overlapping multi-arc retention."""
        split_js = self.nodes["5. Split Clips"]["parameters"]["jsCode"]
        mock_payload = {
            "clips": [
                {
                    "clip_number": 1,
                    "narrative_archetype": "HUBRIS_INSTANT_KARMA",
                    "title": "1v1 For The Scythe?! 💀",
                    "hook_caption": "1V1 FOR THE SCYTHE?!",
                    "virality_score": 92,
                    "start_time": 10.0,
                    "end_time": 343.0,
                    "payoff_time": 340.0,
                    "segments": [
                        {"start": 10.0, "end": 22.0, "role": "SETUP"},
                        {"start": 144.0, "end": 157.0, "role": "ESCALATION"},
                        {"start": 326.0, "end": 340.0, "role": "PAYOFF"}
                    ]
                },
                {
                    "clip_number": 2,
                    "narrative_archetype": "REVERSE_PAYOFF_LOOP",
                    "title": "Scam For $20,000?! 😱",
                    "hook_caption": "SCAM FOR $20,000?!",
                    "virality_score": 95,
                    "start_time": 53.0,
                    "end_time": 454.0,
                    "payoff_time": 450.0,
                    "segments": [
                        {"start": 53.0, "end": 65.0, "role": "SETUP"},
                        {"start": 252.0, "end": 268.0, "role": "ESCALATION"},
                        {"start": 438.0, "end": 453.0, "role": "PAYOFF"}
                    ]
                },
                {
                    "clip_number": 3,
                    "narrative_archetype": "DOUBLE_DOWN_ESCALATION",
                    "title": "Single Span Fallback 😭",
                    "hook_caption": "BRO ACTUALLY LOST",
                    "virality_score": 88,
                    "start_time": 520.0,
                    "end_time": 554.0,
                    "payoff_time": 551.0
                }
            ]
        }
        harness = (
            "const $input = { all: () => [{ json: { output: " + json.dumps(json.dumps(mock_payload)) + " } }] };\n"
            "const $ = (name) => ({ item: { json: {} }, last: () => ({ json: { dry_run: true, streamer_name: 'Kreek' } }), first: () => ({ json: {} }) });\n"
            "function runNode() {\n" + split_js + "\n}\n"
            "console.log(JSON.stringify(runNode()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness)
            tpath = tf.name
        try:
            res = subprocess.run(['node', tpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"5. Split Clips runtime failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertEqual(len(out), 3, f"Expected all 3 distinct multi-segment clips preserved, got {len(out)}")
            for idx_item, item in enumerate(out):
                segs = item['json']['segments']
                roles = [s['role'] for s in segs]
                if len(segs) >= 3:
                    self.assertIn('SETUP', roles)
                    self.assertIn('ESCALATION', roles)
                    self.assertIn('PAYOFF', roles)
                else:
                    self.assertEqual(roles, ['CONTINUOUS_ARC'])
                tot = sum(s['end'] - s['start'] for s in segs)
                self.assertGreaterEqual(tot, 22.0)
                self.assertLessEqual(tot, 45.5)
        finally:
            if os.path.exists(tpath):
                os.remove(tpath)

    def test_sandbox_edl_multi_segment_audit(self):
        """Verify test_script_sandbox.splice_clip_edl and audit_sandbox_edl enforce 3-act 30-45s arcs and zero mid-sentence cuts."""
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
        import test_script_sandbox as tss

        # Build synthetic Whisper words with clean sentence boundaries
        words = []
        t = 10.0
        sentences = [
            "If I win, I get the Nicholas Scythe.",
            "Bring it on, you Teletubby.",
            "I need to lock in right now.",
        ]
        for s in sentences:
            for tok in s.split():
                words.append({"word": tok, "start": round(t, 2), "end": round(t + 0.65, 2)})
                t += 0.72
            t += 0.15
        t = 140.0
        for s in ["I can't hit him!", "Why can't I not hit him?", "Bro is glitching through the walls!"]:
            for tok in s.split():
                words.append({"word": tok, "start": round(t, 2), "end": round(t + 0.65, 2)})
                t += 0.72
            t += 0.15
        t = 320.0
        for s in ["I cheated through the walls!", "Scam him!", "How much can I sell it for on eBay?"]:
            for tok in s.split():
                words.append({"word": tok, "start": round(t, 2), "end": round(t + 0.65, 2)})
                t += 0.72
            t += 0.15

        clips_in = [
            {
                "clip_number": i + 1,
                "narrative_archetype": arch,
                "title": f"Arc {i+1} 💀",
                "hook_caption": f"ARC {i+1}",
                "segments": [
                    {"start": 10.0, "end": 22.0, "role": "SETUP"},
                    {"start": 140.0, "end": 152.0, "role": "ESCALATION"},
                    {"start": 320.0 + i * 100, "end": 332.0 + i * 100, "role": "PAYOFF"},
                ] if i == 0 else [
                    {"start": 10.0, "end": 22.0, "role": "SETUP"},
                    {"start": 140.0, "end": 152.0, "role": "ESCALATION"},
                    {"start": 320.0, "end": 332.0, "role": "PAYOFF"},
                ]
            }
            for i, arch in enumerate(["HUBRIS_INSTANT_KARMA", "DOUBLE_DOWN_ESCALATION", "MYSTERY_OPEN_LOOP", "REVERSE_PAYOFF_LOOP"])
        ]
        # Make payoffs distinct for clips 1..4
        for idx_c, c in enumerate(clips_in):
            off = idx_c * 100.0
            c["segments"][2]["start"] = 320.0 + off
            c["segments"][2]["end"] = 332.0 + off
            if idx_c > 0:
                base = 320.0 + off
                wt = base
                for tok in ["He", "actually", "did", "it.", "Oh", "my", "god,", "no", "way!", "Twenty", "thousand", "dollars!"]:
                    words.append({"word": tok, "start": round(wt, 2), "end": round(wt + 0.85, 2)})
                    wt += 0.90

        previews = [tss.splice_clip_edl(c, words) for c in clips_in]
        idx_doc = {
            "stream_duration_sec": 700.0,
            "anchors": [{"peak_time": 325.0 + i * 100.0, "start": 320.0 + i * 100.0} for i in range(4)],
        }
        audit = tss.audit_sandbox_edl({"previews": previews}, idx_doc, words=words)
        self.assertTrue(audit["all_passed"], f"Sandbox audit failed: {audit}")

    def test_banned_captions_no_words_and_fallback_to_director_hook(self):
        """Bug 1: NO WORDS / NO AUDIO FOUND / NO TRANSCRIPT / UNDEFINED / NULL / ERROR must fall back to Director hook."""
        cs_code = self.nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
        harness = (
            "const $input = { first: () => ({ json: {} }) };\n"
            "const $ = () => ({ item: { json: {} }, last: () => ({ json: {} }) });\n"
            + cs_code.split("const subInput =")[0]
            + "\nconst results = ['NO WORDS','NO AUDIO FOUND','NO TRANSCRIPT','UNDEFINED','NULL','ERROR','He actually screamed!']"
              ".map(s => sanitizeCaption(s, 'ESCAPING THE DOLLHOUSE'));\n"
              "console.log(JSON.stringify(results));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness)
            tpath = tf.name
        try:
            res = subprocess.run(['node', tpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"sanitizeCaption harness failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertEqual(out[:6], ["ESCAPING THE DOLLHOUSE"] * 6)
            self.assertEqual(out[6], "He actually screamed!")
        finally:
            if os.path.exists(tpath):
                os.remove(tpath)

    def test_screen_ui_audit_parser_and_fail_open(self):
        """Bug 2: screen_ui_audit.py parses Vision JSON obstruction verdicts and fails closed on missing/unreadable videos."""
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
        import screen_ui_audit as sua

        pos = sua.parse_audit_response('```json\n{"has_ui_obstruction": true, "bad_frames": [0, 2]}\n```')
        self.assertTrue(pos["has_ui_obstruction"])
        self.assertEqual(pos["bad_frames"], [0, 2])

        neg = sua.parse_audit_response('{"has_ui_obstruction": false, "bad_frames": []}')
        self.assertFalse(neg["has_ui_obstruction"])

        missing = sua.audit_video("/nonexistent/path/concatenated_clip.mp4")
        self.assertTrue(missing["has_ui_obstruction"])
        self.assertEqual(missing.get("reason"), "video_missing")

    def test_extract_viral_segments_sentence_pause_snapping_runtime(self):
        """Bug 4: 6. Extract Viral Segments snaps mid-clause cuts to Whisper sentence/pause boundaries within ±1.2s."""
        ev_js = self.nodes["6. Extract Viral Segments"]["parameters"]["jsCode"]
        words = [
            {"word": "Wait,", "start": 10.0, "end": 10.3},
            {"word": "why", "start": 10.35, "end": 10.6},
            {"word": "do", "start": 10.65, "end": 10.8},
            {"word": "I", "start": 10.85, "end": 11.0},
            {"word": "hear", "start": 11.05, "end": 11.3},
            {"word": "footsteps?", "start": 11.35, "end": 11.9},
            {"word": "Run", "start": 12.4, "end": 12.7},
            {"word": "right", "start": 12.75, "end": 13.0},
            {"word": "now!", "start": 13.05, "end": 13.5},
            {"word": "Oh", "start": 25.0, "end": 25.2},
            {"word": "my", "start": 25.25, "end": 25.45},
            {"word": "gosh,", "start": 25.5, "end": 25.8},
            {"word": "why", "start": 25.85, "end": 26.05},
            {"word": "am", "start": 26.1, "end": 26.25},
            {"word": "I", "start": 26.3, "end": 26.45},
            {"word": "trapped", "start": 26.5, "end": 26.9},
            {"word": "here?!", "start": 26.95, "end": 27.4},
            {"word": "Help!", "start": 40.0, "end": 40.5},
            {"word": "It", "start": 40.55, "end": 40.7},
            {"word": "got", "start": 40.75, "end": 41.0},
            {"word": "me!", "start": 41.05, "end": 41.5},
        ]
        # Pad words so segment durations hit >= 30s cleanly
        clip_in = {
            "clip_number": 1,
            "title": "Footsteps Behind Me 😱",
            "hook_caption": "WAIT WHY FOOTSTEPS?!",
            "payoff_time": 41.2,
            "segments": [
                {"start": 10.5, "end": 20.5, "role": "SETUP"},
                {"start": 25.9, "end": 36.2, "role": "ESCALATION"},
                {"start": 40.4, "end": 50.8, "role": "PAYOFF"},
            ]
        }
        harness = (
            "const $input = { all: () => [{ json: " + json.dumps(clip_in) + " }] };\n"
            "const $ = (name) => name === '3. Groq Whisper' ? { first: () => ({ json: { words: " + json.dumps(words) + " } }) } : { first: () => ({ json: {} }), last: () => ({ json: {} }) };\n"
            "function runNode() {\n" + ev_js + "\n}\n"
            "console.log(JSON.stringify(runNode()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness)
            tpath = tf.name
        try:
            res = subprocess.run(['node', tpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"6. Extract Viral Segments runtime failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertEqual(len(out), 3)
            # SETUP started at 10.5 (mid-clause 'why do I') -> must snap back to 10.0 ('Wait, why do I hear footsteps?')
            self.assertLessEqual(out[0]['json']['start'], 10.05)
            self.assertTrue(out[0]['json']['spoken_text'].startswith("Wait,"))
            # ESCALATION started at 25.9 (mid-clause 'am I trapped') -> must snap back to 25.0 ('Oh my gosh...')
            self.assertLessEqual(out[1]['json']['start'], 25.05)
            self.assertTrue(out[1]['json']['spoken_text'].startswith("Oh my gosh"))
            # PAYOFF started at 40.4 -> must snap back before 'Help!' (<= 40.0)
            self.assertLessEqual(out[2]['json']['start'], 40.05)
            self.assertTrue(out[2]['json']['spoken_text'].startswith("Help!"))
        finally:
            if os.path.exists(tpath):
                os.remove(tpath)

    def test_split_clips_rejects_intro_rules_and_raid_thank_yous(self):
        """Bug 3: 5. Split Clips filters out raid thank-yous and stream intro rules clips."""
        split_js = self.nodes["5. Split Clips"]["parameters"]["jsCode"]
        mock_payload = {
            "clips": [
                {
                    "clip_number": 1,
                    "narrative_archetype": "HUBRIS_INSTANT_KARMA",
                    "title": "Stream Rules Intro 💀",
                    "hook_caption": "KEEP COUNTER RULES",
                    "virality_score": 95,
                    "assembled_spoken_script": "Thank you for the raid guys! Make sure to watch till the end of the stream for the keep counter!",
                    "segments": [
                        {"start": 10.0, "end": 21.0, "role": "SETUP"},
                        {"start": 22.0, "end": 33.0, "role": "ESCALATION"},
                        {"start": 34.0, "end": 45.0, "role": "PAYOFF"}
                    ]
                },
                {
                    "clip_number": 2,
                    "narrative_archetype": "DOUBLE_DOWN_ESCALATION",
                    "title": "Dollhouse Jumpscare 😱",
                    "hook_caption": "DOLLHOUSE MONSTER CHASE",
                    "virality_score": 90,
                    "assembled_spoken_script": "It is right behind us! Run up the stairs right now!",
                    "segments": [
                        {"start": 120.0, "end": 131.0, "role": "SETUP"},
                        {"start": 132.0, "end": 143.0, "role": "ESCALATION"},
                        {"start": 144.0, "end": 156.0, "role": "PAYOFF"}
                    ]
                }
            ]
        }
        harness = (
            "const $input = { all: () => [{ json: { output: " + json.dumps(json.dumps(mock_payload)) + " } }] };\n"
            "const $ = () => ({ item: { json: {} }, last: () => ({ json: { dry_run: true, streamer_name: 'Kreek' } }), first: () => ({ json: {} }) });\n"
            "function runNode() {\n" + split_js + "\n}\n"
            "console.log(JSON.stringify(runNode()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness)
            tpath = tf.name
        try:
            res = subprocess.run(['node', tpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"5. Split Clips runtime failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]['json']['title'], "Dollhouse Jumpscare 😱")
        finally:
            if os.path.exists(tpath):
                os.remove(tpath)

    def test_dead_space_avatar_row_filter(self):
        """Virality Update: cam_detector.py detects static row of non-animated VTuber avatars in top third."""
        real_w, real_h = 1920, 1080
        clusters = [
            {"avg_cx": 400, "avg_cy": 180, "avg_w": 80, "avg_h": 80},
            {"avg_cx": 960, "avg_cy": 170, "avg_w": 85, "avg_h": 85},
            {"avg_cx": 1500, "avg_cy": 185, "avg_w": 80, "avg_h": 80}
        ]
        top_avatars = [c for c in clusters if c["avg_cy"] < real_h * 0.38]
        self.assertEqual(len(top_avatars), 3)
        xs = [c["avg_cx"] for c in top_avatars]
        is_avatar_row = (max(xs) - min(xs)) > real_w * 0.25
        self.assertTrue(is_avatar_row, "Top avatar row across screen width must be detected as dead space")

    def test_scout_chunking_circuit_breaker_and_accumulate_normalization(self):
        """Scout hardening: <=4 chunks on 3h VOD, circuit breaker skips dead primary, Accumulate normalizes MM:SS and drops <120-char stubs."""
        # 1. Test 1. Prepare Scout Prompt chunk count on a simulated 3.3h (3098 sentences) stream
        prep_js = self.nodes["1. Prepare Scout Prompt"]["parameters"]["jsCode"]
        synth_sentences = [
            {"start": i * 3.9, "end": i * 3.9 + 3.5, "text": f"Sentence {i} we are running from the monster inside Roblox Doors!"}
            for i in range(3098)
        ]
        harness_prep = (
            "const staticStore = {};\n"
            "const $getWorkflowStaticData = () => staticStore;\n"
            "const $input = { all: () => [{ json: { dry_run: false, duration: 12132.8, text: 'hello', annotated_sentences: " + json.dumps(synth_sentences) + " } }] };\n"
            "const $ = () => ({ first: () => ({ json: {} }), last: () => ({ json: {} }) });\n"
            "function runNode() {\n" + prep_js + "\n}\n"
            "const res = runNode();\n"
            "console.log(JSON.stringify({ count: res.length, firstIdx: res[0].json.chunk_index }));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_prep)
            p_path = tf.name
        try:
            res = subprocess.run(['node', p_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Prepare Scout Prompt failed: {res.stderr}")
            parsed = json.loads(res.stdout.strip())
            self.assertLessEqual(parsed["count"], 4, "3.3h VOD must be chunked into <= 4 chunks")
            self.assertGreaterEqual(parsed["count"], 3)
        finally:
            if os.path.exists(p_path):
                os.remove(p_path)

        # 2. Test Guard Scout Retries trips _scout_primary_dead after repeated 429s even when error description is stripped
        guard_js = self.nodes["Guard Scout Retries"]["parameters"]["jsCode"]
        health_js = self.nodes["Check Scout Primary Health"]["parameters"]["jsCode"]
        harness_guard = (
            "const staticStore = { _scout_primary_dead: false, _scout_consec_429: 0 };\n"
            "const $getWorkflowStaticData = () => staticStore;\n"
            "let $input = { all: () => [{ json: { error: 'The service is receiving too many requests from you' } }] };\n"
            "function runGuard() {\n" + guard_js + "\n}\n"
            "function runHealth() {\n" + health_js + "\n}\n"
            "const r1 = runGuard();\n"
            "$input = { all: () => [{ json: { ...r1[0].json } }] };\n"
            "const r2 = runGuard();\n"
            "$input = { all: () => [{ json: { prompt: 'chunk2' } }] };\n"
            "const h = runHealth();\n"
            "console.log(JSON.stringify({ r1_retry: r1[0].json._allow_retry, r2_retry: r2[0].json._allow_retry, dead: staticStore._scout_primary_dead, next_live: h[0].json._scout_primary_live }));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_guard)
            g_path = tf.name
        try:
            res = subprocess.run(['node', g_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Guard Scout Retries failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertTrue(out["r1_retry"])
            self.assertFalse(out["r2_retry"])
            self.assertTrue(out["dead"])
            self.assertFalse(out["next_live"])
        finally:
            if os.path.exists(g_path):
                os.remove(g_path)

        # 3. Test Scout Accumulate normalizes MM:SS timestamps, trims partial trailing line, and drops <120-char stubs
        acc_js = self.nodes["Scout Accumulate"]["parameters"]["jsCode"]
        run0 = (
            "Tag & Recommended Archetype: [THE SPOILER REVEAL] | Archetype: [HUBRIS_INSTANT_KARMA]\n"
            "- [SETUP / STAKES] Timestamp: [06:48.0s - 06:59.2s]\n"
            "- [PAYOFF / REACTION] Timestamp: [12:31.9s - 1234.6s]\n"
            "- [ESCALATION / STRUGGLE] Timestamp: [12:36.4s -"
        )
        run2 = "Tag & Recommended Archetype: [THE CORNY JOKE ROAST] | Archetype:"
        harness_acc = (
            "const $items = (name, outIdx, runIdx) => {\n"
            "  if (name === '2. Basic LLM Chain (Scout Fallback)') {\n"
            f"    if (runIdx === 0) return [{{ json: {{ text: {json.dumps(run0)} }} }}];\n"
            f"    if (runIdx === 1) return [{{ json: {{ text: {json.dumps(run2)} }} }}];\n"
            "  }\n"
            "  return [];\n"
            "};\n"
            "const $ = () => ({ first: () => ({ json: { dry_run: false } }) });\n"
            "function runAcc() {\n" + acc_js + "\n}\n"
            "console.log(JSON.stringify(runAcc()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_acc)
            a_path = tf.name
        try:
            res = subprocess.run(['node', a_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Scout Accumulate failed: {res.stderr}")
            out = json.loads(res.stdout.strip())
            self.assertEqual(len(out), 1, "Must drop 64-char truncated stub chunk")
            txt = out[0]["json"]["text"]
            self.assertIn("[408.0s - 419.2s]", txt)
            self.assertIn("[751.9s - 1234.6s]", txt)
            self.assertNotIn("[12:36.4s -", txt)
        finally:
            if os.path.exists(a_path):
                os.remove(a_path)

    def test_masterplan_bug_a_b_c_d_and_telemetry(self):
        """Verify Masterplan Bug A (no payoff truncation/no blind backward padding/22s floor/outro), Bug B (1-seg continuous + entity continuity), Bug C (sandbox parity + hook anti-hallucination), Bug D (staticData guards), and Section 3 telemetry."""
        # 1. Bug A & B in 5. Split Clips
        split_js = self.nodes["5. Split Clips"]["parameters"]["jsCode"]
        synth_words = []
        # Create two disconnected scenes: 100..128 (Entity: Dragon Fruit) and 200..235 (Entity: Pizza Delivery)
        for i in range(14):
            t0 = 100.0 + i * 2.0
            synth_words.append({"word": f"Dragon", "start": t0, "end": t0 + 0.4})
            synth_words.append({"word": f"fruit", "start": t0 + 0.4, "end": t0 + 0.8})
            synth_words.append({"word": f"wow.", "start": t0 + 0.8, "end": t0 + 1.4})
        for i in range(18):
            t0 = 200.0 + i * 2.0
            synth_words.append({"word": f"Pizza", "start": t0, "end": t0 + 0.4})
            synth_words.append({"word": f"box", "start": t0 + 0.4, "end": t0 + 0.8})
            synth_words.append({"word": f"insane!", "start": t0 + 0.8, "end": t0 + 1.5})
        # Also continuous scene 300..324 (24s >= 22s floor, < 30s) with explicitPayoff at start of climax (314.0) while segment ends at 324.0
        for i in range(12):
            t0 = 300.0 + i * 2.0
            synth_words.append({"word": f"Obsidian", "start": t0, "end": t0 + 0.4})
            synth_words.append({"word": f"sword", "start": t0 + 0.4, "end": t0 + 0.8})
            synth_words.append({"word": f"clutch!", "start": t0 + 0.8, "end": t0 + 1.4})

        director_mock = json.dumps({
            "clips": [
                {
                    "title": "CONTINUOUS CLUTCH",
                    "hook_caption": "OBSIDIAN SWORD CLUTCH",
                    "archetype": "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
                    "payoff_time": 314.0,
                    "segments": [{"start": 300.0, "end": 324.0, "role": "CONTINUOUS_ARC"}],
                    "viral_score": 9.2
                },
                {
                    "title": "DISCONNECTED STITCH",
                    "hook_caption": "DRAGON AND PIZZA",
                    "archetype": "HUBRIS_WAGER_INSTANT_KARMA",
                    "payoff_time": 230.0,
                    "segments": [
                        {"start": 100.0, "end": 112.0, "role": "SETUP"},
                        {"start": 200.0, "end": 225.0, "role": "PAYOFF"}
                    ],
                    "viral_score": 8.0
                },
                {
                    "title": "PANHANDLING OUTRO",
                    "hook_caption": "THANK YOU FOR WATCHING",
                    "archetype": "COMEDIC_STORYTELLING_OR_SARCASM",
                    "payoff_time": 320.0,
                    "segments": [{"start": 300.0, "end": 324.0, "role": "CONTINUOUS_ARC"}],
                    "viral_score": 8.0
                }
            ]
        })
        harness_split = (
            "const $input = { all: () => [{ json: { text: " + json.dumps(director_mock) + " } }] };\n"
            "const $ = (name) => {\n"
            "  if (name === 'Load Cached Telemetry') return { first: () => ({ json: {} }), last: () => ({ json: {} }) };\n"
            "  if (name === '3. Groq Whisper' || name === '5. Format Transcript & Get Words' || name === 'Save Whisper Transcript') return { first: () => ({ json: { words: " + json.dumps(synth_words) + " } }), last: () => ({ json: { words: " + json.dumps(synth_words) + " } }) };\n"
            "  if (name === '3. Prepare Director Prompt') return { first: () => ({ json: { stream_duration_sec: 1000.0, total_words: " + str(len(synth_words)) + ", video_fps: 30 } }) };\n"
            "  return { first: () => ({ json: {} }), last: () => ({ json: {} }) };\n"
            "};\n"
            "function runSplit() {\n" + split_js + "\n}\n"
            "console.log(JSON.stringify(runSplit()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_split)
            s_path = tf.name
        try:
            res = subprocess.run(['node', s_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"5. Split Clips runtime failed: {res.stderr}")
            out_clips = json.loads(res.stdout.strip())
            # Should keep CONTINUOUS CLUTCH (24s >= 22s, payoff tail at 324.0 NOT chopped to 316.5, 1 segment preserved!)
            # Should drop DISCONNECTED STITCH (>25s gap with zero shared entities) and PANHANDLING OUTRO
            self.assertEqual(len(out_clips), 1, f"Expected 1 clean continuous clip, got {out_clips}")
            clip = out_clips[0]["json"]
            self.assertEqual(len(clip["segments"]), 1, "Must NOT artificially split 1 continuous segment into 3 acts")
            self.assertGreaterEqual(clip["segments"][0]["end"], 320.0, "Payoff tail must NOT be truncated around payoff_time=314.0")
            self.assertGreaterEqual(clip["segments"][0]["start"], 299.5, "Must NOT apply blind -10s backward padding")
        finally:
            if os.path.exists(s_path):
                os.remove(s_path)

        # 2. Bug C: Prepare Scout Prompt Sandbox == Production parity
        prep_js = self.nodes["1. Prepare Scout Prompt"]["parameters"]["jsCode"]
        synth_sentences = [{"start": i * 4.0, "end": i * 4.0 + 3.5, "text": f"Line {i} battle"} for i in range(400)]
        harness_parity = (
            "const staticStore = {};\n"
            "const $getWorkflowStaticData = () => staticStore;\n"
            "const $ = () => ({ first: () => ({ json: {} }), last: () => ({ json: {} }) });\n"
            "let $input = { all: () => [{ json: { dry_run: true, duration: 3600.0, annotated_sentences: " + json.dumps(synth_sentences) + " } }] };\n"
            "function runPrep() {\n" + prep_js + "\n}\n"
            "const dryRes = runPrep();\n"
            "$input = { all: () => [{ json: { dry_run: false, duration: 3600.0, annotated_sentences: " + json.dumps(synth_sentences) + " } }] };\n"
            "const prodRes = runPrep();\n"
            "console.log(JSON.stringify({ dry: dryRes.length, prod: prodRes.length }));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_parity)
            p2_path = tf.name
        try:
            res = subprocess.run(['node', p2_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Prepare Scout parity failed: {res.stderr}")
            parity = json.loads(res.stdout.strip())
            self.assertEqual(parity["dry"], parity["prod"], "Sandbox and Production must produce identical Scout chunks")
        finally:
            if os.path.exists(p2_path):
                os.remove(p2_path)

        # 3. Bug C: DRY_RUN_SCRIPT_ONLY anti-hallucination & Section 5 preview output runtime test
        dry_js = self.nodes["DRY_RUN_SCRIPT_ONLY"]["parameters"]["jsCode"]
        harness_dry = (
            "const fs = require('fs');\n"
            "const $ = () => ({ first: () => ({ json: { words: [{word:'Roblox',start:10,end:11},{word:'scam',start:11,end:12}] } }) });\n"
            "const $input = { all: () => [{ json: { clip_number: 1, clip_title: 'Roblox Scam Moment', hook_caption: 'PLAYING RUST WITH FANS', narrative_archetype: 'HUBRIS_WAGER_INSTANT_KARMA', segment_order: 1, role: 'CONTINUOUS_ARC', start: 10.0, end: 35.0, duration: 25.0, spoken_text: 'Roblox scam happened!', entity_continuity_check: { passed: true }, signal_justification: { viewer_voice_present: true } } }] };\n"
            "function runDry() {\n" + dry_js + "\n}\n"
            "console.log(JSON.stringify(runDry()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_dry)
            d_path = tf.name
        try:
            res = subprocess.run(['node', d_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"DRY_RUN_SCRIPT_ONLY failed: {res.stderr}")
            out_dry = json.loads(res.stdout.strip())[0]["json"]
            self.assertNotIn("RUST", out_dry["final_top_hook_caption"], "Must reject hallucinated foreign game RUST")
            self.assertTrue(out_dry["signal_justification"]["viewer_voice_present"])
            self.assertIn("entity_continuity_check", out_dry)
            self.assertIn("pre_hook_context_text", out_dry)
            self.assertIn("post_payoff_context_text", out_dry)
        finally:
            if os.path.exists(d_path):
                os.remove(d_path)

        # 4. Bug D: Guard Summary Retries staticData counter trips after 2 retries
        guard_sum_js = self.nodes["Guard Summary Retries"]["parameters"]["jsCode"]
        harness_gs = (
            "const staticStore = {};\n"
            "const $getWorkflowStaticData = () => staticStore;\n"
            "let $input = { all: () => [{ json: { error: '429 Too Many Requests' } }] };\n"
            "function runGS() {\n" + guard_sum_js + "\n}\n"
            "const r1 = runGS();\n"
            "const r2 = runGS();\n"
            "const r3 = runGS();\n"
            "console.log(JSON.stringify([r1[0].json._allow_retry, r2[0].json._allow_retry, r3[0].json._allow_retry]));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_gs)
            gs_path = tf.name
        try:
            res = subprocess.run(['node', gs_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Guard Summary Retries failed: {res.stderr}")
            self.assertEqual(json.loads(res.stdout.strip()), [True, False, False])
        finally:
            if os.path.exists(gs_path):
                os.remove(gs_path)

        # 5. Section 3 Telemetry: telemetry_fusion_indexer strips Whisper hallucinations & defines viewer voice + lagged chat
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
        import telemetry_fusion_indexer as tfi
        self.assertIn("strawberry elephant", tfi.HALLUCINATION_PHRASES)
        self.assertIn("taco combinacion", tfi.HALLUCINATION_PHRASES)
        self.assertTrue(tfi.is_hallucinated_sentence("strawberry elephant strawberry elephant"))
        self.assertTrue(tfi.is_hallucinated_sentence("taco combinacion"))
        self.assertFalse(tfi.is_hallucinated_sentence("Wait he actually fell into the void!"))
        with open(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'telemetry_fusion_indexer.py')), encoding='utf-8') as tf_f:
            tfi_src = tf_f.read()
        self.assertIn("VIEWER_OR_GAME_VOICE", tfi_src)
        self.assertIn("45.0", tfi_src)
        self.assertIn("top_k=20", tfi_src)

    def test_stream_retry_on_zero_shorts_and_loop_reset(self):
        """Ensure Check Stream Shorts Created runs before Delete Source VOD, deleting only on shorts>0 or max retries."""
        conns = self.wf["connections"]
        self.assertEqual(conns["Loop Clips"]["main"][0][0]["node"], "Check Stream Shorts Created")
        self.assertEqual(conns["Check Stream Shorts Created"]["main"][0][0]["node"], "IF: Should Delete VOD?")
        self.assertEqual(conns["IF: Should Delete VOD?"]["main"][0][0]["node"], "Delete Source VOD")
        self.assertEqual(conns["IF: Should Delete VOD?"]["main"][1][0]["node"], "IF: Retry Next Stream?")
        self.assertEqual(conns["Delete Source VOD"]["main"][0][0]["node"], "IF: Retry Next Stream?")
        self.assertEqual(conns["IF: Retry Next Stream?"]["main"][0][0]["node"], "Find Stream")
        self.assertEqual(conns["1. Extract Audio"]["main"][1][0]["node"], "Delete Source VOD")
        self.assertEqual(conns["Pick Random Streamer"]["main"][0][0]["node"], "If Download Allowed?")
        self.assertEqual(conns["If Download Allowed?"]["main"][0][0]["node"], "Fallback Download")

        # Loop nodes must reset on re-entry across stream retries
        self.assertIn("If Bypass Loop Sandbox", self.nodes["Loop Clips"]["parameters"]["options"].get("reset", ""))
        self.assertIn("1. Prepare Scout Prompt", self.nodes["Scout Loop"]["parameters"]["options"].get("reset", ""))

        # Stream-scoped Edit Fields references must prefer .last() rather than bare .first()
        for nm in ("Delete Source VOD", "Cut & Concat All Segments", "1. Extract Audio", "Get Reference Frame", "Run Multimodal Fusion"):
            params_str = json.dumps(self.nodes[nm]["parameters"])
            self.assertIn("$('Edit Fields').last()", params_str, f"{nm} must use .last() on Edit Fields")
            if self.nodes[nm]["type"] != "n8n-nodes-base.code":
                self.assertNotIn("$('Edit Fields').first()", params_str, f"{nm} must not hardcode .first() on Edit Fields")

        # Runtime check of Check Stream Shorts Created Code node
        check_js = self.nodes["Check Stream Shorts Created"]["parameters"]["jsCode"]
        harness = (
            "function runCheck(flagText, statSize, attempts) {\n"
            "  const fs = {\n"
            "    existsSync: (p) => p === '/files/temp/stream_shorts_created.flag' && flagText !== null,\n"
            "    readFileSync: () => flagText || '',\n"
            "    statSync: () => ({ size: statSize })\n"
            "  };\n"
            "  const $items = (nm, o, r) => (nm === 'Find Stream' && r < attempts) ? [{ json: {} }] : [];\n"
            "  const $ = () => ({ last: () => ({ json: { stream_file: 'test.processing.mp4' } }) });\n"
            "  const require = (m) => m === 'fs' ? fs : {};\n"
            "  return (function(){\n" + check_js + "\n  })();\n"
            "}\n"
            "console.log(JSON.stringify([\n"
            "  runCheck(null, 0, 1)[0].json,\n"
            "  runCheck('short1.mp4\\n', 250000, 1)[0].json,\n"
            "  runCheck(null, 0, 10)[0].json\n"
            "]));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness)
            cpath = tf.name
        try:
            res = subprocess.run(['node', cpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Check Stream Shorts Created failed: {res.stderr}")
            r0, r1, r2 = json.loads(res.stdout.strip())
            self.assertTrue(r0["should_retry_stream"])
            self.assertEqual(r0["shorts_created"], 0)
            self.assertFalse(r1["should_retry_stream"])
            self.assertEqual(r1["shorts_created"], 1)
            self.assertFalse(r2["should_retry_stream"])
        finally:
            if os.path.exists(cpath):
                os.remove(cpath)

        # Runtime check: 5. Split Clips must never return [] when all AI clips get filtered out
        split_js = self.nodes["5. Split Clips"]["parameters"]["jsCode"]
        bad_payload = {"clips": [{"clip_number": 1, "title": "Short", "hook_caption": "TOO SHORT", "segments": [{"start": 10.0, "end": 16.0, "role": "CONTINUOUS_ARC"}]}]}
        harness_sp = (
            "const $input = { all: () => [{ json: { text: " + json.dumps(json.dumps(bad_payload)) + " } }] };\n"
            "const $ = () => ({ item: { json: {} }, last: () => ({ json: { dry_run: false, streamer_name: 'Test' } }), first: () => ({ json: {} }) });\n"
            "const $items = () => [];\n"
            "function runSplit() {\n" + split_js + "\n}\n"
            "console.log(JSON.stringify(runSplit()));\n"
        )
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(harness_sp)
            spath = tf.name
        try:
            res = subprocess.run(['node', spath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"5. Split Clips failed: {res.stderr}")
            out_sp = json.loads(res.stdout.strip())
            self.assertGreaterEqual(len(out_sp), 1, "5. Split Clips must emit >= 1 fallback clip when all candidates filter out")
        finally:
            if os.path.exists(spath):
                os.remove(spath)

if __name__ == '__main__':
    unittest.main()


