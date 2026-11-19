#!/usr/bin/env python3
"""
screen_ui_audit.py
------------------
Key-Frame Vision + Local OpenCV Screen Audit for concatenated GTA 6 Shorts clips.
Extracts 4 frames (10%, 35%, 65%, 85%) from concatenated_clip.mp4 and runs:
  1. Local OpenCV checks for NSFW skin clusters, black/solid loading screens,
     EULA / epilepsy health-warning text blocks, and dark static frames.
  2. One single Gemini Vision request to detect browsers, chat dashboards,
     pause/settings/calibration menus, EULA/warning screens, Rockstar logo cards,
     blank loading screens, or M-rated NSFW scenes.
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
    "You are auditing 4 frames (indices 0, 1, 2, 3) extracted from a GTA 6 / gaming Short. "
    "Flag has_ui_obstruction=true if ANY frame shows: "
    "(1) a web browser (Chrome/Edge), Twitch/YouTube chat dashboard, Discord, pause/ESC/settings/map/brightness/audio calibration menus, or commercial break blocking gameplay; "
    "(2) black or solid-color loading screens, blank dark transitions, game boot/splash screens, Rockstar logo title cards, or EULA / epilepsy / seizure / health-warning text walls; "
    "(3) M-rated NSFW scenes (nudity, strip clubs, sexually explicit content, or graphic TOS-violating gore); or "
    "(4) static or dark non-gameplay frames with no visual progression across frames. "
    "WHITELIST (do NOT flag): normal GTA 6 bottom-left minimap radar, active in-game cutscene action with clear character motion, "
    "standard gaming HUD elements, or small corner streamer facecams. "
    "Return JSON: {\"has_ui_obstruction\": bool, \"is_nsfw_or_unsafe\": bool, \"bad_frames\": [indices], \"reason\": \"short_tag_or_clean\"}"
)


def local_nsfw_and_static_heuristic(frames: list) -> dict:
    """Offline OpenCV checks for NSFW skin clusters, black/solid loading screens, EULA text walls, and dark static frames."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return {
            "is_nsfw_heuristic": False,
            "is_static": False,
            "is_black_or_solid_loading": False,
            "is_eula_or_warning_text": False,
            "is_dark_static": False,
            "bad_frames": [],
        }

    skin_ratios = []
    imgs = []
    dark_or_solid_frames = []
    eula_like_frames = []
    dark_frames = []

    for idx, fpath in frames:
        img = cv2.imread(fpath)
        if img is None:
            continue
        h, w = img.shape[:2]
        # Focus on central gameplay region [15%..85% y, 15%..85% x] to ignore corner webcam faces
        roi = img[int(h * 0.15):int(h * 0.85), int(w * 0.15):int(w * 0.85)]
        ycrcb = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb, (60, 133, 77), (255, 173, 127))
        skin_ratios.append(float(np.count_nonzero(mask)) / float(max(1, mask.size)))

        gray_small = cv2.cvtColor(cv2.resize(roi, (160, 90)), cv2.COLOR_BGR2GRAY)
        imgs.append(gray_small)

        mean_luma = float(np.mean(gray_small))
        std_luma = float(np.std(gray_small))
        if (mean_luma < 16.0 and std_luma < 12.0) or std_luma < 8.5:
            dark_or_solid_frames.append(idx)
        if mean_luma < 22.0:
            dark_frames.append(idx)

        # Detect EULA / epilepsy / health-warning text blocks: dark background + sparse bright crisp white text
        bright_ratio = float(np.count_nonzero(gray_small > 185)) / float(max(1, gray_small.size))
        dark_bg_ratio = float(np.count_nonzero(gray_small < 38)) / float(max(1, gray_small.size))
        if dark_bg_ratio > 0.72 and 0.004 <= bright_ratio <= 0.22:
            edges = cv2.Canny(gray_small, 80, 180)
            row_edge_density = np.mean(edges > 0, axis=1)
            text_band_rows = int(np.count_nonzero(row_edge_density > 0.06))
            if text_band_rows >= 8:
                eula_like_frames.append(idx)

    # Strip club / explicit close-up scenes typically exhibit unusually high (>48%) central skin-tone coverage
    is_nsfw = sum(1 for r in skin_ratios if r > 0.48) >= 2
    diffs = []
    if len(imgs) >= 2:
        diffs = [float(np.mean(np.abs(imgs[i].astype(np.float32) - imgs[i - 1].astype(np.float32)))) for i in range(1, len(imgs))]
    is_static = len(diffs) >= 2 and all(d < 2.2 for d in diffs)
    mean_diff = (sum(diffs) / len(diffs)) if diffs else 99.0
    is_black_or_solid = len(dark_or_solid_frames) >= 2
    is_eula_text = len(eula_like_frames) >= 2 or (len(eula_like_frames) >= 1 and mean_diff < 5.0)
    is_dark_static = len(dark_frames) >= 2 and mean_diff < 4.5

    bad = sorted(set(dark_or_solid_frames + eula_like_frames + (dark_frames if is_dark_static else [])))
    return {
        "is_nsfw_heuristic": is_nsfw,
        "is_static": is_static,
        "is_black_or_solid_loading": is_black_or_solid,
        "is_eula_or_warning_text": is_eula_text,
        "is_dark_static": is_dark_static,
        "bad_frames": bad,
    }


