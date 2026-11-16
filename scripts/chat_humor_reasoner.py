#!/usr/bin/env python3
"""
chat_humor_reasoner.py
----------------------
Audience-Synchronized Comedic Beat Engine:
1. Aligns statistical laughter bursts (Z >= 2.5 sigma) with Whisper transcripts across [T_laugh - 15s, T_laugh - 1s].
2. Resolves the "Visual Comedy Blind Spot" by extracting 3 visual keyframes in the causal window for multimodal reasoner.
3. Implements the Conditional Multi-Beat Rule: Only merges Beat 2 if a verified second chat spike occurs in [+8s, +35s], otherwise maintaining a tight 12-18s single-beat clip.
4. Performs Cold Viewer Context Check to filter out meta-banter, inside jokes, and dead-stream sarcasm.
5. Identifies Setup Tension / In-Media-Res hook timestamps (never spoiling the verbal punchline at 0:00).
"""

import sys
import os
import json
import re
import math
import subprocess
import time
import base64
import urllib.request
import urllib.error

GEMINI_KEY_FILES = [
    "/files/temp/gemini_key.txt",
    "/files/gemini_key.txt",
    "/files/gemini_key_2.txt",
    "/files/temp/gemini_key_2.txt",
    "/files/temp/n8n_gemini_key.txt",
    "C:/Users/mlkme/Desktop/AI_Clipper/temp/gemini_key.txt",
    "C:/Users/mlkme/Desktop/AI_Clipper/temp/n8n_gemini_key.txt",
    "/files/temp/all_ai_creds.json"
]


def get_gemini_api_keys() -> list:
    keys = []
    for env_name in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_BACKUP_API_KEY"]:
        val = os.environ.get(env_name, "").strip()
        for part in val.split(","):
            p = part.strip()
            if len(p) > 15 and p not in keys:
                keys.append(p)
    for path in GEMINI_KEY_FILES:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if "{" in content:
                    data = json.loads(content)
                    for k in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "gemini_api_key", "apiKey", "key", "backup_key"]:
                        v = str(data.get(k) or "").strip()
                        if len(v) > 15 and v not in keys:
                            keys.append(v)
                else:
                    for line in content.splitlines():
                        v = line.strip()
                        if len(v) > 15 and v not in keys:
                            keys.append(v)
            except Exception:
                pass
    return keys


def get_gemini_api_key() -> str:
    keys = get_gemini_api_keys()
    return keys[0] if keys else ""


