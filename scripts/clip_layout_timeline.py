#!/usr/bin/env python3
"""
clip_layout_timeline.py
-----------------------
Samples a rendered/concatenated clip at 2 fps (480x270) using OpenCV YuNet
(+ Haar / skin-contour fallback) to build /files/temp/layout_timeline.json.

Classifies each timestamp into:
  - FULLSCREEN_CAM  (centered large face, cam > 45% frame, or >25% overlap with gameplay crop)
  - SPLIT_PIP       (PiP webcam <= 35% frame area alongside gameplay)
  - FULLSCREEN_GAME (no streamer face detected)

Applies <1.5s flicker hysteresis and IoU >= 0.70 segment merging.
"""

import argparse
import json
import os
import sys
import cv2
import numpy as np

YUNET_PATHS = [
    "/files/face_detection_yunet.onnx",
    "/app/face_detection_yunet.onnx",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detection_yunet.onnx"),
]

SAMPLE_W = 480
SAMPLE_H = 270
SAMPLE_FPS = 2.0


def _load_yunet():
    for yp in YUNET_PATHS:
        if os.path.exists(yp):
            try:
                return cv2.FaceDetectorYN.create(yp, "", (SAMPLE_W, SAMPLE_H), 0.55, 0.3, 5000)
            except Exception:
                pass
    return None


def _load_haar():
    try:
        hp = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if os.path.exists(hp):
            c = cv2.CascadeClassifier(hp)
            if not c.empty():
                return c
    except Exception:
        pass
    return None


def _bbox_iou(a: list, b: list) -> float:
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return float(inter / union) if union > 0.0 else 0.0


def _overlap_fraction(inner: list, outer: list) -> float:
    """Fraction of `inner` box area that lies inside `outer` box."""
    if not inner or not outer:
        return 0.0
    ix1, iy1, iw, ih = inner
    ox1, oy1, ow, oh = outer
    ix2, iy2 = ix1 + iw, iy1 + ih
    ox2, oy2 = ox1 + ow, oy1 + oh
    x1, y1 = max(ix1, ox1), max(iy1, oy1)
    x2, y2 = min(ix2, ox2), min(iy2, oy2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = max(1e-6, iw * ih)
    return float(inter / area)


def _detect_largest_face(small_bgr, yunet, haar):
    """Return normalized [nx, ny, nw, nh, score] of largest detected face, or None."""
    faces = []
    if yunet is not None:
        try:
            yunet.setInputSize((SAMPLE_W, SAMPLE_H))
            _, raw = yunet.detect(small_bgr)
            if raw is not None:
                for row in raw:
                    x, y, w, h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                    sc = float(row[-1])
                    if w >= 12 and h >= 12 and sc >= 0.55:
                        faces.append((w * h, x / SAMPLE_W, y / SAMPLE_H, w / SAMPLE_W, h / SAMPLE_H, sc))
        except Exception:
            pass

    if not faces and haar is not None:
        try:
            gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)
            rects = haar.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(20, 20))
            for (x, y, w, h) in rects:
                faces.append((float(w * h), x / SAMPLE_W, y / SAMPLE_H, w / SAMPLE_W, h / SAMPLE_H, 0.75))
        except Exception:
            pass

    if not faces:
        # Lightweight YCrCb skin-region fallback for large centered faces
        try:
            ycrcb = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2YCrCb)
            mask = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 173, 127], dtype=np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if area < (SAMPLE_W * SAMPLE_H * 0.045):
                    continue
                x, y, w, h = cv2.boundingRect(c)
                aspect = w / max(1.0, float(h))
                if 0.55 <= aspect <= 1.65:
                    faces.append((float(w * h), x / SAMPLE_W, y / SAMPLE_H, w / SAMPLE_W, h / SAMPLE_H, 0.50))
        except Exception:
            pass

    if not faces:
        return None
    faces.sort(key=lambda t: t[0], reverse=True)
    _, nx, ny, nw, nh, sc = faces[0]
    return [nx, ny, nw, nh, sc]


