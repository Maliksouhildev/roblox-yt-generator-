#!/usr/bin/env python3
"""
gta6_vision_director.py
-----------------------
Multimodal Vision Director for GTA 6 Viral Shorts Engine.

Reads /files/temp/gta6_candidates.json (Top 8 empirical peaks + 3x3 JPEG grids)
and /files/temp/global_summary.json, calls Gemini Vision (with multi-key/model
and deterministic fallback), and outputs rich clip objects directly compatible
with `5. Split Clips` and `Create Subtitle Binary` (eliminating Context Merge Agent).
"""

from bisect import bisect_left
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

GEMINI_KEY_FILES = [
    "/files/temp/n8n_gemini_key.txt",
    "/files/gemini_key.txt",
    "/files/temp/gemini_key.txt",
    "/files/temp/all_ai_creds.json",
]

DEFAULT_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]

GTA6_ARCHETYPES = [
    "OPEN_WORLD_CHAOS_OR_COP_CHASE",
    "LEONIDA_NPC_ENCOUNTER_OR_ROAST",
    "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    "HUBRIS_WAGER_WASTED_KARMA",
    "COMEDIC_BANTER_OR_SARCASM",
    "STORY_CUTSCENE_OR_TWIST_REACTION",
]

# Part 1.3: Block ALL prepositions, articles, pronouns, auxiliaries, and transitive/perception verbs
TRANSITIVE_OR_DANGLING_WORDS = (
    "TO|A|AN|THE|OF|IN|ON|AT|FOR|WITH|FROM|BY|AND|OR|BUT|IF|IS|ARE|WAS|WERE|"
    "DO|DOES|DID|NOT|GOING|HAVE|HAS|MY|YOUR|OUR|THEIR|THIS|THAT|I|ME|HE|SHE|WE|THEY|"
    "WE'RE|I'M|IT'S|I'VE|WE'VE|YOU'VE|THEY'VE|HE'S|SHE'S|DON'T|DIDN'T|WON'T|CAN'T|"
    "LIKE|LOVE|HATE|DESPISE|WANT|NEED|KNOW|THINK|FEEL|SEE|SAW|LOOK|WATCH|GOT|GET|"
    "MAKE|MADE|TAKE|TOOK|GIVE|GAVE|PUT|SAY|SAID|TELL|TOLD|FIND|FOUND|LET|KEEP|TRY|TRIED|USE|USED|ACTUALLY|REALLY"
)

DANGLING_HOOK_END_RE = re.compile(rf"\b({TRANSITIVE_OR_DANGLING_WORDS})\s*[.!?]*$", re.I)

CLICKBAIT_FORBIDDEN_IF_UNSPOKEN_RE = re.compile(
    r"\b(GLITCH(?:ES)?|HACK(?:S|ED|ING)?|EXPLOIT(?:S|ED)?|MOD(?:S|DED)?|SECRET\s+CODE|INFINITE\s+MONEY|INFINITE|BANNED|CHEAT(?:S|ING)?|ACID\s+LAB)\b",
    re.I,
)

BRAND_SAFE_BANNED_RE = re.compile(
    r"\b(COKE|COCAINE|HEROIN|METH(?:AMPHETAMINE)?|FENTANYL|SUICIDE|KILL\s+YOURSELF)\b",
    re.I,
)

WEAK_TAIL_FILLER_RE = re.compile(
    r"^(?:ok(?:ay)?|alright|anyway|yeah|yep|yup|no|uh+|um+|let'?s\s+see|hold\s+on|wait|one\s+sec(?:ond)?|hmm+)[.!?,\s]*$",
    re.I,
)

FILLER_OPENERS_RE = re.compile(r"^(and|so|but|then|or|because|though|uh+|um+)\b", re.I)

BANNED_HOOK_RE = re.compile(
    r"^(I CALLED TIME OUT|HE ACTUALLY FELL FOR IT|THAT DOES NOT COUNT|"
    r"MY WORST BLUNDER|MUST WATCH MOMENT|VIRAL MOMENT|NO WORDS|"
    r"NO AUDIO FOUND|NO TRANSCRIPT|UNDEFINED|NULL|ERROR|WATCH THIS CLIP)$",
    re.I,
)


RAW_INTERJECTION_START_RE = re.compile(
    r"^(?:whoa|woah|huh|yeah|yep|um+|uh+|wait|so|like|well|okay|ok|alright|i\s+mean)\b",
    re.I,
)
ROBOTIC_COPY_RE = re.compile(
    r"(?:^streamer\s+(?:reflects|tries|attempts|gets|experiences|reacts|is\s+seen)\b|"
    r"bro\s+really\s+said\s+[\"']|right\s+before\s+everything\s+went\s+sideways|"
    r"did\s+you\s+see\s+that\s+coming\s+at|fallback\s+offline\s+mode|watch\s+closely\s+around|"
    r"^gta6_(?:peak_)?clip_\d+$|^crazy\s+leonida\s+moment\s+\d+$)",
    re.I,
)


def _extract_streamer_handle(cand_doc: dict | None = None, summary_doc: dict | None = None) -> str:
    """Resolve clean creator handle from cand_doc stream_file or sidecar .info.json."""
    if isinstance(cand_doc, dict):
        sf = str(cand_doc.get("stream_file") or os.path.basename(str(cand_doc.get("video_path") or ""))).strip()
        if sf:
            stem = re.sub(r"(\.processing)?\.mp4$", "", sf, flags=re.I)
            for base_dir in ("/files/inputs", os.path.dirname(str(cand_doc.get("video_path") or ""))):
                if not base_dir:
                    continue
                for suffix in (".processing.info.json", ".info.json"):
                    ip = os.path.join(base_dir, stem + suffix)
                    if os.path.isfile(ip):
                        info = _load_json(ip) or {}
                        uid = str(info.get("uploader_id") or "").strip().lstrip("@")
                        up = str(info.get("uploader") or info.get("channel") or "").strip().lstrip("@")
                        if re.match(r"^UC[A-Za-z0-9_-]{22}$", uid) and up:
                            uid = up
                        raw = uid or up
                        if raw:
                            return re.sub(r"\s+", "", raw)
            m = re.match(r"^([A-Za-z0-9_-]+?)_(?:vod_\d+|[A-Za-z0-9_-]{11})_chunk\d+", sf, re.I)
            if m:
                return m.group(1)
    if isinstance(summary_doc, dict):
        s_name = str(summary_doc.get("streamer_handle") or summary_doc.get("streamer_name") or "").strip().lstrip("@")
        if s_name and s_name.lower() not in {"streamer", "unknown"}:
            return s_name
    return ""


