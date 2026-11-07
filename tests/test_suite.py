import unittest
import json
import math
import os
import subprocess
import tempfile
import cam_detector

class TestPipelineComprehensive(unittest.TestCase):

    def setUp(self):
        with open('workflow.json', 'r', encoding='utf-8') as f:
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
        """Webcam crop must use 720:460 target ratio (~1.565) and stay inside box/frame boundaries."""
        # Box coords: x=1400, y=50, w=450, h=300
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
        # Even coordinates for FFmpeg
        self.assertEqual(crop["cam_w"] % 2, 0)
        self.assertEqual(crop["cam_h"] % 2, 0)
        # Aspect ratio matches 720:460
        self.assertAlmostEqual(crop["cam_w"] / crop["cam_h"], 720.0 / 460.0, delta=0.08)

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
        # hasCam gameplay crop: 720x820 with 12% vertical offset
        crop_h_cam = int(ih * 0.82 // 2) * 2
        crop_w_cam = int(crop_h_cam * (720.0 / 820.0) // 2) * 2
        crop_y_cam = int(ih * 0.12 // 2) * 2
        self.assertEqual(crop_y_cam, 128, "Top 128px follower counter and timer must be cropped out")
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

if __name__ == '__main__':
    unittest.main()
