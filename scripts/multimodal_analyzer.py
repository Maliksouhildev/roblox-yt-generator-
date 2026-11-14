#!/usr/bin/env python3
"""
multimodal_analyzer.py
----------------------
All-in-one Multimodal Virality Analyzer for n8n Pipeline.
Runs locally in Docker container with zero GPU / API cost.

Combines:
1. Universal Live Chat Analyzer (Z-Score >= 2.5 sigma, Laughter Density > 30%, regex elongated tokens)
2. Face Reaction Tracker (OpenCV DNN + emotion-ferplus ONNX + YuNet MAR)
3. Audio Energy & Vocal Spike Scanner (FFmpeg astats bandpass)
4. Laughter-Triggered Comedic Beat Reasoner (Why Chat Laughed + Visual Comedy + Conditional Multi-Beat + Setup Tension Hook)
5. Fusion Ranker & Viral Anchor Extractor (Top 6 High-Retention Moments)

Outputs JSON to stdout and file for n8n execution.
"""

import sys
import os
import json
import re
import math
import subprocess
import time
from collections import Counter
import cv2
import numpy as np

# Import upgraded chat analyzer & humor reasoner
from chat_analyzer import analyze_chat
from chat_humor_reasoner import process_comedic_beats

EMOTION_MODEL_PATH = "/files/emotion-ferplus-8.onnx"
YUNET_MODEL_PATH = "/files/face_detection_yunet.onnx"
EMOTIONS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]


