import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wf_p = os.path.join(ROOT, 'workflows', 'workflow.json')
with open(wf_p, 'r', encoding='utf-8') as f:
    wf = json.load(f)

nodes = {n['name']: n for n in wf['nodes']}

ts_p = os.path.join(ROOT, 'workflows', 'workflow_bypassed.ts')
with open(ts_p, 'r', encoding='utf-8') as f:
    ts_code = f.read()

checks = [
    # 1. Scout prompt checks
    ("1. Prepare Scout Prompt", "STRICT ANTI-IDLE & ANTI-STATIC", "Scout anti-idle rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-LOADING SCREEN", "Scout anti-loading screen rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-SLOW-UI & TRADE MENUS", "Scout anti-slow-ui rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-CONVERSATIONAL BANTER & DONATION AFTERMATH", "Scout anti-conversational banter rule"),
    ("1. Prepare Scout Prompt", "SATISFYING CLIMAX ONLY", "Scout satisfying climax rule"),
    ("1. Prepare Scout Prompt", "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL", "Scout Archetype 1 Continuous Gameplay"),
    ("1. Prepare Scout Prompt", "HUBRIS_WAGER_INSTANT_KARMA", "Scout Archetype 3 Hubris Wager"),
    ("1. Prepare Scout Prompt", "22-45s", "Scout 22-45s flexible Shorts target"),
    ("1. Prepare Scout Prompt", "Math.min(4, Math.max(1, charChunks))", "Scout chunking parity (sandbox == production)"),

    # 2. Director prompt checks
    ("3. Prepare Director Prompt", "ZERO DEAD TIME AT HOOK", "Director zero dead time rule"),
    ("3. Prepare Director Prompt", "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL", "Director 6-archetype blueprint"),
    ("3. Prepare Director Prompt", "FLASHFORWARD_MYSTERY_INVESTIGATION", "Director Archetype 5 Flash-Forward"),
    ("3. Prepare Director Prompt", "22s and 45s", "Director 22s-45s Shorts duration window"),
    ("3. Prepare Director Prompt", "SENTENCE-BOUNDARY", "Director zero mid-sentence cuts rule"),
    ("3. Prepare Director Prompt", "SEMANTIC ENTITY CONTINUITY", "Director entity continuity & anti-stitching guidance"),

    # 3. Split Clips checks (Bug A & Bug B)
    ("5. Split Clips", "OUTRO_PANHANDLING_RE", "SplitClips outro panhandling filter"),
    ("5. Split Clips", "checkSemanticEntityContinuity", "SplitClips semantic entity continuity validator"),
    ("5. Split Clips", "_total_dur >= 22.0", "SplitClips 22s minimum Shorts duration floor"),
    ("5. Split Clips", "totalSegDur > 42.0", "SplitClips 42s maximum Shorts duration cap"),
    ("5. Split Clips", "minPayoffGap", "SplitClips payoff-centered multi-arc distinctness check"),

    # 4. Extract Viral Segments checks (Bug A)
    ("6. Extract Viral Segments", "BUFFER = 0.12", "ExtractViral tight 0.12 buffer"),
    ("6. Extract Viral Segments", "deadTrimmedIntervals", "ExtractViral >5s dead-air trimming"),
    ("6. Extract Viral Segments", "totalClipDur > 42.0", "ExtractViral 32s-42s duration enforcement"),

    # 5. Global Summary & Context Merge & Guard Retries (Bug C & D)
    ("1. Extract Audio", "dynaudnorm=f=150:g=13:p=0.92:m=5.0", "Audio Extract highpass+dynaudnorm normalization"),
    ("1. Global Summary AI", "Save Whisper Transcript", "Global Summary reads Save Whisper Transcript directly"),
    ("DRY_RUN_SCRIPT_ONLY", "function verifyHook(", "DryRun Hook anti-hallucination check"),
    ("DRY_RUN_SCRIPT_ONLY", "n8n_sandbox_edl_preview.json", "DryRun writes n8n_sandbox_edl_preview.json"),
    ("Guard Summary Retries", "$getWorkflowStaticData('global')", "Guard Summary Retries staticData counter"),
    ("Guard Director Retries", "$getWorkflowStaticData('global')", "Guard Director Retries staticData counter"),
    ("Guard Merge Retries", "$getWorkflowStaticData('global')", "Guard Merge Retries staticData counter"),
    ("Guard Merge Fallback Retries", "$getWorkflowStaticData('global')", "Guard Merge Fallback Retries staticData counter"),

    # 6. Cut Concat checks
    ("Cut & Concat All Segments", "filter(s => (s.end - s.start) >= 0.15)", "CutConcat 0.15s minimum segment filter"),

    # 7. Create Subtitle Binary checks
    ("Create Subtitle Binary", "fs.existsSync('/files/temp/screams.json')", "CreateSubtitle screams.json disk loader"),
    ("Create Subtitle Binary", "trunc(ih*0.92*(720/860)/2)*2", "CreateSubtitle 720:860 aspect gameplay crop"),
    ("Create Subtitle Binary", "gameYRatio", "CreateSubtitle dynamic gameYRatio vertical offset"),
    ("Create Subtitle Binary", "trunc(ih*0.86*(720/1280)/2)*2", "CreateSubtitle no-cam top HUD bypass crop"),
    ("Create Subtitle Binary", "trunc(ih*0.11/2)*2", "CreateSubtitle no-cam y=11% offset"),
    ("Create Subtitle Binary", "vstack=inputs=2", "CreateSubtitle fast vstack=inputs=2 split-screen"),
    ("Create Subtitle Binary", "acompressor=threshold=-20dB", "CreateSubtitle audio compressor"),
    ("Create Subtitle Binary", "alimiter=limit=-1.5dB", "CreateSubtitle audio limiter"),
    ("Create Subtitle Binary", "equalizer=f=3500", "CreateSubtitle voice chat de-harshing EQ"),
    ("Loop Clips", 'options', "LoopClips splitInBatches configured"),
    ("Create Subtitle Binary", "sanitizeCaption", "CreateSubtitle sanitizeCaption anti-placeholder leak"),
    ("Create Subtitle Binary", "subY = 1040", "CreateSubtitle lower-third subtitle y=1040"),
    ("Create Subtitle Binary", "captionY = isSplitCam ? 420 : 145", "CreateSubtitle divider-seam hook caption y=420 (split-cam) / y=145 (fullscreen)"),

    # 8. Hook & Zero-Second Retention checks
    ("1. Prepare Scout Prompt", "ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE", "Scout zero-second retention & anti-mid-thought preamble rule"),
    ("1. Prepare Scout Prompt", "CAUSE-EFFECT NARRATIVE THROUGH-LINE & ANTI-CHAOS", "Scout cause-effect narrative through-line rule"),
    ("3. Prepare Director Prompt", "STRICT RETENTION, SENTENCE-BOUNDARY & SEMANTIC CONTINUITY RULES", "Director retention & semantic continuity rule"),
    ("3. Prepare Director Prompt", "NON-CHRONOLOGICAL HOOKS", "Director non-chronological hook duration guard"),
    ("3. Prepare Director Prompt", "CAUSE-EFFECT EDL (ANTI-CHAOS)", "Director cause-effect EDL rule"),

    # 9. Cold Open & Segment checks
    ("6. Extract Viral Segments", "HOOK_CLIMAX", "ExtractViral HOOK_CLIMAX cold open teaser splicing"),
    ("6. Extract Viral Segments", "fillerWords", "ExtractViral conversational hesitation filler trimming"),

    # 10. Subtitles & Layout Dynamic checks
    ("Create Subtitle Binary", "DANGER_WORDS", "CreateSubtitle high-impact categorical dictionaries"),
    ("Create Subtitle Binary", "-preset veryfast -crf 20 -threads 0", "CreateSubtitle fast CPU encode preset"),
    ("Create Subtitle Binary", "vstack=inputs=2", "CreateSubtitle standardized 9:16 vertical layout constraint"),

    # 11. Multimodal Virality Fusion Engine checks
    ("Run Multimodal Fusion", "multimodal_analyzer.py", "RunMultimodalFusion analyzer script execution"),
    ("1. Prepare Scout Prompt", "PROVEN MULTIMODAL VIRAL PEAKS", "Scout multimodal viral anchors extraction"),
    ("3. Prepare Director Prompt", "PROVEN AUDIENCE & REACTION ANCHORS", "Director multimodal anchors alignment"),

    # 12. Script Sandbox & 5 Viral Narrative Archetypes checks
    ("Load Cached Telemetry", "unified_timeline_index.json", "LoadCachedTelemetry cached multimodal loader"),
    ("Is Dry Run / Script Sandbox?", "dry_run", "HardRenderGate dry_run check"),
    ("DRY_RUN_SCRIPT_ONLY", "edl_segments", "DryRunPreview script & EDL output"),
    ("3. Prepare Director Prompt", "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL", "Director Archetype 1 Continuous Gameplay"),
    ("3. Prepare Director Prompt", "VIEWER_OR_CHAT_ROAST_INTERACTION", "Director Archetype 2 Viewer Roast"),
    ("3. Prepare Director Prompt", "HUBRIS_WAGER_INSTANT_KARMA", "Director Archetype 3 Instant Karma"),
    ("3. Prepare Director Prompt", "COMEDIC_STORYTELLING_OR_SARCASM", "Director Archetype 4 Comedic Storytelling"),
    ("3. Prepare Director Prompt", "FLASHFORWARD_MYSTERY_INVESTIGATION", "Director Archetype 5 Flash-Forward"),
    ("3. Prepare Director Prompt", "EMOTIONAL_SHOCK_OR_BETRAYAL", "Director Archetype 6 Emotional Shock"),
    ("3. Prepare Director Prompt", "ZERO OVERLAPPING TIMESTAMPS", "Director non-overlapping EDL rule"),
    ("3. Prepare Director Prompt", "DISTINCT SCENES (>= 120s APART)", "Director >=120s scene distinctness rule"),
    ("6. Extract Viral Segments", "dedupedIntervals", "ExtractViral non-hook interval deduplication"),

    # 13. Bug 1-4 Production Hardening checks
    ("Context Merge Agent", "assembled_spoken_script", "ContextMerge reads Loop Clips assembled_spoken_script first"),
    ("Context Merge Fallback", "assembled_spoken_script", "ContextMergeFallback reads Loop Clips assembled_spoken_script first"),
    ("Create Subtitle Binary", "NO AUDIO FOUND", "CreateSubtitle BANNED_CAPTION_RE bans NO AUDIO FOUND / NO WORDS"),
    ("Write Sidecar JSON", "NO AUDIO FOUND", "WriteSidecarJSON BANNED regex bans NO AUDIO FOUND / NO WORDS"),
    ("Screen UI Vision Audit", "screen_ui_audit.py", "ScreenUIVisionAudit invokes 4-frame Gemini Vision audit"),
    ("IF: Screen Clean?", "has_ui_obstruction === false", "IfScreenClean fails closed on obstructed/EULA/loading clips"),
    ("1. Prepare Scout Prompt", "keep counter", "Scout anti-intro rules & anti-raid filter"),
    ("3. Prepare Director Prompt", "thank you for the raid", "Director anti-intro rules & anti-raid filter"),
    ("5. Split Clips", "INTRO_RULES_RAID_RE", "SplitClips filters raid thank-yous & intro rules clips"),
    ("6. Extract Viral Segments", "isPauseOrPunctStart", "ExtractViral +-1.2s Whisper sentence/pause boundary snapping"),

    # 14. Scout Retry Circuit-Breaker, Smart Chunking, Gemini Output/Safety & Truncation Guards
    ("1. Prepare Scout Prompt", "Math.min(4, Math.max(1, charChunks))", "PrepareScoutPrompt char-budgeted chunking capped at 4 chunks"),
    ("1. Prepare Scout Prompt", "_scout_primary_dead = false", "PrepareScoutPrompt resets staticData circuit breaker"),
    ("1. Prepare Scout Prompt", "RAW DECIMAL SECONDS", "PrepareScoutPrompt enforces raw decimal seconds format"),
    ("Guard Scout Retries", "_scout_primary_dead = true", "GuardScoutRetries trips circuit breaker on repeated/daily 429"),
    ("Check Scout Primary Health", "_scout_primary_live", "CheckScoutPrimaryHealth exposes primary health flag"),
    ("If Scout Primary Live?", "_scout_primary_live", "IfScoutPrimaryLive bypasses exhausted primary Scout model"),
    ("Scout Accumulate", "normalizeTimestamps", "ScoutAccumulate normalizes MM:SS timestamps to decimal seconds"),
    ("Scout Accumulate", "validItems", "ScoutAccumulate filters <120-char truncated fragments"),
    ("Gemini Model (Scout)", "gemini-3.5-flash-lite", "GeminiModelScout preserves user 3.5-flash-lite"),
    ("Gemini Backup Model Scout", "gemini-2.5-flash", "GeminiBackupModelScout uses full gemini-2.5-flash with BLOCK_NONE"),
    ("Gemini Model (Director)", "BLOCK_NONE", "GeminiModelDirector disables overly strict safety cutoffs"),
    ("Gemini Backup Model Director", "gemini-2.5-flash", "GeminiBackupModelDirector uses full gemini-2.5-flash"),

    # 15. Multi-Provider Tier-3 Mistral Cloud Waterfall
    ("Mistral Backup Model Scout", "mistral-large-latest", "MistralBackupModelScout Tier-3 cross-provider Scout fallback"),
    ("Mistral Backup Model Director", "mistral-large-latest", "MistralBackupModelDirector Tier-3 cross-provider Director fallback"),
    ("Mistral Backup Model Merge", "mistral-small-latest", "MistralBackupModelMerge Tier-3 cross-provider Context Merge fallback"),
    ("Mistral Backup Model Summary", "mistral-small-latest", "MistralBackupModelSummary Tier-3 cross-provider Global Summary fallback"),
    ("Scout Accumulate", "2. Basic LLM Chain (Scout Mistral Fallback)", "ScoutAccumulate collects Tier-3 Mistral Scout outputs"),
]