def collect_gemini_api_keys() -> list:
    keys = []
    seen = set()

    def _add(k: str):
        k = str(k or "").strip()
        if len(k) > 20 and k not in seen:
            seen.add(k)
            keys.append(k)

    _add(os.environ.get("GEMINI_API_KEY", ""))
    for kpath in GEMINI_KEY_FILES:
        if os.path.exists(kpath):
            try:
                content = open(kpath, "r", encoding="utf-8").read().strip()
                if kpath.endswith(".json"):
                    creds = json.loads(content)
                    for c in creds:
                        ctype = str(c.get("type", "")).lower()
                        if "gemini" in ctype or "palm" in ctype or "google" in ctype:
                            _add(c.get("apiKey", ""))
                else:
                    _add(content)
            except Exception:
                pass
    return keys


def get_gemini_api_key() -> str:
    keys = collect_gemini_api_keys()
    return keys[0] if keys else ""


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
    has_obs = bool(data.get("has_ui_obstruction", False) or data.get("is_nsfw_or_unsafe", False))
    bad = data.get("bad_frames") or []
    if not isinstance(bad, list):
        bad = []
    return {
        "has_ui_obstruction": has_obs,
        "is_nsfw_or_unsafe": bool(data.get("is_nsfw_or_unsafe", False)),
        "bad_frames": bad,
    }


def call_gemini_vision(frames: list, api_key: str, models=None) -> dict:
    keys = collect_gemini_api_keys()
    if api_key and api_key not in keys:
        keys.insert(0, api_key)
    if not frames or not keys:
        return {"has_ui_obstruction": False, "bad_frames": [], "skipped": "no_frames_or_key"}

    parts = [{"text": AUDIT_PROMPT}]
    for _, fpath in frames:
        b64 = base64.b64encode(open(fpath, "rb").read()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

    model_list = models or ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]
    last_err = None
    for model in model_list:
        for k in keys:
            gen_cfg = {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 512,
            }
            if "2.5" in model:
                gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
            payload = json.dumps({"contents": [{"parts": parts}], "generationConfig": gen_cfg}).encode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                txt = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = parse_audit_response(txt)
                parsed["model"] = model
                return parsed
            except urllib.error.HTTPError as he:
                last_err = f"HTTP {he.code}"
                continue
            except Exception as ex:
                last_err = str(ex)
                continue

    return {"has_ui_obstruction": False, "bad_frames": [], "error": last_err or "vision_unavailable"}


def audit_video(video_path: str) -> dict:
    if not os.path.isfile(video_path):
        return {"has_ui_obstruction": True, "is_nsfw_or_unsafe": False, "bad_frames": [], "reason": "video_missing"}
    api_key = get_gemini_api_key()

    with tempfile.TemporaryDirectory(prefix="ui_audit_") as tmp_dir:
        frames = extract_key_frames(video_path, tmp_dir)
        if not frames:
            return {"has_ui_obstruction": True, "is_nsfw_or_unsafe": False, "bad_frames": [], "reason": "frame_extraction_failed"}
        heur = local_nsfw_and_static_heuristic(frames)
        if (
            heur.get("is_nsfw_heuristic")
            or heur.get("is_black_or_solid_loading")
            or heur.get("is_eula_or_warning_text")
            or heur.get("is_dark_static")
            or heur.get("is_static")
        ):
            reason = (
                "nsfw_skin_cluster" if heur.get("is_nsfw_heuristic")
                else "black_or_solid_loading_screen" if heur.get("is_black_or_solid_loading")
                else "eula_or_warning_text_screen" if heur.get("is_eula_or_warning_text")
                else "dark_static_frames" if heur.get("is_dark_static")
                else "static_screen"
            )
            return {
                "has_ui_obstruction": True,
                "is_nsfw_or_unsafe": bool(heur.get("is_nsfw_heuristic")),
                "bad_frames": heur.get("bad_frames") or [i for i, _ in frames],
                "reason": reason,
            }
        if not api_key:
            return {"has_ui_obstruction": False, "is_nsfw_or_unsafe": False, "bad_frames": [], "skipped": "missing_api_key"}
        return call_gemini_vision(frames, api_key)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/files/temp/concatenated_clip.mp4"
    result = audit_video(target)
    print(json.dumps(result))
