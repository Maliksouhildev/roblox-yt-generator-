#!/usr/bin/env python3
"""Unit and structural verification tests for GTA 6 Viral Shorts Engine (Peak + 3x3 Vision Edition)."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import cam_detector  # noqa: E402
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
        self.assertIs(self.wf["active"], True)
        self.assertFalse(self.nodes_by_name["Schedule Trigger"].get("disabled", False))
        sched_interval = self.nodes_by_name["Schedule Trigger"]["parameters"]["rule"]["interval"][0]
        self.assertEqual(sched_interval.get("expression"), "*/15 * * * *")
        self.assertFalse(self.nodes_by_name["Webhook"].get("disabled", False))
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
        self.assertIn("live_stream_chunk_scraper.py", fd_cmd)
        fs_cmd = self.nodes_by_name["Find Stream"]["parameters"]["command"]
        self.assertIn(".processing.info.json", fs_cmd)
        self.assertIn(".processing.live_chat.json", fs_cmd)
        self.assertIn(".en.live_chat.json", fs_cmd)
        self.assertNotIn("cp -f", fs_cmd)

        # Resolve Creator Handle wired inline after Edit Fields and checks .processing.info.json first
        self.assertEqual(self.conns["Edit Fields"]["main"][0][0]["node"], "Resolve Creator Handle")
        self.assertEqual(self.conns["Resolve Creator Handle"]["main"][0][0]["node"], "Get Reference Frame")
        rch_js = self.nodes_by_name["Resolve Creator Handle"]["parameters"]["jsCode"]
        self.assertLess(rch_js.index(".processing.info.json"), rch_js.index("stem + '.info.json'"))
        self.assertIn("sf + '.info.json'", rch_js)

        cfg_assigns = {
            a["name"]: a["value"]
            for a in self.nodes_by_name["Config"]["parameters"]["assignments"]["assignments"]
        }
        self.assertIn(".processing.info.json", cfg_assigns["streamer_name"])
        self.assertIn(".processing.info.json", cfg_assigns["creator_credit"])
        self.assertIn(".processing.info.json", self.nodes_by_name["Write Sidecar JSON"]["parameters"]["command"])
        self.assertIn(".processing.live_chat.json", self.nodes_by_name["Run Multimodal Fusion"]["parameters"]["command"])
        self.assertIn("GTA 6 Load Cached Telemetry", self.nodes_by_name["1. Global Summary AI"]["parameters"]["text"])

        for wname in ("3. Groq Whisper", "3. Groq Whisper Fallback", "7d. Get Subtitles (SRT)"):
            params = self.nodes_by_name[wname]["parameters"]["bodyParameters"]["parameters"]
            prompt_val = next(p["value"] for p in params if p["name"] == "prompt")
            self.assertIn("Leonida", prompt_val)
            self.assertIn("Vice City", prompt_val)

        csb_js = self.nodes_by_name["Create Subtitle Binary"]["parameters"]["jsCode"]
        self.assertIn("const subY = 1040;", csb_js)
        self.assertIn("const captionY = isSplitCam ? 420 : 145;", csb_js)
        self.assertIn("WASTED", csb_js)
        self.assertIn("$`", csb_js)

        ws_cmd = self.nodes_by_name["Write Sidecar JSON"]["parameters"]["command"]
        self.assertIn("scoreboard.csv", ws_cmd)
        self.assertIn("youtube_shorts", ws_cmd)
        self.assertIn("comment_bait_question", ws_cmd)
        self.assertIn("SPOILER", ws_cmd)
        swt_js = self.nodes_by_name["Save Whisper Transcript"]["parameters"]["jsCode"]
        self.assertIn("GTA6_PROMPT_ECHO_RE", swt_js)
        self.assertTrue(peak_builder._is_whisper_prompt_hallucination("Grand Theft Auto VI, Vice City, Leonida, Lucia"))

        # Strict webcam gate & staged render wiring
        self.assertEqual(self.conns["Parse Cam Config"]["main"][0][0]["node"], "IF: Has Webcam?")
        self.assertEqual(self.conns["IF: Has Webcam?"]["main"][0][0]["node"], "Config")
        self.assertEqual(self.conns["IF: Has Webcam?"]["main"][1][0]["node"], "Delete Source VOD")
        self.assertEqual(self.conns["Fallback Download"]["main"][0][0]["node"], "Wait Before Next Stream")
        self.assertEqual(self.conns["Wait Before Next Stream"]["main"][0][0]["node"], "Find Stream")
        self.assertIn("ABORT_PREGAME_NO_GAMEPLAY", csb_js)
        self.assertIn(".render.mp4", csb_js)
        self.assertIn("stream_shorts_created.flag", ws_cmd)
        self.assertIn("has_webcam", ws_cmd)
        self.assertIn("short_description", ws_cmd)
        self.assertEqual(self.conns["Loop Clips"]["main"][0][0]["node"], "Check Stream Shorts Created")
        self.assertEqual(self.conns["Check Stream Shorts Created"]["main"][0][0]["node"], "IF: Should Delete VOD?")
        self.assertEqual(self.conns["IF: Should Delete VOD?"]["main"][0][0]["node"], "Delete Source VOD")
        self.assertEqual(self.conns["IF: Should Delete VOD?"]["main"][1][0]["node"], "IF: Retry Next Stream?")
        self.assertEqual(self.conns["Delete Source VOD"]["main"][0][0]["node"], "IF: Retry Next Stream?")
        self.assertEqual(self.conns["IF: Retry Next Stream?"]["main"][0][0]["node"], "Find Stream")
        self.assertEqual(self.conns["Pick Random Streamer"]["main"][0][0]["node"], "If Download Allowed?")
        self.assertEqual(self.conns["If Download Allowed?"]["main"][0][0]["node"], "Fallback Download")
        self.assertIn("If Bypass Loop Sandbox", self.nodes_by_name["Loop Clips"]["parameters"]["options"].get("reset", ""))
        del_cmd = self.nodes_by_name["Delete Source VOD"]["parameters"]["command"]
        self.assertIn("$('Edit Fields').last()", del_cmd)
        self.assertIn(".processing.info.json", del_cmd)
        self.assertIn(".processing.live_chat.json", del_cmd)
        self.assertIn(".en.live_chat.json", del_cmd)

    def test_processing_sidecar_and_creator_credit_in_node(self):
        import subprocess
        js_test = r"""
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { execFileSync } = require('child_process');
const wf = JSON.parse(fs.readFileSync('/files/workflows/gta6_vision_shorts_workflow.json', 'utf8'));
const byName = Object.fromEntries(wf.nodes.map(n => [n.name, n]));

