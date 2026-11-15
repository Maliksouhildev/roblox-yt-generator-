#!/usr/bin/env python3
"""
test_script_sandbox.py
----------------------
Standalone <10s CLI Script & Multi-Segment EDL Sandbox Runner.
Loads cached 1-hour+ multimodal telemetry from /files/temp/, runs the exact upgraded
Scout + Director prompts against Gemini Flash, executes non-sequential Whisper word splicing,
and prints Human-Readable Shorts Scripts + Role-Tagged EDLs in seconds (no video/FFmpeg).
"""

import os
import sys
import json
import re
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/files")

from telemetry_fusion_indexer import build_unified_index, format_mmss, HOUSEKEEPING_NOISE

GEMINI_KEY_PATHS = [
    "/files/gemini_key.txt",
    "/files/temp/gemini_key.txt",
    "/files/temp/n8n_gemini_key.txt",
    "C:/Users/mlkme/Desktop/AI_Clipper/temp/gemini_key.txt",
]

FILLER_WORDS = {"speaking", "of", "um", "uh", "oh", "since", "everyone", "like", "so"}


def get_api_key() -> str:
    env_k = os.environ.get("GEMINI_API_KEY", "").strip()
    if len(env_k) > 10:
        return env_k
    for p in GEMINI_KEY_PATHS:
        if os.path.exists(p):
            try:
                val = open(p, "r", encoding="utf-8").read().strip()
                if len(val) > 15:
                    return val
            except Exception:
                pass
    raise RuntimeError("Gemini API key not found in environment or /files/gemini_key.txt")


