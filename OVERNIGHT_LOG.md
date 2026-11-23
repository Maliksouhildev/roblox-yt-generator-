# Autonomous Viral Discovery & Copywriting Optimization Log

## Iteration 0 — Strict Baseline (Before Fixes)
- **Command:** `python3 /files/eval_viral_discovery.py --temp-dir /files/temp --inputs-dir /files/inputs`
- **Datasets:** `B_vod1_50min_chunk` (`bak_vod1_transcript.json`), `C_vod2_50min_chunk` (`whisper_28754.json`), `C2_gaming_vod_chunk` (`whisper_28888.json`), `D_adversarial_prod_replay`
- **Baseline Metrics:**
  - `total_valid_clips`: `38` (`valid_clips_per_chunk_min`: `0` on `D`, `5` on `C2`, `10` on `B`/`C`)
  - `raw_transcript_title_rate_pct`: `0.0%` (note: fallback templates bypassed raw opener check by emitting `"Live Gameplay Reaction Peak Around T"`)
  - `hallucination_or_robotic_copy_rate_pct`: **`300.0%`** (failures on title, desc, AND truncated hook across clips)
  - `passive_silent_opening_rate_pct`: **`5.26%`** (dead 0–3s opening clips emitted)
  - `duration_sweet_spot_rate_pct`: `100.0%`
  - `duplicate_title_count`: **`33`** (every fallback clip in a chunk collided on `"Live Gameplay Reaction Peak Around T"`)
  - `telemetry_bug_count`: **`67`** (`66` `false_silence_1.0` from `speaker_tag == "STREAMER"` mismatch + `1` Rumble/superchat shoutout leak)
  - `loop_crash_count`: `0`
  - `tfi_fuses_heatmap`: **`false`**
  - `scraper_lightweight_info_json`: **`false`**
- **Top 3 Root Failure Causes Observed:**
  1. `scripts/gta6_peak_storyboard_builder.py` L696 compared `s.get("speaker_tag") == "STREAMER"` instead of `"[STREAMER]"`, making `streamer_silence_ratio = 1.0` for every candidate.
  2. `scripts/gta6_vision_director.py` `deterministic_candidate_fallback` / `_synthesize_clean_metadata` produced `"Live gameplay reaction peak around t=XXXs in Vice City."`, causing identical `"Live Gameplay Reaction Peak Around T"` titles across every clip; AND `5. Split Clips` `fit28` chopped clean hooks (`"He really didn't"`, `"GTA 6 cops have zero"`, `"Bro got humbled in two"`).
  3. `scripts/telemetry_fusion_indexer.py` lacked `[HEATMAP_PEAK]` + facial mouth/head motion delta fusion and Rumble/superchat shoutout filtering; `scripts/live_stream_chunk_scraper.py` saved full 650 KB+ `.info.json` files without compacting bulky format tables.

---

## Iteration 1 — Crowd-Signal + Vocal/Motion Contrast + Lightweight `.info.json`
- **Changes Applied:**
  - `scripts/live_stream_chunk_scraper.py`: Added `_compact_info_doc()` and stamped `chunk_start_sec`/`chunk_end_sec` + preserved `heatmap`/`chapters` cleanly across all chunk paths (including Twitch live).
  - `scripts/telemetry_fusion_indexer.py`: Added `load_heatmap_peaks()`, webcam `mouth_motion` + `head_vel` delta z-score fusion, silent cutscene penalty (`sp_cov < 0.25`), and expanded `HOUSEKEEPING_NOISE` for gifted Rumble premiums / superchats / Champions Club shoutouts.
  - `scripts/multimodal_analyzer.py`: Added `mouth_motion` boost into face intensity and dead-air penalty on low-RMS silent seconds lacking face/crowd delta.
- **Metrics After Iteration 1:**
  - `total_valid_clips`: `42` (`38` -> `42`), `valid_clips_per_chunk_min`: `4` (`0` -> `4`)
  - `tfi_fuses_heatmap`: `false` -> **`true`**
  - `scraper_lightweight_info_json`: `false` -> **`true`**
  - `hallucination_or_robotic_copy_rate_pct`: `300.0%` -> `278.57%`
  - `passive_silent_opening_rate_pct`: `7.14%` (now also exercising `D_adversarial_prod_replay`!)
  - `duplicate_title_count`: `33` (still failing — addressed in Iteration 3)
  - `telemetry_bug_count`: `67` (still failing — addressed in Iteration 2)
  - `tests`: `53/53` unit tests passed.
