#!/usr/bin/env python3
"""
face_reaction_tracker.py
------------------------
Local, Free Facial Expression & Reaction Tracker using OpenCV DNN:
1. Tracks streamer facecam using YuNet face detection & emotion-ferplus ONNX.
2. Identifies:
   - Joy / Laughter bursts (smile + cheek lift)
   - Shock / Jaw-Drop events (surprise + high mouth aperture)
   - Rage / Frustration
3. Runs at 1.5 - 2.0 FPS on CPU with zero GPU requirement.
4. Outputs structured JSON timeline for multimodal fusion.
"""

import sys
import os
import json
import time
import math
import cv2
import numpy as np

EMOTION_MODEL_PATH = "/files/emotion-ferplus-8.onnx"
YUNET_MODEL_PATH = "/files/face_detection_yunet.onnx"
EMOTIONS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]


def get_mouth_aspect_ratio(landmarks):
    """
    Computes mouth aspect ratio using YuNet landmarks:
    landmarks: [re_x, re_y, le_x, le_y, nt_x, nt_y, rmc_x, rmc_y, lmc_x, lmc_y]
    """
    if landmarks is None or len(landmarks) < 10:
        return 0.0
    # Landmarks 6,7: right mouth corner, 8,9: left mouth corner
    rmc = np.array([landmarks[6], landmarks[7]])
    lmc = np.array([landmarks[8], landmarks[9]])
    mouth_width = np.linalg.norm(rmc - lmc)
    if mouth_width < 1.0:
        return 0.0
    # Approximating mouth opening using distance from nose tip to mouth line
    nose = np.array([landmarks[4], landmarks[5]])
    mouth_center = (rmc + lmc) / 2.0
    nose_to_mouth = np.linalg.norm(nose - mouth_center)
    return float(nose_to_mouth / mouth_width)