def format_timestamp(seconds: float) -> str:
    s_total = max(0.0, float(seconds))
    m = int(s_total // 60)
    s = int(s_total % 60)
    cs = int(round((s_total - int(s_total)) * 100))
    if cs >= 100: cs = 99
    return f"{m:02d}:{s:02d}.{cs:02d}"


# ── 1. Vocal Energy & Scream Spikes ─────────────────────────────────────────
def analyze_audio_spikes(audio_path: str, spike_offset: float = 8.0):
    if not audio_path or not os.path.exists(audio_path):
        return []

    cmd = [
        "ffmpeg", "-hide_banner", "-i", audio_path,
        "-af", "highpass=f=200,lowpass=f=3500,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
        "-f", "null", "-"
    ]
    try:
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        raw_rms = []
        c_time = 0.0
        for line in p.stderr:
            if "pts_time:" in line:
                m = re.search(r"pts_time:([\d\.]+)", line)
                if m: c_time = float(m.group(1))
            elif "RMS_level=" in line:
                m = re.search(r"RMS_level=([-\d\.]+|[-+]?inf)", line)
                if m:
                    try:
                        v = float(m.group(1))
                        if not math.isinf(v) and not math.isnan(v):
                            raw_rms.append((c_time, v))
                    except ValueError:
                        pass
        p.wait()

        if not raw_rms:
            return []

        vals = [r[1] for r in raw_rms]
        median_rms = float(sorted(vals)[len(vals) // 2])
        spike_thresh = median_rms + spike_offset

        spikes = []
        for t, val in raw_rms:
            if val >= spike_thresh:
                spikes.append((round(t, 2), round(val, 1)))

        windows = []
        if spikes:
            w_start, w_end = spikes[0][0], spikes[0][0] + 1.5
            for t, val in spikes[1:]:
                if t <= w_end + 1.0:
                    w_end = max(w_end, t + 1.5)
                else:
                    windows.append([w_start, w_end])
                    w_start, w_end = t, t + 1.5
            windows.append([w_start, w_end])

        return windows
    except Exception as e:
        print(f"[Multimodal Warning] Error running audio spike detection: {e}", file=sys.stderr)
        return []


# ── 2. Face Reaction Analysis ───────────────────────────────────────────────
def get_mouth_aspect_ratio(landmarks):
    if landmarks is None or len(landmarks) < 10: return 0.0
    rmc = np.array([landmarks[6], landmarks[7]])
    lmc = np.array([landmarks[8], landmarks[9]])
    mouth_width = np.linalg.norm(rmc - lmc)
    if mouth_width < 1.0: return 0.0
    nose = np.array([landmarks[4], landmarks[5]])
    mouth_center = (rmc + lmc) / 2.0
    return float(np.linalg.norm(nose - mouth_center) / mouth_width)


def analyze_face_reactions(video_path: str, cam_config_path: str, sample_interval: float = 1.5, max_duration: float = None):
    if not video_path or not os.path.exists(video_path):
        return None
    if not os.path.exists(EMOTION_MODEL_PATH):
        return None

    cam_box = None
    if cam_config_path and os.path.exists(cam_config_path):
        try:
            with open(cam_config_path, "r", encoding="utf-8") as f:
                c = json.load(f)
                if c.get("camera_type") != "none" and "cam_x" in c:
                    cam_box = [c["cam_x"], c["cam_y"], c["cam_w"], c["cam_h"]]
        except Exception:
            pass

    net_emotion = cv2.dnn.readNetFromONNX(EMOTION_MODEL_PATH)
    detector_yunet = None
    if os.path.exists(YUNET_MODEL_PATH):
        detector_yunet = cv2.FaceDetectorYN.create(YUNET_MODEL_PATH, "", (320, 320), 0.6, 0.3, 5000)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps
    if max_duration and max_duration < video_duration:
        video_duration = max_duration

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    px_box = None
    if cam_box and len(cam_box) == 4:
        bx, by, bw, bh = cam_box
        if bx <= 1.0 and by <= 1.0 and bw <= 1.0 and bh <= 1.0:
            px_box = [int(bx * width), int(by * height), int(bw * width), int(bh * height)]
        else:
            px_box = [int(bx), int(by), int(bw), int(bh)]
        px_box[0] = max(0, min(width - 10, px_box[0]))
        px_box[1] = max(0, min(height - 10, px_box[1]))
        px_box[2] = min(width - px_box[0], px_box[2])
        px_box[3] = min(height - px_box[1], px_box[3])

    records = []
    curr_time = 0.0

    while curr_time < video_duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, curr_time * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            curr_time += sample_interval
            continue

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

        if face_roi is None or face_roi.shape[0] < 15 or face_roi.shape[1] < 15:
            c_h, c_w = cam_crop.shape[:2]
            margin_y = int(c_h * 0.15)
            margin_x = int(c_w * 0.15)
            face_roi = cam_crop[margin_y:c_h-margin_y, margin_x:c_w-margin_x]

        if face_roi.shape[0] < 15 or face_roi.shape[1] < 15:
            curr_time += sample_interval
            continue

        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64)).astype(np.float32)
        blob = np.expand_dims(np.expand_dims(resized, axis=0), axis=0)

        net_emotion.setInput(blob)
        out = net_emotion.forward()
        probs = np.exp(out - np.max(out))
        probs = probs / np.sum(probs)

        joy = float(probs[0][1])      # happiness
        surprise = float(probs[0][2]) # surprise
        anger = float(probs[0][4])    # anger

        intensity = max(joy * 100.0, surprise * 110.0, anger * 80.0)
        if mar_score > 0.48:
            intensity = max(intensity, 75.0)

        records.append({
            "time": round(curr_time, 2),
            "joy": round(joy, 3),
            "surprise": round(surprise, 3),
            "intensity": round(intensity, 1)
        })
        curr_time += sample_interval

    cap.release()
    return {
        "duration": video_duration,
        "samples": records
    }


# ── 3. Multimodal Fusion Engine ─────────────────────────────────────────────
def run_fusion(
    video_path: str,
    audio_path: str,
    cam_config_path: str,
    output_path: str,
    top_k: int = 6
):
    print(f"[Multimodal Pipeline] Starting analysis for: {video_path}", file=sys.stderr)

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    if base_name.endswith(".processing"):
        base_name = base_name[:-11]
    
    chat_file = None
    input_dir = os.path.dirname(video_path)
    candidates = [
        os.path.join(input_dir, f"{base_name}.live_chat.json"),
        os.path.join(input_dir, f"{base_name}.chat.json"),
        os.path.join(input_dir, f"{base_name}!.live_chat.json"),
        os.path.join("/files/inputs", f"{base_name}.live_chat.json"),
        os.path.join("/files/inputs", f"{base_name}.chat.json")
    ]
    for c in candidates:
        if os.path.exists(c):
            chat_file = c
            break

    if not chat_file and os.path.exists(input_dir):
        for f in os.listdir(input_dir):
            if (f.endswith(".live_chat.json") or f.endswith(".chat.json")) and (base_name[:15].lower() in f.lower() or f[:15].lower() in base_name.lower()):
                chat_file = os.path.join(input_dir, f)
                break

    chat_res = None
    comedic_beats_map = {}
    if chat_file:
        try:
            chat_res = analyze_chat(chat_file)
            chat_out_temp = "/files/temp/chat_analysis.json"
            with open(chat_out_temp, "w", encoding="utf-8") as f:
                json.dump(chat_res, f, indent=2)

            # Run Laughter-Triggered Comedic Beat Reasoner
            beats_res = process_comedic_beats(
                video_path=video_path,
                chat_analysis_path=chat_out_temp,
                whisper_path="/files/temp/whisper.json"
            )
            for b in beats_res.get("comedic_beats", []):
                comedic_beats_map[b["peak_laugh_time"]] = b
        except Exception as e:
            print(f"[Multimodal Warning] Error analyzing chat: {e}", file=sys.stderr)

    audio_spikes = analyze_audio_spikes(audio_path)
    face_res = analyze_face_reactions(video_path, cam_config_path)

    duration = 300.0
    if face_res and face_res.get("duration"):
        duration = face_res["duration"]
    elif chat_res and chat_res.get("duration_sec"):
        duration = chat_res["duration_sec"]

    step = 1.0
    num_bins = int(math.ceil(duration / step))
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

    has_chat = chat_res is not None and len(chat_res.get("buckets", [])) > 0
    if has_chat:
        for b in chat_res["buckets"]:
            b_start, b_end = b["start"], b["end"]
            b_score = b.get("chat_score", 0.0)
            emotes = b.get("top_emotes", [])
            for item in timeline:
                if b_start <= item["time"] <= b_end:
                    if b_score > item["chat_score"]:
                        item["chat_score"] = b_score
                        item["chat_info"] = f"Chat Velocity {b.get('velocity', 0)} msgs/10s (Z={b.get('z_laugh', 0)}σ) | Emotes: {', '.join(emotes[:3])}"

    has_face = face_res is not None and len(face_res.get("samples", [])) > 0
    if has_face:
        for s in face_res["samples"]:
            t = s["time"]
            b_idx = min(num_bins - 1, max(0, int(round(t / step))))
            f_score = s.get("intensity", 0.0)
            if f_score > timeline[b_idx]["face_score"]:
                timeline[b_idx]["face_score"] = f_score
                dom = "Joy/Laugh" if s.get("joy", 0) >= s.get("surprise", 0) else "Shock/Surprise"
                timeline[b_idx]["face_info"] = f"{dom} ({round(max(s.get('joy',0), s.get('surprise',0))*100)}%)"

    for sw in audio_spikes:
        s_start, s_end = float(sw[0]), float(sw[1])
        for item in timeline:
            if s_start <= item["time"] <= s_end:
                item["audio_score"] = 100.0

    # Dynamic Weighting
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

    # Find Peaks
    peaks = []
    min_peak = 45.0
    for i, item in enumerate(timeline):
        if item["composite_score"] >= min_peak:
            is_max = True
            for k in range(max(0, i - 2), min(num_bins, i + 3)):
                if timeline[k]["composite_score"] > item["composite_score"]:
                    is_max = False
                    break
            if is_max:
                peaks.append(item)

    peaks.sort(key=lambda p: p["composite_score"], reverse=True)

    anchors = []
    used_intervals = []
    for p in peaks:
        peak_t = p["time"]
        overlap = any(not (peak_t + 15.0 < u_start or peak_t - 15.0 > u_end) for u_start, u_end in used_intervals)
        if overlap:
            continue

        # Check if matched with a Comedic Beat
        matched_beat = None
        for b_time, beat in comedic_beats_map.items():
            if abs(peak_t - b_time) <= 15.0:
                matched_beat = beat
                break

        if matched_beat:
            anchor_start = matched_beat["clip_start"]
            anchor_end = matched_beat["clip_end"]
            dur = matched_beat["clip_duration"]
            why_laughed = matched_beat["why_chat_laughed"]
            mechanism = matched_beat["comedy_mechanism"]
            tension_hook = matched_beat["setup_tension_hook"]
            is_multi_beat = matched_beat["is_multi_beat"]
            beat_2 = matched_beat.get("beat_2")
            rec_structure = matched_beat["recommended_structure"]
        else:
            anchor_start = max(0.0, peak_t - 12.0)
            anchor_end = min(duration, peak_t + 5.0)
            dur = round(anchor_end - anchor_start, 1)
            why_laughed = "Streamer reaction & gameplay activity"
            mechanism = "High-energy gameplay reaction"
            tension_hook = format_timestamp(anchor_start)
            is_multi_beat = False
            beat_2 = None
            rec_structure = f"Single-Beat Moment ({dur}s): In-media-res setup leading into climax at {format_timestamp(peak_t)}"

        c_infos = [it["chat_info"] for it in timeline if anchor_start <= it["time"] <= anchor_end and it["chat_info"]]
        f_infos = [it["face_info"] for it in timeline if anchor_start <= it["time"] <= anchor_end and it["face_info"]]
        has_screams = any(anchor_start <= it["time"] <= anchor_end and it["audio_score"] > 0 for it in timeline)

        anchors.append({
            "anchor_id": len(anchors) + 1,
            "start": round(anchor_start, 2),
            "end": round(anchor_end, 2),
            "peak_time": round(peak_t, 2),
            "duration": round(dur, 2),
            "virality_score": p["composite_score"],
            "chat_signal": c_infos[0] if c_infos else "Normal chat pace",
            "face_signal": f_infos[0] if f_infos else "Active gameplay expression",
            "audio_signal": "Vocal volume spike (+8dB to +12dB scream/laugh)" if has_screams else "Standard vocal dialogue",
            "why_chat_laughed": why_laughed,
            "comedy_mechanism": mechanism,
            "setup_tension_hook": tension_hook,
            "is_multi_beat": is_multi_beat,
            "beat_2": beat_2,
            "recommended_structure": rec_structure
        })
        used_intervals.append((anchor_start, anchor_end))
        if len(anchors) >= top_k:
            break

    result = {
        "status": "success",
        "has_chat": has_chat,
        "has_face": has_face,
        "audio_spikes_count": len(audio_spikes),
        "total_duration": round(duration, 1),
        "anchors_count": len(anchors),
        "anchors": anchors
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    print(json.dumps(result))
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 multimodal_analyzer.py <video.mp4> <audio.mp3> <cam_config.json> [output.json]")
        sys.exit(1)

    v_path = sys.argv[1]
    a_path = sys.argv[2] if len(sys.argv) > 2 else "/files/temp/audio.mp3"
    c_path = sys.argv[3] if len(sys.argv) > 3 else "/files/temp/cam_config.json"
    o_path = sys.argv[4] if len(sys.argv) > 4 else "/files/temp/viral_anchors.json"

    run_fusion(v_path, a_path, c_path, o_path)