- **Worst Remaining Issues:**
  1. `false_silence_1.0` (`66` candidates) + `adv_shoutout_leak` in `gta6_peak_storyboard_builder.py`.
  2. Dead `0–3s` opening on `A_active_chunk` and `D_adversarial_prod_replay` (`words=1, z_db=0.00, z_face=0.00`).
  3. Fallback title collision (`"Live Gameplay Reaction Peak Around T"`) & `5. Split Clips` `fit28` truncating hooks (`"The ultimate highway police"`, `"SWAT dropped through"`).

---

## Iteration 2 — Fix `streamer_silence_ratio`, Shoutout Suppression, & Storyboard 0–3s Hook Check
- **Changes Applied:**
  - `scripts/gta6_peak_storyboard_builder.py`: Fixed `s.get("speaker_tag") in ("[STREAMER]", "STREAMER")` (previously checked `"STREAMER"` without brackets, leaving silence ratio at `1.0` for every candidate); expanded `HOUSEKEEPING_RE` for gifted Rumble premiums / superchats / Champions Club shoutouts; tightened `[WPM_SPIKE:SHOCK_EXCLAIM]` to require `>= 2` shock tokens or vocal/WPM boost; added `0–3s Hook Energy Check` shifting `w_start` past leading dead air when `< 2` words and no vocal/face spike.
- **Metrics After Iteration 2:**
  - `total_valid_clips`: `48` (`42` -> `48`, `A` jumped from `7` -> `10`)
  - `telemetry_bug_count`: `67` -> **`0`** (100% resolved!)
  - `passive_silent_opening_rate_pct`: `7.14%` -> **`2.08%`** (0 silent openings across all 5 real VOD chunks `A`, `A2`, `B`, `C`, `C2`; only `D` left before `gta6_vision_director.py` trim)
  - `hallucination_or_robotic_copy_rate_pct`: `281.25%` (`duplicate_title_count: 39`)
  - `tests`: `53/53` unit tests passed.
- **Worst Remaining Issues:**
  1. `Live gameplay reaction peak around t=XXXs` in `deterministic_candidate_fallback` / `_synthesize_clean_metadata` producing identical `"Live Gameplay Reaction Peak Around T"` titles across all clips.
  2. Robotic descriptions (`"Doc explains..."`, `"Doc breaks down..."`) in `D_adversarial_prod_replay` + `fit28` truncating hooks in `5. Split Clips`.
  3. Isolated leading word `"hmm"` + `5.5s` dead gap at `t=20s` in `D_adversarial_prod_replay` not trimmed by `_trim_leading_dead_air` (due to outdated `>= 34.0s` guard).

---

## Iteration 3 — Unique Topic-Driven Copy, `fit38` Hook Preservation, & Robotic Filtering
- **Changes Applied:**
  - `scripts/gta6_vision_director.py`: Expanded `ROBOTIC_COPY_RE` (catching `"Doc explains/breaks down/vents"`, `"Streamer reflects"`, `"Live gameplay reaction peak..."`); upgraded `_synthesize_clean_metadata` with `_TOPIC_HOOK_KEYWORDS`, `_extract_topic_phrase`, 6x3 varied archetype copy pools, and per-batch `used_titles` uniqueness tracking; updated `_trim_leading_dead_air` (`>= 14.0s` guard) and capped normalized duration at `38.0s`.
  - `workflows/gta6_vision_shorts_workflow.json`: Replaced `5. Split Clips` `fit28` hook chopper with `fit38` (Sentence case preserved, `<= 38` chars, `3–7` words), added `ROBOTIC_COPY_RE` & duplicate title dedup in `5. Split Clips` + `Write Sidecar JSON`, and added `0–3s` opening speech guard + `38.0s` cap in `6. Extract Viral Segments`.
- **Metrics After Iteration 3:**
  - `duplicate_title_count`: `39` -> **`0`**
  - `hallucination_or_robotic_copy_rate_pct`: `281.25%` -> **`2.38%`** (only 1 live Gemini hook `"Bro really just"` slipped past `DANGLING_END_RE`)
  - `raw_transcript_title_rate_pct`: **`0.0%`**
  - `telemetry_bug_count`: **`0`**
  - `tests`: `53/53` unit tests passed.
