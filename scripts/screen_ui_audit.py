#!/usr/bin/env python3
"""
screen_ui_audit.py
------------------
Lightweight Key-Frame Vision Screen Audit for concatenated Shorts clips.
Extracts 4 frames (10%, 35%, 65%, 85%) from concatenated_clip.mp4 and sends
them in ONE single Gemini 2.5 Flash Vision request to detect Chrome/Edge browsers,
Twitch/YouTube chat dashboards, Discord, or Roblox ESC pause/settings menus.
Fails open (has_ui_obstruction=false) on transient API/FFmpeg errors.
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

GEMINI_KEY_FILES = [
    "/files/temp/n8n_gemini_key.txt",
    "/files/gemini_key.txt",
    "/files/temp/gemini_key.txt",
    "/files/temp/all_ai_creds.json",
]

AUDIT_PROMPT = (
    "You are auditing 4 frames (indices 0, 1, 2, 3) extracted from a Roblox gaming Short. "
    "Does ANY frame show a web browser (Chrome/Edge), Twitch/YouTube chat dashboard window, "
    "Discord, or the Roblox ESC pause/settings menu? "
    "Ignore normal Roblox HUD health/hotbar/nametags or small corner stream facecams. "
    "Return JSON: {\"has_ui_obstruction\": bool, \"bad_frames\": [indices]}"
)


def get_gemini_api_key() -> str:
    env_k = os.environ.get("GEMINI_API_KEY", "").strip()
    if len(env_k) > 20:
        return env_k
    for kpath in GEMINI_KEY_FILES:
        if os.path.exists(kpath):
            try:
                content = open(kpath, "r", encoding="utf-8").read().strip()
                if kpath.endswith(".json"):
                    creds = json.loads(content)
                    for c in creds:
                        ctype = str(c.get("type", "")).lower()
                        if "gemini" in ctype or "palm" in ctype:
                            k = str(c.get("apiKey", "")).strip()
                            if len(k) > 20:
                                return k
                elif len(content) > 20:
                    return content
            except Exception:
                pass
    return ""


def probe_duration(video_path: str) -> float:
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        dur = float(res.stdout.strip() or 0.0)
        if dur > 0.5:
            return dur
    except Exception:
        pass
    return 30.0


def extract_key_frames(video_path: str, tmp_dir: str, fractions=(0.10, 0.35, 0.65, 0.85)) -> list:
    dur = probe_duration(video_path)
    frames = []
    for idx, frac in enumerate(fractions):
        ts = max(0.1, min(dur - 0.1, dur * frac))
        out_jpg = os.path.join(tmp_dir, f"ui_audit_{idx}.jpg")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-loglevel", "error", "-y", "-ss", f"{ts:.2f}",
                    "-i", video_path, "-vf", "scale=640:-2", "-vframes", "1", "-q:v", "3", out_jpg,
                ],
                capture_output=True, timeout=12,
            )
            if os.path.isfile(out_jpg) and os.path.getsize(out_jpg) > 500:
                frames.append((idx, out_jpg))
        except Exception:
            pass
    return frames


def parse_audit_response(raw_text: str) -> dict:
    cleaned = re.sub(r"```json|```", "", str(raw_text or ""), flags=re.I).strip()
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)
    data = json.loads(cleaned)
    has_obs = bool(data.get("has_ui_obstruction", False))
    bad = data.get("bad_frames") or []
    if not isinstance(bad, list):
        bad = []
    return {"has_ui_obstruction": has_obs, "bad_frames": bad}


def call_gemini_vision(frames: list, api_key: str, models=None) -> dict:
    if not frames or not api_key:
        return {"has_ui_obstruction": False, "bad_frames": [], "skipped": "no_frames_or_key"}

    parts = [{"text": AUDIT_PROMPT}]
    for _, fpath in frames:
        b64 = base64.b64encode(open(fpath, "rb").read()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }).encode("utf-8")

    model_list = models or ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite"]
    last_err = None
    for model in model_list:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            txt = resp_data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = parse_audit_response(txt)
            parsed["model"] = model
            return parsed
        except urllib.error.HTTPError as he:
            last_err = f"HTTP {he.code}"
            if he.code in (429, 500, 502, 503, 504):
                continue
            break
        except Exception as ex:
            last_err = str(ex)
            continue

    return {"has_ui_obstruction": False, "bad_frames": [], "error": last_err or "vision_unavailable"}


def audit_video(video_path: str) -> dict:
    if not os.path.isfile(video_path):
        return {"has_ui_obstruction": False, "bad_frames": [], "skipped": "video_missing"}
    api_key = get_gemini_api_key()
    if not api_key:
        return {"has_ui_obstruction": False, "bad_frames": [], "skipped": "missing_api_key"}

    with tempfile.TemporaryDirectory(prefix="ui_audit_") as tmp_dir:
        frames = extract_key_frames(video_path, tmp_dir)
        return call_gemini_vision(frames, api_key)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/files/temp/concatenated_clip.mp4"
    result = audit_video(target)
    print(json.dumps(result))