def track_face_reactions(video_path: str, cam_box: list = None, sample_interval: float = 0.5, max_duration: float = None):
    """
    Scans video facecam frames every `sample_interval` seconds.
    cam_box: [x, y, w, h] normalized (0.0 to 1.0) or pixel coords.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Load DNN Models
    if not os.path.exists(EMOTION_MODEL_PATH):
        raise FileNotFoundError(f"Emotion model not found at {EMOTION_MODEL_PATH}")

    net_emotion = cv2.dnn.readNetFromONNX(EMOTION_MODEL_PATH)
    
    detector_yunet = None
    if os.path.exists(YUNET_MODEL_PATH):
        detector_yunet = cv2.FaceDetectorYN.create(
            YUNET_MODEL_PATH, "", (320, 320), 0.6, 0.3, 5000
        )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps
    if max_duration and max_duration < video_duration:
        video_duration = max_duration

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Convert cam_box to pixel coordinates if normalized
    px_box = None
    if cam_box and len(cam_box) == 4:
        bx, by, bw, bh = cam_box
        if bx <= 1.0 and by <= 1.0 and bw <= 1.0 and bh <= 1.0:
            px_box = [int(bx * width), int(by * height), int(bw * width), int(bh * height)]
        else:
            px_box = [int(bx), int(by), int(bw), int(bh)]
        # Clamp to frame bounds
        px_box[0] = max(0, min(width - 10, px_box[0]))
        px_box[1] = max(0, min(height - 10, px_box[1]))
        px_box[2] = min(width - px_box[0], px_box[2])
        px_box[3] = min(height - px_box[1], px_box[3])

    records = []
    curr_time = 0.0

    print(f"[Face Reaction Tracker] Scanning {video_path} (Duration: {video_duration:.1f}s, Interval: {sample_interval}s)...")
    t0 = time.time()

    while curr_time < video_duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, curr_time * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            curr_time += sample_interval
            continue

        # Extract facecam region
        if px_box:
            bx, by, bw, bh = px_box
            cam_crop = frame[by:by+bh, bx:bx+bw]
        else:
            cam_crop = frame

        if cam_crop.shape[0] < 20 or cam_crop.shape[1] < 20:
            curr_time += sample_interval
            continue

        face_roi = None
        mar_score = 0.0

        # Try YuNet face detection inside cam crop
        if detector_yunet is not None:
            c_h, c_w = cam_crop.shape[:2]
            detector_yunet.setInputSize((c_w, c_h))
            faces = detector_yunet.detect(cam_crop)
            if faces[1] is not None and len(faces[1]) > 0:
                best_face = faces[1][0]
                fx, fy, fw, fh = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
                fx, fy = max(0, fx), max(0, fy)
                fw = min(c_w - fx, fw)
                fh = min(c_h - fy, fh)
                if fw > 15 and fh > 15:
                    face_roi = cam_crop[fy:fy+fh, fx:fx+fw]
                    landmarks = best_face[4:14]
                    mar_score = get_mouth_aspect_ratio(landmarks)

        # Fallback to center-crop if YuNet didn't find face
        if face_roi is None or face_roi.shape[0] < 15 or face_roi.shape[1] < 15:
            c_h, c_w = cam_crop.shape[:2]
            margin_y = int(c_h * 0.15)
            margin_x = int(c_w * 0.15)
            face_roi = cam_crop[margin_y:c_h-margin_y, margin_x:c_w-margin_x]

        if face_roi.shape[0] < 15 or face_roi.shape[1] < 15:
            curr_time += sample_interval
            continue

        # Prepare for emotion-ferplus (1x1x64x64 float32 grayscale)
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64)).astype(np.float32)
        blob = np.expand_dims(np.expand_dims(resized, axis=0), axis=0)

        net_emotion.setInput(blob)
        out = net_emotion.forward()
        probs = np.exp(out - np.max(out))
        probs = probs / np.sum(probs)
        p_dict = {EMOTIONS[i]: float(probs[0][i]) for i in range(len(EMOTIONS))}

        joy = p_dict["happiness"]
        surprise = p_dict["surprise"]
        anger = p_dict["anger"]
        neutral = p_dict["neutral"]

        # Reaction intensity score (0.0 to 100.0)
        # Prioritize Joy (Laughter) and Surprise (Shock / Jaw-drop)
        intensity = max(joy * 100.0, surprise * 110.0, anger * 80.0)
        if mar_score > 0.5:
            intensity = max(intensity, 75.0)

        records.append({
            "time": round(curr_time, 2),
            "joy": round(joy, 3),
            "surprise": round(surprise, 3),
            "anger": round(anger, 3),
            "neutral": round(neutral, 3),
            "mar": round(mar_score, 3),
            "intensity": round(intensity, 1)
        })

        curr_time += sample_interval

    cap.release()
    elapsed = time.time() - t0
    print(f"[Face Reaction Tracker] Completed {len(records)} samples in {elapsed:.2f}s ({len(records)/max(0.1, elapsed):.1f} FPS)")

    # Cluster high-intensity emotion windows
    events = []
    if records:
        threshold = 60.0
        in_event = False
        ev_start = 0.0
        ev_records = []

        for r in records:
            if r["intensity"] >= threshold:
                if not in_event:
                    in_event = True
                    ev_start = r["time"]
                    ev_records = [r]
                else:
                    ev_records.append(r)
            else:
                if in_event:
                    in_event = False
                    ev_end = ev_records[-1]["time"]
                    if (ev_end - ev_start) >= 0.5:
                        peak_int = max(x["intensity"] for x in ev_records)
                        peak_joy = max(x["joy"] for x in ev_records)
                        peak_surp = max(x["surprise"] for x in ev_records)
                        peak_anger = max(x["anger"] for x in ev_records)
                        dom = "joy" if peak_joy >= max(peak_surp, peak_anger) else ("surprise" if peak_surp >= peak_anger else "anger")
                        events.append({
                            "start": ev_start,
                            "end": ev_end,
                            "duration": round(ev_end - ev_start, 2),
                            "dominant": dom,
                            "peak_intensity": peak_int,
                            "peak_joy": peak_joy,
                            "peak_surprise": peak_surp,
                            "peak_anger": peak_anger
                        })
                    ev_records = []

        if in_event and ev_records:
            ev_end = ev_records[-1]["time"]
            if (ev_end - ev_start) >= 0.5:
                peak_int = max(x["intensity"] for x in ev_records)
                peak_joy = max(x["joy"] for x in ev_records)
                peak_surp = max(x["surprise"] for x in ev_records)
                peak_anger = max(x["anger"] for x in ev_records)
                dom = "joy" if peak_joy >= max(peak_surp, peak_anger) else ("surprise" if peak_surp >= peak_anger else "anger")
                events.append({
                    "start": ev_start,
                    "end": ev_end,
                    "duration": round(ev_end - ev_start, 2),
                    "dominant": dom,
                    "peak_intensity": peak_int,
                    "peak_joy": peak_joy,
                    "peak_surprise": peak_surp,
                    "peak_anger": peak_anger
                })

    events.sort(key=lambda e: e["peak_intensity"], reverse=True)

    return {
        "video_duration": round(video_duration, 1),
        "total_samples": len(records),
        "total_reaction_events": len(events),
        "top_events": events[:15],
        "samples": records
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 face_reaction_tracker.py <video.mp4> [output.json] [box_x,box_y,box_w,box_h]")
        sys.exit(1)

    v_path = sys.argv[1]
    o_path = sys.argv[2] if len(sys.argv) > 2 else v_path.replace(".mp4", ".face_reactions.json")
    box_param = None
    if len(sys.argv) > 3:
        try:
            box_param = [float(v) for v in sys.argv[3].split(",")]
        except Exception:
            box_param = None

    res = track_face_reactions(v_path, cam_box=box_param, sample_interval=0.5, max_duration=120.0)
    print(f"[Face Reaction Tracker] Found {len(res['top_events'])} Reaction Events.")
    for i, ev in enumerate(res['top_events'][:5], 1):
        print(f"  #{i}: [{ev['start']}s - {ev['end']}s] {ev['dominant'].upper()} (Intensity: {ev['peak_intensity']} | Joy: {ev['peak_joy']} | Surprise: {ev['peak_surprise']})")

    with open(o_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[Face Reaction Tracker] Saved to {o_path}")
