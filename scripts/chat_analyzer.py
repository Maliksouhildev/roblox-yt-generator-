#!/usr/bin/env python3
"""
chat_analyzer.py
----------------
Universal Audience Reaction & Laughter Anomaly Engine for YouTube & Twitch.
Upgraded with:
1. Regex-based elongated laughter token matching (ha+h+a+, lo+l+, lmf*a+o+, KEKW, OMEGALUL, LULW, ICANT, 💀, 😂, 🤣, 😭).
2. Rolling 5-Minute Z-Score Anomaly Detection (Z >= 2.5 sigma above rolling baseline).
3. Laughter Density Ratio Filter (> 30% of messages in window are laughter tokens).
4. Scientifically Calibrated Causal Window [T_laugh - 15s, T_laugh - 1s] accounting for HLS latency + human reaction delay.
5. Unified YouTube & Twitch schema normalization with millisecond precision.
"""

import sys
import os
import json
import re
import math
from collections import Counter

# ── 1. Regex Token Analyzers ────────────────────────────────────────────────
RE_LAUGH = re.compile(
    r'\b((?:h+[aeiou]+){2,}|(?:j+[aeiou]+){2,}|l+o+l+[a-z]*|l+m+f*a+o+|r+o+f+l+|k+e+k+w*|o+m+e+g+a+l+u+l+|l+u+l+w*|i+c+a+n+t+|d+e+a+d+|d+y+i+n+g+|x+d+)\b|[💀😂🤣😭]',
    re.IGNORECASE
)

RE_SHOCK = re.compile(
    r'\b(w+t+f+|w+h+a+t+|o+m+g+|n+o+\s*w+a+y+|h+a+c+k+e+r+|w+a+i+t+|b+r+o+|b+r+u+h+|s+u+s+|m+o+n+k+a+[sw]|c+l+u+e+l+e+s+s+|w+u+t+f+a+c+e+|a+i+m+b+o+t+|n+o+t+l+i+k+e+t+h+i+s+)\b|\?{2,}|[😱]',
    re.IGNORECASE
)

RE_HYPE = re.compile(
    r'\b(p+o+g+[a-z]*|g+g+|r+i+p+|c+l+u+t+c+h+|s+h+e+e+s+h+|c+o+o+k+e+d+|f+i+r+e+|g+i+g+a+c+h+a+d+|e+z+|c+o+p+i+u+m+|b+a+n+n+e+d+)\b|^[wl]$',
    re.IGNORECASE
)


def parse_youtube_line(data: dict):
    """Parses a YouTube live chat JSON line."""
    offset_ms = data.get("videoOffsetTimeMsec")
    replay_action = data.get("replayChatItemAction") or {}
    if offset_ms is None:
        offset_ms = replay_action.get("videoOffsetTimeMsec")

    if offset_ms is None:
        return None

    try:
        offset_sec = float(offset_ms) / 1000.0
    except (ValueError, TypeError):
        return None

    actions = replay_action.get("actions") or []
    results = []

    for action in actions:
        add_item = action.get("addChatItemAction", {}).get("item", {})
        text_renderer = add_item.get("liveChatTextMessageRenderer")
        if text_renderer:
            runs = text_renderer.get("message", {}).get("runs") or []
            msg_parts = []
            for r in runs:
                if "text" in r:
                    msg_parts.append(r["text"])
                elif "emoji" in r:
                    shortcuts = r["emoji"].get("shortcuts") or []
                    msg_parts.append(shortcuts[0] if shortcuts else "emoji")
            msg_text = " ".join(msg_parts).strip()
            author = text_renderer.get("authorName", {}).get("simpleText", "anonymous")
            results.append({
                "time": offset_sec,
                "text": msg_text,
                "author": author,
                "type": "text",
                "platform": "youtube"
            })
            continue

        paid_renderer = add_item.get("liveChatPaidMessageRenderer")
        if paid_renderer:
            runs = paid_renderer.get("message", {}).get("runs") or []
            msg_parts = [r.get("text", "") for r in runs if "text" in r]
            amount = paid_renderer.get("purchaseAmountText", {}).get("simpleText", "$0")
            author = paid_renderer.get("authorName", {}).get("simpleText", "anonymous")
            results.append({
                "time": offset_sec,
                "text": " ".join(msg_parts).strip(),
                "amount": amount,
                "author": author,
                "type": "superchat",
                "platform": "youtube"
            })

    return results


