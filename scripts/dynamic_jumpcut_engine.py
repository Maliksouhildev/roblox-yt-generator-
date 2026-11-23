#!/usr/bin/env python3
"""
dynamic_jumpcut_engine.py
-------------------------
Intelligent Audio-Visual Dead-Spot Jump-Cut Engine for GTA 6 Viral Shorts.

Analyzes both:
  1. 20ms vocal-band (300Hz-3400Hz) RMS energy + optional Whisper word intervals
  2. 2 fps video frame-difference motion in gameplay & facecam ROIs

Behavior:
  - Cuts blank pauses > 1.05s ONLY when BOTH speech is absent AND gameplay/webcam motion are low.
  - Protects high-motion gameplay (crashes, gunfights, explosions, ragdolls), active webcam
    laughter/shock reactions, and brief comedic timing beats (<= 0.85s).
  - Keeps 0.12s pre-word breathing room & 0.15s post-word tail on cut boundaries, enforces
    max 1 cut per 2.5s (no choppy <1.20s shards), trims dead intro (> 0.35s) and dead outro
    (> 0.90s), and applies 18ms audio fades at every cut seam for zero clicks and tight A/V sync.
"""

import argparse
import json
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile

import numpy as np


def _probe_media(mp4_path: str) -> tuple[float, int, int, float]:
    """Return (duration_sec, width, height, fps)."""
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
            "-of", "json", mp4_path,
        ],
        text=True,
    )
    doc = json.loads(out)
    stream = (doc.get("streams") or [{}])[0]
    fmt = doc.get("format") or {}
    dur = float(stream.get("duration") or fmt.get("duration") or 0.0)
    w = int(stream.get("width") or 1920)
    h = int(stream.get("height") or 1080)
    rate_str = str(stream.get("r_frame_rate") or "30/1")
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        fps = float(num) / max(1.0, float(den))
    else:
        fps = float(rate_str or 30.0)
    return dur, w, h, fps


