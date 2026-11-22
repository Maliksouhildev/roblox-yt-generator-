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




