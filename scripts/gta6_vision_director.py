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
    "LIKE|LOVE|HATE|WANT|NEED|KNOW|THINK|FEEL|SEE|SAW|LOOK|WATCH|GOT|GET|"
    "MAKE|MADE|TAKE|TOOK|GIVE|GAVE|PUT|SAY|SAID|TELL|TOLD|FIND|FOUND|LET|KEEP|TRY|TRIED|USE|USED"
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


def _target_clip_range(candidates: list, cand_doc: dict | None = None) -> tuple[int, int]:
    if isinstance(cand_doc, dict) and cand_doc.get("recommended_max_clips"):
        return (
            int(cand_doc.get("recommended_min_clips") or 1),
            int(cand_doc.get("recommended_max_clips") or 5),
        )
    max_t = max([float(c.get("window_end", 0.0)) for c in (candidates or [])] + [0.0])
    if max_t > 0.0 and max_t < 480.0 and len(candidates) <= 4:
        return 1, 2
    if max_t > 0.0 and max_t <= 1500.0 and len(candidates) <= 6:
        return 2, 3
    return 4, 5


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


def build_prompt_text(summary_doc: dict, candidates: list, meme_files: list, min_clips: int = 4, max_clips: int = 5) -> str:
    game = summary_doc.get("game") or "Gaming / GTA 6"
    vibe = summary_doc.get("vibe") or "Chaotic High-Energy"
    gs = summary_doc.get("global_summary") or "Live gaming stream."
    themes = ", ".join(summary_doc.get("key_themes") or [])

    cand_blocks = []
    for c in candidates:
        cid = c.get("candidate_id", f"cand_{c.get('rank')}")
        w0, w1 = c.get("window_start", 0.0), c.get("window_end", 0.0)
        tp = c.get("peak_time", 0.0)
        chats = " | ".join(str(m) for m in (c.get("chat_samples") or [])[:3])
        tx_lines = "\n    ".join((c.get("transcript_lines") or [])[:24]) or "(No clear speech in window)"
        has_grid = bool(c.get("grid_path") and os.path.exists(c["grid_path"]))
        q_flag = " | [CHAT_QUESTION_CLUSTER]" if c.get("chat_question_cluster") else ""
        cand_blocks.append(
            f"### CANDIDATE {cid} (GridAttached={has_grid}{q_flag})\n"
            f"Window: [{w0:.2f}s - {w1:.2f}s] | Peak: t={tp:.1f}s | Virality={c.get('virality_score', 0):.2f} "
            f"| z_dB={c.get('z_db', 0):.1f} | z_chat_lag={c.get('z_chat_lagged', 0):.1f} | z_face={c.get('z_face', 0):.1f}\n"
            f"ChatSamples: {chats or 'None'}\n"
            f"Timestamps burned on grid tiles: {c.get('frame_timestamps', [])}\n"
            f"Transcript:\n    {tx_lines}"
        )

    memes_str = ", ".join(meme_files[:20])
    return (
        "You are the Lead Multimodal Vision Director for a viral GTA 6 & Gaming Shorts channel.\n"
        f"You are given {len(candidates)} empirically detected Peak Candidates, each with a 3x3 JPEG storyboard grid\n"
        "(9 frames labeled `t=XXX.Xs` at the top-left of each tile) AND its speaker-tagged transcript\n"
        "(`[NPC_OR_OTHER_VOICE]` vs `[STREAMER]`).\n\n"
        f"GLOBAL CONTEXT:\n- Game: {game}\n- Vibe: {vibe}\n- Summary: {gs}\n- Themes: {themes}\n\n"
        f"AVAILABLE SFX MEME FILES: {memes_str}\n\n"
        "STRICT SELECTION & EDITING RULES:\n"
        "1. M-RATED / NSFW & MENU VISION SHIELD (CRITICAL FOR LAUNCH DAY):\n"
        "   Inspect EVERY 3x3 grid first! Immediately REJECT (or set `is_nsfw_or_unsafe: true`) any candidate showing:\n"
        "   - Nudity, strip clubs, sexually explicit M-rated scenes, or graphic TOS-violating gore.\n"
        "   - Chrome/Edge browsers, Twitch/YouTube chat dashboards, Discord, pause/ESC/settings menus, or static non-gameplay screens.\n"
        "   - Boring opening title cards or slow exposition cutscenes without massive streamer shock.\n"
        f"2. SINGLE-SCENE CONTIGUITY & LONG-FORM TARGET (34s-55s): Pick the BEST {min_clips} to {max_clips} distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end]. NEVER stitch minutes apart!\n"
        "   Target 34.0s to 55.0s total duration (sweet spot 38s-50s) with >= 2 story beats (Setup/Escalation -> Payoff).\n"
        "   Split into 2 segments inside that same candidate window ONLY to drop a >4.0s dead silent driving/walking pause.\n"
        "3. BOUNDARY INTEGRITY & ANTI-MUMBLE ENDINGS: Snap start and end cleanly to terminal sentences, keeping 2.5s-4.5s\n"
        "   aftermath after payoff. NEVER end on weak filler ('Okay.', 'Alright.', 'Anyway.') or trailing silence > 1.8s.\n"
        "4. GTA 6 LAUNCH ARCHETYPES (Pick distinct archetypes across clips — NEVER repeat the same archetype twice when 3+ clips!):\n"
        "   - `OPEN_WORLD_CHAOS_OR_COP_CHASE`: 6-star chases, stunts, crashes, gator attacks, explosions.\n"
        "   - `LEONIDA_NPC_ENCOUNTER_OR_ROAST`: crazy Florida/Leonida NPC behavior (`[NPC_OR_OTHER_VOICE]`) or roast.\n"
        "   - `HOW_TO_TIP_OR_SECRET_DISCOVERY`: hidden location/trick/weapon/myth test (prioritize if `[CHAT_QUESTION_CLUSTER]` present).\n"
        "   - `HUBRIS_WAGER_WASTED_KARMA`: cocky boast/bet -> instant fail, WASTED, or BUSTED.\n"
        "   - `COMEDIC_BANTER_OR_SARCASM`: storytelling or voice-chat punchline.\n"
        "   - `STORY_CUTSCENE_OR_TWIST_REACTION`: Lucia & Jason twist + explosive shock (MUST set `is_story_spoiler: true` and NEVER spoil in `hook_caption`!).\n"
        "5. COMPLETE METADATA IN ONE PASS (No downstream merge agent exists!):\n"
        "   - `title`: Catchy 3-7 word YouTube Short title specifically describing THIS clip's action/joke. NEVER use fake clickbait words\n"
        "     like 'Glitch', 'Hack', 'Exploit', 'Mod', 'Secret Code', 'Infinite Money', or 'Banned' unless actually spoken in transcript!\n"
        "   - `hook_caption`: Punchy 3-5 WORDS ALL CAPS headline (<=28 chars) summarizing the visual stakes/event, NEVER slicing a raw clause mid-sentence or ending on a transitive verb (LIKE/WANT/SEE/KNOW/GOT/TO/THE/IN)!\n"
        "   - `short_description`: 2-3 engaging sentences written specifically for THIS Short describing what happens visually in THIS scene and what the streamer/NPCs say (do NOT summarize unrelated parts of the stream!).\n"
        "   - `visual_value_note`: short 1-line transformative tip or 'Watch for...' callout specific to this clip.\n"
        "   - `comment_bait_question`: fun specific question for comments directly about THIS clip (never generic).\n"
        "   - `is_story_spoiler`: boolean; `is_nsfw_or_unsafe`: boolean (must be false for selected clips).\n"
        "   - `climax_quote`: exact short verbatim quote spoken at the payoff spike.\n"
        "   - `reaction_triggers`: 1-2 short verbatim quotes `[{\"quote\": \"...\", \"sfx\": \"<valid meme file>\"}]`.\n"
        "   - `memes`: 1-2 SFX entries `[{\"timestamp\": <sec offset from clip start>, \"file\": \"<valid filename>\", \"volume\": 0.30}]`.\n"
        "   - `visual_evidence`: 1 sentence citing what is seen across the 3x3 grid tiles.\n\n"
        "CANDIDATES:\n" + "\n\n".join(cand_blocks) + "\n\n"
        "OUTPUT STRICT JSON ONLY (NO MARKDOWN FENCES):\n"
        "{\n"
        "  \"clips\": [\n"
        "    {\n"
        "      \"clip_number\": 1,\n"
        "      \"candidate_id\": \"cand_1\",\n"
        "      \"title\": \"Insane 6 Star Vice City Escape\",\n"
        "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
        "      \"hook_caption\": \"SIX STAR POLICE CHASE CHAOS\",\n"
        "      \"short_description\": \"When a routine getaway goes sideways in Vice City, a 6-star police blockade sends cruisers flying off the bridge. Streamer loses it as everything explodes at the last second.\",\n"
        "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge right before the crash.\",\n"
        "      \"comment_bait_question\": \"Could you actually survive that 6-star bridge blockade?\",\n"
        "      \"is_story_spoiler\": false,\n"
        "      \"is_nsfw_or_unsafe\": false,\n"
        "      \"climax_quote\": \"exact verbatim payoff words\",\n"
        "      \"reaction_triggers\": [{\"quote\": \"wait what\", \"sfx\": \"shocked-sound-effect.mp3\"}],\n"
        "      \"memes\": [{\"timestamp\": 14.5, \"file\": \"vine-boom-sound-effect_KT89XIq.mp3\", \"volume\": 0.30}],\n"
        "      \"visual_evidence\": \"What happens visually on the 3x3 tiles.\",\n"
        "      \"start_time\": 120.4,\n"
        "      \"end_time\": 154.2,\n"
        "      \"payoff_time\": 148.0,\n"
        "      \"segments\": [{\"start\": 120.4, \"end\": 154.2, \"role\": \"CONTINUOUS_ARC\"}],\n"
        "      \"virality_score\": 9.1,\n"
        "      \"cause_and_effect_setup\": \"Setup boasty stunt -> immediate 6-star wreck payoff.\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )


def _interleave_vision_parts(summary_doc: dict, candidates: list, meme_files: list, min_clips: int = 4, max_clips: int = 5) -> tuple[list, int]:
    """Build multimodal Vision parts interleaving each candidate's 50s transcript + its 3x3 JPEG grid."""
    game = summary_doc.get("game") or "Gaming / GTA 6"
    vibe = summary_doc.get("vibe") or "Chaotic High-Energy"
    gs = summary_doc.get("global_summary") or "Live gaming stream."
    themes = ", ".join(summary_doc.get("key_themes") or [])
    memes_str = ", ".join(meme_files[:20])

    header_text = (
        "You are the Lead Multimodal Vision Director for a viral GTA 6 & Gaming Shorts channel.\n"
        f"Below are {len(candidates)} empirically detected Peak Candidates. Each candidate is presented with its\n"
        "speaker-tagged transcript (`[NPC_OR_OTHER_VOICE]` vs `[STREAMER]`) IMMEDIATELY followed by\n"
        "its 960x540 `3x3` JPEG storyboard contact sheet (`t=XXX.Xs` burned on every tile).\n\n"
        f"GLOBAL CONTEXT:\n- Game: {game}\n- Vibe: {vibe}\n- Summary: {gs}\n- Themes: {themes}\n\n"
        f"AVAILABLE SFX MEME FILES: {memes_str}\n\n"
        "STRICT SELECTION & EDITING RULES:\n"
        "1. M-RATED / NSFW, BOOT/EULA & MENU VISION SHIELD (CRITICAL FOR LAUNCH DAY):\n"
        "   Inspect EVERY 3x3 grid first! Immediately REJECT (or set `is_nsfw_or_unsafe: true`) any candidate showing:\n"
        "   - Nudity, strip clubs, sexually explicit M-rated scenes, or graphic TOS-violating gore.\n"
        "   - Game boot/splash screens, epilepsy/seizure health warnings, EULA/terms acceptance, brightness/audio calibration menus, blank/static loading screens, or Rockstar logo intros.\n"
        "   - Chrome/Edge browsers, Twitch/YouTube chat dashboards, Discord, pause/ESC/settings/map menus, or static non-gameplay screens.\n"
        "   - Aimless walking/driving or calm shop visits with zero comedic/chaotic payoff, or passive NPC cutscenes where the streamer is silent or barely reacting (require clear streamer vocal/facial/chat reaction spikes!).\n"
        f"2. SINGLE-SCENE CONTIGUITY & LONG-FORM TARGET (34s-55s): Pick the BEST {min_clips} to {max_clips} distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end]. NEVER stitch minutes apart!\n"
        "   Target 34.0s to 55.0s total duration (sweet spot 38s-50s) with >= 2 story beats (Setup/Escalation -> Payoff).\n"
        "   Split into 2 segments ONLY inside that same window to drop a >4.0s dead silent pause gap.\n"
        "3. BOUNDARY INTEGRITY & ANTI-MUMBLE ENDINGS: Snap start and end to natural Whisper sentence/reaction boundaries, keeping 2.5s-4.5s aftermath.\n"
        "4. GTA 6 LAUNCH ARCHETYPES (Pick distinct archetypes — NEVER repeat twice when 3+ clips!):\n"
        "   - `OPEN_WORLD_CHAOS_OR_COP_CHASE`: 6-star chases, stunts, crashes, gator attacks, explosions.\n"
        "   - `LEONIDA_NPC_ENCOUNTER_OR_ROAST`: crazy Florida/Leonida NPC behavior (`[NPC_OR_OTHER_VOICE]`) or roast.\n"
        "   - `HOW_TO_TIP_OR_SECRET_DISCOVERY`: hidden location/trick/weapon/myth test (prioritize if `[CHAT_QUESTION_CLUSTER]` present).\n"
        "   - `HUBRIS_WAGER_WASTED_KARMA`: cocky boast/bet -> instant fail, WASTED, or BUSTED.\n"
        "   - `COMEDIC_BANTER_OR_SARCASM`: storytelling or voice-chat punchline.\n"
        "   - `STORY_CUTSCENE_OR_TWIST_REACTION`: Lucia & Jason twist + explosive shock (MUST set `is_story_spoiler: true` and NEVER spoil in `hook_caption`!).\n"
        "5. COMPLETE METADATA IN ONE PASS (ZERO HALLUCINATION & BRAND-SAFE):\n"
        "   - NEVER invent glitches, bets, acid labs, or fake NPC hostility! Every title, hook, and description MUST strictly reflect literal, verified actions from the transcript and 3x3 frames.\n"
        "   - BRAND-SAFE: NEVER include YouTube-throttled drug/explicit terms (`COKE`, `COCAINE`, `SUICIDE`, etc.) in titles or hooks.\n"
        "   - `title`: Catchy 3-7 word YouTube Short title specifically describing THIS clip (NEVER 'GTA6_Peak_Clip_1').\n"
        "   - `hook_caption`: Punchy 3-5 WORDS ALL CAPS headline (<=28 chars), COMPLETE thought with zero transitive verb or dangling endings (never end on LIKE/WANT/KNOW/SEE/GOT/TO/THE/IN)!\n"
        "   - `short_description`: 2-3 engaging factual sentences written specifically for THIS Short.\n"
        "   - `visual_value_note`: short 1-line transformative tip or 'Watch for...' callout for this clip.\n"
        "   - `comment_bait_question`: fun question directly referencing THIS clip.\n"
        "   - `is_story_spoiler`: boolean; `is_nsfw_or_unsafe`: boolean (must be false for selected clips).\n"
        "   - `climax_quote`, `reaction_triggers`, `memes` (use `[]` when dialogue is clear/calm; only add SFX on real punchlines), `visual_evidence`, `cause_and_effect_setup`.\n"
    )
    parts = [{"text": header_text}]
    attached = 0
    for c in candidates:
        cid = c.get("candidate_id", f"cand_{c.get('rank')}")
        w0, w1 = c.get("window_start", 0.0), c.get("window_end", 0.0)
        tp = c.get("peak_time", 0.0)
        chats = " | ".join(str(m) for m in (c.get("chat_samples") or [])[:3])
        tx_lines = "\n    ".join((c.get("transcript_lines") or [])[:24]) or "(No clear speech in window)"
        has_grid = bool(c.get("grid_path") and os.path.exists(c["grid_path"]))
        q_flag = " | [CHAT_QUESTION_CLUSTER]" if c.get("chat_question_cluster") else ""
        block = (
            f"### CANDIDATE {cid} (GridAttached={has_grid}{q_flag})\n"
            f"Window: [{w0:.2f}s - {w1:.2f}s] | Peak: t={tp:.1f}s | Virality={c.get('virality_score', 0):.2f} "
            f"| z_dB={c.get('z_db', 0):.1f} | z_chat_lag={c.get('z_chat_lagged', 0):.1f} | z_face={c.get('z_face', 0):.1f}\n"
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
            "      \"title\": \"Insane 6 Star Vice City Escape\",\n"
            "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
            "      \"hook_caption\": \"SIX STAR POLICE CHASE CHAOS\",\n"
            "      \"short_description\": \"Things go completely off the rails when a routine getaway turns into a 6-star police blockade right on the Vice City bridge.\",\n"
            "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge right before the crash.\",\n"
            "      \"comment_bait_question\": \"Could you escape that 6-star chase here?\",\n"
            "      \"is_story_spoiler\": false,\n"
            "      \"is_nsfw_or_unsafe\": false,\n"
            "      \"climax_quote\": \"exact verbatim payoff words\",\n"
            "      \"reaction_triggers\": [{\"quote\": \"wait what\", \"sfx\": \"shocked-sound-effect.mp3\"}],\n"
            "      \"memes\": [{\"timestamp\": 14.5, \"file\": \"vine-boom-sound-effect_KT89XIq.mp3\", \"volume\": 0.30}],\n"
            "      \"visual_evidence\": \"What happens visually on the 3x3 tiles.\",\n"
            "      \"start_time\": 120.4,\n"
            "      \"end_time\": 154.2,\n"
            "      \"payoff_time\": 148.0,\n"
            "      \"segments\": [{\"start\": 120.4, \"end\": 154.2, \"role\": \"CONTINUOUS_ARC\"}],\n"
            "      \"virality_score\": 9.1,\n"
            "      \"cause_and_effect_setup\": \"Setup boasty stunt -> immediate 6-star wreck payoff.\"\n"
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


def _guard_and_format_hook(raw_hook: str, raw_text: str, title: str) -> str:
    """Part 1.3: Punchy 3-5 word headline (<=28 chars), zero dangling transitive verbs/auxiliaries, zero ungrounded clickbait."""
    de_baited = _strip_unspoken_clickbait(str(raw_hook or ""), raw_text)
    clean = re.sub(r"[^A-Za-z0-9'\s!?-]", " ", de_baited).upper()
    clean = re.sub(r"[-]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    ctx = f"{title} {raw_text}".lower()
    if "coolest" in ctx:
        clean = re.sub(r"\bCOLDEST\b", "COOLEST", clean)
    clean = re.sub(r"\bRAGE\s+BADER\b", "RAGE BAITER", clean)

    words = clean.split()
    while words and words[0] in {"AND", "SO", "BUT", "BECAUSE", "THEN", "OR", "WELL"} and len(words) > 3:
        words.pop(0)
    if re.match(r"^(PEAK MOMENT|CLIP)\b", " ".join(words)):
        words = []
    if len(words) > 5:
        words = words[:5]
    while words and len(" ".join(words)) > 28 and len(words) > 3:
        words.pop()
    while words and DANGLING_HOOK_END_RE.match(words[-1]) and len(words) > 3:
        words.pop()
    while words and len(" ".join(words)) > 28 and len(words) > 1:
        words.pop()
    if (
        not words
        or len(words) < 3
        or len(words) > 5
        or len(" ".join(words)) > 28
        or DANGLING_HOOK_END_RE.match(words[-1])
    ):
        return _safe_hook_from_text(raw_text, _strip_unspoken_clickbait(title, raw_text))
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


def _smart_clip_title(hook: str, raw_txt: str, climax_q: str, arch: str, idx: int) -> str:
    """Build a descriptive, non-generic Short title from actual speech/action."""
    cand_src = climax_q or raw_txt or hook
    words = re.findall(r"[A-Za-z0-9']+", str(cand_src or ""))
    keep = words[:7]
    while len(keep) > 3 and DANGLING_HOOK_END_RE.match(keep[-1]):
        keep.pop()
    if len(keep) >= 3:
        title_str = " ".join(w.capitalize() if not w.isupper() or len(w) > 3 else w for w in keep)
        return title_str[:55].strip()
    h_words = [w.capitalize() for w in re.findall(r"[A-Za-z0-9']+", hook or "")]
    if len(h_words) >= 2:
        return (" ".join(h_words) + " in GTA 6")[:55]
    arch_label = {
        "OPEN_WORLD_CHAOS_OR_COP_CHASE": "Vice City Police Chaos Moment",
        "LEONIDA_NPC_ENCOUNTER_OR_ROAST": "Wild Leonida NPC Encounter",
        "HOW_TO_TIP_OR_SECRET_DISCOVERY": "Hidden GTA 6 Detail Found",
        "HUBRIS_WAGER_WASTED_KARMA": "Instant Karma Moment in GTA 6",
        "COMEDIC_BANTER_OR_SARCASM": "Hilarious GTA 6 Streamer Reaction",
        "STORY_CUTSCENE_OR_TWIST_REACTION": "Shocking GTA 6 Story Reaction",
    }.get(arch, f"Crazy GTA 6 Live Moment {idx}")
    return arch_label


def _build_short_description(cl: dict, cand_raw_txt: str = "", climax_q: str = "", visual_note: str = "") -> str:
    """Guarantee a concrete, Short-specific description grounded in this clip's events and dialogue."""
    explicit = str(cl.get("short_description") or "").strip()
    if explicit and len(explicit) >= 25 and not re.search(r"fallback offline mode|watch closely around", explicit, re.I):
        return explicit
    setup = str(cl.get("cause_and_effect_setup") or "").strip()
    if setup and re.search(r"Empirical multimodal peak|Setup in window", setup, re.I):
        setup = ""
    vis_ev = str(cl.get("visual_evidence") or "").strip()
    if vis_ev and re.search(r"fallback offline mode|3x3 storyboard peak", vis_ev, re.I):
        vis_ev = ""
    speech_snip = str(climax_q or cl.get("climax_quote") or cand_raw_txt or "").strip()
    speech_snip = re.sub(r"\s+", " ", speech_snip)[:160].strip()
    parts = []
    if setup:
        parts.append(setup)
    if vis_ev and vis_ev != setup:
        parts.append(vis_ev)
    if visual_note and not re.search(r"Watch closely around \d", visual_note, re.I):
        parts.append(visual_note)
    if not parts and speech_snip:
        parts.append(f'Wild live moment: "{speech_snip}"')
    elif speech_snip and speech_snip.lower() not in " ".join(parts).lower() and len(" ".join(parts)) < 120:
        parts.append(f'Highlight quote: "{speech_snip}"')
    return " ".join(parts).strip() or "Unfiltered live GTA 6 reaction caught on stream."


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
            if (before_end - st) >= 34.0 and payoff_t <= before_end + 1.0:
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
    Part 1.1 & 1.5: Snap [st, en] cleanly to Whisper word/sentence boundaries targeting 34.0s-55.0s:
    - Start on terminal punctuation [.!?] or pause >= 0.42s without leading filler/ellipsis.
    - End on terminal punctuation [.!?] preserving 2.5s-4.5s aftermath, <= 1.8s trailing silence, zero weak mumble tails.
    """
    if not words:
        return round(st, 2), round(en, 2), "", "", ""
    st, en = _trim_leading_dead_air(st, en, words, payoff_t)

    max_end = float(words[-1].get("end", hi_bound))
    lo = max(3.0, lo_bound - 4.0)
    hi = min(max_end, hi_bound + 6.0)
    if words:
        first_win_w = next((w for w in words if float(w.get("end", 0.0)) >= lo), None)
        last_win_w = next((w for w in reversed(words) if float(w.get("start", 0.0)) <= hi), None)
        if first_win_w and float(first_win_w.get("start", lo)) - lo > 2.5:
            lo = max(lo, float(first_win_w["start"]) - 0.15)
        if last_win_w and hi - float(last_win_w.get("end", hi)) > 2.5:
            hi = min(hi, float(last_win_w["end"]) + 0.45)
        st = max(lo, st)

    # Target ~42s start lead if window currently <36s
    if payoff_t > 0.0 and (en - st) < 36.0:
        st = max(lo, min(st, payoff_t - 40.0))

    # 1. Find clean start candidate near `st`
    clean_starts = []
    idx0 = max(0, bisect_left(w_starts, max(lo, st - 10.0)))
    for i in range(idx0, len(words)):
        ws = float(words[i].get("start", 0.0))
        if ws > st + 12.0:
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
            span_ok = (hi - ws) >= 34.0 or ws <= lo + 3.0
            if span_ok:
                clean_starts.append((abs(ws - st) + (0.0 if ends_term else 2.5) + ell_pen, max(lo, max(3.0, ws - 0.08))))
    if clean_starts:
        clean_starts.sort(key=lambda x: x[0])
        st = round(clean_starts[0][1], 2)

    # 2. Ensure payoff aftermath (target 2.5s - 4.5s after payoff_t), duration 34.0s-55.0s, and strong terminal sentence
    min_dur_end = st + 34.5
    pref_end = max(min_dur_end, (payoff_t + 3.5) if payoff_t > st else (st + 44.0))
    max_target_end = min(hi, st + 54.5)
    min_target_end = min(max_target_end, min_dur_end)

    clean_ends = []
    idx_e = max(0, bisect_left(w_starts, st + 28.0))
    for i in range(idx_e, len(words)):
        we = float(words[i].get("end", words[i].get("start", 0.0)))
        if we > max_target_end:
            break
        if we < st + 32.5 and max_target_end >= st + 34.0:
            continue
        tok = str(words[i].get("word", "")).strip()
        # Look back up to 3 words to avoid ending on a weak 1-3 word filler sentence like "Okay." / "Alright."
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
            pen = (0.0 if ends_term else 3.0) + (18.0 if is_weak_mumble else 0.0) + (8.0 if (payoff_t > st and we < payoff_t + 2.2 and we < max_end - 2.0) else 0.0)
            clean_ends.append((abs(we - min(max_target_end, pref_end)) + pen, min(hi, we + 0.35)))
    if clean_ends:
        clean_ends.sort(key=lambda x: x[0])
        en = round(clean_ends[0][1], 2)
    else:
        en = round(min(max_target_end, max(min_target_end, en)), 2)

    # Trim trailing dead air > 1.8s past last spoken word unconditionally (never pad silent tail)
    tail_ws = [w for w in words if st <= float(w.get("end", 0.0)) <= en]
    if tail_ws:
        last_w_end = float(tail_ws[-1].get("end", en))
        if en - last_w_end > 1.8:
            en = round(last_w_end + 0.45, 2)

    if en - st < 34.0 and st - lo > 1.0:
        need = 34.5 - (en - st)
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
) -> dict:
    """Grounded deterministic single-scene fallback spanning the 6 GTA 6 Launch Archetypes."""
    sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_files else meme_files[0]
    arch_pool = [
        "OPEN_WORLD_CHAOS_OR_COP_CHASE",
        "HUBRIS_WAGER_WASTED_KARMA",
        "COMEDIC_BANTER_OR_SARCASM",
        "STORY_CUTSCENE_OR_TWIST_REACTION",
        "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    ]
    w_list = words or []
    w_starts = [float(w.get("start", 0.0)) for w in w_list]
    if max_clips is None:
        _, max_clips = _target_clip_range(candidates)

    clips = []
    for idx, c in enumerate(candidates[:max_clips], start=1):
        w0 = float(c.get("window_start", 10.0))
        w1 = float(c.get("window_end", w0 + 85.0))
        tp = float(c.get("peak_time", (w0 + w1) * 0.5))
        # Part 1.1: Target 34.0s-55.0s long-form Shorts arc (sweet spot 38s-50s) centered before payoff
        st = max(w0, round(tp - 38.0, 2))
        en = min(w1, round(tp + 4.0, 2))
        if en - st < 38.0:
            st = max(w0, round(en - 44.0, 2))
            if en - st < 34.0:
                en = min(w1, round(st + 42.0, 2))
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
        smart_title = _strip_unspoken_clickbait(_smart_clip_title("", raw_txt, climax_q, arch, idx), raw_txt) or f"Crazy Leonida Moment {idx}"
        hook = _guard_and_format_hook(smart_title, raw_txt, smart_title)
        clean_segs = [{
            "start": round(st, 2),
            "end": round(en, 2),
            "duration": round(en - st, 2),
            "role": "CONTINUOUS_ARC",
            "spoken_text": raw_txt,
            "signal_tags_in_window": list(c.get("signal_tags") or []),
        }]
        rel_peak = _map_meme_timestamp(tp, clean_segs, c, tp)
        is_spoiler = (arch == "STORY_CUTSCENE_OR_TWIST_REACTION")
        visual_note = f'Wait for the reaction at {rel_peak:.0f}s when "{climax_q}" hits.' if climax_q else "Wait for the live reaction spike mid-clip."
        short_desc = _build_short_description({}, raw_txt, climax_q, visual_note)
        if len(short_desc) < 20:
            short_desc = f'High-energy {arch.replace("_", " ").lower()} reaction peaking around {tp:.0f}s on stream.'
        bait_q = f'Did you see that coming at "{climax_q[:38]}"?' if climax_q else "How would you react if this happened live?"
        vis_ev = f"3x3 storyboard centered around reaction peak at t={tp:.1f}s with active webcam reaction."
        clips.append({
            "clip_number": idx,
            "candidate_id": c.get("candidate_id", f"cand_{idx}"),
            "title": smart_title,
            "narrative_archetype": arch,
            "hook_caption": hook,
            "short_description": short_desc,
            "visual_value_note": visual_note,
            "comment_bait_question": bait_q,
            "is_story_spoiler": is_spoiler,
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
            "virality_score": max(7.5, min(9.8, round(7.2 + float(c.get("virality_score", 1.5)) * 0.35, 1))),
            "cause_and_effect_setup": short_desc,
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
) -> dict:
    """Enforce single-scene window bounds, <=2 segments max, valid meme files & clean hooks."""
    cand_map = {c.get("candidate_id"): c for c in candidates}
    meme_set = set(meme_files)
    default_sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_set else meme_files[0]
    w_list = words or []
    w_starts = [float(w.get("start", 0.0)) for w in w_list]
    if max_clips is None:
        _, max_clips = _target_clip_range(candidates)

    raw_clips = parsed.get("clips") if isinstance(parsed, dict) else []
    if not isinstance(raw_clips, list) or not raw_clips:
        return deterministic_candidate_fallback(candidates, meme_files, words=w_list, max_clips=max_clips)

    valid_clips = []
    for idx, cl in enumerate(raw_clips[:max(6, max_clips + 1)], start=1):
        if not isinstance(cl, dict) or cl.get("is_nsfw_or_unsafe") is True:
            continue
        cid = cl.get("candidate_id") or f"cand_{idx}"
        cand = cand_map.get(cid)
        if not cand and candidates:
            st_guess = float(cl.get("start_time") or (cl.get("segments") or [{}])[0].get("start", 0.0))
            cand = min(candidates, key=lambda x: abs(float(x.get("peak_time", 0.0)) - st_guess))

        w0 = float((cand or {}).get("window_start", 3.0))
        w1 = float((cand or {}).get("window_end", w0 + 50.0))
        payoff_t = float(cl.get("payoff_time") or (cand or {}).get("peak_time", w1 - 4.0))
        segs = [s for s in (cl.get("segments") or []) if isinstance(s, dict)]
        if not segs:
            st = float(cl.get("start_time") or w0)
            en = float(cl.get("end_time") or min(w1, st + 34.0))
            segs = [{"start": st, "end": en, "role": "CONTINUOUS_ARC"}]

        # Enforce max 2 micro-cuts inside the SAME candidate window (drop <4.0s micro-gaps into 1 continuous arc!)
        clean_segs = []
        for s in segs[:2]:
            s0 = max(max(3.0, w0 - 4.0), float(s.get("start", w0)))
            s1 = min(w1 + 4.0, float(s.get("end", s0 + 28.0)))
            if s1 - s0 >= 4.0:
                clean_segs.append({"start": round(s0, 2), "end": round(s1, 2), "role": s.get("role") or "CONTINUOUS_ARC"})
        if not clean_segs:
            s0 = round(max(3.0, w0), 2)
            s1 = round(min(w1, s0 + 34.0), 2)
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
            if len(clean_segs) == 2 and (clean_segs[1]["start"] - clean_segs[0]["end"]) < 4.0:
                clean_segs = [{
                    "start": clean_segs[0]["start"],
                    "end": max(clean_segs[0]["end"], clean_segs[1]["end"]),
                    "role": "CONTINUOUS_ARC",
                }]
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
                    if clean_segs[0]["end"] - s0_a >= 6.0:
                        clean_segs[0]["start"] = s0_a
                    if s1_b - clean_segs[1]["start"] >= 6.0:
                        clean_segs[1]["end"] = s1_b
                for cs in clean_segs:
                    cs["spoken_text"] = _words_text(w_list, cs["start"], cs["end"]) if w_list else ""

        total_dur = sum(s["end"] - s["start"] for s in clean_segs)
        if total_dur < 34.0 and cand:
            word_min = float(w_list[0].get("start", w0)) if w_list else max(3.0, w0 - 6.0)
            word_max = float(w_list[-1].get("end", w1)) + 0.45 if w_list else (w1 + 6.0)
            need = 36.0 - total_dur
            new_st = max(max(3.0, word_min, w0 - 6.0), clean_segs[0]["start"] - need * 0.7)
            rem = max(0.0, need - (clean_segs[0]["start"] - new_st))
            clean_segs[0]["start"] = round(new_st, 2)
            if rem > 0.2:
                clean_segs[-1]["end"] = round(min(word_max, w1 + 6.0, clean_segs[-1]["end"] + rem), 2)
            for cs in clean_segs:
                cs["spoken_text"] = _words_text(w_list, cs["start"], cs["end"]) if w_list else cs.get("spoken_text", "")

        for cs in clean_segs:
            cs["duration"] = round(cs["end"] - cs["start"], 2)
            cs["signal_tags_in_window"] = list((cand or {}).get("signal_tags") or [])

        arch_val = str(cl.get("narrative_archetype") or "OPEN_WORLD_CHAOS_OR_COP_CHASE")
        assembled = " ".join(cs.get("spoken_text") or "" for cs in clean_segs).strip() or (cand or {}).get("raw_text", "")
        raw_title = _strip_unspoken_clickbait(str(cl.get("title") or "").strip(), assembled)
        if not raw_title or re.match(r"^(?:GTA6_Peak_Clip_\d+|GTA6_Clip_\d+|clip|output_clip)$", raw_title, re.I):
            raw_title = _strip_unspoken_clickbait(_smart_clip_title(str(cl.get("hook_caption") or ""), assembled, str(cl.get("climax_quote") or ""), arch_val, idx), assembled)
        hook = _guard_and_format_hook(str(cl.get("hook_caption") or ""), assembled, raw_title or f"CLIP {idx}")
        if bool(BANNED_HOOK_RE.match(hook)):
            hook = _safe_hook_from_text(assembled, raw_title or f"CLIP {idx}")

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
        # Respect explicit `"memes": []` from the LLM — never force vine-boom on calm dialogue!

        used_arches = {vc["narrative_archetype"] for vc in valid_clips}
        if len(raw_clips) >= 3 and arch_val in used_arches and len(used_arches) < 3:
            lines_c = (cand or {}).get("transcript_lines") or []
            has_npc = any("[NPC_OR_OTHER_VOICE]" in ln for ln in lines_c)
            alt_order = [
                "HOW_TO_TIP_OR_SECRET_DISCOVERY",
                "HUBRIS_WAGER_WASTED_KARMA",
                "LEONIDA_NPC_ENCOUNTER_OR_ROAST" if has_npc else "STORY_CUTSCENE_OR_TWIST_REACTION",
                "OPEN_WORLD_CHAOS_OR_COP_CHASE",
                "COMEDIC_BANTER_OR_SARCASM",
            ]
            for alt_a in alt_order:
                if alt_a not in used_arches:
                    arch_val = alt_a
                    break
        is_spoiler = bool(cl.get("is_story_spoiler", False) or arch_val == "STORY_CUTSCENE_OR_TWIST_REACTION")
        cause_setup = str(cl.get("cause_and_effect_setup") or "").strip()
        if len(cause_setup) < 20:
            cause_setup = f"Setup in window [{w0:.1f}s-{w1:.1f}s] builds into live reaction payoff."

        raw_title = _strip_unspoken_clickbait(raw_title or _smart_clip_title(hook, assembled, str(cl.get("climax_quote") or ""), arch_val, idx), assembled) or "Wild GTA 6 Stream Moment"
        visual_note = str(cl.get("visual_value_note") or "").strip()
        if not visual_note or "Watch for the peak moment mid-clip" in visual_note:
            visual_note = str(cl.get("visual_evidence") or "").strip() or "Watch the live streamer reaction unfold here."
        short_desc = _build_short_description(cl, assembled, str(cl.get("climax_quote") or ""), visual_note)
        vis_ev = str(cl.get("visual_evidence") or cl.get("visual_event_description") or f"3x3 grid storyboard at t={payoff_t:.1f}s.").strip()
        tot_clip_dur = round(sum(cs["end"] - cs["start"] for cs in clean_segs), 2)

        valid_clips.append({
            "clip_number": len(valid_clips) + 1,
            "candidate_id": cid,
            "title": raw_title[:60],
            "narrative_archetype": arch_val,
            "hook_caption": hook,
            "short_description": short_desc,
            "visual_value_note": visual_note,
            "comment_bait_question": str(cl.get("comment_bait_question") or "Would you have survived this?").strip(),
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
            "virality_score": float(cl.get("virality_score") or 8.5),
            "cause_and_effect_setup": cause_setup,
            "assembled_spoken_script": assembled,
            "pre_hook_context_text": pre_ctx,
            "post_payoff_context_text": post_ctx,
            "signal_justification": _signal_justification_from_cand(cand or {}, clean_segs),
        })
        if len(valid_clips) >= max_clips:
            break

    return {"clips": valid_clips} if valid_clips else deterministic_candidate_fallback(candidates, meme_files, words=w_list, max_clips=max_clips)


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
    parsed = None
    if not args.no_llm:
        api_keys = collect_gemini_keys()
        prompt_text = build_prompt_text(summary_doc, candidates, meme_files, min_clips=min_clips, max_clips=max_clips)
        interleaved_parts, _ = _interleave_vision_parts(summary_doc, candidates, meme_files, min_clips=min_clips, max_clips=max_clips)
        raw_txt = None
        if api_keys:
            raw_txt, meta = call_gemini_vision(interleaved_parts, candidates, api_keys, DEFAULT_MODELS)
        if not raw_txt:
            m_keys = collect_mistral_keys()
            if m_keys:
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
        normalize_director_clips(parsed, candidates, meme_files, words=words, max_clips=max_clips)
        if has_llm_clips
        else deterministic_candidate_fallback(candidates, meme_files, words=words, max_clips=max_clips)
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
