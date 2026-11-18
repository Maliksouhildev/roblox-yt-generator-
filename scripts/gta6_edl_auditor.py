#!/usr/bin/env python3
"""
Deterministic GTA 6 EDL & Vision Scenario Auditor (/files/gta6_edl_auditor.py)
Grades generated GTA 6 Short scenarios on a strict 0-100 scale across 8 criteria
with zero loopholes, cross-checked against Whisper word timestamps,
unified_timeline_index.json, global_summary.json, and cam_config.json.
"""

import argparse
from bisect import bisect_left
import json
import os
import re
import sys

VALID_GTA6_ARCHETYPES = {
    "OPEN_WORLD_CHAOS_OR_COP_CHASE",
    "LEONIDA_NPC_ENCOUNTER_OR_ROAST",
    "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    "HUBRIS_WAGER_WASTED_KARMA",
    "COMEDIC_BANTER_OR_SARCASM",
    "STORY_CUTSCENE_OR_TWIST_REACTION",
    # Legacy compatible aliases mapped cleanly
    "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
    "VIEWER_OR_CHAT_ROAST_INTERACTION",
    "HUBRIS_WAGER_INSTANT_KARMA",
    "COMEDIC_STORYTELLING_OR_SARCASM",
    "FLASHFORWARD_MYSTERY_INVESTIGATION",
    "EMOTIONAL_SHOCK_OR_BETRAYAL",
}

DANGLING_HOOK_END_RE = re.compile(
    r"\b(TO|A|AN|THE|OF|IN|ON|AT|FOR|WITH|FROM|BY|AND|OR|BUT|IF|IS|ARE|WAS|WERE|"
    r"DO|DOES|DID|NOT|WANT|GOING|HAVE|HAS|MY|YOUR|OUR|THEIR|THIS|THAT|WE'RE|I'M|IT'S|I'VE|WE'VE|YOU'VE|THEY'VE|HE'S|SHE'S|DON'T|DIDN'T|WON'T|CAN'T)\s*[.!?]*$",
    re.I,
)

BANNED_HOOK_RE = re.compile(
    r"^(I CALLED TIME OUT|HE ACTUALLY FELL FOR IT|THAT DOES NOT COUNT|MY WORST BLUNDER|"
    r"MUST WATCH MOMENT|VIRAL MOMENT|NO WORDS|NO AUDIO FOUND|NO TRANSCRIPT|"
    r"UNDEFINED|NULL|ERROR|GAMING MOMENT|WATCH THIS CLIP|CLIP \d+|PEAK MOMENT \d+|GTA6[_ ]PEAK[_ ]CLIP[_ ]\d+)$",
    re.I,
)

ADMIN_MENU_OR_OUTRO_RE = re.compile(
    r"\b(going to say bye|comment\b[^.?!]{0,40}\btomorrow|comment\s+[a-z0-9]{2,12}\s+(?:and we'll|if you)|"
    r"everybody subscribe|hit the like button|smash (?:that |the )?like|"
    r"don'?t forget to subscribe|make sure to subscribe|subscribe to the channel|"
    r"thanks? for watching|peace out everybody|ending the stream|see you next time|"
    r"thank you for the raid|thanks for the raid|welcome raiders)\b",
    re.I,
)

STATIC_UI_EVIDENCE_RE = re.compile(
    r"\b(settings menu|pause menu|esc menu|chrome browser|edge browser|discord window|twitch dashboard|loading screen only|strip club nudity|explicit nsfw)\b",
    re.I,
)

CONTINUITY_STOPWORDS = {
    "about", "after", "again", "already", "also", "always", "another", "around",
    "because", "before", "being", "better", "between", "chat", "chats", "come",
    "could", "didn", "does", "doing", "done", "dont", "dude", "every", "everyone",
    "everything", "first", "from", "fucking", "funny", "game", "getting", "give",
    "going", "gonna", "good", "gotta", "guys", "have", "having", "here", "into",
    "just", "keep", "know", "like", "literally", "little", "look", "looking",
    "make", "maybe", "mean", "more", "most", "much", "need", "never", "nice",
    "nobody", "nothing", "okay", "only", "other", "over", "people", "please",
    "pretty", "really", "right", "said", "saying", "says", "see", "should",
    "some", "someone", "something", "sorry", "start", "still", "stop", "stream",
    "sure", "take", "tell", "thank", "thanks", "that", "their", "them", "then",
    "there", "these", "they", "thing", "things", "think", "this", "those",
    "though", "time", "today", "told", "took", "true", "trying", "wait", "wanna",
    "want", "wanted", "watching", "well", "were", "what", "when", "where", "which",
    "while", "will", "with", "would", "yeah", "your",
}

