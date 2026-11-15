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
from collections import Counter

HALLUCINATION_PHRASES = [
    "roblox gaming",
    "lucky blocks",
    "divine mutation",
    "10x luck",
    "streamer reacting",
    "gaming chaos",
    "thank you for watching",
    "thanks for watching",
    "subscribe and like",
]

BOAST_PATTERNS = re.compile(
    r"\b(watch this|easy|no way i lose|trust me|bet|i'm the best|i got this|cannot lose|never happens|guarantee|hold my|pro player|all of my games|admin abuse|i'm going to buy it|nobody can beat)\b",
    re.I,
)
MYSTERY_PATTERNS = re.compile(
    r"\b(wait what|what is that|who is|why did|how did|secret|hidden|glitch|weird|bro what|no shot|what happened|are you telling me|tricked me|fake account|am i blind|how many)\b",
    re.I,
)
HOUSEKEEPING_NOISE = re.compile(
    r"(thank you for the super\s*chat|for the super chat|get your entries in|enter you into the giveaway|type [a-z0-9]+ into the chat|friend request|let me search him up|make a [0-9,]+ game\s*pass|every giveaway we do|draw a winner|stops the bots|spam the word)",
    re.I,
)
STOPWORDS = {
    "there", "their", "about", "which", "would", "could", "should", "really",
    "going", "gonna", "wanna", "thing", "things", "right", "think", "actually",
    "people", "someone", "something", "because", "before", "after", "these",
    "those", "where", "every", "wait", "dude", "guys", "chat", "bro", "yeah",
    "okay", "just", "like", "know", "what", "that", "this", "with", "from",
    "have", "they", "were", "been", "look", "here", "come", "make", "take",
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


def load_audio_energy(audio_energy_path=None):
    events = []
    p_ae = _first_existing([audio_energy_path, "/files/temp/audio_energy.json"])
    if p_ae:
        try:
            with open(p_ae, "r", encoding="utf-8") as f:
                ae = json.load(f)
            if isinstance(ae, dict) and ae.get("peaks"):
                events.extend(ae["peaks"])
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
    return deduped


def load_chat_clusters(chat_path=None):
    p = _first_existing([
        chat_path,
        "/files/temp/chat_laughter_clusters.json",
        "/files/temp/chat_analysis.json",
        "/files/temp/test_zscore_out.json",
    ])
    clusters = []
    beats_by_t = {}

    if os.path.exists("/files/temp/comedic_beats.json"):
        try:
            with open("/files/temp/comedic_beats.json", "r", encoding="utf-8") as f:
                cb = json.load(f)
            for b in cb.get("comedic_beats") or cb.get("beats") or []:
                t = round(float(b.get("peak_laugh_time", 0.0)), 1)
                beats_by_t[t] = b
        except Exception:
            pass

    if p:
        try:
            with open(p, "r", encoding="utf-8") as f:
                cd = json.load(f)
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


def load_face_emotions(face_path=None):
    p = _first_existing([
        face_path,
        "/files/temp/face_emotions.json",
        "/files/inputs/kreek_face_test.json",
    ])
    events = []
    if not p:
        return events
    try:
        with open(p, "r", encoding="utf-8") as f:
            fd = json.load(f)
        for ev in fd.get("top_events") or []:
            events.append({
                "start": float(ev.get("start", 0.0)),
                "end": float(ev.get("end", 0.0)),
                "dominant": ev.get("dominant", "reaction"),
                "intensity": float(ev.get("peak_intensity", ev.get("intensity", 70.0))),
            })
        if not events:
            for s in fd.get("samples") or []:
                inten = float(s.get("intensity", 0.0))
                if inten >= 65.0:
                    dom = "joy" if s.get("joy", 0) >= s.get("surprise", 0) else "surprise"
                    events.append({
                        "start": float(s.get("time", 0.0)),
                        "end": float(s.get("time", 0.0)) + 1.5,
                        "dominant": dom,
                        "intensity": inten,
                    })
    except Exception:
        pass
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
    top_k=18,
    save_cache=True,
):
    whisper = load_whisper(transcript_path)
    audio_peaks = load_audio_energy(audio_energy_path)
    chat_clusters = load_chat_clusters(chat_path)
    face_events = load_face_emotions(face_path)

    sentences = build_sentences_with_cadence(whisper["words"])
    duration = whisper["duration"] or (sentences[-1]["end"] if sentences else 3600.0)

    # Annotate sentences with inline multimodal telemetry tags
    annotated_lines = []
    for s in sentences:
        st, en = s["start"], s["end"]
        tags = []
        if s["wpm"] >= 210 and s["word_count"] >= 5:
            tags.append(f"[WPM_SPIKE: {int(s['wpm'])}wpm]")
        if 1.2 <= s["pause_after"] <= 6.0:
            tags.append(f"[DRAMATIC_PAUSE: {s['pause_after']:.1f}s]")

        matched_audio = [a for a in audio_peaks if a["start"] <= en + 2.0 and a.get("end", a["start"] + 1.5) >= st - 2.0]
        if matched_audio:
            best_a = max(matched_audio, key=lambda x: x.get("jump_db", 8.0))
            tags.append(f"[dB_PEAK +{best_a.get('jump_db', 8.0)}dB]")

        matched_chat = [c for c in chat_clusters if abs(c.get("peak_time", 0.0) - en) <= 16.0]
        if matched_chat:
            best_c = max(matched_chat, key=lambda x: x.get("z_score", 0.0))
            snips = ", ".join((best_c.get("sample_messages") or [])[:2])
            tags.append(f"[CHAT_BURST Z={best_c.get('z_score', 2.5)}σ ({round(best_c.get('laugh_ratio', 0)*100)}% Laugh) | \"{snips}\"]")

        matched_face = [f for f in face_events if f["start"] <= en + 2.0 and f["end"] >= st - 2.0]
        if matched_face:
            best_f = max(matched_face, key=lambda x: x.get("intensity", 0.0))
            tags.append(f"[EMOTION: {best_f['dominant']} ({int(best_f['intensity'])}%)]")

        tag_str = (" " + " ".join(tags)) if tags else ""
        line_str = f"[{st:.1f}s - {en:.1f}s | {format_mmss(st)}]{tag_str} {s['text']}"
        s["tags"] = tags
        s["annotated_line"] = line_str
        annotated_lines.append(s)

    # Score candidate windows across the full 1h+ timeline (5s grid)
    bin_size = 5.0
    num_bins = max(1, int(math.ceil(duration / bin_size)))
    grid = [{"t": i * bin_size, "score": 0.0, "chat": None, "audio": None, "face": None, "sents": []} for i in range(num_bins)]

    for s in annotated_lines:
        idx = min(num_bins - 1, max(0, int(s["start"] // bin_size)))
        grid[idx]["sents"].append(s)
        if HOUSEKEEPING_NOISE.search(s["text"]):
            grid[idx]["score"] -= 26.0
        if s["wpm"] >= 220 and s["word_count"] >= 5:
            grid[idx]["score"] += 15.0
        if BOAST_PATTERNS.search(s["text"]):
            grid[idx]["score"] += 16.0
        if MYSTERY_PATTERNS.search(s["text"]):
            grid[idx]["score"] += 16.0

    for c in chat_clusters:
        pt = float(c.get("peak_time", 0.0))
        # Credit causal window [pt - 15s, pt] so score aligns with setup & climax
        for offset in (-10.0, -5.0, 0.0):
            idx = min(num_bins - 1, max(0, int((pt + offset) // bin_size)))
            if idx < len(grid):
                grid[idx]["score"] += min(50.0, float(c.get("z_score", 2.5)) * 12.0 + float(c.get("laugh_ratio", 0.3)) * 30.0)
                grid[idx]["chat"] = c

    for a in audio_peaks:
        idx = min(num_bins - 1, max(0, int(a.get("start", 0.0) // bin_size)))
        if idx < len(grid):
            grid[idx]["score"] += min(35.0, float(a.get("jump_db", 8.0)) * 3.0)
            grid[idx]["audio"] = a

    for fe in face_events:
        idx = min(num_bins - 1, max(0, int(fe.get("start", 0.0) // bin_size)))
        if idx < len(grid):
            grid[idx]["score"] += min(30.0, float(fe.get("intensity", 70.0)) * 0.35)
            grid[idx]["face"] = fe

    # Smooth scores slightly across neighboring +/- 10s bins & extract local maxima
    smoothed = []
    for i in range(num_bins):
        win_score = grid[i]["score"]
        for k in range(max(0, i - 2), min(num_bins, i + 3)):
            if k != i:
                win_score += 0.35 * grid[k]["score"]
        smoothed.append((i, win_score))

    smoothed.sort(key=lambda x: x[1], reverse=True)

    # Compute document frequency for rare keyword detection in callback matching
    df_counts = Counter()
    for s in annotated_lines:
        uniq = set(w.lower() for w in re.findall(r"[a-zA-Z]{5,}", s["text"]) if w.lower() not in STOPWORDS)
        for u in uniq:
            df_counts[u] += 1

    max_smoothed = smoothed[0][1] if smoothed and smoothed[0][1] > 0 else 100.0

    # Extract top_k non-overlapping anchors (min 40s apart)
    anchors = []
    used_times = []
    for idx, sc in smoothed:
        if sc <= 10.0:
            break
        t_mid = grid[idx]["t"]
        if any(abs(t_mid - ut) < 40.0 for ut in used_times):
            continue

        # Gather surrounding context sentences [t_mid - 22s, t_mid + 24s]
        win_sents = [s for s in annotated_lines if t_mid - 22.0 <= s["start"] <= t_mid + 24.0]
        if not win_sents and sentences:
            continue

        a_start = round(max(0.0, win_sents[0]["start"] if win_sents else t_mid - 15.0), 1)
        a_end = round(min(duration, (win_sents[-1]["end"] + 2.0) if win_sents else t_mid + 8.0), 1)
        snippet_text = " ".join(s["text"] for s in win_sents)[:380]

        # Inspect signals in this anchor window
        c_hit = grid[idx]["chat"] or next((g["chat"] for g in grid[max(0, idx-2):min(num_bins, idx+3)] if g["chat"]), None)
        a_hit = grid[idx]["audio"] or next((g["audio"] for g in grid[max(0, idx-2):min(num_bins, idx+3)] if g["audio"]), None)
        f_hit = grid[idx]["face"] or next((g["face"] for g in grid[max(0, idx-2):min(num_bins, idx+3)] if g["face"]), None)

        # Callback scanner across whole VOD for genuinely rare recurring keywords (2 <= df <= 12)
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

        # Suggest best-fit Viral Archetype based on structural signals
        arch_slot = len(anchors) % 5
        if c_hit and c_hit.get("is_multi_beat"):
            rec_arch = "DOUBLE_DOWN_ESCALATION"
        elif BOAST_PATTERNS.search(snippet_text):
            rec_arch = "HUBRIS_INSTANT_KARMA"
        elif MYSTERY_PATTERNS.search(snippet_text):
            rec_arch = "MYSTERY_OPEN_LOOP"
        elif a_hit and float(a_hit.get("jump_db", 0.0)) >= 9.0:
            rec_arch = "IN_MEDIA_RES_FLASHFORWARD" if arch_slot in (0, 2, 4) else "DOUBLE_DOWN_ESCALATION"
        else:
            rec_arch = ["REVERSE_PAYOFF_LOOP", "MYSTERY_OPEN_LOOP", "DOUBLE_DOWN_ESCALATION", "HUBRIS_INSTANT_KARMA", "IN_MEDIA_RES_FLASHFORWARD"][arch_slot]

        norm_score = round(min(99.5, 45.0 + (sc / max_smoothed) * 52.0), 1)

        anchors.append({
            "anchor_id": len(anchors) + 1,
            "start": a_start,
            "end": a_end,
            "peak_time": round(t_mid, 1),
            "peak_tc": format_mmss(t_mid),
            "duration": round(a_end - a_start, 1),
            "virality_score": norm_score,
            "recommended_archetype": rec_arch,
            "chat_signal": (
                f"Z={c_hit.get('z_score')}σ ({round(c_hit.get('laugh_ratio', 0)*100)}% Laugh) | \"{', '.join((c_hit.get('sample_messages') or [])[:2])}\""
                if c_hit else "Transcript/Audio/Emotion driven spike"
            ),
            "face_signal": (
                f"{f_hit['dominant']} ({int(f_hit['intensity'])}% intensity)"
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

    # Build compact macro timeline summary string (~4K-8K chars summarizing high-signal moments across 1h+ VOD)
    high_signal_lines = [s["annotated_line"] for s in annotated_lines if s["tags"]]
    if len(high_signal_lines) < 30:
        # Include evenly sampled context lines alongside tagged lines
        step_pick = max(1, len(annotated_lines) // 60)
        sampled = [annotated_lines[i]["annotated_line"] for i in range(0, len(annotated_lines), step_pick)]
        macro_lines = list(dict.fromkeys(high_signal_lines + sampled))
    else:
        macro_lines = high_signal_lines[:120]

    index_doc = {
        "status": "success",
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
        # Save standardized Sandbox cache artifacts
        with open(os.path.join(output_dir, "unified_timeline_index.json"), "w", encoding="utf-8") as f:
            json.dump(index_doc, f, indent=2)

        with open(os.path.join(output_dir, "audio_energy.json"), "w", encoding="utf-8") as f:
            json.dump({"peaks": audio_peaks, "count": len(audio_peaks)}, f, indent=2)

        with open(os.path.join(output_dir, "chat_laughter_clusters.json"), "w", encoding="utf-8") as f:
            json.dump({"clusters": chat_clusters, "count": len(chat_clusters)}, f, indent=2)

        with open(os.path.join(output_dir, "face_emotions.json"), "w", encoding="utf-8") as f:
            json.dump({"top_events": face_events, "count": len(face_events)}, f, indent=2)

        # Ensure /files/temp/transcript.json exists for zero-download Sandbox runs
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
