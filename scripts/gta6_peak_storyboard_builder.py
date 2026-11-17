#!/usr/bin/env python3
"""
gta6_peak_storyboard_builder.py
-------------------------------
Peak-First + 3x3 Visual Storyboard Builder for GTA 6 Viral Shorts Engine.

Computes a 1-second multimodal virality curve V(t) from:
  1. Vocal RMS dB spikes weighted by FFT spectral centroid & sub-frame pitch variance
  2. Latency-shifted live chat velocity Z_chat(t + 5.5s over [t+3s, t+8s]) + gaming hype tokens
  3. Streamer face/mouth/head motion Z_face(t) from face_emotions.json & cam_config.json
  4. Short shock-utterance cadence boost + [NPC_OR_OTHER_VOICE] vs [STREAMER] tagging

Extracts Top 8 non-overlapping peaks (>= 90s apart on VODs >= 20m, >= 40s apart on shorter VODs),
carves [max(3.0, t_peak - 32.0), min(T_max, t_peak + 18.0)] snapped outward to complete Whisper sentences,
and renders 8 FFmpeg 3x3 contact sheets (960x540, 320x180 tiles, burned t=XXX.Xs timestamps, -q:v 5).
"""

import argparse
import bisect
import glob
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

GTA6_HYPE_RE = re.compile(
    r"(lmao|lmfao|wtf|ayo|clip\s*it|wasted|goty|npc|no\s*way|bruh|omg|deadass|"
    r"police|cop|busted|6\s*star|5\s*star|lucia|jason|leonida|vice\s*city|www+|\U0001F480|💀)",
    re.I,
)
CHAT_QUESTION_RE = re.compile(
    r"(\b(how do you|how did|where is|where do|what car|what gun|what weapon|what mission|what song|who is|why is|how to|can you)\b|\?\s*$)",
    re.I,
)
SHOCK_SPEECH_RE = re.compile(
    r"\b(ayo|what|wtf|no\s*way|wait|holy|bro|bruh|stop|run|watch\s*out|he\s*just|"
    r"she\s*just|did\s*you\s*see|wasted|busted|oh\s*my\s*god|clip\s*that|clip\s*it)\b",
    re.I,
)
HOUSEKEEPING_RE = re.compile(
    r"(thank you for the super\s*chat|get your entries in|enter you into the giveaway|"
    r"type [a-z0-9]+ into the chat|thank you for the raid|thanks for the raid|welcome raiders|"
    r"we'?re going to say bye|ending the stream|see you next time|don'?t forget to subscribe)",
    re.I,
)

