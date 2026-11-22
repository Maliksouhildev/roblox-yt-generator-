#!/usr/bin/env python3
"""Strict offline viral discovery, copywriting, and loop-safety evaluator.

Runs against real cached VOD telemetry (/files/temp & /files/inputs or host paths)
plus real director outputs and workflow Node.js stages (5. Split Clips,
6. Extract Viral Segments, Create Subtitle Binary, Write Sidecar JSON).
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if os.path.isdir(os.path.join(ROOT, "scripts")):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
if os.path.isdir("/files"):
    sys.path.insert(0, "/files")

import gta6_peak_storyboard_builder as peak_builder  # noqa: E402
import gta6_vision_director as vision_director  # noqa: E402
import live_stream_chunk_scraper as scraper  # noqa: E402
import multimodal_analyzer as mm_analyzer  # noqa: E402
import telemetry_fusion_indexer as tfi  # noqa: E402

_WF_CANDS = [
    os.path.join(ROOT, "workflows", "gta6_vision_shorts_workflow.json"),
    "/files/workflows/gta6_vision_shorts_workflow.json",
]
WORKFLOW_PATH = next((p for p in _WF_CANDS if os.path.exists(p)), _WF_CANDS[0])

RAW_OPEN_RE = re.compile(
    r"^(?:whoa|woah|huh|yeah|yep|yup|um+|uh+|wait|so|like|well|okay|ok|alright|i\s+mean)\b",
    re.I,
)
ROBOTIC_EVAL_RE = re.compile(
    r"(?:^(?:the\s+)?streamer\s+(?:reflects|tries|attempts|gets|experiences|reacts|breaks\s+down|explains|vents|discusses|shares|claims|is\s+seen)\b|"
    r"\b(?:breaks\s+down|explains\s+(?:his|her|the)|vents\s+about|declares\s+himself)\b|"
    r"bro\s+really\s+said\s+[\"']|right\s+before\s+everything\s+went\s+sideways|"
    r"did\s+you\s+see\s+that\s+coming\s+at|fallback\s+offline\s+mode|watch\s+closely\s+around|"
    r"live\s+gameplay\s+reaction\s+peak(?:\s+around)?|"
    r"^(?:doc|he|she|bro|creator)\s+(?:reflects|explains|vents\s+about|breaks\s+down|discusses)\b)",
    re.I,
)
CRINGE_RE = re.compile(
    r"\b(skibidi|rizz|sigma|gyatt|ohio|fanum\s+tax|no\s+cap|bussin|slay|fam|yeet|epic\s+gaming\s+moment|must\s+watch)\b",
    re.I,
)
SHOUTOUT_OR_HOUSEKEEPING_RE = re.compile(
    r"(gifted\s+\w*\s*premiums|thank\s+you\s+for\s+the\s+\$\d|super\s*chat|welcome\s+to\s+the\s+champions\s+club|"
    r"gifted\s+(?:subs|memberships)|thank\s+you\s+for\s+(?:the\s+raid|subscribing))",
    re.I,
)
DANGLING_TAIL_RE = re.compile(
    r"\b(to|a|an|the|of|in|on|at|for|with|from|by|and|or|but|if|is|are|was|were|my|your|our|their|"
    r"didn't|wasn't|couldn't|wouldn't|shouldn't|haven't|isn't|aren't|doesn't|don't|won't|can't|"
    r"has|had|have|zero|two|three|four|five|ready|just|very|so|too)\s*[.!?]*$",
    re.I,
)


def _resolve_telemetry_dirs(cli_temp: str = "", cli_inputs: str = "") -> tuple[str, str]:
    temp_cands = [cli_temp, "/files/temp", r"C:\Users\mlkme\Desktop\AI_Clipper\temp"]
    in_cands = [cli_inputs, "/files/inputs", r"C:\Users\mlkme\Desktop\AI_Clipper\inputs"]
    t_dir = next((d for d in temp_cands if d and os.path.isdir(d)), "")
    i_dir = next((d for d in in_cands if d and os.path.isdir(d)), "")
    return t_dir, i_dir


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return json.load(f)


def _is_raw_transcript_title(title: str, transcript: str) -> bool:
    s = str(title or "").strip()
    if not s or len(s) < 5:
        return True
    if RAW_OPEN_RE.match(s):
        return True
    toks = [w.lower() for w in re.findall(r"[A-Za-z0-9']+", s)]
    if len(toks) < 3:
        return True
    if transcript:
        f6 = [w.lower() for w in re.findall(r"[A-Za-z0-9']+", transcript)[:6]]
        if len(f6) >= 3:
            cand_s = " ".join(toks)
            f6_s = " ".join(f6)
            if cand_s in f6_s or f6_s.startswith(cand_s):
                return True
    return False


def _is_robotic_or_truncated(clip: dict) -> list[str]:
    issues = []
    title = str(clip.get("title") or "")
    yt = str(clip.get("yt_title") or clip.get("youtube_title") or "")
    hook = str(clip.get("hook_caption") or clip.get("viral_caption") or "")
    desc = str(clip.get("desc_line") or clip.get("short_description") or "")
    comment = str(clip.get("comment_hook") or clip.get("comment_bait_question") or "")
    for field_name, val in (("title", title), ("yt_title", yt), ("hook", hook), ("desc", desc), ("comment", comment)):
        if not val.strip():
            issues.append(f"empty_{field_name}")
            continue
        if ROBOTIC_EVAL_RE.search(val):
            issues.append(f"robotic_{field_name}:{val[:45]}")
        if CRINGE_RE.search(val):
            issues.append(f"cringe_{field_name}:{val[:45]}")
    if hook and DANGLING_TAIL_RE.search(hook):
        issues.append(f"truncated_hook:{hook}")
    return issues


def _run_node_split_and_extract(clips: list, words: list, vod_dur: float, wf: dict, streamer: str = "Tarik") -> tuple[list, list, list]:
    """Run real workflow `5. Split Clips` and `6. Extract Viral Segments` via Node.js."""
    nodes = {n["name"]: n for n in wf["nodes"]}
    split_js = nodes["5. Split Clips"]["parameters"]["jsCode"]
    ext_js = nodes["6. Extract Viral Segments"]["parameters"]["jsCode"]

    with tempfile.TemporaryDirectory() as td:
        split_harness = (
            "const origRequire = require;\n"
            "const fsReal = origRequire('fs');\n"
            "require = (mod) => {\n"
            "  if (mod === 'fs') return {\n"
            "    existsSync: (p) => (p === '/files/temp/clipped_history.json' ? false : fsReal.existsSync(p)),\n"
            "    readFileSync: (p, e) => fsReal.readFileSync(p, e),\n"
            "    writeFileSync: () => {},\n"
            "    appendFileSync: () => {},\n"
            "  };\n"
            "  return origRequire(mod);\n"
            "};\n"
            "const $input = { all: () => [{ json: { text: JSON.stringify(" + json.dumps({"clips": clips}) + ") } }] };\n"
            "const $ = (name) => ({\n"
            "  first: () => ({ json: name === 'Config' ? { duration: " + str(float(vod_dur)) + ", dry_run: true } : (name === 'Resolve Creator Handle' ? { streamer_handle: " + json.dumps(streamer) + " } : {}) }),\n"
            "  last: () => ({ json: name === 'Config' ? { duration: " + str(float(vod_dur)) + ", dry_run: true } : (name === 'Resolve Creator Handle' ? { streamer_handle: " + json.dumps(streamer) + " } : {}) }),\n"
            "});\n"
            "const res = (function() {\n" + split_js + "\n})();\n"
            "console.log(JSON.stringify(res));\n"
        )
        p_sp = os.path.join(td, "split.js")
        with open(p_sp, "w", encoding="utf-8") as f:
            f.write(split_harness)
        r_sp = subprocess.run(["node", p_sp], capture_output=True, text=True, timeout=20)
        if r_sp.returncode != 0:
            raise RuntimeError(f"5. Split Clips failed: {r_sp.stderr}")
        split_items = json.loads(r_sp.stdout)

        extracted = []
        skipped = []
        for idx, it in enumerate(split_items):
            cj = it.get("json") or {}
            if cj.get("_exhausted_vod"):
                continue
            ext_harness = (
                "const origRequire = require;\n"
                "const fsReal = origRequire('fs');\n"
                "require = (mod) => mod === 'fs' ? {\n"
                "  existsSync: (p) => (String(p).includes('unified_timeline_index.json') || String(p).includes('transcript.json')) ? false : fsReal.existsSync(p),\n"
                "  readFileSync: (p, e) => fsReal.readFileSync(p, e),\n"
                "} : origRequire(mod);\n"
                "const _it = { json: " + json.dumps(cj) + " };\n"
                "const $input = { item: _it, all: () => [_it] };\n"
                "const $ = (name) => ({\n"
                "  first: () => ({ json: (name === 'GTA 6 Load Cached Telemetry' || name === 'Save Whisper Transcript') ? { words: " + json.dumps(words) + ", annotated_sentences: [] } : (name === 'Config' ? { duration: " + str(float(vod_dur)) + ", min_clip_dur: 14, max_clip_dur: 38 } : {}) }),\n"
                "  last: () => ({ json: (name === 'GTA 6 Load Cached Telemetry' || name === 'Save Whisper Transcript') ? { words: " + json.dumps(words) + ", annotated_sentences: [] } : (name === 'Config' ? { duration: " + str(float(vod_dur)) + ", min_clip_dur: 14, max_clip_dur: 38 } : {}) }),\n"
                "  item: _it,\n"
                "});\n"
                "const res = (function() {\n" + ext_js + "\n})();\n"
                "console.log(JSON.stringify(res));\n"
            )
            p_ex = os.path.join(td, f"ext_{idx}.js")
            with open(p_ex, "w", encoding="utf-8") as f:
                f.write(ext_harness)
            r_ex = subprocess.run(["node", p_ex], capture_output=True, text=True, timeout=20)
            if r_ex.returncode != 0:
                raise RuntimeError(f"6. Extract Viral Segments crashed: {r_ex.stderr}")
            out_ex = json.loads(r_ex.stdout)
            if not out_ex:
                raise RuntimeError("6. Extract Viral Segments returned [] (loop killer!)")
            if out_ex[0].get("json", {}).get("_skip_clip"):
                skipped.append(out_ex[0]["json"])
                continue
            segs = [{"start": float(x["json"]["start"]), "end": float(x["json"]["end"])} for x in out_ex]
            merged = dict(cj)
            merged["segments"] = segs
            merged["start_time"] = segs[0]["start"]
            merged["end_time"] = segs[-1]["end"]
            merged["total_duration_sec"] = round(sum(s["end"] - s["start"] for s in segs), 2)
            extracted.append(merged)
        return split_items, extracted, skipped


def _has_passive_silent_opening(clip: dict, words: list, audio_info: dict, face_info: dict) -> tuple[bool, str]:
    """Check 0-3s hook energy: require active speech (>=2 words) OR vocal/face spike in [start, start+3.0]."""
    st = float(clip.get("start_time") or (clip.get("segments") or [{}])[0].get("start", 0.0))
    en_hook = st + 3.0
    w_in_3s = [w for w in words if float(w.get("end", 0.0)) >= st and float(w.get("start", 0.0)) <= en_hook]
    raw_bins = (audio_info or {}).get("raw_bins") or {}
    face_scores = (face_info or {}).get("scores") or {}
    max_zdb = max((float((raw_bins.get(sec) or {}).get("z_db", 0.0)) for sec in range(int(st), int(en_hook) + 1)), default=0.0)
    max_zf = max((float(face_scores.get(sec, 0.0)) for sec in range(int(st), int(en_hook) + 1)), default=0.0)
    if len(w_in_3s) >= 2:
        return False, ""
    if max_zdb >= 1.5 or max_zf >= 1.0:
        return False, ""
    return True, f"dead_0_3s(words={len(w_in_3s)}, z_db={max_zdb:.2f}, z_face={max_zf:.2f})"


def _eval_vod_chunk(
    name: str,
    tx_path: str,
    ae_path: str,
    face_path: str,
    wf: dict,
    streamer: str = "Streamer",
    slice_lo: float | None = None,
    slice_hi: float | None = None,
    cached_director_out: dict | None = None,
) -> dict:
    tx_doc = _load_json(tx_path)
    ae_doc = _load_json(ae_path) if ae_path and os.path.exists(ae_path) else {}
    face_doc = _load_json(face_path) if face_path and os.path.exists(face_path) else {}
    words = tx_doc.get("words") or (tx_doc.get("x_groq") or {}).get("words") or []
    dur = float(tx_doc.get("duration") or (words[-1].get("end", 0.0) if words else 3000.0))
    if slice_hi is not None:
        eff_dur = min(dur, float(slice_hi)) - float(slice_lo or 0.0)
    else:
        eff_dur = dur

    audio_info = peak_builder.extract_1s_audio_features("", ae_doc, dur)
    face_info = peak_builder.compute_face_motion_map(face_doc, {"ai_found": bool(face_doc.get("samples"))})
    sents = peak_builder.tag_speaker_roles(peak_builder.build_sentences_from_whisper(tx_doc, {}), audio_info, face_info)
    if slice_lo is not None or slice_hi is not None:
        s0 = float(slice_lo or 0.0)
        s1 = float(slice_hi or dur)
        sents = [s for s in sents if s["end"] >= s0 and s["start"] <= s1]

    _, _, rec_max = peak_builder.get_adaptive_clip_targets(eff_dur)
    cands = peak_builder.extract_top_candidates(
        min(dur, float(slice_hi)) if slice_hi is not None else dur,
        sents,
        audio_info,
        {"scores": {}, "meta": {}},
        face_info,
        top_k=rec_max + 4,
        slice_lo=slice_lo,
        slice_hi=slice_hi,
    )
    filtered_cands = [
        c for c in cands
        if float(c.get("est_virality_10", 0.0)) >= 6.5
        and (int(c.get("multi_beat_count", 0)) >= 2 or float(c.get("heatmap_value", 0.0)) >= 0.55 or float(c.get("est_virality_10", 0.0)) >= 7.0)
    ]

    # Check telemetry health bugs (e.g. silence ratio == 1.0 despite [STREAMER] lines, shoutout leakage)
    telemetry_issues = []
    for c in cands:
        streamer_lines = [ln for ln in (c.get("transcript_lines") or []) if "[STREAMER]" in ln]
        if streamer_lines and float(c.get("streamer_silence_ratio", 0.0)) >= 0.99:
            telemetry_issues.append(f"{c['candidate_id']}:false_silence_1.0")
        if SHOUTOUT_OR_HOUSEKEEPING_RE.search(c.get("raw_text") or ""):
            telemetry_issues.append(f"{c['candidate_id']}:shoutout_leakage")

    meme_files = ["vine-boom-sound-effect_KT89XIq.mp3"]
    if cached_director_out and isinstance(cached_director_out.get("clips"), list):
        norm = vision_director.normalize_director_clips(
            cached_director_out, filtered_cands or cands, meme_files, words=words, max_clips=rec_max, streamer_handle=streamer
        )
    else:
        norm = vision_director.deterministic_candidate_fallback(
            filtered_cands or cands, meme_files, words=words, max_clips=rec_max, streamer_handle=streamer
        )

    split_items, extracted, skipped = _run_node_split_and_extract(norm.get("clips") or [], words, dur, wf, streamer=streamer)

    # Also test Create Subtitle Binary on first extracted clip (with 4s too-short probe for crash check)
    nodes = {n["name"]: n for n in wf["nodes"]}
    csb_js = nodes["Create Subtitle Binary"]["parameters"]["jsCode"]
    loop_crashes = 0
    with tempfile.TemporaryDirectory() as td:
        probe_short = os.path.join(td, "probe_short.js")
        short_harness = (
            "const origRequire = require;\n"
            "require = (mod) => {\n"
            "  if (mod === 'fs') return { existsSync: () => false, readFileSync: () => '{}', writeFileSync: () => {}, mkdirSync: () => {}, unlinkSync: () => {} };\n"
            "  if (mod === 'child_process') return { execSync: (cmd) => /ffprobe/i.test(String(cmd)) ? '4.5' : '' };\n"
            "  return origRequire(mod);\n"
            "};\n"
            "const _it = { json: { text: 'wait', words: [{word:'wait',start:0.1,end:0.4}] } };\n"
            "const $input = { item: _it, first: () => _it, all: () => [_it] };\n"
            "const _clip = { json: { clip_number: 1, duration: 4.5, total_duration: 4.5, segments: [{start:10,end:14.5}], title: 'Test Clip Title', hook_caption: 'Test Hook Line' } };\n"
            "const $ = (n) => ({ first: () => ({ json: {} }), item: _clip, all: () => [_clip], last: () => ({ json: {} }) });\n"
            "console.log(JSON.stringify((function(){\n" + csb_js + "\n})()));\n"
        )
        with open(probe_short, "w", encoding="utf-8") as f:
            f.write(short_harness)
        pr = subprocess.run(["node", probe_short], capture_output=True, text=True, timeout=15)
        if pr.returncode != 0 or not json.loads(pr.stdout)[0].get("json", {}).get("_skip_clip"):
            loop_crashes += 1

    raw_title_fails = []
    copy_fails = []
    silent_open_fails = []
    duplicate_titles = 0
    seen_titles = set()
    sweet_spot_pass = 0
    for cl in extracted:
        txt = cl.get("assembled_spoken_script") or ""
        t_norm = re.sub(r"\s+", " ", str(cl.get("title") or "").strip().lower())
        if t_norm in seen_titles:
            duplicate_titles += 1
        elif t_norm:
            seen_titles.add(t_norm)
        t_vals = [cl.get("title"), cl.get("yt_title"), cl.get("hook_caption")]
        if any(_is_raw_transcript_title(tv or "", txt) for tv in t_vals):
            raw_title_fails.append(f"{cl.get('title')!r} / {cl.get('hook_caption')!r}")
        iss = _is_robotic_or_truncated(cl)
        if iss:
            copy_fails.extend(iss)
        sil_bad, sil_reason = _has_passive_silent_opening(cl, words, audio_info, face_info)
        if sil_bad:
            silent_open_fails.append(f"{cl.get('title')!r}: {sil_reason}")
        tot_d = float(cl.get("total_duration_sec") or 0.0)
        if 14.0 <= tot_d <= 38.0:
            sweet_spot_pass += 1

    return {
        "dataset": name,
        "candidates_total": len(cands),
        "candidates_post_gate": len(filtered_cands),
        "director_clips": len(norm.get("clips") or []),
        "valid_clips": len(extracted),
        "skipped_clips": len(skipped),
        "sweet_spot_pass": sweet_spot_pass,
        "duplicate_titles": duplicate_titles,
        "raw_title_fails": raw_title_fails,
        "copy_fails": copy_fails,
        "silent_open_fails": silent_open_fails,
        "telemetry_issues": telemetry_issues,
        "loop_crashes": loop_crashes,
        "sample_clips": [
            {
                "title": c.get("title"),
                "yt_title": c.get("yt_title"),
                "hook": c.get("hook_caption"),
                "desc": c.get("desc_line"),
                "dur": c.get("total_duration_sec"),
                "virality": c.get("virality_score"),
            }
            for c in extracted[:4]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate viral discovery, copywriting, and loop safety on cached VOD telemetry.")
    parser.add_argument("--temp-dir", default="")
    parser.add_argument("--inputs-dir", default="")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    t_dir, i_dir = _resolve_telemetry_dirs(args.temp_dir, args.inputs_dir)
    if not t_dir:
        print(json.dumps({"error": "Telemetry directory not found"}))
        sys.exit(2)

    wf = _load_json(WORKFLOW_PATH)
    runs = []

    # Dataset A1: Active DrDisRespect chunk telemetry + real cached Gemini Vision Director output
    tx_a = os.path.join(t_dir, "transcript.json")
    ae_a = os.path.join(t_dir, "audio_energy.json")
    fe_a = os.path.join(t_dir, "face_emotions.json")
    dir_a = os.path.join(t_dir, "gta6_vision_director_out.json")
    if os.path.exists(tx_a):
        cached_dir = _load_json(dir_a) if os.path.exists(dir_a) else None
        runs.append(_eval_vod_chunk("A_active_chunk_cached_llm", tx_a, ae_a, fe_a, wf, streamer="DrDisRespect", cached_director_out=cached_dir))
        runs.append(_eval_vod_chunk("A2_active_chunk_deterministic", tx_a, ae_a, fe_a, wf, streamer="DrDisRespect", cached_director_out=None))

    # Dataset B: Mega-VOD 1 chunk [600..3600]
    tx_b = os.path.join(t_dir, "bak_vod1_transcript.json")
    ae_b = os.path.join(t_dir, "bak_vod1_audio_energy.json")
    fe_b = os.path.join(t_dir, "bak_vod1_face_emotions.json")
    if os.path.exists(tx_b):
        runs.append(_eval_vod_chunk("B_vod1_50min_chunk", tx_b, ae_b, fe_b, wf, streamer="KreekCraft", slice_lo=600.0, slice_hi=3600.0))

    # Dataset C: Mega-VOD 2 chunk [300..3300]
    tx_c = os.path.join(t_dir, "whisper_28754.json")
    ae_c = os.path.join(t_dir, "audio_energy_vod2.json")
    fe_c = os.path.join(t_dir, "face_emotions_vod2.json")
    if os.path.exists(tx_c):
        runs.append(_eval_vod_chunk("C_vod2_50min_chunk", tx_c, ae_c, fe_c, wf, streamer="KreekCraft", slice_lo=300.0, slice_hi=3300.0))

    # Dataset C2: Full Gaming VOD chunk (whisper_28888.json)
    tx_d2 = os.path.join(t_dir, "whisper_28888.json")
    if os.path.exists(tx_d2):
        runs.append(_eval_vod_chunk("C2_gaming_vod_chunk", tx_d2, "", "", wf, streamer="KreekCraft"))

    # Dataset D: Adversarial Production Failures (raw filler titles, robotic Doc/Streamer copy, dead 0-3s opening, Rumble shoutout leakage, & Heatmap fusion)
    def _phrase_words(start_t: float, sentence: str, step: float = 0.65) -> list[dict]:
        return [
            {"word": w, "start": round(start_t + i * step, 2), "end": round(start_t + i * step + step - 0.06, 2)}
            for i, w in enumerate(sentence.split())
        ]

    adv_words = (
        [{"word": "hmm", "start": 20.0, "end": 20.3}]  # 5.5s dead opening before 25.8s!
        + _phrase_words(25.8, "Whoa baps are pushing in shit right now lock the back door before they breach through the hallway and flank us bro we are actually cornered")
        + _phrase_words(100.0, "AJ five gifted Rumble premiums thank you for the $5 superchat welcome to the Champions Club appreciate the gifted memberships guys")
        + _phrase_words(200.0, "No way that armored truck just launched over the bridge into the police helicopter mid chase look at the explosion on the water right below us oh my god")
        + _phrase_words(300.0, "Watch me clear this highway ramp jump with five stars behind me easy dub nobody catches me on this bike wait no why did a cop spawn right there")
        + _phrase_words(400.0, "Wait what did that alligator just drag that NPC straight into the swamp grass while he was still talking on the phone oh nah Rockstar actually animated that")
        + _phrase_words(500.0, "Bro the SWAT team just rappelled through the skylight mid interrogation zero warning and three lasers locked straight onto our chest move move move")
    )
    adv_cands = [
        {"candidate_id": "cand_1", "window_start": 18.0, "window_end": 44.0, "peak_time": 34.0, "raw_text": "Whoa baps are pushing in shit right now lock the back door before they breach through the hallway", "signal_tags": ["[VOCAL_SPIKE]"], "streamer_silence_ratio": 0.15, "est_virality_10": 8.4},
        {"candidate_id": "cand_2", "window_start": 198.0, "window_end": 236.0, "peak_time": 216.0, "raw_text": "No way that armored truck just launched over the bridge into the police helicopter mid chase", "signal_tags": ["[HEATMAP_PEAK:val=0.92]"], "streamer_silence_ratio": 0.10, "est_virality_10": 9.1},
        {"candidate_id": "cand_3", "window_start": 298.0, "window_end": 334.0, "peak_time": 316.0, "raw_text": "Watch me clear this highway ramp jump with five stars behind me easy dub nobody catches me", "signal_tags": ["[VOCAL_SPIKE]"], "streamer_silence_ratio": 0.12, "est_virality_10": 8.7},
        {"candidate_id": "cand_4", "window_start": 398.0, "window_end": 436.0, "peak_time": 416.0, "raw_text": "Wait what did that alligator just drag that NPC straight into the swamp grass while he talked", "signal_tags": ["[CROWD_REPLAY]"], "streamer_silence_ratio": 0.10, "est_virality_10": 8.8},
        {"candidate_id": "cand_5", "window_start": 498.0, "window_end": 534.0, "peak_time": 516.0, "raw_text": "Bro the SWAT team just rappelled through the skylight mid interrogation zero warning at all", "signal_tags": ["[VOCAL_SPIKE]"], "streamer_silence_ratio": 0.10, "est_virality_10": 8.9},
    ]
    adv_llm = {
        "clips": [
            {"candidate_id": "cand_1", "title": "Whoa Baps Are Pushing In Shit", "yt_title": "Huh Yeah I Mean If It Gets", "hook_caption": "Whoa baps are pushing", "desc_line": "Doc breaks down the hype and vents about his run.", "comment_hook": "Bro really said whoa", "start_time": 20.0, "end_time": 38.0, "virality_score": 8.4, "narrative_archetype": "OPEN_WORLD_CHAOS_OR_COP_CHASE", "grounding_quote": "lock the back door"},
            {"candidate_id": "cand_2", "title": "Armored Truck Versus Police Chopper", "yt_title": "GTA 6 truck physics sent this chopper flying", "hook_caption": "The anticipation for GTA 6 is real", "desc_line": "Doc explains his theory on Vice City bridge launches.", "comment_hook": "how did that even clear the bridge", "start_time": 200.0, "end_time": 220.0, "virality_score": 9.1, "narrative_archetype": "HUBRIS_WAGER_WASTED_KARMA", "grounding_quote": "launched over the bridge"},
            {"candidate_id": "cand_3", "title": "Five Star Highway Ramp Wipeout", "yt_title": "Bro flexed right before a 5-star crash", "hook_caption": "The ultimate highway police trap", "desc_line": "Streamer reflects on why he opened the ramp boost.", "comment_hook": "instant karma on that ramp jump", "start_time": 300.0, "end_time": 320.0, "virality_score": 8.7, "narrative_archetype": "COMEDIC_BANTER_OR_SARCASM", "grounding_quote": "five stars behind me"},
            {"candidate_id": "cand_4", "title": "Alligator Swamps Vice City NPC", "yt_title": "Leonida wildlife does not play around", "hook_caption": "Leonida gators have zero chill", "desc_line": "An alligator ambushed an NPC mid-conversation near the swamp.", "comment_hook": "Rockstar really coded gator ambushes", "start_time": 400.0, "end_time": 420.0, "virality_score": 8.8, "narrative_archetype": "LEONIDA_NPC_ENCOUNTER_OR_ROAST", "grounding_quote": "alligator just drag"},
            {"candidate_id": "cand_5", "title": "SWAT Crashes Through Skylight", "yt_title": "SWAT breached mid-interrogation in GTA 6", "hook_caption": "SWAT dropped through the roof", "desc_line": "Zero warning before three officers crashed through the glass roof.", "comment_hook": "did anyone expect the skylight breach", "start_time": 500.0, "end_time": 520.0, "virality_score": 8.9, "narrative_archetype": "HOW_TO_TIP_OR_SECRET_DISCOVERY", "grounding_quote": "rappelled through the skylight"},
        ]
    }
    adv_norm = vision_director.normalize_director_clips(adv_llm, adv_cands, ["vine-boom-sound-effect_KT89XIq.mp3"], words=adv_words, max_clips=8, streamer_handle="DrDisRespect")
    _, adv_ext, _ = _run_node_split_and_extract(adv_norm.get("clips") or [], adv_words, 600.0, wf, streamer="DrDisRespect")
    adv_raw_f, adv_copy_f, adv_sil_f, adv_tel_iss, adv_dups = [], [], [], [], 0
    adv_seen_t = set()
    # Check shoutout filter on adv_words
    adv_sents = peak_builder.tag_speaker_roles(peak_builder.build_sentences_from_whisper({"words": adv_words}, {}), {"median_db": -28.0, "raw_bins": {}}, {"enabled": False, "med_mouth": 0.0, "scores": {}, "mouth_by_sec": {}})
    adv_raw_bins = {t: {"db": -30.0, "z_db": 0.0, "spec_boost": 0.0, "audio_score": 0.0} for t in range(600)}
    adv_raw_bins[104] = {"db": -8.0, "z_db": 4.0, "spec_boost": 0.5, "audio_score": 7.0}  # loud superchat shoutout!
    adv_raw_bins[210] = {"db": -10.0, "z_db": 3.5, "spec_boost": 0.4, "audio_score": 5.5}
    adv_cands_chk = peak_builder.extract_top_candidates(600.0, adv_sents, {"median_db": -28.0, "raw_bins": adv_raw_bins}, {"scores": {}, "meta": {}}, {"enabled": False, "scores": {}, "mouth_by_sec": {}}, top_k=5)
    for cc in adv_cands_chk:
        if SHOUTOUT_OR_HOUSEKEEPING_RE.search(cc.get("raw_text") or ""):
            adv_tel_iss.append(f"adv_shoutout_leak:{cc['candidate_id']}")
    adv_sweet = 0
    for cl in adv_ext:
        txt = cl.get("assembled_spoken_script") or ""
        t_norm = re.sub(r"\s+", " ", str(cl.get("title") or "").strip().lower())
        if t_norm in adv_seen_t:
            adv_dups += 1
        elif t_norm:
            adv_seen_t.add(t_norm)
        if any(_is_raw_transcript_title(tv or "", txt) for tv in (cl.get("title"), cl.get("yt_title"), cl.get("hook_caption"))):
            adv_raw_f.append(f"{cl.get('title')!r} / {cl.get('yt_title')!r} / {cl.get('hook_caption')!r}")
        adv_copy_f.extend(_is_robotic_or_truncated(cl))
        sb, sr = _has_passive_silent_opening(cl, adv_words, {"raw_bins": adv_raw_bins}, {"scores": {}})
        if sb:
            adv_sil_f.append(f"{cl.get('title')!r}: {sr}")
        if 14.0 <= float(cl.get("total_duration_sec") or 0.0) <= 38.0:
            adv_sweet += 1
    runs.append({
        "dataset": "D_adversarial_prod_replay",
        "candidates_total": len(adv_cands),
        "candidates_post_gate": len(adv_cands),
        "director_clips": len(adv_norm.get("clips") or []),
        "valid_clips": len(adv_ext),
        "skipped_clips": 0,
        "sweet_spot_pass": adv_sweet,
        "duplicate_titles": adv_dups,
        "raw_title_fails": adv_raw_f,
        "copy_fails": adv_copy_f,
        "silent_open_fails": adv_sil_f,
        "telemetry_issues": adv_tel_iss,
        "loop_crashes": 0,
        "sample_clips": [{"title": c.get("title"), "yt_title": c.get("yt_title"), "hook": c.get("hook_caption"), "desc": c.get("desc_line"), "dur": c.get("total_duration_sec")} for c in adv_ext],
    })

    # Dataset D: Telemetry Fusion Indexer + Heatmap integration check
    with tempfile.TemporaryDirectory() as td:
        hm_info = os.path.join(td, "probe_chunk2.info.json")
        mp4_dummy = os.path.join(td, "probe_chunk2.mp4")
        with open(mp4_dummy, "wb") as f:
            f.write(b"fake")
        with open(hm_info, "w", encoding="utf-8") as f:
            json.dump({
                "id": "probe123",
                "title": "GTA 6 Launch Stream",
                "heatmap": [
                    {"start_time": 3590.0, "end_time": 3620.0, "value": 0.96},
                    {"start_time": 4100.0, "end_time": 4130.0, "value": 0.82},
                ],
                "chunk_start_sec": 3000.0,
                "chunk_end_sec": 6000.0,
            }, f)
        hm_loaded = mm_analyzer.load_youtube_heatmap(mp4_dummy, 3000.0, info_path=hm_info)
        # Check if telemetry_fusion_indexer.build_unified_index supports heatmap/heatmap_path directly
        tfi_has_heatmap = hasattr(tfi, "load_heatmap_peaks")
        tfi_src_path = next((p for p in (os.path.join(ROOT, "scripts", "telemetry_fusion_indexer.py"), "/files/telemetry_fusion_indexer.py") if os.path.exists(p)), "")
        tfi_sig_src = open(tfi_src_path, encoding="utf-8").read() if tfi_src_path else ""
        tfi_uses_heatmap = "HEATMAP_PEAK" in tfi_sig_src
        scraper_compacts_info = hasattr(scraper, "_compact_info_doc")

    total_clips = sum(r["valid_clips"] for r in runs)
    raw_fails = sum(len(r["raw_title_fails"]) for r in runs)
    copy_fails = sum(len(r["copy_fails"]) for r in runs)
    silent_fails = sum(len(r["silent_open_fails"]) for r in runs)
    sweet_pass = sum(r["sweet_spot_pass"] for r in runs)
    tel_issues = sum(len(r["telemetry_issues"]) for r in runs)
    loop_crashes = sum(r["loop_crashes"] for r in runs)
    dup_titles = sum(int(r.get("duplicate_titles", 0)) for r in runs)

    metrics = {
        "datasets_tested": len(runs),
        "total_valid_clips": total_clips,
        "valid_clips_per_chunk_avg": round(total_clips / max(1, len(runs)), 2),
        "valid_clips_per_chunk_min": min((r["valid_clips"] for r in runs), default=0),
        "raw_transcript_title_rate_pct": round((raw_fails / max(1, total_clips)) * 100.0, 2),
        "hallucination_or_robotic_copy_rate_pct": round((copy_fails / max(1, total_clips)) * 100.0, 2),
        "passive_silent_opening_rate_pct": round((silent_fails / max(1, total_clips)) * 100.0, 2),
        "duration_sweet_spot_rate_pct": round((sweet_pass / max(1, total_clips)) * 100.0, 2),
        "duplicate_title_count": dup_titles,
        "telemetry_bug_count": tel_issues,
        "loop_crash_count": loop_crashes,
        "tfi_fuses_heatmap": bool(tfi_has_heatmap and tfi_uses_heatmap),
        "scraper_lightweight_info_json": bool(scraper_compacts_info),
        "heatmap_loader_ok": len(hm_loaded.get("peaks", [])) >= 2,
    }
    metrics["exit_criteria_passed"] = (
        metrics["raw_transcript_title_rate_pct"] == 0.0
        and metrics["hallucination_or_robotic_copy_rate_pct"] == 0.0
        and metrics["passive_silent_opening_rate_pct"] == 0.0
        and metrics["duration_sweet_spot_rate_pct"] == 100.0
        and metrics["valid_clips_per_chunk_min"] >= 5
        and metrics["duplicate_title_count"] == 0
        and metrics["telemetry_bug_count"] == 0
        and metrics["loop_crash_count"] == 0
        and metrics["tfi_fuses_heatmap"]
        and metrics["scraper_lightweight_info_json"]
    )

    report = {"metrics": metrics, "runs": runs}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if metrics["exit_criteria_passed"] else 1)


if __name__ == "__main__":
    main()
