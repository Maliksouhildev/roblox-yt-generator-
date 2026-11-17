# AI YouTube Shorts Automation Engine — Complete A-to-Z System & Architecture Breakdown

This document explains every layer of the platform from ingestion and Docker orchestration down to mathematical multimodal telemetry fusion, 3x3 vision storyboards, FFmpeg 9:16 video mastering, forensic guardrails, and exact runtime versions.

---

## 1. Container Infrastructure, Runtimes & Services

| Service / Runtime | Container / Binary | Exact Version | Purpose & Ports |
|---|---|---|---|
| **Orchestration Engine** | `ai_clipper-n8n-1` (`n8n`) | `1.77.0` | Executes workflow DAGs via Web UI or headless CLI (`n8n execute --id=...`). Exposes `5678:5678`. |
| **Workflow & Credential DB** | `sqlite3` (`/root/.n8n/database.sqlite`) | `3.48.0` | Stores `workflow_entity`, `shared_workflow`, encrypted credentials (`loop3`, `gemini 2 `, `Mistral Cloud account`, `Groq account`). |
| **JS Execution Sandbox** | Node.js inside `ai_clipper-n8n-1` | `v20.18.2` | Runs all n8n `Code` nodes (`NODE_FUNCTION_ALLOW_BUILTIN=*`, `NODE_FUNCTION_ALLOW_EXTERNAL=*`). |
| **Telemetry & Vision Runtime** | Python 3 inside `ai_clipper-n8n-1` | `3.12.14` | Runs DSP, ONNX inference, chat Z-score modeling, storyboard rendering, Vision APIs, and EDL auditing. |
| **Computer Vision Stack** | `opencv-python` (`cv2`), `numpy` | `cv2 4.10.0`, `numpy 2.1.3` | Face detection, landmark extraction (MAR/EAR), emotion classification, frame MAE static checks, YCrCb skin-cluster checks. |
| **Media Engine** | `ffmpeg` / `ffprobe` | `6.1.2` | Dynamic audio extraction (`dynaudnorm`), lossless/frame-accurate `trims`, `xstack` 3x3 contact sheets, 9:16 vertical split-screen compositor, ASS subtitle burning, audio ducking/mixing. |
| **Animated Overlay Renderer** | `cursor-mikow-remotion` (`remotion`) | `remotion 4.0.252` (`@remotion/bundler`, `@remotion/renderer`) | Renders animated 3.5s hook badges via `http://remotion-server:3000/render-overlay` (host `3008`). |
| **Auxiliary Stack** | `ai_clipper-qdrant-1`, `cursor-mikow-kokoro` | `qdrant:latest` (`6333`), `kokoro-fastapi-cpu` (`8880`) | Vector store & local TTS microservices running in Compose stack. |
| **Stream Harvester** | `yt-dlp` (`/files/yt-dlp`) | Latest release binary | Downloads Twitch/YouTube VODs (`<= 1080p mp4`), `.info.json` metadata, and live chat replays (`--write-subs --sub-langs live_chat`). |

---

## 2. Three Workflow Topologies in n8n

All workflows coexist independently inside `/root/.n8n/database.sqlite` and `/files/workflows/`:

1. **`D2hITsyjP5dVsqBZ` — `YouTube Short Automation (Bypassed Version)`** (`workflows/workflow.json`, TS twin `workflows/workflow_bypassed.ts`)
   - Full Roblox/variety production pipeline: VOD acquisition -> facecam detection -> Whisper transcription -> Global Summary -> Multimodal Fusion -> Chunked Scout Loop (4 chunks) -> Director AI (6 archetypes) -> Clip Splitting & Segment Snapping -> Screen UI Audit -> Per-Clip Whisper (`7d`) -> Context Merge Agent -> Remotion Overlay + FFmpeg 9:16 Master Render + Sidecar JSON.