- **Worst Remaining Issues:**
  1. Live Gemini clip (`TypicalGamer_3QjXNSf6keg`) had `hook_caption: "Bro really just"` ending on dangling intensifier `"just"`, and `dur: 38.84s` (sentence-end snapper added `+0.84s` AFTER `totalClipDur > 38.0`).
  2. Live Gemini returned only `4` clips (`< 5` minimum target) out of `10` candidates on `A_active_chunk_cached_llm`.
  3. Dead `0–3s` opening in `D_adversarial_prod_replay` (`20.0..38.0` with `hmm` + `5.5s` gap) refused to shift because `en` was capped at `38.0` instead of extending into `hi_bound = 44.0`.
  4. `probe_short` mock in `eval_viral_discovery.py` hit real `/files/temp/concatenated_clip.mp4` via unmocked `execSync('ffprobe')`.

---

## Iteration 4 — Dangling Intensifier Guard, Post-Snap 38s Cap, 0–3s End Extension, & Lazy-LLM Top-Up (ALL EXIT CRITERIA PASSED)
- **Changes Applied:**
  - `scripts/gta6_vision_director.py`: Added dangling intensifiers/adverbs (`JUST|REALLY|VERY|TOO|...`) to `TRANSITIVE_OR_DANGLING_WORDS`, widened `_safe_hook_from_text` to `3–7` words / `<= 38` chars, upgraded `_trim_leading_dead_air(..., hi_bound=...)` so shifting past silent `0–3s` openings extends end within `hi_bound` to preserve `>= 14.0s`, and added non-overlapping candidate top-up in `normalize_director_clips()` when lazy-LLM output has `< min_clips`.
  - `workflows/gta6_vision_shorts_workflow.json`: Added dangling intensifiers to `5. Split Clips` `DANGLING_END_RE` and added post-snap `38.0s` cap on `enrichedSegs` inside `6. Extract Viral Segments`.
  - `tests/eval_viral_discovery.py`: Isolated `fs` + `child_process` mocks in `6. Extract Viral Segments` and `Create Subtitle Binary` probes from concurrent cron files on `/files/temp/`.
- **Final Verified Metrics (Iteration 4 across 6 datasets / 47 emitted Shorts):**
  - `datasets_tested`: `6`
  - `total_valid_clips`: **`47`** (`valid_clips_per_chunk_avg`: `7.83`, `valid_clips_per_chunk_min`: **`5`**)
  - `raw_transcript_title_rate_pct`: **`0.0%`** (target: `0%`)
  - `hallucination_or_robotic_copy_rate_pct`: **`0.0%`** (target: `0%`)
  - `passive_silent_opening_rate_pct`: **`0.0%`** (target: `0%`)
  - `duration_sweet_spot_rate_pct`: **`100.0%`** (14s–38s, target: `100%`)
  - `duplicate_title_count`: **`0`**
  - `telemetry_bug_count`: **`0`**
  - `loop_crash_count`: **`0`**
  - `tfi_fuses_heatmap`: **`true`**
  - `scraper_lightweight_info_json`: **`true`**
  - `heatmap_loader_ok`: **`true`**
  - **`exit_criteria_passed`: `true`**

---

# Pacing & Subtitle Sync Optimization Loop (`/files/dynamic_jumpcut_engine.py`)

## Sync/Pacing Iteration 0 — Strict Baseline (Untouched Live GTA 6 Renders)
- **Command:** `python3 /files/eval_pacing_and_sync.py`
- **Clips Evaluated:** `Vice City Skyline Fast Climb.mp4` (`33.1s`), `Dual Bike Ride Human Statue Encounter.mp4` (`26.8s`), `GTA 6 Cops Are Relentless.mp4` (`25.0s`), `Zero Escape From Vice PD.mp4` (`15.73s`)
- **Baseline Metrics:**
  - `max_dead_air_ratio_pct`: **`9.53%`** (`avg: 6.05%`) — target `< 6.0%`
  - `avg_cuts_per_30s`: **`0.0`** — target `2.0–7.0`
  - `median_subtitle_onset_error_ms`: **`87.5 ms`** (`Dual Bike: 125ms`, `Zero Escape: 120ms`) — target `<= 55.0 ms`
  - `early_words_gt150ms_total`: **`2`** (`"YOU'RE"` at `25.01s` vs `25.40s` onset = `390ms` early; `"I"` at `2.43s` vs `2.64s` onset = `210ms` early)
  - `max_av_sync_drift_ms`: `35.01 ms`
  - `zero_overlapping_ass_events`: `true`
  - `zero_emoji_tofu`: **`false`** (container has only monochrome `Noto Emoji | color=False`; emojis in `ViralSubs` fail libass rendering)

---

