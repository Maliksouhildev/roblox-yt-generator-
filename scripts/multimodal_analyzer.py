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
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import cv2
import numpy as np

# Ensure local sibling imports resolve regardless of current working directory
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

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
def analyze_audio_spikes(audio_path: str, spike_offset: float = 8.0, return_meta: bool = False):
    if not audio_path or not os.path.exists(audio_path):
        return ([], 0.0) if return_meta else []

    sr = 8000
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", audio_path,
        "-af", "highpass=f=200,lowpass=f=3500",
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pcm = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        audio_dur = round(len(pcm) / float(sr), 2) if len(pcm) else 0.0
        win = sr // 2  # 0.5s RMS bins
        n_bins = len(pcm) // win
        if n_bins <= 0:
            return ([], audio_dur) if return_meta else []

        blocks = pcm[:n_bins * win].reshape(n_bins, win)
        rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
        db = 20.0 * np.log10(rms)
        valid = db[db > -90.0]
        if len(valid) == 0:
            return ([], audio_dur) if return_meta else []

        median_rms = float(np.median(valid))
        spike_thresh = median_rms + spike_offset
        spikes = [(round(i * 0.5, 2), round(float(db[i]), 1)) for i in range(n_bins) if db[i] >= spike_thresh]

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

        return (windows, audio_dur) if return_meta else windows
    except Exception as e:
        print(f"[Multimodal Warning] Error running audio spike detection: {e}", file=sys.stderr)
        return ([], 0.0) if return_meta else []


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


