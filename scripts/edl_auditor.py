#!/usr/bin/env python3
"""
Deterministic EDL Auditor (/files/edl_auditor.py)
Grades /files/temp/n8n_sandbox_edl_preview.json against transcript.json and unified_timeline_index.json
on a 0-100 scale across the 8 Fatal Failure Modes.
"""

import json
import os
import re
import sys
from bisect import bisect_left

VALID_ARCHETYPES = {
    "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
    "VIEWER_OR_CHAT_ROAST_INTERACTION",
    "HUBRIS_WAGER_INSTANT_KARMA",
    "COMEDIC_STORYTELLING_OR_SARCASM",
    "FLASHFORWARD_MYSTERY_INVESTIGATION",
    "EMOTIONAL_SHOCK_OR_BETRAYAL",
}

BANNED_HOOKS_RE = re.compile(
    r"^(I CALLED TIME OUT|HE ACTUALLY FELL FOR IT|THAT DOES NOT COUNT|MY WORST BLUNDER|"
    r"MUST WATCH MOMENT|VIRAL MOMENT|NO WORDS|NO AUDIO FOUND|NO TRANSCRIPT|"
    r"UNDEFINED|NULL|ERROR|GAMING MOMENT|CLIP \d+)$",
    re.I,
)

FOREIGN_GAMES_RE = re.compile(
    r"\b(RUST|TOWER OF HELL|POKEMON|BEYBLADES?|FORTNITE|MINECRAFT|VALORANT|APEX|AMONG US|CSGO|GTA|BEDWARS|BROOKHAVEN|BLOXBURG)\b",
    re.I,
)

ADMIN_OUTRO_RE = re.compile(
    r"\b(going to say bye|comment\b[^.?!]{0,40}\btomorrow|comment\s+[a-z0-9]{2,12}\s+(?:and we'll|if you)|came from the stream|"
    r"everybody subscribe|hit the like button|smash (?:that |the )?like|"
    r"don'?t forget to subscribe|make sure to subscribe|subscribe to the channel|"
    r"thanks? for watching|peace out everybody|ending the stream|see you next time|"
    r"thank you for the raid|thanks for the raid|welcome raiders|"
    r"watch till the end of the stream|keep counter)\b",
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
    "pretty", "really", "right", "roblox", "said", "saying", "says", "see",
    "should", "some", "someone", "something", "sorry", "start", "still", "stop",
    "stream", "sure", "take", "tell", "thank", "thanks", "that", "their", "them",
    "then", "there", "these", "they", "thing", "things", "think", "this", "those",
    "though", "time", "today", "told", "took", "true", "trying", "wait", "wanna",
    "want", "wanted", "watching", "well", "were", "what", "when", "where", "which",
    "while", "will", "with", "would", "yeah", "your", "guys",
}

FILLER_START_RE = re.compile(r"^(and|so|but|then|or|because|though|wait what)\b", re.I)
INCOMPLETE_END_RE = re.compile(r"(?:--|—|,|:|\b(?:and|but|so|or|to|the|a|an|if|that|with|for|of|in|on|at|Wait|like))\s*$", re.I)


def load_json_safe(path, default=None):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def words_in_window(words, w_starts, t0, t1):
    if not words:
        return []
    i = max(0, bisect_left(w_starts, t0 - 1.0))
    out = []
    while i < len(words) and float(words[i].get("start", 0.0)) <= t1:
        w_end = float(words[i].get("end", 0.0))
        w_start = float(words[i].get("start", 0.0))
        if w_end >= t0 and w_start <= t1:
            out.append(words[i])
        i += 1
    return out


def extract_entities(text):
    toks = re.findall(r"[a-z0-9']{4,}", (text or "").lower())
    return {t.strip("'") for t in toks if t.strip("'") not in CONTINUITY_STOPWORDS and len(t.strip("'")) >= 4}


