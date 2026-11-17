# AUTONOMOUS 23-ITERATION EDL OPTIMIZATION & FORENSIC AUDIT REPORT

Comprehensive empirical audit generated from live n8n executions of `IsoEdlArchitectV1` (`Isolated Multimodal Script & EDL Architect`) graded deterministically by `/files/edl_auditor.py` across two full-length multi-hour livestreams (`VOD1` Bugsnax 7,450s & `VOD2` Droid Tycoon 8,929s) and 6 time slices.

## 1. Executive Progression Table (Iterations #1â€“#23)

| Iter | Dataset Tested | Score (/100) | Clips | Archs | Pre-Hook (/20) | Payoff (/20) | Entity (/15) | Hook (/10) | Signal (/10) | Fit (/5) | Pacing (/10) | Admin (/5) | Key Flaws Detected | Exact Code / Prompt Edits Applied |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| #1 | VOD1_Bugsnax_Full (transcript.json, 0s-7450s) | **85.33** | 3 | 3 | 10.0 | 20.0 | 15.0 | 8.7 | 10.0 | 1.7 | 10.0 | 5.0 | MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS, UNNECESSARY_JUMP_CUT | Baseline run (no edits yet). Evaluated newly isolated IsoEdlArchitectV1. |
| #2 | VOD1_Bugsnax_Full (transcript.json, 0s-7450s) | **53.0** | 1 | 1 | 20.0 | 10.0 | 15.0 | 3.0 | 0.0 | 5.0 | 5.0 | 5.0 | DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, HOOK_WORD_COUNT_OFF, PREMATURE_PAYOFF_CUTOFF, UNGROUNDED_HOOK_NOUNS, LOW_ARCHETYPE_DIVERSITY | Batch 1 fixes: Midpoint word ownership, orphan period stripping, <4s jump-cut auto-merge, virality_score fallback, <22s tail rescue, Prepare Merge Items context injection, PLAYING THE GAME ban. |
| #3 | VOD1_Bugsnax_Full (transcript.json, 0s-7450s) | **85.0** | 1 | 1 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | LOW_ARCHETYPE_DIVERSITY | Added IF: Director JSON Valid? validator + trimmed Director anchors (12x520 chars) + auto-merge <4s jump cuts + strict period cleanup. |
| #4 | VOD1_Bugsnax_Full | **87.5** | 4 | 4 | 15.0 | 16.2 | 11.2 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | FILLER_CONTINUATION_START, FRANKENSTEIN_MISMATCH, INSUFFICIENT_AFTERMATH, MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS | Fixed IF:Director JSON Valid? array support & Guard escalation, mandatory 4-5 clips across >=3 archetypes, continuous <4s rule, transitive entity chain continuity. |
| #5 | VOD1_Bugsnax_Full | **82.5** | 2 | 2 | 20.0 | 12.5 | 15.0 | 10.0 | 10.0 | 5.0 | 7.5 | 5.0 | DURATION_OUT_OF_BOUNDS, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY | Fixed 1..4-word prior-sentence tail trimmer + filler conjunction skip + Post-Peak Aftermath Extender (+1 sentence after [dB_PEAK]) + fixed edl_auditor overlapping token check. |
| #6 | VOD2_Tycoon_Full | **67.0** | 1 | 1 | 5.0 | 20.0 | 15.0 | 7.0 | 10.0 | 5.0 | 10.0 | 5.0 | HOOK_WORD_COUNT_OFF, MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS, LOW_ARCHETYPE_DIVERSITY | Cross-VOD |
| #7 | VOD2_Tycoon_Full | **97.5** | 4 | 3 | 20.0 | 20.0 | 15.0 | 10.0 | 7.5 | 5.0 | 10.0 | 5.0 | FLAT_NO_MULTIMODAL_SIGNAL | Fixed leading = on ContextMergeAgent/Fallback/Mistral (CRITICAL), Whisper backward-overlap start guard, <=5 word hook clamp, and real VOD2 override JSON. |
| #8 | VOD1_Bugsnax_H1 | **87.5** | 2 | 2 | 15.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | MID_SENTENCE_START, LOW_ARCHETYPE_DIVERSITY | Updated telemetry STOPWORDS (eliminated generic emotion callbacks like happy/funny) + Director SIGNAL GROUNDING REQUIREMENT + isolated Wait cap <=3s. |
| #9 | VOD1_Bugsnax_H2 | **97.33** | 3 | 3 | 20.0 | 20.0 | 15.0 | 9.0 | 10.0 | 5.0 | 8.3 | 5.0 | DURATION_OUT_OF_BOUNDS, HOOK_WORD_COUNT_OFF | Added 4-char entity stem chaining in 5. Split Clips, strict non-overlapping +-3.2s sentence boundary scanner, and IF: Director Fallback JSON Valid?. |
| #10 | VOD2_Tycoon_H1 | **95.33** | 3 | 3 | 16.7 | 20.0 | 15.0 | 8.7 | 10.0 | 5.0 | 10.0 | 5.0 | PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS | Added post-snap >=22.0s sentence-safe floor rescue in 6. Extract Viral Segments + verifyHook 3-5 word preference over 2-word title fallbacks. |
| #11 | VOD2_Tycoon_H2 | **60.0** | 1 | 1 | 20.0 | 10.0 | 15.0 | 10.0 | 0.0 | 5.0 | 5.0 | 5.0 | DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY | Fixed capitalized opener false positive in edl_auditor.py (PRE_HOOK_SPILLOVER_WORDS) + ContextMergeAgent concrete transcript-word hook grounding rule. |
| #12 | VOD2_Tycoon_H2 | **79.5** | 2 | 2 | 20.0 | 12.0 | 15.0 | 10.0 | 5.0 | 5.0 | 10.0 | 5.0 | DANGLING_CLIMAX_PHRASE, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY | Added multi-run Director clip salvage + multimodal anchor fallback in 5. Split Clips to prevent Backup_Clip regressions when Backup/Mistral hit 429 or timeout. |
| #13 | VOD2_Tycoon_H2 | **93.5** | 4 | 3 | 20.0 | 16.0 | 15.0 | 10.0 | 7.5 | 5.0 | 10.0 | 5.0 | DANGLING_CLIMAX_PHRASE, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF | Rebuilt full 8929s empirical VOD2 audio+face index via multimodal_analyzer.py + expanded final-segment terminal punctuation guard to +-3.5s in 6. Extract Viral Segments. |
| #14 | VOD1_Bugsnax_Mid | **95.0** | 3 | 3 | 15.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS | Strict comma/filler rejection inside isTerminalEnd (gap > 0.85s required if no .!?) + viewer comment-bait filter in OUTRO_PANHANDLING_RE & edl_auditor.py. |
| #15 | VOD2_Tycoon_Mid | **92.5** | 2 | 2 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | LOW_ARCHETYPE_DIVERSITY | Added Monotonic Midpoint Sentence Opener Guard in 6. Extract Viral Segments eliminating residual prior-sentence spillover words (e.g. restroom.). |
| #16 | VOD2_Tycoon_Mid | **100.0** | 3 | 3 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | NONE (ZERO DEFECTS) | Expanded Director anchor context to 780 chars, added strict >=3 archetype & >=14s duration quality gate on IF: Director JSON Valid?, and increased <22s tail rescue reach to 20s. |
| #17 | VOD1_Bugsnax_H1 | **90.0** | 2 | 1 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | LOW_ARCHETYPE_DIVERSITY | Cross-VOD stress-test on VOD1 Hour 1 (0-3700s) with Iteration 16 pipeline (anchor context 780ch, >=3 archetype gate, Monotonic Midpoint Guard). |
| #18 | VOD1_Bugsnax_H1 | **92.5** | 2 | 2 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | LOW_ARCHETYPE_DIVERSITY | Enforced max 1 FLASHFORWARD per batch & >=3 tight single-scene/continuous/roast/comedy/hubris clips (24-44s) in Scout & Director prompts. |
| #19 | VOD2_Tycoon_H1 | **98.75** | 4 | 4 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 8.8 | 5.0 | DEAD_AIR_OVER_5S | Relaxed minPayoffGap from 90s to 50s for dense comedic bursts while keeping >6s segment overlap protection. |
| #20 | VOD2_Tycoon_Full | **82.5** | 2 | 2 | 20.0 | 10.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | DANGLING_CLIMAX_PHRASE, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY | Prevented collapsedSegs from re-merging across >5.0s dead-air cuts (_dead_split_after flag) + tightened dead-air trim padding to +-0.35s. |
| #21 | VOD2_Tycoon_Full | **100.0** | 4 | 3 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | NONE (ZERO DEFECTS) | Added two-pass .!?-first terminal snapping rejecting dangling prepositions/auxiliaries (to/going) + raised Director JSON solid clip floor from 14s to 19s. |
| #22 | VOD1_Bugsnax_Full | **97.5** | 3 | 2 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | LOW_ARCHETYPE_DIVERSITY | Final Champion Validation Run on default VOD1_Bugsnax_Full (0-7450s) with override cleared and Iteration 21 two-pass .!?-first boundary & diversity engine intact. |
| #23 | VOD1_Bugsnax_Full | **100.0** | 3 | 3 | 20.0 | 20.0 | 15.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | NONE (ZERO DEFECTS) | Final Champion Validation (Iteration 23): enforced distinct >=120s Anchor ID spread per clip in Director + restored >=15s pre-rescue gate on IF: Director JSON Valid?. |
| #24 | VOD1_Bugsnax_Full | **99.25** | 4 | 4 | 20.0 | 20.0 | 15.0 | 9.2 | 10.0 | 5.0 | 10.0 | 5.0 | HOOK_WORD_COUNT_OFF | Final build post-regression-suite validation (post-pause exclamation boundary guard + spoken-gap check inside collapsedSegs) on default VOD1_Bugsnax_Full. |

## 2. Iteration-by-Iteration Forensic Breakdown (Iterations 1 to 23)