def analyze_face_reactions(video_path: str, cam_config_path: str, sample_interval: float = 1.5, max_duration: float = None, max_wall_sec: float = 240.0):
    if not video_path or not os.path.exists(video_path):
        return None
    if not os.path.exists(EMOTION_MODEL_PATH):
        return None

    cam_box = None
    if cam_config_path and os.path.exists(cam_config_path):
        try:
            with open(cam_config_path, "r", encoding="utf-8") as f:
                c = json.load(f)
                if c.get("ai_found") is False or c.get("camera_type") == "none":
                    print("[Face Scan] No active webcam in cam_config.json; skipping full-VOD face scan.", file=sys.stderr)
                    return None
                if "cam_x" in c and "cam_w" in c:
                    cam_box = [c["cam_x"], c["cam_y"], c["cam_w"], c["cam_h"]]
        except Exception:
            pass

    if not cam_box:
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    video_duration = total_frames / fps if total_frames > 0 else 0.0
    if max_duration and (video_duration <= 0 or max_duration < video_duration):
        video_duration = max_duration
    if width < 32 or height < 32:
        return None

    bx, by, bw, bh = cam_box
    if bx <= 1.0 and by <= 1.0 and bw <= 1.0 and bh <= 1.0:
        px_box = [int(bx * width), int(by * height), int(bw * width), int(bh * height)]
    else:
        px_box = [int(bx), int(by), int(bw), int(bh)]
    px_box[0] = max(0, min(width - 20, px_box[0]))
    px_box[1] = max(0, min(height - 20, px_box[1]))
    px_box[2] = min(width - px_box[0], px_box[2])
    px_box[3] = min(height - px_box[1], px_box[3])
    cbx, cby, cbw, cbh = px_box
    if cbw < 20 or cbh < 20:
        return None

    out_w = min(320, max(96, (cbw // 2) * 2))
    out_h = max(64, int(round(cbh * (out_w / float(cbw))) // 2 * 2))

    net_emotion = cv2.dnn.readNetFromONNX(EMOTION_MODEL_PATH)
    detector_yunet = None
    if os.path.exists(YUNET_MODEL_PATH):
        detector_yunet = cv2.FaceDetectorYN.create(YUNET_MODEL_PATH, "", (out_w, out_h), 0.6, 0.3, 5000)

    # Sequential keyframe-only FFmpeg decode (avoids OpenCV random GOP-redecode stalls on multi-hour VODs)
    vf_chain = f"crop={cbw}:{cbh}:{cbx}:{cby},scale={out_w}:{out_h},showinfo"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-skip_loop_filter", "all", "-skip_frame", "nokey",
        "-i", video_path,
    ]
    if max_duration:
        cmd.extend(["-t", str(max_duration)])
    cmd.extend([
        "-an", "-sn",
        "-vf", vf_chain,
        "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"
    ])

    frame_bytes = out_w * out_h * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_bytes * 4)
    pts_list = []

    def _drain_pts():
        for raw_line in iter(proc.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="ignore")
            if "pts_time:" in line:
                m = re.search(r"pts_time:([\d\.]+)", line)
                if m:
                    pts_list.append(float(m.group(1)))

    t_err = threading.Thread(target=_drain_pts, daemon=True)
    t_err.start()

    records = []
    frame_idx = 0
    last_eval_t = -999.0
    t_start = time.time()

    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            curr_time = pts_list[frame_idx] if frame_idx < len(pts_list) else (frame_idx * 4.0)
            frame_idx += 1

            if (time.time() - t_start) > max_wall_sec:
                print(f"[Face Scan] Wall budget {max_wall_sec}s reached at {curr_time:.1f}s; stopping cleanly.", file=sys.stderr)
                break
            if (curr_time - last_eval_t) < sample_interval:
                continue
            last_eval_t = curr_time

            cam_crop = np.frombuffer(buf, dtype=np.uint8).reshape((out_h, out_w, 3))
            face_roi = None
            mar_score = 0.0

            if detector_yunet is not None:
                faces = detector_yunet.detect(cam_crop)
                if faces[1] is not None and len(faces[1]) > 0:
                    best_face = faces[1][0]
                    fx, fy, fw, fh = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
                    fx, fy = max(0, fx), max(0, fy)
                    fw = min(out_w - fx, fw)
                    fh = min(out_h - fy, fh)
                    if fw > 12 and fh > 12:
                        face_roi = cam_crop[fy:fy+fh, fx:fx+fw]
                        mar_score = get_mouth_aspect_ratio(best_face[4:14])

            if face_roi is None or face_roi.shape[0] < 12 or face_roi.shape[1] < 12:
                my = int(out_h * 0.15)
                mx = int(out_w * 0.15)
                face_roi = cam_crop[my:out_h-my, mx:out_w-mx]

            if face_roi.shape[0] < 12 or face_roi.shape[1] < 12:
                continue

            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64)).astype(np.float32)
            blob = np.expand_dims(np.expand_dims(resized, axis=0), axis=0)

            net_emotion.setInput(blob)
            out = net_emotion.forward()
            probs = np.exp(out - np.max(out))
            probs = probs / np.sum(probs)

            joy = float(probs[0][1])
            surprise = float(probs[0][2])
            anger = float(probs[0][4])

            intensity = max(joy * 100.0, surprise * 110.0, anger * 80.0)
            if mar_score > 0.48:
                intensity = max(intensity, 75.0)

            records.append({
                "time": round(curr_time, 2),
                "joy": round(joy, 3),
                "surprise": round(surprise, 3),
                "intensity": round(intensity, 1)
            })
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
        proc.wait()
        t_err.join(timeout=2.0)

    print(f"[Face Scan] Decoded {frame_idx} keyframes, scored {len(records)} samples in {time.time()-t_start:.2f}s", file=sys.stderr)
    return {
        "duration": video_duration or (pts_list[-1] if pts_list else 0.0),
        "samples": records
    }


# ── 3. Multimodal Fusion Engine ─────────────────────────────────────────────
def run_fusion(
    video_path: str,
    audio_path: str,
    cam_config_path: str,
    output_path: str,
    top_k: int = 18
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

            # Run Laughter-Triggered Comedic Beat Reasoner on live transcript
            live_whisper = "/files/temp/transcript.json" if os.path.exists("/files/temp/transcript.json") else "/files/temp/whisper.json"
            beats_res = process_comedic_beats(
                video_path=video_path,
                chat_analysis_path=chat_out_temp,
                whisper_path=live_whisper
            )
            for b in beats_res.get("comedic_beats", []):
                comedic_beats_map[b["peak_laugh_time"]] = b
        except Exception as e:
            print(f"[Multimodal Warning] Error analyzing chat: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_audio = pool.submit(analyze_audio_spikes, audio_path, 8.0, True)
        fut_face = pool.submit(analyze_face_reactions, video_path, cam_config_path)
        audio_spikes, audio_dur = fut_audio.result()
        face_res = fut_face.result()

    duration = 300.0
    if face_res and face_res.get("duration"):
        duration = face_res["duration"]
    elif audio_dur and audio_dur > 0:
        duration = audio_dur
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

    # Persist standardized telemetry cache files for <10s Script Sandbox iterations
    try:
        os.makedirs("/files/temp", exist_ok=True)
        ae_peaks = [{"start": round(float(sw[0]), 2), "end": round(float(sw[1]), 2), "mid": round((float(sw[0]) + float(sw[1])) / 2.0, 2), "jump_db": 10.0, "label": "dB_PEAK"} for sw in audio_spikes]
        with open("/files/temp/audio_energy.json", "w", encoding="utf-8") as f:
            json.dump({"peaks": ae_peaks, "count": len(ae_peaks)}, f, indent=2)
        if chat_res is not None:
            with open("/files/temp/chat_laughter_clusters.json", "w", encoding="utf-8") as f:
                json.dump({"clusters": chat_res.get("top_clusters", []), "count": len(chat_res.get("top_clusters", []))}, f, indent=2)
        if face_res is not None:
            f_ev = [{"start": s["time"], "end": s["time"] + 1.5, "dominant": ("joy" if s.get("joy", 0) >= s.get("surprise", 0) else "surprise"), "intensity": s["intensity"]} for s in face_res.get("samples", []) if s.get("intensity", 0) >= 65.0]
            with open("/files/temp/face_emotions.json", "w", encoding="utf-8") as f:
                json.dump({"top_events": f_ev, "samples": face_res.get("samples", [])[:1500]}, f, indent=2)
        from telemetry_fusion_indexer import build_unified_index
        live_tx = "/files/temp/transcript.json" if os.path.exists("/files/temp/transcript.json") else None
        build_unified_index(
            transcript_path=live_tx,
            audio_energy_path="/files/temp/audio_energy.json",
            chat_path="/files/temp/chat_laughter_clusters.json" if chat_res else None,
            face_path="/files/temp/face_emotions.json" if face_res else None,
            output_dir="/files/temp",
            top_k=top_k,
            save_cache=True,
        )
    except Exception as e_idx:
        print(f"[Multimodal Warning] Unified timeline index build failed: {e_idx}", file=sys.stderr)

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