FILLER_START_RE = re.compile(r"^(and|so|but|then|or|because|though|uh+|um+)\b", re.I)
INCOMPLETE_END_RE = re.compile(
    r"(?:--|—|,|:|\.\.\.|…|\b(?:and|but|so|or|to|the|a|an|if|that|with|for|of|in|on|at|like))\s*$",
    re.I,
)


def _load_json_safe(path: str, default=None):
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _words_in_window(words: list, w_starts: list, t0: float, t1: float) -> list:
    if not words:
        return []
    i = max(0, bisect_left(w_starts, t0 - 1.0))
    out = []
    while i < len(words) and float(words[i].get("start", 0.0)) <= t1:
        ws = float(words[i].get("start", 0.0))
        we = float(words[i].get("end", ws))
        if we >= t0 and ws <= t1:
            out.append(words[i])
        i += 1
    return out


def _extract_rare_entities(text: str) -> set:
    toks = re.findall(r"[a-z0-9']{4,}", (text or "").lower())
    return {t.strip("'") for t in toks if t.strip("'") not in CONTINUITY_STOPWORDS and len(t.strip("'")) >= 4}


def _compute_entity_df(sentences: list) -> tuple[dict, int]:
    df = {}
    total = max(1, len(sentences or []))
    for s in (sentences or []):
        for e in _extract_rare_entities(s.get("text", "")):
            df[e] = df.get(e, 0) + 1
    return df, total


def _extract_z_db_values(tags: list) -> list:
    vals = []
    for tg in tags:
        m = re.search(r"Z=([0-9]+(?:\.[0-9]+)?)", str(tg or ""))
        if m:
            try:
                vals.append(float(m.group(1)))
            except ValueError:
                pass
    return vals