### Iteration #1 â€” `VOD1_Bugsnax_Full (transcript.json, 0s-7450s)` â€” Score: **85.33/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, EMOTIONAL_SHOCK_OR_BETRAYAL
- **Fatal Flags:** MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS, UNNECESSARY_JUMP_CUT
- **What Changed in This Iteration:** Baseline run (no edits yet). Evaluated newly isolated IsoEdlArchitectV1.
- **Score & Diagnostics:**
  - Clips 1 & 3 started mid-sentence due to backward snapping grabbing trailing period-ending word ('that.', 'man.')
  - Clips 2 & 3 had 0.15s-1.30s artificial jump cuts between segments (<4s gap) -> UNNECESSARY_JUMP_CUT
  - Clip 3 had weak ungrounded caption 'PLAYING THE GAME' from Context Merge Agent
  - Only 3 clips survived (target 4-5) and virality_score defaulted to 0
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Spicy Noodle Panic 😭** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `COME BACK NOODLER` | Dur: `34.69s` | Segments: [CONTINUOUS_ARC 4838.11sâ€“4872.80s] | SubScore: `80.0/95` â€” FLAGS: MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'lure'; Trailing prior-sentence fragment 'that.' leaked into hook
  - **Clip 2 â€” Mutated Monster Limbs 🤯** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `SNACKDIVATOR MUTATION CHAOS` | Dur: `31.32s` | Segments: [PREMISE 4720.60sâ€“4724.89s], [ESCALATION 4726.19sâ€“4740.29s], [PUNCHLINE 4740.67sâ€“4753.60s] | SubScore: `90.0/95` â€” FLAGS: UNNECESSARY_JUMP_CUT
    - Diagnostics: Gap between seg 1 & 2 is only 1.30s (<4s); should be 1 continuous segment; Gap between seg 2 & 3 is only 0.38s (<4s); should be 1 continuous segment
  - **Clip 3 â€” Fake Stream End 😱** (`EMOTIONAL_SHOCK_OR_BETRAYAL`) | Hook: `PLAYING THE GAME` | Dur: `28.34s` | Segments: [SETUP 3261.30sâ€“3266.00s], [ESCALATION 3266.15sâ€“3275.00s], [PAYOFF 3275.15sâ€“3289.94s] | SubScore: `71.0/95` â€” FLAGS: MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS, UNNECESSARY_JUMP_CUT
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'break,'; Trailing prior-sentence fragment 'man.' leaked into hook; None of hook words ['playing', 'game'] found in clip/summary corpus; Gap between seg 1 & 2 is only 0.15s (<4s); should be 1 continuous segment; Gap between seg 2 & 3 is only 0.15s (<4s); should be 1 continuous segment

### Iteration #2 â€” `VOD1_Bugsnax_Full (transcript.json, 0s-7450s)` â€” Score: **53.0/100**

- **Clip Count:** 1 | **Distinct Archetypes (1):** CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL
- **Fatal Flags:** DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, HOOK_WORD_COUNT_OFF, PREMATURE_PAYOFF_CUTOFF, UNGROUNDED_HOOK_NOUNS, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Batch 1 fixes: Midpoint word ownership, orphan period stripping, <4s jump-cut auto-merge, virality_score fallback, <22s tail rescue, Prepare Merge Items context injection, PLAYING THE GAME ban.
- **Score & Diagnostics:**
  - Director/Scout hit backup or failed parse -> KreekCraft_Backup_Clip emitted! Check LLM fallback & Wait timing.
- **Generated Scenarios Summary:**
  - **Clip 1 â€” KreekCraft_Backup_Clip** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `INSANE MOMENT` | Dur: `29.0s` | Segments: [CONTINUOUS_ARC 3.00sâ€“32.00s] | SubScore: `63.0/95` â€” FLAGS: DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, HOOK_WORD_COUNT_OFF, PREMATURE_PAYOFF_CUTOFF, UNGROUNDED_HOOK_NOUNS
    - Diagnostics: Clip ends mid-clause 'Roblox' with next word 'gaming,' only -4.18s later; Hook 'INSANE MOMENT' has 2 words (target 3-5); None of hook words ['insane', 'moment'] found in clip/summary corpus; Zero dB/chat/face/pitch/viewer signals found in playback window; Segment 1 has 27.00s silent gap (3.0-30.0)

### Iteration #3 â€” `VOD1_Bugsnax_Full (transcript.json, 0s-7450s)` â€” Score: **85.0/100**

