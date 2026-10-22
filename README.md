# Roblox YouTube Shorts Generator

Automated n8n workflow system for generating YouTube Shorts content from Roblox gameplay, with vision-based camera detection and auto-publishing.

## Workflows

| File | Description |
|------|-------------|
| `workflow.ts` | Main YouTube Short automation workflow (n8n-as-code) |
| `workflow_bypassed.ts` | Bypassed/debug version of the workflow |

## Vision Scripts

| File | Description |
|------|-------------|
| `cam_detector.py` | Camera/scene detector — analyzes frames for cuts, POV detection, and visual events |
| `test_vision.py` | Test harness for the vision detection pipeline |

## What the Workflow Does
1. **Trigger** — Manual or webhook-based activation
2. **Gameplay capture** — Pulls Roblox session footage/clips
3. **Vision analysis** — `cam_detector.py` scans frames to detect camera angles, scenes, and highlights
4. **Script generation** — AI generates commentary or voiceover script for the short
5. **Publishing** — Sends to the YouTube Shorts publishing pipeline

## Files

| File | Description |
|------|-------------|
| `workflow.ts` | n8n-as-code TypeScript workflow |
| `cam_detector.py` | Python vision/frame detection script |
| `test_vision.py` | Vision pipeline tests |
| `n8n-workflows.d.ts` | TypeScript type declarations |
| `package.json` | n8n-as-code package config |
| `tsconfig.json` | TypeScript config |

## Setup

### 1. Install n8n
```bash
npm install -g n8n
```

### 2. Python Vision Dependencies
```bash
pip install opencv-python numpy
```

### 3. Import Workflow
Option A — n8n-as-code CLI:
```bash
npm install
npx n8nac push
```

Option B — Import JSON directly in n8n UI

### 4. Configure Credentials
- YouTube Data API v3 key (n8n credentials panel)
- Any AI/LLM API keys used for script generation

### 5. Run Vision Tests
```bash
python test_vision.py
```

## Requirements
- n8n v1.0+
- Node.js 18+
- Python 3.9+
- OpenCV (`pip install opencv-python`)
- YouTube Data API v3 credentials