def score_clip(clip, words, w_starts, sentences, global_summary):
    segs = clip.get("edl_segments") or []
    hook = str(clip.get("final_top_hook_caption") or clip.get("hook_caption") or "").strip()
    arch = str(clip.get("narrative_archetype") or "").strip()
    script_text = str(clip.get("assembled_spoken_script") or "")
    pre_ctx = str(clip.get("pre_hook_context_text") or "").strip()
    post_ctx = str(clip.get("post_payoff_context_text") or "").strip()
    tot_dur = float(clip.get("total_duration_sec") or sum(float(s.get("duration", 0)) for s in segs))

    sub = {}
    flags = []
    notes = []

    # ── 1. Pre-Hook Spillover / Mid-Sentence Start (20 pts) ────────────────
    s1 = 20.0
    if not segs:
        s1 = 0.0
        flags.append("EMPTY_EDL_SEGMENTS")
    else:
        seg0 = segs[0]
        t_start = float(seg0.get("start", 0.0))
        sp0 = str(seg0.get("spoken_text") or "").strip()
        # Locate first word belonging to seg0 via midpoint, and check the exact preceding word in Whisper array
        first_idx = None
        for wi in range(max(0, bisect_left(w_starts, t_start - 1.0)), len(words)):
            ws_i = float(words[wi].get("start", 0.0))
            we_i = float(words[wi].get("end", ws_i))
            if (ws_i + we_i) * 0.5 >= t_start and ws_i <= t_start + 2.5:
                first_idx = wi
                break
        first_w = words[first_idx] if first_idx is not None else None
        prev_w = words[first_idx - 1] if (first_idx is not None and first_idx > 0) else None
        pause_before = max(0.0, float(first_w.get("start", t_start)) - float(prev_w.get("end", 0.0))) if (first_w and prev_w) else 1.0
        prev_tok = str(prev_w.get("word", "")).strip() if prev_w else (pre_ctx.split()[-1] if pre_ctx else "")
        ends_sent = bool(re.search(r"[.!?][\"'\)]*$", prev_tok))
        if not ends_sent and pause_before < 0.40 and t_start > 0.5:
            s1 -= 10.0
            flags.append("MID_SENTENCE_START")
            notes.append(f"Pre-hook pause {pause_before:.2f}s (<0.4s) after non-terminal token '{prev_tok}'")
        if FILLER_START_RE.match(sp0) and (not ends_sent or pause_before < 0.25):
            s1 -= 5.0
            flags.append("FILLER_CONTINUATION_START")
            notes.append(f"Starts with filler '{sp0[:25]}' without clean break")
        # Check prior-sentence trailing spillover fragment (only when preceded by non-terminal token or starts lowercase)
        m_spill = re.match(r"^([^.!?]{1,26}[.!?])\s+\S+", sp0)
        if m_spill and len(m_spill.group(1).split()) <= 4 and (not ends_sent or bool(re.match(r"^[a-z]", sp0))):
            s1 -= 5.0
            flags.append("PRE_HOOK_SPILLOVER_WORDS")
            notes.append(f"Trailing prior-sentence fragment '{m_spill.group(1)}' leaked into hook")
    sub["pre_hook_clean"] = max(0.0, s1)

    # ── 2. Premature Payoff Cutoff / Incomplete Climax (20 pts) ────────────
    s2 = 20.0
    if not segs:
        s2 = 0.0
    else:
        seg_last = segs[-1]
        t_end = float(seg_last.get("end", 0.0))
        sp_last = str(seg_last.get("spoken_text") or "").strip()
        # Locate last word inside seg_last via midpoint so aftermath timing isn't off by word overlap
        tail_words = [
            w for w in words_in_window(words, w_starts, max(0.0, t_end - 2.5), t_end + 0.5)
            if (float(w.get("start", 0.0)) + float(w.get("end", w.get("start", 0.0)))) * 0.5 <= t_end
        ]
        last_w = tail_words[-1] if tail_words else None
        last_idx = words.index(last_w) if last_w in words else None
        next_w = words[last_idx + 1] if (last_idx is not None and last_idx + 1 < len(words)) else None
        last_tok = str(last_w.get("word", "")).strip() if last_w else (sp_last[-10:] if sp_last else "")
        clean_end = bool(re.search(r"[.!?][\"'\)]*$", sp_last) or re.search(r"[.!?][\"'\)]*$", last_tok))
        pause_after = max(0.0, float(next_w.get("start", t_end + 4.0)) - float(last_w.get("end", t_end))) if (last_w and next_w) else 4.0
        if not clean_end and pause_after < 0.40:
            s2 -= 10.0
            flags.append("PREMATURE_PAYOFF_CUTOFF")
            notes.append(f"Clip ends mid-clause '{sp_last[-35:]}' with next word '{next_w.get('word','') if next_w else ''}' only {pause_after:.2f}s later")
        if INCOMPLETE_END_RE.search(sp_last):
            s2 -= 6.0
            flags.append("DANGLING_CLIMAX_PHRASE")
            notes.append(f"Ends on dangling phrase '{sp_last[-30:]}'")
        # Verify aftermath reaction after peak signal inside final segment
        last_start = float(seg_last.get("start", 0.0))
        peak_times = []
        for s in sentences:
            st = float(s.get("start", 0.0))
            en = float(s.get("end", 0.0))
            if st >= last_start and st <= t_end:
                tgs = s.get("tags", [])
                if any("dB_PEAK" in t or "SCREAM" in t or "LAUGH_BURST" in t for t in tgs):
                    # Approximate peak center/end if peak falls within this sentence
                    peak_times.append(min(en, max(st, (st + en) * 0.5 + 0.5), t_end))
        if peak_times:
            aftermath = t_end - max(peak_times)
            if aftermath < 1.2 and post_ctx and pause_after < 0.35 and not clean_end:
                s2 -= 5.0
                flags.append("INSUFFICIENT_AFTERMATH")
                notes.append(f"Only {aftermath:.2f}s reaction aftermath after peak in payoff")
    sub["payoff_completion"] = max(0.0, s2)

    # ── 3. Frankenstein Bait-and-Switch / Entity Continuity (15 pts) ───────
    s3 = 15.0
    if len(segs) >= 2:
        ec = clip.get("entity_continuity_check") or {}
        if ec.get("passed") is False:
            s3 = 0.0
            flags.append("FRANKENSTEIN_MISMATCH")
            notes.append(f"Pipeline entity check failed: {ec.get('reason')}")
        else:
            max_gap = max(
                float(segs[i + 1].get("start", 0.0)) - float(segs[i].get("end", 0.0))
                for i in range(len(segs) - 1)
            )
            e_setup = extract_entities(segs[0].get("spoken_text", ""))
            e_payoff = extract_entities(segs[-1].get("spoken_text", ""))
            # Also include entities from cause_and_effect_setup or middle segment
            e_mid = set()
            for ms in segs[1:-1]:
                e_mid |= extract_entities(ms.get("spoken_text", ""))
            shared = (e_setup & (e_payoff | e_mid))
            # Allow transitive chain continuity (Seg0 <-> Mid <-> Payoff) or explicit bridge
            chain_ok = bool(e_setup & e_mid) and bool((e_mid & e_payoff) or re.search(r"\b(planted|device|secret|truth|found out|because|told you)\b", segs[-1].get("spoken_text", ""), re.I))
            if max_gap > 25.0 and len(shared) == 0 and not chain_ok and arch != "COMEDIC_STORYTELLING_OR_SARCASM":
                # Check 4-char stemmed prefix overlap
                p_setup = {w[:4] for w in e_setup}
                p_payoff = {w[:4] for w in (e_payoff | e_mid)}
                if not (p_setup & p_payoff):
                    s3 = 0.0
                    flags.append("FRANKENSTEIN_MISMATCH")
                    notes.append(f"Gap {max_gap:.1f}s >25s with 0 shared entities between setup ({sorted(list(e_setup))[:5]}) & payoff ({sorted(list(e_payoff))[:5]})")
    sub["entity_continuity"] = max(0.0, s3)

    # ── 4. Hook Caption Hallucination & Specificity (10 pts) ───────────────
    s4 = 10.0
    game_ctx = str(global_summary.get("game") or global_summary.get("summary") or "").lower()
    full_corpus = (game_ctx + " " + script_text + " " + str(clip.get("title") or "")).lower()
    if not hook or BANNED_HOOKS_RE.match(hook):
        s4 = 0.0
        flags.append("BANNED_OR_EMPTY_CAPTION")
    else:
        fg = FOREIGN_GAMES_RE.search(hook)
        if fg and fg.group(1).lower() not in full_corpus:
            s4 = 0.0
            flags.append("HALLUCINATED_CAPTION")
            notes.append(f"Hook '{hook}' mentions foreign game '{fg.group(1)}' absent from transcript/summary")
        else:
            wc = len(hook.split())
            if hook != hook.upper():
                s4 -= 3.0
                flags.append("HOOK_NOT_ALL_CAPS")
            if wc < 3 or wc > 5:
                s4 -= 3.0
                flags.append("HOOK_WORD_COUNT_OFF")
                notes.append(f"Hook '{hook}' has {wc} words (target 3-5)")
            # Grounding check: at least 1 meaningful content noun/verb or theme match
            nouns = [w for w in re.findall(r"[a-z0-9]{4,}", hook.lower()) if w not in {"what", "when", "why", "this", "that", "actually", "literally", "really"}]
            if nouns and all(n[:4] not in full_corpus for n in nouns):
                s4 -= 4.0
                flags.append("UNGROUNDED_HOOK_NOUNS")
                notes.append(f"None of hook words {nouns} found in clip/summary corpus")
    sub["hook_caption_quality"] = max(0.0, s4)

    # ── 5. Multimodal Signal Grounding (10 pts) ────────────────────────────
    s5 = 10.0
    all_tags = []
    for seg in segs:
        all_tags.extend(seg.get("signal_tags_in_window") or [])
    # Verify directly against unified_timeline_index annotated_sentences + [+3, +8] lagged chat
    empirical_tags = set()
    for seg in segs:
        st0 = float(seg.get("start", 0.0))
        en0 = float(seg.get("end", 0.0))
        for s in sentences:
            sst = float(s.get("start", 0.0))
            sen = float(s.get("end", 0.0))
            if sen >= st0 - 0.5 and sst <= en0 + 0.5:
                for tg in s.get("tags", []):
                    empirical_tags.add(tg)
    has_signal = any(
        any(k in t for k in ("dB_PEAK", "SCREAM", "LAUGH_BURST", "CHAT_BURST", "CHAT_LAG", "FACE:", "VIEWER_OR_GAME_VOICE", "VOICE_PITCH_BREAK", "WPM_SPIKE"))
        for t in (set(all_tags) | empirical_tags)
    )
    if not has_signal:
        s5 = 0.0
        flags.append("FLAT_NO_MULTIMODAL_SIGNAL")
        notes.append("Zero dB/chat/face/pitch/viewer signals found in playback window")
    elif not empirical_tags and not all_tags:
        s5 = 4.0
    sub["multimodal_grounding"] = max(0.0, s5)

    # ── 6 (Clip-level). Structural Fit (<4s gap -> single seg) (5 pts of 10) ─
    s6_fit = 5.0
    if len(segs) >= 2:
        for i in range(len(segs) - 1):
            gap = float(segs[i + 1].get("start", 0.0)) - float(segs[i].get("end", 0.0))
            if gap < 4.0:
                s6_fit -= 2.5
                flags.append("UNNECESSARY_JUMP_CUT")
                notes.append(f"Gap between seg {i+1} & {i+2} is only {gap:.2f}s (<4s); should be 1 continuous segment")
    if arch not in VALID_ARCHETYPES:
        s6_fit = max(0.0, s6_fit - 2.5)
        flags.append("INVALID_ARCHETYPE")
    sub["structural_fit"] = max(0.0, s6_fit)

    # ── 7. Pacing, Duration & Dead-Air Hygiene (10 pts) ────────────────────
    s7 = 10.0
    if tot_dur < 22.0 or tot_dur > 45.5:
        s7 -= 5.0
        flags.append("DURATION_OUT_OF_BOUNDS")
        notes.append(f"Duration {tot_dur:.2f}s outside [22.0s, 45.0s]")
    # Check dead air > 5.0s inside each segment
    for idx_s, seg in enumerate(segs):
        st0 = float(seg.get("start", 0.0))
        en0 = float(seg.get("end", 0.0))
        seg_words = words_in_window(words, w_starts, st0, en0)
        max_sil = 0.0
        sil_span = None
        if seg_words:
            lead_gap = float(seg_words[0].get("start", st0)) - st0
            if lead_gap > max_sil:
                max_sil = lead_gap
                sil_span = (st0, float(seg_words[0].get("start", st0)))
            for wi in range(len(seg_words) - 1):
                g = float(seg_words[wi + 1].get("start", 0.0)) - float(seg_words[wi].get("end", 0.0))
                if g > max_sil:
                    max_sil = g
                    sil_span = (float(seg_words[wi].get("end", 0.0)), float(seg_words[wi + 1].get("start", 0.0)))
            tail_gap = en0 - float(seg_words[-1].get("end", en0))
            if tail_gap > max_sil:
                max_sil = tail_gap
                sil_span = (float(seg_words[-1].get("end", en0)), en0)
        elif en0 - st0 > 5.0:
            max_sil = en0 - st0
            sil_span = (st0, en0)
        if max_sil > 5.0 and sil_span:
            # Check if saved by FACE or CHAT_BURST during silent window
            saved = any(
                float(s.get("end", 0.0)) >= sil_span[0] and float(s.get("start", 0.0)) <= sil_span[1]
                and any("FACE:" in tg or "CHAT_BURST" in tg for tg in s.get("tags", []))
                for s in sentences
            )
            if not saved:
                s7 -= 5.0
                flags.append("DEAD_AIR_OVER_5S")
                notes.append(f"Segment {idx_s+1} has {max_sil:.2f}s silent gap ({sil_span[0]:.1f}-{sil_span[1]:.1f})")
    sub["pacing_hygiene"] = max(0.0, s7)

    # ── 8. Zero Admin, Intro Rules, Raid, or Outro Banter (5 pts) ──────────
    s8 = 5.0
    combined_spoken = " ".join([script_text] + [str(s.get("spoken_text") or "") for s in segs])
    m_adm = ADMIN_OUTRO_RE.search(combined_spoken)
    if m_adm:
        s8 = 0.0
        flags.append("ADMIN_OR_OUTRO_LEAK")
        notes.append(f"Matched banned admin/outro phrase: '{m_adm.group(0)}'")
    sub["zero_admin_outro"] = max(0.0, s8)

    clip_score_95 = sum(sub.values())  # 95 pts max per-clip + 5 pts batch diversity = 100
    return {
        "clip_number": clip.get("clip_number"),
        "title": clip.get("title"),
        "archetype": arch,
        "hook_caption": hook,
        "total_duration_sec": round(tot_dur, 2),
        "segment_count": len(segs),
        "sub_scores": sub,
        "clip_score_95": round(clip_score_95, 2),
        "flags": sorted(set(flags)),
        "notes": notes,
    }