FONT_CANDIDATES = [
    "/files/fonts/font.ttf",
    "/files/font.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _pick_font() -> str:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return ""


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _probe_duration(media_path: str) -> float:
    if not media_path or not os.path.exists(media_path):
        return 0.0
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", media_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode("utf-8", errors="replace").strip()
        return max(0.0, float(out))
    except Exception:
        return 0.0


def _load_json(path: str):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _auto_discover_video(target_duration: float) -> str:
    mp4s = sorted(glob.glob("/files/inputs/*.mp4"))
    if not mp4s:
        return ""
    if len(mp4s) == 1 or target_duration <= 0:
        return mp4s[0]
    best_path = mp4s[0]
    best_diff = float("inf")
    for p in mp4s:
        d = _probe_duration(p)
        if d <= 0:
            continue
        diff = abs(d - target_duration)
        if diff < best_diff:
            best_diff = diff
            best_path = p
    return best_path


def extract_1s_audio_features(audio_path: str, audio_energy_doc: dict, duration_hint: float) -> dict:
    """Compute per-second z_db, spectral centroid boost, and sub-frame pitch/ZCR variance."""
    bins = {}  # sec -> {db, z_db, centroid, zcr_var}

    if audio_path and os.path.exists(audio_path):
        sr = 8000
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", audio_path,
            "-af", "highpass=f=100,lowpass=f=3900",
            "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            chunk_bytes = sr * 2 * 60  # 60s chunks of int16 mono
            sec_idx = 0
            leftover = b""
            bytes_per_sec = sr * 2
            while True:
                raw = proc.stdout.read(chunk_bytes)
                if not raw:
                    break
                buf = leftover + raw
                n_full_secs = len(buf) // bytes_per_sec
                usable = n_full_secs * bytes_per_sec
                leftover = buf[usable:]
                if n_full_secs <= 0:
                    continue
                samples = np.frombuffer(buf[:usable], dtype=np.int16).astype(np.float32) / 32768.0
                sec_blocks = samples.reshape(n_full_secs, sr)
                rms = np.sqrt(np.mean(sec_blocks * sec_blocks, axis=1) + 1e-12)
                db_arr = 20.0 * np.log10(rms)

                # Vectorized FFT spectral centroid across 1s blocks
                spec = np.abs(np.fft.rfft(sec_blocks, axis=1)) + 1e-9
                freqs = np.linspace(0.0, 1.0, spec.shape[1], dtype=np.float32)
                cent_arr = (spec @ freqs) / np.sum(spec, axis=1)

                # Sub-frame (0.25s) zero-crossing rate variance -> pitch/articulation shifts
                sub = sec_blocks.reshape(n_full_secs, 4, sr // 4)
                zcr = np.mean((sub[:, :, 1:] * sub[:, :, :-1]) < 0.0, axis=2)
                zcr_var_arr = np.std(zcr, axis=1)

                for i in range(n_full_secs):
                    bins[sec_idx + i] = {
                        "db": float(db_arr[i]),
                        "centroid": float(cent_arr[i]),
                        "zcr_var": float(zcr_var_arr[i]),
                    }
                sec_idx += n_full_secs
            proc.wait(timeout=10)
        except Exception:
            bins = {}

    # Fallback to audio_energy.json raw_bins if FFmpeg PCM sweep didn't produce bins
    if not bins and isinstance(audio_energy_doc, dict):
        grouped = {}
        for rb in audio_energy_doc.get("raw_bins") or []:
            sec = int(float(rb.get("t", 0.0)))
            grouped.setdefault(sec, []).append((float(rb.get("db", -40.0)), float(rb.get("z_db", 0.0))))
        for sec, vals in grouped.items():
            bins[sec] = {
                "db": sum(v[0] for v in vals) / len(vals),
                "z_db_pre": max(v[1] for v in vals),
                "centroid": 0.25,
                "zcr_var": 0.02,
            }

    if not bins:
        max_sec = max(1, int(duration_hint or 60))
        return {
            "median_db": -28.0,
            "std_db": 6.0,
            "raw_bins": {s: {"db": -28.0, "z_db": 0.0, "spec_boost": 0.0, "audio_score": 0.0} for s in range(max_sec)},
        }

    active_dbs = np.array([v["db"] for v in bins.values() if v["db"] > -75.0], dtype=np.float32)
    if len(active_dbs) == 0:
        med_db, mean_db, std_db = -30.0, -30.0, 6.0
    else:
        med_db = float(np.median(active_dbs))
        mean_db = float(np.mean(active_dbs))
        mad_db = float(np.median(np.abs(active_dbs - med_db))) * 1.4826
        std_db = max(2.5, mad_db, float(np.std(active_dbs)))

    cents = np.array([v["centroid"] for v in bins.values() if v["db"] > -75.0], dtype=np.float32)
    med_c = float(np.median(cents)) if len(cents) else 0.25
    std_c = max(0.05, float(np.std(cents)) if len(cents) else 0.1)

    zvars = np.array([v["zcr_var"] for v in bins.values() if v["db"] > -75.0], dtype=np.float32)
    med_zv = float(np.median(zvars)) if len(zvars) else 0.02
    std_zv = max(0.01, float(np.std(zvars)) if len(zvars) else 0.02)

    out_bins = {}
    for sec, v in bins.items():
        z_db = v.get("z_db_pre")
        if z_db is None:
            z_db = max(0.0, (v["db"] - mean_db) / std_db)
        z_spec = max(0.0, (v["centroid"] - med_c) / std_c)
        z_pitch = max(0.0, (v["zcr_var"] - med_zv) / std_zv)
        spec_boost = 0.25 * min(3.0, z_spec) + 0.20 * min(3.0, z_pitch)
        audio_score = max(0.0, z_db) * (1.0 + spec_boost)
        out_bins[sec] = {
            "db": round(v["db"], 2),
            "z_db": round(float(z_db), 2),
            "spec_boost": round(float(spec_boost), 2),
            "audio_score": round(float(audio_score), 3),
        }

    return {"median_db": round(med_db, 2), "mean_db": round(mean_db, 2), "std_db": round(std_db, 2), "raw_bins": out_bins}


def compute_chat_lag_map(chat_doc: dict, max_sec: int) -> dict:
    """Compute latency-compensated Z_chat(t + 5.5s over [t+3s, t+8s]), hype tokens, and [CHAT_QUESTION_CLUSTER]."""
    lag_scores = {}
    lag_meta = {}
    if not isinstance(chat_doc, dict):
        return {"scores": lag_scores, "meta": lag_meta}

    clusters = chat_doc.get("clusters") or chat_doc.get("top_clusters") or []
    for cl in clusters:
        pt = float(cl.get("peak_time", 0.0))
        z = max(0.0, float(cl.get("z_score", 0.0)))
        msgs = cl.get("sample_messages") or []
        hype_hits = sum(1 for m in msgs if GTA6_HYPE_RE.search(str(m)))
        question_hits = sum(1 for m in msgs if CHAT_QUESTION_RE.search(str(m)))
        is_question_cluster = question_hits >= 2 or (len(msgs) >= 2 and (question_hits / float(len(msgs))) >= 0.4)
        laugh_pct = float(cl.get("laugh_ratio", 0.0))
        hype_bonus = min(2.4, hype_hits * 0.45 + laugh_pct * 1.2 + (0.65 if is_question_cluster else 0.0))
        weighted = z + hype_bonus

        # Chat peak at `pt` corresponds to VOD event t in [pt - 8.0, pt - 3.0], centered at pt - 5.5
        t_start = max(0, int(math.floor(pt - 8.0)))
        t_end = min(max_sec, int(math.ceil(pt - 3.0)))
        for s in range(t_start, t_end + 1):
            dist = abs((pt - s) - 5.5)
            kernel = max(0.35, 1.0 - (dist / 3.5))
            val = weighted * kernel
            if val > lag_scores.get(s, 0.0):
                lag_scores[s] = round(val, 3)
                lag_meta[s] = {"z": round(z, 2), "msgs": msgs[:2], "question_cluster": is_question_cluster}

    return {"scores": lag_scores, "meta": lag_meta}


def compute_face_motion_map(face_doc: dict, cam_cfg: dict) -> dict:
    """Compute per-second face/mouth motion Z_face(t), disabled when no real webcam found."""
    has_cam = bool(cam_cfg and cam_cfg.get("ai_found") and not cam_cfg.get("avatar_row_detected"))
    if not has_cam or not isinstance(face_doc, dict):
        return {"enabled": False, "med_mouth": 0.0, "scores": {}, "mouth_by_sec": {}}

    samples = face_doc.get("samples") or []
    top_events = face_doc.get("top_events") or []
    if not samples and not top_events:
        return {"enabled": True, "med_mouth": 0.0, "scores": {}, "mouth_by_sec": {}}

    intens = [float(s.get("intensity", 0.0)) for s in samples] or [60.0]
    med_i = float(np.median(intens))
    std_i = max(8.0, float(np.std(intens)))

    mouths = [float(s.get("mouth_motion", 0.0)) for s in samples if s.get("mouth_motion") is not None]
    med_m = float(np.median(mouths)) if len(mouths) >= 5 else 0.0

    scores = {}
    mouth_by_sec = {}
    for s in samples:
        sec = int(float(s.get("time", 0.0)))
        z_i = max(0.0, (float(s.get("intensity", 0.0)) - med_i) / std_i)
        mm = float(s.get("mouth_motion", 0.0))
        mouth_by_sec[sec] = max(mouth_by_sec.get(sec, 0.0), mm)
        mm_boost = 0.6 if (med_m > 0.015 and mm > med_m * 1.8) else 0.0
        scores[sec] = max(scores.get(sec, 0.0), round(z_i + mm_boost, 3))

    for ev in top_events:
        st_s = int(float(ev.get("start", 0.0)))
        en_s = int(math.ceil(float(ev.get("end", st_s + 1.5))))
        ev_score = max(1.0, (float(ev.get("peak_intensity", ev.get("intensity", 70.0))) - med_i) / std_i)
        for sec in range(max(0, st_s), en_s + 1):
            scores[sec] = max(scores.get(sec, 0.0), round(ev_score, 3))

    return {"enabled": True, "med_mouth": round(med_m, 4), "scores": scores, "mouth_by_sec": mouth_by_sec}


def build_sentences_from_whisper(transcript_doc: dict, index_doc: dict) -> list:
    """Load or build clean sentences with word timestamps from unified index or whisper words."""
    if isinstance(index_doc, dict) and index_doc.get("annotated_sentences"):
        sents = []
        for s in index_doc["annotated_sentences"]:
            sents.append({
                "start": float(s.get("start", 0.0)),
                "end": float(s.get("end", 0.0)),
                "text": str(s.get("text", "")).strip(),
                "word_count": int(s.get("word_count", len(str(s.get("text", "")).split()))),
                "is_viewer_voice": bool(s.get("is_viewer_voice", False)),
                "tags": list(s.get("tags") or []),
            })
        return sents

    words = []
    if isinstance(transcript_doc, dict):
        words = transcript_doc.get("words") or (transcript_doc.get("x_groq") or {}).get("words") or []
    sents = []
    curr_words = []
    curr_st = None
    curr_en = None
    for w in words:
        tok = str(w.get("word", "")).strip()
        if not tok:
            continue
        st = float(w.get("start", 0.0))
        en = float(w.get("end", st + 0.2))
        if curr_st is None:
            curr_st = st
        elif st - curr_en >= 1.8 or len(curr_words) >= 18:
            sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": " ".join(curr_words), "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
            curr_words = []
            curr_st = st
        curr_words.append(tok)
        curr_en = en
        if re.search(r"[.!?]$", tok) and len(curr_words) >= 4:
            sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": " ".join(curr_words), "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
            curr_words = []
            curr_st = None
    if curr_words and curr_st is not None:
        sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": " ".join(curr_words), "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
    return sents


def tag_speaker_roles(sentences: list, audio_info: dict, face_info: dict) -> list:
    """Tag each sentence with [NPC_OR_OTHER_VOICE] vs [STREAMER]."""
    med_db = audio_info.get("median_db", -28.0)
    raw_bins = audio_info.get("raw_bins") or {}
    face_on = face_info.get("enabled", False)
    med_mouth = face_info.get("med_mouth", 0.0)
    mouth_by_sec = face_info.get("mouth_by_sec") or {}

    tagged = []
    for s in sentences:
        item = dict(s)
        st, en = float(item["start"]), float(item["end"])
        s0, s1 = max(0, int(math.floor(st))), int(math.ceil(en))
        dbs = [raw_bins[t]["db"] for t in range(s0, s1 + 1) if t in raw_bins]
        avg_db = (sum(dbs) / len(dbs)) if dbs else None
        low_mic = (avg_db is not None and avg_db < (med_db - 4.5))

        static_mouth = False
        if face_on and med_mouth > 0.015:
            ms = [mouth_by_sec[t] for t in range(s0, s1 + 1) if t in mouth_by_sec]
            if ms and (sum(ms) / len(ms)) < (med_mouth * 0.35):
                static_mouth = True

        is_npc = bool(item.get("is_viewer_voice") or ((low_mic or static_mouth) and item.get("word_count", 0) >= 2))
        item["speaker_tag"] = "[NPC_OR_OTHER_VOICE]" if is_npc else "[STREAMER]"
        tagged.append(item)
    return tagged


def extract_top_candidates(
    duration: float,
    sentences: list,
    audio_info: dict,
    chat_info: dict,
    face_info: dict,
    top_k: int = 8,
) -> list:
    """Compute 1s V(t), suppress intro/outro/housekeeping, select Top K isolated peaks & snap windows."""
    max_sec = max(30, int(math.floor(duration)))
    raw_bins = audio_info.get("raw_bins") or {}
    chat_scores = chat_info.get("scores") or {}
    chat_meta = chat_info.get("meta") or {}
    face_scores = face_info.get("scores") or {}

    # Precompute housekeeping seconds and shock text seconds from Whisper sentences
    suppressed_secs = set()
    shock_secs = {}
    for s in sentences:
        s0, s1 = max(0, int(math.floor(s["start"]))), min(max_sec, int(math.ceil(s["end"])))
        txt = s.get("text", "")
        if HOUSEKEEPING_RE.search(txt):
            for sec in range(max(0, s0 - 2), min(max_sec, s1 + 3)):
                suppressed_secs.add(sec)
        if SHOCK_SPEECH_RE.search(txt):
            for sec in range(s0, s1 + 1):
                shock_secs[sec] = max(shock_secs.get(sec, 0.0), 0.75)

    # 1-second multimodal virality curve V(t)
    v_curve = [0.0] * (max_sec + 1)
    intro_guard = 15
    outro_guard = max(20, max_sec - 20)
    for sec in range(intro_guard, max(intro_guard, outro_guard)):
        if sec in suppressed_secs:
            continue
        a_sc = float((raw_bins.get(sec) or {}).get("audio_score", 0.0))
        c_sc = float(chat_scores.get(sec, 0.0))
        f_sc = float(face_scores.get(sec, 0.0))
        txt_sc = float(shock_secs.get(sec, 0.0))
        # Smooth peak energy slightly across +-1s so micro-spikes coalesce naturally
        local_a = max(a_sc, 0.7 * float((raw_bins.get(sec - 1) or {}).get("audio_score", 0.0)), 0.7 * float((raw_bins.get(sec + 1) or {}).get("audio_score", 0.0)))
        v = 0.42 * local_a + 0.38 * c_sc + 0.20 * f_sc + txt_sc
        v_curve[sec] = round(v, 4)

    min_spacing = 90.0 if duration >= 1200.0 else 40.0
    ranked_secs = sorted(range(intro_guard, max(intro_guard + 1, outro_guard)), key=lambda t: v_curve[t], reverse=True)

    selected_peaks = []
    for spacing_step in (min_spacing, max(25.0, min_spacing * 0.6)):
        for sec in ranked_secs:
            if len(selected_peaks) >= top_k:
                break
            if v_curve[sec] <= 0.0 and len(selected_peaks) > 0:
                continue
            if any(abs(sec - p) < spacing_step for p in selected_peaks):
                continue
            selected_peaks.append(sec)
        if len(selected_peaks) >= top_k:
            break

    # Fallback evenly spaced candidates if a synthetic silent fixture has all-zero V(t)
    if not selected_peaks:
        step = max(20, int((duration - 25.0) // max(1, top_k)))
        selected_peaks = [min(max_sec - 10, 20 + i * step) for i in range(top_k) if 20 + i * step < max_sec]

    sent_starts = [s["start"] for s in sentences]
    candidates = []
    for idx, t_peak in enumerate(selected_peaks[:top_k], start=1):
        w_start = max(3.0, float(t_peak) - 32.0)
        w_end = min(float(duration), float(t_peak) + 18.0)

        # Snap outward to complete Whisper sentences (up to +-6.0s guard)
        if sentences:
            pos_l = bisect.bisect_right(sent_starts, w_start) - 1
            if 0 <= pos_l < len(sentences):
                cand_s = sentences[pos_l]
                if cand_s["end"] > w_start and cand_s["start"] >= max(3.0, w_start - 6.0):
                    w_start = max(3.0, float(cand_s["start"]))
            pos_r = bisect.bisect_left(sent_starts, w_end) - 1
            if 0 <= pos_r < len(sentences):
                cand_e = sentences[pos_r]
                if cand_e["start"] < w_end < cand_e["end"] and cand_e["end"] <= min(float(duration), w_end + 6.0):
                    w_end = min(float(duration), float(cand_e["end"]))

        if w_end - w_start < 18.0:
            w_end = min(float(duration), w_start + 30.0)

        win_sents = [s for s in sentences if s["end"] >= w_start - 0.1 and s["start"] <= w_end + 0.1]
        lines = []
        for s in win_sents:
            m, sec_f = divmod(max(0.0, s["start"]), 60.0)
            lines.append(f"[{int(m):02d}:{sec_f:04.1f} | {s['speaker_tag']}] {s['text']}")

        rb = raw_bins.get(t_peak) or {}
        cm = chat_meta.get(t_peak) or {}
        candidates.append({
            "rank": idx,
            "candidate_id": f"cand_{idx}",
            "peak_time": round(float(t_peak), 2),
            "window_start": round(w_start, 2),
            "window_end": round(w_end, 2),
            "window_duration": round(w_end - w_start, 2),
            "virality_score": round(v_curve[t_peak], 3),
            "z_db": float(rb.get("z_db", 0.0)),
            "spec_boost": float(rb.get("spec_boost", 0.0)),
            "z_chat_lagged": float(chat_scores.get(t_peak, 0.0)),
            "z_face": float(face_scores.get(t_peak, 0.0)),
            "chat_question_cluster": bool(cm.get("question_cluster", False)),
            "chat_samples": cm.get("msgs") or [],
            "transcript_lines": lines,
            "raw_text": " ".join(s.get("text", "") for s in win_sents).strip(),
            "grid_path": "",
            "frame_timestamps": [],
        })

    return candidates


def is_grid_mostly_static(grid_path: str) -> bool:
    """Return True when >70% of central gameplay tiles across the 3x3 storyboard are static."""
    if not grid_path or not os.path.exists(grid_path):
        return False
    try:
        import cv2
    except Exception:
        return False
    img = cv2.imread(grid_path)
    if img is None or img.shape[0] < 540 or img.shape[1] < 960:
        return False
    tiles = []
    for r in range(3):
        for c in range(3):
            y0, y1 = r * 180 + 36, (r + 1) * 180 - 20
            x0, x1 = c * 320 + 24, (c + 1) * 320 - 24
            roi = cv2.cvtColor(cv2.resize(img[y0:y1, x0:x1], (120, 68)), cv2.COLOR_BGR2GRAY)
            tiles.append(roi.astype(np.float32))
    static_pairs = 0
    for i in range(1, len(tiles)):
        mae = float(np.mean(np.abs(tiles[i] - tiles[i - 1])))
        if mae < 2.2:
            static_pairs += 1
    # 8 consecutive transitions; >=6 (<2.2 MAE) means >70% of frames are frozen/static
    return (static_pairs / 8.0) > 0.70


def render_3x3_grid(video_path: str, cand: dict, grid_dir: str, font_path: str) -> dict:
    """Render a 960x540 (3x3 of 320x180 tiles) storyboard JPEG with burned t=XXX.Xs timestamps."""
    w_st = float(cand["window_start"])
    w_en = float(cand["window_end"])
    span = max(2.0, w_en - w_st)
    # 9 evenly spaced timestamps inside the window
    timestamps = [round(w_st + (span * (i + 0.5) / 9.0), 2) for i in range(9)]
    out_path = os.path.join(grid_dir, f"gta6_{cand['candidate_id']}_grid.jpg")
    cand["frame_timestamps"] = timestamps

    if not video_path or not os.path.exists(video_path):
        return cand

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for t in timestamps:
        cmd.extend(["-ss", f"{t:.2f}", "-threads", "1", "-an", "-i", video_path])

    font_opt = f":fontfile={font_path}" if font_path else ""
    filter_parts = []
    stack_inputs = []
    for i, t in enumerate(timestamps):
        label_txt = f"t={t:.1f}s"
        filter_parts.append(
            f"[{i}:v]scale=320:180:force_original_aspect_ratio=decrease,"
            f"pad=320:180:(ow-iw)/2:(oh-ih)/2:black,"
            f"drawbox=x=4:y=4:w=118:h=24:color=black@0.75:t=fill,"
            f"drawtext=text='{label_txt}'{font_opt}:x=9:y=8:fontsize=16:fontcolor=yellow[f{i}]"
        )
        stack_inputs.append(f"[f{i}]")

    layout = "0_0|320_0|640_0|0_180|320_180|640_180|0_360|320_360|640_360"
    filter_parts.append(f"{''.join(stack_inputs)}xstack=inputs=9:layout={layout}[grid]")

    cmd.extend(["-filter_complex", ";".join(filter_parts), "-map", "[grid]", "-frames:v", "1", "-q:v", "5", out_path])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            cand["grid_path"] = out_path
    except Exception:
        pass
    return cand


def main():
    parser = argparse.ArgumentParser(description="Build GTA 6 empirical peak windows and 3x3 vision storyboards.")
    parser.add_argument("--video", default="", help="Source stream MP4 path")
    parser.add_argument("--audio", default="/files/temp/audio.mp3")
    parser.add_argument("--transcript", default="")
    parser.add_argument("--index", default="/files/temp/unified_timeline_index.json")
    parser.add_argument("--cam", default="/files/temp/cam_config.json")
    parser.add_argument("--audio-energy", default="/files/temp/audio_energy.json")
    parser.add_argument("--chat", default="")
    parser.add_argument("--face", default="/files/temp/face_emotions.json")
    parser.add_argument("--out", default="/files/temp/gta6_candidates.json")
    parser.add_argument("--grid-dir", default="/files/temp")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--skip-grids", action="store_true")
    args = parser.parse_args()

    tx_path = _first_existing([
        args.transcript,
        "/files/temp/transcript.json",
        "/files/outputs/whisper_28754.json",
        "/files/temp/whisper_raw.json",
    ])
    chat_path = _first_existing([
        args.chat,
        "/files/temp/chat_laughter_clusters.json",
        "/files/temp/chat_analysis.json",
        "/files/temp/test_zscore_out.json",
    ])

    transcript_doc = _load_json(tx_path) or {}
    index_doc = _load_json(args.index) or {}
    cam_cfg = _load_json(args.cam) or {}
    audio_energy_doc = _load_json(args.audio_energy) or {}
    chat_doc = _load_json(chat_path) or {}
    face_doc = _load_json(args.face) or {}

    tx_dur = float(transcript_doc.get("duration") or index_doc.get("duration") or 0.0)
    aud_dur = _probe_duration(args.audio)
    video_path = args.video if (args.video and os.path.exists(args.video)) else _auto_discover_video(tx_dur or aud_dur)
    active_stream = os.path.basename(video_path) if video_path else ""
    vid_dur = _probe_duration(video_path)

    # Fix 1.1: Validate cached chat telemetry against active stream_file header & purge mismatched caches
    if active_stream and isinstance(chat_doc, dict) and chat_doc:
        cached_sf = os.path.basename(str(chat_doc.get("stream_file") or "").strip())
        if cached_sf and cached_sf != active_stream:
            chat_doc = {}
            if chat_path and os.path.exists(chat_path):
                try:
                    os.remove(chat_path)
                except Exception:
                    pass

    # Clamp effective timeline to overlapping duration so FFmpeg never seeks past EOF
    durs = [d for d in (vid_dur, aud_dur, tx_dur) if d > 0]
    duration = min(vid_dur, max(tx_dur, aud_dur)) if (vid_dur > 0 and (tx_dur > 0 or aud_dur > 0)) else (max(durs) if durs else 120.0)

    audio_info = extract_1s_audio_features(args.audio, audio_energy_doc, duration)
    chat_info = compute_chat_lag_map(chat_doc, int(duration) + 1)
    face_info = compute_face_motion_map(face_doc, cam_cfg)
    sentences = tag_speaker_roles(build_sentences_from_whisper(transcript_doc, index_doc), audio_info, face_info)

    raw_candidates = extract_top_candidates(duration, sentences, audio_info, chat_info, face_info, top_k=args.top_k + 4)

    os.makedirs(args.grid_dir, exist_ok=True)
    font_path = _pick_font()
    candidates = []
    if not args.skip_grids and video_path:
        active_batch = raw_candidates[:args.top_k]
        reserves = raw_candidates[args.top_k:]
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda c: render_3x3_grid(video_path, c, args.grid_dir, font_path), active_batch))
        for c in active_batch:
            if c.get("grid_path") and is_grid_mostly_static(c["grid_path"]):
                c["is_static_screen"] = True
                if reserves:
                    rep = reserves.pop(0)
                    render_3x3_grid(video_path, rep, args.grid_dir, font_path)
                    if not (rep.get("grid_path") and is_grid_mostly_static(rep["grid_path"])):
                        candidates.append(rep)
            else:
                candidates.append(c)
        if not candidates:
            candidates = active_batch
    else:
        candidates = raw_candidates[:args.top_k]

    for idx, c in enumerate(candidates, start=1):
        c["rank"] = idx
        c["candidate_id"] = f"cand_{idx}"

    payload = {
        "stream_file": active_stream,
        "video_path": video_path,
        "video_duration": round(vid_dur, 2),
        "effective_duration": round(duration, 2),
        "peak_spacing_sec": 90.0 if duration >= 1200.0 else 40.0,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps({
        "status": "ok",
        "video_path": video_path,
        "effective_duration": payload["effective_duration"],
        "candidate_count": len(candidates),
        "grids_rendered": sum(1 for c in candidates if c.get("grid_path")),
        "out": args.out,
    }))


if __name__ == "__main__":
    main()