def _estimate_pip_box_from_face(face_norm: list, orig_w: int, orig_h: int, small_bgr) -> list:
    """Estimate stabilized PiP webcam [x, y, w, h] in original pixel coordinates centered on head/shoulders."""
    nx, ny, nw, nh, _ = face_norm
    cx = nx + nw * 0.5
    cy = ny + nh * 0.5

    # Standard PiP webcam aspect ratio (~720:420 = 1.714) sized comfortably around head + shoulders
    box_h_norm = max(0.22, min(0.36, nh * 2.5))
    box_w_norm = max(0.18, min(0.34, box_h_norm * (720.0 / 420.0) * (orig_h / max(1, orig_w))))

    # Snap cleanly to corners if face is near edges, otherwise center around face
    bx_norm = cx - box_w_norm * 0.5
    by_norm = cy - box_h_norm * 0.38
    if cx < 0.22:
        bx_norm = max(0.0, min(bx_norm, 0.02))
    elif cx > 0.78:
        bx_norm = min(1.0 - box_w_norm, max(bx_norm, 0.98 - box_w_norm))
    if cy < 0.22:
        by_norm = max(0.0, min(by_norm, 0.02))
    elif cy > 0.78:
        by_norm = min(1.0 - box_h_norm, max(by_norm, 0.98 - box_h_norm))

    bx = int(max(0, min(orig_w - 40, round(bx_norm * orig_w))))
    by = int(max(0, min(orig_h - 40, round(by_norm * orig_h))))
    bw = int(max(40, min(orig_w - bx, round(box_w_norm * orig_w))))
    bh = int(max(40, min(orig_h - by, round(box_h_norm * orig_h))))
    # Enforce even dims for FFmpeg
    bw -= bw % 2
    bh -= bh % 2
    return [bx, by, max(40, bw), max(40, bh)]


def _classify_frame(small_bgr, yunet, haar, orig_w: int, orig_h: int, cam_hint: list | None = None) -> dict:
    face = _detect_largest_face(small_bgr, yunet, haar)
    if face is None:
        return {"mode": "FULLSCREEN_GAME", "cam_box": None, "face_cx": 0.5}

    nx, ny, nw, nh, _ = face
    fcx = nx + nw * 0.5
    fcy = ny + nh * 0.5

    # Gameplay crop region in normalized coords (matching Create Subtitle Binary 9:16 center crop)
    game_h_norm = 0.92
    game_w_norm = game_h_norm * (720.0 / 860.0) * (orig_h / max(1, orig_w))
    game_x_norm = max(0.0, (1.0 - game_w_norm) * 0.5)
    game_y_norm = min(0.10, max(0.0, 1.0 - game_h_norm))
    game_crop_norm = [game_x_norm, game_y_norm, game_w_norm, game_h_norm]

    is_large_centered = (nh >= 0.22 or nw >= 0.14) and (0.25 <= fcx <= 0.75)
    pip_box = _estimate_pip_box_from_face(face, orig_w, orig_h, small_bgr)
    if cam_hint and len(cam_hint) == 4 and cam_hint[2] > 0 and cam_hint[3] > 0:
        # Use VOD cam_hint if the detected face falls inside it (zero jitter)
        hx, hy, hw, hh = [
            cam_hint[0] / orig_w, cam_hint[1] / orig_h,
            cam_hint[2] / orig_w, cam_hint[3] / orig_h,
        ]
        if hx - 0.04 <= fcx <= hx + hw + 0.04 and hy - 0.04 <= fcy <= hy + hh + 0.04:
            pip_box = [int(cam_hint[0]), int(cam_hint[1]), int(cam_hint[2]), int(cam_hint[3])]

    cam_area_frac = (pip_box[2] * pip_box[3]) / float(max(1, orig_w * orig_h))
    dup_overlap = _overlap_fraction([nx, ny, nw, nh], game_crop_norm)

    if is_large_centered or cam_area_frac > 0.45 or dup_overlap > 0.25:
        return {"mode": "FULLSCREEN_CAM", "cam_box": None, "face_cx": round(fcx, 4)}

    return {"mode": "SPLIT_PIP", "cam_box": pip_box, "face_cx": round(fcx, 4)}