all_passed = True
for node_name, snippet, desc in checks:
    # Check in workflow.json
    node = nodes.get(node_name)
    if not node:
        print(f"[FAIL] {node_name} not found in workflow.json")
        all_passed = False
        continue
    
    # Get node text
    params = node.get('parameters', {})
    node_str = json.dumps(params)
    if snippet not in node_str:
        print(f"[FAIL JSON] {node_name} missing '{snippet}' ({desc})")
        all_passed = False
    else:
        print(f"[OK JSON] {node_name}: {desc}")

    # Check in workflow_bypassed.ts
    if snippet not in ts_code:
        print(f"[FAIL TS] workflow_bypassed.ts missing '{snippet}' ({desc})")
        all_passed = False
    else:
        print(f"[OK TS] workflow_bypassed.ts: {desc}")

# Verify Isolated EDL Architect Workflow
iso_path = os.path.join(ROOT, 'workflows', 'isolated_edl_architect.json')
if not os.path.exists(iso_path):
    print("[FAIL] workflows/isolated_edl_architect.json missing")
    all_passed = False
else:
    with open(iso_path, 'r', encoding='utf-8') as f:
        iso_wf = json.load(f)
    iso_nodes = {n['name']: n for n in iso_wf.get('nodes', [])}
    forbidden_render = [
        "Execute Cut & Concat", "Cut & Concat All Segments",
        "Render Final Video", "Run Remotion Overlay", "FFmpeg Crop"
    ]
    for fn in forbidden_render:
        if fn in iso_nodes:
            print(f"[FAIL ISO] Render node leaked into isolated_edl_architect.json: {fn}")
            all_passed = False
    for req in ["Verify Hooks & Build EDL Preview", "1. Prepare Scout Prompt", "3. Prepare Director Prompt", "5. Split Clips", "6. Extract Viral Segments", "Context Merge Agent"]:
        if req not in iso_nodes:
            print(f"[FAIL ISO] Missing required EDL node: {req}")
            all_passed = False
    for gem in ["Gemini Model (Scout)", "Gemini Model (Director)", "Gemini Model 1", "Gemini Model 2"]:
        m_val = iso_nodes.get(gem, {}).get("parameters", {}).get("modelName", "")
        if "gemini-3.5-flash-lite" not in m_val:
            print(f"[FAIL ISO] {gem} lost gemini-3.5-flash-lite (got {m_val})")
            all_passed = False
    print(f"[OK ISO] isolated_edl_architect.json verified ({len(iso_nodes)} nodes, zero video rendering)")

if all_passed:
    print(f"\nALL {len(checks)} SYSTEM CHECKS + ISOLATED EDL CHECKS PASSED!")
else:
    print("\nSOME CHECKS FAILED!")
    sys.exit(1)
    exit(1)
