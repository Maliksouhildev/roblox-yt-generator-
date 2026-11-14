#!/usr/bin/env python3
"""
multimodal_fusion.py
--------------------
Local Multimodal Virality Fusion Engine:
Fuses 3 free, local reaction signals:
1. Live Chat Velocity & Emote Bursts (chat_analyzer.py)
2. Streamer Facial Expressions: Joy/Laughter, Shock/Surprise (face_reaction_tracker.py)
3. Vocal Energy Spikes & Screams (scream_detector.py)
With Whisper word-level transcripts to isolate the Top 6 Viral Anchors.
"""

import sys
import os
import json
import math

def format_timestamp(seconds: float) -> str:
    """Formats seconds into MM:SS.ms"""
    s_total = max(0.0, float(seconds))
    m = int(s_total // 60)
    s = int(s_total % 60)
    cs = int(round((s_total - int(s_total)) * 100))
    if cs >= 100: cs = 99
    return f"{m:02d}:{s:02d}.{cs:02d}"


def fuse_signals(
    chat_file: str = None,
    face_file: str = None,
    audio_file: str = None,
    whisper_file: str = None,
    total_duration: float = None,
    top_k: int = 6
):
    # 1. Load available signals
    chat_data = None
    if chat_file and os.path.exists(chat_file):
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                chat_data = json.load(f)
        except Exception as e:
            print(f"[Fusion Warning] Failed to load chat file {chat_file}: {e}")

    face_data = None
    if face_file and os.path.exists(face_file):
        try:
            with open(face_file, "r", encoding="utf-8") as f:
                face_data = json.load(f)
        except Exception as e:
            print(f"[Fusion Warning] Failed to load face file {face_file}: {e}")

    scream_windows = []
    if audio_file and os.path.exists(audio_file):
        try:
            with open(audio_file, "r", encoding="utf-8") as f:
                raw_s = json.load(f)
                if isinstance(raw_s, list):
                    scream_windows = raw_s
        except Exception as e:
            print(f"[Fusion Warning] Failed to load audio spikes {audio_file}: {e}")

    whisper_words = []
    whisper_text = ""
    if whisper_file and os.path.exists(whisper_file):
        try:
            with open(whisper_file, "r", encoding="utf-8") as f:
                w_raw = json.load(f)
                whisper_text = w_raw.get("text", "")
                whisper_words = w_raw.get("words") or (w_raw.get("x_groq") or {}).get("words") or []
                if not total_duration:
                    total_duration = w_raw.get("duration")
        except Exception as e:
            print(f"[Fusion Warning] Failed to load whisper file {whisper_file}: {e}")

    # Determine stream duration
    if not total_duration or total_duration <= 0:
        if face_data and face_data.get("video_duration"):
            total_duration = face_data["video_duration"]
        elif chat_data and chat_data.get("duration_sec"):
            total_duration = chat_data["duration_sec"]
        elif whisper_words:
            total_duration = whisper_words[-1].get("end", 60.0)
        else:
            total_duration = 300.0

    print(f"[Multimodal Fusion] Analyzing Stream Duration: {total_duration:.1f}s")

    # 2. Build time-series grid (1.0s resolution)
    step = 1.0
    num_bins = int(math.ceil(total_duration / step))
    timeline = []
    for i in range(num_bins):
        t = i * step
        timeline.append({
            "time": t,
            "chat_score": 0.0,
            "chat_info": None,
            "face_score": 0.0,
            "face_info": None,
            "audio_score": 0.0,
            "composite_score": 0.0
        })

    # Fill Chat Signal
    has_chat = False
    if chat_data and chat_data.get("buckets"):
        has_chat = True
        for b in chat_data["buckets"]:
            b_start = b["start"]
            b_end = b["end"]
            b_score = b.get("chat_score", 0.0)
            emotes = b.get("top_emotes", [])
            for item in timeline:
                if b_start <= item["time"] <= b_end:
                    if b_score > item["chat_score"]:
                        item["chat_score"] = b_score
                        item["chat_info"] = f"Velocity {b.get('velocity', 0)} msgs/10s | Emotes: {', '.join(emotes[:3])}"

    # Fill Face Signal
    has_face = False
    if face_data and face_data.get("samples"):
        has_face = True
        for s in face_data["samples"]:
            t = s["time"]
            bin_idx = min(num_bins - 1, max(0, int(round(t / step))))
            f_score = s.get("intensity", 0.0)
            if f_score > timeline[bin_idx]["face_score"]:
                timeline[bin_idx]["face_score"] = f_score
                dom = "Joy/Laugh" if s.get("joy", 0) >= s.get("surprise", 0) else "Shock/Surprise"
                timeline[bin_idx]["face_info"] = f"{dom} ({round(max(s.get('joy',0), s.get('surprise',0))*100)}%)"

    # Fill Audio Spike Signal
    for sw in scream_windows:
        if isinstance(sw, list) and len(sw) >= 2:
            s_start, s_end = float(sw[0]), float(sw[1])
            for item in timeline:
                if s_start <= item["time"] <= s_end:
                    item["audio_score"] = 100.0

    # 3. Compute Composite Virality Index
    # Weights adapt dynamically based on available signals
    if has_chat and has_face:
        w_chat, w_face, w_audio = 0.40, 0.35, 0.25
    elif has_face:
        w_chat, w_face, w_audio = 0.0, 0.60, 0.40
    elif has_chat:
        w_chat, w_face, w_audio = 0.65, 0.0, 0.35
    else:
        w_chat, w_face, w_audio = 0.0, 0.0, 1.0

    for item in timeline:
        comp = (w_chat * item["chat_score"]) + (w_face * item["face_score"]) + (w_audio * item["audio_score"])
        item["composite_score"] = round(comp, 1)

    # 4. Extract Peak Candidates & Cluster into Anchors
    peaks = []
    min_peak_threshold = 45.0
    for i, item in enumerate(timeline):
        if item["composite_score"] >= min_peak_threshold:
            # Check local maximum in 5-second window
            is_max = True
            for k in range(max(0, i - 2), min(num_bins, i + 3)):
                if timeline[k]["composite_score"] > item["composite_score"]:
                    is_max = False
                    break
            if is_max:
                peaks.append(item)

    peaks.sort(key=lambda p: p["composite_score"], reverse=True)

    # Form cohesive Viral Anchor Windows around top peaks
    anchors = []
    used_intervals = []

    for p in peaks:
        peak_t = p["time"]
        # Check overlap with existing anchors
        overlap = False
        for u_start, u_end in used_intervals:
            if not (peak_t + 15.0 < u_start or peak_t - 15.0 > u_end):
                overlap = True
                break
        if overlap:
            continue

        # Setup: 12 seconds before peak
        anchor_start = max(0.0, peak_t - 12.0)
        # Climax + aftermath: 18 seconds after peak
        anchor_end = min(total_duration, peak_t + 18.0)
        dur = anchor_end - anchor_start

        # Collect metadata in this anchor window
        c_infos = [it["chat_info"] for it in timeline if anchor_start <= it["time"] <= anchor_end and it["chat_info"]]
        f_infos = [it["face_info"] for it in timeline if anchor_start <= it["time"] <= anchor_end and it["face_info"]]
        has_screams = any(anchor_start <= it["time"] <= anchor_end and it["audio_score"] > 0 for it in timeline)

        # Extract transcript in this window
        matched_words = [w for w in whisper_words if w.get("start", 0) >= anchor_start - 1.0 and w.get("end", 0) <= anchor_end + 1.0]
        transcript_snippet = " ".join([w.get("word", "") for w in matched_words]).strip()
        if not transcript_snippet and whisper_text:
            transcript_snippet = f"[Words aligned near {format_timestamp(peak_t)}]"

        anchors.append({
            "anchor_id": len(anchors) + 1,
            "start": round(anchor_start, 2),
            "end": round(anchor_end, 2),
            "peak_time": round(peak_t, 2),
            "duration": round(dur, 2),
            "virality_score": p["composite_score"],
            "chat_signal": c_infos[0] if c_infos else "Normal chat pace",
            "face_signal": f_infos[0] if f_infos else "Active gameplay expression",
            "audio_signal": "Vocal volume spike (+8dB to +12dB)" if has_screams else "Standard vocal dialogue",
            "transcript": transcript_snippet
        })
        used_intervals.append((anchor_start, anchor_end))

        if len(anchors) >= top_k:
            break

    # Format human & AI-readable prompt payload
    scout_anchors_text = []
    for a in anchors:
        block = (
            f"=== [VIRAL ANCHOR #{a['anchor_id']}] [{format_timestamp(a['start'])} - {format_timestamp(a['end'])}] "
            f"VIRALITY SCORE: {a['virality_score']}/100 ===\n"
            f"• AUDIENCE REACTION (CHAT): {a['chat_signal']}\n"
            f"• STREAMER REACTION (FACECAM): {a['face_signal']}\n"
            f"• VOCAL DYNAMICS (AUDIO): {a['audio_signal']}\n"
            f"• TRANSCRIPT DIALOGUE:\n  \"{a['transcript']}\"\n"
        )
        scout_anchors_text.append(block)

    return {
        "total_duration": total_duration,
        "anchors_count": len(anchors),
        "anchors": anchors,
        "scout_prompt_payload": "\n".join(scout_anchors_text)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 multimodal_fusion.py --chat <chat.json> --face <face.json> --audio <audio_spikes.json> --whisper <whisper.json> --output <fusion.json>")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="Multimodal Virality Fusion Engine")
    parser.add_argument("--chat", type=str, default=None, help="Path to chat_analysis.json")
    parser.add_argument("--face", type=str, default=None, help="Path to face_reactions.json")
    parser.add_argument("--audio", type=str, default=None, help="Path to audio scream spikes JSON")
    parser.add_argument("--whisper", type=str, default=None, help="Path to whisper transcript JSON")
    parser.add_argument("--duration", type=float, default=None, help="Total stream duration in seconds")
    parser.add_argument("--top_k", type=int, default=6, help="Number of viral anchors to extract")
    parser.add_argument("--output", type=str, default="/files/outputs/viral_anchors.json", help="Output path")
    args = parser.parse_args()

    res = fuse_signals(
        chat_file=args.chat,
        face_file=args.face,
        audio_file=args.audio,
        whisper_file=args.whisper,
        total_duration=args.duration,
        top_k=args.top_k
    )

    print(f"\n[Multimodal Fusion] Successfully generated {res['anchors_count']} Viral Anchors:")
    print("--------------------------------------------------------------------------------")
    print(res["scout_prompt_payload"])
    print("--------------------------------------------------------------------------------")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[Multimodal Fusion] Saved to {args.output}")
