#!/usr/bin/env python3
"""Benchmark & autonomous evaluator for Dead-Spot Jump Cuts & Subtitle Sync.

Tests real GTA 6 clips, runs Groq Whisper word timestamps (cached by media hash),
executes workflow Create Subtitle Binary ASS generation, and measures:
  - dead_air_ratio_pct (< 6%)
  - jump_cuts_applied (2-7 per 30s clip, 0 choppy <1.2s shards)
  - median_subtitle_onset_error_ms (<= 55ms) & early_words_gt150ms (== 0)
  - audio_av_sync_drift_ms (<= 40ms)
  - zero_overlapping_ass_events (True) & zero_emoji_tofu (True)
"""

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import struct
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if os.path.isdir(os.path.join(ROOT, "scripts")):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
if os.path.isdir("/files"):
    sys.path.insert(0, "/files")

_WF_CANDS = [
    os.path.join(ROOT, "workflows", "gta6_vision_shorts_workflow.json"),
    "/files/workflows/gta6_vision_shorts_workflow.json",
]
WORKFLOW_PATH = next((p for p in _WF_CANDS if os.path.exists(p)), _WF_CANDS[0])

DEFAULT_TEST_CLIPS = [
    "/files/outputs/Vice City Skyline Fast Climb.mp4",
    "/files/outputs/Dual Bike Ride Human Statue Encounter.mp4",
    "/files/outputs/GTA 6 Cops Are Relentless.mp4",
    "/files/outputs/Zero Escape From Vice PD.mp4",
]

EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def _ffprobe_av_durations(mp4_path: str) -> tuple[float, float]:
    v_out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
        text=True,
    ).strip()
    a_out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
        text=True,
    ).strip()
    return float(v_out), float(a_out)


