#!/usr/bin/env python3
"""
telemetry_fusion_indexer.py
---------------------------
Compresses 1-hour+ multimodal stream telemetry (Whisper transcript + speech cadence,
Audio dB RMS/scream peaks, Chat Z-score laughter bursts + Vision summaries, and Face ONNX emotions)
into a Unified Multimodal Timeline Index & Candidate Anchor Map.

Also writes standardized Sandbox cache artifacts to /files/temp/:
  - /files/temp/transcript.json
  - /files/temp/audio_energy.json
  - /files/temp/chat_laughter_clusters.json
  - /files/temp/face_emotions.json
  - /files/temp/unified_timeline_index.json
"""

import os
import sys
import json
import math
import re
import bisect
from collections import Counter

HALLUCINATION_PHRASES = [
    "roblox gaming",
    "lucky blocks",
    "divine mutation",
    "strawberry elephant",
    "taco combinacion",
    "10x luck",
    "streamer reacting",
    "gaming chaos",
    "grand theft auto vi",
    "vice city",
    "vice beach",
    "rockstar games",
    "npc chaos",
    "gta rp",
    "police chase",
    "thank you for watching",
    "thanks for watching",
    "subscribe and like",
]

BOAST_PATTERNS = re.compile(
    r"\b(watch this|easy|no way i lose|trust me|bet|i'm the best|i got this|cannot lose|never happens|guarantee|hold my|pro player|all of my games|admin abuse|i'm going to buy it|nobody can beat|if i die)\b",
    re.I,
)
MYSTERY_PATTERNS = re.compile(
    r"\b(wait what|what is that|who is|why did|how did|secret|hidden|glitch|weird|bro what|no shot|what happened|are you telling me|tricked me|fake account|am i blind|how many)\b",
    re.I,
)
HOUSEKEEPING_NOISE = re.compile(
    r"(thank you for the super\s*chat|for the super chat|get your entries in|enter you into the giveaway|type [a-z0-9]+ into the chat|friend request|let me search him up|make a [0-9,]+ game\s*pass|every giveaway we do|draw a winner|stops the bots|spam the word|thank you for the raid|thanks for the raid|welcome raiders|watch till the end of the stream|keep counter|we'?re going to say bye|ending the stream|see you next time)",
    re.I,
)
STOPWORDS = {
    "there", "their", "about", "which", "would", "could", "should", "really",
    "going", "gonna", "wanna", "thing", "things", "right", "think", "actually",
    "people", "someone", "something", "because", "before", "after", "these",
    "those", "where", "every", "wait", "dude", "guys", "chat", "bro", "yeah",
    "okay", "just", "like", "know", "what", "that", "this", "with", "from",
    "have", "they", "were", "been", "look", "here", "come", "make", "take",
    "happy", "crazy", "funny", "weird", "scared", "sorry", "today", "later",
    "started", "always", "never", "maybe", "pretty", "literally", "totally",
    "other", "everybody", "everyone", "anything", "nothing", "getting", "playing",
    "kind", "need", "want", "together", "relaxing", "tell", "good", "time",
    "little", "probably", "mean", "sure", "give", "said", "saying", "does", "didnt"
}


