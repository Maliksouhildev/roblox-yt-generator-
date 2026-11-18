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

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

GEMINI_KEY_FILES = [
    "/files/temp/n8n_gemini_key.txt",
    "/files/gemini_key.txt",
    "/files/temp/gemini_key.txt",
    "/files/temp/all_ai_creds.json",
]

DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
]

GTA6_ARCHETYPES = [
    "OPEN_WORLD_CHAOS_OR_COP_CHASE",
    "LEONIDA_NPC_ENCOUNTER_OR_ROAST",
    "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    "HUBRIS_WAGER_WASTED_KARMA",
    "COMEDIC_BANTER_OR_SARCASM",
    "STORY_CUTSCENE_OR_TWIST_REACTION",
]

DANGLING_HOOK_END_RE = re.compile(
    r"\b(TO|A|AN|THE|OF|IN|ON|AT|FOR|WITH|FROM|BY|AND|OR|BUT|IF|IS|ARE|WAS|WERE|"
    r"DO|DOES|DID|NOT|WANT|GOING|HAVE|HAS|MY|YOUR|OUR|THEIR|THIS|THAT)$",
    re.I,
)

BANNED_HOOK_RE = re.compile(
    r"^(I CALLED TIME OUT|HE ACTUALLY FELL FOR IT|THAT DOES NOT COUNT|"
    r"MY WORST BLUNDER|MUST WATCH MOMENT|VIRAL MOMENT|NO WORDS|"
    r"NO AUDIO FOUND|NO TRANSCRIPT|UNDEFINED|NULL|ERROR|WATCH THIS CLIP)$",
    re.I,
)


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


def build_prompt_text(summary_doc: dict, candidates: list, meme_files: list) -> str:
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
        "You are given 8 empirically detected Peak Candidates, each with a 3x3 JPEG storyboard grid\n"
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
        "2. SINGLE-SCENE CONTIGUITY & TOP 5 CLIPS: Pick the BEST 4 to 5 distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end]. NEVER stitch minutes apart!\n"
        "   Prefer 1 continuous segment `[start_time, end_time]` (22s-44s). Split into 2 segments ONLY inside that same\n"
        "   window to drop a >4.0s dead silent driving/walking pause gap.\n"
        "3. BOUNDARY INTEGRITY: Snap start and end to natural Whisper sentence/reaction boundaries.\n"
        "4. GTA 6 LAUNCH ARCHETYPES (Pick distinct archetypes across clips):\n"
        "   - `OPEN_WORLD_CHAOS_OR_COP_CHASE`: 6-star chases, stunts, crashes, gator attacks, explosions.\n"
        "   - `LEONIDA_NPC_ENCOUNTER_OR_ROAST`: crazy Florida/Leonida NPC behavior (`[NPC_OR_OTHER_VOICE]`) or roast.\n"
        "   - `HOW_TO_TIP_OR_SECRET_DISCOVERY`: hidden location/trick/weapon/myth test (prioritize if `[CHAT_QUESTION_CLUSTER]` present).\n"
        "   - `HUBRIS_WAGER_WASTED_KARMA`: cocky boast/bet -> instant fail, WASTED, or BUSTED.\n"
        "   - `COMEDIC_BANTER_OR_SARCASM`: storytelling or voice-chat punchline.\n"
        "   - `STORY_CUTSCENE_OR_TWIST_REACTION`: Lucia & Jason twist + explosive shock (MUST set `is_story_spoiler: true` and NEVER spoil in `hook_caption`!).\n"
        "5. COMPLETE METADATA IN ONE PASS (No downstream merge agent exists!):\n"
        "   - `hook_caption`: 3-6 WORDS ALL CAPS (<=32 chars), zero dangling endings (never end on TO/THE/A/IN/ON), grounded in the 3x3 grid + speech!\n"
        "   - `visual_value_note`: short 1-line transformative tip or 'Watch for...' callout.\n"
        "   - `comment_bait_question`: simple engaging question for comments (e.g. 'Would you survive 6 stars here?').\n"
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
        "      \"title\": \"Short Clean Title\",\n"
        "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
        "      \"hook_caption\": \"SIX STAR POLICE CHASE CHAOS\",\n"
        "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge at 0:18.\",\n"
        "      \"comment_bait_question\": \"Could you escape a 6-star chase here?\",\n"
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