def _norm_alnum_tokens(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9']+", str(text or ""))]


def is_garbage_title_or_hook(text: str, transcript: str = "") -> bool:
    """Reject conversational interjection openers, verbatim first-6-word transcript copies, or robotic templates."""
    s = str(text or "").strip()
    if not s or len(s) < 6:
        return True
    if BANNED_HOOK_RE.match(s) or RAW_INTERJECTION_START_RE.match(s) or ROBOTIC_COPY_RE.search(s):
        return True
    toks = _norm_alnum_tokens(s)
    if len(toks) < 3:
        return True
    if transcript:
        first6 = _norm_alnum_tokens(transcript)[:6]
        if len(first6) >= 3:
            cand_norm = " ".join(toks)
            f6_norm = " ".join(first6)
            if cand_norm in f6_norm or (len(toks) >= 3 and f6_norm.startswith(cand_norm)):
                return True
            if len(first6) >= 4 and " ".join(first6[:4]) in cand_norm and cand_norm.startswith(" ".join(first6[:3])):
                return True
    return False


def _target_clip_range(candidates: list, cand_doc: dict | None = None) -> tuple[int, int]:
    if isinstance(cand_doc, dict) and cand_doc.get("recommended_max_clips"):
        return (
            int(cand_doc.get("recommended_min_clips") or 2),
            min(10, int(cand_doc.get("recommended_max_clips") or 10)),
        )
    max_t = max([float(c.get("window_end", 0.0)) for c in (candidates or [])] + [0.0])
    if max_t > 0.0 and max_t < 480.0 and len(candidates) <= 6:
        return 2, 3
    if max_t > 0.0 and max_t <= 1500.0 and len(candidates) <= 10:
        return 4, 6
    return 6, 10


def _load_json(path: str):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def collect_gemini_keys() -> list:
    keys = []
    seen = set()

    def _add(k: str):
        k = str(k or "").strip()
        if len(k) > 20 and k not in seen:
            seen.add(k)
            keys.append(k)

    _add(os.environ.get("GEMINI_API_KEY", ""))
    for kp in GEMINI_KEY_FILES:
        if not os.path.exists(kp):
            continue
        try:
            raw = open(kp, "r", encoding="utf-8").read().strip()
            if kp.endswith(".json"):
                creds = json.loads(raw)
                if isinstance(creds, list):
                    for c in creds:
                        ctype = str(c.get("type", "")).lower()
                        if "gemini" in ctype or "palm" in ctype or "google" in ctype:
                            _add(c.get("apiKey", ""))
            else:
                _add(raw)
        except Exception:
            pass
    return keys


def list_meme_files(meme_dir: str = "/files/memes") -> list:
    if not os.path.isdir(meme_dir):
        return ["vine-boom-sound-effect_KT89XIq.mp3", "shocked-sound-effect.mp3"]
    files = sorted(
        f for f in os.listdir(meme_dir)
        if f.lower().endswith((".mp3", ".wav")) and os.path.isfile(os.path.join(meme_dir, f))
    )
    return files or ["vine-boom-sound-effect_KT89XIq.mp3"]


def build_prompt_text(summary_doc: dict, candidates: list, meme_files: list, min_clips: int = 4, max_clips: int = 10, streamer_handle: str = "") -> str:
    game = summary_doc.get("game") or "Gaming / GTA 6"
    vibe = summary_doc.get("vibe") or "Chaotic High-Energy"
    gs = summary_doc.get("global_summary") or "Live gaming stream."
    themes = ", ".join(summary_doc.get("key_themes") or [])
    creator_ctx = f"\n- Streamer: {streamer_handle}" if streamer_handle else ""

    cand_blocks = []
    for c in candidates:
        cid = c.get("candidate_id", f"cand_{c.get('rank')}")
        w0, w1 = c.get("window_start", 0.0), c.get("window_end", 0.0)
        tp = c.get("peak_time", 0.0)
        chats = " | ".join(str(m) for m in (c.get("chat_samples") or [])[:3])
        tx_lines = "\n    ".join((c.get("transcript_lines") or [])[:20]) or "(No clear speech in window)"
        has_grid = bool(c.get("grid_path") and os.path.exists(c["grid_path"]))
        flags = []
        if c.get("chat_question_cluster"):
            flags.append("[CHAT_QUESTION_CLUSTER]")
        if float(c.get("heatmap_value") or 0.0) >= 0.35:
            flags.append(f"[HEATMAP_PEAK:{float(c.get('heatmap_value')):.2f}][CROWD_REPLAY]")
        flag_str = (" | " + " ".join(flags)) if flags else ""
        sil_pct = int(round(float(c.get("streamer_silence_ratio") or 0.0) * 100))
        cand_blocks.append(
            f"### CANDIDATE {cid} (GridAttached={has_grid}{flag_str})\n"
            f"Window: [{w0:.2f}s - {w1:.2f}s] | Peak: t={tp:.1f}s | Virality={c.get('virality_score', 0):.2f} "
            f"| z_dB={c.get('z_db', 0):.1f} | z_chat={c.get('z_chat_lagged', 0):.1f} | hm={c.get('heatmap_value', 0):.2f} | z_face={c.get('z_face', 0):.1f} | streamer_silent={sil_pct}%\n"
            f"ChatSamples: {chats or 'None'}\n"
            f"Timestamps burned on grid tiles: {c.get('frame_timestamps', [])}\n"
            f"Transcript:\n    {tx_lines}"
        )

    memes_str = ", ".join(meme_files[:20])
    return (
        "You are the Lead Multimodal Vision Director for a viral GTA 6 & Gaming Shorts channel.\n"
        f"You are given {len(candidates)} empirically detected Peak Candidates, each with a 3x3 JPEG storyboard grid\n"
        "(9 frames labeled `t=XXX.Xs` at the top-left of each tile), crowd signals (`[HEATMAP_PEAK]` / `[CHAT_BURST]`),\n"
        "and speaker-tagged transcript (`[NPC_OR_OTHER_VOICE]` vs `[STREAMER]`).\n\n"
        f"GLOBAL CONTEXT:\n- Game: {game}{creator_ctx}\n- Vibe: {vibe}\n- Summary: {gs}\n- Themes: {themes}\n\n"
        f"AVAILABLE SFX MEME FILES: {memes_str}\n\n"
        "STRICT SELECTION & EDITING RULES:\n"
        "1. M-RATED / NSFW & MENU VISION SHIELD:\n"
        "   Inspect EVERY 3x3 grid first! Immediately REJECT (or set `is_nsfw_or_unsafe: true`) any candidate showing:\n"
        "   - Nudity, strip clubs, sexually explicit M-rated scenes, or graphic TOS-violating gore.\n"
        "   - Chrome/Edge browsers, Twitch/YouTube chat dashboards, Discord, pause/ESC/settings menus, or static non-gameplay screens.\n"
        "   - Passive story cutscenes where the streamer is silent >40% of the window.\n"
        f"2. SINGLE-SCENE CONTIGUITY & TIGHT VIRAL PACING (15s-34s): Pick the BEST {min_clips} to {max_clips} distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end]. NEVER pad clips with boring pre-joke walking!\n"
        "   Target 16.0s to 34.0s total duration (hard floor 14.0s, hard cap 40.0s). Start RIGHT on the setup line and end 1.5s-3.0s after the payoff.\n"
        "3. BOUNDARY INTEGRITY & ANTI-MUMBLE ENDINGS: Snap start and end cleanly to complete sentences. NEVER end on weak filler ('Okay.', 'Alright.', 'Anyway.') or trailing silence > 1.2s.\n"
        "4. GTA 6 ARCHETYPE PRIORITY (Strongly prioritize high-replay streamer reactions & gameplay chaos):\n"
        "   - PRIORITY: `OPEN_WORLD_CHAOS_OR_COP_CHASE`, `LEONIDA_NPC_ENCOUNTER_OR_ROAST`, `HUBRIS_WAGER_WASTED_KARMA`, `COMEDIC_BANTER_OR_SARCASM`, `HOW_TO_TIP_OR_SECRET_DISCOVERY`.\n"
        "   - PENALIZE `STORY_CUTSCENE_OR_TWIST_REACTION` if `streamer_silent > 40%` (only pick cutscenes with huge vocal+face shock; MUST set `is_story_spoiler: true` and NEVER spoil in `hook_caption`).\n"
        "   - Prioritize candidates carrying `[HEATMAP_PEAK]` / `[CROWD_REPLAY]` combined with streamer face/vocal spikes.\n"
        "5. PUNCHY HUMAN CLIP-EDITOR COPYWRITING RUBRIC (CRITICAL — NEVER USE RAW TRANSCRIPT OPENINGS AS TITLES!):\n"
        "   - HARD BAN on titles/hooks starting with conversational fillers: 'Whoa', 'Huh', 'Yeah', 'Um', 'Uh', 'Wait', 'So', 'Like', 'Well', 'Okay', 'Alright', 'I mean'.\n"
        "   - HARD BAN on copying the first 4-6 spoken words verbatim as a title or hook!\n"
        "   - BAD EXAMPLES (NEVER OUTPUT):\n"
        "     * BAD title/hook: 'Whoa Baps Are Pushing In Shit' (raw transcript filler!)\n"
        "     * BAD title/hook: 'Huh Yeah I Mean If It Gets' (raw transcript nonsense!)\n"
        "     * BAD description: 'Bro really said \"...\" right before everything went sideways.' or 'Streamer reflects on...'\n"
        "     * BAD comment bait: 'Did you see that coming at \"...\"?' or 'What would you have done here?'\n"
        "   - GOOD EXAMPLES (MATCH THIS EXACT ENERGY & SPECIFICITY):\n"
        "     * GOOD `hook_caption` (4-7 words, Sentence case, <=38 chars): \"Speed wasn't ready for this NPC\", \"Bro got launched across Vice City\", \"GTA 6 cops have zero chill\"\n"
        "     * GOOD `yt_title` / `youtube_title` (<=68 chars): \"IShowSpeed couldn't believe what this GTA 6 NPC just did\", \"DrDisRespect got humbled by Vice City cops in 2 seconds\"\n"
        "     * GOOD `desc_line` / `short_description` (1 deadpan reaction line): \"Bro talked crazy for two seconds and immediately got boxed in by six cruisers.\"\n"
        "     * GOOD `comment_hook` / `comment_bait_question`: \"nah how did that cop even make that turn\", \"scale of 1-10 how cooked was he here\"\n"
        "   - Anti-cringe banlist: skibidi, rizz, sigma, gyatt, ohio, fanum tax, no cap, bussin, slay, fam, yeet, epic gaming moment, must watch.\n"
        "   - `grounding_quote`: exact short verbatim quote from inside this candidate's transcript proving the moment.\n"
        "   - `visual_evidence`: 1 concrete sentence describing what happens on screen across the 3x3 grid tiles.\n\n"
        "CANDIDATES:\n" + "\n\n".join(cand_blocks) + "\n\n"
        "OUTPUT STRICT JSON ONLY (NO MARKDOWN FENCES):\n"
        "{\n"
        "  \"clips\": [\n"
        "    {\n"
        "      \"clip_number\": 1,\n"
        "      \"candidate_id\": \"cand_1\",\n"
        "      \"title\": \"Vice City Cops Boxed Him In\",\n"
        "      \"yt_title\": \"IShowSpeed got humbled by GTA 6 cops in 2 seconds\",\n"
        "      \"youtube_title\": \"IShowSpeed got humbled by GTA 6 cops in 2 seconds\",\n"
        "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
        "      \"hook_caption\": \"GTA 6 cops have zero chill\",\n"
        "      \"desc_line\": \"Bro talked crazy for two seconds and immediately got boxed in by six cruisers.\",\n"
        "      \"short_description\": \"Bro talked crazy for two seconds and immediately got boxed in by six cruisers.\",\n"
        "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge right before the crash.\",\n"
        "      \"comment_hook\": \"scale of 1-10 how cooked was he here\",\n"
        "      \"comment_bait_question\": \"scale of 1-10 how cooked was he here\",\n"
        "      \"is_story_spoiler\": false,\n"
        "      \"is_nsfw_or_unsafe\": false,\n"
        "      \"grounding_quote\": \"exact short verbatim quote from transcript\",\n"
        "      \"climax_quote\": \"exact verbatim payoff words\",\n"
        "      \"reaction_triggers\": [{\"quote\": \"wait what\", \"sfx\": \"shocked-sound-effect.mp3\"}],\n"
        "      \"memes\": [{\"timestamp\": 14.5, \"file\": \"vine-boom-sound-effect_KT89XIq.mp3\", \"volume\": 0.30}],\n"
        "      \"visual_evidence\": \"What happens visually on the 3x3 tiles.\",\n"
        "      \"start_time\": 120.4,\n"
        "      \"end_time\": 146.2,\n"
        "      \"payoff_time\": 143.0,\n"
        "      \"segments\": [{\"start\": 120.4, \"end\": 146.2, \"role\": \"CONTINUOUS_ARC\"}],\n"
        "      \"virality_score\": 9.1,\n"
        "      \"cause_and_effect_setup\": \"Cocky getaway boast -> instant 6-star wreck payoff.\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )


def _interleave_vision_parts(summary_doc: dict, candidates: list, meme_files: list, min_clips: int = 4, max_clips: int = 10, streamer_handle: str = "") -> tuple[list, int]:
    """Build multimodal Vision parts interleaving each candidate's transcript + its 3x3 JPEG grid."""
    game = summary_doc.get("game") or "Gaming / GTA 6"
    vibe = summary_doc.get("vibe") or "Chaotic High-Energy"
    gs = summary_doc.get("global_summary") or "Live gaming stream."
    themes = ", ".join(summary_doc.get("key_themes") or [])
    creator_ctx = f"\n- Streamer: {streamer_handle}" if streamer_handle else ""
    memes_str = ", ".join(meme_files[:20])

    header_text = (
        "You are the Lead Multimodal Vision Director for a viral GTA 6 & Gaming Shorts channel.\n"
        f"Below are {len(candidates)} empirically detected Peak Candidates. Each candidate is presented with its\n"
        "crowd signals (`[HEATMAP_PEAK]` / `[CHAT_BURST]`), speaker-tagged transcript (`[NPC_OR_OTHER_VOICE]` vs `[STREAMER]`),\n"
        "and its 960x540 `3x3` JPEG storyboard contact sheet (`t=XXX.Xs` burned on every tile).\n\n"
        f"GLOBAL CONTEXT:\n- Game: {game}{creator_ctx}\n- Vibe: {vibe}\n- Summary: {gs}\n- Themes: {themes}\n\n"
        f"AVAILABLE SFX MEME FILES: {memes_str}\n\n"
        "STRICT SELECTION & EDITING RULES:\n"
        "1. M-RATED / NSFW, BOOT/EULA & MENU VISION SHIELD:\n"
        "   Inspect EVERY 3x3 grid first! Immediately REJECT (or set `is_nsfw_or_unsafe: true`) any candidate showing:\n"
        "   - Nudity, strip clubs, sexually explicit M-rated scenes, or graphic TOS-violating gore.\n"
        "   - Game boot/splash screens, epilepsy warnings, EULA/calibration menus, loading screens, browsers, Discord, pause/map menus.\n"
        "   - Passive cutscenes or aimless walking/driving where `streamer_silent > 40%`.\n"
        f"2. SINGLE-SCENE CONTIGUITY & TIGHT VIRAL PACING (15s-34s): Pick the BEST {min_clips} to {max_clips} distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end].\n"
        "   Target 16.0s to 34.0s total duration (hard floor 14.0s, hard cap 40.0s). ZERO pre-joke walking bloat! Start tight on the setup and end 1.5s-3.0s after payoff.\n"
        "3. BOUNDARY INTEGRITY: Snap start and end to natural Whisper sentence/reaction boundaries, <=1.2s trailing silence.\n"
        "4. GTA 6 ARCHETYPE PRIORITY:\n"
        "   - PRIORITY: `OPEN_WORLD_CHAOS_OR_COP_CHASE`, `LEONIDA_NPC_ENCOUNTER_OR_ROAST`, `HUBRIS_WAGER_WASTED_KARMA`, `COMEDIC_BANTER_OR_SARCASM`, `HOW_TO_TIP_OR_SECRET_DISCOVERY`.\n"
        "   - PENALIZE `STORY_CUTSCENE_OR_TWIST_REACTION` when streamer is silent >40% of the window (if picked, MUST set `is_story_spoiler: true` and never spoil in `hook_caption`).\n"
        "   - Prioritize `[HEATMAP_PEAK]` / `[CROWD_REPLAY]` spikes paired with active webcam + vocal reaction.\n"
        "5. PUNCHY HUMAN CLIP-EDITOR COPYWRITING RUBRIC (HARD BAN ON RAW TRANSCRIPT FILLER TITLES!):\n"
        "   - NEVER start `title`, `yt_title`, or `hook_caption` with: 'Whoa', 'Huh', 'Yeah', 'Um', 'Uh', 'Wait', 'So', 'Like', 'Well', 'Okay', 'Alright', 'I mean'.\n"
        "   - NEVER copy the first 4-6 raw spoken Whisper words as a title or hook!\n"
        "   - BAD (FORBIDDEN): title='Whoa Baps Are Pushing In Shit', title='Huh Yeah I Mean If It Gets', desc='Bro really said \"...\" right before everything went sideways.', desc='Streamer reflects...'.\n"
        "   - GOOD (MATCH THIS): hook_caption=\"Speed wasn't ready for this NPC\" / \"Bro got launched across Vice City\" / \"GTA 6 cops have zero chill\"; yt_title=\"IShowSpeed couldn't believe what this GTA 6 NPC just did\"; desc_line=\"Bro talked crazy for two seconds and immediately got boxed in.\"; comment_hook=\"nah how did that cop even make that turn\".\n"
        "   - NEVER use skibidi/rizz/sigma/gyatt/ohio/fanum tax/no cap/bussin/slay/fam/lit/yeet/epic gaming moment/must watch or brand-unsafe drug/self-harm words.\n"
        "   - `grounding_quote`: exact short verbatim quote from inside this clip's transcript.\n"
        "   - `visual_evidence`: 1 concrete sentence citing what is actually seen across the 3x3 grid tiles.\n"
    )
    parts = [{"text": header_text}]
    attached = 0
    for c in candidates:
        cid = c.get("candidate_id", f"cand_{c.get('rank')}")
        w0, w1 = c.get("window_start", 0.0), c.get("window_end", 0.0)
        tp = c.get("peak_time", 0.0)
        chats = " | ".join(str(m) for m in (c.get("chat_samples") or [])[:3])
        tx_lines = "\n    ".join((c.get("transcript_lines") or [])[:20]) or "(No clear speech in window)"
        has_grid = bool(c.get("grid_path") and os.path.exists(c["grid_path"]))
        flags = []
        if c.get("chat_question_cluster"):
            flags.append("[CHAT_QUESTION_CLUSTER]")
        if float(c.get("heatmap_value") or 0.0) >= 0.35:
            flags.append(f"[HEATMAP_PEAK:{float(c.get('heatmap_value')):.2f}][CROWD_REPLAY]")
        flag_str = (" | " + " ".join(flags)) if flags else ""
        sil_pct = int(round(float(c.get("streamer_silence_ratio") or 0.0) * 100))
        block = (
            f"### CANDIDATE {cid} (GridAttached={has_grid}{flag_str})\n"
            f"Window: [{w0:.2f}s - {w1:.2f}s] | Peak: t={tp:.1f}s | Virality={c.get('virality_score', 0):.2f} "
            f"| z_dB={c.get('z_db', 0):.1f} | z_chat={c.get('z_chat_lagged', 0):.1f} | hm={c.get('heatmap_value', 0):.2f} | z_face={c.get('z_face', 0):.1f} | streamer_silent={sil_pct}%\n"
            f"ChatSamples: {chats or 'None'}\n"
            f"Timestamps burned on grid tiles: {c.get('frame_timestamps', [])}\n"
            f"Transcript:\n    {tx_lines}"
        )
        parts.append({"text": block})
        if has_grid:
            try:
                b64 = base64.b64encode(open(c["grid_path"], "rb").read()).decode("utf-8")
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                attached += 1
            except Exception:
                pass

    parts.append({
        "text": (
            "\nOUTPUT STRICT JSON ONLY (NO MARKDOWN FENCES):\n"
            "{\n"
            "  \"clips\": [\n"
            "    {\n"
            "      \"clip_number\": 1,\n"
            "      \"candidate_id\": \"cand_1\",\n"
            "      \"title\": \"Vice City Cops Boxed Him In\",\n"
            "      \"yt_title\": \"IShowSpeed got humbled by GTA 6 cops in 2 seconds\",\n"
            "      \"youtube_title\": \"IShowSpeed got humbled by GTA 6 cops in 2 seconds\",\n"
            "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
            "      \"hook_caption\": \"GTA 6 cops have zero chill\",\n"
            "      \"desc_line\": \"Bro talked crazy for two seconds and immediately got boxed in on the bridge.\",\n"
            "      \"short_description\": \"Bro talked crazy for two seconds and immediately got boxed in on the bridge.\",\n"
            "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge right before the crash.\",\n"
            "      \"comment_hook\": \"scale of 1-10 how cooked was he here\",\n"
            "      \"comment_bait_question\": \"scale of 1-10 how cooked was he here\",\n"
            "      \"is_story_spoiler\": false,\n"
            "      \"is_nsfw_or_unsafe\": false,\n"
            "      \"grounding_quote\": \"exact short verbatim quote from transcript\",\n"
            "      \"climax_quote\": \"exact verbatim payoff words\",\n"
            "      \"reaction_triggers\": [{\"quote\": \"wait what\", \"sfx\": \"shocked-sound-effect.mp3\"}],\n"
            "      \"memes\": [{\"timestamp\": 14.5, \"file\": \"vine-boom-sound-effect_KT89XIq.mp3\", \"volume\": 0.30}],\n"
            "      \"visual_evidence\": \"What happens visually on the 3x3 tiles.\",\n"
            "      \"start_time\": 120.4,\n"
            "      \"end_time\": 146.2,\n"
            "      \"payoff_time\": 143.0,\n"
            "      \"segments\": [{\"start\": 120.4, \"end\": 146.2, \"role\": \"CONTINUOUS_ARC\"}],\n"
            "      \"virality_score\": 9.1,\n"
            "      \"cause_and_effect_setup\": \"Cocky getaway boast -> instant 6-star wreck payoff.\"\n"
            "    }\n"
            "  ]\n"
            "}\n"
        )
    })
    return parts, attached


def collect_mistral_keys() -> list:
    keys = []
    seen = set()

    def _add(k: str):
        k = str(k or "").strip()
        if len(k) > 15 and k not in seen:
            seen.add(k)
            keys.append(k)

    _add(os.environ.get("MISTRAL_API_KEY", ""))
    for kp in GEMINI_KEY_FILES:
        if kp.endswith(".json") and os.path.exists(kp):
            try:
                creds = json.loads(open(kp, "r", encoding="utf-8").read())
                if isinstance(creds, list):
                    for c in creds:
                        if "mistral" in str(c.get("type", "")).lower():
                            _add(c.get("apiKey", ""))
            except Exception:
                pass
    # In-memory decrypt from n8n SQLite if CryptoJS/sqlite3 exist inside container
    if not keys and os.path.exists("/root/.n8n/database.sqlite") and os.path.exists("/root/.n8n/config"):
        try:
            import subprocess
            node_snippet = (
                "const C=require('/usr/local/lib/node_modules/n8n/node_modules/crypto-js');"
                "const S=require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');"
                "const enc=JSON.parse(require('fs').readFileSync('/root/.n8n/config','utf8')).encryptionKey;"
                "const db=new S.Database('/root/.n8n/database.sqlite');"
                "db.all(\"SELECT data FROM credentials_entity WHERE type='mistralCloudApi'\",(e,r)=>{"
                "if(r)r.forEach(x=>{try{const p=JSON.parse(C.AES.decrypt(x.data,enc).toString(C.enc.Utf8));if(p.apiKey)console.log(p.apiKey);}catch(_){}});db.close();});"
            )
            out = subprocess.check_output(["node", "-e", node_snippet], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", errors="replace")
            for ln in out.splitlines():
                _add(ln)
        except Exception:
            pass
    return keys


def call_mistral_fallback(prompt_text: str, mistral_keys: list, model: str = "mistral-large-latest"):
    payload = json.dumps({
        "model": model,
        "temperature": 0.25,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt_text}],
    }).encode("utf-8")
    last_err = None
    for k in mistral_keys:
        req = urllib.request.Request(
            "https://api.mistral.ai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {k}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            txt = data["choices"][0]["message"]["content"]
            return txt, {"provider": "mistral_text_fallback", "model": model, "grids_attached": 0}
        except Exception as ex:
            last_err = str(ex)
    return None, {"provider": "none", "error": last_err or "no_mistral_key", "grids_attached": 0}


def call_gemini_vision(parts_or_prompt, candidates: list, api_keys: list, models: list):
    if isinstance(parts_or_prompt, list):
        parts = parts_or_prompt
        attached = sum(1 for p in parts if isinstance(p, dict) and "inline_data" in p)
    else:
        parts = [{"text": parts_or_prompt}]
        attached = 0
        for c in candidates:
            gp = c.get("grid_path", "")
            if gp and os.path.exists(gp):
                try:
                    b64 = base64.b64encode(open(gp, "rb").read()).decode("utf-8")
                    parts.append({"text": f"[STORYBOARD GRID FOR {c.get('candidate_id')}]"})
                    parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                    attached += 1
                except Exception:
                    pass

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    last_err = None
    saw_rate_limit = False
    for attempt in range(2):
        if attempt > 0:
            if not saw_rate_limit:
                break
            time.sleep(15.0)
        for model in models:
            for key in api_keys:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    txt = data["candidates"][0]["content"]["parts"][0]["text"]
                    return txt, {"provider": "gemini_vision", "model": model, "grids_attached": attached}
                except urllib.error.HTTPError as e:
                    if e.code in (429, 503):
                        saw_rate_limit = True
                    last_err = f"{model}: HTTP {e.code}"
                    continue
                except Exception as ex:
                    last_err = f"{model}: {ex}"
                    continue
    return None, {"provider": "none", "error": last_err or "no_api_response", "grids_attached": attached}


def _strip_unspoken_clickbait(text: str, transcript_text: str) -> str:
    """Part 1.4: Remove unspoken clickbait (GLITCH/HACK/EXPLOIT/MOD/BANNED/ACID LAB) and brand-unsafe drug/self-harm terms."""
    t_low = str(transcript_text or "").lower()

    def _rep(m):
        tok = m.group(0).lower()
        return m.group(0) if tok in t_low else ""

    cleaned = CLICKBAIT_FORBIDDEN_IF_UNSPOKEN_RE.sub(_rep, str(text or ""))
    cleaned = BRAND_SAFE_BANNED_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


_HOOK_SPECIAL_CASE = {
    "gta": "GTA", "gta6": "GTA 6", "vi": "VI", "npc": "NPC", "npcs": "NPCs",
    "ishowspeed": "IShowSpeed", "caseoh": "CaseOh", "xqc": "xQc", "xqcow": "xQc",
    "kai": "Kai", "cenat": "Cenat", "jynxzi": "Jynxzi", "vice": "Vice", "city": "City",
    "leonida": "Leonida", "lucia": "Lucia", "jason": "Jason", "rockstar": "Rockstar",
    "florida": "Florida", "fbi": "FBI", "swat": "SWAT", "vip": "VIP", "ai": "AI", "fps": "FPS",
}
_CRINGE_BUZZWORDS_RE = re.compile(
    r"\b(skibidi|rizz|sigma|gyatt|ohio|fanum\s+tax|no\s+cap|bussin|slay|fam|yeet|epic\s+gaming\s+moment|must\s+watch)\b",
    re.I,
)


def _to_sentence_case_hook(words: list) -> str:
    out = []
    for idx, w in enumerate(words):
        low = w.lower()
        if low in _HOOK_SPECIAL_CASE:
            out.append(_HOOK_SPECIAL_CASE[low])
        elif idx == 0:
            out.append(low[0].upper() + low[1:] if len(low) > 1 else low.upper())
        else:
            out.append(low)
    return " ".join(out)


def _guard_and_format_hook(raw_hook: str, raw_text: str, title: str) -> str:
    """Punchy 4-7 word Sentence-case headline (<=38 chars), zero dangling endings, zero cringe/ungrounded clickbait."""
    de_baited = _strip_unspoken_clickbait(str(raw_hook or ""), raw_text)
    de_cringed = _CRINGE_BUZZWORDS_RE.sub("", de_baited)
    clean = re.sub(r"[^A-Za-z0-9'\s!?-]", " ", de_cringed)
    clean = re.sub(r"[-]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    ctx = f"{title} {raw_text}".lower()
    if "coolest" in ctx:
        clean = re.sub(r"\bCOLDEST\b", "coolest", clean, flags=re.I)
    clean = re.sub(r"\bRAGE\s+BADER\b", "rage baiter", clean, flags=re.I)

    words = clean.split()
    while words and words[0].upper() in {"AND", "SO", "BUT", "BECAUSE", "THEN", "OR", "WELL"} and len(words) > 3:
        words.pop(0)
    if re.match(r"^(PEAK MOMENT|CLIP)\b", " ".join(words), re.I):
        words = []
    if len(words) > 7:
        words = words[:7]
    while words and len(" ".join(words)) > 38 and len(words) > 3:
        words.pop()
    while words and DANGLING_HOOK_END_RE.match(words[-1].upper()) and len(words) > 3:
        words.pop()
    while words and len(" ".join(words)) > 38 and len(words) > 1:
        words.pop()
    if (
        not words
        or len(words) < 3
        or len(words) > 7
        or len(" ".join(words)) > 38
        or DANGLING_HOOK_END_RE.match(words[-1].upper())
    ):
        fb = _safe_hook_from_text(raw_text, _strip_unspoken_clickbait(title, raw_text))
        return _to_sentence_case_hook(fb.split())
    return _to_sentence_case_hook(words)
    return " ".join(words)


def _safe_hook_from_text(text: str, title: str) -> str:
    """Synthesize a clean 3-5 word (<=28 char) grounded headline without mid-clause truncation or dangling verbs."""
    t_clean = _strip_unspoken_clickbait(title, text)
    # Try clean title words first if headline-like (not generic)
    t_words = [
        w.upper() for w in re.findall(r"[A-Za-z0-9']+", str(t_clean or ""))
        if not re.match(r"^(PEAK|CLIP|MOMENT|GAMING)$", w, re.I)
    ][:5]
    while t_words and DANGLING_HOOK_END_RE.match(t_words[-1]) and len(t_words) > 3:
        t_words.pop()
    while t_words and len(" ".join(t_words)) > 28 and len(t_words) > 3:
        t_words.pop()
    if 3 <= len(t_words) <= 5 and len(" ".join(t_words)) <= 28 and not DANGLING_HOOK_END_RE.match(t_words[-1]):
        return " ".join(t_words)

    clean_words = re.findall(r"[A-Za-z0-9']+", _strip_unspoken_clickbait(text, text))
    stop = {
        "AND", "THE", "THIS", "THAT", "WITH", "JUST", "LIKE", "YEAH", "OKAY", "UH", "UM",
        "IF", "OR", "TO", "OF", "IN", "ON", "A", "AN", "FOR", "AT", "BECAUSE", "SO", "BUT",
        "IT", "ITS", "IT'S", "IS", "ARE", "WAS", "WERE", "BE", "BEEN", "I", "IM", "I'M", "YOU", "WE", "THEY", "HE", "SHE", "MY", "YOUR",
    }
    kept = []
    for w in clean_words:
        wu = w.upper()
        if wu in stop or len(wu) > 10:
            continue
        if wu not in kept:
            kept.append(wu)
        if len(kept) >= 5:
            break
    while kept and DANGLING_HOOK_END_RE.match(kept[-1]) and len(kept) > 3:
        kept.pop()
    while kept and len(" ".join(kept)) > 28 and len(kept) > 3:
        kept.pop()
    if 3 <= len(kept) <= 5 and len(" ".join(kept)) <= 28 and not DANGLING_HOOK_END_RE.match(kept[-1]):
        return " ".join(kept)
    return "LIVE STREAM CHAOS REACTION"


def _strip_speaker_prefix(line: str) -> str:
    s = re.sub(r"^\[[^\]]*\[[^\]]+\]\]\s*", "", str(line or ""))
    s = re.sub(r"^\[[^\]]+\]\s*", "", s)
    return s.lstrip("] ").strip()


def _synthesize_clean_metadata(
    arch: str,
    visual_ev: str,
    streamer_handle: str = "",
    idx: int = 1,
    is_spoiler: bool = False,
) -> dict:
    """Synthesize punchy, natural metadata from visual_event_description + archetype + streamer (NEVER raw Whisper filler)."""
    creator = str(streamer_handle or "").strip().lstrip("@")
    short_creator = creator if (creator and creator.lower() not in {"streamer", "unknown"}) else "Bro"
    vis = str(visual_ev or "").strip()
    is_generic_vis = not vis or bool(re.search(r"3x3\s+(?:grid|storyboard)|centered around reaction peak|active webcam reaction", vis, re.I))

    arch_defaults = {
        "OPEN_WORLD_CHAOS_OR_COP_CHASE": (
            "GTA 6 Cops Showed Zero Mercy",
            f"{short_creator} couldn't escape this GTA 6 chaos",
            "GTA 6 cops have zero chill",
            "Everything went from zero to six-star chaos in two seconds flat.",
            "scale of 1-10 how cooked was he here",
        ),
        "LEONIDA_NPC_ENCOUNTER_OR_ROAST": (
            "Vice City NPC Caught Him Off Guard",
            f"{short_creator} wasn't ready for this GTA 6 NPC",
            f"{short_creator} wasn't ready for this NPC",
            "Leonida NPCs really wake up choosing chaos every single time.",
            "nah why did that NPC actually do that",
        ),
        "HUBRIS_WAGER_WASTED_KARMA": (
            "Instant Karma in Vice City",
            f"{short_creator} talked crazy and got humbled in GTA 6",
            "Bro got humbled in two seconds",
            "Talked big for one second and the game immediately humbled him.",
            "instant karma or total bad luck",
        ),
        "HOW_TO_TIP_OR_SECRET_DISCOVERY": (
            "Hidden Detail Caught Live in GTA 6",
            f"{short_creator} found a wild detail in GTA 6",
            "Rockstar really put this in GTA 6",
            "Blink and you'd miss this insane detail Rockstar hid in Leonida.",
            "did anyone else even notice this detail",
        ),
        "COMEDIC_BANTER_OR_SARCASM": (
            "Unfiltered Live GTA 6 Moment",
            f"{short_creator} completely lost it in GTA 6",
            "He really didn't see this coming",
            "Chat was losing it the second this unfolded live on stream.",
            "clip of the day or nah",
        ),
        "STORY_CUTSCENE_OR_TWIST_REACTION": (
            "Wild GTA 6 Story Moment Live",
            f"{short_creator} was speechless during this GTA 6 scene",
            "His reaction says everything here",
            "Zero chance anyone expected that turn live on stream.",
            "did that scene catch you off guard too",
        ),
    }
    base_title, base_yt, base_hook, base_desc, base_comment = arch_defaults.get(
        arch,
        arch_defaults["OPEN_WORLD_CHAOS_OR_COP_CHASE"],
    )

    if not is_generic_vis:
        vis_clean = re.sub(r"[^A-Za-z0-9'\s-]", " ", vis)
        vis_clean = re.sub(r"\s+", " ", vis_clean).strip()
        vis_words = [w for w in vis_clean.split() if len(w) <= 14][:7]
        if len(vis_words) >= 4 and not is_garbage_title_or_hook(" ".join(vis_words)):
            base_desc = vis.rstrip(".") + "."
            if len(" ".join(vis_words)) <= 48:
                base_title = " ".join(w.capitalize() if w.lower() not in _HOOK_SPECIAL_CASE else _HOOK_SPECIAL_CASE[w.lower()] for w in vis_words[:6])

    if is_spoiler and re.search(r"\b(dies|dead|betray|ending|killed)\b", base_hook, re.I):
        base_hook = "His reaction says everything here"

    return {
        "title": base_title[:58],
        "youtube_title": base_yt[:68],
        "hook_caption": _guard_and_format_hook(base_hook, "", base_title),
        "short_description": base_desc,
        "comment_bait_question": base_comment,
    }


def _repair_bad_titles_with_llm(
    bad_clips: list,
    api_keys: list,
    mistral_keys: list,
    streamer_handle: str = "",
) -> dict:
    """Run 1 fast targeted text-only repair prompt for clips whose title/hook failed raw-transcript validation."""
    if not bad_clips or (not api_keys and not mistral_keys):
        return {}
    items_desc = []
    for item in bad_clips[:6]:
        items_desc.append(
            f"- candidate_id={item['candidate_id']} | archetype={item['arch']} | streamer={streamer_handle or 'Streamer'}\n"
            f"  visual_event={item['visual_ev']}\n"
            f"  transcript_snippet={item['transcript'][:240]}"
        )
    repair_prompt = (
        "You are a viral YouTube Shorts title/hook editor for a GTA 6 clips channel.\n"
        "Rewrite ONLY the metadata for these clips because their prior titles copied raw Whisper filler.\n"
        "STRICT RULES:\n"
        "- NEVER start title/yt_title/hook_caption with: Whoa, Huh, Yeah, Um, Uh, Wait, So, Like, Well, Okay, Alright, I mean.\n"
        "- NEVER copy the first 6 spoken words verbatim.\n"
        "- `hook_caption`: 4-7 punchy words in Sentence case (<=38 chars), e.g. \"Speed wasn't ready for this NPC\", \"GTA 6 cops have zero chill\".\n"
        "- `yt_title`: natural high-CTR clip title (<=68 chars), e.g. \"IShowSpeed couldn't believe what this GTA 6 NPC just did\".\n"
        "- `desc_line`: 1 casual deadpan reaction line (NO 'Bro really said' or 'Streamer reflects').\n"
        "- `comment_hook`: 1 short natural Shorts comment prompt.\n\n"
        "CLIPS TO REPAIR:\n" + "\n".join(items_desc) + "\n\n"
        "OUTPUT STRICT JSON ONLY:\n"
        "{\"repairs\": [{\"candidate_id\": \"cand_1\", \"title\": \"...\", \"yt_title\": \"...\", \"hook_caption\": \"...\", \"desc_line\": \"...\", \"comment_hook\": \"...\"}]}"
    )
    raw = None
    if api_keys:
        raw, _ = call_gemini_vision(repair_prompt, [], api_keys[:2], ["gemini-2.5-flash", "gemini-2.5-flash-lite"])
    if not raw and mistral_keys:
        raw, _ = call_mistral_fallback(repair_prompt, mistral_keys[:1], model="mistral-small-latest")
    if not raw:
        return {}
    try:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        m = re.search(r"\{[\s\S]*\}", cleaned)
        parsed = json.loads(m.group(0) if m else cleaned)
        out = {}
        for r in (parsed.get("repairs") or []):
            if isinstance(r, dict) and r.get("candidate_id"):
                out[str(r["candidate_id"])] = r
        return out
    except Exception:
        return {}


def _smart_clip_title(hook: str, raw_txt: str, climax_q: str, arch: str, idx: int, visual_ev: str = "", streamer_handle: str = "") -> str:
    """Build a descriptive, non-generic Short title — NEVER slicing raw Whisper filler openings."""
    if hook and not is_garbage_title_or_hook(hook, raw_txt):
        h_words = [
            _HOOK_SPECIAL_CASE[w.lower()] if w.lower() in _HOOK_SPECIAL_CASE else w.capitalize()
            for w in re.findall(r"[A-Za-z0-9']+", hook)
        ]
        if len(h_words) >= 3:
            return " ".join(h_words)[:55].strip()
    return _synthesize_clean_metadata(arch, visual_ev, streamer_handle=streamer_handle, idx=idx)["title"]


def _build_short_description(cl: dict, cand_raw_txt: str = "", climax_q: str = "", visual_note: str = "", arch: str = "", streamer_handle: str = "") -> str:
    """Guarantee a concrete, casual clip-editor description (zero robotic 3rd-person or 'Bro really said' slop)."""
    explicit = str(cl.get("desc_line") or cl.get("short_description") or "").strip()
    if explicit and len(explicit) >= 16 and not ROBOTIC_COPY_RE.search(explicit):
        return explicit
    return _synthesize_clean_metadata(arch or str(cl.get("narrative_archetype") or ""), visual_note, streamer_handle=streamer_handle)["short_description"]


def _words_text(words: list, t0: float, t1: float) -> str:
    if not words:
        return ""
    out = []
    for w in words:
        ws = float(w.get("start", 0.0))
        we = float(w.get("end", ws))
        mid = (ws + we) * 0.5
        if t0 <= mid <= t1:
            tok = str(w.get("word", "")).strip()
            if tok:
                out.append(tok)
    return " ".join(out).strip()


def _trim_leading_dead_air(st: float, en: float, words: list, payoff_t: float) -> tuple[float, float]:
    """Advance clip start past >4.2s internal silent gaps only when >=34.0s duration remains before payoff."""
    if not words:
        return st, en
    seg_ws = [w for w in words if float(w.get("end", 0.0)) >= st and float(w.get("start", 0.0)) <= en]
    if len(seg_ws) < 2:
        return st, en
    for i in range(len(seg_ws) - 1):
        g = float(seg_ws[i + 1].get("start", 0.0)) - float(seg_ws[i].get("end", 0.0))
        if g > 4.2:
            after_start = float(seg_ws[i + 1].get("start", st)) - 0.10
            if (en - after_start) >= 34.0 and after_start <= payoff_t - 10.0:
                return round(after_start, 2), en
            before_end = float(seg_ws[i].get("end", en)) + 0.15
            if (before_end - st) >= 14.0 and payoff_t <= before_end + 1.0:
                return st, round(before_end, 2)
    return st, en


def _snap_boundary_with_words(
    st: float,
    en: float,
    words: list,
    w_starts: list,
    payoff_t: float,
    lo_bound: float,
    hi_bound: float,
) -> tuple[float, float, str, str, str]:
    """
    Snap [st, en] cleanly to Whisper word/sentence boundaries targeting tight 15s-34s pacing (floor 14.0s, cap 40.0s):
    - Start on terminal punctuation [.!?] or pause >= 0.42s without leading filler/ellipsis.
    - End on terminal punctuation [.!?] preserving 1.5s-3.0s aftermath, <= 1.2s trailing silence, zero weak mumble tails.
    """
    if not words:
        return round(st, 2), round(en, 2), "", "", ""
    st, en = _trim_leading_dead_air(st, en, words, payoff_t)

    max_end = float(words[-1].get("end", hi_bound))
    lo = max(3.0, lo_bound - 2.0)
    hi = min(max_end, hi_bound + 3.0)
    if words:
        first_win_w = next((w for w in words if float(w.get("end", 0.0)) >= lo), None)
        last_win_w = next((w for w in reversed(words) if float(w.get("start", 0.0)) <= hi), None)
        if first_win_w and float(first_win_w.get("start", lo)) - lo > 2.0:
            lo = max(lo, float(first_win_w["start"]) - 0.15)
        if last_win_w and hi - float(last_win_w.get("end", hi)) > 2.0:
            hi = min(hi, float(last_win_w["end"]) + 0.35)
        st = max(lo, st)

    # Keep tight setup lead only when clip fell below 14.5s floor (never pad punchy 16s-34s clips!)
    if payoff_t > 0.0 and (en - st) < 14.5:
        st = max(lo, min(st, payoff_t - 18.0))

    # 1. Find clean start candidate near `st`
    clean_starts = []
    idx0 = max(0, bisect_left(w_starts, max(lo, st - 4.0)))
    for i in range(idx0, len(words)):
        ws = float(words[i].get("start", 0.0))
        if ws > st + 6.0:
            break
        if ws < lo - 0.1:
            continue
        tok = str(words[i].get("word", "")).strip()
        if "..." in tok or "…" in tok:
            continue
        if i == 0:
            clean_starts.append((abs(ws - st), max(lo, ws)))
            continue
        prev_tok = str(words[i - 1].get("word", "")).strip()
        prev_end = float(words[i - 1].get("end", ws))
        gap = max(0.0, ws - prev_end)
        ends_term = bool(re.search(r"(?<!\.)[.!?][\"'\)]*$", prev_tok)) and ("..." not in prev_tok and "…" not in prev_tok)
        if (ends_term or gap >= 0.42) and not FILLER_OPENERS_RE.match(tok) and not tok.startswith("..."):
            lookahead = " ".join(str(words[k].get("word", "")).strip() for k in range(i, min(len(words), i + 5)))
            ell_pen = 50.0 if ("..." in lookahead or "…" in lookahead) else 0.0
            span_ok = (hi - ws) >= 14.0 or ws <= lo + 3.0
            if span_ok:
                clean_starts.append((abs(ws - st) + (0.0 if ends_term else 2.5) + ell_pen, max(lo, max(3.0, ws - 0.08))))
    if clean_starts:
        clean_starts.sort(key=lambda x: x[0])
        st = round(clean_starts[0][1], 2)

    # 2. Ensure payoff aftermath (1.5s - 3.0s after payoff_t), duration 14.0s-39.5s, and strong terminal sentence
    min_dur_end = st + 14.5
    pref_end = max(min_dur_end, min(st + 34.0, (payoff_t + 2.5) if payoff_t > st else en))
    max_target_end = min(hi, st + 39.5)
    min_target_end = min(max_target_end, min_dur_end)

    clean_ends = []
    idx_e = max(0, bisect_left(w_starts, st + 12.0))
    for i in range(idx_e, len(words)):
        we = float(words[i].get("end", words[i].get("start", 0.0)))
        if we > max_target_end:
            break
        if we < st + 14.0 and max_target_end >= st + 14.5:
            continue
        tok = str(words[i].get("word", "")).strip()
        sent_tail_words = []
        for k in range(i, max(-1, i - 4), -1):
            w_k = str(words[k].get("word", "")).strip()
            if k < i and re.search(r"[.!?]$", w_k):
                break
            sent_tail_words.insert(0, w_k)
        tail_phrase = " ".join(sent_tail_words).strip()
        is_weak_mumble = bool(WEAK_TAIL_FILLER_RE.match(tail_phrase))
        next_start = float(words[i + 1].get("start", we + 4.0)) if i + 1 < len(words) else (we + 4.0)
        gap_after = max(0.0, next_start - we)
        ends_term = bool(re.search(r"(?<!\.)[.!?][\"'\)]*$", tok)) and ("..." not in tok and "…" not in tok)
        dangling_end = bool(re.search(r"(?:--|—|,|:|\.\.\.|…|\b(?:and|but|so|or|to|the|a|an|if|that|with|for|of|in|on|at|like|want|know|see))$", tok, re.I))
        if (ends_term or gap_after >= 0.42) and not dangling_end:
            pen = (0.0 if ends_term else 3.0) + (18.0 if is_weak_mumble else 0.0) + (8.0 if (payoff_t > st and we < payoff_t + 1.5 and we < max_end - 2.0) else 0.0)
            clean_ends.append((abs(we - min(max_target_end, pref_end)) + pen, min(hi, we + 0.30)))
    if clean_ends:
        clean_ends.sort(key=lambda x: x[0])
        en = round(clean_ends[0][1], 2)
    else:
        en = round(min(max_target_end, max(min_target_end, en)), 2)

    # Trim trailing dead air > 1.2s past last spoken word unconditionally (never pad silent tail)
    tail_ws = [w for w in words if st <= float(w.get("end", 0.0)) <= en]
    if tail_ws:
        last_w_end = float(tail_ws[-1].get("end", en))
        if en - last_w_end > 1.2:
            en = round(last_w_end + 0.35, 2)

    if en - st < 14.0 and st - lo > 1.0:
        need = 14.5 - (en - st)
        new_st_cand = max(lo, st - need)
        if new_st_cand < st - 0.5:
            st = round(new_st_cand, 2)

    pre_words = [
        str(w.get("word", "")).strip()
        for w in words
        if max(0.0, st - 15.0) <= ((float(w.get("start", 0.0)) + float(w.get("end", w.get("start", 0.0)))) * 0.5) < st - 0.02
    ][-10:]
    pre_ctx = " ".join(pre_words).strip()
    post_ctx = _words_text(words, en + 0.05, min(max_end, en + 5.0))
    spoken = _words_text(words, st, en)
    return st, en, spoken, pre_ctx, post_ctx


def _map_meme_timestamp(raw_ts, clean_segs: list, cand: dict, payoff_t: float) -> float:
    """Fix 1.5: Map MM.SS float hints or stream-absolute times into clip-relative seconds deterministically."""
    total_dur = max(2.0, sum(s["end"] - s["start"] for s in clean_segs))
    s0 = clean_segs[0]["start"] if clean_segs else 0.0
    try:
        val = float(raw_ts)
    except (TypeError, ValueError):
        val = -1.0

    # Check if MM.SS decimal encoding (e.g. 22.12 when clip starts past 1200s)
    if val >= 0.0 and s0 > 120.0 and 0.0 < val < s0 and (val * 60.0) >= s0 - 15.0:
        mins = int(val)
        secs = int(round((val - mins) * 100.0))
        if 0 <= secs < 60:
            val = float(mins * 60 + secs)

    # Check if stream-absolute timestamp inside segments
    if val >= s0 - 1.0:
        acc = 0.0
        for seg in clean_segs:
            if val <= seg["end"] + 1.0:
                rel = acc + max(0.0, val - seg["start"])
                return round(max(0.8, min(total_dur - 0.8, rel)), 2)
            acc += seg["end"] - seg["start"]

    # Already clip-relative?
    if 0.8 <= val <= total_dur - 0.8:
        return round(val, 2)

    # Fallback: payoff_time relative offset
    acc = 0.0
    for seg in clean_segs:
        if payoff_t <= seg["end"] + 1.0:
            rel_p = acc + max(1.0, payoff_t - seg["start"])
            return round(max(1.0, min(total_dur - 1.0, rel_p)), 2)
        acc += seg["end"] - seg["start"]
    return round(max(1.5, total_dur * 0.72), 2)


def _signal_justification_from_cand(cand: dict, segs: list) -> dict:
    tags = list((cand or {}).get("signal_tags") or [])
    for s in (segs or []):
        tags.extend(s.get("signal_tags_in_window") or [])
    chat_t = next((t for t in tags if any(k in t for k in ("CHAT_BURST", "LAUGH_BURST", "CHAT_QUESTION_CLUSTER"))), "NONE")
    db_t = next((t for t in tags if any(k in t for k in ("SCREAM", "dB_PEAK"))), "NONE")
    face_t = next((t for t in tags if "FACE:" in t), "NONE")
    return {
        "chat_burst": chat_t,
        "db_spike": db_t,
        "face_emotion": face_t,
        "viewer_voice_present": any("VIEWER_OR_GAME_VOICE" in t or "NPC_OR_OTHER_VOICE" in t for t in tags),
    }


def deterministic_candidate_fallback(
    candidates: list,
    meme_files: list,
    words: list | None = None,
    max_clips: int | None = None,
    streamer_handle: str = "",
) -> dict:
    """Grounded deterministic single-scene fallback prioritizing non-cutscene GTA 6 chaos & clean synthesized titles."""
    sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_files else meme_files[0]
    arch_pool = [
        "OPEN_WORLD_CHAOS_OR_COP_CHASE",
        "LEONIDA_NPC_ENCOUNTER_OR_ROAST",
        "HUBRIS_WAGER_WASTED_KARMA",
        "COMEDIC_BANTER_OR_SARCASM",
        "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    ]
    w_list = words or []
    w_starts = [float(w.get("start", 0.0)) for w in w_list]
    if max_clips is None:
        _, max_clips = _target_clip_range(candidates)

    clips = []
    for idx, c in enumerate(candidates[:max_clips], start=1):
        w0 = float(c.get("window_start", 10.0))
        w1 = float(c.get("window_end", w0 + 44.0))
        tp = float(c.get("peak_time", (w0 + w1) * 0.5))
        # Tight 16s-32s pacing centered around the peak
        st = max(w0, round(tp - 22.0, 2))
        en = min(w1, round(tp + 3.0, 2))
        if en - st < 16.0:
            st = max(w0, round(en - 22.0, 2))
            if en - st < 14.0:
                en = min(w1, round(st + 20.0, 2))
        spoken_seg, pre_ctx, post_ctx = c.get("raw_text") or "", "", ""
        if w_list:
            st, en, spoken_seg, pre_ctx, post_ctx = _snap_boundary_with_words(st, en, w_list, w_starts, tp, w0, w1)
            spoken_seg = spoken_seg or (c.get("raw_text") or "")

        lines = c.get("transcript_lines") or []
        raw_txt = spoken_seg or (c.get("raw_text") or "")
        has_npc = any("[NPC_OR_OTHER_VOICE]" in ln for ln in lines)
        used = {cl["narrative_archetype"] for cl in clips}
        if c.get("chat_question_cluster") and "HOW_TO_TIP_OR_SECRET_DISCOVERY" not in used:
            arch = "HOW_TO_TIP_OR_SECRET_DISCOVERY"
        elif has_npc and "LEONIDA_NPC_ENCOUNTER_OR_ROAST" not in used:
            arch = "LEONIDA_NPC_ENCOUNTER_OR_ROAST"
        else:
            avail = [a for a in arch_pool if a not in used]
            arch = avail[0] if avail else arch_pool[(idx - 1) % len(arch_pool)]
        climax_q = ""
        for ln in reversed(lines):
            stripped = _strip_speaker_prefix(ln)
            if stripped and len(stripped.split()) >= 3 and not WEAK_TAIL_FILLER_RE.match(stripped):
                climax_q = stripped[:70]
                break
        vis_ev = f"Live gameplay reaction peak around t={tp:.1f}s in Vice City."
        synth = _synthesize_clean_metadata(arch, vis_ev, streamer_handle=streamer_handle, idx=idx, is_spoiler=False)
        clean_segs = [{
            "start": round(st, 2),
            "end": round(en, 2),
            "duration": round(en - st, 2),
            "role": "CONTINUOUS_ARC",
            "spoken_text": raw_txt,
            "signal_tags_in_window": list(c.get("signal_tags") or []),
        }]
        rel_peak = _map_meme_timestamp(tp, clean_segs, c, tp)
        visual_note = f"Watch the reaction spike at {rel_peak:.0f}s."
        clips.append({
            "clip_number": idx,
            "candidate_id": c.get("candidate_id", f"cand_{idx}"),
            "title": synth["title"],
            "yt_title": synth["youtube_title"],
            "youtube_title": synth["youtube_title"],
            "narrative_archetype": arch,
            "hook_caption": synth["hook_caption"],
            "viral_caption": synth["hook_caption"],
            "short_description": synth["short_description"],
            "desc_line": synth["short_description"],
            "visual_value_note": visual_note,
            "comment_hook": synth["comment_bait_question"],
            "comment_bait_question": synth["comment_bait_question"],
            "is_story_spoiler": False,
            "is_nsfw_or_unsafe": False,
            "climax_quote": climax_q,
            "reaction_triggers": [{"quote": climax_q[:30], "sfx": sfx}] if climax_q else [],
            "memes": [{"timestamp": rel_peak, "file": sfx, "volume": 0.30}],
            "visual_evidence": vis_ev,
            "visual_event_description": vis_ev,
            "start_time": round(st, 2),
            "end_time": round(en, 2),
            "payoff_time": round(tp, 2),
            "total_duration_sec": round(en - st, 2),
            "segments": [{"start": round(st, 2), "end": round(en, 2), "role": "CONTINUOUS_ARC"}],
            "edl_segments": clean_segs,
            "virality_score": max(7.0, min(9.8, round(7.0 + float(c.get("virality_score", 1.5)) * 0.35, 1))),
            "cause_and_effect_setup": synth["short_description"],
            "assembled_spoken_script": raw_txt,
            "pre_hook_context_text": pre_ctx,
            "post_payoff_context_text": post_ctx,
            "signal_justification": _signal_justification_from_cand(c, clean_segs),
        })
    return {"clips": clips}


def normalize_director_clips(
    parsed: dict,
    candidates: list,
    meme_files: list,
    words: list | None = None,
    max_clips: int | None = None,
    streamer_handle: str = "",
    api_keys: list | None = None,
    mistral_keys: list | None = None,
) -> dict:
    """Enforce single-scene window bounds, tight 14s-40s pacing, crowd/cutscene scoring, and non-filler titles."""
    cand_map = {c.get("candidate_id"): c for c in candidates}
    meme_set = set(meme_files)
    default_sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_set else meme_files[0]
    w_list = words or []
    w_starts = [float(w.get("start", 0.0)) for w in w_list]
    if max_clips is None:
        _, max_clips = _target_clip_range(candidates)

    raw_clips = parsed.get("clips") if isinstance(parsed, dict) else []
    if not isinstance(raw_clips, list) or not raw_clips:
        return deterministic_candidate_fallback(candidates, meme_files, words=w_list, max_clips=max_clips, streamer_handle=streamer_handle)

    valid_clips = []
    for idx, cl in enumerate(raw_clips[:max(10, max_clips + 2)], start=1):
        if not isinstance(cl, dict) or cl.get("is_nsfw_or_unsafe") is True:
            continue
        cid = cl.get("candidate_id") or f"cand_{idx}"
        cand = cand_map.get(cid)
        if not cand and candidates:
            st_guess = float(cl.get("start_time") or (cl.get("segments") or [{}])[0].get("start", 0.0))
            cand = min(candidates, key=lambda x: abs(float(x.get("peak_time", 0.0)) - st_guess))

        w0 = float((cand or {}).get("window_start", 3.0))
        w1 = float((cand or {}).get("window_end", w0 + 44.0))
        payoff_t = float(cl.get("payoff_time") or (cand or {}).get("peak_time", w1 - 3.0))
        segs = [s for s in (cl.get("segments") or []) if isinstance(s, dict)]
        if not segs:
            st = float(cl.get("start_time") or w0)
            en = float(cl.get("end_time") or min(w1, st + 26.0))
            segs = [{"start": st, "end": en, "role": "CONTINUOUS_ARC"}]

        clean_segs = []
        for s in segs[:2]:
            s0 = max(max(3.0, w0 - 3.0), float(s.get("start", w0)))
            s1 = min(w1 + 3.0, float(s.get("end", s0 + 24.0)))
            if s1 - s0 >= 3.0:
                clean_segs.append({"start": round(s0, 2), "end": round(s1, 2), "role": s.get("role") or "CONTINUOUS_ARC"})
        if not clean_segs:
            s0 = round(max(3.0, w0), 2)
            s1 = round(min(w1, s0 + 26.0), 2)
            clean_segs = [{"start": s0, "end": s1, "role": "CONTINUOUS_ARC"}]

        if len(clean_segs) == 2 and (clean_segs[1]["start"] - clean_segs[0]["end"]) < 4.0:
            clean_segs = [{
                "start": clean_segs[0]["start"],
                "end": max(clean_segs[0]["end"], clean_segs[1]["end"]),
                "role": "CONTINUOUS_ARC",
            }]

        pre_ctx, post_ctx = "", ""
        if w_list and len(clean_segs) == 1:
            ns0, ns1, sp_txt, pre_ctx, post_ctx = _snap_boundary_with_words(
                clean_segs[0]["start"], clean_segs[0]["end"], w_list, w_starts, payoff_t, w0, w1
            )
            clean_segs[0]["start"], clean_segs[0]["end"] = ns0, ns1
            clean_segs[0]["spoken_text"] = sp_txt or (cand or {}).get("raw_text", "")
        else:
            if w_list and len(clean_segs) == 2:
                s0_a, _, _, pre_ctx, _ = _snap_boundary_with_words(
                    clean_segs[0]["start"], clean_segs[0]["end"], w_list, w_starts, clean_segs[0]["end"], w0, clean_segs[0]["end"]
                )
                _, s1_b, _, _, post_ctx = _snap_boundary_with_words(
                    clean_segs[1]["start"], clean_segs[1]["end"], w_list, w_starts, payoff_t, clean_segs[1]["start"], w1
                )
                if clean_segs[0]["end"] - s0_a >= 4.0:
                    clean_segs[0]["start"] = s0_a
                if s1_b - clean_segs[1]["start"] >= 4.0:
                    clean_segs[1]["end"] = s1_b
            for cs in clean_segs:
                cs["spoken_text"] = _words_text(w_list, cs["start"], cs["end"]) if w_list else ""

        for cs in clean_segs:
            cs["duration"] = round(cs["end"] - cs["start"], 2)
            cs["signal_tags_in_window"] = list((cand or {}).get("signal_tags") or [])

        arch_val = str(cl.get("narrative_archetype") or "OPEN_WORLD_CHAOS_OR_COP_CHASE")
        assembled = " ".join(cs.get("spoken_text") or "" for cs in clean_segs).strip() or (cand or {}).get("raw_text", "")
        vis_ev = str(cl.get("visual_evidence") or cl.get("visual_event_description") or f"Live gameplay moment at t={payoff_t:.1f}s.").strip()
        is_spoiler = bool(cl.get("is_story_spoiler", False) or arch_val == "STORY_CUTSCENE_OR_TWIST_REACTION")

        # Penalize STORY_CUTSCENE_OR_TWIST_REACTION clips where streamer is silent >40% of the window
        _vscore = float(cl.get("virality_score") or (cand or {}).get("est_virality_10") or 8.2)
        sil_ratio = float((cand or {}).get("streamer_silence_ratio") or 0.0)
        if arch_val == "STORY_CUTSCENE_OR_TWIST_REACTION" and sil_ratio > 0.40:
            _vscore = round(_vscore - 1.5, 2)
        if _vscore < 6.8:
            continue

        # Hard 14.0s floor & 40.0s max duration cap (ZERO 35s+ filler bloat!)
        tot_clip_dur = round(sum(cs["end"] - cs["start"] for cs in clean_segs), 2)
        if tot_clip_dur > 40.0 and clean_segs:
            excess = tot_clip_dur - 40.0
            if (clean_segs[-1]["end"] - clean_segs[-1]["start"]) - excess >= 4.0:
                clean_segs[-1]["end"] = round(clean_segs[-1]["end"] - excess, 2)
                clean_segs[-1]["duration"] = round(clean_segs[-1]["end"] - clean_segs[-1]["start"], 2)
                clean_segs[-1]["spoken_text"] = _words_text(w_list, clean_segs[-1]["start"], clean_segs[-1]["end"]) if w_list else clean_segs[-1].get("spoken_text", "")
                tot_clip_dur = round(sum(cs["end"] - cs["start"] for cs in clean_segs), 2)
        if tot_clip_dur < 14.0:
            continue

        synth = _synthesize_clean_metadata(arch_val, vis_ev, streamer_handle=streamer_handle, idx=idx, is_spoiler=is_spoiler)
        raw_title = _strip_unspoken_clickbait(str(cl.get("title") or "").strip(), assembled)
        raw_hook = str(cl.get("hook_caption") or "").strip()
        raw_yt = _strip_unspoken_clickbait(str(cl.get("youtube_title") or cl.get("yt_title") or "").strip(), assembled)[:68]

        needs_repair = (
            is_garbage_title_or_hook(raw_title, assembled)
            or is_garbage_title_or_hook(raw_hook, assembled)
            or (bool(raw_yt) and is_garbage_title_or_hook(raw_yt, assembled))
        )

        hook = synth["hook_caption"] if is_garbage_title_or_hook(raw_hook, assembled) else _guard_and_format_hook(raw_hook, assembled, raw_title or synth["title"])
        if is_garbage_title_or_hook(hook, assembled):
            hook = synth["hook_caption"]
        if is_garbage_title_or_hook(raw_title, assembled):
            raw_title = synth["title"]
        _yt_title = raw_yt if (raw_yt and not is_garbage_title_or_hook(raw_yt, assembled)) else synth["youtube_title"]

        memes_out = []
        raw_memes = cl.get("memes")
        for m in (raw_memes if isinstance(raw_memes, list) else []):
            if not isinstance(m, dict):
                continue
            mf = str(m.get("file") or m.get("sound") or m.get("name") or "")
            if mf not in meme_set:
                mf = default_sfx
            memes_out.append({
                "timestamp": _map_meme_timestamp(m.get("timestamp"), clean_segs, cand or {}, payoff_t),
                "file": mf,
                "volume": float(m.get("volume") or 0.30),
            })

        cause_setup = str(cl.get("cause_and_effect_setup") or "").strip()
        if len(cause_setup) < 16 or ROBOTIC_COPY_RE.search(cause_setup):
            cause_setup = synth["short_description"]

        visual_note = str(cl.get("visual_value_note") or "").strip()
        if not visual_note or "Watch for the peak moment mid-clip" in visual_note:
            visual_note = vis_ev or "Watch the live streamer reaction unfold here."
        short_desc = _build_short_description(cl, assembled, str(cl.get("climax_quote") or ""), vis_ev, arch=arch_val, streamer_handle=streamer_handle)

        _raw_comment = str(cl.get("comment_hook") or cl.get("comment_bait_question") or "").strip()
        if not _raw_comment or ROBOTIC_COPY_RE.search(_raw_comment) or re.match(r"^(would you have survived this|what would you have done here|what's the worst)\??$", _raw_comment, re.I):
            _raw_comment = synth["comment_bait_question"]

        valid_clips.append({
            "clip_number": len(valid_clips) + 1,
            "candidate_id": cid,
            "title": raw_title[:60],
            "yt_title": _yt_title[:68],
            "youtube_title": _yt_title[:68],
            "narrative_archetype": arch_val,
            "hook_caption": hook,
            "viral_caption": hook,
            "grounding_quote": str(cl.get("grounding_quote") or cl.get("climax_quote") or "").strip(),
            "desc_line": short_desc,
            "short_description": short_desc,
            "visual_value_note": visual_note,
            "comment_hook": _raw_comment,
            "comment_bait_question": _raw_comment,
            "is_story_spoiler": is_spoiler,
            "is_nsfw_or_unsafe": False,
            "climax_quote": str(cl.get("climax_quote") or "").strip(),
            "reaction_triggers": cl.get("reaction_triggers") if isinstance(cl.get("reaction_triggers"), list) else [],
            "memes": memes_out,
            "visual_evidence": vis_ev,
            "visual_event_description": vis_ev,
            "start_time": clean_segs[0]["start"],
            "end_time": clean_segs[-1]["end"],
            "payoff_time": round(payoff_t, 2),
            "total_duration_sec": tot_clip_dur,
            "segments": [{"start": cs["start"], "end": cs["end"], "role": cs["role"]} for cs in clean_segs],
            "edl_segments": clean_segs,
            "virality_score": _vscore,
            "cause_and_effect_setup": cause_setup,
            "assembled_spoken_script": assembled,
            "pre_hook_context_text": pre_ctx,
            "post_payoff_context_text": post_ctx,
            "signal_justification": _signal_justification_from_cand(cand or {}, clean_segs),
            "_needs_title_repair": needs_repair,
        })
        if len(valid_clips) >= max_clips:
            break

    # 1 fast targeted repair prompt for any clip whose LLM title/hook failed validation
    to_repair = [
        {"candidate_id": c["candidate_id"], "arch": c["narrative_archetype"], "visual_ev": c["visual_event_description"], "transcript": c["assembled_spoken_script"]}
        for c in valid_clips if c.get("_needs_title_repair")
    ]
    if to_repair and (api_keys or mistral_keys):
        repaired_map = _repair_bad_titles_with_llm(to_repair, api_keys or [], mistral_keys or [], streamer_handle=streamer_handle)
        for c in valid_clips:
            rep = repaired_map.get(c["candidate_id"])
            if not rep:
                continue
            asm = c["assembled_spoken_script"]
            if rep.get("title") and not is_garbage_title_or_hook(rep["title"], asm):
                c["title"] = _strip_unspoken_clickbait(str(rep["title"]), asm)[:60]
            if rep.get("yt_title") and not is_garbage_title_or_hook(rep["yt_title"], asm):
                c["yt_title"] = _strip_unspoken_clickbait(str(rep["yt_title"]), asm)[:68]
                c["youtube_title"] = c["yt_title"]
            if rep.get("hook_caption") and not is_garbage_title_or_hook(rep["hook_caption"], asm):
                c["hook_caption"] = _guard_and_format_hook(str(rep["hook_caption"]), asm, c["title"])
                c["viral_caption"] = c["hook_caption"]
            if rep.get("desc_line") and not ROBOTIC_COPY_RE.search(str(rep["desc_line"])):
                c["desc_line"] = str(rep["desc_line"]).strip()
                c["short_description"] = c["desc_line"]
            if rep.get("comment_hook") and not ROBOTIC_COPY_RE.search(str(rep["comment_hook"])):
                c["comment_hook"] = str(rep["comment_hook"]).strip()
                c["comment_bait_question"] = c["comment_hook"]

    for c in valid_clips:
        c.pop("_needs_title_repair", None)

    return {"clips": valid_clips} if valid_clips else deterministic_candidate_fallback(candidates, meme_files, words=w_list, max_clips=max_clips, streamer_handle=streamer_handle)


def main():
    parser = argparse.ArgumentParser(description="Run Multimodal Vision Director on GTA 6 3x3 candidate storyboards.")
    parser.add_argument("--candidates", default="/files/temp/gta6_candidates.json")
    parser.add_argument("--summary", default="/files/temp/global_summary.json")
    parser.add_argument("--transcript", default="")
    parser.add_argument("--out", default="/files/temp/gta6_vision_director_out.json")
    parser.add_argument("--meme-dir", default="/files/memes")
    parser.add_argument("--no-llm", action="store_true", help="Skip external LLM call and run deterministic storyboard EDL fallback")
    args = parser.parse_args()

    cand_doc = _load_json(args.candidates) or {}
    candidates = cand_doc.get("candidates") or []
    summary_doc = _load_json(args.summary) or {}
    override_doc = _load_json("/files/temp/iteration_dataset_override.json") if not args.transcript else None
    tx_cand = args.transcript or ((override_doc or {}).get("transcript_path") if isinstance(override_doc, dict) else "")
    tx_path = tx_cand if (tx_cand and os.path.exists(tx_cand)) else "/files/temp/transcript.json"
    tx_doc = _load_json(tx_path) or {}
    words = tx_doc.get("words") or (tx_doc.get("x_groq") or {}).get("words") or []
    meme_files = list_meme_files(args.meme_dir)
    min_clips, max_clips = _target_clip_range(candidates, cand_doc)

    if not candidates:
        out_payload = {"clips": [], "meta": {"error": "no_candidates"}}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out_payload, f, indent=2)
        print(json.dumps({"text": json.dumps(out_payload), "meta": out_payload["meta"]}))
        return

    meta = {"provider": "deterministic_fallback", "grids_attached": 0, "min_clips": min_clips, "max_clips": max_clips}
    streamer_handle = _extract_streamer_handle(cand_doc, summary_doc)
    api_keys = []
    m_keys = []
    parsed = None
    if not args.no_llm:
        api_keys = collect_gemini_keys()
        m_keys = collect_mistral_keys()
        prompt_text = build_prompt_text(summary_doc, candidates, meme_files, min_clips=min_clips, max_clips=max_clips, streamer_handle=streamer_handle)
        interleaved_parts, _ = _interleave_vision_parts(summary_doc, candidates, meme_files, min_clips=min_clips, max_clips=max_clips, streamer_handle=streamer_handle)
        raw_txt = None
        if api_keys:
            raw_txt, meta = call_gemini_vision(interleaved_parts, candidates, api_keys, DEFAULT_MODELS)
        if not raw_txt and m_keys:
            raw_txt, meta = call_mistral_fallback(prompt_text, m_keys, model="mistral-large-latest")
        if raw_txt:
            cleaned = raw_txt.replace("```json", "").replace("```", "").strip()
            parsed = None
            try:
                parsed = json.loads(cleaned)
            except Exception:
                m_obj = re.search(r"\{[\s\S]*\}", cleaned)
                m_arr = re.search(r"\[[\s\S]*\]", cleaned)
                cand_str = (m_arr.group(0) if (cleaned.startswith("[") and m_arr) else (m_obj.group(0) if m_obj else (m_arr.group(0) if m_arr else cleaned)))
                try:
                    parsed = json.loads(cand_str)
                except Exception:
                    parsed = None
            if isinstance(parsed, list):
                parsed = {"clips": parsed}

    has_llm_clips = bool(isinstance(parsed, dict) and isinstance(parsed.get("clips"), list) and len(parsed["clips"]) > 0)
    normalized = (
        normalize_director_clips(
            parsed, candidates, meme_files, words=words, max_clips=max_clips,
            streamer_handle=streamer_handle, api_keys=api_keys, mistral_keys=m_keys,
        )
        if has_llm_clips
        else deterministic_candidate_fallback(candidates, meme_files, words=words, max_clips=max_clips, streamer_handle=streamer_handle)
    )
    if not has_llm_clips:
        meta["fallback_used"] = True
        if meta.get("provider") == "gemini_vision":
            meta["provider"] = "deterministic_fallback_after_vision_0_clips"

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"clips": normalized["clips"], "meta": meta}, f, indent=2)

    print(json.dumps({
        "text": json.dumps({"clips": normalized["clips"]}),
        "clips_count": len(normalized["clips"]),
        "meta": meta,
    }))


if __name__ == "__main__":
    main()
