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

    # 2. Director prompt checks
    ("3. Prepare Director Prompt", "ZERO DEAD TIME AT HOOK", "Director zero dead time rule"),
    ("3. Prepare Director Prompt", "TIGHT SETUP BEFORE CLIMAX", "Director tight setup buildup rule"),
    ("3. Prepare Director Prompt", "SINGLE PREMISE NARRATIVE COHESION", "Director single premise cohesion rule"),
    ("3. Prepare Director Prompt", "PAYOFF IMPACT & ANTI-CLIMAX FILTER", "Director payoff impact rule"),
    ("3. Prepare Director Prompt", "18s and 38s", "Director 18s-38s duration sweet spot"),

    # 3. Context Merge checks
    ("Context Merge Agent", "CLIMAX QUOTE (Exact 3 to 5 words", "ContextMerge climax quote rule"),
    ("Context Merge Fallback", "CLIMAX QUOTE (Exact 3 to 5 words", "ContextMergeFallback climax quote rule"),

    # 4. Split Clips checks
    ("5. Split Clips", "if (sTime < 3.0)", "SplitClips anti-loading screen rule"),
    ("5. Split Clips", "if (pTime > sTime && (pTime - sTime) > 18.0)", "SplitClips tight setup buildup limit"),
    ("5. Split Clips", "if (pTime > sTime && (eTime - pTime) > 3.5)", "SplitClips punchy aftermath rule"),
    ("5. Split Clips", "dur < 16", "SplitClips min duration without artificial dilation"),

    # 5. Extract Viral Segments checks
    ("6. Extract Viral Segments", "BUFFER = 0.12", "ExtractViral tight 0.12 buffer"),
    ("6. Extract Viral Segments", "w.start - lastWordEnd > 0.55", "ExtractViral 0.55s gap jump cut"),
    ("6. Extract Viral Segments", "Math.max(start, clipWords[0].start - 0.10)", "ExtractViral loading screen trim"),

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
    ("Create Subtitle Binary", "subY = 880", "CreateSubtitle 3-zone lower-third subtitle y=880"),
    ("Create Subtitle Binary", "captionY = 75", "CreateSubtitle 3-zone top hook caption y=75"),

    # 8. Hook & Zero-Second Retention checks
    ("1. Prepare Scout Prompt", "ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE", "Scout zero-second retention & anti-mid-thought preamble rule"),
    ("1. Prepare Scout Prompt", "CAUSE-EFFECT NARRATIVE THROUGH-LINE & ANTI-CHAOS", "Scout cause-effect narrative through-line rule"),
    ("3. Prepare Director Prompt", "ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE", "Director zero-second retention rule"),
    ("3. Prepare Director Prompt", "COLD OPEN RETENTION TRAP & ZERO-SECOND HOOK", "Director cold open retention trap rule"),
    ("3. Prepare Director Prompt", "CAUSE-EFFECT EDL (ANTI-CHAOS)", "Director cause-effect EDL rule"),

    # 9. Cold Open & Segment checks
    ("6. Extract Viral Segments", "ColdOpen_teaser", "ExtractViral cold open teaser splicing"),
    ("6. Extract Viral Segments", "fillerWords", "ExtractViral conversational hesitation filler trimming"),

    # 10. Subtitles & Layout Dynamic checks
    ("Create Subtitle Binary", "DANGER_WORDS", "CreateSubtitle high-impact categorical dictionaries"),
    ("Create Subtitle Binary", "scale=trunc(720*1.15/2)*2", "CreateSubtitle 115% reaction punch zoom for screams/kills"),
    ("Create Subtitle Binary", "ZERO-GAP SPLIT SCREEN", "CreateSubtitle standardized 9:16 vertical layout constraint"),

    # 11. Multimodal Virality Fusion Engine checks
    ("Run Multimodal Fusion", "multimodal_analyzer.py", "RunMultimodalFusion analyzer script execution"),
    ("1. Prepare Scout Prompt", "PROVEN MULTIMODAL VIRAL PEAKS", "Scout multimodal viral anchors extraction"),
    ("3. Prepare Director Prompt", "PROVEN AUDIENCE & REACTION ANCHORS", "Director multimodal anchors alignment"),
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
