import os
import json

wf_p = 'workflows/workflow.json' if os.path.exists('workflows/workflow.json') else 'workflow.json'
with open(wf_p, 'r', encoding='utf-8') as f:
    wf = json.load(f)

nodes = {n['name']: n for n in wf['nodes']}

ts_p = 'workflows/workflow_bypassed.ts' if os.path.exists('workflows/workflow_bypassed.ts') else 'workflow_bypassed.ts'
with open(ts_p, 'r', encoding='utf-8') as f:
    ts_code = f.read()

checks = [
    # 1. Scout prompt checks
    ("1. Prepare Scout Prompt", "STRICT ANTI-IDLE & ANTI-STATIC", "Scout anti-idle rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-LOADING SCREEN", "Scout anti-loading screen rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-SLOW-UI & TRADE MENUS", "Scout anti-slow-ui rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-CONVERSATIONAL BANTER & DONATION AFTERMATH", "Scout anti-conversational banter rule"),
    ("1. Prepare Scout Prompt", "STRICT ANTI-GRIND & ANTI-FARMING", "Scout anti-grind rule"),
    ("1. Prepare Scout Prompt", "SATISFYING CLIMAX ONLY", "Scout satisfying climax rule"),
    ("1. Prepare Scout Prompt", "MULTI-SEGMENT NARRATIVE ARCHING", "Scout multi-segment narrative arching enforcement"),
    ("1. Prepare Scout Prompt", "[SETUP / STAKES]", "Scout Act 1 SETUP/STAKES requirement"),
    ("1. Prepare Scout Prompt", "[ESCALATION / STRUGGLE]", "Scout Act 2 ESCALATION/STRUGGLE requirement"),
    ("1. Prepare Scout Prompt", "[PAYOFF / REACTION]", "Scout Act 3 PAYOFF/REACTION requirement"),
    ("1. Prepare Scout Prompt", "30-45s", "Scout 30-45s unified story arc target"),

    # 2. Director prompt checks
    ("3. Prepare Director Prompt", "ZERO DEAD TIME AT HOOK", "Director zero dead time rule"),
    ("3. Prepare Director Prompt", "MULTI-SEGMENT NARRATIVE ARCHING", "Director multi-segment narrative arching enforcement"),
    ("3. Prepare Director Prompt", "[SETUP / STAKES]", "Director Act 1 SETUP/STAKES requirement"),
    ("3. Prepare Director Prompt", "[ESCALATION / STRUGGLE]", "Director Act 2 ESCALATION/STRUGGLE requirement"),
    ("3. Prepare Director Prompt", "[PAYOFF / REACTION]", "Director Act 3 PAYOFF/REACTION requirement"),
    ("3. Prepare Director Prompt", "SINGLE PREMISE NARRATIVE COHESION", "Director single premise cohesion rule"),
    ("3. Prepare Director Prompt", "PAYOFF IMPACT & ANTI-CLIMAX FILTER", "Director payoff impact rule"),
    ("3. Prepare Director Prompt", "30s and 45s", "Director 30s-45s unified Shorts duration window"),
    ("3. Prepare Director Prompt", "ZERO RANDOM MID-SENTENCE CUTS", "Director zero mid-sentence cuts rule"),
    ("3. Prepare Director Prompt", "MANDATORY 3-ACT MULTI-SEGMENT SCHEMA", "Director mandatory 3-act segments schema"),

    # 3. Context Merge checks
    ("Context Merge Agent", "CLIMAX QUOTE (Exact 3 to 5 words", "ContextMerge climax quote rule"),
    ("Context Merge Fallback", "CLIMAX QUOTE (Exact 3 to 5 words", "ContextMergeFallback climax quote rule"),

    # 4. Split Clips checks
    ("5. Split Clips", "normalizeRole", "SplitClips role normalization helper"),
    ("5. Split Clips", "snapSegmentBounds", "SplitClips Whisper sentence-boundary snapping"),
    ("5. Split Clips", "splitIntervalToThreeActs", "SplitClips 3-act fallback arc splitter"),
    ("5. Split Clips", "totalSegDur < 30.0", "SplitClips 30s minimum narrative arc duration"),
    ("5. Split Clips", "totalSegDur > 45.0", "SplitClips 45s maximum Shorts duration cap"),
    ("5. Split Clips", "minPayoffGap", "SplitClips payoff-centered multi-arc distinctness check"),

    # 5. Extract Viral Segments checks
    ("6. Extract Viral Segments", "BUFFER = 0.12", "ExtractViral tight 0.12 buffer"),
    ("6. Extract Viral Segments", "deadTrimmedIntervals", "ExtractViral >5s dead-air trimming"),
    ("6. Extract Viral Segments", "totalClipDur < 30.0", "ExtractViral 30s-45s duration enforcement"),

    # 6. Cut Concat checks
    ("Cut & Concat All Segments", "filter(s => (s.end - s.start) >= 0.15)", "CutConcat 0.15s minimum segment filter"),

    # 7. Create Subtitle Binary checks
    ("Create Subtitle Binary", "fs.existsSync('/files/temp/screams.json')", "CreateSubtitle screams.json disk loader"),
    ("Create Subtitle Binary", "trunc(ih*0.85*(720/900)/2)*2", "CreateSubtitle 720:820 aspect gameplay crop"),
    ("Create Subtitle Binary", "trunc(ih*0.10/2)*2", "CreateSubtitle y=12% offset to bypass top follower goal/timer"),
    ("Create Subtitle Binary", "trunc(ih*0.86*(720/1280)/2)*2", "CreateSubtitle no-cam top HUD bypass crop"),
    ("Create Subtitle Binary", "trunc(ih*0.11/2)*2", "CreateSubtitle no-cam y=11% offset"),
    ("Create Subtitle Binary", "scale=trunc(720*1.45/2)*2", "CreateSubtitle 1.45x punch zoom"),
    ("Create Subtitle Binary", "acompressor=threshold=-20dB", "CreateSubtitle audio compressor"),
    ("Create Subtitle Binary", "alimiter=limit=-1.5dB", "CreateSubtitle audio limiter"),
    ("Create Subtitle Binary", "equalizer=f=3500", "CreateSubtitle voice chat de-harshing EQ"),
    ("Loop Clips", 'batchSize', "LoopClips batchSize 1 for multi-clip iteration"),
    ("Create Subtitle Binary", "sanitizeCaption", "CreateSubtitle sanitizeCaption anti-placeholder leak"),
    ("Create Subtitle Binary", "subY = 920", "CreateSubtitle 3-zone lower-third subtitle y=920"),
    ("Create Subtitle Binary", "captionY = 75", "CreateSubtitle 3-zone top hook caption y=75"),

    # 8. Hook & Zero-Second Retention checks
    ("1. Prepare Scout Prompt", "ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE", "Scout zero-second retention & anti-mid-thought preamble rule"),
    ("1. Prepare Scout Prompt", "CAUSE-EFFECT NARRATIVE THROUGH-LINE & ANTI-CHAOS", "Scout cause-effect narrative through-line rule"),
    ("3. Prepare Director Prompt", "ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE", "Director zero-second retention rule"),
    ("3. Prepare Director Prompt", "NON-CHRONOLOGICAL HOOKS", "Director non-chronological hook duration guard"),
    ("3. Prepare Director Prompt", "CAUSE-EFFECT EDL (ANTI-CHAOS)", "Director cause-effect EDL rule"),

    # 9. Cold Open & Segment checks
    ("6. Extract Viral Segments", "HOOK_CLIMAX", "ExtractViral HOOK_CLIMAX cold open teaser splicing"),
    ("6. Extract Viral Segments", "fillerWords", "ExtractViral conversational hesitation filler trimming"),

    # 10. Subtitles & Layout Dynamic checks
    ("Create Subtitle Binary", "DANGER_WORDS", "CreateSubtitle high-impact categorical dictionaries"),
    ("Create Subtitle Binary", "scale=trunc(720*1.15/2)*2", "CreateSubtitle 115% reaction punch zoom for screams/kills"),
    ("Create Subtitle Binary", "ZERO-GAP SPLIT SCREEN", "CreateSubtitle standardized 9:16 vertical layout constraint"),

    # 11. Multimodal Virality Fusion Engine checks
    ("Run Multimodal Fusion", "multimodal_analyzer.py", "RunMultimodalFusion analyzer script execution"),
    ("1. Prepare Scout Prompt", "PROVEN MULTIMODAL VIRAL PEAKS", "Scout multimodal viral anchors extraction"),
    ("3. Prepare Director Prompt", "PROVEN AUDIENCE & REACTION ANCHORS", "Director multimodal anchors alignment"),

    # 12. Script Sandbox & 5 Viral Narrative Archetypes checks
    ("Load Cached Telemetry", "unified_timeline_index.json", "LoadCachedTelemetry cached multimodal loader"),
    ("Is Dry Run / Script Sandbox?", "dry_run", "HardRenderGate dry_run check"),
    ("DRY_RUN_SCRIPT_ONLY", "edl_segments", "DryRunPreview script & EDL output"),
    ("3. Prepare Director Prompt", "IN_MEDIA_RES_FLASHFORWARD", "Director Archetype A Flash-Forward"),
    ("3. Prepare Director Prompt", "DOUBLE_DOWN_ESCALATION", "Director Archetype B Escalation"),
    ("3. Prepare Director Prompt", "HUBRIS_INSTANT_KARMA", "Director Archetype C Instant Karma"),
    ("3. Prepare Director Prompt", "MYSTERY_OPEN_LOOP", "Director Archetype D Mystery Loop"),
    ("3. Prepare Director Prompt", "REVERSE_PAYOFF_LOOP", "Director Archetype E Infinite Loop"),
    ("3. Prepare Director Prompt", "ZERO OVERLAPPING TIMESTAMPS", "Director non-overlapping EDL rule"),
    ("3. Prepare Director Prompt", "DISTINCT SCENES (>= 120s APART)", "Director >=120s scene distinctness rule"),
    ("6. Extract Viral Segments", "dedupedIntervals", "ExtractViral non-hook interval deduplication"),

    # 13. Bug 1-4 Production Hardening checks
    ("Context Merge Agent", "assembled_spoken_script", "ContextMerge reads Loop Clips assembled_spoken_script first"),
    ("Context Merge Fallback", "assembled_spoken_script", "ContextMergeFallback reads Loop Clips assembled_spoken_script first"),
    ("Create Subtitle Binary", "NO AUDIO FOUND", "CreateSubtitle BANNED_CAPTION_RE bans NO AUDIO FOUND / NO WORDS"),
    ("Write Sidecar JSON", "NO AUDIO FOUND", "WriteSidecarJSON BANNED regex bans NO AUDIO FOUND / NO WORDS"),
    ("Screen UI Vision Audit", "screen_ui_audit.py", "ScreenUIVisionAudit invokes 4-frame Gemini Vision audit"),
    ("IF: Screen Clean?", "has_ui_obstruction !== true", "IfScreenClean skips obstructed browser/ESC menu clips"),
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
    ("Gemini Model (Scout)", "maxOutputTokens", "GeminiModelScout configures maxOutputTokens 8192 + safetySettings"),
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

if all_passed:
    print(f"\nALL {len(checks)} SYSTEM CHECKS PASSED IN BOTH WORKFLOW.JSON AND WORKFLOW_BYPASSED.TS!")
else:
    print("\nSOME CHECKS FAILED!")
    exit(1)