def score_clip(
    clip: dict,
    words: list,
    w_starts: list,
    sentences: list,
    global_summary: dict,
    cam_cfg: dict | None = None,
    entity_df: dict | None = None,
    total_sents: int = 1,
    candidates_by_id: dict | None = None,
) -> dict:
    segs = clip.get("edl_segments") or clip.get("segments") or []
    hook = str(clip.get("final_top_hook_caption") or clip.get("hook_caption") or "").strip()
    arch = str(clip.get("narrative_archetype") or "").strip()
    script_text = str(clip.get("assembled_spoken_script") or "")
    pre_ctx = str(clip.get("pre_hook_context_text") or "").strip()
    post_ctx = str(clip.get("post_payoff_context_text") or "").strip()
    cause_text = str(clip.get("cause_and_effect_setup") or "").strip()
    vis_desc = str(clip.get("visual_event_description") or clip.get("visual_evidence") or "").strip()
    tot_dur = float(
        clip.get("total_duration_sec")
        or sum(max(0.0, float(s.get("end", 0)) - float(s.get("start", 0))) for s in segs)
    )
    cand = (candidates_by_id or {}).get(clip.get("candidate_id")) or {}

    sub = {}
    flags = []
    notes = []

    # 1. Clean Sentence Start / Zero Pre-Hook Spillover (20 pts)
    s1 = 20.0
    if not segs:
        s1 = 0.0
        flags.append("EMPTY_EDL_SEGMENTS")
    else:
        seg0 = segs[0]
        t_start = float(seg0.get("start", 0.0))
        sp0 = str(seg0.get("spoken_text") or "").strip()
        if not sp0 and words:
            seg0_ws = _words_in_window(words, w_starts, t_start, float(seg0.get("end", t_start + 1.0)))
            sp0 = " ".join(str(w.get("word", "")).strip() for w in seg0_ws).strip()

        first_idx = None
        for wi in range(max(0, bisect_left(w_starts, t_start - 1.0)), len(words)):
            ws_i = float(words[wi].get("start", 0.0))
            we_i = float(words[wi].get("end", ws_i))
            if (ws_i + we_i) * 0.5 >= t_start and ws_i <= t_start + 2.5:
                first_idx = wi
                break
        first_w = words[first_idx] if first_idx is not None else None
        prev_w = words[first_idx - 1] if (first_idx is not None and first_idx > 0) else None
        pause_before = (
            max(0.0, float(first_w.get("start", t_start)) - float(prev_w.get("end", 0.0)))
            if (first_w and prev_w)
            else 1.0
        )
        prev_tok = str(prev_w.get("word", "")).strip() if prev_w else (pre_ctx.split()[-1] if pre_ctx else "")
        ends_sent = bool(re.search(r"(?<!\.)[.!?][\"'\)]*$", prev_tok))
        if words and not ends_sent and pause_before < 0.40 and t_start > 3.5:
            s1 -= 10.0
            flags.append("MID_SENTENCE_START")
            notes.append(f"Pre-hook pause {pause_before:.2f}s (<0.40s) after non-terminal '{prev_tok}'")
        if FILLER_START_RE.match(sp0) and (not ends_sent or pause_before < 0.25):
            s1 -= 5.0
            flags.append("FILLER_CONTINUATION_START")
            notes.append(f"Starts on filler continuation '{sp0[:24]}'")
        if re.match(r"^(?:\.\.\.|…)|^[^.!?]{1,36}(?:\.\.\.|…)\s+\S", sp0):
            s1 -= 5.0
            flags.append("DANGLING_ELLIPSIS_OPENER")
            notes.append(f"Ellipsis fragment at clip start '{sp0[:32]}'")
        m_spill = re.match(r"^([^.!?]{1,24}[.!?])\s+\S+", sp0)
        if m_spill and len(m_spill.group(1).split()) <= 3 and (not ends_sent or bool(re.match(r"^[a-z]", sp0))):
            s1 -= 5.0
            flags.append("PRE_HOOK_SPILLOVER_WORDS")
            notes.append(f"Spillover words '{m_spill.group(1)}' at hook start")
    sub["pre_hook_clean"] = max(0.0, round(s1, 2))

    # 2. Complete Climax Resolution & 2.0s-4.5s Aftermath (20 pts)
    s2 = 20.0
    if not segs:
        s2 = 0.0
    else:
        seg_last = segs[-1]
        t_end = float(seg_last.get("end", 0.0))
        sp_last = str(seg_last.get("spoken_text") or "").strip()
        if not sp_last and words:
            last_ws = _words_in_window(words, w_starts, float(seg_last.get("start", 0.0)), t_end)
            sp_last = " ".join(str(w.get("word", "")).strip() for w in last_ws).strip()
        tail_words = [
            w for w in _words_in_window(words, w_starts, max(0.0, t_end - 2.5), t_end + 0.5)
            if (float(w.get("start", 0.0)) + float(w.get("end", w.get("start", 0.0)))) * 0.5 <= t_end
        ]
        last_w = tail_words[-1] if tail_words else None
        last_idx = words.index(last_w) if last_w in words else None
        next_w = words[last_idx + 1] if (last_idx is not None and last_idx + 1 < len(words)) else None
        last_tok = str(last_w.get("word", "")).strip() if last_w else (sp_last.split()[-1] if sp_last.split() else "")
        clean_end = bool(re.search(r"(?<!\.)[.!?][\"'\)]*$", sp_last) or re.search(r"(?<!\.)[.!?][\"'\)]*$", last_tok))
        pause_after = (
            max(0.0, float(next_w.get("start", t_end + 4.0)) - float(last_w.get("end", t_end)))
            if (last_w and next_w)
            else 4.0
        )
        if words and not clean_end and pause_after < 0.40:
            s2 -= 10.0
            flags.append("PREMATURE_PAYOFF_CUTOFF")
            notes.append(f"Mid-clause ending '{sp_last[-30:]}' (pause after={pause_after:.2f}s)")
        if INCOMPLETE_END_RE.search(sp_last):
            s2 -= 6.0
            flags.append("DANGLING_CLIMAX_PHRASE")
            notes.append(f"Incomplete tail phrase '{sp_last[-28:]}'")

        payoff_t = float(clip.get("payoff_time") or cand.get("peak_time") or 0.0)
        if payoff_t <= 0.0:
            last_start = float(seg_last.get("start", 0.0))
            pk_cands = []
            for s in sentences:
                sst = float(s.get("start", 0.0))
                if last_start <= sst <= t_end:
                    if any(k in t for t in (s.get("tags") or []) for k in ("dB_PEAK", "SCREAM", "LAUGH_BURST", "CHAT_BURST")):
                        pk_cands.append(min(float(s.get("end", sst + 1.0)), (sst + float(s.get("end", sst))) * 0.5))
            if pk_cands:
                payoff_t = max(pk_cands)

        if payoff_t > 0.0 and payoff_t <= t_end + 1.0:
            aftermath = t_end - payoff_t
            max_stream_t = float(words[-1].get("end", t_end)) if words else t_end
            near_eof = (max_stream_t - t_end) < 2.0
            if aftermath < 1.8 and not near_eof and not clean_end:
                s2 -= 5.0
                flags.append("INSUFFICIENT_AFTERMATH")
                notes.append(f"Aftermath {aftermath:.2f}s (<2.0s) after payoff t={payoff_t:.1f}s")
            elif aftermath < 1.2 and not near_eof and post_ctx and pause_after < 0.45:
                s2 -= 4.0
                flags.append("INSUFFICIENT_AFTERMATH")
                notes.append(f"Short aftermath {aftermath:.2f}s before post_payoff speech")
    sub["payoff_completion"] = max(0.0, round(s2, 2))

    # 3. Scene & Entity Continuity (15 pts)
    s3 = 15.0
    if len(cause_text) < 20:
        s3 = 0.0
        flags.append("MISSING_CAUSE_AND_EFFECT_SETUP")
        notes.append(f"cause_and_effect_setup < 20 chars ({len(cause_text)})")
    elif len(segs) >= 2:
        ec = clip.get("entity_continuity_check") or {}
        if ec.get("passed") is False:
            s3 = 0.0
            flags.append("FRANKENSTEIN_MISMATCH")
        else:
            max_gap = max(
                float(segs[i + 1].get("start", 0.0)) - float(segs[i].get("end", 0.0))
                for i in range(len(segs) - 1)
            )
            e0 = _extract_rare_entities(segs[0].get("spoken_text", ""))
            e1 = _extract_rare_entities(segs[-1].get("spoken_text", ""))
            if max_gap > 180.0:
                s3 = 0.0
                flags.append("FRANKENSTEIN_MISMATCH")
                notes.append(f"Gap {max_gap:.1f}s exceeds 180s max")
            elif max_gap > 45.0:
                rare = [
                    e for e in (e0 & e1)
                    if entity_df and (entity_df.get(e, 0) / float(max(1, total_sents))) < 0.05
                ]
                if not rare:
                    s3 = 0.0
                    flags.append("FRANKENSTEIN_MISMATCH")
                    notes.append(f"Gap {max_gap:.1f}s >45s without rare concrete entity (<5% DF)")
            elif max_gap > 25.0 and len(e0 & e1) == 0:
                s3 = 0.0
                flags.append("FRANKENSTEIN_MISMATCH")
                notes.append(f"Gap {max_gap:.1f}s >25s with zero concrete entity overlap")
    sub["entity_continuity"] = max(0.0, round(s3, 2))

    # 4. Visually Grounded, Non-Dangling Hook Caption (10 pts)
    s4 = 10.0
    corpus = " ".join([
        str(global_summary.get("game") or ""),
        str(global_summary.get("global_summary") or global_summary.get("summary") or ""),
        script_text,
        str(clip.get("title") or ""),
        vis_desc,
    ]).lower()
    if not hook or BANNED_HOOK_RE.match(hook):
        s4 = 0.0
        flags.append("BANNED_OR_EMPTY_CAPTION")
    else:
        wc = len(hook.split())
        if hook != hook.upper():
            s4 -= 3.0
            flags.append("HOOK_NOT_ALL_CAPS")
        if wc < 3 or wc > 6:
            s4 -= 3.0
            flags.append("HOOK_WORD_COUNT_OFF")
        if len(hook) > 32:
            s4 -= 2.0
            flags.append("HOOK_TOO_LONG_CHARS")
        if re.match(r"^(BECAUSE|AND|SO|BUT|THEN|OR)\b", hook, re.I):
            s4 -= 3.0
            flags.append("HOOK_STARTS_WITH_FILLER")
            notes.append(f"Hook '{hook}' starts with weak continuation word")
        if DANGLING_HOOK_END_RE.search(hook):
            s4 -= 5.0
            flags.append("DANGLING_HOOK_END")
            notes.append(f"Hook '{hook}' ends with dangling word")
        content_toks = [
            w for w in re.findall(r"[a-z0-9]{4,}", hook.lower())
            if w not in {"what", "when", "why", "this", "that", "wild", "crazy", "insane"}
        ]
        if content_toks and all(tok[:4] not in corpus for tok in content_toks):
            s4 -= 4.0
            flags.append("UNGROUNDED_HOOK_NOUNS")
            notes.append(f"Hook tokens {content_toks} ungrounded in visual/transcript corpus")
        if not vis_desc and not clip.get("visual_evidence"):
            s4 -= 1.5
            flags.append("MISSING_VISUAL_GROUNDING")
    sub["hook_visual_grounding"] = max(0.0, round(s4, 2))

    # 5. Empirical Multimodal Signal Grounding (10 pts)
    s5 = 10.0
    sig_tags = []
    for seg in segs:
        sig_tags.extend(seg.get("signal_tags_in_window") or [])
    for seg in segs:
        st0 = float(seg.get("start", 0.0))
        en0 = float(seg.get("end", 0.0))
        for s in sentences:
            if float(s.get("end", 0.0)) >= st0 - 0.5 and float(s.get("start", 0.0)) <= en0 + 0.5:
                sig_tags.extend(s.get("tags") or [])
    tag_set = set(sig_tags)
    z_vals = _extract_z_db_values(tag_set)
    cand_z = max([float(cand.get("z_db", 0.0)), float(cand.get("z_chat_lagged", 0.0)), float(cand.get("z_face", 0.0))] + z_vals)
    has_strong_signal = (
        max(z_vals + [float(cand.get("z_db", 0.0))]) >= 2.2
        or any(any(k in t for k in ("dB_PEAK", "SCREAM", "WPM_SPIKE", "FACE:", "CHAT_BURST", "LAUGH_BURST", "CHAT_QUESTION_CLUSTER")) for t in tag_set)
    )
    if not has_strong_signal and cand_z < 1.5:
        s5 = 0.0
        flags.append("FLAT_NO_MULTIMODAL_SIGNAL")
        notes.append("No empirical dB>=2.2 / WPM_SPIKE / FACE / CHAT_BURST in window")
    sig_just = clip.get("signal_justification")
    if isinstance(sig_just, dict):
        chat_claim = str(sig_just.get("chat_burst") or "NONE")
        if chat_claim != "NONE" and not any(k in str(tag_set) for k in ("CHAT_BURST", "LAUGH_BURST", "CHAT_QUESTION_CLUSTER")) and float(cand.get("z_chat_lagged", 0.0)) <= 0.0:
            s5 = max(0.0, s5 - 5.0)
            flags.append("FABRICATED_SIGNAL_JUSTIFICATION")
    sub["multimodal_grounding"] = max(0.0, round(s5, 2))

    # 6a. Structural Fit (<4s gap -> single segment, valid archetype) (5 pts of 10)
    s6_fit = 5.0
    if arch not in VALID_GTA6_ARCHETYPES:
        s6_fit -= 2.5
        flags.append("INVALID_ARCHETYPE")
    if len(segs) >= 2:
        for i in range(len(segs) - 1):
            gap = float(segs[i + 1].get("start", 0.0)) - float(segs[i].get("end", 0.0))
            if gap < 4.0:
                s6_fit -= 2.5
                flags.append("UNNECESSARY_JUMP_CUT")
                notes.append(f"Micro-gap {gap:.2f}s (<4s) should be 1 continuous segment")
    sub["structural_fit"] = max(0.0, round(s6_fit, 2))

    # 7. Pacing, Duration (20s-45s) & Dead-Air Hygiene (10 pts)
    s7 = 10.0
    if tot_dur < 20.0 or tot_dur > 45.5:
        s7 -= 5.0
        flags.append("DURATION_OUT_OF_BOUNDS")
        notes.append(f"Duration {tot_dur:.2f}s outside [20.0, 45.0]")
    for idx_s, seg in enumerate(segs):
        st0 = float(seg.get("start", 0.0))
        en0 = float(seg.get("end", 0.0))
        sw = _words_in_window(words, w_starts, st0, en0)
        max_sil = 0.0
        sil_span = None
        if sw:
            lg = float(sw[0].get("start", st0)) - st0
            if lg > max_sil:
                max_sil, sil_span = lg, (st0, float(sw[0].get("start", st0)))
            for wi in range(len(sw) - 1):
                g = float(sw[wi + 1].get("start", 0.0)) - float(sw[wi].get("end", 0.0))
                if g > max_sil:
                    max_sil, sil_span = g, (float(sw[wi].get("end", 0.0)), float(sw[wi + 1].get("start", 0.0)))
            tg = en0 - float(sw[-1].get("end", en0))
            if tg > max_sil:
                max_sil, sil_span = tg, (float(sw[-1].get("end", en0)), en0)
        elif en0 - st0 > 5.0:
            max_sil, sil_span = en0 - st0, (st0, en0)
        if max_sil > 5.0 and sil_span:
            saved = any(
                float(s.get("end", 0.0)) >= sil_span[0] and float(s.get("start", 0.0)) <= sil_span[1]
                and any("FACE:" in t or "CHAT_BURST" in t or "dB_PEAK" in t for t in (s.get("tags") or []))
                for s in sentences
            ) or float(cand.get("z_face", 0.0)) >= 1.5
            if not saved:
                s7 -= 5.0
                flags.append("DEAD_AIR_OVER_5S")
                notes.append(f"Seg {idx_s+1} has {max_sil:.2f}s silent dead air ({sil_span[0]:.1f}-{sil_span[1]:.1f})")
    sub["pacing_hygiene"] = max(0.0, round(s7, 2))

    # 8. NSFW / Spoiler / Static-UI / Webcam / Outro Safety (5 pts)
    s8 = 5.0
    combined_text = " ".join([script_text] + [str(s.get("spoken_text") or "") for s in segs])
    if clip.get("is_nsfw_or_unsafe") is True:
        s8 = 0.0
        flags.append("NSFW_UNSAFE_LEAK")
    if cam_cfg is not None and isinstance(cam_cfg, dict) and cam_cfg.get("ai_found") is False:
        s8 = 0.0
        flags.append("NO_WEBCAM_LEAK")
    if STATIC_UI_EVIDENCE_RE.search(vis_desc):
        s8 = max(0.0, s8 - 3.0)
        flags.append("STATIC_UI_OR_MENU_LEAK")
    if ADMIN_MENU_OR_OUTRO_RE.search(combined_text):
        s8 = 0.0
        flags.append("ADMIN_OR_OUTRO_LEAK")
    if not str(clip.get("title") or "").strip() or re.match(r"^(GTA6_Peak_Clip_\d+|clip_\d+)$", str(clip.get("title") or "").strip(), re.I):
        s8 = max(0.0, s8 - 2.0)
        flags.append("GENERIC_TITLE_LEAK")
    sub["safety_and_ui_gate"] = max(0.0, round(s8, 2))

    clip_score_95 = round(sum(sub.values()), 2)
    return {
        "clip_number": clip.get("clip_number"),
        "title": clip.get("title"),
        "archetype": arch,
        "hook_caption": hook,
        "total_duration_sec": round(tot_dur, 2),
        "segment_count": len(segs),
        "sub_scores": sub,
        "clip_score_95": clip_score_95,
        "flags": sorted(set(flags)),
        "notes": notes,
    }


