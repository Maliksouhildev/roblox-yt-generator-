#!/usr/bin/env python3
"""
chat_analyzer.py
----------------
Universal, zero-dependency stream chat parser & audience reaction heatmap generator.
Supports both YouTube Live Replay and Twitch VOD chat JSON (via yt-dlp or TwitchDownloader).

Calculates:
1. Sub-second message velocity (msgs/10s).
2. Gamer & Twitch emote bursts (Laughter, Shock, Hype, Superchats/Bits).
3. Statistical velocity spikes relative to rolling baseline.
4. Outputs structured JSON for multimodal fusion.
"""

import sys
import os
import json
import re
from collections import Counter

# Gamer, YouTube & Twitch emote dictionary
LEXICON = {
    "laugh": {
        "lol", "lmao", "lmfao", "kekw", "haha", "hahaha", "💀", "😂", "rofl", "dying", "dead",
        "xd", "crying", "omg haha", "he really did that", "no he didnt", "omegalul", "lul",
        "luzz", "kek", "kekerino", "jajaja", "catjam"
    },
    "shock": {
        "wtf", "what", "omg", "no way", "hacker", "wait", "whaaat", "how", "???", "😱",
        "bro", "aint no way", "bruh", "caught", "sus", "run", "behind you", "watch out",
        "monkas", "monkaw", "notlikethis", "wutface", "clueless", "huh", "aimbot"
    },
    "hype": {
        "w", "l", "pog", "poggers", "pogchamp", "gg", "rip", "clutch", "lets go", "sheesh",
        "hype", "fire", "cooked", "banned", "gigachad", "ez", "pepehands", "sadge", "copium"
    }
}


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
    """Parses a Twitch chat JSON comment object (from TwitchDownloader or yt-dlp)."""
    offset_sec = comment.get("content_offset_seconds")
    if offset_sec is None:
        offset_ms = comment.get("offset_ms") or comment.get("time")
        if offset_ms is not None:
            offset_sec = float(offset_ms) / 1000.0

    if offset_sec is None:
        return None

    author = comment.get("commenter", {}).get("display_name") or comment.get("author", {}).get("name", "anonymous")
    
    # Message text
    msg_obj = comment.get("message", {})
    if isinstance(msg_obj, str):
        msg_text = msg_obj
    else:
        msg_text = msg_obj.get("body", "")
        if not msg_text and "fragments" in msg_obj:
            msg_text = "".join([f.get("text", "") for f in msg_obj["fragments"]])

    # Bits check
    bits = msg_obj.get("bits_spent") or 0 if isinstance(msg_obj, dict) else 0

    return [{
        "time": float(offset_sec),
        "text": msg_text.strip(),
        "author": author,
        "type": "bits" if bits > 0 else "text",
        "amount": f"{bits} bits" if bits > 0 else "$0",
        "platform": "twitch"
    }]


def analyze_chat(file_path: str, window_sec: float = 10.0, step_sec: float = 2.5):
    """
    Reads .live_chat.json or .chat.json (YouTube or Twitch) and computes rolling velocity & sentiment heatmap.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Chat file not found: {file_path}")

    messages = []
    platform = "unknown"

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        # Check first line / block to see if it's a monolithic JSON (Twitch) or JSONL (YouTube/yt-dlp)
        first_chunk = f.read(2048)
        f.seek(0)

        if '"comments":' in first_chunk or '"comments" :' in first_chunk:
            # Monolithic Twitch JSON structure
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
            # Line-delimited JSON (YouTube or yt-dlp Twitch)
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

    while curr <= end_time:
        w_start = curr
        w_end = curr + window_sec

        window_msgs = [m for m in messages if w_start <= m["time"] <= w_end]
        count = len(window_msgs)
        velocity = count / (window_sec / 10.0)  # msgs per 10s

        laugh_count = 0
        shock_count = 0
        hype_count = 0
        superchats = 0
        all_words = []

        for m in window_msgs:
            t_lower = m["text"].lower()
            if m.get("type") in ["superchat", "bits"]:
                superchats += 1

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

            clean_tokens = re.findall(r'\b\w+\b|[💀😂😱]', t_lower)
            all_words.extend([tk for tk in clean_tokens if len(tk) > 2 or tk in ['w', 'l', '💀', '😂', '😱', 'gg']])

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

    # Baseline statistics
    all_velocities = [b["velocity"] for b in buckets]
    median_vel = float(sorted(all_velocities)[len(all_velocities) // 2]) if all_velocities else 1.0
    mean_vel = float(sum(all_velocities) / max(1, len(all_velocities)))
    baseline_vel = max(1.0, median_vel)

    spikes = []
    for b in buckets:
        v = b["velocity"]
        vel_ratio = v / baseline_vel
        emote_burst = (b["laugh_count"] * 1.5 + b["shock_count"] * 1.8 + b["hype_count"] * 1.2 + b["superchats"] * 3.0)
        score = min(100.0, (vel_ratio * 25.0) + (emote_burst * 5.0))
        b["chat_score"] = round(score, 1)

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

    # Cluster overlapping spikes
    clustered_spikes = []
    if spikes:
        curr_cluster = [spikes[0]]
        for sp in spikes[1:]:
            last = curr_cluster[-1]
            if sp["start"] <= last["end"] + 7.5:
                curr_cluster.append(sp)
            else:
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

    clustered_spikes.sort(key=lambda s: s["max_score"], reverse=True)

    return {
        "platform": platform,
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
        print("Usage: python3 chat_analyzer.py <input.live_chat.json|input.chat.json> [output.json]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else in_file.replace(".json", ".analysis.json")

    print(f"[Chat Analyzer] Parsing {in_file}...")
    res = analyze_chat(in_file)
    print(f"[Chat Analyzer] Platform: {res['platform'].upper()} | Total Messages: {res['total_messages']} | Baseline: {res['baseline_velocity']} msgs/10s")
    print(f"[Chat Analyzer] Identified {len(res['top_clusters'])} High-Hype Scene Clusters.")
    for i, sc in enumerate(res['top_clusters'][:5], 1):
        print(f"  #{i}: [{sc['start']}s - {sc['end']}s] Score: {sc['max_score']} | Peak Vel: {sc['peak_velocity']} | Laugh: {sc['laugh_count']} | Shock: {sc['shock_count']} | Emotes: {', '.join(sc['sample_emotes'])}")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[Chat Analyzer] Saved analysis to {out_file}")