const tmpDir = fs.mkdtempSync('/tmp/gta6_wire_');
try {
  const inputsDir = path.join(tmpDir, 'inputs');
  const tempDir = path.join(tmpDir, 'temp');
  fs.mkdirSync(inputsDir, { recursive: true });
  fs.mkdirSync(tempDir, { recursive: true });

  // 1. Test Find Stream + Delete Source VOD against isolated tmpDir
  const stem = 'TypicalGamer_dQw4w9WgXcQ_chunk1';
  fs.writeFileSync(path.join(inputsDir, stem + '.mp4'), 'video-bytes');
  fs.writeFileSync(path.join(inputsDir, stem + '.info.json'), JSON.stringify({ uploader_id: '@TypicalGamer', uploader: 'TypicalGamer' }));
  fs.writeFileSync(path.join(inputsDir, stem + '.en.live_chat.json'), '{"replayChatItemAction":{}}\n');

  const fsCmd = byName['Find Stream'].parameters.command
    .replaceAll('/files/inputs/', inputsDir + '/')
    .replaceAll('/files/temp/', tempDir + '/');
  const procOut = execFileSync('sh', ['-c', fsCmd], { encoding: 'utf8' }).trim();
  assert.strictEqual(procOut, stem + '.processing.mp4');
  assert.strictEqual(fs.existsSync(path.join(inputsDir, stem + '.processing.mp4')), true);
  assert.strictEqual(fs.existsSync(path.join(inputsDir, stem + '.processing.info.json')), true);
  assert.strictEqual(fs.existsSync(path.join(inputsDir, stem + '.processing.live_chat.json')), true);
  assert.strictEqual(fs.existsSync(path.join(inputsDir, stem + '.info.json')), false, '.info.json moved not copied');
  assert.strictEqual(fs.existsSync(path.join(inputsDir, stem + '.en.live_chat.json')), false, '.en.live_chat.json moved');

  const delRaw = byName['Delete Source VOD'].parameters.command
    .replace(/^=/, '')
    .replace("{{ $('Edit Fields').last().json.stream_file }}", procOut)
    .replace('/files/inputs/', inputsDir + '/');
  execFileSync('sh', ['-c', delRaw], { encoding: 'utf8' });
  assert.strictEqual(fs.readdirSync(inputsDir).length, 0, 'Delete Source VOD removes all processing & unrenamed sidecars');

  // 2. Test Resolve Creator Handle + Config + Write Sidecar JSON filename & .processing.info.json extraction
  const rchFn = new Function('$input', '$', 'require', byName['Resolve Creator Handle'].parameters.jsCode);
  const resChunk = rchFn(
    { all: () => [{ json: { stream_file: 'CaseOh__abc_def1234_chunk2.processing.mp4' } }] },
    () => ({ last: () => ({ json: {} }), first: () => ({ json: {} }) }),
    require
  );
  assert.strictEqual(resChunk[0].json.streamer_handle, 'CaseOh_');
  assert.strictEqual(resChunk[0].json.creator_credit, '🎥 @CaseOh_');

  const cfgAssigns = Object.fromEntries(
    byName['Config'].parameters.assignments.assignments.map(a => [a.name, a.value])
  );
  const evalExpr = (expr, $json, nodes, reqFn = require) => {
    const code = String(expr).replace(/^=/, '').replace(/^\{\{/, '').replace(/\}\}$/, '').trim();
    const $ = (nm) => ({ last: () => nodes[nm] || { json: {} }, first: () => nodes[nm] || { json: {} }, item: nodes[nm] || { json: {} } });
    return (new Function('$json', '$', 'require', 'return (' + code + ');'))($json, $, reqFn);
  };
  const cfgNodes = { 'Resolve Creator Handle': resChunk[0], 'Edit Fields': { json: { stream_file: 'CaseOh__abc_def1234_chunk2.processing.mp4' } } };
  assert.strictEqual(evalExpr(cfgAssigns.streamer_name, {}, cfgNodes), 'CaseOh_');
  assert.strictEqual(evalExpr(cfgAssigns.creator_credit, {}, cfgNodes), '🎥 @CaseOh_');

  // Write Sidecar JSON extraction using <stem>.processing.info.json (intercepted to tmpDir)
  const realInputsDir = inputsDir;
  const mockStem = 'MockCreator_xyz98765432_chunk1';
  fs.writeFileSync(path.join(realInputsDir, mockStem + '.processing.info.json'), JSON.stringify({ uploader_id: 'UC1234567890123456789012', uploader: 'DarkViperAU' }));
  const fsProxy = Object.assign({}, fs, {
    existsSync: (p) => fs.existsSync(String(p).startsWith('/files/inputs/') ? path.join(realInputsDir, path.basename(p)) : p),
    readFileSync: (p, enc) => fs.readFileSync(String(p).startsWith('/files/inputs/') ? path.join(realInputsDir, path.basename(p)) : p, enc),
  });
  const reqProxy = (m) => (m === 'fs' ? fsProxy : require(m));
  const sidecarNodes = {
    'Loop Clips': { json: { title: 'Test_Clip', hook_caption: 'INSANE CHASE', short_description: 'Streamer dodges 5 police cruisers cleanly across the bridge.', virality_score: 9.2, stream_file: mockStem + '.processing.mp4', start_time: 10, end_time: 40 } },
    'Resolve Creator Handle': { json: { streamer_handle: 'Streamer', creator_credit: '🎥 @Streamer' } },
    'Edit Fields': { json: { stream_file: mockStem + '.processing.mp4' } },
    'GTA 6 Load Cached Telemetry': { json: {} },
    'Config': { json: { streamer_name: 'malik' } },
    'Parse Cam Config': { json: { ai_found: true, camera_type: 'box', cam_x: 0, cam_y: 540, cam_w: 368, cam_h: 294 } },
  };
  const wsCmd = evalExpr(byName['Write Sidecar JSON'].parameters.command, {}, sidecarNodes, reqProxy);
  // Extract JSON payload written to SIDECAR_EOF
  const mJson = wsCmd.match(/SIDECAR_EOF'\s*>\s*"[^"]+"\n([\s\S]*?)\nSIDECAR_EOF/);
  assert.ok(mJson, 'sidecar JSON block generated');
  const meta = JSON.parse(mJson[1]);
  assert.strictEqual(meta.streamer_handle, 'DarkViperAU');
  assert.strictEqual(meta.creator_credit, '🎥 @DarkViperAU');
  assert.strictEqual(meta.has_webcam, true);
  assert.ok(meta.youtube_description.includes('Streamer dodges 5 police cruisers'), 'Short-specific description preserved');

  // Verify Write Sidecar JSON works WITHOUT require() (real n8n executeCommand expression runtime)
  const noReq = () => { throw new ReferenceError('require is not defined'); };
  const sidecarNodesNoReq = Object.assign({}, sidecarNodes, {
    'Loop Clips': { json: Object.assign({}, sidecarNodes['Loop Clips'].json, { stream_file: 'xqc_321206426716_chunk1.processing.mp4' }) },
    'Edit Fields': { json: { stream_file: 'xqc_321206426716_chunk1.processing.mp4' } },
    'Resolve Creator Handle': { json: { streamer_handle: 'xqc', creator_credit: '🎥 @xqc' } },
  });
  const wsCmdNoReq = evalExpr(byName['Write Sidecar JSON'].parameters.command, {}, sidecarNodesNoReq, noReq);
  assert.ok(typeof wsCmdNoReq === 'string' && wsCmdNoReq.includes('SIDECAR_EOF'), 'must succeed when require() throws inside n8n expression');
  const mJsonNoReq = wsCmdNoReq.match(/SIDECAR_EOF'\s*>\s*"[^"]+"\n([\s\S]*?)\nSIDECAR_EOF/);
  const metaNoReq = JSON.parse(mJsonNoReq[1]);
  assert.strictEqual(metaNoReq.streamer_handle, 'xqc');
  assert.strictEqual(metaNoReq.has_webcam, true);
  console.log('ALL_GTA6_WIRING_SANDBOX_CHECKS_PASSED');
} finally {
  fs.rmSync(tmpDir, { recursive: true, force: true });
}
"""
        proc = subprocess.run(
            ["docker", "exec", "-i", "-e", "NODE_FUNCTION_ALLOW_BUILTIN=*", "ai_clipper-n8n-1", "node", "-"],
            input=js_test,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        self.assertIn("ALL_GTA6_WIRING_SANDBOX_CHECKS_PASSED", proc.stdout)


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
        # Wide 85.0s window: peak at 200 -> w_start = 148.0, covering complete setup + payoff
        self.assertEqual(cands[0]["window_start"], 148.0)
        self.assertGreaterEqual(cands[0]["window_duration"], 75.0)

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

    def test_cam_detector_bottom_left_box_and_motion_filter(self):
        # 1) Bottom-left box (xQc layout): persistent white border enclosing face at (0,540)-(368,834)
        frames = []
        for idx in range(3):
            img = np.zeros((1080, 1920, 3), dtype=np.uint8)
            img[:, :] = (30, 35, 45)
            # Draw webcam box in bottom-left
            cv2.rectangle(img, (0, 540), (368, 834), (240, 240, 240), 3)
            # Realistic head/face movement and lighting variation inside the webcam ROI
            shift = idx * 18
            cv2.circle(img, (215 + idx * 10, 675 + idx * 4), 42, (165 + shift, 140 + shift, 130 + shift), -1)
            cv2.rectangle(img, (185 + idx * 6, 650), (255 + idx * 6, 710), (70 + shift, 90 + shift, 210), -1)
            frames.append(img)

        cluster = {"cx": 220, "cy": 675, "w": 110, "h": 110, "frames": {0, 1, 2}, "is_docked": True}
        has_box, box_coords = cam_detector.find_physical_box_borders(frames, cluster, 1920, 1080)
        self.assertTrue(has_box)
        self.assertIsNotNone(box_coords)
        bx1, by1, bx2, by2 = box_coords
        self.assertLessEqual(bx1, 10)
        self.assertLess(abs(by1 - 540), 15)
        self.assertLess(abs(bx2 - 368), 15)
        self.assertLess(abs(by2 - 834), 15)
        # Active live webcam motion must NOT be flagged as a static PNG
        self.assertFalse(cam_detector.is_static_png_overlay(frames, cluster, 1920, 1080, active_indices={0, 1, 2}))

        # 2) Identical pixels across all frames -> rejected as static PNG overlay
        static_img = frames[0].copy()
        static_frames = [static_img.copy(), static_img.copy(), static_img.copy()]
        self.assertTrue(cam_detector.is_static_png_overlay(static_frames, cluster, 1920, 1080, active_indices={0, 1, 2}))

    def test_part1_part2_longform_auditor_and_gates(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import gta6_edl_auditor as gta6_auditor

        # 1) Verify director strips unspoken clickbait ("Glitch") & transitive verb cutoff ("I LIKE")
        clean_title = vision_director._strip_unspoken_clickbait("Easy 500 Dollar Payout Glitch", "I got 500 bucks what a chap.")
        self.assertNotIn("Glitch", clean_title)
        clean_hook = vision_director._guard_and_format_hook("HE BUCKED ME HARD I LIKE", "He bucked me hard I like that.", "Five Hundred Dollar Payout")
        self.assertLessEqual(len(clean_hook), 28)
        self.assertLessEqual(len(clean_hook.split()), 5)
        self.assertFalse(gta6_auditor.DANGLING_HOOK_END_RE.search(clean_hook))

        # 2) Verify gta6_edl_auditor enforces -25 (<32s), -15 (DANGLING_HOOK_VERB), -15 (clickbait), -20 (weak ending)
        words = [{"word": w, "start": 10.0 + i * 0.4, "end": 10.35 + i * 0.4} for i, w in enumerate(["Bro", "look", "at", "this", "500", "bucks.", "Okay."])]
        w_starts = [w["start"] for w in words]
        bad_clip = {
            "clip_number": 1,
            "title": "500 Dollar Glitch",
            "narrative_archetype": "HUBRIS_WAGER_WASTED_KARMA",
            "final_top_hook_caption": "HE BUCKED ME HARD I LIKE",
            "cause_and_effect_setup": "Short clip without enough narrative arc.",
            "assembled_spoken_script": "Bro look at this 500 bucks. Okay.",
            "visual_event_description": "Streamer looking at phone.",
            "edl_segments": [{"segment_order": 0, "start": 10.0, "end": 24.0, "duration": 14.0, "spoken_text": "Bro look at this 500 bucks. Okay.", "signal_tags_in_window": ["[dB_PEAK:Z=2.5]"]}],
            "total_duration_sec": 14.0,
        }
        rep = gta6_auditor.score_clip(bad_clip, words, w_starts, [], {"game": "GTA 6"})
        self.assertIn("CLIP_TOO_SHORT_UNDER_32S", rep["flags"])
        self.assertIn("DANGLING_HOOK_VERB", rep["flags"])
        self.assertIn("HALLUCINATED_CLICKBAIT_TITLE", rep["flags"])
        self.assertIn("WEAK_MUMBLE_OR_SILENT_ENDING", rep["flags"])
        self.assertIn("SINGLE_SPIKE_NO_STORY_ARC", rep["flags"])
        self.assertEqual(rep["clip_score_95"], 0.0)

        # 3) Verify Create Subtitle Binary throws ABORT_CLIP_TOO_SHORT when clipDur < 32.0
        with open(os.path.join(ROOT, "workflows", "gta6_vision_shorts_workflow.json"), "r", encoding="utf-8") as f:
            wf_doc = json.load(f)
        csb = next(n for n in wf_doc["nodes"] if n["name"] == "Create Subtitle Binary")
        self.assertIn("ABORT_CLIP_TOO_SHORT", csb["parameters"]["jsCode"])
        ws = next(n for n in wf_doc["nodes"] if n["name"] == "Write Sidecar JSON")
        self.assertIn("source_stream_id", ws["parameters"]["command"])
        self.assertIn("vod_start_time", ws["parameters"]["command"])
        self.assertIn("vod_end_time", ws["parameters"]["command"])

    def test_6_shorts_failure_mode_patches(self):
        """Verify all 4 mandatory patch groups across workflow.json, gta6_vision_shorts_workflow.json, and Python scripts."""
        import subprocess
        import subprocess
        import tempfile
        import cv2
        import numpy as np
        import screen_ui_audit as sua

        for wf_rel in ("workflows/workflow.json", "workflows/gta6_vision_shorts_workflow.json"):
            with open(os.path.join(ROOT, wf_rel), "r", encoding="utf-8") as f:
                wf = json.load(f)
            ids = [n["id"] for n in wf["nodes"]]
            names = [n["name"] for n in wf["nodes"]]
            by_n = {n["name"]: n for n in wf["nodes"]}
            # Zero duplicate IDs & zero orphan nodes
            self.assertEqual(len(ids), len(set(ids)), f"{wf_rel} has duplicate node IDs")
            for orphan in ("Prepare Frames", "Read Reference", "Cam Vision Prep", "Cam Vision Call", "Vision Prep", "Groq Vision Analyzer", "If HfFace 429", "Wait HfFace Error", "Restore HfFace Input", "If Groq Vision 429", "Wait Groq Vision Error", "Wait Summary Fallback Error"):
                self.assertNotIn(orphan, names, f"{wf_rel} still contains orphan node {orphan}")

            # 1) Whisper GTA 6 prompt + GTA removed from FOREIGN_GAME_RE + Wait Inside Loop reduced
            for wname in ("3. Groq Whisper", "3. Groq Whisper Fallback", "7d. Get Subtitles (SRT)"):
                params = by_n[wname]["parameters"]["bodyParameters"]["parameters"]
                p_val = next(p["value"] for p in params if p["name"] == "prompt")
                self.assertIn("IShowSpeed", p_val)
                self.assertNotIn("Lucky Blocks", p_val)
            self.assertLessEqual(by_n["Wait Inside Loop"]["parameters"]["amount"], 10)

            csb_js = by_n["Create Subtitle Binary"]["parameters"]["jsCode"]
            self.assertNotIn("|GTA|", csb_js)
            self.assertIn("const subY = 1040;", csb_js)
            self.assertIn("const captionY = isSplitCam ? 420 : 145;", csb_js)
            self.assertIn("if (!useAssHookCaption)", csb_js)
            self.assertNotIn("drawbox", csb_js)
            self.assertNotIn("Auto-inject vine-boom", csb_js)
            self.assertIn("fscx100", csb_js)
            self.assertIn("fscy100", csb_js)
            self.assertNotIn("c_bg_blur", csb_js)
            self.assertNotIn("cam_bordered", csb_js)
            self.assertIn("gameYRatio", csb_js)

            # Fail-closed IF: Screen Clean? & If Summary Fallback 429 distinct branches
            sc_expr = by_n["IF: Screen Clean?"]["parameters"]["conditions"]["conditions"][0]["leftValue"]
            self.assertIn("has_ui_obstruction === false", sc_expr)
            self.assertIn("return false;", sc_expr)
            sf_conns = wf["connections"]["If Summary Fallback 429"]["main"]
            self.assertNotEqual(sf_conns[0][0]["node"], sf_conns[1][0]["node"])

            # Runtime Node.js test of Create Subtitle Binary: overlapping/frozen words, scale reset, no forced vine-boom, smart-fill cam
            harness = (
                "const $input = { first: () => ({ json: { merge_result: { story_hook: 'CRAZY GTA SWAMP CHASE', climax_quote: 'no way bro', reaction_triggers: [5.0], memes: [] } } }) };\n"
                "const nodeMap = {\n"
                "  '7d. Get Subtitles (SRT)': { words: [\n"
                "    { word: 'Wait', start: 0.5, end: 0.9 },\n"
                "    { word: 'bro', start: 0.7, end: 1.1 },\n"
                "    { word: 'what', start: 4.5, end: 4.8 },\n"
                "    { word: 'is', start: 4.82, end: 5.0 },\n"
                "    { word: 'that?!', start: 5.02, end: 5.4 }\n"
                "  ] },\n"
                "  'Parse Cam Config': { ai_found: true, cam_w: 360, cam_h: 240, cam_x: 0, cam_y: 540, avatar_row_detected: true },\n"
                "  'Get Meme List': { stdout: 'vine-boom-sound-effect_KT89XIq.mp3\\n---DIMENSIONS---\\n1920x1080' },\n"
                "  'Loop Clips': { title: 'GTA6_Peak_Clip_1', hook_caption: 'WHY IS IT DROPPING COKE', start_time: 10, end_time: 48, payoff_time: 44, segments: [{ start: 10, end: 48 }], assembled_spoken_script: 'Wait bro what is that in GTA 6 swamp!' }\n"
                "};\n"
                "const $ = (nm) => ({ item: { json: nodeMap[nm] || {} }, last: () => ({ json: nodeMap[nm] || {} }), first: () => ({ json: nodeMap[nm] || {} }) });\n"
                "const origReq = require;\n"
                "require = (m) => m === 'child_process' ? { execSync: () => '38.0' } : (m === 'fs' ? { existsSync: () => false, writeFileSync: () => {}, mkdirSync: () => {} } : origReq(m));\n"
                "const out = (function(){\n" + csb_js + "\n})();\n"
                "const ass = Buffer.from(out[0].binary.data.data, 'base64').toString('utf8');\n"
                "console.log(JSON.stringify({ cmd: out[0].json.command, hook: out[0].json.resolved_hook, stem: out[0].json.resolved_stem, ass }));\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
                tf.write(harness)
                tpath = tf.name
            try:
                res = subprocess.run(["node", tpath], capture_output=True, text=True, timeout=15)
                self.assertEqual(res.returncode, 0, f"Node runtime failed for {wf_rel}: {res.stderr}")
                out_obj = json.loads(res.stdout.strip().splitlines()[-1])
                self.assertNotIn("vine-boom", out_obj["cmd"], "Must NOT force vine-boom when memes=[]")
                self.assertIn("trunc(ih*0.20/2)*2", out_obj["cmd"], "gameYRatio=0.20 must be interpolated when avatar_row_detected=true")
                self.assertNotIn("GTA6_Peak_Clip_1", out_obj["stem"], "Internal fallback filename must be rejected")
                self.assertNotIn("COKE", out_obj["hook"], "Brand-unsafe keyword COKE must be scrubbed")
                # Check ASS Dialogue: 1 lines are strictly non-overlapping, bounded across 3.4s pause, and reset scale
                d1_lines = [ln for ln in out_obj["ass"].splitlines() if ln.startswith("Dialogue: 1,")]
                self.assertGreaterEqual(len(d1_lines), 4)
                prev_end = -1.0
                for ln in d1_lines:
                    parts = ln.split(",", 9)
                    def _to_sec(tc):
                        h, m, s = tc.split(":")
                        return int(h) * 3600 + int(m) * 60 + float(s)
                    s_t, e_t = _to_sec(parts[1]), _to_sec(parts[2])
                    self.assertGreater(e_t, s_t)
                    self.assertLessEqual(e_t - s_t, 1.5, f"Frozen subtitle detected across pause: {ln}")
                    self.assertGreaterEqual(s_t + 0.005, prev_end, f"Overlapping ASS lines: {prev_end} vs {s_t}")
                    self.assertIn(r"\fscx100\fscy100}", parts[9])
                    prev_end = e_t
            finally:
                if os.path.exists(tpath):
                    os.remove(tpath)

        # Verify screen_ui_audit local OpenCV heuristic flags black loading screens AND EULA warning text walls
        with tempfile.TemporaryDirectory() as td:
            black_frames = []
            for idx in range(4):
                p = os.path.join(td, f"blk_{idx}.jpg")
                cv2.imwrite(p, np.zeros((360, 640, 3), dtype=np.uint8))
                black_frames.append((idx, p))
            hb = sua.local_nsfw_and_static_heuristic(black_frames)
            self.assertTrue(hb["is_black_or_solid_loading"])

            eula_frames = []
            for idx in range(4):
                img = np.full((360, 640, 3), 12, dtype=np.uint8)
                for row_y in range(85, 280, 20):
                    cv2.putText(img, "EPILEPSY WARNING: READ BEFORE PLAYING GTA 6 EULA", (110, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (235, 235, 235), 1)
                p = os.path.join(td, f"eula_{idx}.jpg")
                cv2.imwrite(p, img)
                eula_frames.append((idx, p))
            he = sua.local_nsfw_and_static_heuristic(eula_frames)
            self.assertTrue(he["is_eula_or_warning_text"])

        # Verify brand-safe & memes=[] preservation in gta6_vision_director.py
        norm_empty = vision_director.normalize_director_clips(
            {"clips": [{"candidate_id": "cand_1", "title": "Boat Chase", "hook_caption": "WHY IS IT DROPPING COKE", "start_time": 100.0, "end_time": 140.0, "memes": []}]},
            [{"candidate_id": "cand_1", "window_start": 95.0, "window_end": 150.0, "peak_time": 132.0, "raw_text": "Look at this wild boat chase through the swamp in Vice City!"}],
            ["vine-boom-sound-effect_KT89XIq.mp3"],
        )
        self.assertEqual(norm_empty["clips"][0]["memes"], [])
        self.assertNotIn("COKE", norm_empty["clips"][0]["hook_caption"])

    def test_divider_badge_hook_caption_runtime(self):
        """Verify Option B divider-badge seam banner (y=380 split-cam, y=145 vertical/no-cam, 2-line wrap, Remotion mutual exclusion, subY=900)."""
        import subprocess
        import subprocess
        import tempfile

        for wf_rel in ("workflows/gta6_vision_shorts_workflow.json", "workflows/workflow.json"):
            with open(os.path.join(ROOT, wf_rel), "r", encoding="utf-8") as f:
                wf = json.load(f)
            csb_js = next(n for n in wf["nodes"] if n["name"] == "Create Subtitle Binary")["parameters"]["jsCode"]

            def _run_case(hook_txt, has_cam=True, dims="1920x1080"):
                harness = (
                    "let remotionCalled = false;\n"
                    f"const $input = {{ first: () => ({{ json: {{ merge_result: {{ story_hook: {json.dumps(hook_txt)}, climax_quote: 'no way', reaction_triggers: [], memes: [] }} }} }}) }};\n"
                    "const nodeMap = {\n"
                    "  '7d. Get Subtitles (SRT)': { words: [{ word: 'No', start: 1.0, end: 1.2 }, { word: 'way!', start: 1.25, end: 1.5 }] },\n"
                    f"  'Parse Cam Config': {{ ai_found: {'true' if has_cam else 'false'}, cam_w: 360, cam_h: 240, cam_x: 0, cam_y: 540, avatar_row_detected: false }},\n"
                    f"  'Get Meme List': {{ stdout: 'vine-boom-sound-effect_KT89XIq.mp3\\n---DIMENSIONS---\\n{dims}' }},\n"
                    f"  'Loop Clips': {{ title: 'Vice City Chase', hook_caption: {json.dumps(hook_txt)}, start_time: 10, end_time: 48, payoff_time: 44, segments: [{{ start: 10, end: 48 }}], assembled_spoken_script: 'No way this Vice City chase just happened in GTA 6!' }}\n"
                    "};\n"
                    "const $ = (nm) => ({ item: { json: nodeMap[nm] || {} }, last: () => ({ json: nodeMap[nm] || {} }), first: () => ({ json: nodeMap[nm] || {} }) });\n"
                    "const origReq = require;\n"
                    "require = (m) => m === 'child_process' ? { execSync: (cmd) => { if (String(cmd).includes('remotion-server')) remotionCalled = true; return '38.0'; } } : (m === 'fs' ? { existsSync: () => false, writeFileSync: () => {}, mkdirSync: () => {} } : origReq(m));\n"
                    "const out = (function(){\n" + csb_js + "\n})();\n"
                    "const ass = Buffer.from(out[0].binary.data.data, 'base64').toString('utf8');\n"
                    "console.log(JSON.stringify({ cmd: out[0].json.command, ass, remotionCalled }));\n"
                )
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
                    tf.write(harness)
                    tp = tf.name
                try:
                    res = subprocess.run(["node", tp], capture_output=True, text=True, timeout=15)
                    self.assertEqual(res.returncode, 0, f"{wf_rel} failed: {res.stderr}")
                    return json.loads(res.stdout.strip().splitlines()[-1])
                finally:
                    if os.path.exists(tp):
                        os.remove(tp)

            # 1) Single-line split-cam hook (<=28 chars) + zero drawbox + mixed-case + yellow highlight + subY=1040 + y=420 seam
            c1 = _run_case("GTA 6 INFLUENCERS ARE INSANE 😱", has_cam=True, dims="1920x1080")
            self.assertFalse(c1["remotionCalled"], "Remotion must be bypassed when ASS ViralCaption is active")
            self.assertIn("Style: ViralSubs,Lilita One,48,&HFFFFFF&,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,20,20,240,1", c1["ass"])
            self.assertIn("Style: ViralCaption,Lilita One,42,&HFFFFFF&,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,40,40,0,1", c1["ass"])
            d1_cap = [ln for ln in c1["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertIn(r"{\q2\pos(360,420)}", d1_cap)
            self.assertIn("GTA 6", d1_cap)
            self.assertIn(r"{\c&H00E5FF&}influencers{\c&HFFFFFF&}", d1_cap)
            self.assertIn(r"{\c&H00E5FF&}insane{\c&HFFFFFF&}", d1_cap)
            self.assertNotIn("😱", d1_cap)
            self.assertNotIn(r"\N", d1_cap)
            self.assertIn(r"{\pos(360,1040)}", c1["ass"])
            self.assertIn("vstack=inputs=2[base]", c1["cmd"])
            self.assertNotIn("drawbox", c1["cmd"])

            # 2) Two-line split-cam hook (29..40 chars) -> fontSize=34, flush seam, zero drawbox
            c2 = _run_case("INSANE SIX STAR POLICE CHASE THROUGHOUT", has_cam=True, dims="1920x1080")
            self.assertIn("Style: ViralCaption,Lilita One,34,&HFFFFFF&,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,40,40,0,1", c2["ass"])
            d2_line = [ln for ln in c2["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertIn(r"{\q2\pos(360,420)}", d2_line)
            self.assertIn(r"\N", d2_line)
            self.assertNotIn("drawbox", c2["cmd"])

            # 3) Dangling word & transitive verb stripped + apostrophes preserved ("I've" stays "I've")
            c_dang = _run_case("INSANE SIX STAR POLICE CHASE HAPPENED IN THE", has_cam=True, dims="1920x1080")
            d_dang = [ln for ln in c_dang["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertNotIn(r"\Nthe", d_dang.lower())
            self.assertFalse(d_dang.lower().endswith(" in"))
            self.assertFalse(d_dang.lower().endswith(" the"))

            c_apos = _run_case("I've never seen cops this cooked", has_cam=True, dims="1920x1080")
            d_apos = [ln for ln in c_apos["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertIn("I've", d_apos)

            c_verb = _run_case("Bro really said I absolutely despise", has_cam=True, dims="1920x1080")
            d_verb = [ln for ln in c_verb["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertFalse(d_verb.lower().endswith("despise"))

            # 4) Vertical / no-cam mode -> captionY = 175
            c3 = _run_case("SIX STAR COPS IN GTA", has_cam=False, dims="720x1280")
            d3_cap = [ln for ln in c3["ass"].splitlines() if ln.startswith("Dialogue: 2,")][0]
            self.assertIn(r"{\q2\pos(360,175)}", d3_cap)
            self.assertIn("GTA", d3_cap)

    def test_progressive_subtitles_silence_clamp_and_natural_sidecar(self):
        """Verify progressive word reveal, leading-silence forward clamp, anti-cringe Sentence case, and 4-block youtubeDescription."""
        import subprocess
        import tempfile
        for wf_rel in ["workflows/gta6_vision_shorts_workflow.json", "workflows/workflow.json"]:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            with open(os.path.join(repo_root, wf_rel), encoding="utf-8") as f:
                wf_obj = json.load(f)
            nodes_map = {n["name"]: n for n in wf_obj["nodes"]}
            cs_code = nodes_map["Create Subtitle Binary"]["parameters"]["jsCode"]

            # 1) Progressive reveal + leading-silence forward clamp
            harness = (
                "const $input = { first: () => ({ json: { words: ["
                "  { word: 'Wait', start: 0.0, end: 2.0 },"
                "  { word: 'what', start: 2.05, end: 2.35 },"
                "  { word: 'bro', start: 2.40, end: 2.70 }"
                "] } }) };\n"
                "const $ = (name) => ({\n"
                "  item: { json: name === 'Loop Clips' ? { title: 'Test', hook_caption: 'GTA 6 cops have skibidi zero chill', start_time: 0, end_time: 48, segments: [{start:0,end:48}] } : {} },\n"
                "  last: () => ({ json: name === 'Parse Cam Config' ? { ai_found: true, cam_w: 400, cam_h: 250, cam_x: 0, cam_y: 0 } : {} })\n"
                "});\n"
                "const out = (function() {\n"
                + cs_code
                + "\n})();\nconsole.log(JSON.stringify({ ass: Buffer.from(out[0].binary.data.data, 'base64').toString('utf8') }));\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
                tf.write(harness)
                tp = tf.name
            try:
                res = subprocess.run(["node", tp], capture_output=True, text=True, timeout=15)
                self.assertEqual(res.returncode, 0, f"{wf_rel} progressive harness failed: {res.stderr}")
                ass_out = json.loads(res.stdout.strip().splitlines()[-1])["ass"]
                sub_lines = [ln for ln in ass_out.splitlines() if ln.startswith("Dialogue: 1,")]
                self.assertEqual(len(sub_lines), 3, f"Expected 3 progressive lines, got: {sub_lines}")
                # First word 'Wait' had 2.0s Whisper stretch -> clamped forward toward 2.0s (start >= 1.68s, NOT 0:00:00.00!)
                self.assertNotIn("0:00:00.00", sub_lines[0], "Early Whisper silence stretch must be clamped forward")
                # Progressive reveal: line 0 has only WAIT, line 1 has WAIT + WHAT, line 2 has WAIT + WHAT + BRO
                self.assertIn("WAIT", sub_lines[0])
                self.assertNotIn("WHAT", sub_lines[0])
                self.assertIn("WHAT", sub_lines[1])
                self.assertNotIn("BRO", sub_lines[1])
                self.assertIn("BRO", sub_lines[2])
                # Anti-cringe Sentence case on ViralCaption
                cap_line = [ln for ln in ass_out.splitlines() if ln.startswith("Dialogue: 2,")][0]
                self.assertIn("GTA 6", cap_line)
                self.assertNotIn("skibidi", cap_line.lower())
            finally:
                if os.path.exists(tp):
                    os.remove(tp)

            # 2) Write Sidecar JSON 4-block description (no globalSummary dump) + custom yt_title/desc_line/comment_hook
            sidecar_expr = nodes_map["Write Sidecar JSON"]["parameters"]["command"].strip()
            self.assertTrue(sidecar_expr.startswith("={{") and sidecar_expr.endswith("}}"))
            js_body = sidecar_expr[3:-2].strip()
            sidecar_harness = (
                "const $ = (name) => ({\n"
                "  item: { json: name === 'Loop Clips' ? { title: 'Police Chase', hook_caption: 'GTA 6 cops have zero chill', start_time: 10, end_time: 48, segments: [{start:10,end:48}] } : (name === 'Normalize Merge Output' ? { merge_result: { yt_title: 'xQc folded the second GTA 6 cops pulled up', desc_line: 'Bro talked crazy for two seconds and got boxed in.', comment_hook: 'scale of 1-10 how cooked was he here' } } : {}) },\n"
                "  last: () => ({ json: name === '1. Global Summary AI' ? { output: JSON.stringify({ game: 'GTA 6', global_summary: 'LONG_GLOBAL_SUMMARY_SHOULD_NOT_APPEAR' }) } : {} })\n"
                "});\n"
                f"const cmd = {js_body};\n"
                "const m = cmd.match(/SIDECAR_EOF['\"]?\\s*>\\s*\"[^\"]+\"\\n([\\s\\S]*?)\\nSIDECAR_EOF/);\n"
                "console.log(m[1]);\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
                tf.write(sidecar_harness)
                tp2 = tf.name
            try:
                res2 = subprocess.run(["node", tp2], capture_output=True, text=True, timeout=15)
                self.assertEqual(res2.returncode, 0, f"{wf_rel} sidecar harness failed: {res2.stderr}")
                meta = json.loads(res2.stdout)
                self.assertEqual(meta["youtube_title"], "xQc folded the second GTA 6 cops pulled up")
                self.assertNotIn("LONG_GLOBAL_SUMMARY_SHOULD_NOT_APPEAR", meta["youtube_description"])
                self.assertIn("Bro talked crazy for two seconds and got boxed in.", meta["youtube_description"])
                self.assertIn("scale of 1-10 how cooked was he here", meta["youtube_description"])
                self.assertEqual(len(meta["youtube_description"].split("\n\n")), 4)
            finally:
                if os.path.exists(tp2):
                    os.remove(tp2)

    def test_dynamic_layout_timeline_transitions_and_quality_gates(self):
        """Verify FULLSCREEN_CAM duplicate-head prevention, SPLIT_PIP->FULLSCREEN_CAM->SPLIT_PIP transitions, virality>=6.8 gate, and trailing silence trim."""
        import subprocess
        import tempfile
        import sys
        import cv2
        import numpy as np

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        sys.path.insert(0, os.path.join(repo_root, "scripts"))
        import clip_layout_timeline as clt

        # 1) FULLSCREEN_CAM classification when face is large & centered -> zero duplicate heads (cam_box=None, caption_y=175)
        with tempfile.TemporaryDirectory() as td:
            vid_path = os.path.join(td, "fullcam.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            vw = cv2.VideoWriter(vid_path, fourcc, 10.0, (480, 270))
            for _ in range(30):
                frame = np.zeros((270, 480, 3), dtype=np.uint8)
                # Large centered skin-toned face region (BGR) covering > 22% height
                cv2.rectangle(frame, (180, 40), (300, 190), (140, 170, 210), -1)
                vw.write(frame)
            vw.release()
            res_lt = clt.analyze_video_layout(vid_path)
            self.assertGreaterEqual(len(res_lt["segments"]), 1)
            self.assertEqual(res_lt["segments"][0]["mode"], "FULLSCREEN_CAM")
            self.assertIsNone(res_lt["segments"][0]["cam_box"])
            self.assertEqual(res_lt["segments"][0]["caption_y"], 175)

        # 2) Mid-clip transition SPLIT_PIP -> FULLSCREEN_CAM -> SPLIT_PIP in Create Subtitle Binary
        with open(os.path.join(repo_root, "workflows/gta6_vision_shorts_workflow.json"), encoding="utf-8") as f:
            wf_obj = json.load(f)
        nodes_map = {n["name"]: n for n in wf_obj["nodes"]}
        cs_code = nodes_map["Create Subtitle Binary"]["parameters"]["jsCode"]

        # Inject a mocked /files/temp/layout_timeline.json via fs.readFileSync interception in Node
        timeline_mock = {
            "clip_duration": 36.0,
            "width": 1920,
            "height": 1080,
            "segments": [
                {"start": 0.0, "end": 12.0, "mode": "SPLIT_PIP", "cam_box": [20, 20, 380, 240], "face_cx": 0.12, "caption_y": 420},
                {"start": 12.0, "end": 24.0, "mode": "FULLSCREEN_CAM", "cam_box": None, "face_cx": 0.50, "caption_y": 175},
                {"start": 24.0, "end": 36.0, "mode": "SPLIT_PIP", "cam_box": [20, 20, 380, 240], "face_cx": 0.12, "caption_y": 420},
            ],
        }
        harness = (
            "const fs = require('fs');\n"
            "const origRead = fs.readFileSync;\n"
            f"fs.readFileSync = function(p, enc) {{ if (String(p).includes('layout_timeline.json')) return {json.dumps(json.dumps(timeline_mock))}; return origRead.apply(fs, arguments); }};\n"
            "const $input = { first: () => ({ json: { words: [{ word: 'Look', start: 0.5, end: 0.9 }, { word: 'chat', start: 1.0, end: 1.4 }] } }) };\n"
            "const $ = (name) => ({\n"
            "  item: { json: name === 'Loop Clips' ? { title: 'Transition Test', hook_caption: 'GTA 6 cops have zero chill', start_time: 0, end_time: 36, segments: [{start:0,end:36}], virality_score: 8.8 } : {} },\n"
            "  last: () => ({ json: name === 'Parse Cam Config' ? { ai_found: true, cam_x: 20, cam_y: 20, cam_w: 380, cam_h: 240 } : {} })\n"
            "});\n"
            "const out = (function() {\n" + cs_code + "\n})();\n"
            "console.log(JSON.stringify({ cmd: out[0].json.command, ass: Buffer.from(out[0].binary.data.data, 'base64').toString('utf8') }));\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
            tf.write(harness)
            tp = tf.name
        try:
            r = subprocess.run(["node", tp], capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, f"Transition harness failed: {r.stderr}")
            out = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertIn("concat=n=3:v=1:a=0[base]", out["cmd"])
            self.assertIn("vstack=inputs=2[segout0]", out["cmd"])
            self.assertNotIn("vstack=inputs=2[segout1]", out["cmd"])
            self.assertIn("vstack=inputs=2[segout2]", out["cmd"])
            cap_lines = [ln for ln in out["ass"].splitlines() if ln.startswith("Dialogue: 2,")]
            self.assertEqual(len(cap_lines), 3)
            self.assertIn(r"\pos(360,420)", cap_lines[0])
            self.assertIn(r"\pos(360,175)", cap_lines[1])
            self.assertIn(r"\pos(360,420)", cap_lines[2])
        finally:
            if os.path.exists(tp):
                os.remove(tp)

        # 3) Hard virality_score < 6.8 rejection & 42s max duration in 5. Split Clips + gta6_vision_director.py
        split_code = nodes_map["5. Split Clips"]["parameters"]["jsCode"]
        self.assertIn("virality_score || 0) >= 6.8", split_code)
        ext_code = nodes_map["6. Extract Viral Segments"]["parameters"]["jsCode"]
        self.assertIn("silTail > 1.5", ext_code)
        self.assertIn("totalClipDur > 42.0", ext_code)


if __name__ == "__main__":
    unittest.main()