- **Clip Count:** 1 | **Distinct Archetypes (1):** CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL
- **Fatal Flags:** LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Added IF: Director JSON Valid? validator + trimmed Director anchors (12x520 chars) + auto-merge <4s jump cuts + strict period cleanup.
- **Score & Diagnostics:**
  - Clip 1 hit 95/95 ZERO FLAGS (perfect boundaries, hook, payoff, pacing!), BUT clip_count=1 -> lost 15 pts on clip count & diversity.
  - Investigating why Director only yielded 1 surviving clip after 5. Split Clips filters.
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Noodler Catching Chaos 💀** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `CATCHING THE NOODLER` | Dur: `30.33s` | Segments: [CONTINUOUS_ARC 4842.47sâ€“4872.80s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #4 â€” `VOD1_Bugsnax_Full` â€” Score: **87.5/100**

- **Clip Count:** 4 | **Distinct Archetypes (4):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, FLASHFORWARD_MYSTERY_INVESTIGATION, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** FILLER_CONTINUATION_START, FRANKENSTEIN_MISMATCH, INSUFFICIENT_AFTERMATH, MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS
- **What Changed in This Iteration:** Fixed IF:Director JSON Valid? array support & Guard escalation, mandatory 4-5 clips across >=3 archetypes, continuous <4s rule, transitive entity chain continuity.
- **Score & Diagnostics:**
  - FILLER_CONTINUATION_START
  - FRANKENSTEIN_MISMATCH
  - INSUFFICIENT_AFTERMATH
  - MID_SENTENCE_START
  - PRE_HOOK_SPILLOVER_WORDS
  - Clip 1: Only 0.00s reaction aftermath after peak in payoff
  - Clip 1: Gap 32.1s >25s with 0 shared entities between setup (["chandler's", 'chandlo', 'danger', 'knowing', 'project']) & payoff (['clinging', 'device', 'during', 'hugging', "i've"])
  - Clip 2: Trailing prior-sentence fragment 'in town.' leaked into hook
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Secret Tracker! 😱** (`FLASHFORWARD_MYSTERY_INVESTIGATION`) | Hook: `HE PLANTED A TRACKER` | Dur: `23.83s` | Segments: [PROMPT_SETUP 2508.19sâ€“2517.96s], [ESCALATION 2528.50sâ€“2534.92s], [PAYOFF 2567.01sâ€“2574.65s] | SubScore: `75.0/95` â€” FLAGS: FRANKENSTEIN_MISMATCH, INSUFFICIENT_AFTERMATH
    - Diagnostics: Only 0.00s reaction aftermath after peak in payoff; Gap 32.1s >25s with 0 shared entities between setup (["chandler's", 'chandlo', 'danger', 'knowing', 'project']) & payoff (['clinging', 'device', 'during', 'hugging', "i've"])
  - **Clip 2 â€” Mailbox Rant! 💀** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `MAILBOXES ARE NOT QUESTS` | Dur: `23.91s` | Segments: [CONTINUOUS_ARC 6814.02sâ€“6837.93s] | SubScore: `90.0/95` â€” FLAGS: PRE_HOOK_SPILLOVER_WORDS
    - Diagnostics: Trailing prior-sentence fragment 'in town.' leaked into hook
  - **Clip 3 â€” Top Secret! 🤯** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `REDACT EVERYTHING RIGHT NOW` | Dur: `23.12s` | Segments: [PROMPT_SETUP 5727.40sâ€“5734.15s], [REACTION_PAYOFF 5846.10sâ€“5862.47s] | SubScore: `75.0/95` â€” FLAGS: FILLER_CONTINUATION_START, INSUFFICIENT_AFTERMATH, MID_SENTENCE_START
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'don't'; Starts with filler 'But we'll start an interv' without clean break; Only 0.00s reaction aftermath after peak in payoff
  - **Clip 4 â€” Floating Floor! 😭** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `FLOOR IS OVER WATER` | Dur: `36.82s` | Segments: [CONTINUOUS_ARC 2331.83sâ€“2368.64s] | SubScore: `90.0/95` â€” FLAGS: INSUFFICIENT_AFTERMATH
    - Diagnostics: Only 0.00s reaction aftermath after peak in payoff

### Iteration #5 â€” `VOD1_Bugsnax_Full` â€” Score: **82.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** FLASHFORWARD_MYSTERY_INVESTIGATION, HUBRIS_WAGER_INSTANT_KARMA
- **Fatal Flags:** DURATION_OUT_OF_BOUNDS, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Fixed 1..4-word prior-sentence tail trimmer + filler conjunction skip + Post-Peak Aftermath Extender (+1 sentence after [dB_PEAK]) + fixed edl_auditor overlapping token check.
- **Score & Diagnostics:**
  - DURATION_OUT_OF_BOUNDS
  - INSUFFICIENT_AFTERMATH
  - PREMATURE_PAYOFF_CUTOFF
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 1: Clip ends mid-clause 't want to junk mail. I have to read' with next word 'it' only 0.00s later
  - Clip 1: Only 0.00s reaction aftermath after peak in payoff
  - Clip 1: Duration 45.65s outside [22.0s, 45.0s]
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Mailbox Conspiracy 😱** (`FLASHFORWARD_MYSTERY_INVESTIGATION`) | Hook: `MAILBOX CONSPIRACY 😱` | Dur: `45.65s` | Segments: [CONTINUOUS_ARC 6747.60sâ€“6793.25s] | SubScore: `75.0/95` â€” FLAGS: DURATION_OUT_OF_BOUNDS, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF
    - Diagnostics: Clip ends mid-clause 't want to junk mail. I have to read' with next word 'it' only 0.00s later; Only 0.00s reaction aftermath after peak in payoff; Duration 45.65s outside [22.0s, 45.0s]
  - **Clip 2 â€” Feeding The Beast 😭** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `FEEDING THE BEAST 😭` | Dur: `36.22s` | Segments: [WAGER_SETUP 5040.20sâ€“5050.07s], [KARMA_PAYOFF 5058.65sâ€“5085.00s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #6 â€” `VOD2_Tycoon_Full` â€” Score: **67.0/100**

- **Clip Count:** 1 | **Distinct Archetypes (1):** COMEDIC_STORYTELLING_OR_SARCASM
- **Fatal Flags:** HOOK_WORD_COUNT_OFF, MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Cross-VOD
- **Score & Diagnostics:**
  - HOOK_WORD_COUNT_OFF
  - MID_SENTENCE_START
  - PRE_HOOK_SPILLOVER_WORDS
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 1: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'Is'
  - Clip 1: Trailing prior-sentence fragment 'in town.' leaked into hook
  - Clip 1: Hook 'MAILBOX IS NOT A TEXT CHAIN' has 6 words (target 3-5)
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Mailbox Quest Rant 😡** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `MAILBOX IS NOT A TEXT CHAIN` | Dur: `26.76s` | Segments: [CONTINUOUS_ARC 6814.02sâ€“6840.78s] | SubScore: `77.0/95` â€” FLAGS: HOOK_WORD_COUNT_OFF, MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'Is'; Trailing prior-sentence fragment 'in town.' leaked into hook; Hook 'MAILBOX IS NOT A TEXT CHAIN' has 6 words (target 3-5)

### Iteration #7 â€” `VOD2_Tycoon_Full` â€” Score: **97.5/100**

- **Clip Count:** 4 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** FLAT_NO_MULTIMODAL_SIGNAL
- **What Changed in This Iteration:** Fixed leading = on ContextMergeAgent/Fallback/Mistral (CRITICAL), Whisper backward-overlap start guard, <=5 word hook clamp, and real VOD2 override JSON.
- **Score & Diagnostics:**
  - FLAT_NO_MULTIMODAL_SIGNAL
  - Clip 3: Zero dB/chat/face/pitch/viewer signals found in playback window
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Rainbow Lounge Ban 💀** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `FREE SCRAPS REJECTED` | Dur: `31.95s` | Segments: [CONTINUOUS_ARC 3125.88sâ€“3157.83s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Destroying The Server 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `I BEAT DRACO NOW` | Dur: `30.51s` | Segments: [WAGER_SETUP 7576.00sâ€“7586.80s], [KARMA_PAYOFF 7608.90sâ€“7628.61s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Playing Nonchalant 😭** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `ACTING LIKE I DONT CARE` | Dur: `35.7s` | Segments: [CONTINUOUS_ARC 6143.80sâ€“6179.50s] | SubScore: `85.0/95` â€” FLAGS: FLAT_NO_MULTIMODAL_SIGNAL
    - Diagnostics: Zero dB/chat/face/pitch/viewer signals found in playback window
  - **Clip 4 â€” Draco's Base Tour 🤯** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `PREPARING FOR DRACO TOUR` | Dur: `26.58s` | Segments: [PREMISE 7976.65sâ€“7985.10s], [PUNCHLINE 8008.02sâ€“8026.15s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #8 â€” `VOD1_Bugsnax_H1` â€” Score: **87.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL
- **Fatal Flags:** MID_SENTENCE_START, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Updated telemetry STOPWORDS (eliminated generic emotion callbacks like happy/funny) + Director SIGNAL GROUNDING REQUIREMENT + isolated Wait cap <=3s.
- **Score & Diagnostics:**
  - MID_SENTENCE_START
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 1: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'Is'
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Tasty Island Trap 😭** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `EVERYTHING IS SO TASTY` | Dur: `32.72s` | Segments: [CONTINUOUS_ARC 1137.77sâ€“1170.49s] | SubScore: `85.0/95` â€” FLAGS: MID_SENTENCE_START
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'Is'
  - **Clip 2 â€” Cinna Snail Overload 😱** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `TOO MANY CINNA SNAILS` | Dur: `24.77s` | Segments: [PREMISE 1930.30sâ€“1933.20s], [ESCALATION 1937.63sâ€“1959.50s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #9 â€” `VOD1_Bugsnax_H2` â€” Score: **97.33/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** DURATION_OUT_OF_BOUNDS, HOOK_WORD_COUNT_OFF
- **What Changed in This Iteration:** Added 4-char entity stem chaining in 5. Split Clips, strict non-overlapping +-3.2s sentence boundary scanner, and IF: Director Fallback JSON Valid?.
- **Score & Diagnostics:**
  - DURATION_OUT_OF_BOUNDS
  - HOOK_WORD_COUNT_OFF
  - Clip 3: Hook 'AWKWARD COUPLE' has 2 words (target 3-5)
  - Clip 3: Duration 20.95s outside [22.0s, 45.0s]
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Mailbox Rant 🤬** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `MAILBOX IS NOT A TEXT` | Dur: `25.16s` | Segments: [CONTINUOUS_ARC 6815.62sâ€“6840.78s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Rage Bading Fail 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `I AM THE RAGE BADER` | Dur: `22.5s` | Segments: [WAGER_SETUP 4236.80sâ€“4241.30s], [KARMA_PAYOFF 4252.15sâ€“4270.15s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Awkward Couple 💀** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `AWKWARD COUPLE` | Dur: `20.95s` | Segments: [PROMPT_SETUP 5269.00sâ€“5276.25s], [REACTION_PAYOFF 5367.54sâ€“5381.24s] | SubScore: `87.0/95` â€” FLAGS: DURATION_OUT_OF_BOUNDS, HOOK_WORD_COUNT_OFF
    - Diagnostics: Hook 'AWKWARD COUPLE' has 2 words (target 3-5); Duration 20.95s outside [22.0s, 45.0s]

### Iteration #10 â€” `VOD2_Tycoon_H1` â€” Score: **95.33/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS
- **What Changed in This Iteration:** Added post-snap >=22.0s sentence-safe floor rescue in 6. Extract Viral Segments + verifyHook 3-5 word preference over 2-word title fallbacks.
- **Score & Diagnostics:**
  - PRE_HOOK_SPILLOVER_WORDS
  - UNGROUNDED_HOOK_NOUNS
  - Clip 2: Trailing prior-sentence fragment 'Look at this.' leaked into hook
  - Clip 3: Trailing prior-sentence fragment 'Wow.' leaked into hook
  - Clip 3: None of hook words ['pass'] found in clip/summary corpus
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Bodyguard Betrayal 😱** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `STAY BACK LUNAR BASE` | Dur: `22.5s` | Segments: [PREMISE 4234.52sâ€“4238.30s], [PUNCHLINE 4243.13sâ€“4261.85s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Standing Right There 😭** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `YOU ARE STANDING THERE` | Dur: `22.62s` | Segments: [PROMPT_SETUP 3342.00sâ€“3346.71s], [REACTION_PAYOFF 3363.11sâ€“3381.02s] | SubScore: `90.0/95` â€” FLAGS: PRE_HOOK_SPILLOVER_WORDS
    - Diagnostics: Trailing prior-sentence fragment 'Look at this.' leaked into hook
  - **Clip 3 â€” Failed The Test 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `SHE DID NOT PASS` | Dur: `22.23s` | Segments: [WAGER_SETUP 3883.82sâ€“3888.20s], [KARMA_PAYOFF 3894.14sâ€“3911.99s] | SubScore: `86.0/95` â€” FLAGS: PRE_HOOK_SPILLOVER_WORDS, UNGROUNDED_HOOK_NOUNS
    - Diagnostics: Trailing prior-sentence fragment 'Wow.' leaked into hook; None of hook words ['pass'] found in clip/summary corpus

### Iteration #11 â€” `VOD2_Tycoon_H2` â€” Score: **60.0/100**

- **Clip Count:** 1 | **Distinct Archetypes (1):** CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL
- **Fatal Flags:** DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Fixed capitalized opener false positive in edl_auditor.py (PRE_HOOK_SPILLOVER_WORDS) + ContextMergeAgent concrete transcript-word hook grounding rule.
- **Score & Diagnostics:**
  - DEAD_AIR_OVER_5S
  - FLAT_NO_MULTIMODAL_SIGNAL
  - PREMATURE_PAYOFF_CUTOFF
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 1: Clip ends mid-clause 'Roblox' with next word 'gaming,' only 0.00s later
  - Clip 1: Zero dB/chat/face/pitch/viewer signals found in playback window
  - Clip 1: Segment 1 has 27.00s silent gap (3.0-30.0)
- **Generated Scenarios Summary:**
  - **Clip 1 â€” KreekCraft_Backup_Clip** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `PLAYING ROBLOX GAME` | Dur: `29.0s` | Segments: [CONTINUOUS_ARC 3.00sâ€“32.00s] | SubScore: `70.0/95` â€” FLAGS: DEAD_AIR_OVER_5S, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF
    - Diagnostics: Clip ends mid-clause 'Roblox' with next word 'gaming,' only 0.00s later; Zero dB/chat/face/pitch/viewer signals found in playback window; Segment 1 has 27.00s silent gap (3.0-30.0)

### Iteration #12 â€” `VOD2_Tycoon_H2` â€” Score: **79.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** COMEDIC_STORYTELLING_OR_SARCASM, FLASHFORWARD_MYSTERY_INVESTIGATION
- **Fatal Flags:** DANGLING_CLIMAX_PHRASE, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Added multi-run Director clip salvage + multimodal anchor fallback in 5. Split Clips to prevent Backup_Clip regressions when Backup/Mistral hit 429 or timeout.
- **Score & Diagnostics:**
  - DANGLING_CLIMAX_PHRASE
  - FLAT_NO_MULTIMODAL_SIGNAL
  - PREMATURE_PAYOFF_CUTOFF
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 2: Clip ends mid-clause 'nk my gold base is better. Oh wait,' with next word 'actually,' only 0.00s later
  - Clip 2: Ends on dangling phrase ' gold base is better. Oh wait,'
  - Clip 2: Zero dB/chat/face/pitch/viewer signals found in playback window
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Rainbow Lounge VIP 🌈** (`FLASHFORWARD_MYSTERY_INVESTIGATION`) | Hook: `WELCOME TO RAINBOW LOUNGE` | Dur: `23.29s` | Segments: [SETUP 6667.93sâ€“6671.80s], [ESCALATION 6705.98sâ€“6709.72s], [PAYOFF 6714.60sâ€“6730.27s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Secret Code Bit 🤫** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `COMMENT BU40 RIGHT NOW` | Dur: `23.73s` | Segments: [CONTINUOUS_ARC 8372.34sâ€“8396.07s] | SubScore: `69.0/95` â€” FLAGS: DANGLING_CLIMAX_PHRASE, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF
    - Diagnostics: Clip ends mid-clause 'nk my gold base is better. Oh wait,' with next word 'actually,' only 0.00s later; Ends on dangling phrase ' gold base is better. Oh wait,'; Zero dB/chat/face/pitch/viewer signals found in playback window

### Iteration #13 â€” `VOD2_Tycoon_H2` â€” Score: **93.5/100**

- **Clip Count:** 4 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** DANGLING_CLIMAX_PHRASE, FLAT_NO_MULTIMODAL_SIGNAL, PREMATURE_PAYOFF_CUTOFF
- **What Changed in This Iteration:** Rebuilt full 8929s empirical VOD2 audio+face index via multimodal_analyzer.py + expanded final-segment terminal punctuation guard to +-3.5s in 6. Extract Viral Segments.
- **Score & Diagnostics:**
  - DANGLING_CLIMAX_PHRASE
  - FLAT_NO_MULTIMODAL_SIGNAL
  - PREMATURE_PAYOFF_CUTOFF
  - Clip 2: Zero dB/chat/face/pitch/viewer signals found in playback window
  - Clip 4: Clip ends mid-clause 'nk my gold base is better. Oh wait,' with next word 'actually,' only 0.00s later
  - Clip 4: Ends on dangling phrase ' gold base is better. Oh wait,'
- **Generated Scenarios Summary:**
  - **Clip 1 â€” BB-8 Event Panic 😱** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `BB-8 EVENT IS UNLOCKING` | Dur: `25.43s` | Segments: [CONTINUOUS_ARC 8271.26sâ€“8296.68s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Acting Nonchalant 💀** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `ACTING TOTALLY NONCHALANT` | Dur: `26.9s` | Segments: [CONTINUOUS_ARC 6143.80sâ€“6170.70s] | SubScore: `85.0/95` â€” FLAGS: FLAT_NO_MULTIMODAL_SIGNAL
    - Diagnostics: Zero dB/chat/face/pitch/viewer signals found in playback window
  - **Clip 3 â€” Rainbow Lounge Flex ✨** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `WELCOME TO RAINBOW LOUNGE` | Dur: `23.23s` | Segments: [CONTINUOUS_ARC 6702.45sâ€“6725.67s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 4 â€” Secret Chaos Code 🤫** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `SECRET STREAMER CODE WORD` | Dur: `23.73s` | Segments: [CONTINUOUS_ARC 8372.34sâ€“8396.07s] | SubScore: `79.0/95` â€” FLAGS: DANGLING_CLIMAX_PHRASE, PREMATURE_PAYOFF_CUTOFF
    - Diagnostics: Clip ends mid-clause 'nk my gold base is better. Oh wait,' with next word 'actually,' only 0.00s later; Ends on dangling phrase ' gold base is better. Oh wait,'

### Iteration #14 â€” `VOD1_Bugsnax_Mid` â€” Score: **95.0/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, FLASHFORWARD_MYSTERY_INVESTIGATION
- **Fatal Flags:** MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS
- **What Changed in This Iteration:** Strict comma/filler rejection inside isTerminalEnd (gap > 0.85s required if no .!?) + viewer comment-bait filter in OUTRO_PANHANDLING_RE & edl_auditor.py.
- **Score & Diagnostics:**
  - MID_SENTENCE_START
  - PRE_HOOK_SPILLOVER_WORDS
  - Clip 3: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'the'
  - Clip 3: Trailing prior-sentence fragment 'restroom.' leaked into hook
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Rage Baiting Snacks 🍫** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `YOURE ABOUT TO BECOME SNACKS` | Dur: `30.7s` | Segments: [CONTINUOUS_ARC 2425.80sâ€“2456.50s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Awkward Hugs 🫂** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `BESTOW A HUG ON YOU` | Dur: `30.36s` | Segments: [CONTINUOUS_ARC 2528.50sâ€“2558.86s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Restroom Clues 🕵️‍♂️** (`FLASHFORWARD_MYSTERY_INVESTIGATION`) | Hook: `SCAN THE AREA FOR CLUES` | Dur: `31.94s` | Segments: [CONTINUOUS_ARC 3419.85sâ€“3451.79s] | SubScore: `80.0/95` â€” FLAGS: MID_SENTENCE_START, PRE_HOOK_SPILLOVER_WORDS
    - Diagnostics: Pre-hook pause 0.00s (<0.4s) after non-terminal token 'the'; Trailing prior-sentence fragment 'restroom.' leaked into hook

### Iteration #15 â€” `VOD2_Tycoon_Mid` â€” Score: **92.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** COMEDIC_STORYTELLING_OR_SARCASM, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Added Monotonic Midpoint Sentence Opener Guard in 6. Extract Viral Segments eliminating residual prior-sentence spillover words (e.g. restroom.).
- **Score & Diagnostics:**
  - LOW_ARCHETYPE_DIVERSITY
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Rainbow Lounge Denied 💀** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `REJECTED FROM RAINBOW LOUNGE` | Dur: `28.15s` | Segments: [CONTINUOUS_ARC 3124.40sâ€“3152.55s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Security Guard Fired 😭** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `SECURITY GUARD FIRED` | Dur: `22.01s` | Segments: [CONTINUOUS_ARC 4485.09sâ€“4507.10s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #16 â€” `VOD2_Tycoon_Mid` â€” Score: **100.0/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** None (Clean Pass)
- **What Changed in This Iteration:** Expanded Director anchor context to 780 chars, added strict >=3 archetype & >=14s duration quality gate on IF: Director JSON Valid?, and increased <22s tail rescue reach to 20s.
- **Score & Diagnostics:**
  - None - All clips clean
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Zero Hat Policy 😭** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `ACT LIKE YOU DONT WANT` | Dur: `29.87s` | Segments: [PREMISE 6143.80sâ€“6149.20s], [ESCALATION 6157.33sâ€“6170.70s], [PUNCHLINE 6182.80sâ€“6193.90s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Rainbow Lounge Invite 🤯** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `WELCOME TO RAINBOW LOUNGE` | Dur: `22.6s` | Segments: [PROMPT_SETUP 6581.10sâ€“6590.60s], [REACTION_PAYOFF 6655.20sâ€“6668.30s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Failed Security Duty 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `SECURITY GUARD TRAINING FAIL` | Dur: `23.27s` | Segments: [WAGER_SETUP 3718.10sâ€“3726.05s], [ESCALATION 3743.80sâ€“3747.83s], [KARMA_PAYOFF 3777.05sâ€“3788.34s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #17 â€” `VOD1_Bugsnax_H1` â€” Score: **90.0/100**

- **Clip Count:** 2 | **Distinct Archetypes (1):** HUBRIS_WAGER_INSTANT_KARMA
- **Fatal Flags:** LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Cross-VOD stress-test on VOD1 Hour 1 (0-3700s) with Iteration 16 pipeline (anchor context 780ch, >=3 archetype gate, Monotonic Midpoint Guard).
- **Score & Diagnostics:**
  - LOW_ARCHETYPE_DIVERSITY
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Lost My Balls 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `I LOST MY BALLS` | Dur: `34.13s` | Segments: [WAGER_SETUP 1445.94sâ€“1449.03s], [ESCALATION 1465.22sâ€“1479.54s], [KARMA_PAYOFF 1523.90sâ€“1540.63s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Cabin Trap Fail 😭** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `CABIN TRAP FAIL` | Dur: `27.81s` | Segments: [WAGER_SETUP 1137.27sâ€“1142.30s], [ESCALATION 1332.40sâ€“1344.92s], [KARMA_PAYOFF 1354.60sâ€“1364.85s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #18 â€” `VOD1_Bugsnax_H1` â€” Score: **92.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, HUBRIS_WAGER_INSTANT_KARMA
- **Fatal Flags:** LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Enforced max 1 FLASHFORWARD per batch & >=3 tight single-scene/continuous/roast/comedy/hubris clips (24-44s) in Scout & Director prompts.
- **Score & Diagnostics:**
  - LOW_ARCHETYPE_DIVERSITY
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Instant Burger Karma 🍔** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `THE BURGER HIT US` | Dur: `22.76s` | Segments: [WAGER_SETUP 3140.73sâ€“3144.22s], [ESCALATION 3163.31sâ€“3168.54s], [KARMA_PAYOFF 3173.56sâ€“3187.60s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Following Spooky Tracks 👣** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `FOLLOW THE TRACKS` | Dur: `25.61s` | Segments: [CONTINUOUS_ARC 3426.18sâ€“3451.79s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #19 â€” `VOD2_Tycoon_H1` â€” Score: **98.75/100**

- **Clip Count:** 4 | **Distinct Archetypes (4):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** DEAD_AIR_OVER_5S
- **What Changed in This Iteration:** Relaxed minPayoffGap from 90s to 50s for dense comedic bursts while keeping >6s segment overlap protection.
- **Score & Diagnostics:**
  - DEAD_AIR_OVER_5S
  - Clip 3: Segment 1 has 6.20s silent gap (2455.5-2461.7)
- **Generated Scenarios Summary:**
  - **Clip 1 â€” BB-8 Live Event! 😱** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `BB-8 LIVE EVENT UNLOCKED` | Dur: `38.34s` | Segments: [CONTINUOUS_ARC 1044.26sâ€“1082.60s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Donating Rainbow Droids? 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `DONATING THE RAINBOW DROID` | Dur: `39.44s` | Segments: [CONTINUOUS_ARC 2275.67sâ€“2315.11s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Morning Grind Madness 😭** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `MORNING GRIND MADNESS` | Dur: `42.51s` | Segments: [CONTINUOUS_ARC 2439.49sâ€“2482.00s] | SubScore: `90.0/95` â€” FLAGS: DEAD_AIR_OVER_5S
    - Diagnostics: Segment 1 has 6.20s silent gap (2455.5-2461.7)
  - **Clip 4 â€” Fastest Droid Ever! ⚡** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `FASTEST DROID EVER` | Dur: `23.29s` | Segments: [CONTINUOUS_ARC 4078.32sâ€“4101.60s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #20 â€” `VOD2_Tycoon_Full` â€” Score: **82.5/100**

- **Clip Count:** 2 | **Distinct Archetypes (2):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL
- **Fatal Flags:** DANGLING_CLIMAX_PHRASE, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF, LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Prevented collapsedSegs from re-merging across >5.0s dead-air cuts (_dead_split_after flag) + tightened dead-air trim padding to +-0.35s.
- **Score & Diagnostics:**
  - DANGLING_CLIMAX_PHRASE
  - INSUFFICIENT_AFTERMATH
  - PREMATURE_PAYOFF_CUTOFF
  - LOW_ARCHETYPE_DIVERSITY
  - Clip 2: Clip ends mid-clause ' rainbow lounge? Yeah, I'm going to' with next word 'flex' only 0.00s later
  - Clip 2: Ends on dangling phrase 'bow lounge? Yeah, I'm going to'
  - Clip 2: Only 0.00s reaction aftermath after peak in payoff
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Coolest Room Ever 🤯** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `MY COLDEST ROOM EVER` | Dur: `29.64s` | Segments: [CONTINUOUS_ARC 2458.43sâ€“2488.07s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Donating Rainbows? 😭** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `DONATE THE RAINBOW DROID` | Dur: `23.77s` | Segments: [PREMISE 2277.10sâ€“2282.82s], [ESCALATION 2311.89sâ€“2317.60s], [PUNCHLINE 2324.47sâ€“2336.82s] | SubScore: `75.0/95` â€” FLAGS: DANGLING_CLIMAX_PHRASE, INSUFFICIENT_AFTERMATH, PREMATURE_PAYOFF_CUTOFF
    - Diagnostics: Clip ends mid-clause ' rainbow lounge? Yeah, I'm going to' with next word 'flex' only 0.00s later; Ends on dangling phrase 'bow lounge? Yeah, I'm going to'; Only 0.00s reaction aftermath after peak in payoff

### Iteration #21 â€” `VOD2_Tycoon_Full` â€” Score: **100.0/100**

- **Clip Count:** 4 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** None (Clean Pass)
- **What Changed in This Iteration:** Added two-pass .!?-first terminal snapping rejecting dangling prepositions/auxiliaries (to/going) + raised Director JSON solid clip floor from 14s to 19s.
- **Score & Diagnostics:**
  - None - All clips clean
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Nonchalant Hat Glitch 🤯** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `ACTING NONCHALANT FOR HATS` | Dur: `44.38s` | Segments: [PREMISE 6143.80sâ€“6156.44s], [ESCALATION 6166.10sâ€“6179.50s], [PUNCHLINE 6325.62sâ€“6343.96s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Coolest Room Ever 😭** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `MY COLDEST ROOM YET` | Dur: `22.57s` | Segments: [PROMPT_SETUP 2461.70sâ€“2466.41s], [REACTION_PAYOFF 2475.34sâ€“2493.20s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Secret Rainbow Cartel 😱** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `SECRET RAINBOW DROIDS` | Dur: `22.81s` | Segments: [PREMISE 472.84sâ€“476.00s], [PUNCHLINE 482.31sâ€“501.95s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 4 â€” Pickaxe Disconnect 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `FORGOT MY PICKAXE` | Dur: `27.18s` | Segments: [CONTINUOUS_ARC 1499.42sâ€“1526.60s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #22 â€” `VOD1_Bugsnax_Full` â€” Score: **97.5/100**

- **Clip Count:** 3 | **Distinct Archetypes (2):** COMEDIC_STORYTELLING_OR_SARCASM, HUBRIS_WAGER_INSTANT_KARMA
- **Fatal Flags:** LOW_ARCHETYPE_DIVERSITY
- **What Changed in This Iteration:** Final Champion Validation Run on default VOD1_Bugsnax_Full (0-7450s) with override cleared and Iteration 21 two-pass .!?-first boundary & diversity engine intact.
- **Score & Diagnostics:**
  - LOW_ARCHETYPE_DIVERSITY
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Taking Snorpy's Balls 💀** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `TAKE MY NEWEST INVENTION` | Dur: `38.44s` | Segments: [WAGER_SETUP 1465.22sâ€“1479.54s], [ESCALATION 1526.90sâ€“1537.14s], [KARMA_PAYOFF 1590.60sâ€“1604.48s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Mailbox Rage 😡** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `THIS IS NOT A TEXT` | Dur: `27.23s` | Segments: [CONTINUOUS_ARC 6813.56sâ€“6840.78s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Trappy Nose Fail 😭** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `JUST DO A TRAPPY` | Dur: `24.33s` | Segments: [WAGER_SETUP 6246.30sâ€“6251.61s], [ESCALATION 6265.88sâ€“6284.90s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #23 â€” `VOD1_Bugsnax_Full` â€” Score: **100.0/100**

- **Clip Count:** 3 | **Distinct Archetypes (3):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, HUBRIS_WAGER_INSTANT_KARMA
- **Fatal Flags:** None (Clean Pass)
- **What Changed in This Iteration:** Final Champion Validation (Iteration 23): enforced distinct >=120s Anchor ID spread per clip in Director + restored >=15s pre-rescue gate on IF: Director JSON Valid?.
- **Score & Diagnostics:**
  - None - All clips clean
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Mailbox Rage 💀** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `THIS IS A MAILBOX` | Dur: `41.77s` | Segments: [CONTINUOUS_ARC 6782.56sâ€“6824.34s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Lifting Houses 😱** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `DO NOT LIFT MY CRIB` | Dur: `26.56s` | Segments: [WAGER_SETUP 1272.90sâ€“1281.40s], [KARMA_PAYOFF 1290.58sâ€“1308.64s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Burning Smore Rage 😭** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `ITS CHOSEN DEATH` | Dur: `34.34s` | Segments: [CONTINUOUS_ARC 2336.56sâ€“2370.90s] | SubScore: `95.0/95` â€” PASS (95/95)

### Iteration #24 â€” `VOD1_Bugsnax_Full` â€” Score: **99.25/100**

- **Clip Count:** 4 | **Distinct Archetypes (4):** COMEDIC_STORYTELLING_OR_SARCASM, CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL, HUBRIS_WAGER_INSTANT_KARMA, VIEWER_OR_CHAT_ROAST_INTERACTION
- **Fatal Flags:** HOOK_WORD_COUNT_OFF
- **What Changed in This Iteration:** Final build post-regression-suite validation (post-pause exclamation boundary guard + spoken-gap check inside collapsedSegs) on default VOD1_Bugsnax_Full.
- **Score & Diagnostics:**
  - HOOK_WORD_COUNT_OFF
  - Clip 3: Hook 'IMPOSSIBLE SPEEDRUN' has 2 words (target 3-5)
- **Generated Scenarios Summary:**
  - **Clip 1 â€” Tower Clutch Jump 💀** (`CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`) | Hook: `ARE WE GOING TO` | Dur: `30.09s` | Segments: [CONTINUOUS_ARC 2638.62sâ€“2668.70s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 2 â€” Mailbox Rant 😡** (`COMEDIC_STORYTELLING_OR_SARCASM`) | Hook: `STOP SENDING ME QUESTS` | Dur: `43.74s` | Segments: [CONTINUOUS_ARC 6780.60sâ€“6824.34s] | SubScore: `95.0/95` â€” PASS (95/95)
  - **Clip 3 â€” Impossible Speedrun 😭** (`HUBRIS_WAGER_INSTANT_KARMA`) | Hook: `IMPOSSIBLE SPEEDRUN` | Dur: `38.49s` | Segments: [CONTINUOUS_ARC 4053.03sâ€“4091.52s] | SubScore: `92.0/95` â€” FLAGS: HOOK_WORD_COUNT_OFF
    - Diagnostics: Hook 'IMPOSSIBLE SPEEDRUN' has 2 words (target 3-5)
  - **Clip 4 â€” Teamwork Copium 😭** (`VIEWER_OR_CHAT_ROAST_INTERACTION`) | Hook: `NO MATCH FOR TEAMWORK` | Dur: `32.26s` | Segments: [CONTINUOUS_ARC 6702.35sâ€“6734.61s] | SubScore: `95.0/95` â€” PASS (95/95)

## 3. Final Champion Iterations Full Deep-Dive

### Champion Run: Iteration #24 (`VOD1_Bugsnax_Full`) â€” **99.25/100**

#### Clip #1: Tower Clutch Jump 💀

- **Title:** Tower Clutch Jump 💀
- **Top Hook Caption:** `ARE WE GOING TO`
- **Archetype:** `CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL`
- **Total Duration:** `30.09s` (`segment_count=1`)
- **Virality Score:** `9.4`
- **Pre-Hook 5s Context:** "that. The flying. We got to knock the, uh, white fellow into it."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[CONTINUOUS_ARC 2638.62s - 2668.70s]` (43:58.62â€“44:28.70) `[WPM_SPIKE: 258wpm] [DRAMATIC_PAUSE: 1.3s] [dB_PEAK:+6.7dB] [DRAMATIC_PAUSE: 2.9s] [SCREAM][dB_PEAK:+10.0dB] [DRAMATIC_PAUSE: 1.6s] [DRAMATIC_PAUSE: 1.7s]`: "Watch this. Are we going to boink it? We're gonna boop it. Boop. It died. Alright, return to me for the next release of the plan. No way! Oh, never mind, I'm okay. We did it. I have your device. Ah, chum, I have such a craving for cookies."
- **Post-Payoff 5s Context:** "Why, my craving is so terrible that I would like my teeth to be quookies,"
- **Why This Clip Is Viral:** Continuous single-take gameplay sequence where the streamer successfully pulls off a risky maneuver.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 1,
  "title": "Tower Clutch Jump 💀",
  "final_top_hook_caption": "ARE WE GOING TO",
  "narrative_archetype": "CONTINUOUS_GAMEPLAY_CLUTCH_OR_FAIL",
  "virality_score": 9.4,
  "total_duration_sec": 30.09,
  "segment_count": 1,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "CONTINUOUS_ARC",
      "start": 2638.618,
      "end": 2668.704,
      "start_tc": "43:58.62",
      "end_tc": "44:28.70",
      "duration": 30.086,
      "spoken_text": "Watch this. Are we going to boink it? We're gonna boop it. Boop. It died. Alright, return to me for the next release of the plan. No way! Oh, never mind, I'm okay. We did it. I have your device. Ah, chum, I have such a craving for cookies.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 258wpm]",
        "[DRAMATIC_PAUSE: 1.3s]",
        "[dB_PEAK:+6.7dB]",
        "[DRAMATIC_PAUSE: 2.9s]",
        "[SCREAM][dB_PEAK:+10.0dB]",
        "[DRAMATIC_PAUSE: 1.6s]",
        "[DRAMATIC_PAUSE: 1.7s]"
      ]
    }
  ],
  "assembled_spoken_script": "Watch this. Are we going to boink it? We're gonna boop it. Boop. It died. Alright, return to me for the next release of the plan. No way! Oh, never mind, I'm okay. We did it. I have your device. Ah, chum, I have such a craving for cookies.",
  "pre_hook_context_text": "that. The flying. We got to knock the, uh, white fellow into it.",
  "post_payoff_context_text": "Why, my craving is so terrible that I would like my teeth to be quookies,",
  "signal_justification": {
    "chat_burst": "Z=2.8 sigma high tension chat reaction",
    "db_spike": "+10.0dB scream peak at tower jump",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": false
  },
  "cause_and_effect_setup": "Continuous single-take gameplay sequence where the streamer successfully pulls off a risky maneuver.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 0,
    "shared_tokens": [],
    "reason": "contiguous_single_segment"
  },
  "climax_quote": "Are we going to boink it?",
  "memes": []
}
```

</details>

#### Clip #2: Mailbox Rant 😡

- **Title:** Mailbox Rant 😡
- **Top Hook Caption:** `STOP SENDING ME QUESTS`
- **Archetype:** `COMEDIC_STORYTELLING_OR_SARCASM`
- **Total Duration:** `43.74s` (`segment_count=1`)
- **Virality Score:** `9.3`
- **Pre-Hook 5s Context:** "all four types of Pilbug. Please make it happy. That's hilarious."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[CONTINUOUS_ARC 6780.60s - 6824.34s]` (113:00.60â€“113:44.34) `[SCREAM][dB_PEAK:+10.0dB] [LAUGH_BURST] [CHAT_BURST: Z=2.41 | "u never claimed it xD", "im willing to trade mine but idek what you could offer LOL"] [WPM_SPIKE: 367wpm] [WPM_SPIKE: 248wpm] [WPM_SPIKE: 232wpm] [WPM_SPIKE: 400wpm] [WPM_SPIKE: 250wpm] [WPM_SPIKE: 411wpm] [WPM_SPIKE: 344wpm]`: "I can use... Guys, they're using our mailbox as a messaging system. This is dumb, y'all. Well, I don't have to read this. This is griefing. Y'all just want to junk mail. I have to read it off. Ah, chum. I can use your health stress testing the snack-o-grapper. It excels at snatching snack pods, so if you can catch any five of them under your 30 seconds, that'd be stupendous. Under 30? They're wanting a speed run? I didn't. Guys, I thought this was a mailbox. Okay? Everyone in town. Can we just decorate our house? Okay, no, I have to rant to everyone in town. Everyone in town, this is a mailbox. You send letters. You do not send me quests. I do not want to do them. I do not need a quick box."
- **Post-Payoff 5s Context:** "Yeah, and do not send me, like, this is not a text chain."
- **Why This Clip Is Viral:** Streamer reads an absurd mailbox quest, escalating into a full comedy rant about proper mail etiquette.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 2,
  "title": "Mailbox Rant 😡",
  "final_top_hook_caption": "STOP SENDING ME QUESTS",
  "narrative_archetype": "COMEDIC_STORYTELLING_OR_SARCASM",
  "virality_score": 9.3,
  "total_duration_sec": 43.74,
  "segment_count": 1,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "CONTINUOUS_ARC",
      "start": 6780.595,
      "end": 6824.335,
      "start_tc": "113:00.60",
      "end_tc": "113:44.34",
      "duration": 43.74,
      "spoken_text": "I can use... Guys, they're using our mailbox as a messaging system. This is dumb, y'all. Well, I don't have to read this. This is griefing. Y'all just want to junk mail. I have to read it off. Ah, chum. I can use your health stress testing the snack-o-grapper. It excels at snatching snack pods, so if you can catch any five of them under your 30 seconds, that'd be stupendous. Under 30? They're wanting a speed run? I didn't. Guys, I thought this was a mailbox. Okay? Everyone in town. Can we just decorate our house? Okay, no, I have to rant to everyone in town. Everyone in town, this is a mailbox. You send letters. You do not send me quests. I do not want to do them. I do not need a quick box.",
      "signal_tags_in_window": [
        "[SCREAM][dB_PEAK:+10.0dB]",
        "[LAUGH_BURST]",
        "[CHAT_BURST: Z=2.41 | \"u never claimed it xD\", \"im willing to trade mine but idek what you could offer LOL\"]",
        "[WPM_SPIKE: 367wpm]",
        "[WPM_SPIKE: 248wpm]",
        "[WPM_SPIKE: 232wpm]",
        "[WPM_SPIKE: 400wpm]",
        "[WPM_SPIKE: 250wpm]",
        "[WPM_SPIKE: 411wpm]",
        "[WPM_SPIKE: 344wpm]"
      ]
    }
  ],
  "assembled_spoken_script": "I can use... Guys, they're using our mailbox as a messaging system. This is dumb, y'all. Well, I don't have to read this. This is griefing. Y'all just want to junk mail. I have to read it off. Ah, chum. I can use your health stress testing the snack-o-grapper. It excels at snatching snack pods, so if you can catch any five of them under your 30 seconds, that'd be stupendous. Under 30? They're wanting a speed run? I didn't. Guys, I thought this was a mailbox. Okay? Everyone in town. Can we just decorate our house? Okay, no, I have to rant to everyone in town. Everyone in town, this is a mailbox. You send letters. You do not send me quests. I do not want to do them. I do not need a quick box.",
  "pre_hook_context_text": "all four types of Pilbug. Please make it happy. That's hilarious.",
  "post_payoff_context_text": "Yeah, and do not send me, like, this is not a text chain.",
  "signal_justification": {
    "chat_burst": "Z=2.41 sigma chat laughing burst",
    "db_spike": "+10.0dB vocal rant peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": false
  },
  "cause_and_effect_setup": "Streamer reads an absurd mailbox quest, escalating into a full comedy rant about proper mail etiquette.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 0,
    "shared_tokens": [],
    "reason": "contiguous_single_segment"
  },
  "climax_quote": "You do not send me quests",
  "memes": []
}
```

</details>

#### Clip #3: Impossible Speedrun 😭

- **Title:** Impossible Speedrun 😭
- **Top Hook Caption:** `IMPOSSIBLE SPEEDRUN`
- **Archetype:** `HUBRIS_WAGER_INSTANT_KARMA`
- **Total Duration:** `38.49s` (`segment_count=1`)
- **Virality Score:** `9.1`
- **Pre-Hook 5s Context:** "it. on the rock. Can't put it on the bed."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[CONTINUOUS_ARC 4053.03s - 4091.52s]` (67:33.03â€“68:11.52) `[WPM_SPIKE: 362wpm] [SCREAM][dB_PEAK:+10.0dB] [WPM_SPIKE: 391wpm] [WPM_SPIKE: 229wpm] [WPM_SPIKE: 221wpm] [WPM_SPIKE: 260wpm] [WPM_SPIKE: 245wpm] [DRAMATIC_PAUSE: 1.4s] [WPM_SPIKE: 514wpm] [DRAMATIC_PAUSE: 4.9s] [WPM_SPIKE: 225wpm] [WPM_SPIKE: 296wpm] [DRAMATIC_PAUSE: 1.7s]`: "Whoa, this is going to be hard. It's going to jump this way. It's going to jump. Drakko, how am I going to... Right there. Yeah, you gotta aim a little higher. There, right there. In the yellow. No way. You gotta wait for it to come right. No way that's gonna work. No way that's gonna work. You gotta go a little higher. Oh, come on. Oh, does it love anything? Oh, yeah, it's... Oh, Miss Lucy wants something really hard to catch. Oh, bro! Of course she wants... Oh, maybe I have to go farther back. Oh my gosh."
- **Post-Payoff 5s Context:** "Does it like"
- **Why This Clip Is Viral:** 

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 3,
  "title": "Impossible Speedrun 😭",
  "final_top_hook_caption": "IMPOSSIBLE SPEEDRUN",
  "narrative_archetype": "HUBRIS_WAGER_INSTANT_KARMA",
  "virality_score": 9.1,
  "total_duration_sec": 38.49,
  "segment_count": 1,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "CONTINUOUS_ARC",
      "start": 4053.027,
      "end": 4091.517,
      "start_tc": "67:33.03",
      "end_tc": "68:11.52",
      "duration": 38.49,
      "spoken_text": "Whoa, this is going to be hard. It's going to jump this way. It's going to jump. Drakko, how am I going to... Right there. Yeah, you gotta aim a little higher. There, right there. In the yellow. No way. You gotta wait for it to come right. No way that's gonna work. No way that's gonna work. You gotta go a little higher. Oh, come on. Oh, does it love anything? Oh, yeah, it's... Oh, Miss Lucy wants something really hard to catch. Oh, bro! Of course she wants... Oh, maybe I have to go farther back. Oh my gosh.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 362wpm]",
        "[SCREAM][dB_PEAK:+10.0dB]",
        "[WPM_SPIKE: 391wpm]",
        "[WPM_SPIKE: 229wpm]",
        "[WPM_SPIKE: 221wpm]",
        "[WPM_SPIKE: 260wpm]",
        "[WPM_SPIKE: 245wpm]",
        "[DRAMATIC_PAUSE: 1.4s]",
        "[WPM_SPIKE: 514wpm]",
        "[DRAMATIC_PAUSE: 4.9s]",
        "[WPM_SPIKE: 225wpm]",
        "[WPM_SPIKE: 296wpm]",
        "[DRAMATIC_PAUSE: 1.7s]"
      ]
    }
  ],
  "assembled_spoken_script": "Whoa, this is going to be hard. It's going to jump this way. It's going to jump. Drakko, how am I going to... Right there. Yeah, you gotta aim a little higher. There, right there. In the yellow. No way. You gotta wait for it to come right. No way that's gonna work. No way that's gonna work. You gotta go a little higher. Oh, come on. Oh, does it love anything? Oh, yeah, it's... Oh, Miss Lucy wants something really hard to catch. Oh, bro! Of course she wants... Oh, maybe I have to go farther back. Oh my gosh.",
  "pre_hook_context_text": "it. on the rock. Can't put it on the bed.",
  "post_payoff_context_text": "Does it like",
  "signal_justification": {
    "chat_burst": "Z=2.6 sigma laughter explosion",
    "db_spike": "+10.0dB frustration peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": false
  },
  "cause_and_effect_setup": "",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 0,
    "shared_tokens": [],
    "reason": "contiguous_single_segment"
  },
  "climax_quote": "Of course she wants",
  "memes": [
    {
      "sound": "vine-boom-sound-effect_KT89XIq.mp3",
      "timestamp": 70.8,
      "volume": 0.35
    }
  ]
}
```

</details>

#### Clip #4: Teamwork Copium 😭

- **Title:** Teamwork Copium 😭
- **Top Hook Caption:** `NO MATCH FOR TEAMWORK`
- **Archetype:** `VIEWER_OR_CHAT_ROAST_INTERACTION`
- **Total Duration:** `32.26s` (`segment_count=1`)
- **Virality Score:** `8.9`
- **Pre-Hook 5s Context:** "You may have this plant that I found, Floofty, a red tea plant."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[CONTINUOUS_ARC 6702.35s - 6734.61s]` (111:42.35â€“112:14.61) `[WPM_SPIKE: 223wpm] [LAUGH_BURST] [CHAT_BURST: Z=2.57 | "one pet doesn't automatically make the game p2w lol", "im willing to trade mine but idek what you could offer LOL"] [WPM_SPIKE: 225wpm] [SCREAM][dB_PEAK:+10.0dB] [WPM_SPIKE: 257wpm] [WPM_SPIKE: 236wpm]`: "Hey, buddy. Thanks for hanging out and telling scary stories. I'm not the biggest fan of getting spooked, but I'm lucky I've got a friend like you to keep my courage up. Oh, a grumpy baby mare! That's cute. Well, you got merch? That's cool. Thanks. Okay, Filbo, a little obsessive. Thanks for calming the crowd, buddy. The others might fight a lot, but I know that we'll all come together when things get tough. Whatever monsters out there, it's no match for our teamwork. Hey, you got good Philbo boys."
- **Post-Payoff 5s Context:** "Hey, Bessie. I've been itching to take another look at your Bugapedia. Have you"
- **Why This Clip Is Viral:** Streamer interacts with NPC dialogue while processing the eerie mood of the island.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 4,
  "title": "Teamwork Copium 😭",
  "final_top_hook_caption": "NO MATCH FOR TEAMWORK",
  "narrative_archetype": "VIEWER_OR_CHAT_ROAST_INTERACTION",
  "virality_score": 8.9,
  "total_duration_sec": 32.26,
  "segment_count": 1,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "CONTINUOUS_ARC",
      "start": 6702.35,
      "end": 6734.61,
      "start_tc": "111:42.35",
      "end_tc": "112:14.61",
      "duration": 32.26,
      "spoken_text": "Hey, buddy. Thanks for hanging out and telling scary stories. I'm not the biggest fan of getting spooked, but I'm lucky I've got a friend like you to keep my courage up. Oh, a grumpy baby mare! That's cute. Well, you got merch? That's cool. Thanks. Okay, Filbo, a little obsessive. Thanks for calming the crowd, buddy. The others might fight a lot, but I know that we'll all come together when things get tough. Whatever monsters out there, it's no match for our teamwork. Hey, you got good Philbo boys.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 223wpm]",
        "[LAUGH_BURST]",
        "[CHAT_BURST: Z=2.57 | \"one pet doesn't automatically make the game p2w lol\", \"im willing to trade mine but idek what you could offer LOL\"]",
        "[WPM_SPIKE: 225wpm]",
        "[SCREAM][dB_PEAK:+10.0dB]",
        "[WPM_SPIKE: 257wpm]",
        "[WPM_SPIKE: 236wpm]"
      ]
    }
  ],
  "assembled_spoken_script": "Hey, buddy. Thanks for hanging out and telling scary stories. I'm not the biggest fan of getting spooked, but I'm lucky I've got a friend like you to keep my courage up. Oh, a grumpy baby mare! That's cute. Well, you got merch? That's cool. Thanks. Okay, Filbo, a little obsessive. Thanks for calming the crowd, buddy. The others might fight a lot, but I know that we'll all come together when things get tough. Whatever monsters out there, it's no match for our teamwork. Hey, you got good Philbo boys.",
  "pre_hook_context_text": "You may have this plant that I found, Floofty, a red tea plant.",
  "post_payoff_context_text": "Hey, Bessie. I've been itching to take another look at your Bugapedia. Have you",
  "signal_justification": {
    "chat_burst": "Z=2.57 sigma chat laughing spike",
    "db_spike": "+10.0dB vocal peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": true
  },
  "cause_and_effect_setup": "Streamer interacts with NPC dialogue while processing the eerie mood of the island.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 0,
    "shared_tokens": [],
    "reason": "contiguous_single_segment"
  },
  "climax_quote": "no match for our teamwork",
  "memes": []
}
```

</details>

### Champion Run: Iteration #21 (`VOD2_Tycoon_Full`) â€” **100.0/100**

#### Clip #1: Nonchalant Hat Glitch 🤯

- **Title:** Nonchalant Hat Glitch 🤯
- **Top Hook Caption:** `ACTING NONCHALANT FOR HATS`
- **Archetype:** `COMEDIC_STORYTELLING_OR_SARCASM`
- **Total Duration:** `44.38s` (`segment_count=3`)
- **Virality Score:** `9.5`
- **Pre-Hook 5s Context:** "Keep going, dude. Alright, from that, wait."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[PREMISE 6143.80s - 6156.44s]` (102:23.80â€“102:36.44) `[SPEECH_CADENCE]`: "One of our fans said maybe you should act nonchalant, like you don't even want a hat. Oh, oh, yes, that's nonchalant. Bro, who needs a, like, a Sherry whipped cream hat for their droid?"
  - `[ESCALATION 6166.10s - 6179.50s]` (102:46.10â€“102:59.50) `[DRAMATIC_PAUSE: 3.3s]`: "Guys, who needs a hat? Totally not sitting around looking for a hat right now. I don't even need the hat, y'all."
  - `[PUNCHLINE 6325.62s - 6343.96s]` (105:25.62â€“105:43.96) `[WPM_SPIKE: 317wpm] [WPM_SPIKE: 367wpm] [WPM_SPIKE: 245wpm] [SCREAM][dB_PEAK:+11.7dB] [WPM_SPIKE: 225wpm] [DRAMATIC_PAUSE: 3.8s]`: "Let me see the cool hat. Let me see the cool hat. Yeah, we did it. Bro, that's such a cool hat. It's because all of our fans were saying hats are so boring. Thanks for being so nonchalant, KF. It worked, guys. It worked. It worked. It was nonchalant. KF, nonchalantism works. I'm just kidding. Let's go."
- **Post-Payoff 5s Context:** "Let's go."
- **Why This Clip Is Viral:** The streamer follows chat's bizarre advice to act completely nonchalant about getting a rare hat, and miraculously it drops.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 1,
  "title": "Nonchalant Hat Glitch 🤯",
  "final_top_hook_caption": "ACTING NONCHALANT FOR HATS",
  "narrative_archetype": "COMEDIC_STORYTELLING_OR_SARCASM",
  "virality_score": 9.5,
  "total_duration_sec": 44.38,
  "segment_count": 3,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "PREMISE",
      "start": 6143.8,
      "end": 6156.44,
      "start_tc": "102:23.80",
      "end_tc": "102:36.44",
      "duration": 12.64,
      "spoken_text": "One of our fans said maybe you should act nonchalant, like you don't even want a hat. Oh, oh, yes, that's nonchalant. Bro, who needs a, like, a Sherry whipped cream hat for their droid?",
      "signal_tags_in_window": []
    },
    {
      "segment_order": 1,
      "role": "ESCALATION",
      "start": 6166.1,
      "end": 6179.5,
      "start_tc": "102:46.10",
      "end_tc": "102:59.50",
      "duration": 13.4,
      "spoken_text": "Guys, who needs a hat? Totally not sitting around looking for a hat right now. I don't even need the hat, y'all.",
      "signal_tags_in_window": [
        "[DRAMATIC_PAUSE: 3.3s]"
      ]
    },
    {
      "segment_order": 2,
      "role": "PUNCHLINE",
      "start": 6325.62,
      "end": 6343.96,
      "start_tc": "105:25.62",
      "end_tc": "105:43.96",
      "duration": 18.34,
      "spoken_text": "Let me see the cool hat. Let me see the cool hat. Yeah, we did it. Bro, that's such a cool hat. It's because all of our fans were saying hats are so boring. Thanks for being so nonchalant, KF. It worked, guys. It worked. It worked. It was nonchalant. KF, nonchalantism works. I'm just kidding. Let's go.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 317wpm]",
        "[WPM_SPIKE: 367wpm]",
        "[WPM_SPIKE: 245wpm]",
        "[SCREAM][dB_PEAK:+11.7dB]",
        "[WPM_SPIKE: 225wpm]",
        "[DRAMATIC_PAUSE: 3.8s]"
      ]
    }
  ],
  "assembled_spoken_script": "One of our fans said maybe you should act nonchalant, like you don't even want a hat. Oh, oh, yes, that's nonchalant. Bro, who needs a, like, a Sherry whipped cream hat for their droid? Guys, who needs a hat? Totally not sitting around looking for a hat right now. I don't even need the hat, y'all. Let me see the cool hat. Let me see the cool hat. Yeah, we did it. Bro, that's such a cool hat. It's because all of our fans were saying hats are so boring. Thanks for being so nonchalant, KF. It worked, guys. It worked. It worked. It was nonchalant. KF, nonchalantism works. I'm just kidding. Let's go.",
  "pre_hook_context_text": "Keep going, dude. Alright, from that, wait.",
  "post_payoff_context_text": "Let's go.",
  "signal_justification": {
    "chat_burst": "Z=3.2 sigma chat burst",
    "db_spike": "+11.7dB scream at peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": true
  },
  "cause_and_effect_setup": "The streamer follows chat's bizarre advice to act completely nonchalant about getting a rare hat, and miraculously it drops.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 146.1,
    "shared_tokens": [
      "fans",
      "nonchalant"
    ],
    "reason": "shared_entity_tokens"
  },
  "climax_quote": "nonchalantism works I'm just",
  "memes": []
}
```

</details>

#### Clip #2: Coolest Room Ever 😭

- **Title:** Coolest Room Ever 😭
- **Top Hook Caption:** `MY COLDEST ROOM YET`
- **Archetype:** `VIEWER_OR_CHAT_ROAST_INTERACTION`
- **Total Duration:** `22.57s` (`segment_count=2`)
- **Virality Score:** `9.2`
- **Pre-Hook 5s Context:** ""
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[PROMPT_SETUP 2461.70s - 2466.41s]` (41:01.70â€“41:06.41) `[dB_PEAK:+8.8dB] [VIEWER_OR_GAME_VOICE] [DRAMATIC_PAUSE: 2.1s]`: "A morning stream where I show you my coolest room ever."
  - `[REACTION_PAYOFF 2475.34s - 2493.20s]` (41:15.34â€“41:33.20) `[WPM_SPIKE: 326wpm] [SCREAM][dB_PEAK:+14.6dB] [WPM_SPIKE: 306wpm] [VIEWER_OR_GAME_VOICE] [WPM_SPIKE: 367wpm] [DRAMATIC_PAUSE: 2.1s] [SCREAM][dB_PEAK:+11.3dB] [WPM_SPIKE: 223wpm] [DRAMATIC_PAUSE: 4.2s] [SCREAM][dB_PEAK:+10.1dB]`: "Yeah, funny. Oh, yeah, you got to rebirth a lot. I don't hear them yet. Bro, I rebirth once. Oh, wait, I got blue. Nice. Oh, cool. The more you rebirth, the more things you get. I want a purple base."
- **Post-Payoff 5s Context:** "Alright, so the Mythic Companion we got. Is it in here?"
- **Why This Clip Is Viral:** The streamer flexes their custom room during an early morning stream before realizing how many rebirths they actually need.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 2,
  "title": "Coolest Room Ever 😭",
  "final_top_hook_caption": "MY COLDEST ROOM YET",
  "narrative_archetype": "VIEWER_OR_CHAT_ROAST_INTERACTION",
  "virality_score": 9.2,
  "total_duration_sec": 22.57,
  "segment_count": 2,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "PROMPT_SETUP",
      "start": 2461.7,
      "end": 2466.41,
      "start_tc": "41:01.70",
      "end_tc": "41:06.41",
      "duration": 4.71,
      "spoken_text": "A morning stream where I show you my coolest room ever.",
      "signal_tags_in_window": [
        "[dB_PEAK:+8.8dB]",
        "[VIEWER_OR_GAME_VOICE]",
        "[DRAMATIC_PAUSE: 2.1s]"
      ]
    },
    {
      "segment_order": 1,
      "role": "REACTION_PAYOFF",
      "start": 2475.335,
      "end": 2493.2,
      "start_tc": "41:15.34",
      "end_tc": "41:33.20",
      "duration": 17.865,
      "spoken_text": "Yeah, funny. Oh, yeah, you got to rebirth a lot. I don't hear them yet. Bro, I rebirth once. Oh, wait, I got blue. Nice. Oh, cool. The more you rebirth, the more things you get. I want a purple base.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 326wpm]",
        "[SCREAM][dB_PEAK:+14.6dB]",
        "[WPM_SPIKE: 306wpm]",
        "[VIEWER_OR_GAME_VOICE]",
        "[WPM_SPIKE: 367wpm]",
        "[DRAMATIC_PAUSE: 2.1s]",
        "[SCREAM][dB_PEAK:+11.3dB]",
        "[WPM_SPIKE: 223wpm]",
        "[DRAMATIC_PAUSE: 4.2s]",
        "[SCREAM][dB_PEAK:+10.1dB]"
      ]
    }
  ],
  "assembled_spoken_script": "A morning stream where I show you my coolest room ever. Yeah, funny. Oh, yeah, you got to rebirth a lot. I don't hear them yet. Bro, I rebirth once. Oh, wait, I got blue. Nice. Oh, cool. The more you rebirth, the more things you get. I want a purple base.",
  "pre_hook_context_text": "",
  "post_payoff_context_text": "Alright, so the Mythic Companion we got. Is it in here?",
  "signal_justification": {
    "chat_burst": "Chat emotion spike",
    "db_spike": "+14.6dB vocal peak at 41:17.7",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": true
  },
  "cause_and_effect_setup": "The streamer flexes their custom room during an early morning stream before realizing how many rebirths they actually need.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 9,
    "shared_tokens": [],
    "reason": "short_internal_gap_<=25s"
  },
  "climax_quote": "I want a purple base",
  "memes": []
}
```

</details>

#### Clip #3: Secret Rainbow Cartel 😱

- **Title:** Secret Rainbow Cartel 😱
- **Top Hook Caption:** `SECRET RAINBOW DROIDS`
- **Archetype:** `COMEDIC_STORYTELLING_OR_SARCASM`
- **Total Duration:** `22.81s` (`segment_count=2`)
- **Virality Score:** `8.9`
- **Pre-Hook 5s Context:** "duh, duh, duh, duh, duh. Oh, whoa."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[PREMISE 472.84s - 476.00s]` (07:52.84â€“07:56.00) `[SCREAM][dB_PEAK:+10.7dB]`: "It already says Draco crafted a rainbow droid."
  - `[PUNCHLINE 482.31s - 501.95s]` (08:02.31â€“08:21.95) `[dB_PEAK:+6.6dB] [WPM_SPIKE: 260wpm] [dB_PEAK:+6.2dB] [WPM_SPIKE: 400wpm] [dB_PEAK:+6.1dB] [WPM_SPIKE: 558wpm] [WPM_SPIKE: 405wpm] [WPM_SPIKE: 308wpm] [DRAMATIC_PAUSE: 2.3s]`: "What the? I thought I was the only one playing this for hours. I didn't know there was someone. Oh, my gosh. Don't spoil it yet. Don't spoil it yet. Okay, wait, wait, wait. Give me a second. I need to start mine first. All right. No, you won't. Let's go. Entry Workshop makes no credits. Build a scrap station. What does a scrap station receive? Oh, nice."
- **Post-Payoff 5s Context:** "Smash scrap, collect credit. That's right, help me. Ow,"
- **Why This Clip Is Viral:** The streamer boasts about grinding droids only to find out a rival player already crafted a rainbow droid.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 3,
  "title": "Secret Rainbow Cartel 😱",
  "final_top_hook_caption": "SECRET RAINBOW DROIDS",
  "narrative_archetype": "COMEDIC_STORYTELLING_OR_SARCASM",
  "virality_score": 8.9,
  "total_duration_sec": 22.81,
  "segment_count": 2,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "PREMISE",
      "start": 472.84,
      "end": 476.005,
      "start_tc": "07:52.84",
      "end_tc": "07:56.00",
      "duration": 3.165,
      "spoken_text": "It already says Draco crafted a rainbow droid.",
      "signal_tags_in_window": [
        "[SCREAM][dB_PEAK:+10.7dB]"
      ]
    },
    {
      "segment_order": 1,
      "role": "PUNCHLINE",
      "start": 482.31,
      "end": 501.95,
      "start_tc": "08:02.31",
      "end_tc": "08:21.95",
      "duration": 19.64,
      "spoken_text": "What the? I thought I was the only one playing this for hours. I didn't know there was someone. Oh, my gosh. Don't spoil it yet. Don't spoil it yet. Okay, wait, wait, wait. Give me a second. I need to start mine first. All right. No, you won't. Let's go. Entry Workshop makes no credits. Build a scrap station. What does a scrap station receive? Oh, nice.",
      "signal_tags_in_window": [
        "[dB_PEAK:+6.6dB]",
        "[WPM_SPIKE: 260wpm]",
        "[dB_PEAK:+6.2dB]",
        "[WPM_SPIKE: 400wpm]",
        "[dB_PEAK:+6.1dB]",
        "[WPM_SPIKE: 558wpm]",
        "[WPM_SPIKE: 405wpm]",
        "[WPM_SPIKE: 308wpm]",
        "[DRAMATIC_PAUSE: 2.3s]"
      ]
    }
  ],
  "assembled_spoken_script": "It already says Draco crafted a rainbow droid. What the? I thought I was the only one playing this for hours. I didn't know there was someone. Oh, my gosh. Don't spoil it yet. Don't spoil it yet. Okay, wait, wait, wait. Give me a second. I need to start mine first. All right. No, you won't. Let's go. Entry Workshop makes no credits. Build a scrap station. What does a scrap station receive? Oh, nice.",
  "pre_hook_context_text": "duh, duh, duh, duh, duh. Oh, whoa.",
  "post_payoff_context_text": "Smash scrap, collect credit. That's right, help me. Ow,",
  "signal_justification": {
    "chat_burst": "High WPM 400",
    "db_spike": "+10.7dB vocal peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": false
  },
  "cause_and_effect_setup": "The streamer boasts about grinding droids only to find out a rival player already crafted a rainbow droid.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 6.6,
    "shared_tokens": [],
    "reason": "short_internal_gap_<=25s"
  },
  "climax_quote": "I thought I was",
  "memes": []
}
```

</details>

#### Clip #4: Pickaxe Disconnect 💀

- **Title:** Pickaxe Disconnect 💀
- **Top Hook Caption:** `FORGOT MY PICKAXE`
- **Archetype:** `HUBRIS_WAGER_INSTANT_KARMA`
- **Total Duration:** `27.18s` (`segment_count=1`)
- **Virality Score:** `8.7`
- **Pre-Hook 5s Context:** "Okay, let's see, let's see, let's see. Okay, got a minute."
- **Full Stitched Verbatim Script & Signal Tags:**
  - `[CONTINUOUS_ARC 1499.42s - 1526.60s]` (24:59.42â€“25:26.60) `[WPM_SPIKE: 248wpm] [dB_PEAK:+8.4dB] [WPM_SPIKE: 259wpm] [DRAMATIC_PAUSE: 1.3s] [WPM_SPIKE: 302wpm] [dB_PEAK:+8.5dB] [DRAMATIC_PAUSE: 3.6s] [VIEWER_OR_GAME_VOICE] [DRAMATIC_PAUSE: 1.8s] [dB_PEAK:+6.6dB] [WPM_SPIKE: 324wpm]`: "Oh, look at her, she's going fast. Oh, guys, I literally forgot to offer my pickaxe. It literally dropped me out. Beautiful. You have to offer it so she can't work for that. Alright, hello. Donate. And where's the pickaxe? Alright, yeah. I need 61 straps though. Okay."
- **Post-Payoff 5s Context:** "Yeah, I'll go back. Yeah, I'll go back."
- **Why This Clip Is Viral:** The streamer races ahead with base upgrades only to get dropped instantly by a game error.

<details><summary>Full Raw EDL JSON Payload</summary>

```json
{
  "clip_number": 4,
  "title": "Pickaxe Disconnect 💀",
  "final_top_hook_caption": "FORGOT MY PICKAXE",
  "narrative_archetype": "HUBRIS_WAGER_INSTANT_KARMA",
  "virality_score": 8.7,
  "total_duration_sec": 27.18,
  "segment_count": 1,
  "edl_segments": [
    {
      "segment_order": 0,
      "role": "CONTINUOUS_ARC",
      "start": 1499.425,
      "end": 1526.6,
      "start_tc": "24:59.42",
      "end_tc": "25:26.60",
      "duration": 27.175,
      "spoken_text": "Oh, look at her, she's going fast. Oh, guys, I literally forgot to offer my pickaxe. It literally dropped me out. Beautiful. You have to offer it so she can't work for that. Alright, hello. Donate. And where's the pickaxe? Alright, yeah. I need 61 straps though. Okay.",
      "signal_tags_in_window": [
        "[WPM_SPIKE: 248wpm]",
        "[dB_PEAK:+8.4dB]",
        "[WPM_SPIKE: 259wpm]",
        "[DRAMATIC_PAUSE: 1.3s]",
        "[WPM_SPIKE: 302wpm]",
        "[dB_PEAK:+8.5dB]",
        "[DRAMATIC_PAUSE: 3.6s]",
        "[VIEWER_OR_GAME_VOICE]",
        "[DRAMATIC_PAUSE: 1.8s]",
        "[dB_PEAK:+6.6dB]",
        "[WPM_SPIKE: 324wpm]"
      ]
    }
  ],
  "assembled_spoken_script": "Oh, look at her, she's going fast. Oh, guys, I literally forgot to offer my pickaxe. It literally dropped me out. Beautiful. You have to offer it so she can't work for that. Alright, hello. Donate. And where's the pickaxe? Alright, yeah. I need 61 straps though. Okay.",
  "pre_hook_context_text": "Okay, let's see, let's see, let's see. Okay, got a minute.",
  "post_payoff_context_text": "Yeah, I'll go back. Yeah, I'll go back.",
  "signal_justification": {
    "chat_burst": "WPM 302 spike",
    "db_spike": "+8.5dB vocal peak",
    "face_emotion": "FACE:SHOCK_OR_SCREAM",
    "viewer_voice_present": true
  },
  "cause_and_effect_setup": "The streamer races ahead with base upgrades only to get dropped instantly by a game error.",
  "entity_continuity_check": {
    "passed": true,
    "max_gap_sec": 0,
    "shared_tokens": [],
    "reason": "contiguous_single_segment"
  },
  "climax_quote": "literally dropped me out",
  "memes": []
}
```

</details>

## 4. Remaining Edge Cases & Honest Self-Critique

1. **Free-Tier LLM Latency & Truncation Variance:** `models/gemini-3.5-flash-lite` (`loop3`) occasionally returns `<3` clips, under-sized stubs (`5sâ€“19s`), or raw JSON arrays without `{clips:[...]}`. Our `IF: Director JSON Valid?` quality gate (`>=3` distinct archetypes, `>=15s` solid duration) and `5. Split Clips` multi-run clip salvage (`allClips < 3` recovery + deterministic multimodal anchor fallback) absorb these failures cleanly, while `gemini-2.5-flash` Backup / Mistral Tier-3 Cloud can still experience upstream 429 rate limits under rapid bursts.
2. **Groq Whisper Non-Monotonic Word Overlapping:** Whisper occasionally assigns a word like `Can` (`6814.01s`) a start time earlier than the preceding sentence-ending word `town.` (`6814.37sâ€“6814.99s`). Our Monotonic Midpoint Sentence Opener Guard forces `seg.start` strictly above the preceding overlapping midpoint window so trailing period fragments cannot leak into hooks.
3. **Whisper Punctuation Gaps on Calm Sarcastic Bits:** On dry comedic monologues lacking `.!?` punctuation near target cut points (`VOD2_Tycoon_Full` Iteration 20 Clip 2), pause-based snapping can stop on a dangling preposition (`to`). Our two-pass `.!?`-first terminal snapping in `6. Extract Viral Segments` (Iteration 21) now refuses dangling tails and prioritizes `.!?` within `+-4.2s`.
4. **Zero-Chat / Missing Webcam Telemetry Graceful Degradation:** Offline VODs lacking live chat logs or webcam face crops (`VOD2` has no chat clusters and only audio + cadence signals) lose empirical chat-lag confirmation (`[CHAT_LAG]` / `[FACE:*]`) unless `telemetry_fusion_indexer.py` receives full Twitch chat JSON and video webcam crops.