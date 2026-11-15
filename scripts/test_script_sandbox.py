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

from telemetry_fusion_indexer import build_unified_index, format_mmss

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

    # Expand undersized non-hook beats when total raw duration is too short (<16s)
    tot = sum(s["end"] - s["start"] for s in raw_segs)
    if tot < 16.0:
        for s in raw_segs:
            if s["role"] != "HOOK_CLIMAX" and (s["end"] - s["start"]) < 5.5:
                s["end"] = round(s["start"] + 6.0, 2)
        tot = sum(s["end"] - s["start"] for s in raw_segs)

    # Cap total non-linear duration <= 44s
    if len(raw_segs) > 1 and tot > 44.0:
        ratio = 42.0 / tot
        raw_segs = [
            {
                "start": s["start"],
                "end": round(s["start"] + max(1.2, (s["end"] - s["start"]) * ratio), 2),
                "role": s["role"],
            }
            for s in raw_segs
        ]

    final_segs = []
    for idx, interval in enumerate(raw_segs):
        start = interval["start"]
        int_end = interval["end"]
        role = interval["role"]

        clip_words = [w for w in words if float(w.get("end", 0)) >= start and float(w.get("start", 0)) <= int_end]
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
            curr_start = max(start, float(clip_words[0]["start"]) - 0.10)
            if w_idx > 0 and float(init_w["start"]) > curr_start:
                curr_start = float(init_w["start"]) - 0.08
            last_end = float(init_w["end"])

            for w in clip_words[w_idx + 1:]:
                ws, we = float(w["start"]), float(w["end"])
                if ws - last_end > 0.55:
                    final_segs.append({"role": role, "start": curr_start, "end": last_end + buf})
                    curr_start = max(last_end + buf, ws - buf)
                last_end = we
            final_segs.append({"role": role, "start": curr_start, "end": min(int_end, last_end + buf)})
        else:
            final_segs.append({"role": role, "start": max(0.0, start - buf), "end": int_end + buf})

    edl_segments = []
    tot_dur = 0.0
    for order, seg in enumerate(final_segs):
        st = round(seg["start"], 3)
        en = round(max(st + 0.15, seg["end"]), 3)
        dur = round(en - st, 3)
        tot_dur += dur
        spoken = " ".join(
            str(w.get("word", "")).strip()
            for w in words
            if float(w.get("end", 0)) >= st and float(w.get("start", 0)) <= en
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
            "Analyze the multimodal anchors and timeline index from this 1+ hour livestream and select the top 5 high-retention candidates across distinct archetypes:\n"
            "1. IN_MEDIA_RES_FLASHFORWARD (Peak shock/scream cut 0.3s before punchline -> rewind to setup -> full payoff)\n"
            "2. DOUBLE_DOWN_ESCALATION (Setup/Fail 1 -> jump cut past dead air or across VOD -> Double Down -> Bigger Fail 2)\n"
            "3. HUBRIS_INSTANT_KARMA (Arrogant claim -> 0.5s beat -> instant collapse + stunned reaction)\n"
            "4. MYSTERY_OPEN_LOOP (Weird anomaly/question -> escalating clues -> twist reveal)\n"
            "5. REVERSE_PAYOFF_LOOP (Final truncated line flows grammatically straight into 0:00 opening words)\n\n"
            "REJECT intro music hallucinations, idle lobby banter, and menu browsing.\n\n"
            f"=== PROVEN MULTIMODAL VIRAL PEAKS ===\n{anchors_text}\n"
            f"=== HIGH-SIGNAL TIMELINE INDEX ===\n{macro_timeline}\n\n"
            "OUTPUT concise candidate notes using exact float seconds (e.g. [1912.0 - 1920.5]) for HOOK_CLIMAX, SETUP (6-12s), ESCALATION (5-10s), and PAYOFF (5-10s)."
        )
        scout_out = call_gemini(api_key, scout_prompt, temperature=0.3, json_mode=False)
        try:
            with open(scout_cache_path, "w", encoding="utf-8") as f:
                json.dump({"index_mtime": idx_mtime, "scout_out": scout_out}, f, indent=2)
        except Exception:
            pass
    t_scout = time.time() - t_s0

    # Build Director Prompt
    schema_ex = (
        '{"clips":[{"clip_number":1,"narrative_archetype":"IN_MEDIA_RES_FLASHFORWARD",'
        '"title":"3-4 Word Curiosity Teaser 💀","hook_caption":"3-5 WORDS IN ALL CAPS",'
        '"theme":"Core theme","start_time":1885.0,"end_time":1918.5,"payoff_time":1914.5,'
        '"segments":[{"start":1912.0,"end":1914.2,"role":"HOOK_CLIMAX"},{"start":1885.0,"end":1895.5,"role":"SETUP"},{"start":1896.0,"end":1905.0,"role":"ESCALATION"},{"start":1910.0,"end":1918.5,"role":"PAYOFF"}],'
        '"assembled_spoken_script":"Exact stitched spoken narrative...","signal_justification":{"chat_burst":"...","db_spike":"...","face_emotion":"..."},'
        '"cause_and_effect_setup":"Why a cold viewer laughs/is shocked within 3s"}]}'
    )

    director_prompt = (
        "SYSTEM: You are the #1 Elite YouTube Shorts Creative Director & Scriptwriter.\n"
        "Turn the scouted multimodal moments below into 5 diverse, viral, non-linear YouTube Shorts EDLs using exact float-second VOD timestamps.\n\n"
        "=== 5 VIRAL NARRATIVE MODELS (ONE PER CLIP, ALL 5 REPRESENTED) ===\n"
        "• IN_MEDIA_RES_FLASHFORWARD: HOOK_CLIMAX at 0:00-0:02.2 (1.8-3.0s, cut 0.3s BEFORE final punchline) -> SETUP (6-12s earlier) -> ESCALATION (5-10s) -> PAYOFF (5-10s).\n"
        "• DOUBLE_DOWN_ESCALATION: SETUP (6-12s) -> jump-cut past dead air (+10s to +35s or callback minutes later) -> ESCALATION (5-10s) -> bigger PAYOFF (5-10s).\n"
        "• HUBRIS_INSTANT_KARMA: Bold claim/boast SETUP (6-10s) -> smash cut -> ESCALATION -> instant punishment + reaction PAYOFF (5-10s).\n"
        "• MYSTERY_OPEN_LOOP: Intriguing anomaly/question HOOK_CLIMAX (2-3s) or SETUP (6-10s) -> ESCALATION clues (5-10s) -> twist PAYOFF (5-10s).\n"
        "• REVERSE_PAYOFF_LOOP: Setup & story where final PAYOFF ends mid-clause leading grammatically straight into 0:00 opening words.\n\n"
        "=== STRICT COLD-VIEWER & SEGMENT DURATION RULES ===\n"
        "1. Zero-Context Cold Viewer: Always include enough SETUP context (6-12s) so a viewer who knows nothing understands why the climax is funny.\n"
        "2. No Spoilers at 0:00: Create an information gap, never reveal the punchline in frame 1.\n"
        "3. Total stitched duration per Short MUST be 18s to 38s across segments[] (HOOK_CLIMAX 1.8-3.0s, SETUP 6-12s, ESCALATION 5-10s, PAYOFF 5-10s). NEVER output 1-second fragments!\n"
        "4. Return STRICT VALID JSON ONLY matching:\n" + schema_ex + "\n\n"
        f"=== PROVEN ANCHORS & FLOAT-SECOND CONTEXT ===\n{anchors_text[:9500]}\n\n"
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

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    cache_tag = " [Scout Cache Hit]" if scout_cached else ""
    print(f"\n==================================================================")
    print(f"SCRIPT SANDBOX DRY-RUN COMPLETE in {total_elapsed}s "
          f"(Load={t_load:.2f}s | Scout={t_scout:.2f}s{cache_tag} | Director={t_director:.2f}s)")
    print(f"Stream Duration: {index_doc.get('stream_duration_sec')}s | Shorts Generated: {len(previews)}")
    print(f"Saved Preview JSON: {output_path}")
    print(f"==================================================================\n")

    for p in previews:
        print(f"[CLIP #{p['clip_number']}] Archetype: {p['narrative_archetype']} | Title: {p['title']} | Hook: \"{p['hook_caption']}\" | Dur: {p['total_duration_sec']}s")
        print(f"  Signals : {json.dumps(p['signal_justification'])}")
        print(f"  Script  : {p['verbatim_word_spliced_script'][:240]}...")
        for s in p["edl_segments"]:
            print(f"    - #{s['segment_order']} [{s['role']:12s}] {s['start_tc']} -> {s['end_tc']} ({s['duration']}s): \"{s['spoken_text'][:90]}\"")
        print()

    return result


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full-scout"]
    full_flag = "--full-scout" in sys.argv[1:]
    tx_arg = args[0] if args else None
    run_sandbox(tx_arg, full_scout=full_flag)
