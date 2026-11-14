#!/usr/bin/env python3
"""
chat_analyzer.py
----------------
Free, zero-dependency stream chat parser & audience reaction heatmap generator.
Analyzes YouTube/Twitch live chat replay JSON (downloaded via yt-dlp).

Calculates:
1. Sub-second message velocity (msgs/10s).
2. Gamer emote bursts (Laughter, Shock, Hype, Superchats).
3. Statistical velocity spikes relative to rolling baseline.
4. Outputs structured JSON for multimodal fusion.
"""

import sys
import os
import json
import re
from collections import Counter

# Gamer emote & keyword dictionary
LEXICON = {
    "laugh": {
        "lol", "lmao", "lmfao", "kekw", "haha", "hahaha", "💀", "😂", "rofl", "dying", "dead",
        "xd", "crying", "omg haha", "he really did that", "no he didnt"
    },
    "shock": {
        "wtf", "what", "omg", "no way", "hacker", "wait", "whaaat", "how", "???", "😱",
        "bro", "aint no way", "bruh", "caught", "sus", "run", "behind you", "watch out"
    },
    "hype": {
        "w", "l", "pog", "poggers", "gg", "rip", "clutch", "lets go", "sheesh",
        "hype", "fire", "cooked", "banned"
    }
}


def parse_chat_line(line_str: str):
    """Parses a single yt-dlp live chat JSON line."""
    try:
        data = json.loads(line_str)
    except Exception:
        return None

    # Locate videoOffsetTimeMsec
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

    # Extract actions
    actions = replay_action.get("actions") or []
    results = []

    for action in actions:
        add_item = action.get("addChatItemAction", {}).get("item", {})
        
        # 1. Normal Text Message
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
                "type": "text"
            })
            continue

        # 2. Superchat / Paid Message
        paid_renderer = add_item.get("liveChatPaidMessageRenderer")
        if paid_renderer:
            runs = paid_renderer.get("message", {}).get("runs") or []
            msg_text = " ".join([r.get("text", "") for r in runs]).strip()
            amount = paid_renderer.get("purchaseAmountText", {}).get("simpleText", "$0")
            author = paid_renderer.get("authorName", {}).get("simpleText", "anonymous")
            results.append({
                "time": offset_sec,
                "text": msg_text,
                "amount": amount,
                "author": author,
                "type": "superchat"
            })

    return results