## Sync/Pacing Iteration 1 — Initial `/files/dynamic_jumpcut_engine.py` Build
- **Changes Applied:**
  - Created `scripts/dynamic_jumpcut_engine.py` combining 20ms `300–3400Hz` vocal-band RMS + `2 fps` FFmpeg motion analysis + Whisper word protection + `18ms` `afade` audio crossfades + CFR sample-locked concat rendering.
- **Metrics After Iteration 1:**
  - `max_av_sync_drift_ms`: `35.01ms` -> **`19.0ms`** (`0.0ms` on multi-cut `GTA 6 Cops Are Relentless`)
  - `avg_dead_air_ratio_pct`: `6.05%` -> **`4.93%`** (`Vice City Skyline` dropped `9.06%` -> `4.59%`, `GTA 6 Cops` dropped to `0.0%`)
  - `max_dead_air_ratio_pct`: **`9.53%`** (`Zero Escape`: `min_final_dur=12.0` blocked cuts; `Dual Bike`: single brief camera turn blocked cutting 4s calm silence via whole-span `max()`)
  - `avg_cuts_per_30s`: **`0.83`** (under-cut on `Dual Bike` & `Zero Escape` & `Vice City Skyline` due to ambient wind at `-40dB` + whole-span `max()` motion guard)
  - `median_subtitle_onset_error_ms`: `100.0 ms`, `early_words_gt150ms_total`: `2`, `zero_emoji_tofu`: `false` (workflow `7b` & `Create Subtitle Binary` not yet updated).

---

## Sync/Pacing Iteration 2 — Per-Bin Motion Protection + `7b` 300–3400Hz RMS + Emoji Tofu Fix
- **Changes Applied:**
  - `scripts/dynamic_jumpcut_engine.py`: Switched from whole-span `max()` motion protection to per-0.5s-bin protection (carving calm silent sub-spans inside multi-second pauses), raised ambient threshold `+3.5 dB` outside Whisper words, and enforced `14.1s` minimum post-cut floor (preventing `ABORT_CLIP_TOO_SHORT` on `Zero Escape`).
  - `workflows/gta6_vision_shorts_workflow.json`: Wired `dynamic_jumpcut_engine.py` into `7b. Extract Clip Audio` before `ffmpeg` audio/RMS extraction, upgraded `speech_rms.json` to `300–3400Hz` bandpass (`p25 + 6.5`), stripped `ViralSubs` emoji tofu in `Create Subtitle Binary`, and added 2-frame RMS check.
- **Metrics After Iteration 2:**
  - `avg_dead_air_ratio_pct`: `6.05%` -> **`2.38%`** (`0.0%` dead air on `Vice City Skyline`, `Dual Bike Ride`, `GTA 6 Cops`!)
  - `avg_cuts_per_30s`: `0.83` -> **`2.29`** (`Vice City Skyline`: `5` cuts / `4.53` per 30s; `Dual Bike`: `2` cuts; `GTA 6 Cops`: `2` cuts)
  - `max_av_sync_drift_ms`: `19.0ms` -> **`13.33ms`** (`<= 40ms`)
  - `zero_emoji_tofu`: `false` -> **`true`**
  - **Remaining Failures Found:**
    1. `Zero Escape From Vice PD.mp4` (`15.73s`): `min_final_dur = 14.1s` dropped the entire `3.1s` cut instead of trimming it down to `1.6s`, leaving `max_dead_air_ratio_pct: 9.53%`.
    2. `isPhraseStart` ran BEFORE `maxPlausibleDur` clamp in `Create Subtitle Binary`, skipping RMS gating on stretched words like `"GO."` (`200ms` early); AND `maxFrame` (`wEnd - 0.06`) stopped 1 frame short of vocal onset on `"I"` (`210ms` early), `"HOW"` (`270ms` early), and `"YOU'RE"` (`500ms` early), pushing `median_subtitle_onset_error_ms` to `87.5ms`.

---

## Sync/Pacing Iteration 3 — Shrink-to-Budget Cut Trimming + Post-Clamp `isPhraseStart` RMS Sync
- **Changes Applied:**
  - `scripts/dynamic_jumpcut_engine.py`: Instead of dropping the whole cut when `tot_kept < min_final_dur` (`14.1s`), shrinks only the excess from the largest `dead_pause` cut (`Zero Escape`: trimmed `5.01..6.64` so `15.73s -> 14.10s >= 14.0s` floor!).
  - `workflows/gta6_vision_shorts_workflow.json` (`Create Subtitle Binary`): Moved `isPhraseStart` computation AFTER `maxPlausibleDur` clamp (`<= 0.46s` opener), and widened RMS onset scan window to `min(wEnd + 0.14, nextWordStart - 0.03)` (keeping `<= 0.40s` shift cap) so tail-onset words snap accurately instead of staying stuck in leading silence.