def parse_twitch_comment(comment: dict):
    """Parses a Twitch chat comment (from Twitch GraphQL or TwitchDownloader)."""
    offset_sec = comment.get("content_offset_seconds")
    if offset_sec is None:
        offset_ms = comment.get("offset_ms") or comment.get("time")
        if offset_ms is not None:
            offset_sec = float(offset_ms) / 1000.0

    if offset_sec is None:
        return None

    author = comment.get("commenter", {}).get("display_name") or comment.get("author", {}).get("name", "anonymous")
    msg_obj = comment.get("message", {})
    if isinstance(msg_obj, str):
        msg_text = msg_obj
    else:
        msg_text = msg_obj.get("body", "")
        if not msg_text and "fragments" in msg_obj:
            msg_text = "".join([f.get("text", "") for f in msg_obj["fragments"]])

    bits = msg_obj.get("bits_spent") or 0 if isinstance(msg_obj, dict) else 0

    return [{
        "time": float(offset_sec),
        "text": msg_text.strip(),
        "author": author,
        "type": "bits" if bits > 0 else "text",
        "amount": f"{bits} bits" if bits > 0 else "$0",
        "platform": "twitch"
    }]


def analyze_chat(file_path: str, window_sec: float = 10.0, step_sec: float = 2.5, rolling_window_sec: float = 300.0):
    """
    Parses chat JSON, computes sliding-window statistics, and extracts high-precision laughter & hype anomalies
    using a 5-minute rolling Z-score.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Chat file not found: {file_path}")

    messages = []
    platform = "unknown"

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        first_chunk = f.read(2048)
        f.seek(0)

        if '"comments":' in first_chunk or '"comments" :' in first_chunk:
            platform = "twitch"
            try:
                full_doc = json.load(f)
                comments = full_doc.get("comments") or []
                for c in comments:
                    parsed = parse_twitch_comment(c)
                    if parsed:
                        messages.extend(parsed)
            except Exception as e:
                print(f"[Chat Analyzer] Error parsing monolithic Twitch JSON: {e}", file=sys.stderr)
        else:
            for line in f:
                line_s = line.strip()
                if not line_s:
                    continue
                try:
                    data = json.loads(line_s)
                    if "replayChatItemAction" in data or "videoOffsetTimeMsec" in data:
                        platform = "youtube"
                        parsed = parse_youtube_line(data)
                        if parsed:
                            messages.extend(parsed)
                    elif "content_offset_seconds" in data or "commenter" in data:
                        platform = "twitch"
                        parsed = parse_twitch_comment(data)
                        if parsed:
                            messages.extend(parsed)
                except Exception:
                    pass

    if not messages:
        return {
            "platform": platform,
            "total_messages": 0,
            "duration": 0,
            "laughter_clusters": [],
            "buckets": []
        }

    # Sort strictly by timestamp
    messages.sort(key=lambda m: m["time"])
    start_time = max(0.0, messages[0]["time"])
    end_time = messages[-1]["time"]
    total_msgs = len(messages)

    # ── 2. Time-series Binning (Sliding Window) ──────────────────────────────
    buckets = []
    curr = start_time
    msg_idx = 0
    total_count = len(messages)

    while curr <= end_time:
        w_start = curr
        w_end = curr + window_sec

        # Collect messages in this window
        window_msgs = []
        for m in messages:
            if m["time"] > w_end:
                break
            if m["time"] >= w_start:
                window_msgs.append(m)

        count = len(window_msgs)
        velocity = count / (window_sec / 10.0)  # msgs per 10s

        laugh_count = 0
        shock_count = 0
        hype_count = 0
        superchats = 0
        all_words = []
        sample_snippets = []

        for m in window_msgs:
            t = m["text"]
            if m.get("type") in ["superchat", "bits"]:
                superchats += 1

            is_laugh = bool(RE_LAUGH.search(t))
            is_shock = bool(RE_SHOCK.search(t))
            is_hype = bool(RE_HYPE.search(t))

            if is_laugh:
                laugh_count += 1
                if len(sample_snippets) < 6:
                    sample_snippets.append(t)
            if is_shock:
                shock_count += 1
            if is_hype:
                hype_count += 1

            clean_tokens = re.findall(r'\b\w+\b|[💀😂🤣😭😱]', t.lower())
            all_words.extend([tk for tk in clean_tokens if len(tk) > 2 or tk in ['w', 'l', '💀', '😂', '🤣', '😭', 'gg']])

        word_counts = Counter(all_words).most_common(5)
        top_emotes = [f"{w}({c})" for w, c in word_counts if c >= 2]

        laugh_velocity = laugh_count / (window_sec / 10.0)
        laugh_ratio = float(laugh_count / max(1, count))

        buckets.append({
            "start": round(w_start, 2),
            "end": round(w_end, 2),
            "mid": round((w_start + w_end) / 2.0, 2),
            "count": count,
            "velocity": round(velocity, 2),
            "laugh_count": laugh_count,
            "laugh_velocity": round(laugh_velocity, 2),
            "laugh_ratio": round(laugh_ratio, 3),
            "shock_count": shock_count,
            "hype_count": hype_count,
            "superchats": superchats,
            "top_emotes": top_emotes,
            "sample_snippets": sample_snippets
        })
        curr += step_sec

    # ── 3. Rolling 5-Minute Z-Score Anomaly Detection ────────────────────────
    # rolling_window_sec / step_sec = number of buckets in rolling window (e.g. 300 / 2.5 = 120 buckets)
    rolling_steps = int(math.ceil(rolling_window_sec / step_sec))
    all_laugh_vels = [b["laugh_velocity"] for b in buckets]
    all_total_vels = [b["velocity"] for b in buckets]

    median_vel = float(sorted(all_total_vels)[len(all_total_vels) // 2]) if all_total_vels else 1.0
    baseline_vel = max(1.0, median_vel)

    for i, b in enumerate(buckets):
        r_start = max(0, i - rolling_steps)
        r_slice_laugh = all_laugh_vels[r_start:i+1]
        r_slice_total = all_total_vels[r_start:i+1]

        mu_laugh = float(sum(r_slice_laugh) / max(1, len(r_slice_laugh)))
        var_laugh = float(sum((x - mu_laugh) ** 2 for x in r_slice_laugh) / max(1, len(r_slice_laugh)))
        sigma_laugh = math.sqrt(var_laugh)

        mu_total = float(sum(r_slice_total) / max(1, len(r_slice_total)))
        var_total = float(sum((x - mu_total) ** 2 for x in r_slice_total) / max(1, len(r_slice_total)))
        sigma_total = math.sqrt(var_total)

        z_laugh = (b["laugh_velocity"] - mu_laugh) / (sigma_laugh + 1e-4)
        z_total = (b["velocity"] - mu_total) / (sigma_total + 1e-4)

        b["z_laugh"] = round(z_laugh, 2)
        b["z_total"] = round(z_total, 2)

        # Composite Chat Score (0.0 to 100.0) based on Z-Score & Density
        comp_score = min(100.0, max(0.0, (z_laugh * 20.0) + (b["laugh_ratio"] * 40.0) + (z_total * 10.0)))
        b["chat_score"] = round(comp_score, 1)

    # ── 4. Laughter Cluster & Causal Window Extraction ──────────────────────
    # Peak Trigger: Z_laugh >= 2.5 AND laugh_ratio >= 0.30 AND laugh_count >= 2
    raw_peaks = []
    for b in buckets:
        if (b["z_laugh"] >= 2.5 and b["laugh_ratio"] >= 0.30 and b["laugh_count"] >= 2) or (b["z_laugh"] >= 3.5 and b["laugh_count"] >= 3):
            raw_peaks.append(b)

    # Cluster adjacent peaks into cohesive laughter bursts
    clusters = []
    if raw_peaks:
        curr_cluster = [raw_peaks[0]]
        for p in raw_peaks[1:]:
            last = curr_cluster[-1]
            if p["start"] <= last["end"] + 7.5:
                curr_cluster.append(p)
            else:
                # Merge cluster
                c_start = curr_cluster[0]["start"]
                c_end = curr_cluster[-1]["end"]
                peak_bucket = max(curr_cluster, key=lambda x: (x["z_laugh"], x["laugh_velocity"]))
                c_peak_t = peak_bucket["mid"]
                c_max_z = peak_bucket["z_laugh"]
                c_peak_vel = peak_bucket["velocity"]
                c_tot_laugh = sum(x["laugh_count"] for x in curr_cluster)
                c_tot_msgs = sum(x["count"] for x in curr_cluster)
                all_snips = []
                for x in curr_cluster:
                    all_snips.extend(x["sample_snippets"])

                # Causal Trigger Window: [T_laugh - 15s, T_laugh - 1s]
                causal_start = max(0.0, c_peak_t - 15.0)
                causal_end = max(0.0, c_peak_t - 1.0)

                clusters.append({
                    "cluster_id": len(clusters) + 1,
                    "peak_time": c_peak_t,
                    "burst_window": [c_start, c_end],
                    "causal_window": [round(causal_start, 1), round(causal_end, 1)],
                    "z_score": c_max_z,
                    "laugh_count": c_tot_laugh,
                    "total_messages": c_tot_msgs,
                    "laugh_ratio": round(c_tot_laugh / max(1, c_tot_msgs), 3),
                    "peak_velocity": c_peak_vel,
                    "sample_messages": list(dict.fromkeys(all_snips))[:8]
                })
                curr_cluster = [p]

        if curr_cluster:
            c_start = curr_cluster[0]["start"]
            c_end = curr_cluster[-1]["end"]
            peak_bucket = max(curr_cluster, key=lambda x: (x["z_laugh"], x["laugh_velocity"]))
            c_peak_t = peak_bucket["mid"]
            c_max_z = peak_bucket["z_laugh"]
            c_peak_vel = peak_bucket["velocity"]
            c_tot_laugh = sum(x["laugh_count"] for x in curr_cluster)
            c_tot_msgs = sum(x["count"] for x in curr_cluster)
            all_snips = []
            for x in curr_cluster:
                all_snips.extend(x["sample_snippets"])

            causal_start = max(0.0, c_peak_t - 15.0)
            causal_end = max(0.0, c_peak_t - 1.0)

            clusters.append({
                "cluster_id": len(clusters) + 1,
                "peak_time": c_peak_t,
                "burst_window": [c_start, c_end],
                "causal_window": [round(causal_start, 1), round(causal_end, 1)],
                "z_score": c_max_z,
                "laugh_count": c_tot_laugh,
                "total_messages": c_tot_msgs,
                "laugh_ratio": round(c_tot_laugh / max(1, c_tot_msgs), 3),
                "peak_velocity": c_peak_vel,
                "sample_messages": list(dict.fromkeys(all_snips))[:8]
            })

    # Sort clusters by Z-Score descending
    clusters.sort(key=lambda c: c["z_score"], reverse=True)

    return {
        "platform": platform,
        "total_messages": total_msgs,
        "duration_sec": round(end_time, 1),
        "baseline_velocity": round(baseline_vel, 2),
        "total_laughter_bursts": len(clusters),
        "top_clusters": clusters[:15],
        "buckets": buckets
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chat_analyzer.py <input.live_chat.json|input.chat.json> [output.json]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else in_file.replace(".json", ".analysis.json")

    print(f"[Chat Analyzer] Parsing {in_file}...")
    res = analyze_chat(in_file)
    print(f"[Chat Analyzer] Platform: {res['platform'].upper()} | Total Msgs: {res['total_messages']} | Baseline: {res['baseline_velocity']} msgs/10s")
    print(f"[Chat Analyzer] Discovered {len(res['top_clusters'])} Statistical Laughter Bursts (Z >= 2.5 sigma).")
    for i, cl in enumerate(res['top_clusters'][:5], 1):
        print(f"  #{i}: Peak at {cl['peak_time']}s | Z-Score: {cl['z_score']}σ | Laughs: {cl['laugh_count']} ({int(cl['laugh_ratio']*100)}%) | Causal Window: [{cl['causal_window'][0]}s - {cl['causal_window'][1]}s]")
        print(f"      Top Chat: {', '.join(cl['sample_messages'][:4])}")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[Chat Analyzer] Saved analysis to {out_file}")