2. **`IsoEdlArchitectV1` — `Isolated Multimodal Script & EDL Architect`** (`workflows/isolated_edl_architect.json`, `75` nodes)
   - Headless script & EDL testbench with ZERO FFmpeg rendering. Reads cached `/files/temp/` telemetry (`Load Cached Telemetry` -> `Scout` -> `Director` -> `5. Split Clips` -> `6. Extract Viral Segments` -> `Prepare Merge Items` -> `Context Merge Agent` -> `Verify Hooks & Build EDL Preview`) and emits `/files/temp/n8n_sandbox_edl_preview.json` for mathematical grading by `/files/edl_auditor.py`.
3. **`Gta6VisionShortsV1` — `GTA 6 Viral Shorts Engine (Peak + 3x3 Vision Edition)`** (`workflows/gta6_vision_shorts_workflow.json`, `73` nodes)
   - Cloned and re-architected for visual-first gaming & GTA 6 launch streams:
     - **Eliminated completely:** Multi-chunk text `Scout Loop`, old text-only `Director`, and inside-loop `Context Merge Agent` (removing ~48 legacy LLM retry/wait nodes).
     - **Replaced with a 2-Stage Peak + Vision Pipeline:**
       - **Stage 2A (`gta6_peak_storyboard_builder.py`):** Bottom-up empirical 1-second multimodal virality curve $V(t)$ -> Top 8 non-overlapping peaks -> eight `960x540` `3x3` FFmpeg visual storyboard JPEGs (`/files/temp/gta6_cand_<k>_grid.jpg`).
       - **Stage 2B (`gta6_vision_director.py`):** Single-pass Multimodal Vision Director inspecting all 8 grids + speaker-tagged dialogue simultaneously, emitting complete clips (`hook_caption`, `climax_quote`, `reaction_triggers`, `memes`, `visual_value_note`, `comment_bait_question`, `is_story_spoiler`, `segments[]`) straight to `5. Split Clips`.
     - **Dedicated Isolated Branch (`GTA 6 Sandbox: Test Vision Script & EDL` -> `GTA 6 Load Cached Telemetry` -> `Run GTA6 Peak & Storyboard Builder` -> `Run GTA6 Vision Director` -> `5. Split Clips` -> `6. Extract Viral Segments` -> `Is Dry Run / Script Sandbox?` -> `DRY_RUN_SCRIPT_ONLY`):** Outputs `/files/temp/gta6_sandbox_edl_preview.json` for instant zero-render auditing.

---

## 3. AI Models, Fallback Waterfalls & Computer Vision Weights

### Cloud AI Models
| Pipeline Role | Primary Model | Fallback Tier 2 | Fallback Tier 3 / Offline |
|---|---|---|---|
| **ASR / Word-Level Alignment** | Groq `whisper-large-v3-turbo` (`verbose_json`, word timestamps) | Backup Groq Credential Pool (`Groq account 2/3/4`) | Pre-cached `/files/temp/transcript.json` |
| **Global VOD Summary** | Google Gemini `models/gemini-3.5-flash-lite` (`loop3`) | `models/gemini-2.5-flash` (`gemini 2 `) | Mistral `mistral-small-latest` |
| **Prod / Isolated Scout & Director** | Google Gemini `models/gemini-3.5-flash-lite` (`BLOCK_NONE`) | `models/gemini-2.5-flash` (`BLOCK_NONE`) | Mistral `mistral-large-latest` |
| **GTA 6 Vision Director (`gta6_vision_director.py`)** | `gemini-2.5-flash` (8 `3x3` JPEGs via `inline_data`) | `gemini-3.5-flash-lite` (Vision multi-key pool) | Deterministic peak-aligned EDL generator |
| **Facecam Bounding Box Vision (`cam_detector.py`)** | `gemini-3.5-flash` / `gemini-2.5-flash` | OpenCV YuNet + Spatial Motion Clustering (local, zero API cost) | Static avatar / full-screen game fallback |
| **Screen Obstruction & NSFW Audit (`screen_ui_audit.py`)** | `gemini-2.5-flash` -> `gemini-3.5-flash` | Offline OpenCV YCrCb skin-cluster & frozen-frame MAE check | Fails open only on transient API outage |