def format_mmss(seconds: float) -> str:
    s_tot = max(0.0, float(seconds))
    m = int(s_tot // 60)
    s = s_tot % 60
    return f"{m:02d}:{s:04.1f}"


def is_hallucinated_sentence(text: str) -> bool:
    low = text.lower().strip()
    if not low or low in {"music", "music.", "[music]", "you", "you."}:
        return True
    if "strawberry elephant" in low or "taco combinacion" in low:
        return True
    hits = sum(1 for p in HALLUCINATION_PHRASES if p in low)
    if hits >= 2:
        return True
    return False


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def load_whisper(transcript_path=None):
    candidates = [transcript_path] if transcript_path else []
    candidates.extend([
        "/files/temp/transcript.json",
        "/files/outputs/whisper_28754.json",
        "/files/temp/whisper_raw.json",
        "/files/outputs/whisper_28696.json",
        "/files/outputs/whisper_28759.json",
    ])
    p = _first_existing(candidates)
    if not p:
        return {"text": "", "words": [], "duration": 0.0, "source_path": None}
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    words = data.get("words") or (data.get("x_groq") or {}).get("words") or []
    dur = float(data.get("duration") or (words[-1].get("end", 0.0) if words else 0.0) or 0.0)
    return {
        "text": data.get("text", ""),
        "words": words,
        "duration": dur,
        "source_path": p,
    }


def load_audio_energy(audio_energy_path=None, return_meta=False):
    events = []
    audio_meta = {"median_rms_db": None, "std_rms_db": 6.0, "raw_bins": []}
    p_ae = _first_existing([audio_energy_path, "/files/temp/audio_energy.json"])
    if p_ae:
        try:
            with open(p_ae, "r", encoding="utf-8") as f:
                ae = json.load(f)
            if isinstance(ae, dict):
                if ae.get("peaks"):
                    events.extend(ae["peaks"])
                if ae.get("raw_bins"):
                    audio_meta["raw_bins"] = ae["raw_bins"]
                if ae.get("median_rms_db") is not None:
                    audio_meta["median_rms_db"] = float(ae["median_rms_db"])
                if ae.get("std_rms_db") is not None:
                    audio_meta["std_rms_db"] = float(ae["std_rms_db"])
            elif isinstance(ae, list):
                events.extend(ae)
        except Exception:
            pass

    if not events and os.path.exists("/files/temp/screams.json"):
        try:
            with open("/files/temp/screams.json", "r", encoding="utf-8") as f:
                sc = json.load(f)
            for item in sc:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    events.append({
                        "start": float(item[0]),
                        "end": float(item[1]),
                        "mid": round((float(item[0]) + float(item[1])) / 2.0, 2),
                        "jump_db": 10.5,
                        "percentile": 98,
                        "label": "SCREAM_OR_LAUGH_SPIKE",
                    })
                elif isinstance(item, dict) and "start" in item:
                    events.append(item)
        except Exception:
            pass

    if os.path.exists("/files/temp/enriched_transcript.json"):
        try:
            with open("/files/temp/enriched_transcript.json", "r", encoding="utf-8") as f:
                et = json.load(f)
            buckets = et.get("buckets") or []
            rms_vals = [float(b.get("rms_db", -30.0)) for b in buckets if "rms_db" in b]
            p95 = sorted(rms_vals)[int(0.95 * len(rms_vals))] if len(rms_vals) >= 20 else -12.0
            for b in buckets:
                jump = float(b.get("jump_db", 0.0))
                rms = float(b.get("rms_db", -30.0))
                if jump >= 6.0 or rms >= p95 or "SCREAM" in str(b.get("audio_tag", "")):
                    st = float(b.get("start", 0.0))
                    en = float(b.get("end", st + 2.0))
                    events.append({
                        "start": round(st, 2),
                        "end": round(en, 2),
                        "mid": round((st + en) / 2.0, 2),
                        "jump_db": round(max(jump, 8.0 if rms >= p95 else jump), 1),
                        "rms_db": round(rms, 1),
                        "percentile": 96 if rms >= p95 else 90,
                        "label": "dB_PEAK",
                    })
        except Exception:
            pass

    # Deduplicate close audio events within 3s
    events.sort(key=lambda x: x.get("start", 0.0))
    deduped = []
    for ev in events:
        if deduped and ev["start"] - deduped[-1]["start"] < 3.0:
            if ev.get("jump_db", 0) > deduped[-1].get("jump_db", 0):
                deduped[-1] = ev
        else:
            deduped.append(ev)
    if return_meta:
        return deduped, audio_meta
    return deduped


def _resolve_active_stream(stream_file=None):
    if stream_file:
        return os.path.basename(str(stream_file).strip())
    for p in ("/files/temp/active_stream.txt",):
        if os.path.exists(p):
            try:
                v = open(p, "r", encoding="utf-8").read().strip()
                if v:
                    return os.path.basename(v)
            except Exception:
                pass
    try:
        if os.path.exists("/files/inputs"):
            for f in sorted(os.listdir("/files/inputs")):
                if f.endswith(".processing.mp4"):
                    return f
    except Exception:
        pass
    return ""


def _validate_cache_stream(doc, file_path, active_stream, require_header=False):
    if not isinstance(doc, dict):
        return False
    cached = os.path.basename(str(doc.get("stream_file") or "").strip())
    if active_stream:
        if require_header and not cached:
            try:
                os.remove(file_path)
            except Exception:
                pass
            return False
        if cached and cached != active_stream:
            try:
                os.remove(file_path)
            except Exception:
                pass
            return False
    return True


def _has_matching_live_chat(active_stream):
    if not active_stream or not os.path.isdir("/files/inputs"):
        return True  # Cannot verify when active_stream unknown
    stem = re.sub(r"(\.processing)?\.mp4$", "", active_stream, flags=re.I)
    prefix = re.sub(r"[^a-z0-9]", "", stem.lower())[:14]
    for fn in os.listdir("/files/inputs"):
        if fn.endswith((".live_chat.json", ".chat.json")):
            f_pref = re.sub(r"[^a-z0-9]", "", fn.lower())[:14]
            if prefix and (prefix in f_pref or f_pref in prefix):
                return True
    return False


def load_chat_clusters(chat_path=None, active_stream=""):
    default_chat_p = "/files/temp/chat_laughter_clusters.json"
    p = _first_existing([
        chat_path,
        default_chat_p,
        "/files/temp/chat_analysis.json",
        "/files/temp/test_zscore_out.json",
    ])
    clusters = []
    beats_by_t = {}

    if active_stream and not _has_matching_live_chat(active_stream):
        # No live_chat file exists for current VOD: purge stale cache files
        for stale_p in (default_chat_p, "/files/temp/chat_analysis.json", "/files/temp/comedic_beats.json"):
            if os.path.exists(stale_p):
                try:
                    os.remove(stale_p)
                except Exception:
                    pass
        if not chat_path:
            return []

    if os.path.exists("/files/temp/comedic_beats.json"):
        try:
            with open("/files/temp/comedic_beats.json", "r", encoding="utf-8") as f:
                cb = json.load(f)
            if _validate_cache_stream(cb, "/files/temp/comedic_beats.json", active_stream, require_header=True):
                for b in cb.get("comedic_beats") or cb.get("beats") or []:
                    t = round(float(b.get("peak_laugh_time", 0.0)), 1)
                    beats_by_t[t] = b
        except Exception:
            pass

    if p:
        try:
            with open(p, "r", encoding="utf-8") as f:
                cd = json.load(f)
            if p == default_chat_p and not _validate_cache_stream(cd, p, active_stream, require_header=True):
                return []
            if not _validate_cache_stream(cd, p, active_stream, require_header=False):
                return []
            raw = cd.get("clusters") or cd.get("top_clusters") or []
            for c in raw:
                pt = float(c.get("peak_time", 0.0))
                matched_b = None
                for bt, bobj in beats_by_t.items():
                    if abs(bt - pt) <= 5.0:
                        matched_b = bobj
                        break
                item = dict(c)
                if matched_b:
                    item["why_chat_laughed"] = matched_b.get("why_chat_laughed", "")
                    item["comedy_mechanism"] = matched_b.get("comedy_mechanism", "")
                    item["setup_tension_hook"] = matched_b.get("setup_tension_hook", "")
                    item["is_multi_beat"] = matched_b.get("is_multi_beat", False)
                    item["beat_2"] = matched_b.get("beat_2")
                clusters.append(item)
        except Exception:
            pass

    return clusters


def load_face_emotions(face_path=None, return_samples=False):
    p = _first_existing([
        face_path,
        "/files/temp/face_emotions.json",
        "/files/inputs/kreek_face_test.json",
    ])
    events = []
    samples = []
    if not p:
        return (events, samples) if return_samples else events
    try:
        with open(p, "r", encoding="utf-8") as f:
            fd = json.load(f)
        samples = fd.get("samples") or []
        for ev in fd.get("top_events") or []:
            events.append({
                "start": float(ev.get("start", 0.0)),
                "end": float(ev.get("end", 0.0)),
                "dominant": ev.get("dominant", "reaction"),
                "face_tag": ev.get("face_tag", ""),
                "intensity": float(ev.get("peak_intensity", ev.get("intensity", 70.0))),
                "mouth_motion": float(ev.get("mouth_motion", 0.0)),
            })
        if not events:
            for s in samples:
                inten = float(s.get("intensity", 0.0))
                if inten >= 55.0 or s.get("face_tag") == "FACE:DEADPAN_STARE":
                    dom = "joy" if s.get("joy", 0) >= s.get("surprise", 0) else "surprise"
                    events.append({
                        "start": float(s.get("time", 0.0)),
                        "end": float(s.get("time", 0.0)) + 1.5,
                        "dominant": dom,
                        "face_tag": s.get("face_tag", ""),
                        "intensity": inten,
                        "mouth_motion": float(s.get("mouth_motion", 0.0)),
                    })
    except Exception:
        pass
    if return_samples:
        return events, samples
    return events


def build_sentences_with_cadence(words: list):
    sentences = []
    if not words:
        return sentences

    curr_words = []
    curr_start = None
    curr_end = None

    for w in words:
        token = str(w.get("word", ""))
        st = float(w.get("start", 0.0))
        en = float(w.get("end", st + 0.2))
        if curr_start is None:
            curr_start = st
        elif st - curr_end >= 2.2 or len(curr_words) >= 18:
            text = " ".join(curr_words).strip()
            if not is_hallucinated_sentence(text):
                dur = max(0.3, curr_end - curr_start)
                wpm = (len(curr_words) / dur) * 60.0
                sentences.append({
                    "start": round(curr_start, 2),
                    "end": round(curr_end, 2),
                    "text": re.sub(r"\s+", " ", text),
                    "word_count": len(curr_words),
                    "wpm": round(wpm, 1),
                    "pause_after": round(max(0.0, st - curr_end), 2),
                })
            curr_words = []
            curr_start = st

        curr_words.append(token.strip())
        curr_end = en

        if re.search(r"[.!?]$", token.strip()) and len(curr_words) >= 6:
            text = " ".join(curr_words).strip()
            if not is_hallucinated_sentence(text):
                dur = max(0.3, curr_end - curr_start)
                wpm = (len(curr_words) / dur) * 60.0
                sentences.append({
                    "start": round(curr_start, 2),
                    "end": round(curr_end, 2),
                    "text": re.sub(r"\s+", " ", text),
                    "word_count": len(curr_words),
                    "wpm": round(wpm, 1),
                    "pause_after": 0.0,
                })
            curr_words = []
            curr_start = None

    if curr_words:
        text = " ".join(curr_words).strip()
        if not is_hallucinated_sentence(text):
            dur = max(0.3, curr_end - curr_start)
            sentences.append({
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "text": re.sub(r"\s+", " ", text),
                "word_count": len(curr_words),
                "wpm": round((len(curr_words) / dur) * 60.0, 1),
                "pause_after": 0.0,
            })

    # Update pause_after accurately between kept sentences
    for i in range(len(sentences) - 1):
        gap = sentences[i + 1]["start"] - sentences[i]["end"]
        sentences[i]["pause_after"] = round(max(0.0, gap), 2)

    return sentences


def build_unified_index(
    transcript_path=None,
    audio_energy_path=None,
    chat_path=None,
    face_path=None,
    output_dir="/files/temp",
    top_k=20,
    save_cache=True,
    stream_file=None,
):
    active_stream = _resolve_active_stream(stream_file)
    whisper = load_whisper(transcript_path)
    audio_peaks, audio_meta = load_audio_energy(audio_energy_path, return_meta=True)
    chat_clusters = load_chat_clusters(chat_path, active_stream=active_stream)
    face_events, face_samples = load_face_emotions(face_path, return_samples=True)

    sentences = build_sentences_with_cadence(whisper["words"])
    duration = whisper["duration"] or (sentences[-1]["end"] if sentences else 3600.0)

    # Pre-index raw audio RMS bins & face motion samples for fast O(log N) lookup
    raw_bins = sorted(audio_meta.get("raw_bins") or [], key=lambda x: x.get("t", 0.0))
    raw_bin_times = [float(b.get("t", 0.0)) for b in raw_bins]
    streamer_med_db = audio_meta.get("median_rms_db")

    # Estimate true per-stream mean and std RMS dB for unbiased Z-score peak classification
    valid_dbs = [float(b.get("db", -30.0)) for b in raw_bins if float(b.get("db", -90.0)) > -70.0]
    if streamer_med_db is None and valid_dbs:
        vals = sorted(valid_dbs)
        streamer_med_db = vals[len(vals) // 2]
    stream_mean_db = (sum(valid_dbs) / len(valid_dbs)) if valid_dbs else (streamer_med_db if streamer_med_db is not None else -28.0)
    stream_std_db = float(audio_meta.get("std_rms_db") or 6.0)
    if len(valid_dbs) >= 10:
        calc_std = math.sqrt(sum((x - stream_mean_db) ** 2 for x in valid_dbs) / len(valid_dbs))
        stream_std_db = max(2.5, calc_std, stream_std_db)

    face_samples_sorted = sorted(face_samples, key=lambda x: float(x.get("time", 0.0)))
    face_sample_times = [float(s.get("time", 0.0)) for s in face_samples_sorted]
    motion_vals = sorted(float(s.get("mouth_motion", 0.0)) for s in face_samples_sorted if s.get("mouth_motion") is not None)
    med_mouth_motion = motion_vals[len(motion_vals) // 2] if len(motion_vals) >= 10 else 0.0

    # Baseline WPM stats for Z_wpm calculation
    wpm_list = [float(s["wpm"]) for s in sentences if s.get("word_count", 0) >= 3]
    mean_wpm = (sum(wpm_list) / len(wpm_list)) if wpm_list else 150.0
    std_wpm = max(25.0, math.sqrt(sum((x - mean_wpm) ** 2 for x in wpm_list) / max(1, len(wpm_list))) if wpm_list else 40.0)

    # Compute lagged chat lookup sorted by peak_time (chat lags stream event t by 3.0s..8.0s, center Δ_lag = 5.5s)
    chat_sorted = sorted(chat_clusters, key=lambda c: float(c.get("peak_time", 0.0)))
    chat_times = [float(c.get("peak_time", 0.0)) for c in chat_sorted]

    def _window_audio_stats(st_t, en_t):
        if not raw_bins:
            return None, 0.0
        lo = bisect.bisect_left(raw_bin_times, st_t - 0.5)
        hi = bisect.bisect_right(raw_bin_times, en_t + 0.5)
        slice_b = raw_bins[lo:hi]
        if not slice_b:
            return None, 0.0
        dbs = [float(b.get("db", -40.0)) for b in slice_b]
        zdbs = [float(b.get("z_db", 0.0)) for b in slice_b]
        return sum(dbs) / len(dbs), max(zdbs)

    def _window_face_motion(st_t, en_t):
        if not face_samples_sorted:
            return None, None
        lo = bisect.bisect_left(face_sample_times, st_t - 0.8)
        hi = bisect.bisect_right(face_sample_times, en_t + 0.8)
        slice_f = face_samples_sorted[lo:hi]
        if not slice_f:
            return None, None
        avg_m = sum(float(f.get("mouth_motion", 0.0)) for f in slice_f) / len(slice_f)
        best_f = max(slice_f, key=lambda f: float(f.get("intensity", 0.0)))
        return avg_m, best_f

    SHOCK_TOKENS_RE = re.compile(r"\b(wtf|ayo|bro|clip\s+it|no\s+way|omg|wait\s+what)\b", re.I)

    # Annotate sentences with inline multimodal telemetry tags
    annotated_lines = []
    for s in sentences:
        st, en = s["start"], s["end"]
        tags = []
        z_wpm = (float(s["wpm"]) - mean_wpm) / std_wpm if s["word_count"] >= 3 else 0.0
        s["z_wpm"] = round(z_wpm, 2)
        if (s["wpm"] >= 210 or z_wpm >= 1.5) and s["word_count"] >= 5:
            tags.append(f"[WPM_SPIKE: {int(s['wpm'])}wpm]")
        if 1.2 <= s["pause_after"] <= 6.0:
            tags.append(f"[DRAMATIC_PAUSE: {s['pause_after']:.1f}s]")

        avg_db, max_z_db = _window_audio_stats(st, en)
        matched_audio = [a for a in audio_peaks if a["start"] <= en + 2.0 and a.get("end", a["start"] + 1.5) >= st - 2.0]
        if matched_audio:
            best_a = max(matched_audio, key=lambda x: float(x.get("z_db", x.get("jump_db", 0.0) / stream_std_db)))
            jmp = float(best_a.get("jump_db", 0.0))
            true_z = float(best_a.get("z_db") if best_a.get("z_db") is not None else ((avg_db - stream_mean_db) / stream_std_db if avg_db is not None else jmp / stream_std_db))
            true_z = max(true_z, max_z_db)
            if true_z >= 2.8:
                tags.append(f"[SCREAM:Z={true_z:.1f}|+{jmp:.1f}dB]")
            elif true_z >= 2.0 or jmp >= 6.5:
                tags.append(f"[dB_PEAK:Z={true_z:.1f}|+{jmp:.1f}dB]")
        elif max_z_db >= 2.8:
            jmp_est = max_z_db * stream_std_db
            tags.append(f"[SCREAM:Z={max_z_db:.1f}|+{jmp_est:.1f}dB]")
        elif max_z_db >= 2.0:
            jmp_est = max_z_db * stream_std_db
            tags.append(f"[dB_PEAK:Z={max_z_db:.1f}|+{jmp_est:.1f}dB]")

        # Viewer / In-game voice detection: speech present, but low raw RMS or zero webcam mouth motion
        is_viewer_voice = False
        if s["word_count"] >= 3:
            low_rms_voice = (avg_db is not None and streamer_med_db is not None and avg_db < (streamer_med_db - 4.5))
            avg_mouth_m, best_sample_f = _window_face_motion(st, en)
            static_mouth = (avg_mouth_m is not None and med_mouth_motion > 0.015 and avg_mouth_m < (med_mouth_motion * 0.35))
            if low_rms_voice or static_mouth:
                is_viewer_voice = True
                tags.append("[VIEWER_OR_GAME_VOICE]")
        s["is_viewer_voice"] = is_viewer_voice

        # Latency-compensated live chat alignment: event at [st, en] aligns with chat peak in [st + 3.0s, en + 8.0s] (Δ_lag = 5.5s)
        c_lo = bisect.bisect_left(chat_times, max(0.0, st + 3.0))
        c_hi = bisect.bisect_right(chat_times, en + 8.0)
        matched_chat = chat_sorted[c_lo:c_hi]
        if not matched_chat:
            # Fallback narrow window around event center + Δ_lag=5.5s
            target_t = en + 5.5
            matched_chat = [c for c in chat_sorted if abs(float(c.get("peak_time", 0.0)) - target_t) <= 3.5]
        if matched_chat:
            best_c = max(matched_chat, key=lambda x: float(x.get("z_score", 0.0)))
            raw_msgs = best_c.get("sample_messages") or []
            snips = ", ".join(f'"{m}"' for m in raw_msgs[:2])
            laugh_pct = round(float(best_c.get("laugh_ratio", 0)) * 100)
            if laugh_pct >= 30:
                tags.append("[LAUGH_BURST]")
            elif any(SHOCK_TOKENS_RE.search(str(m)) for m in raw_msgs):
                tags.append("[CHAT_SHOCK]")
            tags.append(f"[CHAT_BURST: Z={best_c.get('z_score', 2.5)} | {snips}]" if snips else f"[CHAT_BURST: Z={best_c.get('z_score', 2.5)}]")

        # Streamer facecam expression delta tag
        matched_face = [f for f in face_events if f["start"] <= en + 2.0 and f["end"] >= st - 2.0]
        if matched_face:
            best_f = max(matched_face, key=lambda x: float(x.get("intensity", 0.0)))
            ftag = best_f.get("face_tag")
            if ftag and ftag != "FACE:NEUTRAL":
                tags.append(f"[{ftag}]")
            else:
                tags.append(f"[FACE:{str(best_f.get('dominant', 'reaction')).upper()}]")

        tag_str = (" " + " ".join(tags)) if tags else ""
        line_str = f"[{st:.1f}s - {en:.1f}s | {format_mmss(st)}]{tag_str} {s['text']}"
        s["tags"] = tags
        s["annotated_line"] = line_str
        annotated_lines.append(s)

    # ── Composite Multimodal Virality Score V(t) at 1-second resolution ─────
    # V(t) = 0.25*max_{u in [t-1,t+1]} Z_dB(u) + 0.30*max_{u in [t+3,t+8]} Z_chat(u)
    #      + 0.20*Z_face(t) + 0.15*Z_wpm(t) + 0.10*I_viewer(t-3, t)
    num_sec = max(1, int(math.ceil(duration)))
    z_db_sec = [0.0] * num_sec
    z_chat_sec = [0.0] * num_sec
    z_face_sec = [0.0] * num_sec
    z_wpm_sec = [0.0] * num_sec
    i_viewer_sec = [0.0] * num_sec
    sec_audio = [None] * num_sec
    sec_chat = [None] * num_sec
    sec_face = [None] * num_sec
    sec_sents = [[] for _ in range(num_sec)]

    for b in raw_bins:
        sec_i = min(num_sec - 1, max(0, int(round(float(b.get("t", 0.0))))))
        zv = max(0.0, float(b.get("z_db", 0.0)))
        if zv > z_db_sec[sec_i]:
            z_db_sec[sec_i] = zv

    for a in audio_peaks:
        st_s = min(num_sec - 1, max(0, int(float(a.get("start", 0.0)))))
        en_s = min(num_sec - 1, max(st_s, int(float(a.get("end", st_s + 1.5)))))
        zv = max(2.2, float(a.get("z_db", float(a.get("jump_db", 8.0)) / 3.5)))
        for u in range(st_s, en_s + 1):
            if zv > z_db_sec[u]:
                z_db_sec[u] = zv
            sec_audio[u] = a

    for c in chat_sorted:
        pt = float(c.get("peak_time", 0.0))
        zv = max(0.0, float(c.get("z_score", 2.5)))
        for u in range(max(0, int(pt - 2)), min(num_sec, int(pt + 3))):
            if zv > z_chat_sec[u]:
                z_chat_sec[u] = zv
                sec_chat[u] = c

    face_intens = [float(fe.get("intensity", 50.0)) for fe in face_events] or [50.0]
    mean_fi = sum(face_intens) / len(face_intens)
    std_fi = max(15.0, math.sqrt(sum((x - mean_fi) ** 2 for x in face_intens) / len(face_intens)))
    for fe in face_events:
        st_s = min(num_sec - 1, max(0, int(float(fe.get("start", 0.0)))))
        en_s = min(num_sec - 1, max(st_s, int(float(fe.get("end", st_s + 1.5)))))
        zv = max(0.0, (float(fe.get("intensity", 60.0)) - 35.0) / std_fi)
        for u in range(st_s, en_s + 1):
            if zv > z_face_sec[u]:
                z_face_sec[u] = zv
                sec_face[u] = fe

    penalty_sec = [0.0] * num_sec
    bonus_sec = [0.0] * num_sec
    for s in annotated_lines:
        st_s = min(num_sec - 1, max(0, int(s["start"])))
        en_s = min(num_sec - 1, max(st_s, int(s["end"])))
        sec_sents[st_s].append(s)
        zv_wpm = max(0.0, float(s.get("z_wpm", 0.0)))
        for u in range(st_s, en_s + 1):
            if zv_wpm > z_wpm_sec[u]:
                z_wpm_sec[u] = zv_wpm
            if s.get("is_viewer_voice"):
                i_viewer_sec[u] = 1.0
            if HOUSEKEEPING_NOISE.search(s["text"]):
                penalty_sec[u] = max(penalty_sec[u], 2.5)
            elif BOAST_PATTERNS.search(s["text"]) or MYSTERY_PATTERNS.search(s["text"]):
                bonus_sec[u] = max(bonus_sec[u], 0.45)

    v_scores = []
    for t in range(num_sec):
        max_db = max(z_db_sec[max(0, t - 1):min(num_sec, t + 2)])
        chat_slice = z_chat_sec[min(num_sec - 1, t + 3):min(num_sec, t + 9)]
        max_chat = max(chat_slice) if chat_slice else 0.0
        max_face = z_face_sec[t]
        max_wpm = z_wpm_sec[t]
        iv_slice = i_viewer_sec[max(0, t - 3):min(num_sec, t + 1)]
        i_viewer = 1.0 if (iv_slice and max(iv_slice) > 0.0) else 0.0
        vt = (0.25 * max_db) + (0.30 * max_chat) + (0.20 * max_face) + (0.15 * max_wpm) + (0.10 * i_viewer) + bonus_sec[t] - penalty_sec[t]
        v_scores.append((t, vt))

    v_scores.sort(key=lambda x: x[1], reverse=True)

    # Compute document frequency for rare keyword detection in callback matching
    df_counts = Counter()
    for s in annotated_lines:
        uniq = set(w.lower() for w in re.findall(r"[a-zA-Z]{5,}", s["text"]) if w.lower() not in STOPWORDS)
        for u in uniq:
            df_counts[u] += 1

    max_v = v_scores[0][1] if v_scores and v_scores[0][1] > 0 else 3.0

    # Extract top_k=20 non-overlapping anchors (min 40s apart), each with ±45s surrounding context window
    anchors = []
    used_times = []
    for t_sec, v_val in v_scores:
        if v_val <= 0.15 and len(anchors) >= min(6, top_k):
            break
        t_mid = float(t_sec)
        if any(abs(t_mid - ut) < 40.0 for ut in used_times):
            continue

        # ±45s surrounding context window
        win_sents = [s for s in annotated_lines if (t_mid - 45.0) <= s["start"] <= (t_mid + 45.0)]
        if not win_sents and sentences:
            continue

        a_start = round(max(0.0, win_sents[0]["start"] if win_sents else t_mid - 45.0), 1)
        a_end = round(min(duration, (win_sents[-1]["end"] + 2.0) if win_sents else t_mid + 45.0), 1)
        snippet_text = " ".join(s["text"] for s in win_sents if abs(s["start"] - t_mid) <= 20.0)[:380] or (" ".join(s["text"] for s in win_sents)[:380])

        # Inspect lagged chat, audio & face hits around t_mid
        c_hit = None
        best_cz = -1.0
        for u in range(min(num_sec - 1, int(t_mid + 3)), min(num_sec, int(t_mid + 9))):
            if sec_chat[u] and float(sec_chat[u].get("z_score", 0.0)) > best_cz:
                best_cz = float(sec_chat[u].get("z_score", 0.0))
                c_hit = sec_chat[u]
        a_hit = next((sec_audio[u] for u in range(max(0, int(t_mid - 2)), min(num_sec, int(t_mid + 3))) if sec_audio[u]), None)
        f_hit = next((sec_face[u] for u in range(max(0, int(t_mid - 2)), min(num_sec, int(t_mid + 3))) if sec_face[u]), None)
        viewer_in_win = any(s.get("is_viewer_voice") for s in win_sents if abs(s["start"] - t_mid) <= 15.0)

        # Callback scanner across whole VOD for rare recurring keywords (2 <= df <= 12)
        toks = [w.lower() for w in re.findall(r"[a-zA-Z]{5,}", snippet_text) if w.lower() not in STOPWORDS and 2 <= df_counts.get(w.lower(), 0) <= 12]
        rare_keys = [k for k, _ in Counter(toks).most_common(3)]
        callbacks = []
        if rare_keys:
            for other in annotated_lines:
                if abs(other["start"] - t_mid) > 45.0 and len(other["tags"]) > 0:
                    olow = other["text"].lower()
                    matched_kw = [rk for rk in rare_keys if rk in olow]
                    if matched_kw:
                        callbacks.append({
                            "time": other["start"],
                            "tc": format_mmss(other["start"]),
                            "keyword": matched_kw[0],
                            "text": other["text"][:120],
                        })
                        if len(callbacks) >= 2:
                            break

        # Recommend from the 6 Structural Archetype Blueprints
        arch_slot = len(anchors) % 6
        if viewer_in_win:
            rec_arch = "VIEWER_OR_CHAT_ROAST_INTERACTION"
        elif BOAST_PATTERNS.search(snippet_text):
            rec_arch = "HUBRIS_WAGER_INSTANT_KARMA"
        elif f_hit and f_hit.get("face_tag") == "FACE:SHOCK_OR_SCREAM":
            rec_arch = "EMOTIONAL_SHOCK_OR_BETRAYAL"
        elif callbacks or MYSTERY_PATTERNS.search(snippet_text):
            rec_arch = "FLASHFORWARD_MYSTERY_INVESTIGATION"
        elif a_hit and float(a_hit.get("jump_db", 0.0)) >= 9.0:
            rec_arch = "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL"
        else:
            rec_arch = [
                "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
                "VIEWER_OR_CHAT_ROAST_INTERACTION",
                "HUBRIS_WAGER_INSTANT_KARMA",
                "COMEDIC_STORYTELLING_OR_SARCASM",
                "FLASHFORWARD_MYSTERY_INVESTIGATION",
                "EMOTIONAL_SHOCK_OR_BETRAYAL",
            ][arch_slot]

        norm_score = round(min(99.5, max(35.0, 40.0 + (max(0.0, v_val) / max_v) * 58.0)), 1)

        anchors.append({
            "anchor_id": len(anchors) + 1,
            "start": a_start,
            "end": a_end,
            "peak_time": round(t_mid, 1),
            "peak_tc": format_mmss(t_mid),
            "duration": round(a_end - a_start, 1),
            "virality_score": norm_score,
            "raw_v_score": round(v_val, 3),
            "recommended_archetype": rec_arch,
            "viewer_voice_present": viewer_in_win,
            "chat_signal": (
                f"Z={c_hit.get('z_score')}σ ({round(c_hit.get('laugh_ratio', 0)*100)}% Laugh) | \"{', '.join((c_hit.get('sample_messages') or [])[:2])}\""
                if c_hit else "Transcript/Audio/Emotion driven spike"
            ),
            "face_signal": (
                f"{f_hit.get('face_tag', f_hit['dominant'])} ({int(f_hit['intensity'])}% intensity)"
                if f_hit else "Active webcam/reaction"
            ),
            "audio_signal": (
                f"+{a_hit.get('jump_db', 8.0)}dB vocal peak at {format_mmss(a_hit.get('start', t_mid))}"
                if a_hit else "High WPM / dramatic vocal cadence"
            ),
            "why_chat_laughed": (c_hit or {}).get("why_chat_laughed", ""),
            "comedy_mechanism": (c_hit or {}).get("comedy_mechanism", rec_arch),
            "setup_tension_hook": (c_hit or {}).get("setup_tension_hook", format_mmss(max(0.0, t_mid - 2.0))),
            "is_multi_beat": bool((c_hit or {}).get("is_multi_beat") or callbacks),
            "beat_2": (c_hit or {}).get("beat_2"),
            "callback_links": callbacks,
            "transcript_snippet": snippet_text,
            "annotated_context": "\n".join(s["annotated_line"] for s in win_sents),
        })
        used_times.append(t_mid)
        if len(anchors) >= top_k:
            break

    # Build compact macro timeline summary string summarizing high-signal moments across full VOD
    high_signal_lines = [s["annotated_line"] for s in annotated_lines if s["tags"]]
    if len(high_signal_lines) < 30:
        step_pick = max(1, len(annotated_lines) // 60)
        sampled = [annotated_lines[i]["annotated_line"] for i in range(0, len(annotated_lines), step_pick)]
        macro_lines = list(dict.fromkeys(high_signal_lines + sampled))
    else:
        macro_lines = high_signal_lines[:150]

    index_doc = {
        "status": "success",
        "stream_file": active_stream,
        "source_whisper": whisper["source_path"],
        "stream_duration_sec": round(duration, 1),
        "total_sentences": len(sentences),
        "audio_peaks_count": len(audio_peaks),
        "chat_clusters_count": len(chat_clusters),
        "face_events_count": len(face_events),
        "anchors_count": len(anchors),
        "anchors": anchors,
        "macro_high_signal_timeline": "\n".join(macro_lines),
        "annotated_sentences": annotated_lines,
    }

    if save_cache and output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "unified_timeline_index.json"), "w", encoding="utf-8") as f:
            json.dump(index_doc, f, indent=2)

        ae_out = {"stream_file": active_stream, "peaks": audio_peaks, "count": len(audio_peaks)}
        if audio_meta.get("median_rms_db") is not None:
            ae_out["median_rms_db"] = audio_meta["median_rms_db"]
            ae_out["mean_rms_db"] = round(stream_mean_db, 2)
            ae_out["std_rms_db"] = round(stream_std_db, 2)
        if audio_meta.get("raw_bins"):
            ae_out["raw_bins"] = audio_meta["raw_bins"]
        with open(os.path.join(output_dir, "audio_energy.json"), "w", encoding="utf-8") as f:
            json.dump(ae_out, f, indent=2)

        if chat_clusters:
            with open(os.path.join(output_dir, "chat_laughter_clusters.json"), "w", encoding="utf-8") as f:
                json.dump({"stream_file": active_stream, "clusters": chat_clusters, "count": len(chat_clusters)}, f, indent=2)

        fe_out = {"stream_file": active_stream, "top_events": face_events, "count": len(face_events)}
        if face_samples:
            fe_out["samples"] = face_samples
        with open(os.path.join(output_dir, "face_emotions.json"), "w", encoding="utf-8") as f:
            json.dump(fe_out, f, indent=2)

        tx_out = os.path.join(output_dir, "transcript.json")
        if not os.path.exists(tx_out) and whisper["words"]:
            clean_text = " ".join(s["text"] for s in sentences)
            with open(tx_out, "w", encoding="utf-8") as f:
                json.dump({
                    "duration": duration,
                    "text": clean_text,
                    "words": whisper["words"],
                }, f)

    return index_doc


if __name__ == "__main__":
    t_arg = sys.argv[1] if len(sys.argv) > 1 else None
    doc = build_unified_index(transcript_path=t_arg)
    print(json.dumps({
        "status": doc["status"],
        "source_whisper": doc["source_whisper"],
        "stream_duration_sec": doc["stream_duration_sec"],
        "total_sentences": doc["total_sentences"],
        "audio_peaks_count": doc["audio_peaks_count"],
        "chat_clusters_count": doc["chat_clusters_count"],
        "face_events_count": doc["face_events_count"],
        "anchors_count": doc["anchors_count"],
    }, indent=2))