def extract_vocal_band_rms(mp4_path: str, frame_ms: int = 20) -> dict:
    """Compute 20ms vocal-band (300-3400Hz) RMS dB curve and adaptive threshold."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", mp4_path, "-vn",
        "-af", "highpass=f=300,lowpass=f=3400",
        "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
    ]
    pcm = subprocess.check_output(cmd)
    samples = struct.unpack("<" + str(len(pcm) // 2) + "h", pcm)
    step = int(16000 * (frame_ms / 1000.0))
    rms_db = []
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        if not chunk:
            continue
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        rms_db.append(round(20.0 * math.log10(max(1e-5, rms)), 2))
    s_rms = sorted(rms_db) if rms_db else [-55.0]
    p25 = s_rms[len(s_rms) // 4]
    thresh = round(max(-40.0, min(-26.0, p25 + 6.5)), 2)
    return {"frame_ms": frame_ms, "threshold_db": thresh, "p25_db": round(p25, 2), "rms_db": rms_db}


def extract_2fps_motion(mp4_path: str, w: int, h: int, cam_box: dict | None = None) -> dict:
    """Compute 2 fps pixel MAE series for gameplay ROI and webcam ROI via fast FFmpeg pipe."""
    sw, sh = (180, 320) if h > w else (320, 180)
    raw = subprocess.check_output(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp4_path,
            "-vf", f"fps=2,scale={sw}:{sh}:flags=fast_bilinear",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ]
    )
    frame_sz = sw * sh
    n_frames = len(raw) // frame_sz

    # Determine webcam ROI in scaled coords
    if h > w:
        cy0, cy1, cx0, cx1 = 0, int(sh * 0.33), 0, sw
        gy0, gy1, gx0, gx1 = int(sh * 0.33), int(sh * 0.92), 0, sw
    elif cam_box and cam_box.get("w", 0) > 0 and cam_box.get("h", 0) > 0:
        cx0 = max(0, min(sw - 8, int(round(cam_box["x"] * sw / w))))
        cy0 = max(0, min(sh - 8, int(round(cam_box["y"] * sh / h))))
        cx1 = max(cx0 + 8, min(sw, cx0 + int(round(cam_box["w"] * sw / w))))
        cy1 = max(cy0 + 8, min(sh, cy0 + int(round(cam_box["h"] * sh / h))))
        gy0, gy1, gx0, gx1 = 0, sh, 0, sw
    else:
        cx0, cy0, cx1, cy1 = 0, 0, 0, 0
        gy0, gy1, gx0, gx1 = 0, sh, 0, sw

    cam_vals, game_vals = {}, {}
    prev_cam, prev_game = None, None
    for idx in range(n_frames):
        arr = np.frombuffer(raw[idx * frame_sz:(idx + 1) * frame_sz], dtype=np.uint8).reshape((sh, sw)).astype(np.float32)
        g_roi = arr[gy0:gy1, gx0:gx1]
        c_roi = arr[cy0:cy1, cx0:cx1] if cx1 > cx0 and cy1 > cy0 else None
        if prev_game is not None:
            game_vals[idx] = round(float(np.mean(np.abs(g_roi - prev_game))), 2)
            if c_roi is not None and prev_cam is not None:
                cam_vals[idx] = round(float(np.mean(np.abs(c_roi - prev_cam))), 2)
        prev_game = g_roi
        prev_cam = c_roi

    g_list = sorted(game_vals.values()) or [18.0]
    c_list = sorted(cam_vals.values()) or [2.5]
    return {
        "game_vals": game_vals,
        "cam_vals": cam_vals,
        "game_med": float(statistics.median(g_list)),
        "game_p75": float(g_list[min(len(g_list) - 1, int(len(g_list) * 0.75))]),
        "cam_med": float(statistics.median(c_list)),
        "cam_p75": float(c_list[min(len(c_list) - 1, int(len(c_list) * 0.75))]),
    }


def _extract_word_intervals(whisper_doc: dict | None, duration: float) -> list[tuple[float, float]]:
    if not isinstance(whisper_doc, dict):
        return []
    words = whisper_doc.get("words") or (whisper_doc.get("x_groq") or {}).get("words") or []
    out = []
    for w in words:
        txt = str(w.get("word") or "").strip()
        if not txt:
            continue
        st = max(0.0, float(w.get("start") or 0.0))
        en = max(st + 0.05, float(w.get("end") or (st + 0.2)))
        if st < duration:
            out.append((st, min(duration, en)))
    return out


def plan_jumpcuts(
    duration: float,
    rms_info: dict,
    motion_info: dict,
    word_intervals: list[tuple[float, float]] | None = None,
    min_pause_to_cut: float = 1.05,
    protect_beat_sec: float = 0.85,
    pre_pad: float = 0.12,
    post_pad: float = 0.15,
    min_cut_spacing: float = 2.5,
    min_kept_seg: float = 1.20,
    min_final_dur: float | None = None,
) -> dict:
    """Compute speech/action active spans & dead-spot cuts respecting motion protection and rhythm."""
    rms_db = rms_info["rms_db"]
    thresh = rms_info["threshold_db"]
    frame_sec = rms_info["frame_ms"] / 1000.0
    n_frames = len(rms_db)
    if min_final_dur is None:
        # Never shrink a valid >=14.2s clip below Create Subtitle Binary's 14.0s minimum floor!
        min_final_dur = 14.1 if duration >= 14.2 else max(10.0, duration)

    # Mark frames covered by Whisper words (tightened against leading stretch > 0.45s)
    word_covered = [False] * n_frames
    if word_intervals:
        for ws, we in word_intervals:
            dur_w = we - ws
            eff_ws = (we - 0.50) if dur_w > 0.65 else ws
            f0 = max(0, int(math.floor(eff_ws / frame_sec)))
            f1 = min(n_frames - 1, int(math.ceil(we / frame_sec)))
            for f_i in range(f0, f1 + 1):
                word_covered[f_i] = True

    # Mark 20ms active speech frames (require 2/3 frames >= thresh; outside Whisper words require +3.5dB so wind/engines don't mask dead pauses)
    active = [False] * n_frames
    outside_thresh = min(-24.0, thresh + 3.5) if word_intervals else thresh
    for i in range(n_frames):
        lo = max(0, i - 1)
        hi = min(n_frames, i + 2)
        eff_th = thresh if word_covered[i] else outside_thresh
        if sum(1 for v in rms_db[lo:hi] if v >= eff_th) >= 2:
            active[i] = True
        elif word_covered[i] and any(rms_db[k] >= thresh - 3.5 for k in range(lo, hi)):
            active[i] = True

    # Bridge tiny <= 0.35s micro-gaps inside phrases so consonant stops don't split words
    bridge_frames = int(round(0.35 / frame_sec))
    i = 0
    while i < n_frames:
        if not active[i]:
            j = i
            while j < n_frames and not active[j]:
                j += 1
            if i > 0 and j < n_frames and (j - i) <= bridge_frames:
                for k in range(i, j):
                    active[k] = True
            i = j
        else:
            i += 1

    # Per-0.5s-bin motion protection: only protect genuine high-action gameplay spikes or active streamer face reactions
    game_vals = motion_info["game_vals"]
    cam_vals = motion_info["cam_vals"]
    game_spike_thresh = max(32.0, motion_info["game_p75"] * 1.25, motion_info["game_med"] * 1.35)
    cam_spike_thresh = max(3.6, motion_info["cam_p75"] * 1.02, motion_info["cam_med"] * 1.22)

    def _is_bin_protected(b_idx: int) -> bool:
        g_v = game_vals.get(b_idx, 0.0)
        c_v = cam_vals.get(b_idx, 0.0)
        return (g_v >= game_spike_thresh) or (c_v >= cam_spike_thresh)

    def _extract_unprotected_cuts(span_s: float, span_e: float, is_intro: bool, is_outro: bool) -> list[tuple[float, float, str]]:
        if is_intro:
            cut_e = max(0.0, span_e - pre_pad)
            if (span_e - span_s) > 0.35 and cut_e >= 0.25:
                b0, b1 = 1, max(1, int(math.ceil(cut_e * 2.0)))
                if not any(_is_bin_protected(b) for b in range(b0, b1 + 1)):
                    return [(0.0, round(cut_e, 3), "dead_intro")]
            return []
        if is_outro:
            cut_s = min(duration, span_s + post_pad)
            if (span_e - span_s) > 0.90 and (duration - cut_s) >= 0.65:
                b0, b1 = max(1, int(math.floor(cut_s * 2.0))), max(1, int(math.ceil(duration * 2.0)))
                if not any(_is_bin_protected(b) for b in range(b0, b1 + 1)):
                    return [(round(cut_s, 3), round(duration, 3), "dead_outro")]
            return []
        # Internal silent span: carve unprotected 0.5s sub-spans > min_pause_to_cut (1.05s) so a single turn inside a 6s silence doesn't block cutting the rest!
        if (span_e - span_s) <= max(min_pause_to_cut, protect_beat_sec):
            return []
        b_start = max(0, int(math.floor(span_s * 2.0)))
        b_end = max(b_start, int(math.ceil(span_e * 2.0)))
        out = []
        cur_u_s = None
        for b in range(b_start, b_end + 1):
            t0_b = max(span_s, b * 0.5)
            t1_b = min(span_e, (b + 1) * 0.5)
            if t1_b <= t0_b:
                continue
            if not _is_bin_protected(b):
                if cur_u_s is None:
                    cur_u_s = t0_b
            else:
                if cur_u_s is not None:
                    sub_e = t0_b
                    if (sub_e - cur_u_s) > min_pause_to_cut:
                        cs = round(cur_u_s + (post_pad if cur_u_s <= span_s + 0.05 else 0.12), 3)
                        ce = round(sub_e - 0.12, 3)
                        if (ce - cs) >= 0.55:
                            out.append((cs, ce, "dead_pause"))
                    cur_u_s = None
        if cur_u_s is not None:
            sub_e = span_e
            if (sub_e - cur_u_s) > min_pause_to_cut:
                cs = round(cur_u_s + (post_pad if cur_u_s <= span_s + 0.05 else 0.12), 3)
                ce = round(sub_e - pre_pad, 3)
                if (ce - cs) >= 0.55:
                    out.append((cs, ce, "dead_pause"))
        return out

    # Identify silent spans & candidate cut intervals
    raw_cuts = []
    i = 0
    while i < n_frames:
        if not active[i]:
            j = i
            while j < n_frames and not active[j]:
                j += 1
            s_t = round(i * frame_sec, 3)
            e_t = round(min(duration, j * frame_sec), 3)
            raw_cuts.extend(_extract_unprotected_cuts(s_t, e_t, is_intro=(i == 0), is_outro=(j >= n_frames)))
            i = j
        else:
            i += 1

    # Enforce max 1 internal cut per min_cut_spacing (2.5s), >=1.20s kept segments, and >=min_final_dur
    kept_cuts = []
    # Sort priority: intro/outro + longest dead pauses first when spacing conflicts occur
    internal_cuts = sorted([c for c in raw_cuts if c[2] == "dead_pause"], key=lambda x: x[1] - x[0], reverse=True)
    edge_cuts = [c for c in raw_cuts if c[2] != "dead_pause"]

    selected_internal = []
    for c in internal_cuts:
        mid = (c[0] + c[1]) * 0.5
        if any(abs(mid - ((ex[0] + ex[1]) * 0.5)) < min_cut_spacing for ex in selected_internal):
            continue
        selected_internal.append(c)

    all_cuts = sorted(edge_cuts + selected_internal, key=lambda x: x[0])

    # Convert cuts into kept segments, dropping cuts that create choppy <min_kept_seg shards or shrink below min_final_dur
    def _cuts_to_segments(cuts_list):
        segs = []
        cursor = 0.0
        for cs, ce, reason in cuts_list:
            if cs > cursor + 0.05:
                segs.append({"start": round(cursor, 3), "end": round(cs, 3)})
            cursor = max(cursor, ce)
        if duration > cursor + 0.05:
            segs.append({"start": round(cursor, 3), "end": round(duration, 3)})
        return segs

    # Prune cuts violating min_kept_seg (1.20s) or min_final_dur
    pruned = list(all_cuts)
    while pruned:
        segs = _cuts_to_segments(pruned)
        tot_kept = sum(s["end"] - s["start"] for s in segs)
        bad_idx = None
        for idx, s in enumerate(segs):
            if (s["end"] - s["start"]) < min_kept_seg:
                # Find cut adjacent to this short shard
                if idx == 0:
                    bad_idx = 0
                elif idx == len(segs) - 1:
                    bad_idx = len(pruned) - 1
                else:
                    # Drop whichever flanking cut is smaller
                    bad_idx = idx - 1 if (pruned[idx - 1][1] - pruned[idx - 1][0]) <= (pruned[idx][1] - pruned[idx][0]) else idx
                break
        if bad_idx is not None:
            pruned.pop(bad_idx)
            continue
        if tot_kept < min_final_dur:
            need = min_final_dur - tot_kept
            # Proportionally trim down dead_pause cuts so multiple dead spots are each shortened below 1.0s rather than dropping one wholly
            shrinkable = [k for k in range(len(pruned)) if pruned[k][2] == "dead_pause" and (pruned[k][1] - pruned[k][0]) > 0.55]
            total_slack = sum((pruned[k][1] - pruned[k][0]) - 0.50 for k in shrinkable)
            if shrinkable and total_slack >= need:
                rem = need
                ordered_k = sorted(shrinkable, key=lambda x: pruned[x][1] - pruned[x][0], reverse=True)
                for idx_s, k in enumerate(ordered_k):
                    if rem <= 0.001:
                        break
                    cs, ce, rsn = pruned[k]
                    avail = (ce - cs) - 0.50
                    if idx_s == len(ordered_k) - 1:
                        take = min(avail, rem)
                    else:
                        take = min(avail, rem, round(need * (avail / total_slack), 3))
                    if take > 0.005:
                        pruned[k] = (cs, round(ce - take, 3), rsn)
                        rem = round(rem - take, 3)
                if rem <= 0.01:
                    continue
            smallest_i = min(range(len(pruned)), key=lambda k: pruned[k][1] - pruned[k][0])
            pruned.pop(smallest_i)
            continue
        break

    final_segs = _cuts_to_segments(pruned)
    if not final_segs:
        final_segs = [{"start": 0.0, "end": round(duration, 3)}]

    return {
        "orig_duration": round(duration, 3),
        "final_duration": round(sum(s["end"] - s["start"] for s in final_segs), 3),
        "cuts_applied": max(0, len(final_segs) - 1 + (1 if final_segs[0]["start"] > 0.1 else 0) + (1 if final_segs[-1]["end"] < duration - 0.1 else 0)),
        "cut_regions": [{"start": c[0], "end": c[1], "reason": c[2]} for c in pruned],
        "kept_segments": final_segs,
    }


def render_jumpcuts(src_mp4: str, dst_mp4: str, kept_segments: list[dict], fps: float = 30.0) -> None:
    """Render kept segments with 18ms audio fades at every cut seam and lock video/audio sample alignment."""
    if len(kept_segments) == 1 and kept_segments[0]["start"] <= 0.05:
        v_dur, _, _, _ = _probe_media(src_mp4)
        if abs(kept_segments[0]["end"] - v_dur) <= 0.10:
            if os.path.abspath(src_mp4) != os.path.abspath(dst_mp4):
                shutil.copy2(src_mp4, dst_mp4)
            return

    filter_parts = []
    concat_inputs = []
    fade_d = 0.018  # 18ms click-free fade at every seam
    for idx, seg in enumerate(kept_segments):
        st = float(seg["start"])
        en = float(seg["end"])
        seg_dur = max(0.2, en - st)
        fd = min(fade_d, seg_dur * 0.20)
        out_st = max(0.0, seg_dur - fd)
        filter_parts.append(f"[0:v]trim=start={st:.3f}:end={en:.3f},setpts=PTS-STARTPTS[v{idx}]")
        # Fade in at every non-first cut & fade out at every non-last cut (or all seams smoothly)
        af = f"[0:a]atrim=start={st:.3f}:end={en:.3f},asetpts=PTS-STARTPTS"
        if idx > 0:
            af += f",afade=t=in:ss=0:d={fd:.3f}"
        if idx < len(kept_segments) - 1:
            af += f",afade=t=out:st={out_st:.3f}:d={fd:.3f}"
        af += f"[a{idx}]"
        filter_parts.append(af)
        concat_inputs.append(f"[v{idx}][a{idx}]")

    n = len(kept_segments)
    if n > 1:
        filter_parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[vc][ac]")
        v_map, a_map = "[vc]", "[ac]"
    else:
        v_map, a_map = "[v0]", "[a0]"

    total_out_dur = sum(float(s["end"]) - float(s["start"]) for s in kept_segments)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src_mp4,
        "-filter_complex", ";".join(filter_parts),
        "-map", v_map, "-map", a_map,
        "-r", f"{fps:.3f}", "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{total_out_dur:.3f}",
        dst_mp4,
    ]
    subprocess.run(cmd, check=True)


def process_jumpcuts(
    src_mp4: str,
    dst_mp4: str = "",
    whisper_doc: dict | None = None,
    cam_box: dict | None = None,
) -> dict:
    """Analyze mp4, cut verified low-motion dead spots, and write cleanly to dst_mp4 (or replace in-place)."""
    in_place = (not dst_mp4) or (os.path.abspath(src_mp4) == os.path.abspath(dst_mp4))
    dur, w, h, fps = _probe_media(src_mp4)
    if dur < 14.5:
        return {
            "status": "skipped_short",
            "orig_duration": round(dur, 3),
            "final_duration": round(dur, 3),
            "cuts_applied": 0,
            "cut_regions": [],
            "kept_segments": [{"start": 0.0, "end": round(dur, 3)}],
        }

    rms_info = extract_vocal_band_rms(src_mp4)
    motion_info = extract_2fps_motion(src_mp4, w, h, cam_box=cam_box)
    word_intervals = _extract_word_intervals(whisper_doc, dur)
    plan = plan_jumpcuts(dur, rms_info, motion_info, word_intervals=word_intervals)

    if plan["cuts_applied"] > 0:
        if in_place:
            tmp_out = src_mp4 + ".jc_tmp.mp4"
            render_jumpcuts(src_mp4, tmp_out, plan["kept_segments"], fps=fps)
            os.replace(tmp_out, src_mp4)
        else:
            render_jumpcuts(src_mp4, dst_mp4, plan["kept_segments"], fps=fps)
    elif not in_place:
        shutil.copy2(src_mp4, dst_mp4)

    return {"status": "ok", **plan}


def main():
    parser = argparse.ArgumentParser(description="Apply intelligent audio-visual dead-spot jump cuts.")
    parser.add_argument("input_mp4", help="Source clip MP4 path")
    parser.add_argument("output_mp4", nargs="?", default="", help="Optional output path (in-place if omitted)")
    parser.add_argument("--cam", default="/files/temp/cam_config.json")
    parser.add_argument("--whisper", default="")
    parser.add_argument("--out-json", default="/files/temp/jumpcut_plan.json")
    args = parser.parse_args()

    cam_box = None
    if args.cam and os.path.exists(args.cam):
        try:
            c = json.load(open(args.cam, "r", encoding="utf-8"))
            if c.get("ai_found") and c.get("cam_w", 0) > 0:
                cam_box = {"x": c.get("cam_x", 0), "y": c.get("cam_y", 0), "w": c.get("cam_w", 0), "h": c.get("cam_h", 0)}
        except Exception:
            pass
    w_doc = None
    if args.whisper and os.path.exists(args.whisper):
        try:
            w_doc = json.load(open(args.whisper, "r", encoding="utf-8"))
        except Exception:
            pass

    res = process_jumpcuts(args.input_mp4, args.output_mp4, whisper_doc=w_doc, cam_box=cam_box)
    if args.out_json:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
        except Exception:
            pass
    print(json.dumps(res))


if __name__ == "__main__":
    main()
