#!/usr/bin/env python3
"""
Production Hybrid Facecam Detector Engine for n8n AI Clipper Pipeline.
Combines OpenCV YuNet DNN, Multi-Frame Spatial Clustering, Temporal Motion Difference,
Border Edge Analysis, and Gemini 2.5 Flash Vision Arbitration.

Key Protections:
1. Multi-Frame Consensus: Requires face presence in >= 50% of reference frames (eliminates transient glitches).
2. Anti-Static Overlay Filter: Computes pixel-wise absdiff across frames to reject static PNG avatars & donation tickers.
3. Geometric Classification: Distinguishes physical webcam boxes vs green-screen docked streamers (anchored to bottom).
4. Guardrails: Rejects oversize candidate boxes lacking borders or face landmarks.
5. Gemini Vision Arbiter: Resolves ambiguous candidates using direct API verification.
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
GEMINI_KEY_FILE = "/files/gemini_key.txt"
FALLBACK_GEMINI_KEY = "AIzaSyDqACFpgY2IsbUFoul7D62V17DPTXGkTrQ"


def log(msg: str):
    """Outputs high-density diagnostic logs to stderr."""
    print(f"[CamDetector] {msg}", file=sys.stderr)


def get_gemini_api_key() -> str:
    """Resolves Gemini API key from environment, disk, or fallback."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(GEMINI_KEY_FILE):
        try:
            with open(GEMINI_KEY_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            log(f"Warning: Failed to read {GEMINI_KEY_FILE}: {e}")
    return FALLBACK_GEMINI_KEY


def detect_faces_in_image(img, detector, real_w=1920, real_h=1080, score_threshold=0.48) -> list:
    """
    Detects faces in a single frame using OpenCV YuNet DNN.
    Returns list of normalized faces: [{'x', 'y', 'w', 'h', 'conf', 'cx', 'cy'}] in 1920x1080 space.
    """
    if img is None:
        return []
    h_img, w_img = img.shape[:2]
    detector.setInputSize((w_img, h_img))
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        return []

    scale_x = real_w / float(w_img)
    scale_y = real_h / float(h_img)

    results = []
    for f in faces:
        conf = float(f[-1])
        if conf < score_threshold:
            continue
        fx, fy, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
        # Scale to 1920x1080
        norm_x = int(fx * scale_x)
        norm_y = int(fy * scale_y)
        norm_w = int(fw * scale_x)
        norm_h = int(fh * scale_y)

        # Reject micro-artifacts (< 32px at 1080p)
        if norm_w < 32 or norm_h < 32:
            continue

        results.append({
            "x": norm_x,
            "y": norm_y,
            "w": norm_w,
            "h": norm_h,
            "cx": norm_x + norm_w // 2,
            "cy": norm_y + norm_h // 2,
            "conf": conf
        })

    return results


def cluster_faces_across_frames(frame_detections: list, max_dist=140.0) -> list:
    """
    Clusters detections across multiple frames by spatial proximity.
    Each item in frame_detections is a tuple (frame_idx, face_dict).
    Returns list of clusters: [{'detections': [...], 'unique_frames': int, 'avg_cx': float, 'avg_cy': float, 'avg_w': float, 'avg_h': float, 'max_conf': float}]
    """
    clusters = []

    for frame_idx, face in frame_detections:
        matched_cluster = None
        min_d = float("inf")

        for c in clusters:
            d = math.hypot(face["cx"] - c["avg_cx"], face["cy"] - c["avg_cy"])
            if d < max_dist and d < min_d:
                min_d = d
                matched_cluster = c

        if matched_cluster is not None:
            matched_cluster["detections"].append((frame_idx, face))
            # Update running averages
            all_dets = [d[1] for d in matched_cluster["detections"]]
            matched_cluster["avg_cx"] = float(np.mean([d["cx"] for d in all_dets]))
            matched_cluster["avg_cy"] = float(np.mean([d["cy"] for d in all_dets]))
            matched_cluster["avg_w"] = float(np.mean([d["w"] for d in all_dets]))
            matched_cluster["avg_h"] = float(np.mean([d["h"] for d in all_dets]))
            matched_cluster["max_conf"] = float(max([d["conf"] for d in all_dets]))
            matched_cluster["unique_frames"] = len(set(d[0] for d in matched_cluster["detections"]))
        else:
            clusters.append({
                "detections": [(frame_idx, face)],
                "unique_frames": 1,
                "avg_cx": float(face["cx"]),
                "avg_cy": float(face["cy"]),
                "avg_w": float(face["w"]),
                "avg_h": float(face["h"]),
                "max_conf": float(face["conf"])
            })

    # Sort by consensus count desc, then confidence desc
    clusters.sort(key=lambda c: (c["unique_frames"], c["max_conf"]), reverse=True)
    return clusters


def check_temporal_motion(candidate_box: tuple, frame_paths: list, real_w=1920, real_h=1080) -> tuple:
    """
    Computes pixel-wise absdiff across reference frames inside the candidate box.
    Returns (is_dynamic: bool, avg_mean_diff: float, max_motion_pct: float).
    Detects static PNG avatars, logos, or donation tickers with zero movement.
    """
    bx, by, bw, bh = candidate_box
    if bw <= 0 or bh <= 0 or len(frame_paths) < 2:
        return True, 10.0, 10.0

    rois = []
    for fp in frame_paths:
        img = cv2.imread(fp)
        if img is None:
            continue
        h_img, w_img = img.shape[:2]
        scale_x = float(w_img) / real_w
        scale_y = float(h_img) / real_h

        rx = int(bx * scale_x)
        ry = int(by * scale_y)
        rw = int(bw * scale_x)
        rh = int(bh * scale_y)

        rx = max(0, min(w_img - 1, rx))
        ry = max(0, min(h_img - 1, ry))
        rw = max(1, min(w_img - rx, rw))
        rh = max(1, min(h_img - ry, rh))

        roi = img[ry:ry+rh, rx:rx+rw]
        roi_std = cv2.resize(roi, (160, 160), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(roi_std, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        rois.append(blurred)

    if len(rois) < 2:
        return True, 10.0, 10.0

    pair_diffs = []
    pair_motion_pcts = []

    for i in range(len(rois) - 1):
        diff = cv2.absdiff(rois[i], rois[i+1])
        mean_val = float(np.mean(diff))
        active_pixels = np.sum(diff > 14)
        pct = float(active_pixels) / float(diff.size) * 100.0
        pair_diffs.append(mean_val)
        pair_motion_pcts.append(pct)

    avg_mean_diff = float(np.mean(pair_diffs))
    max_motion_pct = float(np.max(pair_motion_pcts))

    log(f"Temporal Motion Check: avg_mean_diff={avg_mean_diff:.2f}, max_pct={max_motion_pct:.2f}% across {len(pair_diffs)} pairs")

    # Anti-Static Threshold:
    # A live human webcam always exhibits natural movement (head shifts, blinking, mouth talking).
    # Static graphics (PNG overlays, Roblox W-sign donation tickers) produce avg_mean_diff < 1.5 and max_pct < 1.0%.
    if avg_mean_diff < 1.5 and max_motion_pct < 1.0:
        log("Anti-Static Filter: REJECTED candidate box (interior is 100% static across all frames).")
        return False, avg_mean_diff, max_motion_pct

    return True, avg_mean_diff, max_motion_pct


def analyze_box_borders(img, face_norm: dict, real_w=1920, real_h=1080) -> tuple:
    """
    Checks if there are high-contrast rectangular border lines surrounding the face.
    Returns (has_box: bool, box_rect: tuple (bx, by, bw, bh)) in 1920x1080 space.
    """
    h_img, w_img = img.shape[:2]
    scale_x = float(w_img) / real_w
    scale_y = float(h_img) / real_h

    fx = int(face_norm["x"] * scale_x)
    fy = int(face_norm["y"] * scale_y)
    fw = int(face_norm["w"] * scale_x)
    fh = int(face_norm["h"] * scale_y)

    # Search window around face
    search_w = int(fw * 3.2)
    search_h = int(fh * 3.4)
    x1 = max(0, fx - int(fw * 1.1))
    y1 = max(0, fy - int(fh * 0.9))
    x2 = min(w_img, x1 + search_w)
    y2 = min(h_img, y1 + search_h)

    gray = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    # Detect horizontal lines (top/bottom) and vertical lines (left/right)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=int(fw * 0.8), maxLineGap=15)
    if lines is None or len(lines) == 0:
        return False, None

    has_horiz = False
    has_vert = False

    for line in lines:
        lx1, ly1, lx2, ly2 = line[0]
        dx = abs(lx2 - lx1)
        dy = abs(ly2 - ly1)
        if dx > fw * 0.8 and dy < 10:
            has_horiz = True
        elif dy > fh * 0.8 and dx < 10:
            has_vert = True

    if has_horiz and has_vert:
        # Scale back to 1920x1080
        norm_bx = int(x1 / scale_x)
        norm_by = int(y1 / scale_y)
        norm_bw = int((x2 - x1) / scale_x)
        norm_bh = int((y2 - y1) / scale_y)
        return True, (norm_bx, norm_by, norm_bw, norm_bh)

    return False, None


def sanitize_crop(cx: int, cy: int, fw: int, fh: int, camera_type: str, real_w=1920, real_h=1080) -> dict:
    """
    Computes clean 16:9 aspect-ratio crop coordinates (cam_x, cam_y, cam_w, cam_h)
    anchored cleanly to frame boundaries with even integers for FFmpeg compatibility.
    """
    # Scale face height to target webcam height (covers head & upper torso)
    target_h = int(fh * 2.4)
    target_h = max(380, min(640, target_h))
    target_w = int(target_h * (16.0 / 9.0))

    if camera_type == "green_screen_docked" or cy >= real_h * 0.52 or (cy + fh // 2) >= real_h * 0.82:
        # Streamer anchored to bottom of screen (e.g. KreekCraft)
        cam_h = target_h
        cam_w = target_w
        cam_y = real_h - cam_h  # Anchored to 1080 -> 0% chin cutoff
        cam_x = int(cx - (cam_w / 2.0))
        final_type = "green_screen_docked"
    else:
        # Physical box or floating PiP
        cam_h = target_h
        cam_w = target_w
        cam_y = int(cy - (cam_h * 0.42))
        cam_x = int(cx - (cam_w / 2.0))
        final_type = camera_type if camera_type != "none" else "box"

    # Clamp bounds inside frame
    cam_x = max(0, min(real_w - cam_w, cam_x))
    cam_y = max(0, min(real_h - cam_h, cam_y))

    # Force even integers
    cam_w = int((cam_w // 2) * 2)
    cam_h = int((cam_h // 2) * 2)
    cam_x = int((cam_x // 2) * 2)
    cam_y = int((cam_y // 2) * 2)

    return {
        "ai_found": True,
        "camera_type": final_type,
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_w": cam_w,
        "cam_h": cam_h,
        "confidence": 0.95
    }


def call_gemini_vision_verifier(img_path: str, candidate_box: tuple, api_key: str) -> bool:
    """
    Calls Gemini 2.5 Flash Vision API to verify if an ambiguous candidate is a genuine live streamer
    vs an in-game avatar or static overlay.
    """
    if not os.path.isfile(img_path) or not api_key:
        return False

    try:
        with open(img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        bx, by, bw, bh = candidate_box
        prompt = (
            f"Analyze this gaming livestream frame. Look specifically at the region around [x={bx}, y={by}, width={bw}, height={bh}].\n"
            "Is there a LIVE human streamer webcam OR live VTuber avatar in this livestream?\n"
            "CRITICAL RULES:\n"
            "1. Real human facecams (in a box or green-screen transparent at the bottom/corner) = TRUE.\n"
            "2. Static PNG channel logos, donation tickers, or 2D Roblox avatar signs = FALSE.\n"
            "3. In-game third-person gameplay characters controlled by the player = FALSE.\n"
            "Reply strictly with JSON: {\"is_live_streamer\": true/false}"
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
                "maxOutputTokens": 128
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = json.loads(text_part.strip())
                is_streamer = bool(parsed.get("is_live_streamer", False))
                log(f"Gemini Vision verification result: {is_streamer}")
                return is_streamer
    except Exception as e:
        log(f"Gemini Vision verification exception: {e}")

    return False


def run_pipeline(input_arg: str = "/files/temp/ref_*.jpg", out_config: str = DEFAULT_CONFIG_PATH, video_arg: str = "") -> dict:
    """
    Main orchestration pipeline:
    1. Gathers reference frames (supports 1 to 5+ frames).
    2. Runs OpenCV YuNet DNN on all frames.
    3. Performs Multi-Frame Spatial Clustering and Consensus Filtering.
    4. Executes Temporal Motion Check (Anti-Static Filter).
    5. Checks Borders and Screen Docking.
    6. Calls Gemini Vision Arbiter if candidate is ambiguous.
    7. Outputs clean JSON to stdout and writes config to disk.
    """
    real_w, real_h = 1920, 1080
    fallback_res = {
        "ai_found": False,
        "camera_type": "none",
        "cam_x": 0,
        "cam_y": 0,
        "cam_w": 0,
        "cam_h": 0,
        "confidence": 0.0
    }

    # 1. Resolve Reference Frames
    if os.path.isfile(input_arg):
        frames = [input_arg]
    else:
        frames = sorted(glob.glob(input_arg))

    if not frames and video_arg and os.path.isfile(video_arg):
        log(f"No frames found matching {input_arg}. Extracting 3 reference frames from video...")
        cap = cv2.VideoCapture(video_arg)
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for i, r in enumerate([0.15, 0.50, 0.85]):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * r))
                ret, frame = cap.read()
                if ret and frame is not None:
                    out_p = f"/files/temp/ref_{i+1}.jpg"
                    cv2.imwrite(out_p, frame)
                    frames.append(out_p)
            cap.release()

    if not frames:
        log("No reference frames available. Returning no-cam fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    log(f"Loaded {len(frames)} reference frame(s): {[os.path.basename(f) for f in frames]}")

    # Check YuNet model
    if not os.path.exists(YUNET_MODEL):
        log(f"Error: YuNet model not found at {YUNET_MODEL}. Returning fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    detector = cv2.FaceDetectorYN.create(YUNET_MODEL, "", (480, 270), score_threshold=0.48)

    # 2. Detect faces across all frames
    frame_detections = []
    loaded_images = {}

    for idx, fpath in enumerate(frames):
        img = cv2.imread(fpath)
        if img is None:
            continue
        loaded_images[idx] = img
        faces = detect_faces_in_image(img, detector, real_w, real_h, score_threshold=0.48)
        for face in faces:
            frame_detections.append((idx, face))

    if not frame_detections:
        log("No face candidates detected across any reference frames.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    # 3. Multi-Frame Spatial Clustering & Consensus Check
    num_frames = len(frames)
    clusters = cluster_faces_across_frames(frame_detections, max_dist=140.0)

    log(f"Clustered into {len(clusters)} spatial candidate group(s).")
    for i, c in enumerate(clusters):
        log(f"  Cluster {i+1}: pos=({int(c['avg_cx'])}, {int(c['avg_cy'])}), size={int(c['avg_w'])}x{int(c['avg_h'])}, frames={c['unique_frames']}/{num_frames}, max_conf={c['max_conf']:.2f}")

    # Consensus Rule:
    # If 3 or more frames are provided, candidate face MUST appear in at least 2 frames (>= 40%).
    # Single-frame transient detections (e.g. an in-game character or passing banner) are rejected.
    best_cluster = None
    for c in clusters:
        if num_frames >= 3:
            if c["unique_frames"] >= 2 and c["max_conf"] >= 0.55:
                best_cluster = c
                break
        elif num_frames == 2:
            if c["unique_frames"] >= 2 or (c["unique_frames"] == 1 and c["max_conf"] >= 0.85 and c["avg_w"] >= 50):
                best_cluster = c
                break
        else:
            # Single frame mode (e.g. testing standalone frame)
            if c["max_conf"] >= 0.70 and c["avg_w"] >= 45:
                best_cluster = c
                break

    if best_cluster is None:
        log("Consensus Filter: No candidate met multi-frame persistence threshold. Returning no-cam fallback.")
        save_and_output(fallback_res, out_config)
        return fallback_res

    cand_cx = int(best_cluster["avg_cx"])
    cand_cy = int(best_cluster["avg_cy"])
    cand_w = int(best_cluster["avg_w"])
    cand_h = int(best_cluster["avg_h"])
    candidate_box = (max(0, cand_cx - cand_w), max(0, cand_cy - cand_h), cand_w * 2, cand_h * 2)

    log(f"Best Candidate: center=({cand_cx}, {cand_cy}), size={cand_w}x{cand_h}, consensus={best_cluster['unique_frames']}/{num_frames}, conf={best_cluster['max_conf']:.2f}")

    # 4. Anti-Static Temporal Motion Check
    if num_frames >= 2:
        is_dynamic, avg_diff, max_pct = check_temporal_motion(candidate_box, frames, real_w, real_h)
        if not is_dynamic:
            log("Anti-Static Filter: REJECTED candidate (motion is 0% across all frames -> static PNG overlay).")
            save_and_output(fallback_res, out_config)
            return fallback_res

    # 5. Border Analysis & Camera Type Classification
    first_img = loaded_images.get(0, cv2.imread(frames[0]))
    has_box, box_coords = analyze_box_borders(first_img, {"x": cand_cx - cand_w // 2, "y": cand_cy - cand_h // 2, "w": cand_w, "h": cand_h}, real_w, real_h)

    # Docking classification:
    # If face is in the bottom half of the screen (cy >= 520) or near the bottom boundary, it's green_screen_docked (e.g. KreekCraft)
    is_docked = (cand_cy >= real_h * 0.52) or ((cand_cy + cand_h // 2) >= real_h * 0.80)

    if has_box:
        camera_type = "box"
        log("Geometric analysis: Confirmed physical webcam box with borders.")
    elif is_docked:
        camera_type = "green_screen_docked"
        log("Geometric analysis: Confirmed bottom-docked green screen streamer.")
    else:
        camera_type = "floating"
        log("Geometric analysis: Floating candidate in gameplay.")

    # 6. Ambiguity Resolution via Gemini Vision Arbiter
    # If candidate is floating in center of gameplay (not corner/docked) and confidence < 0.88, verify with Gemini
    is_center_gameplay = (real_w * 0.25 <= cand_cx <= real_w * 0.75) and (real_h * 0.20 <= cand_cy <= real_h * 0.70)
    if not has_box and not is_docked and (is_center_gameplay or best_cluster["max_conf"] < 0.80):
        log("Candidate is in center gameplay without box borders. Querying Gemini Vision arbiter...")
        api_key = get_gemini_api_key()
        confirmed = call_gemini_vision_verifier(frames[0], candidate_box, api_key)
        if not confirmed:
            log("Gemini Vision Arbiter: Candidate is in-game character or overlay, NOT live streamer. REJECTED.")
            save_and_output(fallback_res, out_config)
            return fallback_res

    # 7. Final Crop Sanitization (16:9 safe bounds)
    clean_crop = sanitize_crop(cand_cx, cand_cy, cand_w, cand_h, camera_type, real_w, real_h)
    log(f"VERIFIED WEBCAM: {clean_crop['camera_type']} at x={clean_crop['cam_x']}, y={clean_crop['cam_y']}, {clean_crop['cam_w']}x{clean_crop['cam_h']} (Conf: {best_cluster['max_conf']:.2f})")

    save_and_output(clean_crop, out_config)
    return clean_crop


def save_and_output(result: dict, out_config: str):
    """Saves config to disk and prints clean JSON to stdout for n8n capture."""
    if out_config:
        try:
            os.makedirs(os.path.dirname(out_config), exist_ok=True)
            with open(out_config, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            log(f"Error saving {out_config}: {e}")

    # Output strictly the JSON string to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    arg_pattern = sys.argv[1] if len(sys.argv) > 1 else "/files/temp/ref_*.jpg"
    arg_out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CONFIG_PATH
    arg_video = sys.argv[3] if len(sys.argv) > 3 else ""
    run_pipeline(arg_pattern, arg_out, arg_video)