### Local ONNX Neural Networks (`/files/`)
1. **`face_detection_yunet.onnx`** (`cv2.FaceDetectorYN`): Detects faces inside cropped webcam ROIs and outputs 5-point facial landmarks (left/right eye, nose tip, left/right mouth corners) used to compute Mouth Aspect Ratio (MAR), eye-to-mouth vertical openness, and inter-frame head velocity.
2. **`emotion-ferplus-8.onnx`** (`cv2.dnn` `64x64` grayscale FER+): Scores 8 facial expression probabilities (`neutral`, `happiness`, `surprise`, `sadness`, `anger`, `disgust`, `fear`, `contempt`), labeling spikes (`FACE:SHOCK_OR_SCREAM`, `FACE:LAUGH`, `FACE:RAGE`, `FACE:DEADPAN_STARE`).

---

## 4. End-to-End Execution Logic (Step-by-Step A to Z)

### Phase A: Acquisition & Creator Attribution
1. **`Find Stream` -> `If Stream Exists` -> `Fallback Download` -> `Pick Random Streamer`:**
   - Scans `/files/inputs/*.mp4` for unprocessed VODs; renames active file to `*.processing.mp4` and purges mismatched `/files/temp/*.json` caches.
   - If empty, picks from 15 launch channels (`TypicalGamer`, `IShowSpeed`, `CaseOh_`, `penguinz0`, `xQc`, `KaiCenat`, `lirik`, `summit1g`, `DarkViperAU`, `LazarBeam`, `Valkyrae`, `TimTheTatman`, `DrDisRespect`, `Tarik`, `jynxzi`) and invokes `yt-dlp` (`duration <= 36000` for up to 10-hour marathons, `--write-info-json --write-subs --sub-langs live_chat`).
2. **`Resolve Creator Handle`:**
   - Inspects `/files/inputs/<stem>.info.json` (`uploader_id`, `channel`, `uploader`), falling back to filename regex / `Config.streamer_name`, emitting `streamer_handle` and `creator_credit: "🎥 @<handle>"`.

### Phase B: Audio Normalization & Facecam Geometry
1. **`Get Reference Frame` -> `Cam Vision Prep / Call` -> `Parse Cam Config`:**
   - Extracts 5 staggered frames (`ref_1..5.jpg`). `cam_detector.py` combines Gemini Vision + local YuNet temporal variance (`med_diff`, `unchanged_ratio`) to pinpoint corner facecam coordinates (`cam_x, cam_y, cam_w, cam_h`), automatically rejecting static VTuber/PNG avatars (`avatar_row_detected`, e.g., IBella PNGs) so gameplay stays full-screen instead of cropping a static image!
2. **`1. Extract Audio` -> `3. Groq Whisper` -> `Save Whisper Transcript`:**
   - Runs FFmpeg `-af "highpass=f=80,dynaudnorm=f=150:g=13:p=0.92:m=5.0" -acodec libmp3lame -b:a 32k -ac 1 -ar 16000 /files/temp/audio.mp3` so both close-mic streamer speech and quiet in-game NPCs / proximity voice chat remain clear for `whisper-large-v3-turbo` word timestamps.