def audit_preview(
    preview_path="/files/temp/n8n_sandbox_edl_preview.json",
    transcript_path="/files/temp/transcript.json",
    index_path="/files/temp/unified_timeline_index.json",
    summary_path="/files/temp/global_summary.json",
):
    previews = load_json_safe(preview_path, [])
    transcript = load_json_safe(transcript_path, {}) or {}
    index_doc = load_json_safe(index_path, {}) or {}
    global_summary = load_json_safe(summary_path, {}) or {}

    words = transcript.get("words") or (transcript.get("x_groq") or {}).get("words") or []
    w_starts = [float(w.get("start", 0.0)) for w in words]
    sentences = index_doc.get("annotated_sentences") or []

    if not previews:
        return {
            "overall_score": 0.0,
            "clip_count": 0,
            "distinct_archetypes": [],
            "diversity_score_5": 0.0,
            "fatal_flags": ["NO_CLIPS_GENERATED"],
            "clips": [],
        }

    clip_reports = [score_clip(c, words, w_starts, sentences, global_summary) for c in previews]
    distinct_arches = sorted({c["archetype"] for c in clip_reports if c["archetype"] in VALID_ARCHETYPES})

    # 6 (Batch-level). Archetype Diversity (5 pts of 10): >=3 distinct archetypes -> 5, 2 -> 2.5, 1 -> 0
    if len(distinct_arches) >= 3:
        div_score = 5.0
    elif len(distinct_arches) == 2:
        div_score = 2.5
    else:
        div_score = 0.0

    # Extra penalty if <= 2 clips generated (starvation)
    avg_clip_95 = sum(c["clip_score_95"] for c in clip_reports) / len(clip_reports)
    overall = avg_clip_95 + div_score
    if len(clip_reports) < 3:
        overall = max(0.0, overall - (3 - len(clip_reports)) * 5.0)

    fatal_flags = sorted({f for c in clip_reports for f in c["flags"]})
    if len(distinct_arches) < 3:
        fatal_flags.append("LOW_ARCHETYPE_DIVERSITY")

    return {
        "overall_score": round(overall, 2),
        "avg_clip_score_95": round(avg_clip_95, 2),
        "diversity_score_5": div_score,
        "clip_count": len(clip_reports),
        "distinct_archetypes": distinct_arches,
        "fatal_flags": fatal_flags,
        "clips": clip_reports,
    }


def main():
    preview_p = sys.argv[1] if len(sys.argv) > 1 else "/files/temp/n8n_sandbox_edl_preview.json"
    transcript_p = sys.argv[2] if len(sys.argv) > 2 else "/files/temp/transcript.json"
    index_p = sys.argv[3] if len(sys.argv) > 3 else "/files/temp/unified_timeline_index.json"
    summary_p = sys.argv[4] if len(sys.argv) > 4 else "/files/temp/global_summary.json"
    res = audit_preview(preview_p, transcript_p, index_p, summary_p)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