- **Metrics After Iteration 3 (`task-3328`):**
  - `max_dead_air_ratio_pct`: **`10.64%`** (`0.0%` on `Vice City Skyline`, `Dual Bike`, `GTA 6 Cops`; `Zero Escape` `15.73s -> 14.10s` spent full `1.63s` budget on `[7.55..9.18]`, leaving `[5.0..6.5]` `1.50s` untouched!)
  - `avg_dead_air_ratio_pct`: `6.05%` -> **`2.66%`**
  - `avg_cuts_per_30s`: **`2.77`** (`choppy_shards_total: 0`)
  - `median_subtitle_onset_error_ms`: `87.5 ms` -> **`10.0 ms`** (`10ms`, `10ms`, `10ms`, `120ms`!)
  - `early_words_gt150ms_total`: `5` -> **`2`** (`"YOU'RE"` `430ms` early and `"HOW"` `260ms` early — `scanCeiling` stopped at `nextWordRawStart - 0.03` right before the `60ms`-later vocal peak!)
  - `max_av_sync_drift_ms`: **`13.33 ms`**
  - `zero_overlapping_ass_events`: **`true`**, `zero_emoji_tofu`: **`true`**
  - `exit_criteria_passed`: `false` (2 remaining gaps to fix in Iteration 4)

---

## Sync/Pacing Iteration 4 — Extended Tail-Onset RMS Scan Ceiling (`wEnd + 0.24s`)
- **Changes Applied:**
  - `workflows/gta6_vision_shorts_workflow.json` (`Create Subtitle Binary`): Set `scanCeiling = Math.min(clipDur, wEnd + 0.24)` so soft pre-vowel breaths (`"YOU'RE"` and `"HOW"`) snap cleanly onto the vocal RMS peak while monotonic sanitization shifts neighboring boundaries cleanly.
  - `scripts/dynamic_jumpcut_engine.py`: Added proportional cut-shrink budget allocation so short ~15s clips preserve multiple short cuts rather than dropping down to zero.
- **Metrics After Iteration 4 (`task-3347`):**
  - `early_words_gt150ms_total`: `2` -> **`0`** (100% resolved!)
  - `median_subtitle_onset_error_ms`: **`10.0 ms`** (`Vice City Skyline: 10ms`, `Dual Bike: 10ms`, `GTA 6 Cops: 10ms`)
  - `max_av_sync_drift_ms`: `13.33ms` -> **`10.0 ms`**
  - `avg_dead_air_ratio_pct`: **`2.55%`** (`0.0%` on `Vice City`, `Dual Bike`, `GTA 6 Cops`), `Zero Escape`: `10.2%` (`need` shrink bug using `rem` instead of `need` inside loop caused second cut to drop).

---

## Sync/Pacing Iteration 5 — Fixed Proportional Shrink Math (`need * ratio`) (ALL EXIT CRITERIA PASSED)
- **Changes Applied:**
  - `scripts/dynamic_jumpcut_engine.py`: Fixed proportional shrink calculation (`need * (avail / total_slack)` + exact `min(avail, rem)` on final item) so `Zero Escape` cleanly trims BOTH silent pockets `[5.03..5.758]` and `[7.62..8.525]` down to `14.10s >= 14.0s`.
- **Final Verified Metrics (`task-3369`, 4 real GTA 6 clips, 168 ASS events):**
  - `clips_evaluated`: **`4`** (`Vice City Skyline Fast Climb.mp4`, `Dual Bike Ride Human Statue Encounter.mp4`, `GTA 6 Cops Are Relentless.mp4`, `Zero Escape From Vice PD.mp4`)
  - `max_dead_air_ratio_pct`: **`0.0%`** (`avg_dead_air_ratio_pct: 0.0%`, target `< 6%`)
  - `avg_cuts_per_30s`: **`3.25`** (`4.53`, `2.24`, `2.40`, `3.81`; target `2–7`)
  - `choppy_shards_total`: **`0`**
  - `median_subtitle_onset_error_ms`: **`10.0 ms`** (target `<= 55ms`)
  - `early_words_gt150ms_total`: **`0`**
  - `max_av_sync_drift_ms`: **`10.0 ms`** (target `<= 40ms`)
  - `zero_overlapping_ass_events`: **`true`**
  - `zero_emoji_tofu`: **`true`**
  - **`exit_criteria_passed`: `true`**