def audit_gta6_preview(
    preview_path: str = "/files/temp/gta6_sandbox_edl_preview.json",
    transcript_path: str = "/files/temp/transcript.json",
    index_path: str = "/files/temp/unified_timeline_index.json",
    summary_path: str = "/files/temp/global_summary.json",
    candidates_path: str = "/files/temp/gta6_candidates.json",
    cam_path: str = "/files/temp/cam_config.json",
) -> dict:
    previews = _load_json_safe(preview_path, [])
    if isinstance(previews, dict):
        previews = previews.get("clips") or []
    transcript = _load_json_safe(transcript_path, {}) or {}
    index_doc = _load_json_safe(index_path, {}) or {}
    global_summary = _load_json_safe(summary_path, {}) or {}
    cand_doc = _load_json_safe(candidates_path, {}) or {}
    cam_cfg = _load_json_safe(cam_path, None)

    words = transcript.get("words") or (transcript.get("x_groq") or {}).get("words") or []
    w_starts = [float(w.get("start", 0.0)) for w in words]
    sentences = index_doc.get("annotated_sentences") or []
    cands_list = cand_doc.get("candidates") or []
    cands_by_id = {c.get("candidate_id"): c for c in cands_list if isinstance(c, dict)}
    eff_dur = float(
        cand_doc.get("effective_duration")
        or transcript.get("duration")
        or (words[-1].get("end", 0.0) if words else 0.0)
        or 1800.0
    )

    if not previews:
        return {
            "overall_score": 0.0,
            "avg_clip_score_95": 0.0,
            "diversity_score_5": 0.0,
            "clip_count": 0,
            "distinct_archetypes": [],
            "fatal_flags": ["NO_CLIPS_GENERATED"],
            "clips": [],
        }

    entity_df, total_sents = _compute_entity_df(sentences)
    clip_reports = [
        score_clip(
            c, words, w_starts, sentences, global_summary,
            cam_cfg=cam_cfg, entity_df=entity_df, total_sents=total_sents, candidates_by_id=cands_by_id,
        )
        for c in previews
    ]
    distinct_arches = sorted({c["archetype"] for c in clip_reports if c["archetype"] in VALID_GTA6_ARCHETYPES})

    # Adaptive target based on chunk length (<8m: 1-2, 8-25m: 2-3, >25m: 4-5 & >=3 archetypes)
    if eff_dur < 480.0:
        min_req_clips, req_arches = 1, min(2, max(1, len(clip_reports)))
    elif eff_dur <= 1500.0:
        min_req_clips, req_arches = 2, 2
    else:
        min_req_clips, req_arches = 3, 3

    if len(distinct_arches) >= req_arches:
        div_score = 5.0
    elif len(distinct_arches) >= 1:
        div_score = round(5.0 * (len(distinct_arches) / float(req_arches)), 2)
    else:
        div_score = 0.0

    avg_95 = sum(c["clip_score_95"] for c in clip_reports) / len(clip_reports)
    overall = avg_95 + div_score
    if len(clip_reports) < min_req_clips:
        overall = max(0.0, overall - (min_req_clips - len(clip_reports)) * 5.0)

    fatal_flags = sorted({f for c in clip_reports for f in c["flags"]})
    if len(distinct_arches) < req_arches:
        fatal_flags.append("LOW_ARCHETYPE_DIVERSITY")
    if len(clip_reports) < min_req_clips:
        fatal_flags.append("CLIP_STARVATION")

    return {
        "overall_score": round(min(100.0, overall), 2),
        "avg_clip_score_95": round(avg_95, 2),
        "diversity_score_5": div_score,
        "effective_duration_sec": round(eff_dur, 2),
        "clip_count": len(clip_reports),
        "distinct_archetypes": distinct_arches,
        "fatal_flags": sorted(set(fatal_flags)),
        "clips": clip_reports,
    }


def main():
    parser = argparse.ArgumentParser(description="Deterministic GTA 6 0-100 EDL Scenario Auditor.")
    parser.add_argument("preview", nargs="?", default="/files/temp/gta6_sandbox_edl_preview.json")
    parser.add_argument("transcript", nargs="?", default="/files/temp/transcript.json")
    parser.add_argument("index", nargs="?", default="/files/temp/unified_timeline_index.json")
    parser.add_argument("summary", nargs="?", default="/files/temp/global_summary.json")
    parser.add_argument("--candidates", default="/files/temp/gta6_candidates.json")
    parser.add_argument("--cam", default="/files/temp/cam_config.json")
    args = parser.parse_args()

    rep = audit_gta6_preview(
        preview_path=args.preview,
        transcript_path=args.transcript,
        index_path=args.index,
        summary_path=args.summary,
        candidates_path=args.candidates,
        cam_path=args.cam,
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
