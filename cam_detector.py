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
    "/files/temp/all_ai_creds.json"
]
TARGET_ASPECT = 720.0 / 380.0  # 1.8947 matching zero-gap Short top box (720x380)


def log(msg: str):
    print(f"[CamDetector] {msg}", file=sys.stderr)


def get_gemini_api_key() -> str:
    """Resolves Gemini API key from environment or local credentials."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key and len(key) > 20:
        return key

    for kpath in GEMINI_KEY_FILES:
        if os.path.exists(kpath):
            try:
                with open(kpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if kpath.endswith(".json"):
                    creds = json.loads(content)
                    for c in creds:
                        if "gemini" in c.get("type", "").lower() or "palm" in c.get("type", "").lower():
                            k = c.get("apiKey", "").strip()
                            if k:
                                return k
                elif content and len(content) > 20:
                    return content
            except Exception as e:
                log(f"Warning: Failed reading {kpath}: {e}")

    return ""


def detect_streamer_gemini_vision(img_path: str, api_key: str) -> dict:
    """Calls Gemini 2.5 Flash Vision to identify streamer presence and exact boundaries."""
    if not os.path.isfile(img_path) or not api_key:
        return None

    try:
        with open(img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "Analyze this gaming livestream frame to detect the streamer's camera layout for a vertical YouTube Short crop.\n"
            "Identify:\n"
            "1. Is there a LIVE streamer webcam or live VTuber avatar? (CRITICAL: In-game gameplay characters, passing banner signs, or logos = FALSE).\n"
            "2. Camera type: 'box' (streamer is in a distinct rectangular webcam box with their bedroom/room/studio background or vertical phone stream box) "
            "OR 'green_screen' (streamer has transparent cutout background directly over the game).\n"
            "3. Exact outer boundaries of the webcam:\n"
            "   - If 'box': Find the EXACT [ymin, xmin, ymax, xmax] coordinates (0 to 1000 scale) of the ENTIRE physical webcam box rectangle. "
            "     CRITICAL: Do NOT include any game screen, website menus, or stream UI outside the webcam border!\n"
            "   - If 'green_screen': Find the [ymin, xmin, ymax, xmax] coordinates (0 to 1000 scale) enclosing the streamer from top of head/hair down to their bottom edge, and shoulders.\n"
            "4. Exact streamer face/head box in normalized [ymin, xmin, ymax, xmax] (0 to 1000 scale).\n\n"
            "Return strictly JSON:\n"
            "{\n"
            '  "has_streamer": true,\n'
            '  "type": "box" | "green_screen",\n'
            '  "webcam_box": [ymin, xmin, ymax, xmax],\n'
            '  "face_box": [ymin, xmin, ymax, xmax]\n'
            "}\n"
            "If NO live streamer exists, return: {\"has_streamer\": false, \"type\": \"none\", \"webcam_box\": [0,0,0,0], \"face_box\": [0,0,0,0]}"
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}}
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 1024
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=12) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                all_text = ""
                for p in candidates[0].get("content", {}).get("parts", []):
                    if "text" in p and p["text"]:
                        all_text += p["text"]
                clean_text = all_text.strip()
                if clean_text.startswith("```"):
                    clean_text = clean_text.split("\n", 1)[-1]
                if clean_text.endswith("```"):
                    clean_text = clean_text.rsplit("\n", 1)[0]
                clean_text = clean_text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_text)
                log(f"Gemini Vision Output: has_streamer={parsed.get('has_streamer')}, type={parsed.get('type')}, box={parsed.get('webcam_box')}")
                return {
                    "has_streamer": bool(parsed.get("has_streamer", False)),
                    "type": str(parsed.get("type", "none")),
                    "webcam_box": parsed.get("webcam_box", [0, 0, 0, 0]),
                    "face_box": parsed.get("face_box", [0, 0, 0, 0]),
                    "confidence": 0.98 if parsed.get("has_streamer") else 0.0
                }
    except Exception as e:
        log(f"Gemini Vision API call failed: {e}")

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
    Detects straight continuous border lines (dx <= 2 or dy <= 2) enclosing the face.
    Handles both single-image calls (legacy) and multi-image cluster calls.
    Ensures lines do not cut inside the streamer's face or body.
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
            "is_docked": (face_or_cluster["cy"] >= real_h * 0.48)
        }

    scale_x = real_w / 960.0
    scale_y = real_h / 540.0

    s_fx = int((cluster["cx"] - cluster["w"] // 2) / scale_x)
    s_fy = int((cluster["cy"] - cluster["h"] // 2) / scale_y)
    s_fw = int(cluster["w"] / scale_x)
    s_fh = int(cluster["h"] / scale_y)

    anchored_left = (s_fx < 960 * 0.20)
    anchored_right = ((s_fx + s_fw) > 960 * 0.80)
    anchored_top = (s_fy < 540 * 0.22)
    anchored_bottom = ((s_fy + s_fh) > 540 * 0.80)

    # Pure bottom-docked streamers are green-screen cutouts; don't search for table/room boxes
    if cluster.get("is_docked") and not (anchored_left and anchored_top):
        return False, None

    detected_boxes = []

    for f_idx in cluster.get("frames", {0}):
        if f_idx >= len(images):
            continue
        img = images[f_idx]
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small_gray = cv2.resize(gray, (960, 540), interpolation=cv2.INTER_AREA)
        edges = cv2.Canny(small_gray, 40, 120)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=35, minLineLength=50, maxLineGap=12)
        if lines is None:
            continue

        vert_lines = []
        horiz_lines = []
        for line in lines:
            lx1, ly1, lx2, ly2 = line[0]
            dx = abs(lx2 - lx1)
            dy = abs(ly2 - ly1)
            if dx <= 2 and dy >= 50:
                vert_lines.append((min(lx1, lx2), min(ly1, ly2), max(ly1, ly2), dy))
            elif dy <= 2 and dx >= 50:
                horiz_lines.append((min(ly1, ly2), min(lx1, lx2), max(lx1, lx2), dx))

        bx1 = 0 if anchored_left else None
        by1 = 0 if anchored_top else None
        bx2 = 960 if anchored_right else None
        by2 = 540 if anchored_bottom else None

        # Search right border (MUST be strictly to the right of face)
        if anchored_left and bx2 is None:
            cands = [x for x, y1, y2, l in vert_lines if (s_fx + s_fw) <= x <= min(960, s_fx + int(s_fw * 3.5)) and max(y1, s_fy) <= min(y2, s_fy + s_fh + 120)]
            if cands:
                bx2 = min(cands)

        # Search bottom border (MUST be strictly below face/chin)
        if anchored_top and by2 is None:
            cands = [y for y, x1, x2, l in horiz_lines if (s_fy + s_fh) <= y <= min(540, s_fy + int(s_fh * 3.5)) and max(x1, 0) <= min(x2, bx2 if bx2 else 960)]
            if cands:
                by2 = min(cands)

        # Search left border
        if anchored_right and bx1 is None:
            cands = [x for x, y1, y2, l in vert_lines if max(0, s_fx - int(s_fw * 2.5)) <= x <= s_fx]
            if cands:
                bx1 = max(cands)

        # Search top border
        if anchored_bottom and by1 is None:
            cands = [y for y, x1, x2, l in horiz_lines if max(0, s_fy - int(s_fh * 2.5)) <= y <= s_fy]
            if cands:
                by1 = max(cands)

        if bx1 is not None and bx2 is not None and by1 is not None and by2 is not None:
            norm_box = (
                int(bx1 * scale_x),
                int(by1 * scale_y),
                int(bx2 * scale_x),
                int(by2 * scale_y)
            )
            detected_boxes.append(norm_box)

    if detected_boxes:
        med_bx1 = int(np.median([b[0] for b in detected_boxes]))
        med_by1 = int(np.median([b[1] for b in detected_boxes]))
        med_bx2 = int(np.median([b[2] for b in detected_boxes]))
        med_by2 = int(np.median([b[3] for b in detected_boxes]))
        return True, (med_bx1, med_by1, med_bx2, med_by2)

    return False, None


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
    1. Gathers reference frames (or samples 5 distributed frames across video).
    2. Runs Gemini 2.5 Flash Vision Ground-Truth Detection (if available).
    3. Runs OpenCV YuNet Multi-Frame Spatial Clustering & Consensus.
    4. Runs Geometric Border Snapping for physical webcam boxes.
    5. Computes bulletproof framing & centering.
    6. Outputs clean JSON and saves to disk.
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

    if (not frames or len(frames) <= 1) and video_arg and os.path.isfile(video_arg):
        log(f"Sampling distributed reference frames from {video_arg}...")
        cap = cv2.VideoCapture(video_arg)
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total > 0:
                frames = []
                for i, r in enumerate([0.15, 0.32, 0.50, 0.68, 0.85]):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * r))
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

    # 2. Primary Cloud Engine: Gemini 2.5 Flash Vision Ground-Truth Detection
    api_key = get_gemini_api_key()
    if api_key:
        primary_frame = frames[len(frames) // 2]
        vision_layout = detect_streamer_gemini_vision(primary_frame, api_key)

        if vision_layout is not None:
            if not vision_layout.get("has_streamer"):
                log("Gemini Vision confirmed NO streamer facecam (pure gameplay).")
                save_and_output(fallback_res, out_config)
                return fallback_res

            clean_crop = compute_bulletproof_crop_from_vision(vision_layout)
            log(f"VERIFIED WEBCAM (Vision): {clean_crop['camera_type']} at x={clean_crop['cam_x']}, y={clean_crop['cam_y']}, {clean_crop['cam_w']}x{clean_crop['cam_h']}")
            save_and_output(clean_crop, out_config)
            return clean_crop

    # 3. Autonomous Local Engine: OpenCV YuNet DNN + Multi-Frame Spatial Clustering
    log("Running autonomous local OpenCV YuNet + Spatial Clustering + Geometric Border Engine...")
    if not os.path.exists(YUNET_MODEL):
        log(f"Error: YuNet model not found at {YUNET_MODEL}. Returning fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    detector = cv2.FaceDetectorYN.create(YUNET_MODEL, "", (960, 540), score_threshold=0.45)
    loaded_imgs = []
    dets_per_frame = []
    for fpath in frames:
        img = cv2.imread(fpath)
        if img is not None:
            loaded_imgs.append(img)
            dets = detect_faces_yunet(img, detector)
            dets_per_frame.append(dets)

    best_cluster = cluster_faces_across_frames(dets_per_frame)
    if best_cluster is None:
        log("No persistent streamer facecam detected across frames (pure gameplay).")
        save_and_output(fallback_res, out_config)
        return fallback_res

    log(f"Streamer cluster found: cx={best_cluster['cx']}, cy={best_cluster['cy']}, w={best_cluster['w']}, h={best_cluster['h']} (Persistence: {best_cluster['persistence']}/{len(loaded_imgs)})")

    # Check for physical straight box borders
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
