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
    r"(thank you for the super\s*chat|for the super chat|get your entries in|enter you into the giveaway|"
    r"type [a-z0-9]+ into the chat|thank you for the raid|thanks for the raid|welcome raiders|"
    r"we'?re going to say bye|going to say bye|ending the stream|see you next time|don'?t forget to subscribe|"
    r"make sure to subscribe|subscribe to the channel|everybody subscribe|hit the like button|"
    r"smash (?:that |the )?like|thanks? for watching|peace out everybody|comment\b[^.?!]{0,40}\btomorrow|"
    r"thank you so much for watching|catch you guys tomorrow|subathon timer|shoutout to the raiders|"
    r"gifted\s+\w*\s*premiums|gifted\s+(?:subs?|memberships?)|thank you for the \$\d|"
    r"welcome to the champions club|thank you for subscribing)",
    re.I,
)
GTA6_PROMPT_HALLUCINATION_TOKENS = (
    "grand theft auto vi", "vice city", "vice beach", "rockstar games",
    "npc chaos", "gta rp", "roblox gaming", "lucky blocks", "divine mutation",
    "strawberry elephant", "taco combinacion", "streamer reacting",
)


def _is_whisper_prompt_hallucination(text: str) -> bool:
    low = str(text or "").lower().strip()
    if not low or low in {"music", "music.", "[music]", "you", "you."}:
        return True
    if "grand theft auto vi, vice city, leonida" in low:
        return True
    return sum(1 for p in GTA6_PROMPT_HALLUCINATION_TOKENS if p in low) >= 2

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


