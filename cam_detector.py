#!/usr/bin/env python3
"""
Production Hybrid Facecam Detector Engine v4 for n8n AI Clipper Pipeline.
Combines:
1. Multi-Frame Distributed Video Sampling (5-7 frames across stream).
2. OpenCV YuNet DNN Multi-Frame Spatial Clustering & Persistence Scoring.
3. Anti-HUD & Anti-Micro-Noise Spatial Filters.
4. Geometric Straight-Line Border Snapping (isolating physical webcam boxes).
5. Zero-Bleed Narrow/Vertical Webcam Handling (exact physical box + FFmpeg blurred pillarbox composite).
6. Golden Eye-Line (36-39%) Bottom-Docked Framing for Green-Screen Streamers.
7. Gemini 2.5 Flash Vision Ground-Truth Detection (when available).
8. 100% Offline / Fallback Autonomous Resilience.
"""

import sys
import os
import glob
import json
import base64
import time
import math
import urllib.request
import urllib.error
import cv2
import numpy as np

# File paths & Models
YUNET_MODEL = "/files/face_detection_yunet.onnx"
DEFAULT_CONFIG_PATH = "/files/temp/cam_config.json"
GEMINI_KEY_FILES = [
    "/files/temp/n8n_gemini_key.txt",
    "/files/gemini_key.txt",
    "/files/temp/gemini_key.txt",
    "/files/temp/all_ai_creds.json",
]
VISION_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
]
TARGET_ASPECT = 720.0 / 380.0  # 1.8947 matching zero-gap Short top box (720x380)


def log(msg: str):
    print(f"[CamDetector] {msg}", file=sys.stderr)


def collect_gemini_api_keys() -> list:
    """Collects all unique Gemini API keys from env and credential files."""
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
                    if isinstance(creds, list):
                        for c in creds:
                            ctype = str(c.get("type", "")).lower()
                            if "gemini" in ctype or "palm" in ctype or "google" in ctype:
                                _add(c.get("apiKey", ""))
                else:
                    _add(content)
            except Exception as e:
                log(f"Warning: Failed reading {kpath}: {e}")
    return keys


def get_gemini_api_key() -> str:
    """Resolves primary Gemini API key (backwards-compatible wrapper)."""
    keys = collect_gemini_api_keys()
    return keys[0] if keys else ""


def _parse_vision_json(raw_text: str) -> dict | None:
    clean = str(raw_text or "").strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
    if clean.endswith("```"):
        clean = clean.rsplit("\n", 1)[0]
    clean = clean.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(clean)
    if isinstance(parsed, list):
        positives = [p for p in parsed if isinstance(p, dict) and p.get("has_streamer")]
        parsed = positives[0] if positives else (parsed[0] if parsed and isinstance(parsed[0], dict) else {})
    if not isinstance(parsed, dict):
        return None
    has_s = bool(parsed.get("has_streamer", False))
    wb = parsed.get("webcam_box") or [0, 0, 0, 0]
    fb = parsed.get("face_box") or [0, 0, 0, 0]
    if has_s and len(wb) == 4:
        bh = float(wb[2]) - float(wb[0])
        bw = float(wb[3]) - float(wb[1])
        # Sanity bounds: reject tiny UI badges or full-screen boxes (>65% screen area)
        if bh < 50 or bw < 50 or (bh * bw) > 650000:
            has_s = False
    return {
        "has_streamer": has_s,
        "type": str(parsed.get("type", "none")) if has_s else "none",
        "webcam_box": wb if has_s else [0, 0, 0, 0],
        "face_box": fb if has_s else [0, 0, 0, 0],
        "confidence": 0.98 if has_s else 0.0,
    }