def _interleave_vision_parts(summary_doc: dict, candidates: list, meme_files: list) -> tuple[list, int]:
    """Build multimodal Vision parts interleaving each candidate's 50s transcript + its 3x3 JPEG grid."""
    game = summary_doc.get("game") or "Gaming / GTA 6"
    vibe = summary_doc.get("vibe") or "Chaotic High-Energy"
    gs = summary_doc.get("global_summary") or "Live gaming stream."
    themes = ", ".join(summary_doc.get("key_themes") or [])
    memes_str = ", ".join(meme_files[:20])

    header_text = (
        "You are the Lead Multimodal Vision Director for a viral GTA 6 & Gaming Shorts channel.\n"
        "Below are 8 empirically detected Peak Candidates. Each candidate is presented with its\n"
        "speaker-tagged transcript (`[NPC_OR_OTHER_VOICE]` vs `[STREAMER]`) IMMEDIATELY followed by\n"
        "its 960x540 `3x3` JPEG storyboard contact sheet (`t=XXX.Xs` burned on every tile).\n\n"
        f"GLOBAL CONTEXT:\n- Game: {game}\n- Vibe: {vibe}\n- Summary: {gs}\n- Themes: {themes}\n\n"
        f"AVAILABLE SFX MEME FILES: {memes_str}\n\n"
        "STRICT SELECTION & EDITING RULES:\n"
        "1. M-RATED / NSFW & MENU VISION SHIELD (CRITICAL FOR LAUNCH DAY):\n"
        "   Inspect EVERY 3x3 grid first! Immediately REJECT (or set `is_nsfw_or_unsafe: true`) any candidate showing:\n"
        "   - Nudity, strip clubs, sexually explicit M-rated scenes, or graphic TOS-violating gore.\n"
        "   - Chrome/Edge browsers, Twitch/YouTube chat dashboards, Discord, pause/ESC/settings menus, or static non-gameplay screens.\n"
        "   - Boring opening title cards or slow exposition cutscenes without massive streamer shock.\n"
        "2. SINGLE-SCENE CONTIGUITY & TOP 5 CLIPS: Pick the BEST 4 to 5 distinct candidates.\n"
        "   Each clip MUST stay strictly inside ONE candidate's [window_start, window_end]. NEVER stitch minutes apart!\n"
        "   Prefer 1 continuous segment `[start_time, end_time]` (22s-44s). Split into 2 segments ONLY inside that same\n"
        "   window to drop a >4.0s dead silent driving/walking pause gap.\n"
        "3. BOUNDARY INTEGRITY: Snap start and end to natural Whisper sentence/reaction boundaries.\n"
        "4. GTA 6 LAUNCH ARCHETYPES (Pick distinct archetypes across clips):\n"
        "   - `OPEN_WORLD_CHAOS_OR_COP_CHASE`: 6-star chases, stunts, crashes, gator attacks, explosions.\n"
        "   - `LEONIDA_NPC_ENCOUNTER_OR_ROAST`: crazy Florida/Leonida NPC behavior (`[NPC_OR_OTHER_VOICE]`) or roast.\n"
        "   - `HOW_TO_TIP_OR_SECRET_DISCOVERY`: hidden location/trick/weapon/myth test (prioritize if `[CHAT_QUESTION_CLUSTER]` present).\n"
        "   - `HUBRIS_WAGER_WASTED_KARMA`: cocky boast/bet -> instant fail, WASTED, or BUSTED.\n"
        "   - `COMEDIC_BANTER_OR_SARCASM`: storytelling or voice-chat punchline.\n"
        "   - `STORY_CUTSCENE_OR_TWIST_REACTION`: Lucia & Jason twist + explosive shock (MUST set `is_story_spoiler: true` and NEVER spoil in `hook_caption`!).\n"
        "5. COMPLETE METADATA IN ONE PASS (No downstream merge agent exists!):\n"
        "   - `hook_caption`: 3-6 WORDS ALL CAPS (<=32 chars), zero dangling endings (never end on TO/THE/A/IN/ON), grounded in the 3x3 grid + speech!\n"
        "   - `visual_value_note`: short 1-line transformative tip or 'Watch for...' callout.\n"
        "   - `comment_bait_question`: simple engaging question for comments.\n"
        "   - `is_story_spoiler`: boolean; `is_nsfw_or_unsafe`: boolean (must be false for selected clips).\n"
        "   - `climax_quote`, `reaction_triggers`, `memes`, `visual_evidence`, `cause_and_effect_setup`.\n"
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
            "      \"title\": \"Short Clean Title\",\n"
            "      \"narrative_archetype\": \"OPEN_WORLD_CHAOS_OR_COP_CHASE\",\n"
            "      \"hook_caption\": \"SIX STAR POLICE CHASE CHAOS\",\n"
            "      \"visual_value_note\": \"Watch the police cruiser launch off the bridge.\",\n"
            "      \"comment_bait_question\": \"Could you escape a 6-star chase here?\",\n"
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
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {k}"},
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
    for model in models:
        for key in api_keys:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                txt = data["candidates"][0]["content"]["parts"][0]["text"]
                return txt, {"provider": "gemini_vision", "model": model, "grids_attached": attached}
            except urllib.error.HTTPError as he:
                last_err = f"HTTP {he.code} ({model})"
                if he.code in (429, 500, 502, 503, 504):
                    continue
            except Exception as ex:
                last_err = f"{type(ex).__name__}: {ex}"
                continue
    return None, {"provider": "none", "error": last_err or "no_keys", "grids_attached": attached}


def _guard_and_format_hook(raw_hook: str, raw_text: str, title: str) -> str:
    """Fix 1.4: 3-6 words (<=32 chars), semantic homophone cleanup, and zero dangling function endings."""
    clean = re.sub(r"[^A-Za-z0-9'\s!?-]", " ", str(raw_hook or "")).upper()
    clean = re.sub(r"\s+", " ", clean).strip()
    ctx = f"{title} {raw_text}".lower()
    if "coolest" in ctx:
        clean = re.sub(r"\bCOLDEST\b", "COOLEST", clean)
    clean = re.sub(r"\bRAGE\s+BADER\b", "RAGE BAITER", clean)

    words = clean.split()
    if len(words) > 6:
        words = words[:6]
    while words and len(" ".join(words)) > 32 and len(words) > 3:
        words.pop()
    while words and DANGLING_HOOK_END_RE.match(words[-1]) and len(words) > 3:
        words.pop()
    if not words or len(words) < 3 or DANGLING_HOOK_END_RE.match(words[-1]):
        return _safe_hook_from_text(raw_text, title)
    return " ".join(words)


def _safe_hook_from_text(text: str, title: str) -> str:
    clean_words = re.findall(r"[A-Za-z0-9']+", str(text or ""))
    stop = {"AND", "THE", "THIS", "THAT", "WITH", "JUST", "LIKE", "YEAH", "OKAY", "UH", "UM", "IF", "OR", "TO", "OF", "IN", "ON", "A", "AN", "FOR", "AT"}
    kept = [w.upper() for w in clean_words if w.upper() not in stop][:5]
    while kept and DANGLING_HOOK_END_RE.match(kept[-1]) and len(kept) > 3:
        kept.pop()
    while kept and len(" ".join(kept)) > 32 and len(kept) > 3:
        kept.pop()
    if len(kept) >= 3 and not DANGLING_HOOK_END_RE.match(kept[-1]):
        return " ".join(kept)
    t_words = [w.upper() for w in re.findall(r"[A-Za-z0-9']+", str(title or ""))][:5]
    while t_words and DANGLING_HOOK_END_RE.match(t_words[-1]) and len(t_words) > 3:
        t_words.pop()
    return " ".join(t_words)[:32] if len(t_words) >= 3 else "WILD STREAMER REACTION MOMENT"


def _strip_speaker_prefix(line: str) -> str:
    s = re.sub(r"^\[[^\]]*\[[^\]]+\]\]\s*", "", str(line or ""))
    s = re.sub(r"^\[[^\]]+\]\s*", "", s)
    return s.lstrip("] ").strip()


def deterministic_candidate_fallback(candidates: list, meme_files: list) -> dict:
    """Grounded deterministic single-scene fallback spanning the 6 GTA 6 Launch Archetypes."""
    sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_files else meme_files[0]
    arch_pool = [
        "OPEN_WORLD_CHAOS_OR_COP_CHASE",
        "HUBRIS_WAGER_WASTED_KARMA",
        "COMEDIC_BANTER_OR_SARCASM",
        "STORY_CUTSCENE_OR_TWIST_REACTION",
        "HOW_TO_TIP_OR_SECRET_DISCOVERY",
    ]
    clips = []
    for idx, c in enumerate(candidates[:5], start=1):
        w0 = float(c.get("window_start", 10.0))
        w1 = float(c.get("window_end", w0 + 36.0))
        tp = float(c.get("peak_time", (w0 + w1) * 0.5))
        # Clamp strictly to 26-38s contiguous single-scene arc centered before peak
        st = max(w0, round(tp - 24.0, 2))
        en = min(w1, round(st + 34.0, 2))
        if en - st < 24.0:
            st = max(w0, round(en - 28.0, 2))
        lines = c.get("transcript_lines") or []
        raw_txt = c.get("raw_text") or ""
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
            if stripped and len(stripped.split()) >= 3:
                climax_q = stripped[:70]
                break
        hook = _guard_and_format_hook(climax_q or raw_txt, raw_txt, f"PEAK MOMENT {idx}")
        rel_peak = max(3.0, min(round((en - st) - 1.5, 1), round(tp - st, 1)))
        is_spoiler = (arch == "STORY_CUTSCENE_OR_TWIST_REACTION")
        clips.append({
            "clip_number": idx,
            "candidate_id": c.get("candidate_id", f"cand_{idx}"),
            "title": f"GTA6_Peak_Clip_{idx}",
            "narrative_archetype": arch,
            "hook_caption": hook,
            "visual_value_note": f"Watch closely around {rel_peak:.1f}s for the main reaction beat.",
            "comment_bait_question": "What would you have done in this spot?",
            "is_story_spoiler": is_spoiler,
            "is_nsfw_or_unsafe": False,
            "climax_quote": climax_q,
            "reaction_triggers": [{"quote": climax_q[:30], "sfx": sfx}] if climax_q else [],
            "memes": [{"timestamp": rel_peak, "file": sfx, "volume": 0.30}],
            "visual_evidence": f"3x3 storyboard peak at t={tp:.1f}s (fallback offline mode).",
            "start_time": round(st, 2),
            "end_time": round(en, 2),
            "payoff_time": round(tp, 2),
            "segments": [{"start": round(st, 2), "end": round(en, 2), "role": "CONTINUOUS_ARC"}],
            "virality_score": max(7.5, min(9.8, round(7.2 + float(c.get("virality_score", 1.5)) * 0.35, 1))),
            "cause_and_effect_setup": f"Empirical multimodal peak at t={tp:.1f}s (z_db={c.get('z_db', 0):.1f}, z_chat={c.get('z_chat_lagged', 0):.1f}).",
            "assembled_spoken_script": raw_txt,
        })
    return {"clips": clips}


def normalize_director_clips(parsed: dict, candidates: list, meme_files: list) -> dict:
    """Enforce single-scene window bounds, <=2 segments max, valid meme files & clean hooks."""
    cand_map = {c.get("candidate_id"): c for c in candidates}
    meme_set = set(meme_files)
    default_sfx = "vine-boom-sound-effect_KT89XIq.mp3" if "vine-boom-sound-effect_KT89XIq.mp3" in meme_set else meme_files[0]

    raw_clips = parsed.get("clips") if isinstance(parsed, dict) else []
    if not isinstance(raw_clips, list) or not raw_clips:
        return deterministic_candidate_fallback(candidates, meme_files)

    valid_clips = []
    for idx, cl in enumerate(raw_clips[:6], start=1):
        if not isinstance(cl, dict) or cl.get("is_nsfw_or_unsafe") is True:
            continue
        cid = cl.get("candidate_id") or f"cand_{idx}"
        cand = cand_map.get(cid)
        if not cand and candidates:
            # Match closest candidate by start_time
            st_guess = float(cl.get("start_time") or (cl.get("segments") or [{}])[0].get("start", 0.0))
            cand = min(candidates, key=lambda x: abs(float(x.get("peak_time", 0.0)) - st_guess))

        w0 = float((cand or {}).get("window_start", 3.0))
        w1 = float((cand or {}).get("window_end", w0 + 50.0))
        segs = [s for s in (cl.get("segments") or []) if isinstance(s, dict)]
        if not segs:
            st = float(cl.get("start_time") or w0)
            en = float(cl.get("end_time") or min(w1, st + 34.0))
            segs = [{"start": st, "end": en, "role": "CONTINUOUS_ARC"}]

        # Enforce max 2 micro-cuts inside the SAME candidate window (no multi-minute stitching!)
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

        total_dur = sum(s["end"] - s["start"] for s in clean_segs)
        if total_dur < 22.0 and cand:
            clean_segs[-1]["end"] = round(min(w1 + 4.0, clean_segs[-1]["end"] + (24.0 - total_dur)), 2)

        hook = _guard_and_format_hook(str(cl.get("hook_caption") or ""), (cand or {}).get("raw_text", ""), cl.get("title", f"CLIP {idx}"))
        if bool(BANNED_HOOK_RE.match(hook)):
            hook = _safe_hook_from_text((cand or {}).get("raw_text", ""), cl.get("title", f"CLIP {idx}"))

        memes_out = []
        for m in (cl.get("memes") or []):
            if not isinstance(m, dict):
                continue
            mf = str(m.get("file") or m.get("sound") or m.get("name") or "")
            if mf not in meme_set:
                mf = default_sfx
            memes_out.append({
                "timestamp": round(max(0.5, float(m.get("timestamp") or 10.0)), 2),
                "file": mf,
                "volume": float(m.get("volume") or 0.30),
            })
        if not memes_out:
            rel_p = max(2.0, round(float((cand or {}).get("peak_time", clean_segs[0]["end"] - 2.0)) - clean_segs[0]["start"], 1))
            memes_out = [{"timestamp": rel_p, "file": default_sfx, "volume": 0.30}]

        arch_val = str(cl.get("narrative_archetype") or "OPEN_WORLD_CHAOS_OR_COP_CHASE")
        is_spoiler = bool(cl.get("is_story_spoiler", False) or arch_val == "STORY_CUTSCENE_OR_TWIST_REACTION")
        cause_setup = str(cl.get("cause_and_effect_setup") or "").strip()
        if len(cause_setup) < 15:
            cause_setup = f"Setup in window [{w0:.1f}s-{w1:.1f}s] builds into high-intensity payoff."

        valid_clips.append({
            "clip_number": len(valid_clips) + 1,
            "candidate_id": cid,
            "title": str(cl.get("title") or f"GTA6_Clip_{idx}").strip()[:60],
            "narrative_archetype": arch_val,
            "hook_caption": hook,
            "visual_value_note": str(cl.get("visual_value_note") or "Watch for the peak moment mid-clip.").strip(),
            "comment_bait_question": str(cl.get("comment_bait_question") or "Would you have survived this?").strip(),
            "is_story_spoiler": is_spoiler,
            "is_nsfw_or_unsafe": False,
            "climax_quote": str(cl.get("climax_quote") or "").strip(),
            "reaction_triggers": cl.get("reaction_triggers") if isinstance(cl.get("reaction_triggers"), list) else [],
            "memes": memes_out,
            "visual_evidence": str(cl.get("visual_evidence") or "").strip(),
            "start_time": clean_segs[0]["start"],
            "end_time": clean_segs[-1]["end"],
            "payoff_time": round(float(cl.get("payoff_time") or (cand or {}).get("peak_time", clean_segs[-1]["end"] - 2.0)), 2),
            "segments": clean_segs,
            "virality_score": float(cl.get("virality_score") or 8.5),
            "cause_and_effect_setup": cause_setup,
            "assembled_spoken_script": (cand or {}).get("raw_text", ""),
        })
        if len(valid_clips) >= 5:
            break

    return {"clips": valid_clips} if valid_clips else deterministic_candidate_fallback(candidates, meme_files)


def main():
    parser = argparse.ArgumentParser(description="Run Multimodal Vision Director on GTA 6 3x3 candidate storyboards.")
    parser.add_argument("--candidates", default="/files/temp/gta6_candidates.json")
    parser.add_argument("--summary", default="/files/temp/global_summary.json")
    parser.add_argument("--out", default="/files/temp/gta6_vision_director_out.json")
    parser.add_argument("--meme-dir", default="/files/memes")
    parser.add_argument("--no-llm", action="store_true", help="Skip external LLM call and run deterministic storyboard EDL fallback")
    args = parser.parse_args()

    cand_doc = _load_json(args.candidates) or {}
    candidates = cand_doc.get("candidates") or []
    summary_doc = _load_json(args.summary) or {}
    meme_files = list_meme_files(args.meme_dir)

    if not candidates:
        out_payload = {"clips": [], "meta": {"error": "no_candidates"}}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out_payload, f, indent=2)
        print(json.dumps({"text": json.dumps(out_payload), "meta": out_payload["meta"]}))
        return

    meta = {"provider": "deterministic_fallback", "grids_attached": 0}
    parsed = None
    if not args.no_llm:
        api_keys = collect_gemini_keys()
        prompt_text = build_prompt_text(summary_doc, candidates, meme_files)
        interleaved_parts, _ = _interleave_vision_parts(summary_doc, candidates, meme_files)
        raw_txt = None
        if api_keys:
            raw_txt, meta = call_gemini_vision(interleaved_parts, candidates, api_keys, DEFAULT_MODELS)
        if not raw_txt:
            m_keys = collect_mistral_keys()
            if m_keys:
                raw_txt, meta = call_mistral_fallback(prompt_text, m_keys, model="mistral-large-latest")
        if raw_txt:
            cleaned = raw_txt.replace("```json", "").replace("```", "").strip()
            m = re.search(r"\{[\s\S]*\}", cleaned)
            try:
                parsed = json.loads(m.group(0) if m else cleaned)
            except Exception:
                parsed = None

    has_llm_clips = bool(isinstance(parsed, dict) and isinstance(parsed.get("clips"), list) and len(parsed["clips"]) > 0)
    normalized = normalize_director_clips(parsed, candidates, meme_files) if has_llm_clips else deterministic_candidate_fallback(candidates, meme_files)
    if not has_llm_clips:
        meta["fallback_used"] = True
        if meta.get("provider") == "gemini_vision":
            meta["provider"] = "deterministic_fallback_after_vision_0_clips"

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"clips": normalized["clips"], "meta": meta}, f, indent=2)

    # Print exact `{ "text": "<json_string>", "clips": ..., "meta": ... }` so `5. Split Clips` consumes `$input.all()` identically
    print(json.dumps({
        "text": json.dumps({"clips": normalized["clips"]}),
        "clips_count": len(normalized["clips"]),
        "meta": meta,
    }))


if __name__ == "__main__":
    main()