def compute_heatmap_map(video_path: str, duration: float, info_path: str = "") -> dict:
    """Load YouTube 'Most Replayed' heatmap from chunk .info.json, offset by chunk_start_sec, and map spikes to Z-equivalent scores."""
    cand_paths = []
    if info_path:
        cand_paths.append(info_path)
    if video_path:
        input_dir = os.path.dirname(video_path) or "/files/inputs"
        raw_base = os.path.splitext(os.path.basename(video_path))[0]
        clean_base = raw_base[:-11] if raw_base.endswith(".processing") else raw_base
        for d in (input_dir, "/files/inputs"):
            for fn in (
                f"{clean_base}.processing.info.json",
                f"{clean_base}.info.json",
                f"{raw_base}.info.json",
            ):
                p = os.path.join(d, fn)
                if p not in cand_paths:
                    cand_paths.append(p)
    found = next((p for p in cand_paths if p and os.path.isfile(p)), "")
    doc = _load_json(found) if found else None
    if not isinstance(doc, dict):
        return {"scores": {}, "raw_values": {}, "peak_count": 0, "chunk_start_sec": 0.0, "source": found}
    raw_hm = doc.get("heatmap")
    if not isinstance(raw_hm, list) or not raw_hm:
        return {"scores": {}, "raw_values": {}, "peak_count": 0, "chunk_start_sec": 0.0, "source": found}

    chunk_start = doc.get("chunk_start_sec")
    if chunk_start is None:
        m = re.search(r"_chunk(\d+)", os.path.basename(video_path or found), re.I)
        chunk_idx = int(m.group(1)) if m else 1
        chunk_start = float(max(0, chunk_idx - 1) * 3000.0)
    else:
        chunk_start = float(chunk_start or 0.0)

    max_sec = max(30, int(math.floor(duration or 3600.0)))
    local_buckets = []
    for entry in raw_hm:
        if not isinstance(entry, dict):
            continue
        try:
            st = float(entry.get("start_time", 0.0)) - chunk_start
            en = float(entry.get("end_time", st + 1.0)) - chunk_start
            val = float(entry.get("value", 0.0))
        except (TypeError, ValueError):
            continue
        if en <= 0.0 or st >= max_sec:
            continue
        st_c = max(0.0, st)
        en_c = min(float(max_sec), en)
        if en_c <= st_c:
            continue
        local_buckets.append((st_c, en_c, max(0.0, min(1.0, val))))

    if not local_buckets:
        return {"scores": {}, "raw_values": {}, "peak_count": 0, "chunk_start_sec": chunk_start, "source": found}

    vals_desc = sorted((b[2] for b in local_buckets), reverse=True)
    top15_cut = vals_desc[min(14, len(vals_desc) - 1)]
    scores = {}
    raw_values = {}
    peak_count = 0
    for st_c, en_c, val in local_buckets:
        is_peak = (val >= 0.55) or (val >= top15_cut and val >= 0.35)
        if not is_peak:
            continue
        peak_count += 1
        # Map heatmap replay intensity [0.35..1.0] to Z-equivalent [1.8..3.8] (equivalent to [CHAT_BURST])
        z_eq = round(1.5 + val * 2.3, 3)
        s0 = max(0, int(math.floor(st_c)))
        s1 = min(max_sec, int(math.ceil(en_c)))
        for s in range(s0, s1 + 1):
            if z_eq > scores.get(s, 0.0):
                scores[s] = z_eq
                raw_values[s] = round(val, 4)

    return {
        "scores": scores,
        "raw_values": raw_values,
        "peak_count": peak_count,
        "chunk_start_sec": round(chunk_start, 2),
        "source": found,
    }


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
            txt = " ".join(curr_words)
            if not _is_whisper_prompt_hallucination(txt):
                sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": txt, "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
            curr_words = []
            curr_st = st
        curr_words.append(tok)
        curr_en = en
        if re.search(r"[.!?]$", tok) and len(curr_words) >= 4:
            txt = " ".join(curr_words)
            if not _is_whisper_prompt_hallucination(txt):
                sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": txt, "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
            curr_words = []
            curr_st = None
    if curr_words and curr_st is not None:
        txt = " ".join(curr_words)
        if not _is_whisper_prompt_hallucination(txt):
            sents.append({"start": round(curr_st, 2), "end": round(curr_en, 2), "text": txt, "word_count": len(curr_words), "is_viewer_voice": False, "tags": []})
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
    top_k: int = 12,
    slice_lo: float = None,
    slice_hi: float = None,
    heatmap_info: dict | None = None,
) -> list:
    """Compute 1s V(t), suppress intro/outro/housekeeping, select Top K isolated peaks & snap windows."""
    max_sec = max(30, int(math.floor(duration)))
    raw_bins = audio_info.get("raw_bins") or {}
    chat_scores = chat_info.get("scores") or {}
    chat_meta = chat_info.get("meta") or {}
    hm_scores = (heatmap_info or {}).get("scores") or {}
    hm_raw = (heatmap_info or {}).get("raw_values") or {}
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
    lo_bound = max(3.0, float(slice_lo)) if slice_lo is not None else 3.0
    hi_bound = min(float(duration), float(slice_hi)) if slice_hi is not None else float(duration)
    intro_guard = max(15, int(math.floor(lo_bound)) + 10)
    outro_guard = min(max(intro_guard + 1, max_sec - 20), int(math.floor(hi_bound)) - 10)
    if outro_guard <= intro_guard:
        intro_guard = max(3, int(math.floor(lo_bound)))
        outro_guard = min(max_sec, max(intro_guard + 1, int(math.floor(hi_bound))))

    for sec in range(intro_guard, outro_guard):
        if sec in suppressed_secs:
            continue
        a_sc = float((raw_bins.get(sec) or {}).get("audio_score", 0.0))
        c_sc = float(chat_scores.get(sec, 0.0))
        h_sc = float(hm_scores.get(sec, 0.0))
        crowd_sc = max(c_sc, h_sc)
        f_sc = float(face_scores.get(sec, 0.0))
        txt_sc = float(shock_secs.get(sec, 0.0))
        # Smooth peak energy slightly across +-1s so micro-spikes coalesce naturally
        local_a = max(a_sc, 0.7 * float((raw_bins.get(sec - 1) or {}).get("audio_score", 0.0)), 0.7 * float((raw_bins.get(sec + 1) or {}).get("audio_score", 0.0)))
        v = 0.42 * local_a + 0.38 * crowd_sc + 0.20 * f_sc + txt_sc
        # Boost genuine crowd-replayed streamer reactions (heatmap + face/vocal burst) over random explosions
        if h_sc >= 1.5 and (f_sc >= 0.8 or local_a >= 1.2 or txt_sc > 0.0):
            v += 0.45
        v_curve[sec] = round(v, 4)

    eff_span = max(60.0, hi_bound - lo_bound)
    min_spacing = 45.0 if eff_span >= 1200.0 else 30.0
    ranked_secs = sorted(range(intro_guard, max(intro_guard + 1, outro_guard)), key=lambda t: v_curve[t], reverse=True)

    dense_tx = len(sentences) >= 6 and sum(int(s.get("word_count", 0)) for s in sentences) >= 60

    # Helper: verify candidate window actually contains substantive speech when sentences exist
    def _has_window_speech(sec_pt: int, min_wc: int = 12) -> bool:
        if not sentences:
            return True
        eff_min = min_wc if dense_tx else 1
        w0 = max(lo_bound, float(sec_pt) - 30.0)
        w1 = min(hi_bound, float(sec_pt) + 14.0)
        wc_w = sum(int(s.get("word_count", 0)) for s in sentences if float(s["end"]) >= w0 and float(s["start"]) <= w1)
        return wc_w >= eff_min

    selected_peaks = []
    for spacing_step in (min_spacing, max(25.0, min_spacing * 0.65)):
        for sec in ranked_secs:
            if len(selected_peaks) >= top_k:
                break
            if v_curve[sec] <= 0.0 and len(selected_peaks) > 0:
                continue
            if not _has_window_speech(sec, 12):
                continue
            if any(abs(sec - p) < spacing_step for p in selected_peaks):
                continue
            selected_peaks.append(sec)
        if len(selected_peaks) >= top_k:
            break

    # Fallback: prefer sentence anchors when sparse audio/flat V(t)
    if not selected_peaks:
        if sentences:
            step_s = max(1, len(sentences) // max(1, top_k))
            for idx_s in range(0, len(sentences), step_s):
                st_s = int(round(float(sentences[idx_s]["start"])))
                if intro_guard <= st_s < outro_guard and _has_window_speech(st_s, 10):
                    if all(abs(st_s - p) >= 25.0 for p in selected_peaks):
                        selected_peaks.append(st_s)
                if len(selected_peaks) >= top_k:
                    break
        if not selected_peaks:
            step = max(20, int((hi_bound - lo_bound - 20.0) // max(1, top_k)))
            selected_peaks = [min(outro_guard, intro_guard + i * step) for i in range(top_k) if intro_guard + i * step < outro_guard]

    sent_starts = [s["start"] for s in sentences] if sentences else []
    candidates = []
    for idx, t_peak in enumerate(selected_peaks[:top_k], start=1):
        # Tight 44s candidate window [peak - 30s, peak + 14s] tuned for punchy 15s-34s viral Shorts
        w_start = max(lo_bound, float(t_peak) - 30.0)
        w_end = min(hi_bound, float(t_peak) + 14.0)

        # Snap start/end cleanly to complete Whisper sentences (up to +-4.5s guard)
        if sentences:
            pos_l = bisect.bisect_right(sent_starts, w_start) - 1
            if 0 <= pos_l < len(sentences):
                cand_s = sentences[pos_l]
                prev_s = sentences[pos_l - 1] if pos_l > 0 else None
                prev_ends_term = bool(prev_s and re.search(r"(?<!\.)[.!?][\"'\)]*$", str(prev_s.get("text") or "").strip()))
                gap_prev = (float(cand_s["start"]) - float(prev_s["end"])) if prev_s else 1.0
                if cand_s["end"] > w_start and cand_s["start"] >= max(lo_bound, w_start - 4.5) and (prev_ends_term or gap_prev >= 0.35 or pos_l == 0):
                    w_start = max(lo_bound, float(cand_s["start"]))
                elif pos_l + 1 < len(sentences) and float(sentences[pos_l + 1]["start"]) < float(t_peak) - 10.0:
                    w_start = max(lo_bound, float(sentences[pos_l + 1]["start"]))
            pos_r = bisect.bisect_left(sent_starts, w_end) - 1
            if 0 <= pos_r < len(sentences):
                cand_e = sentences[pos_r]
                if cand_e["start"] < w_end < cand_e["end"] and cand_e["end"] <= min(hi_bound, w_end + 4.5):
                    w_end = min(hi_bound, float(cand_e["end"]))
                elif cand_e["start"] > float(t_peak) + 2.0 and cand_e["end"] <= w_end:
                    w_end = min(hi_bound, float(cand_e["end"]))

        win_sents = [s for s in sentences if w_start <= (s["start"] + s["end"]) * 0.5 <= w_end]
        if win_sents and dense_tx:
            # Never carry >2.5s leading/trailing dead air inside dense windows
            first_sp = max(lo_bound, float(win_sents[0]["start"]) - 0.30)
            last_sp = min(hi_bound, float(win_sents[-1]["end"]) + 0.50)
            if first_sp - w_start > 2.5:
                w_start = first_sp
            if w_end - last_sp > 2.5:
                w_end = last_sp
        elif w_end - w_start < 20.0 and (hi_bound - lo_bound) >= 24.0:
            w_start = max(lo_bound, min(w_start, float(w_end) - 24.0))
            w_end = min(hi_bound, max(w_end, w_start + 30.0))

        # 0-3s Hook Energy Check: shift w_start forward if first 3s lack speech AND lack vocal/face spike
        if sentences:
            h_words = sum(int(s.get("word_count", 0)) for s in win_sents if float(s["end"]) >= w_start and float(s["start"]) <= w_start + 3.0)
            h_zdb = max((float((raw_bins.get(sec) or {}).get("z_db", 0.0)) for sec in range(int(w_start), int(w_start + 3.0) + 1)), default=0.0)
            h_zf = max((float(face_scores.get(sec, 0.0)) for sec in range(int(w_start), int(w_start + 3.0) + 1)), default=0.0)
            if h_words < 2 and h_zdb < 1.5 and h_zf < 1.0:
                active_early = [s for s in win_sents if float(s["end"]) <= float(t_peak) - 3.0 and int(s.get("word_count", 0)) >= 2]
                if active_early:
                    cand_shift = max(w_start, float(active_early[0]["start"]) - 0.25)
                    if (w_end - cand_shift) >= 16.0:
                        w_start = cand_shift

        win_sents = [s for s in sentences if w_start <= (s["start"] + s["end"]) * 0.5 <= w_end]
        if dense_tx and sum(int(s.get("word_count", 0)) for s in win_sents) < 10:
            continue
        cm = chat_meta.get(t_peak) or {}
        q_cluster = bool(cm.get("question_cluster", False))
        lines = []
        win_tags = []
        rb = raw_bins.get(t_peak) or {}
        peak_z_db = float(rb.get("z_db", 0.0))
        peak_z_chat = float(chat_scores.get(t_peak, 0.0))
        peak_z_hm = float(hm_scores.get(t_peak, 0.0))
        peak_hm_val = float(hm_raw.get(t_peak, 0.0))
        if peak_z_hm <= 0.0 and hm_scores:
            # Check +-6s neighborhood around peak for heatmap bucket
            for hs in range(max(0, int(t_peak) - 6), min(max_sec, int(t_peak) + 6) + 1):
                if float(hm_scores.get(hs, 0.0)) > peak_z_hm:
                    peak_z_hm = float(hm_scores.get(hs, 0.0))
                    peak_hm_val = float(hm_raw.get(hs, 0.0))
        peak_z_face = float(face_scores.get(t_peak, 0.0))

        # Sustained Multi-Beat Arc check: >=2 distinct beats >=5s apart inside escalation span
        beat_secs = []
        b_lo = max(3, int(t_peak) - 28)
        b_hi = min(max_sec, int(t_peak) + 8)
        for bs in range(b_lo, b_hi + 1):
            rb_b = raw_bins.get(bs) or {}
            b_hit = (
                float(rb_b.get("z_db", 0.0)) >= 1.5
                or float(chat_scores.get(bs, 0.0)) >= 1.2
                or float(hm_scores.get(bs, 0.0)) >= 1.5
                or float(face_scores.get(bs, 0.0)) >= 1.0
                or float(shock_secs.get(bs, 0.0)) > 0.0
            )
            if b_hit and (not beat_secs or (bs - beat_secs[-1]) >= 5):
                beat_secs.append(bs)
        if len(beat_secs) < 2 and len(win_sents) >= 3:
            early_sents = [s for s in win_sents if float(s["end"]) < float(t_peak) - 4.0 and int(s.get("word_count", 0)) >= 4]
            if early_sents and (beat_secs or any(SHOCK_SPEECH_RE.search(s.get("text", "")) for s in win_sents)):
                beat_secs.insert(0, int(early_sents[0]["start"]))

        if peak_z_db >= 2.8:
            win_tags.append(f"[SCREAM:Z={peak_z_db:.1f}]")
        elif peak_z_db >= 2.0:
            win_tags.append(f"[dB_PEAK:Z={peak_z_db:.1f}]")
        if peak_z_chat > 0.0:
            win_tags.append(f"[CHAT_BURST:Z={peak_z_chat:.1f}]")
        if peak_z_hm > 0.0:
            win_tags.append(f"[HEATMAP_PEAK:val={peak_hm_val:.2f}]")
            win_tags.append("[CROWD_REPLAY]")
        if peak_z_face >= 1.2:
            win_tags.append("[FACE:SHOCK_OR_REACTION]")
        word_sum = sum(int(s.get("word_count", 0)) for s in win_sents)
        win_dur_s = max(1.0, w_end - w_start)
        wpm_val = word_sum / (win_dur_s / 60.0)
        if wpm_val >= 145.0:
            win_tags.append(f"[WPM_SPIKE:{int(round(wpm_val))}wpm]")
        shock_hits = sum(1 for s in win_sents if SHOCK_SPEECH_RE.search(str(s.get("text") or "")))
        if (shock_hits >= 2 or (shock_hits >= 1 and (peak_z_db >= 1.4 or wpm_val >= 165.0))) and not any("dB_PEAK" in t or "SCREAM" in t for t in win_tags):
            win_tags.append("[WPM_SPIKE:SHOCK_EXCLAIM]")
        streamer_spoken_sec = 0.0
        for si_l, s in enumerate(win_sents):
            m, sec_f = divmod(max(0.0, s["start"]), 60.0)
            q_tag = " [CHAT_QUESTION_CLUSTER]" if (q_cluster and si_l == len(win_sents) // 2) else ""
            lines.append(f"[{int(m):02d}:{sec_f:04.1f} | {s['speaker_tag']}{q_tag}] {s['text']}")
            if s.get("speaker_tag") in ("[STREAMER]", "STREAMER"):
                streamer_spoken_sec += max(0.0, min(w_end, float(s["end"])) - max(w_start, float(s["start"])))
            for tg in (s.get("tags") or []):
                if tg not in win_tags:
                    win_tags.append(tg)
        streamer_silence_ratio = round(max(0.0, min(1.0, 1.0 - (streamer_spoken_sec / win_dur_s))), 3)

        peak_z_crowd = max(peak_z_chat, peak_z_hm)
        sig_strength = (
            (1.15 if peak_z_db >= 2.8 else (0.85 if peak_z_db >= 2.1 else (0.35 if peak_z_db >= 1.4 else 0.0)))
            + (0.85 if peak_z_crowd >= 2.0 else (0.45 if peak_z_crowd >= 1.0 else 0.0))
            + (0.65 if peak_z_face >= 1.2 else 0.0)
            + (0.65 if wpm_val >= 145.0 else (0.35 if wpm_val >= 125.0 else 0.0))
            + (0.45 if shock_hits >= 2 else (0.20 if shock_hits >= 1 else 0.0))
        )
        # Penalize passive/silent cutscene stretches where streamer is mostly silent
        silence_penalty = 0.85 if (dense_tx and streamer_silence_ratio > 0.65 and peak_z_db < 2.2 and peak_z_face < 1.2) else 0.0
        est_virality = max(4.0, min(9.9, round(6.5 + min(1.8, v_curve[t_peak] * 0.48) + (0.85 if len(beat_secs) >= 2 else 0.0) + min(1.55, sig_strength) - silence_penalty, 2)))
        if len(beat_secs) >= 2:
            win_tags.append(f"[MULTI_BEAT:{len(beat_secs)}]")

        candidates.append({
            "rank": idx,
            "candidate_id": f"cand_{idx}",
            "peak_time": round(float(t_peak), 2),
            "window_start": round(w_start, 2),
            "window_end": round(w_end, 2),
            "window_duration": round(w_end - w_start, 2),
            "virality_score": round(v_curve[t_peak], 3),
            "est_virality_10": est_virality,
            "multi_beat_count": len(beat_secs),
            "beat_timestamps": beat_secs[:5],
            "z_db": round(peak_z_db, 2),
            "spec_boost": float(rb.get("spec_boost", 0.0)),
            "z_chat_lagged": peak_z_chat,
            "z_heatmap": round(peak_z_hm, 2),
            "heatmap_value": round(peak_hm_val, 3),
            "z_face": peak_z_face,
            "streamer_silence_ratio": streamer_silence_ratio,
            "signal_tags": win_tags,
            "chat_question_cluster": bool(cm.get("question_cluster", False)),
            "chat_samples": cm.get("msgs") or [],
            "transcript_lines": lines,
            "raw_text": " ".join(s.get("text", "") for s in win_sents).strip(),
            "grid_path": "",
            "frame_timestamps": [],
        })

    return candidates


def get_adaptive_clip_targets(duration_sec: float) -> tuple[int, int, int]:
    """Scale candidate extraction and target clip counts dynamically by chunk duration."""
    if duration_sec < 480.0:
        return 6, 2, 3
    if duration_sec <= 1500.0:
        return 10, 4, 6
    return 14, 6, 10


def _measure_webcam_activity(video_path: str, w_start: float, w_end: float, cam_box: dict) -> float:
    """Return fraction of sampled adjacent frame pairs in cam_box showing active facial/head motion (0.0..1.0)."""
    if not video_path or not os.path.exists(video_path) or not isinstance(cam_box, dict):
        return 1.0
    cw, ch = int(cam_box.get("w") or 0), int(cam_box.get("h") or 0)
    cx, cy = int(cam_box.get("x") or 0), int(cam_box.get("y") or 0)
    if cw <= 20 or ch <= 20:
        return 1.0
    try:
        import cv2
        import numpy as np
    except Exception:
        return 1.0
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 1.0
    try:
        span = max(2.0, w_end - w_start)
        ts_list = [w_start + span * frac for frac in (0.12, 0.28, 0.44, 0.60, 0.76, 0.90)]
        rois = []
        for ts in ts_list:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts * 1000.0))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            fh, fw = frame.shape[:2]
            x0, y0 = max(0, min(fw - 1, cx)), max(0, min(fh - 1, cy))
            x1, y1 = max(x0 + 1, min(fw, cx + cw)), max(y0 + 1, min(fh, cy + ch))
            crop = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            rois.append(cv2.resize(crop, (64, 48)))
        if len(rois) < 3:
            return 1.0
        active = sum(
            1 for i in range(1, len(rois))
            if float(np.mean(np.abs(rois[i].astype("float32") - rois[i - 1].astype("float32")))) >= 2.2
        )
        return round(active / max(1, len(rois) - 1), 3)
    except Exception:
        return 1.0
    finally:
        cap.release()


def is_grid_mostly_static(grid_path: str) -> bool:
    """Return True when >55% of central gameplay tiles across the 3x3 storyboard lack real scene progression."""
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
    low_prog_pairs = 0
    for i in range(1, len(tiles)):
        mae = float(np.mean(np.abs(tiles[i] - tiles[i - 1])))
        if mae < 2.5:
            static_pairs += 1
        if mae < 4.5:
            low_prog_pairs += 1
    # Reject frozen/paused screens (>55% static) or monotonous single-room/menu staring (>70% low progression)
    return (static_pairs / 8.0) > 0.55 or (low_prog_pairs / 8.0) > 0.72


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
    parser.add_argument("--info-json", default="", help="Optional yt-dlp .info.json path for YouTube heatmap")
    parser.add_argument("--out", default="/files/temp/gta6_candidates.json")
    parser.add_argument("--grid-dir", default="/files/temp")
    parser.add_argument("--top-k", type=int, default=0, help="Candidate count (0=adaptive by stream duration)")
    parser.add_argument("--min-virality", type=float, default=0.0, help="Drop candidates with est_virality_10 below threshold (e.g. 8.8 in live production)")
    parser.add_argument("--slice-start", type=float, default=None, help="Optional slice start sec")
    parser.add_argument("--slice-end", type=float, default=None, help="Optional slice end sec")
    parser.add_argument("--skip-grids", action="store_true")
    args = parser.parse_args()

    override_doc = _load_json("/files/temp/iteration_dataset_override.json") if not args.transcript else None
    if not isinstance(override_doc, dict):
        override_doc = {}

    tx_path = _first_existing([
        args.transcript,
        override_doc.get("transcript_path"),
        "/files/temp/transcript.json",
        "/files/outputs/whisper_28754.json",
        "/files/temp/whisper_raw.json",
    ])
    idx_path = _first_existing([
        args.index if args.index != "/files/temp/unified_timeline_index.json" else "",
        override_doc.get("index_path"),
        args.index,
    ]) or args.index
    audio_path = _first_existing([
        args.audio if args.audio != "/files/temp/audio.mp3" else "",
        override_doc.get("audio_path"),
        args.audio,
    ]) or args.audio
    audio_energy_path = _first_existing([
        args.audio_energy if args.audio_energy != "/files/temp/audio_energy.json" else "",
        override_doc.get("audio_energy_path"),
        args.audio_energy,
    ]) or args.audio_energy
    face_path = _first_existing([
        args.face if args.face != "/files/temp/face_emotions.json" else "",
        override_doc.get("face_path"),
        args.face,
    ]) or args.face
    chat_path = _first_existing([
        args.chat,
        override_doc.get("chat_path"),
        "/files/temp/chat_laughter_clusters.json",
        "/files/temp/chat_analysis.json",
        "/files/temp/test_zscore_out.json",
    ])

    transcript_doc = _load_json(tx_path) or {}
    index_doc = _load_json(idx_path) or {}
    cam_cfg = _load_json(args.cam) or {}
    audio_energy_doc = _load_json(audio_energy_path) or {}
    chat_doc = _load_json(chat_path) or {}
    face_doc = _load_json(face_path) or {}

    tx_dur = float(transcript_doc.get("duration") or index_doc.get("duration") or index_doc.get("stream_duration_sec") or 0.0)
    aud_dur = _probe_duration(audio_path)
    video_hint = args.video or override_doc.get("video_path") or ""
    if video_hint and os.path.exists(video_hint):
        video_path = video_hint
    elif not args.skip_grids:
        video_path = _auto_discover_video(tx_dur or aud_dur)
    else:
        video_path = ""
    vid_dur = _probe_duration(video_path) if video_path else 0.0
    if not video_hint and video_path and tx_dur > 0 and vid_dur > 0 and abs(vid_dur - tx_dur) > max(30.0, 0.25 * max(vid_dur, tx_dur)):
        video_path = ""
        vid_dur = 0.0
    active_stream = os.path.basename(video_path) if video_path else os.path.basename(tx_path or "")

    # Fix 1.1: Validate cached telemetry against active stream_file header & purge mismatched caches
    if active_stream and video_path:
        for nm_doc, p_doc, is_chat in (
            ("chat", chat_path, True),
            ("audio_energy", audio_energy_path, False),
            ("face", face_path, False),
        ):
            cur_d = chat_doc if nm_doc == "chat" else (audio_energy_doc if nm_doc == "audio_energy" else face_doc)
            if isinstance(cur_d, dict) and cur_d:
                cached_sf = os.path.basename(str(cur_d.get("stream_file") or "").strip())
                if cached_sf and cached_sf != active_stream:
                    if nm_doc == "chat":
                        chat_doc = {}
                    elif nm_doc == "audio_energy":
                        audio_energy_doc = {}
                    else:
                        face_doc = {}
                    if is_chat and p_doc and os.path.exists(p_doc):
                        try:
                            os.remove(p_doc)
                        except Exception:
                            pass

    # Standalone raw .live_chat.json scan if chat_doc is empty
    if not chat_doc and active_stream and os.path.isdir("/files/inputs"):
        stem = re.sub(r"^\d+_top_", "", re.sub(r"(\.processing)?\.mp4$", "", active_stream, flags=re.I), flags=re.I)
        pref = re.sub(r"[^a-z0-9]", "", stem.lower())[:14]
        for fn in sorted(os.listdir("/files/inputs")):
            if fn.endswith((".live_chat.json", ".chat.json")):
                f_pref = re.sub(r"[^a-z0-9]", "", re.sub(r"^\d+_top_", "", fn, flags=re.I).lower())[:14]
                if pref and (pref in f_pref or f_pref in pref):
                    try:
                        from chat_analyzer import analyze_chat
                        chat_doc = analyze_chat(os.path.join("/files/inputs", fn)) or {}
                    except Exception:
                        chat_doc = {}
                    break

    # Cross-stream duration mismatch guard: never pair unrelated default /files/temp/audio.mp3 or index
    if tx_dur > 0:
        idx_dur = float(index_doc.get("duration") or index_doc.get("stream_duration_sec") or 0.0)
        if not idx_dur and index_doc.get("annotated_sentences"):
            idx_dur = max(float(s.get("end", 0.0)) for s in index_doc["annotated_sentences"])
        if idx_dur > 0 and abs(idx_dur - tx_dur) > max(30.0, 0.25 * max(idx_dur, tx_dur)):
            index_doc = {}
        if aud_dur > 0 and args.audio == "/files/temp/audio.mp3" and not override_doc.get("audio_path") and abs(aud_dur - tx_dur) > max(30.0, 0.25 * max(aud_dur, tx_dur)):
            aud_dur = 0.0
            audio_energy_doc = {}
        if face_doc and args.face == "/files/temp/face_emotions.json" and not override_doc.get("face_path") and tx_dur > 400 and not video_path:
            face_doc = {}

    # Clamp effective timeline to overlapping duration so FFmpeg never seeks past EOF
    durs = [d for d in (vid_dur, aud_dur, tx_dur) if d > 0]
    duration = min(vid_dur, max(tx_dur, aud_dur)) if (vid_dur > 0 and (tx_dur > 0 or aud_dur > 0)) else (max(durs) if durs else 120.0)

    slice_lo = args.slice_start if args.slice_start is not None else override_doc.get("slice_start_sec")
    slice_hi = args.slice_end if args.slice_end is not None else override_doc.get("slice_end_sec")
    slice_span = duration
    if slice_lo is not None or slice_hi is not None:
        s_lo = max(0.0, float(slice_lo or 0.0))
        s_hi = min(duration, float(slice_hi or duration))
        slice_span = max(60.0, s_hi - s_lo)
    else:
        s_lo, s_hi = 0.0, duration

    audio_info = extract_1s_audio_features(audio_path if os.path.exists(audio_path) and aud_dur > 0 else "", audio_energy_doc, duration)
    chat_info = compute_chat_lag_map(chat_doc, int(duration) + 1)
    heatmap_info = compute_heatmap_map(video_path, duration, info_path=args.info_json)
    face_info = compute_face_motion_map(face_doc, cam_cfg)
    sentences = tag_speaker_roles(build_sentences_from_whisper(transcript_doc, index_doc), audio_info, face_info)

    # Filter sentences inside requested iteration time slice cleanly
    if slice_lo is not None or slice_hi is not None:
        sentences = [s for s in sentences if s["end"] >= s_lo and s["start"] <= s_hi]
        # Shift audio bins/raw_bins? Keep original timeline coordinates & zero V(t) outside slice cleanly!
        for sec_k in list((audio_info.get("raw_bins") or {}).keys()):
            if sec_k < int(s_lo) or sec_k > int(s_hi):
                del audio_info["raw_bins"][sec_k]

    adap_k, rec_min_clips, rec_max_clips = get_adaptive_clip_targets(slice_span)
    eff_top_k = args.top_k if args.top_k > 0 else adap_k

    raw_candidates = extract_top_candidates(
        s_hi if (slice_lo is not None or slice_hi is not None) else duration,
        sentences, audio_info, chat_info, face_info,
        top_k=eff_top_k + 4,
        slice_lo=s_lo if (slice_lo is not None or slice_hi is not None) else None,
        slice_hi=s_hi if (slice_lo is not None or slice_hi is not None) else None,
        heatmap_info=heatmap_info,
    )
    if slice_lo is not None or slice_hi is not None:
        raw_candidates = [c for c in raw_candidates if c["window_start"] >= max(0.0, s_lo - 5.0) and c["window_end"] <= s_hi + 5.0]
    if args.min_virality > 0.0:
        raw_candidates = [
            c for c in raw_candidates
            if float(c.get("est_virality_10", 0.0)) >= args.min_virality
            and (int(c.get("multi_beat_count", 0)) >= 2 or float(c.get("heatmap_value", 0.0)) >= 0.55 or float(c.get("est_virality_10", 0.0)) >= args.min_virality + 0.5)
        ]

    os.makedirs(args.grid_dir, exist_ok=True)
    font_path = _pick_font()
    candidates = []
    if not args.skip_grids and video_path:
        active_batch = raw_candidates[:eff_top_k]
        reserves = raw_candidates[eff_top_k:]
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda c: render_3x3_grid(video_path, c, args.grid_dir, font_path), active_batch))
        for c in active_batch:
            cam_box_cfg = face_info.get("cam_box") if isinstance(face_info, dict) else None
            cam_act = _measure_webcam_activity(video_path, c["window_start"], c["window_end"], cam_box_cfg)
            c["webcam_activity"] = cam_act
            is_passive = cam_act < 0.50 and float(c.get("z_db", 0.0)) < 1.2
            is_static = bool(c.get("grid_path") and is_grid_mostly_static(c["grid_path"]))
            if is_static or is_passive:
                c["is_static_screen"] = is_static
                c["is_passive_silent"] = is_passive
                if reserves:
                    rep = reserves.pop(0)
                    render_3x3_grid(video_path, rep, args.grid_dir, font_path)
                    rep_act = _measure_webcam_activity(video_path, rep["window_start"], rep["window_end"], cam_box_cfg)
                    rep["webcam_activity"] = rep_act
                    if not (rep.get("grid_path") and is_grid_mostly_static(rep["grid_path"])) and not (rep_act < 0.50 and float(rep.get("z_db", 0.0)) < 1.2):
                        candidates.append(rep)
            else:
                candidates.append(c)
        if not candidates:
            candidates = active_batch
    else:
        candidates = raw_candidates[:eff_top_k]

    for idx, c in enumerate(candidates, start=1):
        c["rank"] = idx
        old_id = c.get("candidate_id")
        c["candidate_id"] = f"cand_{idx}"
        gp = c.get("grid_path", "")
        if gp and os.path.exists(gp) and old_id != c["candidate_id"]:
            new_gp = os.path.join(args.grid_dir, f"gta6_{c['candidate_id']}_grid.jpg")
            try:
                os.replace(gp, new_gp)
                c["grid_path"] = new_gp
            except Exception:
                pass

    payload = {
        "stream_file": active_stream,
        "video_path": video_path,
        "video_duration": round(vid_dur, 2),
        "effective_duration": round(slice_span, 2),
        "recommended_min_clips": rec_min_clips,
        "recommended_max_clips": rec_max_clips,
        "peak_spacing_sec": 45.0 if slice_span >= 1200.0 else 30.0,
        "heatmap_peaks_detected": int(heatmap_info.get("peak_count", 0)),
        "chunk_start_sec": float(heatmap_info.get("chunk_start_sec", 0.0)),
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
        "heatmap_peaks_detected": payload["heatmap_peaks_detected"],
        "candidate_count": len(candidates),
        "grids_rendered": sum(1 for c in candidates if c.get("grid_path")),
        "out": args.out,
    }))


if __name__ == "__main__":
    main()