def format_timestamp(seconds: float) -> str:
    s_total = max(0.0, float(seconds))
    m = int(s_total // 60)
    s = int(s_total % 60)
    cs = int(round((s_total - int(s_total)) * 100))
    if cs >= 100: cs = 99
    return f"{m:02d}:{s:02d}.{cs:02d}"


def extract_frames(video_path: str, timestamps: list, output_prefix: str) -> list:
    """Extracts lightweight visual keyframes at specific timestamps for multimodal reasoner."""
    saved_frames = []
    for idx, ts in enumerate(timestamps):
        out_jpg = f"{output_prefix}_{idx+1}.jpg"
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-ss", str(max(0.0, ts)),
            "-i", video_path,
            "-vf", "scale=480:270",
            "-vframes", "1",
            "-q:v", "4",
            out_jpg
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
            if os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 1000:
                saved_frames.append(out_jpg)
        except Exception:
            pass
    return saved_frames


def analyze_humor_multimodal(
    api_key: str,
    frames: list,
    transcript_text: str,
    top_chat: list,
    t_laugh: float
) -> dict:
    """Queries Gemini 2.5 Flash Vision with causal frames + transcript + chat to deduce true comedy mechanism."""
    if not api_key or not frames:
        return {
            "comedy_mechanism": "Verbal / Gameplay Reaction",
            "why_chat_laughed": "Streamer reaction triggered audience laughter.",
            "cold_viewer_approved": True,
            "setup_tension_moment": format_timestamp(max(0.0, t_laugh - 8.0))
        }

    # Encode images to base64
    image_parts = []
    for fp in frames:
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            image_parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": b64
                }
            })
        except Exception:
            pass

    prompt_text = (
        "You are an elite YouTube Shorts Viral Content Director analyzing why a livestream audience erupted in laughter.\n\n"
        f"AUDIENCE LAUGHTER SPIKE at {format_timestamp(t_laugh)}:\n"
        f"Top Chat Messages: {json.dumps(top_chat)}\n\n"
        f"DIALOGUE IN PRECEDING 14 SECONDS:\n\"{transcript_text}\"\n\n"
        "Attached are sequential visual frames showing what happened on screen leading up to this laughter.\n\n"
        "TASK:\n"
        "1. Check the attached visual frames for ANY desktop/web-browser screen (Chrome/Edge tabs, YouTube Studio live chat popout, OBS/Notepad windows, Discord, or Roblox website group/payout pages). If ANY frame shows desktop/browser UI instead of active gameplay, set \"is_desktop_or_browser\": true and \"cold_viewer_approved\": false.\n"
        "2. Identify the EXACT comedic catalyst: Was it verbal dialogue, a visual gameplay fail, ragdoll physics, a game glitch, silent streamer face reaction, or instant karma?\n"
        "3. In 1 clear, high-density sentence, explain WHY the audience laughed.\n"
        "4. COLD VIEWER CONTEXT CHECK: Can a stranger scrolling TikTok who has NEVER seen this streamer understand why this is funny within 3 seconds? Answer TRUE or FALSE. (Reject if it shows a browser/desktop window, requires 2 hours of inside lore, TTS donation meta-banter, outro panhandling like 'hit the like button'/'everybody subscribe', or boring repetitive deaths).\n"
        "5. SETUP TENSION HOOK: Give the best timestamp (e.g. 0.5s before the blunder or the bold declaration) for an in-media-res hook that builds tension WITHOUT spoiling the verbal punchline at 0:00.\n\n"
        "OUTPUT FORMAT (STRICT JSON ONLY):\n"
        "{\n"
        "  \"is_desktop_or_browser\": false,\n"
        "  \"comedy_mechanism\": \"Instant Karma / Physical Blunder / Verbal Punchline\",\n"
        "  \"why_chat_laughed\": \"...\",\n"
        "  \"cold_viewer_approved\": true,\n"
        "  \"rejection_reason\": null,\n"
        "  \"setup_tension_moment\": \"MM:SS.ms\"\n"
        "}"
    )

    contents = [{
        "parts": image_parts + [{"text": prompt_text}]
    }]

    api_keys = api_key if isinstance(api_key, list) else ([api_key] if api_key else [])
    for extra in get_gemini_api_keys():
        if extra not in api_keys:
            api_keys.append(extra)

    models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    for key_idx, key_val in enumerate(api_keys):
        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key_val}"
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps({"contents": contents}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    match = re.search(r'\{[\s\S]*\}', raw_text)
                    if match:
                        parsed = json.loads(match.group(0))
                        print(f"[Humor Reasoner] {model_name} (key#{key_idx+1}) resolved comedic beat at {format_timestamp(t_laugh)}: {parsed.get('comedy_mechanism')}")
                        return parsed
            except urllib.error.HTTPError as e:
                print(f"[Humor Reasoner Warning] {model_name} (key#{key_idx+1}) HTTP {e.code}", file=sys.stderr)
                if e.code in (403, 404, 429):
                    continue
                time.sleep(1.0)
            except Exception as e:
                print(f"[Humor Reasoner Warning] {model_name} (key#{key_idx+1}) error: {e}", file=sys.stderr)
                time.sleep(1.0)

    return {
        "comedy_mechanism": "Verbal / Gameplay Reaction",
        "why_chat_laughed": "Streamer reaction triggered audience laughter.",
        "cold_viewer_approved": True,
        "setup_tension_moment": format_timestamp(max(0.0, t_laugh - 8.0))
    }


def process_comedic_beats(
    video_path: str,
    chat_analysis_path: str,
    whisper_path: str,
    output_path: str = "/files/temp/comedic_beats.json"
):
    print(f"[Humor Reasoner] Aligning laughter bursts for {video_path}...")

    if not os.path.exists(chat_analysis_path):
        print(f"[Humor Reasoner] No chat analysis file at {chat_analysis_path}")
        return {"status": "no_chat", "beats": []}

    with open(chat_analysis_path, "r", encoding="utf-8") as f:
        chat_data = json.load(f)

    clusters = chat_data.get("top_clusters") or []
    buckets = chat_data.get("buckets") or []

    whisper_words = []
    if whisper_path and os.path.exists(whisper_path):
        try:
            with open(whisper_path, "r", encoding="utf-8") as f:
                w_doc = json.load(f)
                whisper_words = w_doc.get("words") or (w_doc.get("x_groq") or {}).get("words") or []
        except Exception:
            pass

    api_key = get_gemini_api_key()
    beats = []

    # Map all burst peak times for fast secondary spike lookup
    all_peak_times = [c["peak_time"] for c in clusters]

    for idx, cl in enumerate(clusters[:8]):
        t_laugh = cl["peak_time"]
        c_start, c_end = cl["causal_window"]  # [T_laugh - 15s, T_laugh - 1s]

        # 1. Extract Whisper words in causal window
        matched_words = [w for w in whisper_words if c_start - 0.5 <= w.get("start", 0) <= c_end + 0.5]
        transcript_text = " ".join([w.get("word", "") for w in matched_words]).strip()
        if not transcript_text:
            transcript_text = "[Visual action / physical gameplay moment with minimal dialogue]"

        # 2. Extract 3 Keyframes in Causal Window
        sample_times = [
            max(0.0, t_laugh - 11.0),
            max(0.0, t_laugh - 6.0),
            max(0.0, t_laugh - 1.5)
        ]
        prefix = f"/files/temp/humor_b{idx+1}"
        frames = extract_frames(video_path, sample_times, prefix)

        # 3. Conditional Multi-Beat Check (+8s to +35s Callback)
        # Only merge Beat 2 IF a secondary statistical laughter spike actually occurs in that window!
        secondary_cluster = None
        for other_cl in clusters:
            other_t = other_cl["peak_time"]
            if t_laugh + 8.0 <= other_t <= t_laugh + 35.0:
                secondary_cluster = other_cl
                break

        is_multi_beat = False
        beat_2_info = None

        if secondary_cluster:
            t2 = secondary_cluster["peak_time"]
            t2_words = [w for w in whisper_words if t2 - 10.0 <= w.get("start", 0) <= t2]
            t2_text = " ".join([w.get("word", "") for w in t2_words]).strip()
            is_multi_beat = True
            beat_2_info = {
                "peak_time": t2,
                "z_score": secondary_cluster["z_score"],
                "sample_messages": secondary_cluster.get("sample_messages", [])[:4],
                "transcript": t2_text,
                "window": [round(t2 - 10.0, 1), round(t2 + 3.5, 1)]
            }

        # 4. Multimodal Semantic Analysis (Why They Laughed + Cold Viewer Check)
        humor_analysis = analyze_humor_multimodal(
            api_key,
            frames,
            transcript_text,
            cl.get("sample_messages", []),
            t_laugh
        )

        # Skip if desktop/browser UI visible or cold viewer check rejected (e.g. inside joke / meta-banter)
        if humor_analysis.get("is_desktop_or_browser", False) or not humor_analysis.get("cold_viewer_approved", True):
            print(f"[Humor Reasoner] Skipping burst at {t_laugh}s: Failed Vision/Cold Viewer Check ({humor_analysis.get('rejection_reason')})")
            continue

        # 5. Formulate Recommended Short Framing
        if is_multi_beat and beat_2_info:
            short_start = max(0.0, c_start)
            short_end = beat_2_info["window"][1]
            rec_structure = (
                f"2-Beat Escalation ({round(short_end - short_start, 1)}s):\n"
                f"• Hook (0:00 - 0:02): Tension hook at {humor_analysis.get('setup_tension_moment')}\n"
                f"• Beat 1: Initial setup & hilarious fail (Laugh 1 at {format_timestamp(t_laugh)})\n"
                f"• Beat 2: 10-20s later callback / 'happens again' (Laugh 2 at {format_timestamp(beat_2_info['peak_time'])})\n"
                f"• Outro: Reaction climax"
            )
        else:
            short_start = max(0.0, t_laugh - 13.0)
            short_end = min(t_laugh + 3.5, short_start + 18.0)
            rec_structure = (
                f"Tight Single-Beat Punch ({round(short_end - short_start, 1)}s):\n"
                f"• Hook (0:00 - 0:02): Setup tension hook at {humor_analysis.get('setup_tension_moment')}\n"
                f"• Setup & Climax: Dialogue & blunder leading directly into Laugh Burst at {format_timestamp(t_laugh)}\n"
                f"• Outro (2.5s): Reaction aftermath"
            )

        beat_item = {
            "beat_id": len(beats) + 1,
            "peak_laugh_time": t_laugh,
            "z_score": cl["z_score"],
            "laugh_count": cl["laugh_count"],
            "laugh_ratio": cl["laugh_ratio"],
            "causal_window": [c_start, c_end],
            "causal_transcript": transcript_text,
            "top_chat": cl.get("sample_messages", [])[:5],
            "comedy_mechanism": humor_analysis.get("comedy_mechanism", "Visual/Verbal Comedy"),
            "why_chat_laughed": humor_analysis.get("why_chat_laughed", "Audience erupted at hilarious reaction."),
            "setup_tension_hook": humor_analysis.get("setup_tension_moment", format_timestamp(c_start)),
            "is_multi_beat": is_multi_beat,
            "beat_2": beat_2_info,
            "clip_start": round(short_start, 1),
            "clip_end": round(short_end, 1),
            "clip_duration": round(short_end - short_start, 1),
            "recommended_structure": rec_structure
        }
        beats.append(beat_item)

        if len(beats) >= 6:
            break

    result = {
        "status": "success",
        "video": os.path.basename(video_path),
        "total_beats": len(beats),
        "comedic_beats": beats
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"[Humor Reasoner] Successfully compiled {len(beats)} Comedic Beat Storyboards to {output_path}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 chat_humor_reasoner.py <video.mp4> <chat_analysis.json> [whisper.json] [output.json]")
        sys.exit(1)

    v_p = sys.argv[1]
    c_p = sys.argv[2]
    w_p = sys.argv[3] if len(sys.argv) > 3 else ""
    o_p = sys.argv[4] if len(sys.argv) > 4 else "/files/temp/comedic_beats.json"

    process_comedic_beats(v_p, c_p, w_p, o_p)
