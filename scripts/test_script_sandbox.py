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
    env_model = os.environ.get("SANDBOX_GEMINI_MODEL", "").strip()
    candidates = [env_model] if env_model else []
    for m in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"]:
        if m not in candidates:
            candidates.append(m)

    gen_cfg = {
        "temperature": temperature,
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }).encode("utf-8")

    last_err = None
    for model in candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(2):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as he:
                last_err = he
                if he.code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except Exception as ex:
                last_err = ex
                time.sleep(1.0)
                continue
    raise RuntimeError(f"All Gemini models failed: {last_err}")


def _find_word_bounds(words: list, st: float, en: float):
    first_i, last_i = None, None
    for i, w in enumerate(words):
        ws = float(w.get("start", 0.0))
        we = float(w.get("end", ws))
        mid = (ws + we) * 0.5
        if st - 0.01 <= mid <= en + 0.01:
            if first_i is None:
                first_i = i
            last_i = i
    return first_i, last_i


def snap_segment_to_sentences(words: list, st: float, en: float, role: str, min_st: float = 3.0, max_en: float = 1e9):
    """Snap segment boundaries cleanly between Whisper words at full sentence starts/ends."""
    if not words:
        return max(min_st, st), min(max_en, en)
    if role == "HOOK_CLIMAX":
        st_c, en_c = max(min_st, st), min(max_en, en)
        fi, li = _find_word_bounds(words, st_c, en_c)
        if fi is not None and li is not None and not re.search(r"[.!?]$", str(words[li].get("word", "")).strip()):
            for j in range(li, fi - 1, -1):
                we_j = float(words[j].get("end", en_c))
                if re.search(r"[.!?]$", str(words[j].get("word", "")).strip()) and (we_j - st_c) >= 0.9:
                    nxt_st = float(words[j + 1].get("start", we_j + 0.5)) if j + 1 < len(words) else we_j + 0.5
                    en_c = min(en_c, nxt_st - 0.02, we_j + 0.10)
                    break
        return st_c, max(st_c + 0.8, en_c)

    first_i, last_i = _find_word_bounds(words, st, en)
    if first_i is None:
        return max(min_st, st), min(max_en, en)

    # Drop orphan sentence-ending token at word[first_i] (e.g. trailing 'plus.' or 'that.')
    if first_i > 0 and first_i + 1 < len(words):
        first_tok = str(words[first_i].get("word", "")).strip()
        prev_tok_0 = str(words[first_i - 1].get("word", "")).strip()
        if re.search(r"[.!?]$", first_tok) and not re.search(r"[.!?]$", prev_tok_0):
            first_mid = (float(words[first_i].get("start", st)) + float(words[first_i].get("end", st))) * 0.5
            # Advance to the first subsequent word whose midpoint is strictly after first_mid (or next sentence boundary)
            moved = False
            for k in range(first_i + 1, min(len(words), first_i + 12)):
                cand_mid = (float(words[k].get("start", st)) + float(words[k].get("end", st))) * 0.5
                prev_k = str(words[k - 1].get("word", "")).strip()
                if cand_mid > first_mid + 0.01 and re.search(r"[.!?]$", prev_k) and (en - float(words[k].get("start", st))) >= 1.5:
                    st = max(min_st, first_mid + 0.02, float(words[k].get("start", st)) - 0.04)
                    first_i = k
                    moved = True
                    break
            if not moved:
                for k in range(first_i + 1, min(len(words), first_i + 18)):
                    prev_k = str(words[k - 1].get("word", "")).strip()
                    ws_k = float(words[k].get("start", st))
                    if re.search(r"[.!?]$", prev_k) and ws_k > first_mid and (en - ws_k) >= 1.5:
                        st = max(min_st, float(words[k - 1].get("end", 0.0)) + 0.02, ws_k - 0.04)
                        first_i = k
                        break

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
                    prev_mid = (float(words[j - 1].get("start", 0.0)) + prev_end) * 0.5 if j > 0 else 0.0
                    curr_mid = (ws_j + float(words[j].get("end", ws_j))) * 0.5
                    clean_cut = max(prev_end + 0.02, ws_j - 0.06) if prev_end <= ws_j else min(ws_j - 0.02, (prev_mid + curr_mid) * 0.5)
                    st = max(min_st, clean_cut)
                    snapped = True
                    break
            if not snapped:
                for j in range(first_i + 1, min(len(words), first_i + 12)):
                    prev_j = str(words[j - 1].get("word", "")).strip()
                    ws_j = float(words[j].get("start", st))
                    if re.search(r"[.!?]$", prev_j) and (en - ws_j) >= 2.2:
                        prev_end = float(words[j - 1].get("end", 0.0))
                        prev_mid = (float(words[j - 1].get("start", 0.0)) + prev_end) * 0.5
                        curr_mid = (ws_j + float(words[j].get("end", ws_j))) * 0.5
                        clean_cut = max(prev_end + 0.02, ws_j - 0.06) if prev_end <= ws_j else min(ws_j - 0.02, (prev_mid + curr_mid) * 0.5)
                        st = max(min_st, clean_cut)
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