def detect_streamer_gemini_vision(img_or_paths, api_key: str = "", api_keys: list | None = None) -> dict | None:
    """Calls Gemini Vision across key/model rotation using 1-3 active frames to locate persistent webcam boundaries."""
    keys = list(api_keys or [])
    if api_key and api_key not in keys:
        keys.insert(0, api_key)
    if not keys:
        keys = collect_gemini_api_keys()
    if not keys:
        return None

    img_paths = [img_or_paths] if isinstance(img_or_paths, str) else list(img_or_paths or [])
    img_parts = []
    for p in img_paths[:2]:
        if not p or not os.path.isfile(p):
            continue
        im = cv2.imread(p)
        if im is None:
            continue
        im_s = cv2.resize(im, (640, 360), interpolation=cv2.INTER_AREA)
        ok_enc, buf = cv2.imencode(".jpg", im_s, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
        if ok_enc:
            img_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.tobytes()).decode("utf-8")}})
    if not img_parts:
        return None

    prompt = (
        "Analyze these livestream frames to detect the streamer's PERSISTENT LIVE webcam or live VTuber avatar.\n"
        "CRITICAL RULES:\n"
        "1. In-game characters, NPCs, transient subscriber/donation alert popups, or commercial breaks = NOT streamer cam.\n"
        "2. If a commercial/ad break appears in one frame, ignore it and use the gameplay frame(s).\n"
        "3. Return ONE SINGLE JSON OBJECT representing the consistent webcam position across gameplay frames:\n"
        "   - type='box': streamer is in a distinct rectangular webcam box (top-left, top-right, bottom-left, bottom-right, etc.).\n"
        "     `webcam_box` [ymin, xmin, ymax, xmax] (0..1000) MUST tightly match the outer border of that box (ZERO game bleed).\n"
        "   - type='green_screen': transparent cutout directly over gameplay (no box background).\n"
        "     `webcam_box` encloses streamer head + shoulders (0..1000).\n"
        "   - `face_box`: streamer head/face [ymin, xmin, ymax, xmax] (0..1000).\n\n"
        "OUTPUT STRICT SINGLE JSON OBJECT (NEVER A JSON ARRAY):\n"
        '{"has_streamer": true, "type": "box", "webcam_box": [ymin, xmin, ymax, xmax], "face_box": [ymin, xmin, ymax, xmax]}\n'
        'If NO persistent live streamer cam exists, return: {"has_streamer": false, "type": "none", "webcam_box": [0,0,0,0], "face_box": [0,0,0,0]}'
    )
    parts = [{"text": prompt}] + img_parts

    last_err = None
    for model in VISION_MODELS:
        for key in keys:
            gen_cfg = {
                "responseMimeType": "application/json",
                "temperature": 0.0,
                "maxOutputTokens": 1536,
            }
            if "2.5" in model:
                gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
            payload = {"contents": [{"parts": parts}], "generationConfig": gen_cfg}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates:
                    all_text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if p.get("text"))
                    if all_text.strip():
                        res = _parse_vision_json(all_text)
                        if res is not None:
                            log(f"Gemini Vision ({model}): has_streamer={res['has_streamer']}, type={res['type']}, box={res['webcam_box']}")
                            return res
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")[:160]
                last_err = f"{model} HTTP {he.code}"
                if he.code == 400 and "thinkingBudget" in err_body:
                    gen_cfg.pop("thinkingConfig", None)
                    try:
                        req2 = urllib.request.Request(url, data=json.dumps({"contents": [{"parts": parts}], "generationConfig": gen_cfg}).encode("utf-8"), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req2, timeout=14) as resp2:
                            res_json2 = json.loads(resp2.read().decode("utf-8"))
                        all_text2 = "".join(p.get("text", "") for p in res_json2.get("candidates", [{}])[0].get("content", {}).get("parts", []) if p.get("text"))
                        if all_text2.strip():
                            res2 = _parse_vision_json(all_text2)
                            if res2 is not None:
                                log(f"Gemini Vision ({model}): has_streamer={res2['has_streamer']}, type={res2['type']}, box={res2['webcam_box']}")
                                return res2
                    except Exception:
                        pass
                continue
            except Exception as e:
                last_err = f"{model}: {e}"
                continue

    if last_err:
        log(f"Gemini Vision API call failed: {last_err}")
    return None


def detect_faces_yunet(img, detector, real_w=1920, real_h=1080, score_threshold=0.45) -> list:
    """Local face detection using OpenCV YuNet DNN."""
    if img is None:
        return []
    h_img, w_img = img.shape[:2]
    scaled = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
    detector.setInputSize((960, 540))
    _, faces = detector.detect(scaled)
    if faces is None or len(faces) == 0:
        return []

    scale_x = real_w / 960.0
    scale_y = real_h / 540.0
    results = []
    for f in faces:
        conf = float(f[-1])
        if conf < score_threshold:
            continue
        fx, fy, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
        x = int(fx * scale_x)
        y = int(fy * scale_y)
        w = int(fw * scale_x)
        h = int(fh * scale_y)
        if w < 32 or h < 32:
            continue
        cx = x + w // 2
        cy = y + h // 2
        # Anti-top HUD filter (reject center 60% of top 25%)
        if cy < real_h * 0.25 and (real_w * 0.20 <= cx <= real_w * 0.80):
            continue
        results.append({
            "x": x, "y": y, "w": w, "h": h,
            "cx": cx, "cy": cy,
            "conf": conf
        })
    return results