def smooth_and_merge_samples(samples: list, clip_duration: float, sample_dt: float = 0.5) -> list:
    """Apply <1.5s flicker hysteresis and merge SPLIT_PIP segments with IoU >= 0.70."""
    if not samples:
        return [{
            "start": 0.0,
            "end": round(clip_duration, 3),
            "mode": "FULLSCREEN_GAME",
            "cam_box": None,
            "face_cx": 0.5,
            "caption_y": 175,
        }]

    # 1. Temporal hysteresis: replace runs shorter than 3 samples (< 1.5s) with neighbor state
    modes = [s["mode"] for s in samples]
    n = len(modes)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < n:
            j = i
            while j < n and modes[j] == modes[i]:
                j += 1
            run_len = j - i
            if run_len < 3 and n > run_len:
                rep_idx = i - 1 if i > 0 else j
                rep_mode = modes[rep_idx]
                for k in range(i, j):
                    modes[k] = rep_mode
                    samples[k]["mode"] = rep_mode
                    if rep_mode != "SPLIT_PIP":
                        samples[k]["cam_box"] = None
                    elif samples[k]["cam_box"] is None and samples[rep_idx]["cam_box"] is not None:
                        samples[k]["cam_box"] = list(samples[rep_idx]["cam_box"])
                changed = True
                break
            i = j

    # 2. Merge contiguous samples with same mode and IoU >= 0.70 (for SPLIT_PIP)
    segments = []
    cur_group = [samples[0]]
    for s in samples[1:]:
        prev = cur_group[-1]
        same_mode = (s["mode"] == prev["mode"])
        if same_mode and s["mode"] == "SPLIT_PIP":
            iou = _bbox_iou(prev.get("cam_box"), s.get("cam_box"))
            if iou < 0.70:
                same_mode = False
        if same_mode:
            cur_group.append(s)
        else:
            segments.append(cur_group)
            cur_group = [s]
    segments.append(cur_group)

    out = []
    for idx, grp in enumerate(segments):
        st = round(grp[0]["t"], 3) if idx > 0 else 0.0
        en = round(segments[idx + 1][0]["t"], 3) if idx < len(segments) - 1 else round(clip_duration, 3)
        if en <= st:
            continue
        mode = grp[0]["mode"]
        avg_fcx = round(sum(float(g.get("face_cx", 0.5)) for g in grp) / len(grp), 4)
        avg_box = None
        if mode == "SPLIT_PIP":
            boxes = [g["cam_box"] for g in grp if g.get("cam_box")]
            if boxes:
                avg_box = [
                    int(round(sum(b[0] for b in boxes) / len(boxes))),
                    int(round(sum(b[1] for b in boxes) / len(boxes))),
                    int(round(sum(b[2] for b in boxes) / len(boxes))),
                    int(round(sum(b[3] for b in boxes) / len(boxes))),
                ]
                avg_box[2] -= avg_box[2] % 2
                avg_box[3] -= avg_box[3] % 2
        out.append({
            "start": st,
            "end": en,
            "mode": mode,
            "cam_box": avg_box,
            "face_cx": avg_fcx,
            "caption_y": 420 if mode == "SPLIT_PIP" else 175,
        })
    return out


def analyze_video_layout(video_path: str, cam_hint: list | None = None) -> dict:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    clip_duration = max(0.5, total_frames / fps)
    cap.release()

    yunet = _load_yunet()
    haar = _load_haar() if yunet is None else None

    samples = []
    dt = 1.0 / SAMPLE_FPS
    frame_bytes = SAMPLE_W * SAMPLE_H * 3

    # Fast sequential FFmpeg pipe (avoids slow H.264 CAP_PROP_POS_FRAMES random seeks -> <1s runtime)
    try:
        import subprocess
        proc = subprocess.Popen(
            [
                "ffmpeg", "-loglevel", "error", "-i", video_path,
                "-vf", f"fps={SAMPLE_FPS},scale={SAMPLE_W}:{SAMPLE_H}:flags=fast_bilinear",
                "-f", "rawvideo", "-pix_fmt", "bgr24", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        idx = 0
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            small = np.frombuffer(raw, dtype=np.uint8).reshape((SAMPLE_H, SAMPLE_W, 3))
            info = _classify_frame(small, yunet, haar, orig_w, orig_h, cam_hint=cam_hint)
            info["t"] = round(idx * dt, 3)
            samples.append(info)
            idx += 1
        proc.wait(timeout=5)
    except Exception:
        samples = []

    # Fallback to OpenCV sequential grab if FFmpeg pipe unavailable
    if not samples:
        cap = cv2.VideoCapture(video_path)
        t = 0.0
        while t < clip_duration - 0.05:
            frame_idx = min(total_frames - 1, max(0, int(round(t * fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if ok and frame is not None:
                small = cv2.resize(frame, (SAMPLE_W, SAMPLE_H), interpolation=cv2.INTER_AREA)
                info = _classify_frame(small, yunet, haar, orig_w, orig_h, cam_hint=cam_hint)
                info["t"] = round(t, 3)
                samples.append(info)
            t += dt
        cap.release()

    segments = smooth_and_merge_samples(samples, clip_duration, sample_dt=dt)
    return {
        "clip_duration": round(clip_duration, 3),
        "width": orig_w,
        "height": orig_h,
        "segments": segments,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze per-timestamp webcam layout timeline.")
    parser.add_argument("video", nargs="?", default="/files/temp/concatenated_clip.mp4")
    parser.add_argument("output", nargs="?", default="/files/temp/layout_timeline.json")
    parser.add_argument("--cam-config", default="/files/temp/cam_config.json")
    args = parser.parse_args()

    cam_hint = None
    if args.cam_config and os.path.exists(args.cam_config):
        try:
            cfg = json.load(open(args.cam_config, encoding="utf-8"))
            if cfg.get("ai_found") and int(cfg.get("cam_w") or 0) > 0:
                cam_hint = [int(cfg.get("cam_x") or 0), int(cfg.get("cam_y") or 0), int(cfg["cam_w"]), int(cfg["cam_h"])]
        except Exception:
            pass

    result = analyze_video_layout(args.video, cam_hint=cam_hint)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({"ok": True, "segments": len(result["segments"]), "output": args.output}))


if __name__ == "__main__":
    main()