def analyze_chat(file_path: str, window_sec: float = 10.0, step_sec: float = 2.5):
    """
    Reads .live_chat.json line-by-line and computes rolling velocity & sentiment heatmap.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Chat file not found: {file_path}")

    messages = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parsed = parse_chat_line(line)
            if parsed:
                messages.extend(parsed)

    if not messages:
        return {
            "total_messages": 0,
            "duration": 0,
            "spikes": [],
            "buckets": []
        }

    # Sort strictly by timestamp
    messages.sort(key=lambda m: m["time"])
    start_time = max(0.0, messages[0]["time"])
    end_time = messages[-1]["time"]
    total_msgs = len(messages)

    # Binning with sliding window
    buckets = []
    curr = start_time
    idx = 0

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

        # Emote counts
        laugh_count = 0
        shock_count = 0
        hype_count = 0
        superchats = 0
        all_words = []

        for m in window_msgs:
            t_lower = m["text"].lower()
            if m.get("type") == "superchat":
                superchats += 1

            # Keyword matches
            for word in LEXICON["laugh"]:
                if word in t_lower:
                    laugh_count += 1
                    break
            for word in LEXICON["shock"]:
                if word in t_lower:
                    shock_count += 1
                    break
            for word in LEXICON["hype"]:
                if word in t_lower:
                    hype_count += 1
                    break

            # Collect tokens for top words
            clean_tokens = re.findall(r'\b\w+\b|[💀😂😱]', t_lower)
            all_words.extend([tk for tk in clean_tokens if len(tk) > 2 or tk in ['w', 'l', '💀', '😂', '😱']])

        word_counts = Counter(all_words).most_common(5)
        top_emotes = [f"{w}({c})" for w, c in word_counts if c >= 2]

        buckets.append({
            "start": round(w_start, 2),
            "end": round(w_end, 2),
            "mid": round((w_start + w_end) / 2.0, 2),
            "count": count,
            "velocity": round(velocity, 2),
            "laugh_count": laugh_count,
            "shock_count": shock_count,
            "hype_count": hype_count,
            "superchats": superchats,
            "top_emotes": top_emotes
        })

        curr += step_sec

    # Compute baseline statistics
    all_velocities = [b["velocity"] for b in buckets]
    median_vel = float(sorted(all_velocities)[len(all_velocities) // 2]) if all_velocities else 1.0
    mean_vel = float(sum(all_velocities) / max(1, len(all_velocities)))
    baseline_vel = max(1.0, median_vel)

    # Identify Velocity & Sentiment Spikes
    spikes = []
    for b in buckets:
        v = b["velocity"]
        vel_ratio = v / baseline_vel
        
        # Emote bonus
        emote_burst = (b["laugh_count"] * 1.5 + b["shock_count"] * 1.8 + b["hype_count"] * 1.2 + b["superchats"] * 3.0)
        
        # Viral score for chat window: 0 to 100
        score = min(100.0, (vel_ratio * 25.0) + (emote_burst * 5.0))
        b["chat_score"] = round(score, 1)

        # Trigger spike if velocity > 2.2x baseline OR high emote burst
        if (vel_ratio >= 2.2 and v >= 5) or emote_burst >= 6 or b["superchats"] > 0:
            spikes.append({
                "start": b["start"],
                "end": b["end"],
                "mid": b["mid"],
                "velocity": b["velocity"],
                "vel_ratio": round(vel_ratio, 2),
                "laugh": b["laugh_count"],
                "shock": b["shock_count"],
                "hype": b["hype_count"],
                "superchats": b["superchats"],
                "top_emotes": b["top_emotes"],
                "score": round(score, 1)
            })

    # Cluster overlapping spikes into cohesive scenes
    clustered_spikes = []
    if spikes:
        curr_cluster = [spikes[0]]
        for sp in spikes[1:]:
            last = curr_cluster[-1]
            if sp["start"] <= last["end"] + 7.5:
                curr_cluster.append(sp)
            else:
                # Merge cluster
                c_start = curr_cluster[0]["start"]
                c_end = curr_cluster[-1]["end"]
                c_peak_vel = max(c["velocity"] for c in curr_cluster)
                c_max_score = max(c["score"] for c in curr_cluster)
                c_laugh = sum(c["laugh"] for c in curr_cluster)
                c_shock = sum(c["shock"] for c in curr_cluster)
                c_hype = sum(c["hype"] for c in curr_cluster)
                c_super = sum(c["superchats"] for c in curr_cluster)
                # Combine top emotes
                all_top = []
                for c in curr_cluster:
                    all_top.extend(c["top_emotes"])
                clustered_spikes.append({
                    "start": c_start,
                    "end": c_end,
                    "duration": round(c_end - c_start, 1),
                    "peak_velocity": c_peak_vel,
                    "max_score": c_max_score,
                    "laugh_count": c_laugh,
                    "shock_count": c_shock,
                    "hype_count": c_hype,
                    "superchats": c_super,
                    "sample_emotes": list(set(all_top))[:6]
                })
                curr_cluster = [sp]

        if curr_cluster:
            c_start = curr_cluster[0]["start"]
            c_end = curr_cluster[-1]["end"]
            c_peak_vel = max(c["velocity"] for c in curr_cluster)
            c_max_score = max(c["score"] for c in curr_cluster)
            c_laugh = sum(c["laugh"] for c in curr_cluster)
            c_shock = sum(c["shock"] for c in curr_cluster)
            c_hype = sum(c["hype"] for c in curr_cluster)
            c_super = sum(c["superchats"] for c in curr_cluster)
            all_top = []
            for c in curr_cluster:
                all_top.extend(c["top_emotes"])
            clustered_spikes.append({
                "start": c_start,
                "end": c_end,
                "duration": round(c_end - c_start, 1),
                "peak_velocity": c_peak_vel,
                "max_score": c_max_score,
                "laugh_count": c_laugh,
                "shock_count": c_shock,
                "hype_count": c_hype,
                "superchats": c_super,
                "sample_emotes": list(set(all_top))[:6]
            })

    # Sort clustered spikes by max_score descending
    clustered_spikes.sort(key=lambda s: s["max_score"], reverse=True)

    return {
        "total_messages": total_msgs,
        "duration_sec": round(end_time, 1),
        "baseline_velocity": round(baseline_vel, 2),
        "mean_velocity": round(mean_vel, 2),
        "total_spikes_found": len(clustered_spikes),
        "top_clusters": clustered_spikes[:15],
        "buckets": buckets
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chat_analyzer.py <input.live_chat.json> [output.json]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else in_file.replace(".live_chat.json", ".chat_analysis.json")

    print(f"[Chat Analyzer] Parsing {in_file}...")
    res = analyze_chat(in_file)
    print(f"[Chat Analyzer] Total Messages: {res['total_messages']}, Baseline Velocity: {res['baseline_velocity']} msgs/10s")
    print(f"[Chat Analyzer] Identified {len(res['top_clusters'])} High-Hype Scene Clusters.")
    for i, sc in enumerate(res['top_clusters'][:5], 1):
        print(f"  #{i}: [{sc['start']}s - {sc['end']}s] Score: {sc['max_score']} | Peak Vel: {sc['peak_velocity']} | Laugh: {sc['laugh_count']} | Shock: {sc['shock_count']} | Emotes: {', '.join(sc['sample_emotes'])}")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[Chat Analyzer] Saved analysis to {out_file}")