### Phase C: Multimodal Telemetry Fusion (`multimodal_analyzer.py` + `telemetry_fusion_indexer.py`)
Runs locally in parallel (`ThreadPoolExecutor`) with zero LLM cost:
1. **Per-Stream Audio DSP:** Computes `8 kHz` `0.5s` RMS bins, true per-stream mean/MAD-std $Z_{\text{dB}} = (\text{dB} - \mu_{\text{stream}}) / \sigma_{\text{stream}}$, FFT spectral centroid, and `50ms` sub-frame pitch/energy variance to filter desk thumps and tag genuine screams (`[SCREAM:Z=...|+XX.XdB]` strictly when $Z_{\text{dB}} \ge 2.8$).
2. **Latency-Compensated Chat Velocity (`chat_analyzer.py`, `chat_humor_reasoner.py`):** Bins Twitch/YouTube live chat, computes rolling Z-scores ($\ge 2.5\sigma$), laughter density, GTA 6 hype tokens (`LMAO`, `💀`, `WTF`, `AYO`, `WASTED`, `GOTY`, `NPC`), and `[CHAT_QUESTION_CLUSTER]` detection (`"how do you..."`, `"where is..."`), shifting chat peaks backward by $\Delta_{\text{lag}} = 5.5\text{s}$ (`[t+3s, t+8s]`) to match the stream cause frame at $t$.
3. **Diarization-Lite (`[STREAMER]` vs `[NPC_OR_OTHER_VOICE]`):** Compares per-sentence pre-normalized mic dB and YuNet `mouth_motion` against stream medians; speech occurring during low mic RMS or static webcam lips is tagged `[NPC_OR_OTHER_VOICE]`.
4. **Unified Index Export:** Embeds mandatory `"stream_file"` headers inside `/files/temp/{audio_energy,chat_laughter_clusters,face_emotions,comedic_beats,unified_timeline_index}.json` to prevent stale cross-VOD cache contamination.

### Phase D: GTA 6 Peak-First + 3x3 Vision Storyboard Engine
1. **`Run GTA6 Peak & Storyboard Builder` (`scripts/gta6_peak_storyboard_builder.py`):**
   - Computes 1-second multimodal curve:
     $$V(t) = 0.42 \cdot \max(0, Z_{\text{dB}}(t)) \cdot (1 + 0.25 Z_{\text{spec}} + 0.20 Z_{\text{pitch}}) + 0.38 \cdot Z_{\text{chat}}(t + 5.5\text{s}) + 0.20 \cdot Z_{\text{face}}(t) + B_{\text{shock}}(t)$$
   - Suppresses `[0s, 15s]` intro deadzones, final `20s` outros, and housekeeping/raid/giveaway banter.
   - Extracts **Top 8 non-overlapping local maxima** (`>= 90.0s` apart on VODs `>= 20m`, `>= 40.0s` on shorter VODs), carves $[\max(3.0, t_{\text{peak}} - 32.0), \min(T_{\text{max}}, t_{\text{peak}} + 18.0)]$, and snaps boundaries outward to complete Whisper sentences.
   - Renders 8 `960x540` JPEG contact sheets (`/files/temp/gta6_cand_<k>_grid.jpg`, 9 evenly spaced `320x180` tiles per sheet, yellow `t=XXX.Xs` burned labels) via single-thread FFmpeg `xstack`, auto-rejecting windows where OpenCV tile MAE shows `> 70%` frozen/static menu frames.
2. **`Run GTA6 Vision Director` (`scripts/gta6_vision_director.py`):**
   - Sends all 8 `3x3` JPEG storyboards + speaker-tagged transcripts + Global Summary in ONE Vision pass (`gemini-2.5-flash` -> `gemini-3.5-flash-lite` -> offline fallback).
   - Enforces M-rated/NSFW/browser/menu rejection (`is_nsfw_or_unsafe`), selects Top 4–5 distinct clips across the 6 GTA 6 Launch Archetypes (`OPEN_WORLD_CHAOS_OR_COP_CHASE`, `LEONIDA_NPC_ENCOUNTER_OR_ROAST`, `HOW_TO_TIP_OR_SECRET_DISCOVERY`, `HUBRIS_WAGER_WASTED_KARMA`, `COMEDIC_BANTER_OR_SARCASM`, `STORY_CUTSCENE_OR_TWIST_REACTION`), enforces `1–2` segments strictly inside the same candidate window, and outputs complete captions/SFX metadata without a downstream Merge agent.

### Phase E: EDL Refinement, Screen Safety Audit & 9:16 Mastering
1. **`5. Split Clips` & `6. Extract Viral Segments`:**
   - Enforces Entity Continuity (`max_gap <= 45.0s` unless rare concrete noun `< 5%` VOD DF; zero empty-token bypasses), duration bounds (`22.0s – 45.0s`), tight `0.12s` cut buffers, `>5.0s` silent air trimming, Whisper sentence/pause boundary snapping, orphan ellipsis (`...`) trimming, `3–6` word (`<= 32` chars) non-dangling homophone-cleaned hooks, and deterministic `MM.SS`/decimal-minute/VOD-second meme SFX timestamp mapping.