def call_gemini(api_key: str, prompt: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    model = os.environ.get("SANDBOX_GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    gen_cfg = {
        "temperature": temperature,
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _find_word_bounds(words: list, st: float, en: float):
    first_i, last_i = None, None
    for i, w in enumerate(words):
        ws = float(w.get("start", 0.0))
        we = float(w.get("end", ws))
        if we >= st and ws <= en:
            if first_i is None:
                first_i = i
            last_i = i
    return first_i, last_i


def snap_segment_to_sentences(words: list, st: float, en: float, role: str, min_st: float = 3.0, max_en: float = 1e9):
    """Snap non-hook boundaries cleanly between Whisper words at full sentence starts/ends."""
    if not words or role == "HOOK_CLIMAX":
        return max(min_st, st), min(max_en, en)

    first_i, last_i = _find_word_bounds(words, st, en)
    if first_i is None:
        return max(min_st, st), min(max_en, en)

    # Drop orphan sentence-ending token at word[first_i] (e.g. trailing 'plus.' or 'anything.')
    if first_i + 1 < len(words):
        first_tok = str(words[first_i].get("word", "")).strip()
        next_start = float(words[first_i + 1].get("start", st))
        if re.search(r"[.!?]$", first_tok) and next_start < en - 1.5:
            first_i += 1
            st = max(min_st, next_start - 0.04)

    # Snap start backward/forward if st landed mid-sentence (prev word lacks [.!?])
    if first_i > 0:
        prev_tok = str(words[first_i - 1].get("word", "")).strip()
        if not re.search(r"[.!?]$", prev_tok):
            snapped = False
            for j in range(first_i - 1, max(-1, first_i - 18), -1):
                ws_j = float(words[j].get("start", st))
                if ws_j < min_st or st - ws_j > 2.6:
                    break
                if j == 0 or re.search(r"[.!?]$", str(words[j - 1].get("word", "")).strip()):
                    prev_end = float(words[j - 1].get("end", 0.0)) if j > 0 else 0.0
                    st = max(min_st, prev_end + 0.02, ws_j - 0.06)
                    snapped = True
                    break
            if not snapped:
                for j in range(first_i + 1, min(len(words), first_i + 12)):
                    prev_j = str(words[j - 1].get("word", "")).strip()
                    ws_j = float(words[j].get("start", st))
                    if re.search(r"[.!?]$", prev_j) and (en - ws_j) >= 2.2:
                        prev_end = float(words[j - 1].get("end", 0.0))
                        st = max(min_st, prev_end + 0.02, ws_j - 0.06)
                        break

    # Snap end to clean sentence termination [.!?] without bleeding into next word
    first_i, last_i = _find_word_bounds(words, st, en)
    if last_i is not None and role not in ("HOOK_CLIMAX", "REVERSE_PAYOFF_END"):
        last_tok = str(words[last_i].get("word", "")).strip()
        if not re.search(r"[.!?]$", last_tok):
            snapped_end = False
            for j in range(last_i + 1, min(len(words), last_i + 22)):
                we_j = float(words[j].get("end", en))
                if we_j > max_en or we_j - en > 6.0:
                    break
                if re.search(r"[.!?]$", str(words[j].get("word", "")).strip()):
                    nxt_st = float(words[j + 1].get("start", we_j + 0.5)) if j + 1 < len(words) else we_j + 0.5
                    en = min(max_en, nxt_st - 0.02, we_j + 0.10)
                    snapped_end = True
                    break
            if not snapped_end:
                for j in range(last_i, max(first_i + 2, last_i - 12), -1):
                    we_j = float(words[j].get("end", en))
                    if re.search(r"[.!?]$", str(words[j].get("word", "")).strip()) and (we_j - st) >= 2.0:
                        nxt_st = float(words[j + 1].get("start", we_j + 0.5)) if j + 1 < len(words) else we_j + 0.5
                        en = min(nxt_st - 0.02, we_j + 0.10)
                        break

    return max(min_st, st), min(max_en, max(st + 0.8, en))


def _words_in_range(words: list, st: float, en: float) -> list:
    return [
        w for w in words
        if (float(w.get("start", 0.0)) + float(w.get("end", 0.0))) * 0.5 >= st - 0.01
        and (float(w.get("start", 0.0)) + float(w.get("end", 0.0))) * 0.5 <= en + 0.01
    ]


def splice_clip_edl(clip: dict, words: list) -> dict:
    """Mirrors 5. Split Clips + 6. Extract Viral Segments + DRY_RUN_SCRIPT_ONLY logic."""
    buf = 0.12
    raw_segs = []
    for s in clip.get("segments") or []:
        try:
            st = max(3.0, float(s["start"]))
            en = max(st + 0.5, float(s["end"]))
            raw_segs.append({
                "start": st,
                "end": en,
                "role": str(s.get("role") or "STORY_BEAT").upper(),
            })
        except Exception:
            pass

    if not raw_segs:
        st = max(3.0, float(clip.get("start_time") or 3.0))
        en = max(st + 12.0, float(clip.get("end_time") or st + 25.0))
        raw_segs = [{"start": st, "end": en, "role": "STORY_BEAT"}]

    # Separate optional 0:00 HOOK_CLIMAX flash-forward teaser from body segments so they never collide
    cleaned_segs = []
    hook_seg = None
    body_segs = []
    for i, s in enumerate(raw_segs):
        if i == 0 and s["role"] == "HOOK_CLIMAX":
            s["end"] = min(s["end"], s["start"] + 2.6)
            hook_seg = s
        else:
            body_segs.append(s)

    # Deduplicate and de-overlap chronological body segments strictly
    body_norm = []
    for s in body_segs:
        st, en, role = s["start"], s["end"], s["role"]
        for prev in body_norm:
            if st < prev["end"] + 0.15 and en > prev["start"] - 0.15:
                if en > prev["end"] + 1.2:
                    st = prev["end"] + 0.15
                elif st < prev["start"] - 1.2:
                    en = prev["start"] - 0.15
                else:
                    st = en
        if en - st >= 1.2:
            body_norm.append({"start": round(st, 2), "end": round(en, 2), "role": role})

    # Bounded pre-extension if raw body < 16s without invading subsequent body segments
    if hook_seg:
        cleaned_segs.append(hook_seg)
    tot = (hook_seg["end"] - hook_seg["start"] if hook_seg else 0.0) + sum(b["end"] - b["start"] for b in body_norm)
    if tot < 16.0 and body_norm:
        for idx_b, b in enumerate(body_norm):
            if b["end"] - b["start"] < 6.0:
                later_starts = [other["start"] for other in body_norm[idx_b + 1:] if other["start"] > b["start"]]
                safe_cap = (min(later_starts) - 0.25) if later_starts else (b["start"] + 10.0)
                b["end"] = round(min(safe_cap, max(b["end"], b["start"] + 7.5)), 2)

    cleaned_segs.extend(body_norm)
    raw_segs = cleaned_segs if cleaned_segs else raw_segs

    # Cap total non-linear duration <= 42s
    tot = sum(s["end"] - s["start"] for s in raw_segs)
    if len(raw_segs) > 1 and tot > 42.0:
        ratio = 40.0 / tot
        raw_segs = [
            {
                "start": s["start"],
                "end": round(s["start"] + max(1.5, (s["end"] - s["start"]) * ratio), 2),
                "role": s["role"],
            }
            for s in raw_segs
        ]

    final_segs = []
    emitted_body_ranges = []
    for idx, interval in enumerate(raw_segs):
        role = interval["role"]
        min_st = 3.0 if role == "HOOK_CLIMAX" else max([3.0] + [r[1] + 0.15 for r in emitted_body_ranges if interval["start"] >= r[0] - 0.5])
        future_starts = [o["start"] - 0.15 for o in raw_segs[idx + 1:] if o["start"] > interval["start"] and o["role"] != "HOOK_CLIMAX"]
        max_en = min(future_starts) if future_starts else 1e9

        start, int_end = snap_segment_to_sentences(words, interval["start"], interval["end"], role, min_st=min_st, max_en=max_en)
        if int_end - start < 0.8:
            continue

        clip_words = _words_in_range(words, start, int_end)
        if clip_words:
            w_idx = 0
            if idx == 0:
                while w_idx < min(3, len(clip_words) - 1):
                    cw = re.sub(r"[^a-z]", "", str(clip_words[w_idx].get("word", "")).lower())
                    if cw in FILLER_WORDS:
                        w_idx += 1
                    else:
                        break
            init_w = clip_words[w_idx] if w_idx < len(clip_words) else clip_words[0]
            curr_start = max(start, float(clip_words[0]["start"]) - 0.08)
            if w_idx > 0 and float(init_w["start"]) > curr_start:
                curr_start = float(init_w["start"]) - 0.06
            last_end = float(init_w["end"])

            role_segs = []
            for w in clip_words[w_idx + 1:]:
                ws, we = float(w["start"]), float(w["end"])
                if ws - last_end > 0.55:
                    role_segs.append({"role": role, "start": curr_start, "end": min(last_end + buf, ws - 0.02)})
                    curr_start = max(last_end + buf, ws - 0.06)
                last_end = we
            role_segs.append({"role": role, "start": curr_start, "end": min(int_end, last_end + buf)})
            # Drop orphan 1-word micro-shards (<0.45s) and mid-scene housekeeping thank-yous
            for rs in role_segs:
                sw = _words_in_range(words, rs["start"], rs["end"])
                stext = " ".join(str(w.get("word", "")).strip() for w in sw)
                if len(role_segs) > 1 and (HOUSEKEEPING_NOISE.search(stext) or "we are cunts" in stext.lower()):
                    continue
                if rs["end"] - rs["start"] >= 0.45 or len(sw) >= 2:
                    final_segs.append(rs)
        else:
            final_segs.append({"role": role, "start": max(0.0, start - buf), "end": int_end + buf})

        if role != "HOOK_CLIMAX":
            emitted_body_ranges.append((start, int_end))

    # Post-pause duration rescue: if clip < 15.0s after dead-air cuts, append following full sentences cleanly
    cur_tot = sum(s["end"] - s["start"] for s in final_segs)
    if cur_tot < 15.0 and words and final_segs:
        last_body = final_segs[-1]
        tail_st = last_body["end"] + 0.05
        tail_candidates = [w for w in words if float(w.get("start", 0.0)) >= tail_st and float(w.get("start", 0.0)) <= tail_st + 30.0]
        added_words = []
        active_added = 0.0
        prev_we = None
        last_kept_idx = -1
        for idx_tw, w in enumerate(tail_candidates):
            ws, we = float(w.get("start", 0.0)), float(w.get("end", 0.0))
            if prev_we is None:
                active_added += max(0.1, we - ws)
            elif ws - prev_we <= 0.55:
                active_added += max(0.05, we - prev_we)
            else:
                active_added += max(0.1, we - ws)
            prev_we = we
            added_words.append(w)
            last_kept_idx = idx_tw
            if re.search(r"[.!?]$", str(w.get("word", "")).strip()) and (cur_tot + active_added) >= 16.5:
                break
        if added_words:
            # Slice added_words smoothly with >0.55s pause cuts without bleeding into subsequent word
            cs = float(added_words[0]["start"]) - 0.06
            le = float(added_words[0]["end"])
            for w in added_words[1:]:
                ws, we = float(w["start"]), float(w["end"])
                if ws - le > 0.55:
                    if le - cs >= 0.45:
                        final_segs.append({"role": "PAYOFF", "start": cs, "end": min(le + buf, ws - 0.02)})
                    cs = max(le + buf, ws - 0.06)
                le = we
            nxt_st = float(tail_candidates[last_kept_idx + 1]["start"]) if last_kept_idx + 1 < len(tail_candidates) else le + 1.0
            if le - cs >= 0.45:
                final_segs.append({"role": "PAYOFF", "start": cs, "end": min(le + buf, nxt_st - 0.02)})

    edl_segments = []
    tot_dur = 0.0
    for order, seg in enumerate(final_segs):
        st = round(seg["start"], 3)
        en = round(max(st + 0.15, seg["end"]), 3)
        dur = round(en - st, 3)
        tot_dur += dur
        spoken = " ".join(
            str(w.get("word", "")).strip()
            for w in _words_in_range(words, st, en)
        ).strip()
        edl_segments.append({
            "segment_order": order,
            "start": st,
            "end": en,
            "start_tc": format_mmss(st),
            "end_tc": format_mmss(en),
            "duration": dur,
            "role": seg["role"],
            "spoken_text": spoken,
        })

    assembled = " -> ".join(
        f"[{s['role']} {s['start_tc']}-{s['end_tc']}] \"{s['spoken_text']}\""
        for s in edl_segments
    )

    return {
        "dry_run": True,
        "clip_number": clip.get("clip_number", 1),
        "narrative_archetype": clip.get("narrative_archetype", "HUBRIS_INSTANT_KARMA"),
        "title": clip.get("title", "Viral Moment 💀"),
        "hook_caption": str(clip.get("hook_caption", "WATCH WHAT HAPPENS")).upper(),
        "theme": clip.get("theme", "Gaming"),
        "total_duration_sec": round(tot_dur, 2),
        "assembled_spoken_script": clip.get("assembled_spoken_script") or assembled,
        "verbatim_word_spliced_script": assembled,
        "edl_segments": edl_segments,
        "signal_justification": clip.get("signal_justification", {}),
        "cause_and_effect_setup": clip.get("cause_and_effect_setup", ""),
    }


def run_sandbox(
    transcript_path: str = None,
    output_path: str = "/files/temp/sandbox_edl_preview.json",
    full_scout: bool = False,
):
    t_start = time.time()
    api_key = get_api_key()

    # 1. Load cached unified telemetry index (<0.3s) or build if needed
    idx_path = "/files/temp/unified_timeline_index.json"
    if not transcript_path and os.path.exists(idx_path) and os.path.exists("/files/temp/transcript.json"):
        with open(idx_path, "r", encoding="utf-8") as f:
            index_doc = json.load(f)
        with open("/files/temp/transcript.json", "r", encoding="utf-8") as f:
            tx_doc = json.load(f)
        words = tx_doc.get("words") or []
    else:
        index_doc = build_unified_index(transcript_path=transcript_path)
        with open("/files/temp/transcript.json", "r", encoding="utf-8") as f:
            tx_doc = json.load(f)
        words = tx_doc.get("words") or []

    t_load = time.time() - t_start
    anchors = index_doc.get("anchors") or []
    macro_timeline = index_doc.get("macro_high_signal_timeline", "")[:11000]

    # Build Scout Prompt with full float-second annotated context
    anchors_text = ""
    for a in anchors[:18]:
        cb_str = ""
        if a.get("callback_links"):
            cb_str = "\n  - Cross-Stream Callbacks: " + " | ".join(
                f"{cb['time']}s ({cb['tc']} | \"{cb['keyword']}\"): {cb['text']}" for cb in a["callback_links"]
            )
        anchors_text += (
            f"• [ANCHOR #{a['anchor_id']}] [{a['start']}s - {a['end']}s] (Peak {a['peak_time']}s | {a['peak_tc']} | Score {a['virality_score']} | Fit: {a.get('recommended_archetype')})\n"
            f"  - Audio: {a.get('audio_signal')} | Chat: {a.get('chat_signal')} | Face: {a.get('face_signal')}{cb_str}\n"
            f"  - Annotated Context:\n{a.get('annotated_context', '')[:1200]}\n\n"
        )

    scout_cache_path = "/files/temp/sandbox_scout_cache.json"
    idx_mtime = os.path.getmtime(idx_path) if os.path.exists(idx_path) else 0.0
    scout_out = None
    scout_cached = False

    if not full_scout and not transcript_path and os.path.exists(scout_cache_path):
        try:
            with open(scout_cache_path, "r", encoding="utf-8") as f:
                sc = json.load(f)
            if abs(float(sc.get("index_mtime", -1.0)) - idx_mtime) < 1.0 and sc.get("scout_out"):
                scout_out = sc["scout_out"]
                scout_cached = True
        except Exception:
            pass

    t_s0 = time.time()
    if scout_out is None:
        scout_prompt = (
            "SYSTEM: You are an elite YouTube Shorts Viral Content Scout.\n"
            "Analyze the multimodal anchors and timeline index from this 1+ hour livestream and select 5 DIVERSE, high-retention comedy/gaming candidates across ALL 5 archetypes:\n"
            "1. IN_MEDIA_RES_FLASHFORWARD (Shocked/panicked 1.5-2.4s tease cut STRICTLY 0.5s BEFORE the punchline -> rewind to earlier SETUP -> ESCALATION -> full PAYOFF)\n"
            "2. DOUBLE_DOWN_ESCALATION (SETUP/Fail 1 -> jump cut past dead air -> ESCALATION double-down -> Bigger Fail 2 PAYOFF)\n"
            "3. HUBRIS_INSTANT_KARMA (Arrogant boast/confidence SETUP -> smash cut -> instant collapse + stunned reaction PAYOFF)\n"
            "4. MYSTERY_OPEN_LOOP (Intriguing question/anomaly HOOK_CLIMAX 1.8-2.5s -> escalating clues SETUP/ESCALATION -> twist reveal PAYOFF)\n"
            "5. REVERSE_PAYOFF_LOOP (Chronological SETUP -> ESCALATION -> truncated PAYOFF clause flowing back into 0:00 opening words)\n\n"
            "STRICT ANTI-ADMIN FILTER: REJECT superchat thank-you rollcalls ('thank you for the super chat'), giveaway chat-spam prompts ('type X into the chat'), and boring friend-request searches.\n"
            "Focus on funny scams, sudden bans, absurd viewer requests, rage/panic moments, and visual gags.\n\n"
            f"=== PROVEN MULTIMODAL VIRAL PEAKS ===\n{anchors_text}\n"
            f"=== HIGH-SIGNAL TIMELINE INDEX ===\n{macro_timeline}\n\n"
            "OUTPUT concise candidate notes using exact float seconds from the transcript with NON-OVERLAPPING windows for SETUP (6-12s), ESCALATION (5-10s), PAYOFF (5-10s), plus an optional non-spoilering HOOK_CLIMAX (1.5-2.4s cut BEFORE the punchline)."
        )
        scout_out = call_gemini(api_key, scout_prompt, temperature=0.25, json_mode=False)
        try:
            with open(scout_cache_path, "w", encoding="utf-8") as f:
                json.dump({"index_mtime": idx_mtime, "scout_out": scout_out}, f, indent=2)
        except Exception:
            pass
    t_scout = time.time() - t_s0

    # Build Director Prompt
    schema_ex = (
        '{"clips":[{"clip_number":1,"narrative_archetype":"IN_MEDIA_RES_FLASHFORWARD",'
        '"title":"Wait... They Banned Me?! 😱","hook_caption":"WAIT WHAT HAPPENED?!",'
        '"theme":"Core theme","start_time":6770.0,"end_time":6817.0,"payoff_time":6808.0,'
        '"segments":[{"start":6782.1,"end":6784.4,"role":"HOOK_CLIMAX"},{"start":6765.0,"end":6776.5,"role":"SETUP"},{"start":6785.0,"end":6796.0,"role":"ESCALATION"},{"start":6798.5,"end":6816.6,"role":"PAYOFF"}],'
        '"assembled_spoken_script":"Exact stitched spoken narrative...","signal_justification":{"chat_burst":"Z=2.41 sigma at 6797.5s","db_spike":"+8.0dB vocal peak","face_emotion":"Active shock reaction"},'
        '"cause_and_effect_setup":"Why a cold viewer laughs/is shocked within 3s"}]}'
    )

    director_prompt = (
        "SYSTEM: You are the #1 Elite YouTube Shorts Creative Director & Scriptwriter.\n"
        "Turn the scouted multimodal moments below into 5 diverse, viral, non-linear YouTube Shorts EDLs using exact float-second VOD timestamps.\n\n"
        "=== 5 VIRAL NARRATIVE MODELS (ONE DISTINCT MODEL PER CLIP) ===\n"
        "• IN_MEDIA_RES_FLASHFORWARD (REQUIRED: segments[0].role MUST be \"HOOK_CLIMAX\"): 1.8-2.4s HOOK_CLIMAX tease (MUST stop BEFORE speaking the punchline!) -> SETUP (6-12s earlier) -> ESCALATION (5-10s) -> PAYOFF (5-10s).\n"
        "• DOUBLE_DOWN_ESCALATION: SETUP (6-12s) -> jump-cut past dead air (+10s to +35s or callback minutes later) -> ESCALATION (5-10s) -> bigger PAYOFF (5-10s).\n"
        "• HUBRIS_INSTANT_KARMA: Confident claim/boast SETUP (6-10s) -> ESCALATION -> instant failure/roast PAYOFF (5-10s).\n"
        "• MYSTERY_OPEN_LOOP (REQUIRED: segments[0].role MUST be \"HOOK_CLIMAX\"): Intriguing question HOOK_CLIMAX (1.8-2.5s, NO answer spoiled!) -> SETUP clues (6-10s) -> ESCALATION -> twist reveal PAYOFF (5-10s).\n"
        "• REVERSE_PAYOFF_LOOP: SETUP (6-10s) -> ESCALATION (5-8s) -> PAYOFF (5-8s) whose final words loop smoothly back into SETUP's 0:00 opening words (ALWAYS put SETUP before PAYOFF!).\n\n"
        "=== CRITICAL ANTI-SPOILER, NON-OVERLAP & RETENTION RULES ===\n"
        "1. ZERO SPOILERS IN 0:00-0:03 HOOK: Frame 0:00-0:02.5 MUST create a curiosity/tension gap and NEVER speak the punchline reveal, twist, or ending joke!\n"
        "2. ZERO OVERLAPPING TIMESTAMPS: SETUP, ESCALATION, and PAYOFF MUST have strictly non-overlapping timestamps (`SETUP.end < ESCALATION.start < PAYOFF.start`). Never repeat the exact same lines in two segments!\n"
        "3. FULL SENTENCES & ZERO GIVEAWAY/SUPERCHAT SPAM: Start segments at clean sentence beginnings (`[start_s - end_s]` lines from anchors). Strictly REJECT 'thank you for the super chat', 'every giveaway', 'stops the bots', or giveaway entry spam.\n"
        "4. DISTINCT SCENES (>= 120s APART): Each of the 5 Shorts MUST cover a completely different event across the 1+ hour stream (minimum 120 seconds between clip centers). Never reuse the same scene twice!\n"
        "5. REAL CLIP DURATION: Each Short MUST total 16s to 38s across segments[]. Only use timestamps grounded in the anchors/transcript below.\n"
        "6. Return STRICT VALID JSON ONLY matching:\n" + schema_ex + "\n\n"
        f"=== PROVEN ANCHORS & FLOAT-SECOND CONTEXT ===\n{anchors_text[:18000]}\n\n"
        f"=== SCOUT CANDIDATES ===\n{scout_out}"
    )

    t_d0 = time.time()
    director_raw = call_gemini(api_key, director_prompt, temperature=0.15, json_mode=True)
    t_director = time.time() - t_d0

    cleaned = re.sub(r"```json|```", "", director_raw, flags=re.I).strip()
    parsed = json.loads(cleaned)
    clips = parsed.get("clips") if isinstance(parsed, dict) else parsed

    previews = [splice_clip_edl(c, words) for c in (clips or [])]
    total_elapsed = round(time.time() - t_start, 2)

    result = {
        "dry_run": True,
        "scout_cached": scout_cached,
        "execution_time_sec": total_elapsed,
        "timings_sec": {
            "load_cached_telemetry": round(t_load, 2),
            "scout_gemini": round(t_scout, 2),
            "director_gemini": round(t_director, 2),
        },
        "stream_duration_sec": index_doc.get("stream_duration_sec"),
        "clips_count": len(previews),
        "previews": previews,
    }
    audit = audit_sandbox_edl(result, index_doc)
    result["goal_audit"] = audit

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    cache_tag = " [Scout Cache Hit]" if scout_cached else ""
    print(f"\n==================================================================")
    print(f"SCRIPT SANDBOX DRY-RUN COMPLETE in {total_elapsed}s "
          f"(Load={t_load:.2f}s | Scout={t_scout:.2f}s{cache_tag} | Director={t_director:.2f}s)")
    print(f"Stream Duration: {index_doc.get('stream_duration_sec')}s | Shorts Generated: {len(previews)} | Audit: {audit['status']}")
    print(f"Saved Preview JSON: {output_path}")
    print(f"==================================================================\n")

    for p in previews:
        print(f"[CLIP #{p['clip_number']}] Archetype: {p['narrative_archetype']} | Title: {p['title']} | Hook: \"{p['hook_caption']}\" | Dur: {p['total_duration_sec']}s")
        print(f"  Signals : {json.dumps(p['signal_justification'])}")
        print(f"  Script  : {p['verbatim_word_spliced_script'][:240]}...")
        for s in p["edl_segments"]:
            print(f"    - #{s['segment_order']} [{s['role']:12s}] {s['start_tc']} -> {s['end_tc']} ({s['duration']}s): \"{s['spoken_text'][:90]}\"")
        print()

    print("=== [GOAL CRITERIA AUDIT] ===")
    for chk, detail in audit["checks"].items():
        print(f"  - {chk}: {'PASS' if detail['passed'] else 'FAIL'} ({detail['detail']})")

    return result


def audit_sandbox_edl(result: dict, index_doc: dict) -> dict:
    """Deterministic validator for all /goal Sandbox EDL quality & anti-spoiler criteria."""
    previews = result.get("previews") or []
    anchors = index_doc.get("anchors") or []
    anchor_times = [float(a.get("peak_time", 0.0)) for a in anchors] + [float(a.get("start", 0.0)) for a in anchors]

    archetypes = {p.get("narrative_archetype") for p in previews if p.get("narrative_archetype")}
    c1_pass = 4 <= len(previews) <= 5 and len(archetypes) >= 3

    spoiler_issues = []
    overlap_issues = []
    anchor_issues = []
    dur_issues = []
    distinct_issues = []
    clip_centers = []

    for p in previews:
        cid = p.get("clip_number")
        segs = p.get("edl_segments") or []
        dur = float(p.get("total_duration_sec", 0.0))
        if dur < 14.0 or dur > 44.0:
            dur_issues.append(f"Clip #{cid} dur={dur}s outside [14s,44s]")

        if not segs:
            anchor_issues.append(f"Clip #{cid} has 0 segments")
            continue

        body = [s for s in segs if not (s.get("segment_order") == 0 and s.get("role") == "HOOK_CLIMAX")]
        center_t = body[-1]["start"] if body else segs[-1]["start"]
        for prev_cid, prev_t in clip_centers:
            if abs(center_t - prev_t) < 90.0:
                distinct_issues.append(f"Clip #{cid} ({center_t:.1f}s) too close to Clip #{prev_cid} ({prev_t:.1f}s)")
        clip_centers.append((cid, center_t))

        # Criterion 2: Anti-spoiler check on 0:00-0:03 hook vs closing payoff tokens
        s0 = segs[0]
        if s0.get("role") == "HOOK_CLIMAX" and float(s0.get("duration", 0.0)) > 3.1:
            spoiler_issues.append(f"Clip #{cid} HOOK_CLIMAX {s0['duration']}s > 3.1s")

        # Token overlap between opening segment (<=3s) and final segment (PAYOFF)
        if len(segs) >= 2:
            open_toks = {w for w in re.findall(r"[a-z]{4,}", s0.get("spoken_text", "").lower())}
            pay_toks = {w for w in re.findall(r"[a-z]{4,}", segs[-1].get("spoken_text", "").lower())}
            if open_toks and pay_toks:
                overlap_ratio = len(open_toks & pay_toks) / max(1, len(open_toks))
                if overlap_ratio >= 0.65:
                    spoiler_issues.append(f"Clip #{cid} opening 0:00 overlaps {overlap_ratio:.0%} with final payoff")

        # Criterion 3a: Non-hook segments must have zero timestamp overlap
        for i in range(len(body)):
            for j in range(i + 1, len(body)):
                if body[i]["start"] < body[j]["end"] - 0.05 and body[i]["end"] > body[j]["start"] + 0.05:
                    overlap_issues.append(f"Clip #{cid} body segs #{body[i]['segment_order']} & #{body[j]['segment_order']} overlap")

        # Criterion 3b: Every segment has spoken text and at least one segment is within <=75s of an indexed anchor
        empty_segs = [s["segment_order"] for s in segs if not s.get("spoken_text")]
        if empty_segs:
            anchor_issues.append(f"Clip #{cid} empty Whisper words on segs {empty_segs}")
        if anchor_times:
            best_dist = min(abs(s["start"] - at) for s in segs for at in anchor_times)
            if best_dist > 75.0:
                anchor_issues.append(f"Clip #{cid} min dist {best_dist:.1f}s > 75s from indexed anchors")

    checks = {
        "clip_count_and_archetype_diversity": {
            "passed": c1_pass,
            "detail": f"{len(previews)} clips, {len(archetypes)} distinct models: {sorted(archetypes)}",
        },
        "zero_punchline_spoilers_in_hook": {
            "passed": len(spoiler_issues) == 0,
            "detail": "OK" if not spoiler_issues else "; ".join(spoiler_issues),
        },
        "zero_segment_overlaps": {
            "passed": len(overlap_issues) == 0,
            "detail": "OK" if not overlap_issues else "; ".join(overlap_issues),
        },
        "distinct_stream_moments": {
            "passed": len(distinct_issues) == 0,
            "detail": "OK" if not distinct_issues else "; ".join(distinct_issues),
        },
        "whisper_and_anchor_grounding": {
            "passed": len(anchor_issues) == 0,
            "detail": "OK" if not anchor_issues else "; ".join(anchor_issues),
        },
        "target_shorts_duration_14s_44s": {
            "passed": len(dur_issues) == 0,
            "detail": "OK" if not dur_issues else "; ".join(dur_issues),
        },
    }
    all_ok = all(c["passed"] for c in checks.values())
    return {"status": "PASS" if all_ok else "NEEDS_ITERATION", "all_passed": all_ok, "checks": checks}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full-scout"]
    full_flag = "--full-scout" in sys.argv[1:]
    tx_arg = args[0] if args else None
    run_sandbox(tx_arg, full_scout=full_flag)