def _compute_vocal_band_rms(media_path: str, bandpass: bool = True) -> dict:
    """Compute 20ms frame RMS dB sequence via FFmpeg (optionally 300-3400Hz vocal bandpass)."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", media_path, "-vn"]
    if bandpass:
        cmd.extend(["-af", "highpass=f=300,lowpass=f=3400"])
    cmd.extend(["-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"])
    pcm = subprocess.check_output(cmd)
    samples = struct.unpack("<" + str(len(pcm) // 2) + "h", pcm)
    step = 320  # 20ms @ 16kHz
    rms_db = []
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        if not chunk:
            continue
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        rms_db.append(round(20.0 * math.log10(max(1e-5, rms)), 2))
    s_rms = sorted(rms_db) if rms_db else [-55.0]
    p25 = s_rms[len(s_rms) // 4]
    thresh = round(max(-40.0, min(-26.0, p25 + 6.5)), 2)
    return {"frame_ms": 20, "threshold_db": thresh, "p25_db": round(p25, 2), "rms_db": rms_db}


def _compute_2fps_motion(mp4_path: str) -> tuple[list[tuple[float, float]], list[tuple[float, float]], float, float]:
    """Fast sequential FFmpeg pipe 2fps cam & gameplay pixel MAE series."""
    import numpy as np
    v_dur, _ = _ffprobe_av_durations(mp4_path)
    out = subprocess.check_output(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp4_path, "-vf", "fps=2,scale=180:320:flags=fast_bilinear", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    )
    frame_sz = 180 * 320
    n_frames = len(out) // frame_sz
    cam_diffs, game_diffs = [], []
    prev_cam, prev_game = None, None
    for idx in range(n_frames):
        arr = np.frombuffer(out[idx * frame_sz:(idx + 1) * frame_sz], dtype=np.uint8).reshape((320, 180)).astype(np.float32)
        cam_roi = arr[:105, :]
        game_roi = arr[105:295, :]
        if prev_cam is not None:
            t = round(idx * 0.5, 2)
            cam_diffs.append((t, round(float(np.mean(np.abs(cam_roi - prev_cam))), 2)))
            game_diffs.append((t, round(float(np.mean(np.abs(game_roi - prev_game))), 2)))
        prev_cam = cam_roi
        prev_game = game_roi
    cam_med = float(statistics.median([x[1] for x in cam_diffs])) if cam_diffs else 2.5
    game_med = float(statistics.median([x[1] for x in game_diffs])) if game_diffs else 18.0
    return cam_diffs, game_diffs, cam_med, game_med


def _measure_dead_air_ratio(mp4_path: str, rms_info: dict) -> float:
    """Percentage of clip duration in >1.0s silent pauses with low gameplay & cam motion."""
    v_dur, _ = _ffprobe_av_durations(mp4_path)
    cam_diffs, game_diffs, cam_med, game_med = _compute_2fps_motion(mp4_path)
    rms_db = rms_info["rms_db"]
    thresh = rms_info["threshold_db"]
    # Map 0.5s bins
    n_bins = max(1, int(math.floor(v_dur / 0.5)))
    dead_bins = []
    cam_map = {int(round(t * 2)): v for t, v in cam_diffs}
    game_map = {int(round(t * 2)): v for t, v in game_diffs}
    cam_cap = max(3.0, cam_med * 1.10)
    game_cap = max(22.0, game_med * 1.15)
    for b in range(n_bins):
        f0 = int(b * 25)
        f1 = min(len(rms_db), f0 + 25)
        slice_rms = rms_db[f0:f1]
        is_sil = (not slice_rms) or (sum(1 for x in slice_rms if x >= thresh) <= 3)
        c_val = cam_map.get(b, 0.0)
        g_val = game_map.get(b, 0.0)
        low_motion = (c_val <= cam_cap) and (g_val <= game_cap)
        dead_bins.append(is_sil and low_motion)
    # Count only contiguous dead runs > 1.0s (>= 3 half-sec bins)
    dead_sec = 0.0
    i = 0
    while i < len(dead_bins):
        if dead_bins[i]:
            j = i
            while j < len(dead_bins) and dead_bins[j]:
                j += 1
            if (j - i) * 0.5 > 1.0:
                dead_sec += (j - i) * 0.5
            i = j
        else:
            i += 1
    return round((dead_sec / max(0.1, v_dur)) * 100.0, 2)


def _get_groq_key() -> str:
    creds_p = "/files/temp/all_ai_creds.json"
    if not os.path.exists(creds_p):
        return ""
    try:
        items = json.load(open(creds_p, "r", encoding="utf-8"))
        for it in items:
            if isinstance(it, dict) and it.get("type") == "groqApi":
                k = (it.get("data") or {}).get("apiKey") or ""
                if k:
                    return k.strip()
    except Exception:
        pass
    return ""


def _remap_words_to_kept_segments(words: list, kept_segments: list) -> list:
    """Project original Whisper word timestamps cleanly onto post-jumpcut concatenated timeline."""
    remapped = []
    out_cursor = 0.0
    for seg in kept_segments:
        s0 = float(seg["start"])
        s1 = float(seg["end"])
        seg_dur = max(0.0, s1 - s0)
        for w in words:
            ws = float(w.get("start", 0.0))
            we = float(w.get("end", ws))
            mid = (ws + we) * 0.5
            if s0 - 0.05 <= mid <= s1 + 0.05:
                ns = round(out_cursor + max(0.0, ws - s0), 3)
                ne = round(out_cursor + min(seg_dur, max(ws - s0 + 0.04, we - s0)), 3)
                if ne > ns:
                    remapped.append({**w, "start": ns, "end": ne})
        out_cursor += seg_dur
    return remapped


def _transcribe_whisper(src_mp4: str, cache_dir: str, kept_segments: list | None = None, is_cut: bool = False) -> dict:
    """Load real Groq Whisper word timestamps from cache (remapped onto kept_segments if cut) or call Groq if key present."""
    os.makedirs(cache_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src_mp4))[0]
    stem_cache = os.path.join(cache_dir, f"{stem}.whisper.json")
    if os.path.exists(stem_cache):
        base_doc = json.load(open(stem_cache, "r", encoding="utf-8"))
        if is_cut and kept_segments:
            new_words = _remap_words_to_kept_segments(base_doc.get("words") or [], kept_segments)
            new_dur = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in kept_segments)
            return {
                "duration": round(new_dur, 3),
                "text": " ".join(str(w.get("word", "")).strip() for w in new_words),
                "words": new_words,
            }
        return base_doc

    h = hashlib.sha1()
    with open(src_mp4, "rb") as f:
        while True:
            b = f.read(65536)
            if not b:
                break
            h.update(b)
    cache_p = os.path.join(cache_dir, f"whisper_{h.hexdigest()[:16]}.json")
    if os.path.exists(cache_p):
        return json.load(open(cache_p, "r", encoding="utf-8"))

    wav_p = os.path.join(cache_dir, f"tmp_{h.hexdigest()[:12]}.wav")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src_mp4, "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", wav_p], check=True)
    key = _get_groq_key()
    if not key:
        raise RuntimeError("No cached .whisper.json and no plaintext groqApi key found in /files/temp/all_ai_creds.json")

    boundary = "----AntigravityWhisperBoundary7f9a"
    wav_bytes = open(wav_p, "rb").read()
    parts = []
    for nm, val in (
        ("model", "whisper-large-v3-turbo"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("prompt", "GTA 6, Grand Theft Auto VI, Vice City, Leonida, Jason, Lucia, Rockstar Games, clip it, NPC, police chase, busted, wasted."),
    ):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{nm}\"\r\n\r\n{val}\r\n".encode("utf-8"))
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8"))
    parts.append(wav_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    with open(cache_p, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    try:
        os.remove(wav_p)
    except Exception:
        pass
    return res


def _parse_ass_time(ts: str) -> float:
    h, m, s = ts.strip().split(":")
    return int(h) * 3600.0 + int(m) * 60.0 + float(s)


def _run_create_subtitle_binary(mp4_path: str, whisper_doc: dict, rms_doc: dict, wf: dict, title: str = "Test Clip") -> str:
    """Execute workflow `Create Subtitle Binary` JS node with real Whisper + RMS data and return generated ASS text."""
    csb_js = [n for n in wf["nodes"] if n["name"] == "Create Subtitle Binary"][0]["parameters"]["jsCode"]
    v_dur, _ = _ffprobe_av_durations(mp4_path)
    with tempfile.TemporaryDirectory() as td:
        rms_p = os.path.join(td, "speech_rms.json")
        with open(rms_p, "w", encoding="utf-8") as f:
            json.dump(rms_doc, f)
        harness = (
            "const origRequire = require;\n"
            "const fsReal = origRequire('fs');\n"
            "require = (mod) => {\n"
            "  if (mod === 'fs') return {\n"
            "    existsSync: (p) => (p === '/files/temp/speech_rms.json' ? true : (String(p).includes('layout_timeline') ? false : fsReal.existsSync(p))),\n"
            "    readFileSync: (p, e) => p === '/files/temp/speech_rms.json' ? fsReal.readFileSync(" + json.dumps(rms_p) + ", e) : fsReal.readFileSync(p, e),\n"
            "    readdirSync: (p) => fsReal.readdirSync(p),\n"
            "    writeFileSync: () => {},\n"
            "    mkdirSync: () => {},\n"
            "    unlinkSync: () => {},\n"
            "  };\n"
            "  if (mod === 'child_process') return {\n"
            "    execSync: (cmd) => /ffprobe/i.test(String(cmd)) ? '" + f"{v_dur:.3f}" + "' : '',\n"
            "  };\n"
            "  return origRequire(mod);\n"
            "};\n"
            "const _it = { json: " + json.dumps(whisper_doc) + " };\n"
            "const $input = { item: _it, first: () => _it, all: () => [_it] };\n"
            "const _clip = { json: { clip_number: 1, duration: " + f"{v_dur:.3f}" + ", total_duration: " + f"{v_dur:.3f}" + ", segments: [{start: 0, end: " + f"{v_dur:.3f}" + "}], title: " + json.dumps(title) + ", hook_caption: 'GTA 6 cops have zero chill', has_webcam: true, cam_box: {x: 10, y: 474, w: 432, h: 228} } };\n"
            "const $ = (n) => ({\n"
            "  first: () => (n === '7d. Get Subtitles (SRT)' ? _it : { json: n === 'Config' ? { duration: 3000 } : (n === 'Parse Cam Config' ? { ai_found: true, cam_x: 10, cam_y: 474, cam_w: 432, cam_h: 228 } : {}) }),\n"
            "  item: n === '7d. Get Subtitles (SRT)' ? _it : _clip,\n"
            "  all: () => [n === '7d. Get Subtitles (SRT)' ? _it : _clip],\n"
            "  last: () => (n === '7d. Get Subtitles (SRT)' ? _it : { json: n === 'Parse Cam Config' ? { ai_found: true, cam_x: 10, cam_y: 474, cam_w: 432, cam_h: 228 } : {} }),\n"
            "});\n"
            "const out = (function(){\n" + csb_js + "\n})();\n"
            "console.log(JSON.stringify(out));\n"
        )
        hp = os.path.join(td, "csb_eval.js")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(harness)
        r = subprocess.run(["node", hp], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            raise RuntimeError(f"Create Subtitle Binary failed: {r.stderr}")
        out = json.loads(r.stdout)
        if out[0].get("json", {}).get("_skip_clip"):
            raise RuntimeError(f"Create Subtitle Binary skipped clip: {out[0]['json'].get('skip_reason')}")
        b64 = out[0]["binary"]["data"]["data"]
        import base64
        return base64.b64decode(b64).decode("utf-8")


def _measure_ass_sync(ass_text: str, vocal_rms: dict) -> dict:
    """Measure subtitle overlap, emoji tofu glyphs, and phrase-onset sync error vs 300-3400Hz RMS."""
    subs = []
    has_emoji_tofu = False
    for ln in ass_text.splitlines():
        if ln.startswith("Dialogue: 1,"):
            parts = ln.split(",", 9)
            st = _parse_ass_time(parts[1])
            en = _parse_ass_time(parts[2])
            txt = parts[9]
            if EMOJI_RE.search(txt):
                has_emoji_tofu = True
            subs.append((st, en, txt))

    overlaps = 0
    for i in range(1, len(subs)):
        if subs[i][0] < subs[i - 1][1] - 0.005:
            overlaps += 1

    rms_db = vocal_rms["rms_db"]
    thresh = vocal_rms["threshold_db"]
    frame_sec = vocal_rms["frame_ms"] / 1000.0
    onset_errs_ms = []
    early_gt150 = 0
    worst_early_examples = []

    for idx, (st, en, txt) in enumerate(subs):
        prev_en = subs[idx - 1][1] if idx > 0 else -1.0
        # Evaluate phrase openers (clip start or after >0.22s pause) AND initial word of each progressive step
        if idx == 0 or (st - prev_en) > 0.22:
            # Find actual vocal RMS onset inside [st - 0.12, max(st + 0.45, en)]
            f0 = max(0, int(math.floor(max(0.0, st - 0.12) / frame_sec)))
            f1 = min(len(rms_db) - 1, int(math.floor(max(st + 0.50, en) / frame_sec)))
            true_onset = None
            for fi in range(f0, f1 + 1):
                if rms_db[fi] >= thresh:
                    true_onset = fi * frame_sec
                    break
            if true_onset is not None:
                err_ms = abs(st - true_onset) * 1000.0
                onset_errs_ms.append(round(err_ms, 1))
                early_sec = true_onset - st
                if early_sec > 0.150:
                    early_gt150 += 1
                    worst_early_examples.append({"sub_start": round(st, 3), "vocal_onset": round(true_onset, 3), "early_ms": round(early_sec * 1000, 1), "text": re.sub(r"\{[^}]*\}", "", txt)[:40]})

    med_err = round(statistics.median(onset_errs_ms), 1) if onset_errs_ms else 0.0
    return {
        "sub_events": len(subs),
        "phrase_openers_checked": len(onset_errs_ms),
        "median_onset_error_ms": med_err,
        "early_words_gt150ms": early_gt150,
        "overlapping_events": overlaps,
        "has_emoji_tofu": has_emoji_tofu,
        "worst_early": worst_early_examples[:3],
    }


def _run_extract_audio_cmd(mp4_path: str, work_dir: str, wf: dict) -> dict:
    """Compute speech_rms.json matching the workflow `7b. Extract Clip Audio` filter settings."""
    cmd_7b = [n for n in wf["nodes"] if n["name"] == "7b. Extract Clip Audio"][0]["parameters"]["command"]
    uses_bandpass = ("highpass=f=300" in cmd_7b and "lowpass=f=3400" in cmd_7b)
    return _compute_vocal_band_rms(mp4_path, bandpass=uses_bandpass)


def main():
    parser = argparse.ArgumentParser(description="Evaluate dead-spot jump cuts & millisecond subtitle sync.")
    parser.add_argument("--apply-jumpcut", action="store_true", help="Run /files/dynamic_jumpcut_engine.py on copies of real clips before scoring.")
    parser.add_argument("--cache-dir", default="/files/temp/eval_pacing_cache")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    wf = json.load(open(WORKFLOW_PATH, "r", encoding="utf-8"))
    results = []
    os.makedirs(args.cache_dir, exist_ok=True)

    use_jumpcut = args.apply_jumpcut
    has_engine = False
    try:
        import dynamic_jumpcut_engine as dje
        has_engine = True
    except Exception:
        dje = None

    with tempfile.TemporaryDirectory() as td:
        for i, src_mp4 in enumerate(DEFAULT_TEST_CLIPS, start=1):
            if not os.path.exists(src_mp4):
                continue
            orig_v, orig_a = _ffprobe_av_durations(src_mp4)
            target_mp4 = src_mp4
            jc_meta = {"cuts_applied": 0, "choppy_shards": 0, "kept_segments": [{"start": 0.0, "end": orig_v}]}

            if use_jumpcut and has_engine:
                orig_tx = _transcribe_whisper(src_mp4, args.cache_dir)
                out_mp4 = os.path.join(td, f"cut_{i}.mp4")
                jc_res = dje.process_jumpcuts(src_mp4, out_mp4, whisper_doc=orig_tx)
                if os.path.exists(out_mp4):
                    target_mp4 = out_mp4
                    jc_meta = jc_res

            v_dur, a_dur = _ffprobe_av_durations(target_mp4)
            av_drift_ms = round(abs(v_dur - a_dur) * 1000.0, 2)
            # Ground truth vocal RMS (always 300-3400Hz) vs workflow 7b RMS (bandpass or unbandpassed depending on workflow)
            true_vocal_rms = _compute_vocal_band_rms(target_mp4, bandpass=True)
            wf_rms = _run_extract_audio_cmd(target_mp4, td, wf)
            dead_air_pct = _measure_dead_air_ratio(target_mp4, true_vocal_rms)

            whisper_doc = _transcribe_whisper(
                src_mp4, args.cache_dir,
                kept_segments=jc_meta.get("kept_segments"),
                is_cut=(target_mp4 != src_mp4),
            )
            ass_text = _run_create_subtitle_binary(target_mp4, whisper_doc, wf_rms, wf, title=os.path.splitext(os.path.basename(src_mp4))[0])
            sync_stats = _measure_ass_sync(ass_text, true_vocal_rms)

            kept = jc_meta.get("kept_segments") or []
            choppy = sum(1 for s in kept if (float(s["end"]) - float(s["start"])) < 1.20)
            cuts_per_30s = round((jc_meta.get("cuts_applied", 0) * 30.0) / max(1.0, orig_v), 2)

            results.append({
                "clip": os.path.basename(src_mp4),
                "orig_dur_s": round(orig_v, 2),
                "final_dur_s": round(v_dur, 2),
                "dead_air_ratio_pct": dead_air_pct,
                "cuts_applied": int(jc_meta.get("cuts_applied", 0)),
                "cuts_per_30s": cuts_per_30s,
                "choppy_shards": choppy,
                "av_sync_drift_ms": av_drift_ms,
                "cuts_detail": jc_meta.get("cut_regions", []),
                **sync_stats,
            })

    avg_dead = round(statistics.mean(r["dead_air_ratio_pct"] for r in results), 2) if results else 100.0
    max_dead = max((r["dead_air_ratio_pct"] for r in results), default=100.0)
    avg_cuts_30 = round(statistics.mean(r["cuts_per_30s"] for r in results), 2) if results else 0.0
    total_choppy = sum(r["choppy_shards"] for r in results)
    med_err_all = round(statistics.median(r["median_onset_error_ms"] for r in results), 1) if results else 999.0
    total_early_150 = sum(r["early_words_gt150ms"] for r in results)
    max_av_drift = max((r["av_sync_drift_ms"] for r in results), default=999.0)
    total_overlaps = sum(r["overlapping_events"] for r in results)
    total_tofu = sum(1 for r in results if r["has_emoji_tofu"])

    summary = {
        "clips_evaluated": len(results),
        "jumpcut_engine_loaded": has_engine and use_jumpcut,
        "max_dead_air_ratio_pct": max_dead,
        "avg_dead_air_ratio_pct": avg_dead,
        "avg_cuts_per_30s": avg_cuts_30,
        "choppy_shards_total": total_choppy,
        "median_subtitle_onset_error_ms": med_err_all,
        "early_words_gt150ms_total": total_early_150,
        "max_av_sync_drift_ms": max_av_drift,
        "zero_overlapping_ass_events": (total_overlaps == 0),
        "zero_emoji_tofu": (total_tofu == 0),
        "exit_criteria_passed": (
            len(results) >= 2
            and has_engine and use_jumpcut
            and max_dead < 6.0
            and 2.0 <= avg_cuts_30 <= 7.0
            and total_choppy == 0
            and med_err_all <= 55.0
            and total_early_150 == 0
            and max_av_drift <= 40.0
            and total_overlaps == 0
            and total_tofu == 0
        ),
    }
    report = {"summary": summary, "clips": results}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if summary["exit_criteria_passed"] else 1)


if __name__ == "__main__":
    main()