def cluster_faces_across_frames(detections_per_frame, real_w=1920, real_h=1080):
    """
    Spatially clusters face detections across multiple video frames.
    Determines persistence and distinguishes persistent streamer from transient avatars.
    """
    all_dets = []
    for f_idx, dlist in enumerate(detections_per_frame):
        for d in dlist:
            d_copy = dict(d)
            d_copy["frame_idx"] = f_idx
            all_dets.append(d_copy)

    if not all_dets:
        return None

    clusters = []
    for d in all_dets:
        placed = False
        for c in clusters:
            ref = c["dets"][0]
            if abs(d["cx"] - ref["cx"]) < max(ref["w"] * 1.5, 160) and abs(d["cy"] - ref["cy"]) < max(ref["h"] * 1.5, 160):
                c["dets"].append(d)
                c["frames"].add(d["frame_idx"])
                placed = True
                break
        if not placed:
            clusters.append({
                "dets": [d],
                "frames": {d["frame_idx"]}
            })

    total_frames = len(detections_per_frame)
    scored_clusters = []
    for c in clusters:
        dets = c["dets"]
        persistence = len(c["frames"])
        cxs = [d["cx"] for d in dets]
        cys = [d["cy"] for d in dets]
        ws = [d["w"] for d in dets]
        hs = [d["h"] for d in dets]
        confs = [d["conf"] for d in dets]

        med_cx = int(np.median(cxs))
        med_cy = int(np.median(cys))
        med_w = int(np.median(ws))
        med_h = int(np.median(hs))
        avg_conf = float(np.mean(confs))

        is_docked = (med_cy >= real_h * 0.48) or ((med_cy + med_h // 2) >= real_h * 0.78)
        is_corner = (med_cx < real_w * 0.25 or med_cx > real_w * 0.75) and (med_cy < real_h * 0.35)
        is_center = (real_w * 0.25 <= med_cx <= real_w * 0.75) and (real_h * 0.25 <= med_cy <= real_h * 0.75)

        score = persistence * 10.0 + avg_conf * 2.0
        if is_docked:
            score += 12.0
        elif is_corner:
            score += 10.0
        elif is_center:
            score -= 8.0

        scored_clusters.append({
            "score": score,
            "persistence": persistence,
            "dets": dets,
            "frames": c["frames"],
            "cx": med_cx, "cy": med_cy, "w": med_w, "h": med_h,
            "is_docked": is_docked, "is_corner": is_corner,
            "conf": avg_conf
        })

    scored_clusters.sort(key=lambda x: x["score"], reverse=True)
    best = scored_clusters[0]

    # Consensus validation: when 3+ frames provided, require persistence >= 2 unless strongly docked or corner
    if total_frames >= 3 and best["persistence"] < 2 and not (best["is_docked"] or best["is_corner"]):
        return None
    if best["score"] < 10.0:
        return None

    return best


def find_physical_box_borders(img_or_imgs, face_or_cluster, real_w=1920, real_h=1080):
    """
    Detects straight persistent border lines enclosing the streamer webcam box across frames.
    Works for ANY corner/edge (top-left, top-right, bottom-left like xQc, bottom-right, mid-side)
    while rejecting green-screen cutouts near unrelated full-screen UI lines.
    """
    if isinstance(img_or_imgs, list):
        images = img_or_imgs
        cluster = face_or_cluster
    else:
        images = [img_or_imgs]
        cluster = {
            "cx": face_or_cluster["cx"],
            "cy": face_or_cluster["cy"],
            "w": face_or_cluster["w"],
            "h": face_or_cluster["h"],
            "frames": {0},
            "is_docked": (face_or_cluster["cy"] >= real_h * 0.48),
        }

    scale_x = real_w / 960.0
    scale_y = real_h / 540.0

    s_fx = int((cluster["cx"] - cluster["w"] // 2) / scale_x)
    s_fy = int((cluster["cy"] - cluster["h"] // 2) / scale_y)
    s_fw = max(12, int(cluster["w"] / scale_x))
    s_fh = max(12, int(cluster["h"] / scale_y))

    anchored_left = (s_fx < 960 * 0.16)
    anchored_right = ((s_fx + s_fw) > 960 * 0.84)
    anchored_top = (s_fy < 540 * 0.16)
    anchored_bottom = ((s_fy + s_fh) > 540 * 0.80)

    frame_indices = sorted(f for f in cluster.get("frames", {0}) if f < len(images) and images[f] is not None)
    if not frame_indices:
        frame_indices = [i for i, im in enumerate(images) if im is not None]
    if not frame_indices:
        return False, None

    left_cands, right_cands, top_cands, bot_cands = [], [], [], []
    per_frame_lines = {}

    for f_idx in frame_indices:
        small_gray = cv2.cvtColor(cv2.resize(images[f_idx], (960, 540), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(small_gray, 35, 115)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=45, maxLineGap=10)
        vlines, hlines = [], []
        if lines is not None:
            for l in lines:
                pts = l[0] if getattr(l, "ndim", 1) > 1 else l
                lx1, ly1, lx2, ly2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
                if abs(lx2 - lx1) <= 2 and abs(ly2 - ly1) >= 45:
                    vlines.append((int(round((lx1 + lx2) / 2.0)), min(ly1, ly2), max(ly1, ly2)))
                elif abs(ly2 - ly1) <= 2 and abs(lx2 - lx1) >= 45:
                    hlines.append((int(round((ly1 + ly2) / 2.0)), min(lx1, lx2), max(lx1, lx2)))
        per_frame_lines[f_idx] = (vlines, hlines)

        for x, y1, y2 in vlines:
            if (s_fx + s_fw) <= x <= min(960, s_fx + int(s_fw * 3.8)):
                if max(y1, s_fy - s_fh) <= min(y2, s_fy + s_fh * 2):
                    right_cands.append((f_idx, x, y1, y2))
            if max(0, s_fx - int(s_fw * 3.8)) <= x <= s_fx:
                if max(y1, s_fy - s_fh) <= min(y2, s_fy + s_fh * 2):
                    left_cands.append((f_idx, x, y1, y2))

        for y, x1, x2 in hlines:
            if max(0, s_fy - int(s_fh * 1.15)) <= y <= s_fy:
                if max(x1, s_fx - s_fw) <= min(x2, s_fx + s_fw * 2):
                    top_cands.append((f_idx, y, x1, x2))
            if (s_fy + s_fh) <= y <= min(540, s_fy + int(s_fh * 3.2)):
                if max(x1, s_fx - s_fw) <= min(x2, s_fx + s_fw * 2):
                    bot_cands.append((f_idx, y, x1, x2))

    def _persistent_edges(cands, n_frames):
        groups = []
        for f_i, coord, span_a, span_b in cands:
            placed = False
            for g in groups:
                if abs(coord - g["med"]) <= 4:
                    g["items"].append((f_i, coord, span_a, span_b))
                    g["frames"].add(f_i)
                    g["med"] = float(np.median([it[1] for it in g["items"]]))
                    placed = True
                    break
            if not placed:
                groups.append({"items": [(f_i, coord, span_a, span_b)], "frames": {f_i}, "med": float(coord)})
        req = 2 if n_frames >= 2 else 1
        return [g for g in groups if len(g["frames"]) >= req]

    n_f = len(frame_indices)
    p_left = _persistent_edges(left_cands, n_f)
    p_right = _persistent_edges(right_cands, n_f)
    p_top = _persistent_edges(top_cands, n_f)
    p_bot = _persistent_edges(bot_cands, n_f)

    # Pick right/left edges strongest + closest outside face
    def _pick_edge(groups, fallback, prefer_outer_min=False, prefer_outer_max=False):
        if not groups:
            return fallback, None
        if prefer_outer_max:
            groups.sort(key=lambda g: (-len(g["frames"]), -g["med"]))
        elif prefer_outer_min:
            groups.sort(key=lambda g: (-len(g["frames"]), g["med"]))
        else:
            groups.sort(key=lambda g: (-len(g["frames"]), -sum(it[3] - it[2] for it in g["items"])))
        return int(round(groups[0]["med"])), groups[0]

    bx1 = 0 if anchored_left else None
    bx2 = 960 if anchored_right else None
    bx1_grp, bx2_grp = None, None
    if bx1 is None:
        bx1, bx1_grp = _pick_edge(p_left, None)
    else:
        # Check if persistent inner left inset exists
        c_l, c_lg = _pick_edge(p_left, None)
        if c_l is not None and 8 < c_l < s_fx and anchored_right:
            bx1, bx1_grp = c_l, c_lg
    if bx2 is None:
        bx2, bx2_grp = _pick_edge(p_right, None)
    elif p_right and anchored_left:
        pass

    by1 = 0 if anchored_top else None
    by2 = 540 if anchored_bottom else None
    by1_grp, by2_grp = None, None

    # For bottom boundary of top box (like MeganPlays): prefer horizontal lines aligning cleanly to bx2 (not ending mid-chest)
    if by2 is None:
        if p_bot and bx2 is not None:
            # Prefer horizontal edge below chin+offset (s_fy + s_fh * 1.15) that ends cleanly near bx2 (not spanning full screen)
            scored_bot = []
            for g in p_bot:
                y_med = g["med"]
                max_x2 = max(it[3] for it in g["items"])
                min_x1 = min(it[2] for it in g["items"])
                box_w = max(50, bx2 - (bx1 or 0))
                ends_near_bx2 = abs(max_x2 - bx2) <= 25 or (bx1 is not None and max_x2 <= bx2 + 30)
                not_screenwide = (max_x2 - min_x1) <= box_w * 1.8
                below_torso = y_med >= s_fy + s_fh * 1.25
                sc = len(g["frames"]) * 10 + (15 if ends_near_bx2 else 0) + (10 if not_screenwide else -20) + (8 if below_torso else 0)
                scored_bot.append((sc, g))
            scored_bot.sort(key=lambda t: (-t[0], -t[1]["med"]))
            by2_grp = scored_bot[0][1]
            by2 = int(round(by2_grp["med"]))
        else:
            by2, by2_grp = _pick_edge(p_bot, None, prefer_outer_max=True)

    if by1 is None:
        by1, by1_grp = _pick_edge(p_top, None, prefer_outer_min=True)

    if bx1 is None or bx2 is None or by1 is None or by2 is None:
        return False, None
    if bx2 - bx1 < 60 or by2 - by1 < 60:
        return False, None

    # Anti-green-screen sanity check:
    # A genuine physical box tightly frames the face/shoulders and never stretches across the full screen height
    box_w = bx2 - bx1
    box_h = by2 - by1
    if box_h > max(270, int(s_fh * 3.1)):
        return False, None
    if anchored_bottom and by2 >= 520:
        # Bottom-docked green-screen guard: require BOTH an interior top border and interior side border
        # whose extents actually align closely with the box rather than spanning across the entire screen
        if not by1_grp or not (bx2_grp or bx1_grp):
            return False, None
        top_spans = [(it[3] - it[2]) for it in by1_grp["items"]]
        if min(top_spans) > box_w * 1.45:
            return False, None
        side_grp = bx2_grp if anchored_left else bx1_grp
        side_spans = [(it[3] - it[2]) for it in side_grp["items"]]
        # A green-screen streamer next to a webpage sidebar has side lines taller than the localized box or no tight top corner
        if max(side_spans) < box_h * 0.45 or max(side_spans) > box_h * 1.45:
            return False, None

    return True, (
        int(bx1 * scale_x),
        int(by1 * scale_y),
        int(bx2 * scale_x),
        int(by2 * scale_y),
    )


def sanitize_crop(cx: int, cy: int, fw: int, fh: int, camera_type: str, box_coords: tuple = None, real_w=1920, real_h=1080) -> dict:
    """
    Computes clean aspect-ratio crop coordinates (cam_x, cam_y, cam_w, cam_h)
    anchored cleanly to frame boundaries with even integers for FFmpeg compatibility.
    Matches 720:380 target webcam frame (~30% screen height) to give gameplay 70% space,
    while maintaining generous headroom and chin clearance for VTuber avatars and live webcams.
    """
    CAM_ASPECT = 720.0 / 380.0  # Matches zero-gap 720x380 split screen ratio (~1.895)

    if camera_type == "box" and box_coords is not None:
        if len(box_coords) == 4:
            b0, b1, b2, b3 = box_coords
            if b2 > b0 and b3 > b1 and (b2 - b0 >= 100) and (b3 - b1 >= 100) and b2 > 100:
                bx, by, bw, bh = b0, b1, b2 - b0, b3 - b1
            else:
                bx, by, bw, bh = b0, b1, b2, b3
        else:
            bx, by, bw, bh = 0, 0, real_w, real_h

        aspect = bw / float(bh) if bh > 0 else 1.0

        if aspect < 1.55:
            # Narrow or vertical physical box (phone streams, 4:3 boxes)
            # PRESERVE EXACT PHYSICAL BOUNDARIES: Zero game/menu bleed!
            cam_w = bw
            cam_h = bh
            cam_x = bx
            cam_y = by
        else:
            # Wide 16:9 physical box: crop within box centered on face
            target_h = max(230, min(bh, int(fh * 2.3)))
            target_w = int(target_h * CAM_ASPECT)
            if target_w > bw:
                target_w = bw
                target_h = int(target_w / CAM_ASPECT)

            cam_h = target_h
            cam_w = target_w
            cam_x = max(bx, min(bx + bw - cam_w, int(cx - (cam_w / 2.0))))
            cam_y = max(by, min(by + bh - cam_h, int(cy - (cam_h * 0.38))))

        final_type = "box"

    elif camera_type == "green_screen_docked" or cy >= real_h * 0.48 or (cy + fh // 2) >= real_h * 0.78:
        target_h = max(360, min(410, int(fh * 1.90)))
        target_w = int(target_h * CAM_ASPECT)
        cam_h = target_h
        cam_w = target_w

        eye_y = cy - int(0.12 * fh)
        cam_y = int(eye_y - cam_h * 0.38)
        head_top = cy - int(0.50 * fh)
        if cam_y > head_top - 35:
            cam_y = max(0, head_top - 35)

        if (cy + fh // 2) >= int(real_h * 0.80):
            cam_y = max(0, real_h - cam_h)
            if cam_y > head_top - 20:
                needed_h = real_h - max(0, head_top - 35)
                cam_h = min(460, needed_h)
                cam_w = int(cam_h * CAM_ASPECT)
                cam_y = real_h - cam_h

        cam_x = max(0, min(real_w - cam_w, int(cx - (cam_w / 2.0))))
        final_type = "green_screen_docked"

    else:
        target_h = max(240, min(440, int(fh * 2.3)))
        target_w = int(target_h * CAM_ASPECT)
        cam_h = target_h
        cam_w = target_w
        cam_x = max(0, min(real_w - cam_w, int(cx - (cam_w / 2.0))))
        cam_y = max(0, min(real_h - cam_h, int(cy - (cam_h * 0.38))))
        final_type = "floating"

    cam_x = max(0, min(real_w - 2, int((cam_x // 2) * 2)))
    cam_y = max(0, min(real_h - 2, int((cam_y // 2) * 2)))
    cam_w = max(2, min(real_w - cam_x, int((cam_w // 2) * 2)))
    cam_h = max(2, min(real_h - cam_y, int((cam_h // 2) * 2)))

    return {
        "ai_found": True,
        "camera_type": final_type,
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_w": cam_w,
        "cam_h": cam_h,
        "confidence": 0.98
    }


def compute_bulletproof_framing(face_or_cluster: dict, has_box: bool, box_coords: tuple, real_w=1920, real_h=1080):
    camera_type = "box" if has_box else "green_screen_docked" if face_or_cluster.get("is_docked", face_or_cluster["cy"] >= real_h * 0.48) else "floating"
    return sanitize_crop(face_or_cluster["cx"], face_or_cluster["cy"], face_or_cluster["w"], face_or_cluster["h"], camera_type, box_coords, real_w, real_h)


def compute_bulletproof_crop_from_vision(layout: dict, real_w=1920, real_h=1080) -> dict:
    """Computes framing from Vision API layout coordinates."""
    wb = layout.get("webcam_box", [0, 0, 0, 0])
    fb = layout.get("face_box", [0, 0, 0, 0])
    cam_type = layout.get("type", "box")

    by1 = int(wb[0] * real_h / 1000.0)
    bx1 = int(wb[1] * real_w / 1000.0)
    by2 = int(wb[2] * real_h / 1000.0)
    bx2 = int(wb[3] * real_w / 1000.0)

    fy1 = int(fb[0] * real_h / 1000.0)
    fx1 = int(fb[1] * real_w / 1000.0)
    fy2 = int(fb[2] * real_h / 1000.0)
    fx2 = int(fb[3] * real_w / 1000.0)

    face = {
        "x": fx1, "y": fy1,
        "w": max(1, fx2 - fx1), "h": max(1, fy2 - fy1),
        "cx": (fx1 + fx2) // 2, "cy": (fy1 + fy2) // 2
    }
    has_box = (cam_type == "box")
    box_coords = (bx1, by1, bx2, by2) if has_box else None

    return compute_bulletproof_framing(face, has_box, box_coords, real_w, real_h)


def build_piecewise_timeline(frames, loaded_imgs, dets_per_frame, primary_crop, detector, real_w=1920, real_h=1080):
    """
    Checks if facecam shifted position across the reference frame timeline.
    Outputs a timestamped list of layout coordinates.
    """
    timestamps = []
    for idx, f in enumerate(frames):
        ts = 180.0 + idx * 270.0
        base = os.path.basename(f)
        if "ref_1" in base: ts = 180.0
        elif "ref_2" in base: ts = 450.0
        elif "ref_3" in base: ts = 720.0
        elif "ref_4" in base: ts = 990.0
        elif "ref_5" in base: ts = 1260.0
        timestamps.append(ts)

    p_cx = primary_crop["cam_x"] * real_w + (primary_crop["cam_w"] * real_w) / 2.0
    p_cy = primary_crop["cam_y"] * real_h + (primary_crop["cam_h"] * real_h) / 2.0

    frame_crops = []
    for idx, dets in enumerate(dets_per_frame):
        t = timestamps[idx] if idx < len(timestamps) else idx * 300.0
        if not dets:
            frame_crops.append((t, primary_crop))
            continue

        best_d = 999999
        closest_f = None
        for d in dets:
            dist = math.hypot(d["cx"] - p_cx, d["cy"] - p_cy)
            if dist < best_d:
                best_d = dist
                closest_f = d

        if best_d > 180 and closest_f and closest_f.get("confidence", 0) > 0.6:
            has_b, b_coords = find_physical_box_borders(loaded_imgs[idx:idx+1], closest_f, real_w, real_h)
            shift_crop = compute_bulletproof_framing(closest_f, has_b, b_coords, real_w, real_h)
            frame_crops.append((t, shift_crop))
        else:
            frame_crops.append((t, primary_crop))

    if not frame_crops:
        return [{
            "start": 0.0, "end": 999999.0,
            "cam_x": primary_crop["cam_x"], "cam_y": primary_crop["cam_y"],
            "cam_w": primary_crop["cam_w"], "cam_h": primary_crop["cam_h"],
            "camera_type": primary_crop["camera_type"]
        }]

    timeline = []
    curr_crop = frame_crops[0][1]
    seg_start = 0.0

    for idx in range(1, len(frame_crops)):
        t, c = frame_crops[idx]
        dx = abs(c["cam_x"] - curr_crop["cam_x"])
        dy = abs(c["cam_y"] - curr_crop["cam_y"])
        if dx > 0.08 or dy > 0.08:
            prev_t = frame_crops[idx - 1][0]
            split_t = (prev_t + t) / 2.0
            timeline.append({
                "start": round(seg_start, 1),
                "end": round(split_t, 1),
                "cam_x": curr_crop["cam_x"], "cam_y": curr_crop["cam_y"],
                "cam_w": curr_crop["cam_w"], "cam_h": curr_crop["cam_h"],
                "camera_type": curr_crop["camera_type"]
            })
            curr_crop = c
            seg_start = split_t

    timeline.append({
        "start": round(seg_start, 1),
        "end": 999999.0,
        "cam_x": curr_crop["cam_x"], "cam_y": curr_crop["cam_y"],
        "cam_w": curr_crop["cam_w"], "cam_h": curr_crop["cam_h"],
        "camera_type": curr_crop["camera_type"]
    })

    return timeline


def is_static_png_overlay(
    images: list,
    face_box: dict,
    real_w: int = 1920,
    real_h: int = 1080,
    active_indices: set | list | None = None,
) -> bool:
    """
    Compares pixel variance inside the candidate face bounding box across face-containing reference frames.
    Returns True ONLY if the candidate face is a genuine static PNG/cartoon sticker (near-zero motion across frames).
    """
    src_imgs = images or []
    if active_indices:
        chosen = [src_imgs[i] for i in sorted(active_indices) if 0 <= i < len(src_imgs) and src_imgs[i] is not None]
        valid_imgs = chosen if len(chosen) >= 2 else [im for im in src_imgs if im is not None]
    else:
        valid_imgs = [im for im in src_imgs if im is not None]
    if len(valid_imgs) < 2 or not face_box:
        return False

    cx = float(face_box.get("cx", 0))
    cy = float(face_box.get("cy", 0))
    fw = max(16.0, float(face_box.get("w", 0)))
    fh = max(16.0, float(face_box.get("h", 0)))

    rois = []
    for im in valid_imgs:
        ih, iw = im.shape[:2]
        sx, sy = iw / float(real_w), ih / float(real_h)
        # Inner 68% of candidate face box captures head/mouth/eyes while avoiding outer game bleed
        x1 = max(0, int((cx - fw * 0.34) * sx))
        y1 = max(0, int((cy - fh * 0.34) * sy))
        x2 = min(iw, int((cx + fw * 0.34) * sx))
        y2 = min(ih, int((cy + fh * 0.34) * sy))
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        gray = cv2.cvtColor(im[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.float32)
        rois.append(gray)

    if len(rois) < 2:
        return False

    target_h, target_w = rois[0].shape[:2]
    rois = [
        cv2.resize(r, (target_w, target_h)) if r.shape[:2] != (target_h, target_w) else r
        for r in rois
    ]

    pair_meds, pair_p90s, pair_means, pair_unch = [], [], [], []
    for i in range(len(rois)):
        for j in range(i + 1, len(rois)):
            diff = np.abs(rois[i] - rois[j])
            pair_meds.append(float(np.median(diff)))
            pair_p90s.append(float(np.percentile(diff, 90)))
            pair_means.append(float(np.mean(diff)))
            pair_unch.append(float(np.mean(diff < 3.0)))

    mean_med_diff = float(np.mean(pair_meds))
    max_p90 = float(np.max(pair_p90s))
    mean_diff = float(np.mean(pair_means))
    min_unchanged = float(np.min(pair_unch))
    temporal_std = float(np.mean(np.std(np.stack(rois, axis=0), axis=0)))

    log(
        f"Face ROI motion check (n={len(rois)}): med={mean_med_diff:.2f}, max_p90={max_p90:.2f}, "
        f"mean={mean_diff:.2f}, temporal_std={temporal_std:.2f}, min_unchanged={min_unchanged:.2f}"
    )
    is_static = (temporal_std < 5.0 and max_p90 < 14.0) or (mean_diff < 3.5 and min_unchanged > 0.72)
    if is_static:
        log("REJECTED static PNG/cartoon overlay (near-zero pixel variance across reference frames).")
        return True
    return False


def _is_low_detail_ad_frame(img) -> bool:
    """Detects uniform gradient commercial break / blank screens."""
    if img is None:
        return True
    small = cv2.cvtColor(cv2.resize(img, (320, 180), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    lap_var = float(cv2.Laplacian(small, cv2.CV_32F).var())
    return lap_var < 18.0


def save_and_output(result: dict, out_config: str):
    if out_config and out_config != "/dev/null":
        try:
            os.makedirs(os.path.dirname(out_config), exist_ok=True)
            with open(out_config, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            log(f"Error saving {out_config}: {e}")
    print(json.dumps(result))


def run_pipeline(input_arg: str = "/files/temp/ref_*.jpg", out_config: str = DEFAULT_CONFIG_PATH, video_arg: str = "") -> dict:
    """
    Main Pipeline:
    1. Gathers distributed reference frames (or samples 7 distributed frames across video when needed).
    2. Runs fast local OpenCV YuNet DNN multi-frame spatial clustering first to pinpoint streamer frames & reject ads.
    3. Cross-checks with Gemini Vision (rotated keys + models) using face-active / non-blank frames.
    4. Snaps physical box borders accurately in any corner/edge and verifies real live motion.
    5. Outputs clean JSON and saves to disk.
    """
    fallback_res = {
        "ai_found": False,
        "camera_type": "none",
        "cam_x": 0, "cam_y": 0, "cam_w": 0, "cam_h": 0,
        "confidence": 0.0
    }

    # 1. Resolve Reference Frames
    if os.path.isfile(input_arg):
        frames = [input_arg]
    else:
        frames = sorted(glob.glob(input_arg))

    if (not frames or len(frames) <= 2) and video_arg and os.path.isfile(video_arg):
        log(f"Sampling 7 distributed reference frames from {video_arg}...")
        cap = cv2.VideoCapture(video_arg)
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total > 0:
                frames = []
                for i, r in enumerate([0.06, 0.19, 0.33, 0.48, 0.63, 0.77, 0.90]):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, max(0, int(total * r))))
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        out_p = f"/files/temp/auto_ref_{i+1}.jpg"
                        cv2.imwrite(out_p, frame)
                        frames.append(out_p)
            cap.release()

    if not frames:
        log("No reference frames available. Returning fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    log(f"Loaded {len(frames)} reference frame(s): {[os.path.basename(f) for f in frames]}")
    loaded_pairs = [(f, cv2.imread(f)) for f in frames]
    loaded_pairs = [(f, im) for f, im in loaded_pairs if im is not None]
    frames = [f for f, _ in loaded_pairs]
    loaded_imgs = [im for _, im in loaded_pairs]
    if not loaded_imgs:
        log("Failed reading any reference image. Returning fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    # 2. Fast Local YuNet Clustering First (gives active face frame indices & offline resilience)
    best_cluster = None
    if os.path.exists(YUNET_MODEL):
        detector = cv2.FaceDetectorYN.create(YUNET_MODEL, "", (960, 540), score_threshold=0.45)
        dets_per_frame = [detect_faces_yunet(img, detector) for img in loaded_imgs]
        best_cluster = cluster_faces_across_frames(dets_per_frame)

    if best_cluster is not None:
        log(
            f"Local YuNet cluster: cx={best_cluster['cx']}, cy={best_cluster['cy']}, "
            f"w={best_cluster['w']}, h={best_cluster['h']} (Persistence: {best_cluster['persistence']}/{len(loaded_imgs)})"
        )
        if is_static_png_overlay(loaded_imgs, best_cluster, active_indices=best_cluster.get("frames")):
            log("Local YuNet cluster rejected: Static PNG overlay detected across reference frames.")
            best_cluster = None

    # 3. Gemini Vision Cross-Check / VTuber Detection using active non-ad frames
    api_keys = collect_gemini_api_keys()
    vision_layout = None
    if api_keys:
        if best_cluster and best_cluster.get("frames"):
            f_idxs = sorted(i for i in best_cluster["frames"] if 0 <= i < len(frames))
            if len(f_idxs) > 3:
                f_idxs = [f_idxs[0], f_idxs[len(f_idxs) // 2], f_idxs[-1]]
            vision_frames = [frames[i] for i in f_idxs]
        else:
            active_idxs = [i for i, im in enumerate(loaded_imgs) if not _is_low_detail_ad_frame(im)]
            if not active_idxs:
                active_idxs = list(range(len(frames)))
            if len(active_idxs) > 3:
                active_idxs = [active_idxs[0], active_idxs[len(active_idxs) // 2], active_idxs[-1]]
            vision_frames = [frames[i] for i in active_idxs]

        vision_layout = detect_streamer_gemini_vision(vision_frames, api_keys=api_keys)

    if vision_layout is not None:
        if vision_layout.get("has_streamer"):
            fb = vision_layout.get("face_box") or [0, 0, 0, 0]
            wb = vision_layout.get("webcam_box") or [0, 0, 0, 0]
            # Validate Gemini agrees with persistent >=3/5 cluster when one exists
            v_cy = ((wb[0] + wb[2]) / 2.0) * 1080.0 / 1000.0 if len(wb) == 4 else 0
            v_cx = ((wb[1] + wb[3]) / 2.0) * 1920.0 / 1000.0 if len(wb) == 4 else 0
            cluster_conflict = (
                best_cluster is not None
                and best_cluster["persistence"] >= 3
                and math.hypot(v_cx - best_cluster["cx"], v_cy - best_cluster["cy"]) > 420.0
            )
            if not cluster_conflict:
                box_src = fb if (len(fb) == 4 and (fb[2] - fb[0]) > 5 and (fb[3] - fb[1]) > 5) else wb
                v_static = False
                if len(box_src) == 4 and (box_src[2] - box_src[0]) > 5 and (box_src[3] - box_src[1]) > 5:
                    vy1, vx1, vy2, vx2 = [float(v) for v in box_src]
                    v_face = {
                        "cx": ((vx1 + vx2) / 2.0) * 1920.0 / 1000.0,
                        "cy": ((vy1 + vy2) / 2.0) * 1080.0 / 1000.0,
                        "w": max(16.0, (vx2 - vx1) * 1920.0 / 1000.0),
                        "h": max(16.0, (vy2 - vy1) * 1080.0 / 1000.0),
                    }
                    active_set = best_cluster.get("frames") if (best_cluster and math.hypot(v_face["cx"] - best_cluster["cx"], v_face["cy"] - best_cluster["cy"]) < 260) else None
                    v_static = is_static_png_overlay(loaded_imgs, v_face, active_indices=active_set)
                if not v_static:
                    clean_crop = compute_bulletproof_crop_from_vision(vision_layout)
                    log(f"VERIFIED WEBCAM (Vision): {clean_crop['camera_type']} at x={clean_crop['cam_x']}, y={clean_crop['cam_y']}, {clean_crop['cam_w']}x{clean_crop['cam_h']}")
                    save_and_output(clean_crop, out_config)
                    return clean_crop
                log("Gemini Vision candidate rejected: Static PNG overlay.")
            else:
                log("Gemini Vision box differed from strong local cluster; using local cluster + persistent borders.")
        else:
            # Gemini explicitly said NO live streamer. Allow strong persistent live corner/docked cluster (>=3/5)
            # only if single noisy frame; veto transient/weak <=2 detections.
            if best_cluster is None or best_cluster["persistence"] < 3:
                log("Gemini Vision confirmed NO streamer facecam (pure gameplay).")
                save_and_output(fallback_res, out_config)
                return fallback_res

    # 4. Fallback / Autonomous Local Engine: Persistent Box Borders + Bulletproof Framing
    if best_cluster is None:
        log("No persistent streamer facecam detected across frames (pure gameplay).")
        save_and_output(fallback_res, out_config)
        return fallback_res

    has_box, box_coords = find_physical_box_borders(loaded_imgs, best_cluster)
    clean_crop = compute_bulletproof_framing(best_cluster, has_box, box_coords)
    log(f"VERIFIED WEBCAM (Local Engine): {clean_crop['camera_type']} at x={clean_crop['cam_x']}, y={clean_crop['cam_y']}, {clean_crop['cam_w']}x{clean_crop['cam_h']}")
    save_and_output(clean_crop, out_config)
    return clean_crop


if __name__ == "__main__":
    arg_pattern = sys.argv[1] if len(sys.argv) > 1 else "/files/temp/ref_*.jpg"
    arg_out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CONFIG_PATH
    arg_video = sys.argv[3] if len(sys.argv) > 3 else ""
    run_pipeline(arg_pattern, arg_out, arg_video)