2. **`Is Dry Run / Script Sandbox?`:**
   - **Sandbox (`true`) -> `DRY_RUN_SCRIPT_ONLY`:** Emits verified EDL JSON (`/files/temp/gta6_sandbox_edl_preview.json` or `/files/temp/n8n_sandbox_edl_preview.json`) with `pre_hook_context_text` (last 10 words up to `15s` back), `post_payoff_context_text`, and deterministic `signal_justification`.
   - **Production (`false`) -> `Loop Clips` -> `Cut & Concat All Segments` -> `Execute Cut & Concat` -> `Screen UI Vision Audit` (`IF: Screen Clean?`):** Rejects Chrome/Twitch/Discord/ESC-pause/NSFW clips before investing in audio/video mastering (whitelisting GTA 6 minimap & cutscene bars).
3. **Final Render (`Create Subtitle Binary` -> `7f. Final Render` -> `Write Sidecar JSON`):**
   - Builds ASS captions (`PlayRes 720x1280`, `Lilita One`, GTA 6 color-coded `DANGER_WORDS`/`WIN_WORDS`/`SHOCK_WORDS` highlighting, `subY = 1010`), Mixes `/files/memes/` SFX (`amix` + `-20dB` compressor + `-1.5dB` limiter), Composites Remotion animated overlay (`y=75`), Facecam (`720x380` top, 1.15x/1.35x reaction zoom), Gameplay (`720x900` bottom or `720x1280` full-screen no-cam, 1.12x/1.15x/1.45x punch zoom), and exports `libx264` `-crf 18` `.mp4`, rich multi-platform `.json` sidecar (`youtube_shorts`, `tiktok`, `instagram_reels`, `x_post`, spoiler prefixing, `comment_bait_question`, `🎥 @handle`), and logs the run row to `/files/outputs/scoreboard.csv`.

---

## 5. Deterministic Grading & 7 Forensic Hardening Patches (`/files/edl_auditor.py`)

`edl_auditor.py` scores every Sandbox EDL preview across **8 weighted dimensions (`0–100`)** and enforces the 7 closed forensic loopholes:
1. **Pre-Hook Cleanliness (`20 pts`):** Orphan ellipsis opener check + 10-word / `15.0s` backward context check (`MID_SENTENCE_START`, `PRE_HOOK_SPILLOVER_WORDS`, `DANGLING_ELLIPSIS_OPENER`).
2. **Payoff Completion (`20 pts`):** Climax aftermath & sentence closure check.
3. **Entity Continuity (`15 pts`):** No `transitive_chain_entities` bypass; `max_gap <= 45.0s` (or `<5%` DF rare concrete noun up to `180s`); requires non-empty `cause_and_effect_setup >= 15 chars`.
4. **Hook Caption Quality (`10 pts`):** `3–6 words`, `<= 32 chars`, ALL CAPS, no foreign game hallucinations, no dangling trailing function words (`DANGLING_HOOK_END`).
5. **Multimodal Grounding (`10 pts`):** Requires true empirical VOD peak (`z_db >= 2.5`, `[SCREAM:Z=...]`, `[LAUGH_BURST]`, `[CHAT_BURST]`, or `[CHAT_QUESTION_CLUSTER]`) with active `stream_file` header validation.
6. **Structural Fit + Archetype Diversity (`5 + 5 pts`):** Single continuous segment for `<4s` gaps; requires explicit reversal evidence for `HUBRIS_*` / `FLASHFORWARD_*` single-segment clips; `>= 3` distinct archetypes across batch.
7. **Pacing Hygiene (`10 pts`):** Total clip duration in `[22.0s, 45.5s]` and zero unmotivated silent gaps `> 5.0s`.
8. **Zero Admin/Outro (`5 pts`):** Filters giveaway rules, super chat banter, raids, and outro sign-offs.