def _normalize_role(role_str: str) -> str:
    r = str(role_str or "").upper().strip()
    if r in ("HOOK_CLIMAX", "HOOK", "FLASH_FORWARD", "COLD_OPEN"):
        return "HOOK_CLIMAX"
    if r in ("SETUP", "SETUP_HOOK", "STAKES", "REWIND_SETUP"):
        return "SETUP"
    if r in ("ESCALATION", "ACTION_BRIDGE", "STRUGGLE", "BUILDUP"):
        return "ESCALATION"
    if r in ("PAYOFF", "PAYOFF_CLIMAX", "CLIMAX", "REACTION", "REVEAL"):
        return "PAYOFF"
    return "STORY_BEAT"


def splice_clip_edl(clip: dict, words: list) -> dict:
    """Mirrors 5. Split Clips + 6. Extract Viral Segments + DRY_RUN_SCRIPT_ONLY logic."""
    buf = 0.10
    raw_segs = []
    for s in clip.get("segments") or []:
        try:
            st = max(3.0, float(s["start"]))
            en = max(st + 0.8, float(s["end"]))
            raw_segs.append({
                "start": st,
                "end": en,
                "role": _normalize_role(s.get("role")),
            })
        except Exception:
            pass

    if not raw_segs:
        st = max(3.0, float(clip.get("start_time") or 3.0))
        en = max(st + 18.0, float(clip.get("end_time") or st + 34.0))
        span = en - st
        raw_segs = [
            {"start": round(st, 2), "end": round(st + span * 0.33, 2), "role": "SETUP"},
            {"start": round(st + span * 0.33 + 0.15, 2), "end": round(st + span * 0.67, 2), "role": "ESCALATION"},
            {"start": round(st + span * 0.67 + 0.15, 2), "end": round(en, 2), "role": "PAYOFF"},
        ]

    # Separate optional 0:00 HOOK_CLIMAX flash-forward teaser from chronological body segments
    hook_seg = None
    body_raw = []
    for i, s in enumerate(raw_segs):
        if i == 0 and s["role"] == "HOOK_CLIMAX":
            st_h = s["start"]
            en_h = min(s["end"], st_h + 2.6)
            _, en_h = snap_segment_to_sentences(words, st_h, en_h, "HOOK_CLIMAX", min_st=3.0, max_en=st_h + 2.6)
            s["end"] = round(en_h, 2)
            hook_seg = s
        else:
            body_raw.append(s)

    # Sort body segments chronologically and de-overlap cleanly without chopping next sentence's first word
    body_raw.sort(key=lambda x: x["start"])
    body_norm = []
    for s in body_raw:
        st, en, role = s["start"], s["end"], s["role"]
        if body_norm and st < body_norm[-1]["end"] + 0.02:
            st = body_norm[-1]["end"] + 0.02
        if en - st >= 1.2:
            body_norm.append({"start": round(st, 2), "end": round(en, 2), "role": role})

    # Ensure every clip populates SETUP -> ESCALATION -> PAYOFF
    if len(body_norm) == 1:
        b = body_norm[0]
        sp = b["end"] - b["start"]
        body_norm = [
            {"start": round(b["start"], 2), "end": round(b["start"] + sp * 0.33, 2), "role": "SETUP"},
            {"start": round(b["start"] + sp * 0.33 + 0.05, 2), "end": round(b["start"] + sp * 0.67, 2), "role": "ESCALATION"},
            {"start": round(b["start"] + sp * 0.67 + 0.05, 2), "end": round(b["end"], 2), "role": "PAYOFF"},
        ]
    elif len(body_norm) == 2:
        d0 = body_norm[0]["end"] - body_norm[0]["start"]
        d1 = body_norm[1]["end"] - body_norm[1]["start"]
        if d0 >= d1 and d0 >= 5.0:
            mid = round(body_norm[0]["start"] + d0 * 0.5, 2)
            body_norm = [
                {"start": body_norm[0]["start"], "end": mid, "role": "SETUP"},
                {"start": round(mid + 0.05, 2), "end": body_norm[0]["end"], "role": "ESCALATION"},
                {"start": body_norm[1]["start"], "end": body_norm[1]["end"], "role": "PAYOFF"},
            ]
        elif d1 >= 5.0:
            mid = round(body_norm[1]["start"] + d1 * 0.5, 2)
            body_norm = [
                {"start": body_norm[0]["start"], "end": body_norm[0]["end"], "role": "SETUP"},
                {"start": body_norm[1]["start"], "end": mid, "role": "ESCALATION"},
                {"start": round(mid + 0.05, 2), "end": body_norm[1]["end"], "role": "PAYOFF"},
            ]

    if len(body_norm) >= 3:
        body_norm[0]["role"] = "SETUP"
        for k in range(1, len(body_norm) - 1):
            body_norm[k]["role"] = "ESCALATION"
        body_norm[-1]["role"] = "PAYOFF"

    # Snap body segments cleanly to full Whisper sentence boundaries
    for idx_b, b in enumerate(body_norm):
        min_st = 3.0 if idx_b == 0 else body_norm[idx_b - 1]["end"] + 0.02
        max_en = (body_norm[idx_b + 1]["start"] - 0.02) if idx_b + 1 < len(body_norm) else (b["end"] + 2.5)
        if max_en > min_st + 1.0:
            s_st, s_en = snap_segment_to_sentences(words, b["start"], b["end"], b["role"], min_st=min_st, max_en=max_en)
            b["start"], b["end"] = round(s_st, 2), round(s_en, 2)

    body_dur = sum(b["end"] - b["start"] for b in body_norm)
    use_hook = hook_seg is not None and body_dur >= 27.5
    raw_segs = ([hook_seg] + body_norm) if use_hook else list(body_norm)

    def _split_pauses(segs_in):
        out_segs = []
        for interval in segs_in:
            role = interval["role"]
            start = interval["start"]
            int_end = interval["end"]
            clip_words = _words_in_range(words, start, int_end)
            if clip_words:
                w_first_st = float(clip_words[0]["start"])
                w_last_en = float(clip_words[-1]["end"])
                first_g, last_g = _find_word_bounds(words, start, int_end)
                prev_en = float(words[first_g - 1]["end"]) if (first_g is not None and first_g > 0) else 0.0
                prev_mid = (float(words[first_g - 1]["start"]) + prev_en) * 0.5 if (first_g is not None and first_g > 0) else 0.0
                w_first_mid = (w_first_st + float(clip_words[0]["end"])) * 0.5
                clean_st = max(prev_en + 0.02, w_first_st - buf) if prev_en <= w_first_st else min(w_first_st - 0.02, (prev_mid + w_first_mid) * 0.5)
                nxt_st = float(words[last_g + 1]["start"]) if (last_g is not None and last_g + 1 < len(words)) else (w_last_en + 1.0)
                seg_st = max(start, clean_st)
                seg_en = min(int_end, nxt_st - 0.02, w_last_en + buf)

                curr_start = seg_st
                last_end = float(clip_words[0]["end"])
                role_segs = []
                for w_idx_i in range(1, len(clip_words)):
                    w = clip_words[w_idx_i]
                    prev_w_txt = str(clip_words[w_idx_i - 1].get("word", "")).strip()
                    ws, we = float(w["start"]), float(w["end"])
                    gap = ws - last_end
                    if gap > 1.40 or (gap > 0.85 and re.search(r"[.!?]$", prev_w_txt)):
                        sub_en = min(last_end + buf, ws - 0.02)
                        if sub_en - curr_start >= 0.6:
                            role_segs.append({"role": role, "start": curr_start, "end": sub_en})
                            curr_start = max(last_end + buf, ws - 0.06)
                    last_end = we
                if seg_en - curr_start >= 0.45:
                    role_segs.append({"role": role, "start": curr_start, "end": seg_en})
                for rs in role_segs:
                    sw = _words_in_range(words, rs["start"], rs["end"])
                    stext = " ".join(str(w.get("word", "")).strip() for w in sw)
                    if len(role_segs) > 1 and HOUSEKEEPING_NOISE.search(stext):
                        continue
                    if sw:
                        out_segs.append(rs)
            else:
                out_segs.append({"role": role, "start": start, "end": int_end})
        return out_segs

    final_segs = _split_pauses(raw_segs)
    tot = sum(s["end"] - s["start"] for s in final_segs)

    # Expand cleanly on sentence boundaries if post-pause duration < 30.0s (up to 3 passes to account for internal pauses)
    for _pass in range(3):
        if tot >= 30.0 or not body_norm:
            break
        deficit = 30.8 - tot
        if body_norm[0]["start"] > 3.5 and deficit > 0:
            step_back = min(max(6.0, deficit * 2.0), 14.0)
            cand_st = max(3.0, body_norm[0]["start"] - step_back)
            max_b0 = body_norm[1]["start"] - 0.02 if len(body_norm) > 1 else body_norm[0]["end"]
            s_st, s_en = snap_segment_to_sentences(words, cand_st, body_norm[0]["end"], "SETUP", min_st=3.0, max_en=max_b0)
            body_norm[0]["start"], body_norm[0]["end"] = round(s_st, 2), round(s_en, 2)
        for idx_b, b in enumerate(body_norm):
            max_next = (body_norm[idx_b + 1]["start"] - 0.02) if idx_b + 1 < len(body_norm) else (b["end"] + 2.5)
            gap_next = max(0.0, max_next - b["end"])
            if gap_next > 0.5:
                add = min(max(4.0, deficit * 1.5), gap_next, 12.0 if idx_b + 1 < len(body_norm) else 2.5)
                min_b = 3.0 if idx_b == 0 else body_norm[idx_b - 1]["end"] + 0.02
                s_st, s_en = snap_segment_to_sentences(words, b["start"], b["end"] + add, b["role"], min_st=min_b, max_en=max_next)
                b["start"], b["end"] = round(s_st, 2), round(s_en, 2)
            if idx_b > 0:
                min_prev = body_norm[idx_b - 1]["end"] + 0.02
                gap_prev = max(0.0, b["start"] - min_prev)
                if gap_prev > 0.5:
                    back = min(max(4.0, deficit * 1.5), gap_prev, 10.0)
                    s_st, s_en = snap_segment_to_sentences(words, b["start"] - back, b["end"], b["role"], min_st=min_prev, max_en=max_next)
                    b["start"], b["end"] = round(s_st, 2), round(s_en, 2)
        body_dur = sum(b["end"] - b["start"] for b in body_norm)
        use_hook = hook_seg is not None and body_dur >= 27.5
        raw_segs = ([hook_seg] + body_norm) if use_hook else list(body_norm)
        final_segs = _split_pauses(raw_segs)
        tot = sum(s["end"] - s["start"] for s in final_segs)

    # Trim cleanly at sentence boundaries (never proportional chopping!) if total duration > 45.0s
    for _trim_pass in range(2):
        if tot <= 45.0 or not body_norm:
            break
        excess = tot - 43.5
        for idx_b, _ in sorted(enumerate(body_norm), key=lambda kv: kv[1]["end"] - kv[1]["start"], reverse=True):
            if excess <= 0.1:
                break
            b = body_norm[idx_b]
            dur_b = b["end"] - b["start"]
            if dur_b > 6.5:
                cut = min(excess, dur_b - 6.5)
                min_b = 3.0 if idx_b == 0 else body_norm[idx_b - 1]["end"] + 0.02
                target_end = max(min_b + 4.0, b["end"] - cut)
                s_st, s_en = snap_segment_to_sentences(words, b["start"], target_end, b["role"], min_st=min_b, max_en=target_end + 0.2)
                reduced = max(0.0, b["end"] - s_en)
                if reduced > 0.2:
                    b["end"] = round(s_en, 2)
                    excess -= reduced
        body_dur = sum(b["end"] - b["start"] for b in body_norm)
        use_hook = hook_seg is not None and body_dur >= 27.5
        raw_segs = ([hook_seg] + body_norm) if use_hook else list(body_norm)
        final_segs = _split_pauses(raw_segs)
        tot = sum(s["end"] - s["start"] for s in final_segs)

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
    macro_timeline = index_doc.get("macro_high_signal_timeline", "")[:14000]
    annotated_lines = "\n".join(
        f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}"
        for s in (index_doc.get("annotated_sentences") or [])
    )[:18000]

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
            if (
                abs(float(sc.get("index_mtime", -1.0)) - idx_mtime) < 1.0
                and sc.get("prompt_version") == "multi_arc_v2"
                and sc.get("scout_out")
            ):
                scout_out = sc["scout_out"]
                scout_cached = True
        except Exception:
            pass

    t_s0 = time.time()
    if scout_out is None:
        scout_prompt = (
            "SYSTEM: You are an elite YouTube Shorts Viral Content Scout & Story Architect.\n"
            "STOP extracting isolated, random 15-20s soundbites! Instead, analyze the multimodal anchors and sentence timeline to construct 5 DIVERSE, complete 30-45s multi-segment story arcs across ALL 5 archetypes:\n"
            "1. IN_MEDIA_RES_FLASHFORWARD (Optional 1.8-2.4s HOOK_CLIMAX cut BEFORE punchline -> rewind to SETUP -> ESCALATION -> PAYOFF)\n"
            "2. DOUBLE_DOWN_ESCALATION (SETUP wager/fail 1 -> jump cut past dead air -> ESCALATION double-down -> Bigger Fail/Win PAYOFF)\n"
            "3. HUBRIS_INSTANT_KARMA (Arrogant boast/wager SETUP -> gameplay struggle ESCALATION -> instant collapse + reaction PAYOFF)\n"
            "4. MYSTERY_OPEN_LOOP (Intriguing anomaly/question SETUP or optional HOOK_CLIMAX -> escalating clues ESCALATION -> twist reveal PAYOFF)\n"
            "5. REVERSE_PAYOFF_LOOP (Chronological SETUP -> ESCALATION -> PAYOFF flowing smoothly back into 0:00 SETUP opening words)\n\n"
            "MANDATORY 3-ACT STORY ARC PER CANDIDATE (30-45s TOTAL):\n"
            "• (1) [SETUP / STAKES] (8-14s): The wager, challenge, promise, or boast (e.g., agreeing to 1v1 for the Nicholas Scythe).\n"
            "• (2) [ESCALATION / STRUGGLE] (8-16s): The gameplay action, failure, glitching, or frantic no-hit frustration (strictly after SETUP).\n"
            "• (3) [PAYOFF / REACTION] (8-16s): The victory, confession, scam accusation, or item reveal + reaction (strictly after ESCALATION).\n"
            "• Use exact `[start_s - end_s]` full-sentence boundaries from the transcript/anchors so there are ZERO mid-sentence cuts! Never start before 3.0s.\n"
            "STRICT ANTI-ADMIN FILTER: REJECT superchat thank-you rollcalls, giveaway chat-spam prompts, and boring friend-request searches.\n\n"
            f"=== PROVEN MULTIMODAL VIRAL PEAKS ===\n{anchors_text}\n"
            f"=== SENTENCE TIMELINE ([start_s - end_s]) ===\n{annotated_lines or macro_timeline}\n\n"
            "OUTPUT concise candidate notes using exact float seconds from `[start_s - end_s]` with NON-OVERLAPPING windows for [SETUP / STAKES] (8-14s), [ESCALATION / STRUGGLE] (8-16s), [PAYOFF / REACTION] (8-16s), plus optional non-spoilering HOOK_CLIMAX (1.8-2.4s cut BEFORE the punchline)."
        )
        scout_out = call_gemini(api_key, scout_prompt, temperature=0.25, json_mode=False)
        try:
            with open(scout_cache_path, "w", encoding="utf-8") as f:
                json.dump({"index_mtime": idx_mtime, "prompt_version": "multi_arc_v2", "scout_out": scout_out}, f, indent=2)
        except Exception:
            pass
    t_scout = time.time() - t_s0

    # Build Director Prompt
    schema_ex = (
        '{"clips":[{"clip_number":1,"narrative_archetype":"HUBRIS_INSTANT_KARMA",'
        '"title":"1v1 For The Scythe?! 😱","hook_caption":"1V1 FOR THE SCYTHE?!",'
        '"theme":"Core theme","start_time":53.3,"end_time":453.7,"payoff_time":450.0,'
        '"segments":[{"start":53.3,"end":64.4,"role":"SETUP"},{"start":144.8,"end":160.7,"role":"ESCALATION"},{"start":441.9,"end":453.7,"role":"PAYOFF"}],'
        '"assembled_spoken_script":"Exact stitched spoken narrative...","signal_justification":{"chat_burst":"Z=2.41 sigma","db_spike":"+8.0dB vocal peak","face_emotion":"Active shock reaction"},'
        '"cause_and_effect_setup":"Why a cold viewer follows SETUP -> ESCALATION -> PAYOFF cleanly"}]}'
    )

    director_prompt = (
        "SYSTEM: You are the #1 Elite YouTube Shorts Creative Director & Narrative Architect.\n"
        "STOP extracting isolated, random 20s soundbites! Construct 4 to 5 unified 30s-45s YouTube Shorts by stitching non-sequential moments together into a complete beginning-to-end 3-act story arc.\n\n"
        "=== MANDATORY 3-ACT MULTI-SEGMENT STRUCTURE (EVERY APPROVED SHORT) ===\n"
        "Every Short in clips[] MUST populate segments[] with ALL THREE roles in chronological story order (plus optional leading HOOK_CLIMAX 1.8-2.4s ONLY for Flash-Forward/Mystery if non-spoilering):\n"
        "1. [SETUP / STAKES] (role: \"SETUP\", 8-15s): The wager, challenge, promise, or boast that gives a cold viewer clear stakes.\n"
        "2. [ESCALATION / STRUGGLE] (role: \"ESCALATION\", 8-16s): The gameplay action, failure, glitching, or frantic no-hit frustration (strictly after SETUP, jumping past dead air).\n"
        "3. [PAYOFF / REACTION] (role: \"PAYOFF\", 8-16s): The victory, confession, scam accusation, or item reveal + reaction (strictly after ESCALATION).\n\n"
        "=== 5 VIRAL NARRATIVE MODELS (DIVERSIFY ACROSS CLIPS) ===\n"
        "• IN_MEDIA_RES_FLASHFORWARD: Optional 1.8-2.4s HOOK_CLIMAX tease (MUST stop BEFORE speaking the punchline!) -> SETUP -> ESCALATION -> PAYOFF.\n"
        "• DOUBLE_DOWN_ESCALATION: SETUP -> jump-cut past dead air -> ESCALATION double-down -> bigger PAYOFF.\n"
        "• HUBRIS_INSTANT_KARMA: Confident claim/wager SETUP -> gameplay struggle ESCALATION -> instant consequence/reaction PAYOFF.\n"
        "• MYSTERY_OPEN_LOOP: Optional HOOK_CLIMAX question (NO answer spoiled!) -> SETUP -> ESCALATION clues -> twist reveal PAYOFF.\n"
        "• REVERSE_PAYOFF_LOOP: SETUP -> ESCALATION -> PAYOFF whose final line flows seamlessly back into SETUP's 0:00 opening words.\n\n"
        "=== CRITICAL ANTI-SPOILER, SENTENCE-BOUNDARY & RETENTION RULES ===\n"
        "1. ZERO RANDOM MID-SENTENCE CUTS: Pick EVERY segment's `start` and `end` directly from exact `[start_s - end_s]` full-sentence boundaries in the timeline below (and keep `start >= 3.0`)!\n"
        "2. ZERO SPOILERS IN 0:00-0:03 HOOK: Frame 0:00-0:02.5 MUST create curiosity/stakes and NEVER speak the punchline reveal or ending joke!\n"
        "3. ZERO OVERLAPPING TIMESTAMPS: SETUP, ESCALATION, and PAYOFF MUST have strictly non-overlapping timestamps (`SETUP.end < ESCALATION.start < PAYOFF.start`). Never repeat identical lines!\n"
        "4. DISTINCT CLIMAXES / PAYOFFS (ZERO DUPLICATE ENDINGS): Each of the 5 Shorts MUST have a completely unique PAYOFF segment at least 45s apart (for 1h+ VODs >= 120s apart). NEVER reuse the same PAYOFF moment/ending lines across two different clips (e.g., at most ONE clip may use the 498-502s eBay payoff)!\n"
        "5. UNIFIED 30s-45s DURATION: Sum of segment durations in segments[] MUST be strictly between 30s and 45s (sweet spot 32s-42s). Never copy example numbers!\n"
        "6. Return STRICT VALID JSON ONLY matching:\n" + schema_ex + "\n\n"
        f"=== PROVEN ANCHORS & FLOAT-SECOND CONTEXT ===\n{anchors_text[:14000]}\n\n"
        f"=== EXACT FULL-SENTENCE TIMELINE ([start_s - end_s]) ===\n{annotated_lines or macro_timeline}\n\n"
        f"=== SCOUT CANDIDATES ===\n{scout_out}"
    )

    t_d0 = time.time()
    director_raw = call_gemini(api_key, director_prompt, temperature=0.15, json_mode=True)
    t_director = time.time() - t_d0

    cleaned = re.sub(r"```json|```", "", director_raw, flags=re.I).strip()
    parsed = json.loads(cleaned)
    clips = parsed.get("clips") if isinstance(parsed, dict) else parsed

    raw_previews = [splice_clip_edl(c, words) for c in (clips or [])]
    # Deduplicate overlapping PAYOFFs just like 5. Split Clips
    stream_dur = float(index_doc.get("stream_duration_sec") or 3600.0)
    min_pay_gap = 90.0 if stream_dur > 1200.0 else min(45.0, max(35.0, stream_dur / 12.0))
    previews = []
    for cand in raw_previews:
        c_segs = cand.get("edl_segments") or []
        c_body = [s for s in c_segs if not (s.get("segment_order") == 0 and s.get("role") == "HOOK_CLIMAX")]
        c_pay = [s for s in c_body if s.get("role") == "PAYOFF"]
        cp = c_pay[-1] if c_pay else (c_body[-1] if c_body else None)
        if cp:
            c_mid = (float(cp["start"]) + float(cp["end"])) * 0.5
            clash = False
            for ex in previews:
                e_segs = ex.get("edl_segments") or []
                e_body = [s for s in e_segs if not (s.get("segment_order") == 0 and s.get("role") == "HOOK_CLIMAX")]
                e_pay = [s for s in e_body if s.get("role") == "PAYOFF"]
                ep = e_pay[-1] if e_pay else (e_body[-1] if e_body else None)
                if ep:
                    e_mid = (float(ep["start"]) + float(ep["end"])) * 0.5
                    if abs(c_mid - e_mid) < min_pay_gap:
                        clash = True
                        break
            if clash:
                continue
        previews.append(cand)
    for idx_p, p in enumerate(previews):
        p["clip_number"] = idx_p + 1
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
    audit = audit_sandbox_edl(result, index_doc, words=words)
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


def audit_sandbox_edl(result: dict, index_doc: dict, words: list = None) -> dict:
    """Deterministic validator for Multi-Segment Narrative Arching, 30-45s duration, & zero mid-sentence cuts."""
    previews = result.get("previews") or []
    anchors = index_doc.get("anchors") or []
    anchor_times = [float(a.get("peak_time", 0.0)) for a in anchors] + [float(a.get("start", 0.0)) for a in anchors]
    stream_dur = float(index_doc.get("stream_duration_sec") or 3600.0)
    min_payoff_gap = 90.0 if stream_dur > 1200.0 else min(45.0, max(35.0, stream_dur / 12.0))

    archetypes = {p.get("narrative_archetype") for p in previews if p.get("narrative_archetype")}
    c1_pass = 4 <= len(previews) <= 5 and len(archetypes) >= 3

    spoiler_issues = []
    overlap_issues = []
    anchor_issues = []
    dur_issues = []
    distinct_issues = []
    arc_issues = []
    sentence_issues = []
    payoff_centers = []

    for p in previews:
        cid = p.get("clip_number")
        segs = p.get("edl_segments") or []
        dur = float(p.get("total_duration_sec", 0.0))
        if dur < 29.0 or dur > 45.5:
            dur_issues.append(f"Clip #{cid} dur={dur}s outside [29.0s,45.5s]")

        if not segs:
            anchor_issues.append(f"Clip #{cid} has 0 segments")
            continue

        body = [s for s in segs if not (s.get("segment_order") == 0 and s.get("role") == "HOOK_CLIMAX")]

        # Criterion: Mandatory 3-act Multi-Segment Narrative Arc (SETUP -> ESCALATION -> PAYOFF)
        roles_seq = [s.get("role") for s in body]
        if not ("SETUP" in roles_seq and "ESCALATION" in roles_seq and "PAYOFF" in roles_seq):
            arc_issues.append(f"Clip #{cid} missing 3-act roles (found {roles_seq})")
        else:
            s_idx = roles_seq.index("SETUP")
            e_idx = roles_seq.index("ESCALATION")
            p_idx = len(roles_seq) - 1 - roles_seq[::-1].index("PAYOFF")
            if not (s_idx < e_idx < p_idx):
                arc_issues.append(f"Clip #{cid} bad role order {roles_seq}")

        # Distinct PAYOFF climaxes across clips
        payoff_segs = [s for s in body if s.get("role") == "PAYOFF"]
        p_seg = payoff_segs[-1] if payoff_segs else (body[-1] if body else segs[-1])
        center_t = (float(p_seg["start"]) + float(p_seg["end"])) * 0.5
        for prev_cid, prev_t in payoff_centers:
            if abs(center_t - prev_t) < min_payoff_gap:
                distinct_issues.append(f"Clip #{cid} payoff ({center_t:.1f}s) too close to Clip #{prev_cid} ({prev_t:.1f}s)")
        payoff_centers.append((cid, center_t))

        # Anti-spoiler check on 0:00-0:03 hook vs closing payoff tokens
        s0 = segs[0]
        if s0.get("role") == "HOOK_CLIMAX" and float(s0.get("duration", 0.0)) > 3.1:
            spoiler_issues.append(f"Clip #{cid} HOOK_CLIMAX {s0['duration']}s > 3.1s")

        if len(segs) >= 2:
            open_toks = {w for w in re.findall(r"[a-z]{4,}", s0.get("spoken_text", "").lower())}
            pay_toks = {w for w in re.findall(r"[a-z]{4,}", segs[-1].get("spoken_text", "").lower())}
            if open_toks and pay_toks:
                overlap_ratio = len(open_toks & pay_toks) / max(1, len(open_toks))
                if overlap_ratio >= 0.65:
                    spoiler_issues.append(f"Clip #{cid} opening 0:00 overlaps {overlap_ratio:.0%} with final payoff")

        # Non-hook segments must have zero timestamp overlap
        for i in range(len(body)):
            for j in range(i + 1, len(body)):
                if body[i]["start"] < body[j]["end"] - 0.05 and body[i]["end"] > body[j]["start"] + 0.05:
                    overlap_issues.append(f"Clip #{cid} body segs #{body[i]['segment_order']} & #{body[j]['segment_order']} overlap")

        # Zero mid-sentence cuts on non-hook segments when word list is available
        if words:
            for b in body:
                fi, li = _find_word_bounds(words, float(b["start"]), float(b["end"]))
                if fi is not None and fi > 0:
                    prev_w = str(words[fi - 1].get("word", "")).strip()
                    gap_before = float(words[fi].get("start", 0.0)) - float(words[fi - 1].get("end", 0.0))
                    if not re.search(r"[.!?]$", prev_w) and gap_before < 0.75:
                        sentence_issues.append(f"Clip #{cid} seg #{b['segment_order']} ({b['role']}) starts mid-sentence after '{prev_w}'")
                if li is not None and li + 1 < len(words):
                    last_w = str(words[li].get("word", "")).strip()
                    gap_after = float(words[li + 1].get("start", 0.0)) - float(words[li].get("end", 0.0))
                    if not re.search(r"[.!?]$", last_w) and gap_after < 0.75:
                        sentence_issues.append(f"Clip #{cid} seg #{b['segment_order']} ({b['role']}) ends mid-sentence at '{last_w}'")

        # Every segment has spoken text and at least one segment is within <=75s of an indexed anchor
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
        "three_act_narrative_arc": {
            "passed": len(arc_issues) == 0,
            "detail": "OK" if not arc_issues else "; ".join(arc_issues),
        },
        "zero_mid_sentence_cuts": {
            "passed": len(sentence_issues) == 0,
            "detail": "OK" if not sentence_issues else "; ".join(sentence_issues),
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
        "target_shorts_duration_30s_45s": {
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
