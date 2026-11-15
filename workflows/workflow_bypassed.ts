import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : YouTube Short Automation (Bypassed Version)
// Nodes   : 80  |  Connections: 95
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ScheduleTrigger                    scheduleTrigger            [disabled]
// WhenClickingTestWorkflow           manualTrigger
// ExecuteWorkflowTrigger             executeWorkflowTrigger
// Webhook                            webhook                    [disabled]
// FindStream                         executeCommand
// IfStreamExists                     if
// EditFields                         set
// ReadReference                      readWriteFile
// CamVisionPrep                      code
// CamVisionCall                      httpRequest                [onError→out(1)]
// ParseCamConfig                     code
// VisionPrep                         code
// VisionPrep1                        code
// Config                             set
// _2ReadAudioFile                    readBinaryFile
// _3GroqWhisper                      httpRequest                [creds] [retry]
// LoopClips                          splitInBatches
// _6ExtractViralSegments             code
// CutConcatAllSegments               code
// ExecuteCutConcat                   executeCommand
// _7bExtractClipAudio                executeCommand
// _7cReadAudio                       readBinaryFile
// _7dGetSubtitlesSrt                 httpRequest                [creds] [retry]
// GetMemeList                        executeCommand
// CreateSubtitleBinary               code
// ReadWriteFilesFromDisk             readWriteFile
// _7fFinalRender                     executeCommand
// DeleteSourceVod                    executeCommand
// GetReferenceFrame                  executeCommand
// _1GlobalSummaryAi                  agent                      [AI] [onError→out(1)]
// GeminiModel1                       lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// ContextMergeAgent                  agent                      [AI] [onError→out(1)]
// GeminiModel2                       lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// PrepareFrames                      code
// IfSummaryOk                        if
// _1GlobalSummaryFallback            agent                      [AI] [onError→out(1)]
// GeminiBackupModel1                 lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// IfMergeOk                          if
// ContextMergeFallback               agent                      [AI] [onError→out(1)]
// GeminiBackupModel3                 lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// _3GroqWhisperFallback              httpRequest                [creds] [retry]
// IfWhisperOk                        if
// WaitBeforeFallback                 wait
// ReadAudioForFallback               readBinaryFile
// _1PrepareScoutPrompt               code
// GeminiModelScout                   lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// _2BasicLlmChainScout               chainLlm                   [AI] [onError→out(1)]
// ScoutLoop                          splitInBatches
// ScoutWait                          wait
// ScoutAccumulate                    code
// _3PrepareDirectorPrompt            code
// GeminiModelDirector                lmChatGoogleGemini         [creds] [retry] [ai_languageModel]
// _4BasicLlmChainDirector            chainLlm                   [AI] [onError→out(1)]
// _5SplitClips                       code
// WriteSidecarJson                   executeCommand
// PickRandomStreamer                 code
// FallbackDownload                   executeCommand             [onError→out(1)]
// WaitBeforeScout                    wait
// WaitInsideLoop                     wait
// _1ExtractAudio                     executeCommand
// GroqVisionAnalyzer                 httpRequest                [onError→out(1)]
// WaitSummaryError                   wait
// WaitSummaryFallbackError           wait
// WaitMergeError                     wait
// WaitMergeFallbackError             wait
// WaitScoutError                     wait
// WaitDirectorError                  wait
// RestoreScoutPrompt                 set
// RestoreDirectorPrompt              set
// WaitHffaceError                    wait
// RestoreHffaceInput                 set
// WaitGroqVisionError                wait
// IfSummary429                       if
// IfSummaryFallback429               if
// IfMerge429                         if
// IfMergeFallback429                 if
// IfScout429                         if
// IfDirector429                      if
// IfHfface429                        if
// IfGroqVision429                    if
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ScheduleTrigger
//    → FindStream
//      → IfStreamExists
//        → EditFields
//          → GetReferenceFrame
//            → PrepareFrames
//              → ReadReference
//                → CamVisionPrep
//                  → CamVisionCall
//                    → ParseCamConfig
//                      → VisionPrep1
//                        → GroqVisionAnalyzer
//                          → Config
//                            → _1ExtractAudio
//                              → _2ReadAudioFile
//                                → _3GroqWhisper
//                                  → IfWhisperOk
//                                    → _1GlobalSummaryAi
//                                      → IfSummaryOk
//                                        → WaitBeforeScout
//                                          → _1PrepareScoutPrompt
//                                            → ScoutLoop
//                                              → ScoutAccumulate
//                                                → _3PrepareDirectorPrompt
//                                                  → _4BasicLlmChainDirector
//                                                    → _5SplitClips
//                                                      → LoopClips
//                                                        → DeleteSourceVod
//                                                       .out(1) → WaitInsideLoop
//                                                          → _6ExtractViralSegments
//                                                            → CutConcatAllSegments
//                                                              → ExecuteCutConcat
//                                                                → _7bExtractClipAudio
//                                                                  → _7cReadAudio
//                                                                    → _7dGetSubtitlesSrt
//                                                                      → GetMemeList
//                                                                        → ContextMergeAgent
//                                                                          → IfMergeOk
//                                                                            → CreateSubtitleBinary
//                                                                              → ReadWriteFilesFromDisk
//                                                                                → _7fFinalRender
//                                                                                  → WriteSidecarJson
//                                                                                    → LoopClips (↩ loop)
//                                                                           .out(1) → ContextMergeFallback
//                                                                              → CreateSubtitleBinary (↩ loop)
//                                                                             .out(1) → IfMergeFallback429
//                                                                                → WaitMergeFallbackError
//                                                                                  → ContextMergeFallback (↩ loop)
//                                                                               .out(1) → CreateSubtitleBinary (↩ loop)
//                                                                         .out(1) → IfMerge429
//                                                                            → WaitMergeError
//                                                                              → ContextMergeAgent (↩ loop)
//                                                                           .out(1) → ContextMergeFallback (↩ loop)
//                                                   .out(1) → IfDirector429
//                                                      → WaitDirectorError
//                                                        → RestoreDirectorPrompt
//                                                          → _4BasicLlmChainDirector (↩ loop)
//                                                     .out(1) → _5SplitClips (↩ loop)
//                                             .out(1) → ScoutWait
//                                                → _2BasicLlmChainScout
//                                                  → ScoutLoop (↩ loop)
//                                                 .out(1) → IfScout429
//                                                    → WaitScoutError
//                                                      → RestoreScoutPrompt
//                                                        → _2BasicLlmChainScout (↩ loop)
//                                                   .out(1) → ScoutLoop (↩ loop)
//                                       .out(1) → _1GlobalSummaryFallback
//                                          → _1PrepareScoutPrompt (↩ loop)
//                                         .out(1) → IfSummaryFallback429
//                                            → WaitSummaryFallbackError
//                                              → _1GlobalSummaryFallback (↩ loop)
//                                           .out(1) → WaitBeforeScout (↩ loop)
//                                     .out(1) → IfSummary429
//                                        → WaitSummaryError
//                                          → _1GlobalSummaryAi (↩ loop)
//                                       .out(1) → _1GlobalSummaryFallback (↩ loop)
//                                   .out(1) → WaitBeforeFallback
//                                      → ReadAudioForFallback
//                                        → _3GroqWhisperFallback
//                                          → _1GlobalSummaryAi (↩ loop)
//                         .out(1) → IfGroqVision429
//                            → WaitGroqVisionError
//                              → VisionPrep1 (↩ loop)
//                           .out(1) → Config (↩ loop)
//                   .out(1) → IfHfface429
//                      → WaitHffaceError
//                        → RestoreHffaceInput
//                          → ReadReference (↩ loop)
//                     .out(1) → ParseCamConfig (↩ loop)
//       .out(1) → PickRandomStreamer
//          → FallbackDownload
//            → FindStream (↩ loop)
//           .out(1) → FindStream (↩ loop)
// WhenClickingTestWorkflow
//    → FindStream (↩ loop)
// ExecuteWorkflowTrigger
//    → FindStream (↩ loop)
// Webhook
//    → FindStream (↩ loop)
//
// AI CONNECTIONS
// _1GlobalSummaryAi.uses({ ai_languageModel: GeminiModel1 })
// ContextMergeAgent.uses({ ai_languageModel: GeminiModel2 })
// _1GlobalSummaryFallback.uses({ ai_languageModel: GeminiBackupModel1 })
// ContextMergeFallback.uses({ ai_languageModel: GeminiBackupModel3 })
// _2BasicLlmChainScout.uses({ ai_languageModel: GeminiModelScout })
// _4BasicLlmChainDirector.uses({ ai_languageModel: GeminiModelDirector })
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'D2hITsyjP5dVsqBZ',
    name: 'YouTube Short Automation (Bypassed Version)',
    active: true,
    settings: { executionOrder: 'v1' },
})
export class YoutubeShortAutomationBypassedVersionWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: '68b8f480-563b-428a-8984-9c9888eddf90',
        name: 'Schedule Trigger',
        type: 'n8n-nodes-base.scheduleTrigger',
        version: 1.2,
        position: [-97000, 26300],
        disabled: true,
    })
    ScheduleTrigger = {
        rule: {
            interval: [
                {
                    field: 'hours',
                },
            ],
        },
    };

    @node({
        id: 'manual-trigger-yt-short',
        name: 'When clicking Test workflow',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [-97000, 26100],
    })
    WhenClickingTestWorkflow = {};

    @node({
        id: 'execute-workflow-trigger-yt-short',
        name: 'Execute Workflow Trigger',
        type: 'n8n-nodes-base.executeWorkflowTrigger',
        version: 1,
        position: [-97000, 26500],
    })
    ExecuteWorkflowTrigger = {};

    @node({
        id: 'test-webhook-trigger',
        webhookId: 'test-short-trigger',
        name: 'Webhook',
        type: 'n8n-nodes-base.webhook',
        version: 1.1,
        position: [-97000, 25900],
        disabled: true,
    })
    Webhook = {
        path: 'test-run',
        responseMode: 'lastNode',
        options: {},
    };

    @node({
        id: '902599e5-d85a-472c-a17d-e425f6b049ff',
        name: 'Find Stream',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-96800, 26300],
    })
    FindStream = {
        command:
            'file=$(ls -1 /files/inputs/ | grep "\\.mp4$" | grep -v "\\.processing\\.mp4$" | head -n 1); if [ -z "$file" ]; then stale=$(ls -1 /files/inputs/ | grep "\\.processing\\.mp4$" | head -n 1); if [ -n "$stale" ]; then mv "/files/inputs/$stale" "/files/inputs/${stale%.processing.mp4}.mp4"; file="${stale%.processing.mp4}.mp4"; fi; fi; if [ -n "$file" ]; then mv "/files/inputs/$file" "/files/inputs/${file%.mp4}.processing.mp4"; echo "${file%.mp4}.processing.mp4"; else echo ""; fi',
    };

    @node({
        id: 'b5a5239f-0109-4da8-88eb-26bc2ff3bf8f',
        name: 'If Stream Exists',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-96600, 26300],
    })
    IfStreamExists = {
        conditions: {
            options: {
                caseSensitive: true,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ $json.stdout.trim().length }}',
                    rightValue: 0,
                    operator: {
                        type: 'number',
                        operation: 'gt',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'd5e2ebac-2e9d-4969-85d8-a24b334adccd',
        name: 'Edit Fields',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [-96400, 26100],
    })
    EditFields = {
        assignments: {
            assignments: [
                {
                    id: 'file_set',
                    name: 'stream_file',
                    value: '={{ $json.stdout.trim() }}',
                    type: 'string',
                },
            ],
        },
        options: {},
    };

    @node({
        id: '74842daf-31d2-40ed-a451-d9fef48fbc2c',
        name: 'Read Reference',
        type: 'n8n-nodes-base.readWriteFile',
        version: 1,
        position: [-95680, 26100],
    })
    ReadReference = {
        fileSelector: '={{ $json.file }}',
        options: {
            dataPropertyName: 'data',
        },
    };

    @node({
        id: '40a29d15-5a53-4c58-ad81-912c99a2f221',
        name: 'Cam Vision Prep',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-95440, 26280],
    })
    CamVisionPrep = {
        jsCode: `const base64Data = $('Read Reference').first().binary.data.data.replace(/\\s/g, "");
return [{ pairedItem: { item: 0 }, json: { cam_vision_payload: { 
    contents: [{
        parts: [
            { text: "This is a gaming livestream frame. Find the streamer's webcam PiP overlay. VERY IMPORTANT: Return a TIGHT bounding box around ONLY the streamer's head and shoulders! Do NOT include the background of the streamer's room or the edges of the webcam box. Return ONLY JSON like this: {'found': true, 'xmin': 10, 'ymin': 10, 'xmax': 150, 'ymax': 100} with pixel coords in a 480x270 image. If no PiP exists return {'found': false}." },
            { inline_data: { mime_type: "image/jpeg", data: base64Data } }
        ]
    }],
    generationConfig: {
        responseMimeType: "application/json",
        maxOutputTokens: 4096
    }
} } }];`,
    };

    @node({
        id: '40a29d15-5a53-4c58-ad81-912c99a2f221b',
        name: 'Cam Vision Call',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [-95200, 26280],
        onError: 'continueErrorOutput',
    })
    CamVisionCall = {
        method: 'POST',
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={{ $env.GEMINI_API_KEY }}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ $json.cam_vision_payload }}',
        options: {},
    };

    @node({
        id: '9e5021d9-aa8f-4b3e-a7cc-06f249a6cb8e',
        name: 'Parse Cam Config',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-94860, 26340],
    })
    ParseCamConfig = {
        jsCode: `let camConfig = {
  ai_found: false,
  camera_type: 'none',
  cam_x: 0,
  cam_y: 0,
  cam_w: 0,
  cam_h: 0,
  confidence: 0
};
let parsed = false;

try {
  // 1. Read stdout from previous node (Get Reference Frame)
  const inputData = $input.first()?.json || {};
  const raw = inputData.stdout || '';

  if (inputData.cam_x !== undefined && inputData.cam_y !== undefined && inputData.ai_found !== undefined) {
    camConfig = inputData;
    parsed = true;
  } else if (raw) {
    const match = raw.match(/\\{[\\s\\S]*\\}/);
    if (match) {
      camConfig = JSON.parse(match[0]);
      parsed = true;
    }
  }
} catch (e) {
  // fallback if parse fails
}

// 2. Safe disk fallback ONLY if stdout was empty or incomplete
if (!parsed) {
  try {
    const fs = require('fs');
    if (fs && fs.existsSync && fs.existsSync('/files/temp/cam_config.json')) {
      const raw = fs.readFileSync('/files/temp/cam_config.json', 'utf8');
      const diskConfig = JSON.parse(raw);
      if (diskConfig && typeof diskConfig === 'object') {
        camConfig = diskConfig;
      }
    }
  } catch (e) {
    // fs not permitted in sandbox or file missing
  }
}

return [{
  pairedItem: { item: 0 },
  json: {
    cam_x: Number(camConfig.cam_x) || 0,
    cam_y: Number(camConfig.cam_y) || 0,
    cam_w: Number(camConfig.cam_w) || 0,
    cam_h: Number(camConfig.cam_h) || 0,
    ai_found: !!camConfig.ai_found,
    camera_type: camConfig.camera_type || 'none',
    confidence: Number(camConfig.confidence) || 0
  }
}];`,
    };

    @node({
        id: '73f1d8b2-da6f-4aea-af00-17533bfb2248',
        name: 'Vision Prep',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-94200, 26320],
    })
    VisionPrep = {
        jsCode: `const base64Data = $('Read Reference').first().binary.data.data.replace(/\\s/g, "");
return [{ pairedItem: { item: 0 }, json: { cam_vision_payload: { 
    contents: [{
        parts: [
            { text: "This is a gaming livestream frame. Find the streamer's webcam PiP (Picture-in-Picture) overlay. It may be a person, vtuber avatar, or emoji. Return ONLY JSON: {\\\"found\\\": true, \\\"xmin\\\": 10, \\\"ymin\\\": 10, \\\"xmax\\\": 150, \\\"ymax\\\": 100} with pixel coords in a 480x270 image. If no PiP exists return {\\\"found\\\": false}." },
            { inline_data: { mime_type: "image/jpeg", data: base64Data } }
        ]
    }],
    generationConfig: {
        responseMimeType: "application/json",
        maxOutputTokens: 4096
    }
} } }];`,
    };

    @node({
        id: '73f1d8b2-da6f-4aea-af00-17533bfb2248',
        name: 'Vision Prep',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-93340, 26000],
    })
    VisionPrep1 = {
        jsCode: `const base64Data = $('Read Reference').first().binary.data.data.replace(/\\s/g, "");
return [{ pairedItem: { item: 0 }, json: { vision_payload: { 
    contents: [{
        parts: [
            { text: "This is a gaming livestream frame. Briefly describe what is happening in the gameplay and what the streamer's reaction is. Keep it to 2 sentences." },
            { inline_data: { mime_type: "image/jpeg", data: base64Data } }
        ]
    }],
    generationConfig: {
        responseMimeType: "application/json",
        maxOutputTokens: 4096
    }
} } }];`,
    };

    @node({
        id: 'd2c47f93-b3ac-422c-afb9-8f585f6929da',
        name: 'Config',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [-92920, 26360],
    })
    Config = {
        assignments: {
            assignments: [
                {
                    id: 'config_name',
                    name: 'streamer_name',
                    value: 'malik',
                    type: 'string',
                },
            ],
        },
        options: {},
    };

    @node({
        id: '3d9075f9-061f-4f1e-9bef-671418883d98',
        name: '2. Read Audio File',
        type: 'n8n-nodes-base.readBinaryFile',
        version: 1,
        position: [-92540, 25900],
    })
    _2ReadAudioFile = {
        filePath: '/files/temp/audio.mp3',
    };

    @node({
        id: '1269e981-bdce-45e8-b5d2-b45a1306f31d',
        name: '3. Groq Whisper',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [-92340, 25900],
        credentials: { groqApi: { id: 'PF1ZMT03O2E5waqU', name: 'Groq account 2' } },
        retryOnFail: true,
        maxTries: 4,
        waitBetweenTries: 5000,
    })
    _3GroqWhisper = {
        method: 'POST',
        url: 'https://api.groq.com/openai/v1/audio/transcriptions',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'groqApi',
        sendBody: true,
        contentType: 'multipart-form-data',
        bodyParameters: {
            parameters: [
                {
                    name: 'model',
                    value: 'whisper-large-v3-turbo',
                },
                {
                    parameterType: 'formBinaryData',
                    name: 'file',
                    inputDataFieldName: 'data',
                },
                {
                    name: 'response_format',
                    value: 'verbose_json',
                },
                {
                    name: 'timestamp_granularities[]',
                    value: 'word',
                },
                {
                    name: 'prompt',
                    value: 'Roblox gaming, Lucky Blocks, Divine Mutation, Strawberry Elephant, Taco Combinacion, 10x Luck, streamer reacting, gaming chaos.',
                },
            ],
        },
        options: {
            timeout: 300000,
        },
    };

    @node({
        id: 'c9e2930c-af14-479a-8437-500650057dcf',
        name: 'Loop Clips',
        type: 'n8n-nodes-base.splitInBatches',
        version: 3,
        position: [-85540, 26140],
    })
    LoopClips = {
        batchSize: 1,
        options: {},
    };

    @node({
        id: '2e9bdfb8-34d6-444b-81bd-d986eba553be',
        name: '6. Extract Viral Segments',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-85180, 26240],
    })
    _6ExtractViralSegments = {
        jsCode: `const fs = require('fs');
const inputItems = $input.all().map(i => i.json);
const BUFFER = 0.12; // Tight buffer for snappy Shorts pacing

// Load Whisper words (Production nodes first -> Sandbox cache / disk fallbacks)
let words = [];
try {
  const w1 = $('3. Groq Whisper').first().json;
  words = w1.words || (w1.x_groq && w1.x_groq.words) || [];
} catch(e) {}
if (words.length === 0) {
  try {
    const w2 = $('3. Groq Whisper Fallback').first().json;
    words = w2.words || (w2.x_groq && w2.x_groq.words) || [];
  } catch(e) {}
}
if (words.length === 0) {
  try {
    const lct = $('Load Cached Telemetry').first().json;
    words = lct.words || [];
  } catch(e) {}
}
if (words.length === 0) {
  const txFiles = ['/files/temp/transcript.json', '/files/outputs/whisper_28754.json', '/files/temp/whisper_raw.json'];
  for (const fp of txFiles) {
    if (fs.existsSync(fp)) {
      try {
        const d = JSON.parse(fs.readFileSync(fp, 'utf8'));
        words = d.words || (d.x_groq && d.x_groq.words) || [];
        if (words.length > 0) break;
      } catch(e) {}
    }
  }
}

const fillerWords = new Set(["speaking", "of", "um", "uh", "oh", "since", "everyone", "like", "so"]);
const allOut = [];

inputItems.forEach((clipData, clipIdx) => {
  const isDryRun = Boolean(clipData.dry_run);
  let finalSegs = [];

  let rawIntervals = [];
  if (clipData.segments && Array.isArray(clipData.segments) && clipData.segments.length > 0) {
    rawIntervals = clipData.segments
      .filter(s => typeof s.start === 'number' && typeof s.end === 'number' && s.end > s.start)
      .map(s => ({ start: s.start, end: s.end, role: s.role || 'STORY_BEAT' }));
  }

  if (rawIntervals.length === 0) {
    const start = clipData.start_time;
    const end = clipData.end_time;
    if (typeof start !== 'number' || typeof end !== 'number') {
      allOut.push({ pairedItem: { item: 0 }, json: { error: "No timestamps", clip_title: clipData.title, dry_run: isDryRun } });
      return;
    }
    rawIntervals = [{ start, end, role: 'STORY_BEAT' }];
  }

  // De-overlap non-hook body intervals & cap opening HOOK_CLIMAX teaser at <= 2.6s
  const dedupedIntervals = [];
  const seenBody = [];
  rawIntervals.forEach((iv, iIdx) => {
    let st = Math.max(3.0, iv.start);
    let en = iv.end;
    const r = String(iv.role || 'STORY_BEAT').toUpperCase();
    if (iIdx === 0 && r === 'HOOK_CLIMAX') {
      dedupedIntervals.push({ start: st, end: Math.min(en, st + 2.6), role: r });
      return;
    }
    for (const pb of seenBody) {
      if (st < pb.end + 0.15 && en > pb.start - 0.15) {
        if (en > pb.end + 1.2) st = pb.end + 0.15;
        else if (st < pb.start - 1.2) en = pb.start - 0.15;
        else st = en;
      }
    }
    if (en - st >= 0.8) {
      seenBody.push({ start: st, end: en });
      dedupedIntervals.push({ start: st, end: en, role: r });
    }
  });
  if (dedupedIntervals.length > 0) rawIntervals = dedupedIntervals;

  rawIntervals.forEach((interval, intervalIdx) => {
    const start = interval.start;
    const intEnd = interval.end;
    const role = interval.role || 'STORY_BEAT';

    if (words.length > 0) {
      const clipWords = words.filter(w => w.end >= start && w.start <= intEnd);

      if (clipWords.length > 0) {
        let wordIdx = 0;
        if (intervalIdx === 0) {
          // ZERO-SECOND RETENTION: Trim conversational hesitation filler at start
          while (wordIdx < Math.min(3, clipWords.length - 1)) {
            const cleanWord = String(clipWords[wordIdx].word || "").toLowerCase().replace(/[^a-z]/g, '');
            if (fillerWords.has(cleanWord)) {
              wordIdx++;
            } else {
              break;
            }
          }
        }
        const initialWord = clipWords[wordIdx] || clipWords[0];
        let currentSegStart = Math.max(start, clipWords[0].start - 0.10);
        if (wordIdx > 0 && initialWord.start > currentSegStart) {
          currentSegStart = initialWord.start - 0.08;
        }
        let lastWordEnd = initialWord.end;

        for (let i = wordIdx + 1; i < clipWords.length; i++) {
          const w = clipWords[i];
          // If gap is more than 0.55s, jump cut the dead air!
          if (w.start - lastWordEnd > 0.55) {
            finalSegs.push({
              name: \`\${role}_part\`,
              role,
              start: currentSegStart,
              end: lastWordEnd + BUFFER
            });
            currentSegStart = Math.max(lastWordEnd + BUFFER, w.start - BUFFER);
          }
          lastWordEnd = w.end;
        }
        finalSegs.push({
          name: \`\${role}_part\`,
          role,
          start: currentSegStart,
          end: Math.min(intEnd, lastWordEnd + BUFFER)
        });
      } else {
        finalSegs.push({
          name: role,
          role,
          start: Math.max(0, start - BUFFER),
          end: intEnd + BUFFER
        });
      }
    } else {
      finalSegs.push({
        name: role,
        role,
        start: Math.max(0, start - BUFFER),
        end: intEnd + BUFFER
      });
    }
  });

  // COLD OPEN RETENTION TRAP: Prepend 1.8s cold open payoff teaser ONLY if segment 0 isn't already a HOOK_CLIMAX
  const hasExplicitHook = rawIntervals[0] && rawIntervals[0].role === 'HOOK_CLIMAX';
  if (!hasExplicitHook && rawIntervals.length === 1 && typeof clipData.cold_open_start === 'number' && typeof clipData.cold_open_end === 'number') {
    const coStart = clipData.cold_open_start;
    const coEnd = Math.min(clipData.cold_open_end, coStart + 1.8);
    const totalStart = rawIntervals[0].start;
    const totalEnd = rawIntervals[rawIntervals.length - 1].end;
    if (coEnd - coStart >= 1.0 && coStart >= totalStart && coEnd <= totalEnd) {
      if (coStart - totalStart > 4.0) {
        finalSegs.unshift({
          name: 'ColdOpen_teaser',
          role: 'HOOK_CLIMAX',
          start: coStart,
          end: coEnd
        });
      }
    }
  }

  // Attach spoken_text per cut segment and compute assembled script
  const enrichedSegs = finalSegs.map((seg) => {
    const segWords = words.length > 0
      ? words.filter(w => w.end >= seg.start && w.start <= seg.end).map(w => String(w.word || '').trim()).join(' ')
      : '';
    return {
      ...seg,
      spoken_text: segWords
    };
  });

  const computedScript = enrichedSegs
    .map(s => \`[\${s.role} \${s.start.toFixed(1)}s-\${s.end.toFixed(1)}s] "\${s.spoken_text || '...'}"\`)
    .join(' -> ');

  enrichedSegs.forEach((seg, idx) => {
    allOut.push({
      pairedItem: { item: 0 },
      json: {
        dry_run: isDryRun,
        clip_number: clipData.clip_number || (clipIdx + 1),
        segment_order: idx,
        segment_name: seg.name,
        role: seg.role,
        start: Number(seg.start.toFixed(3)),
        end: Number(seg.end.toFixed(3)),
        duration: Number((seg.end - seg.start).toFixed(3)),
        spoken_text: seg.spoken_text,
        clip_title: clipData.title,
        narrative_archetype: clipData.narrative_archetype || 'HUBRIS_INSTANT_KARMA',
        theme: clipData.theme,
        hook_caption: clipData.hook_caption,
        cause_and_effect_setup: clipData.cause_and_effect_setup,
        assembled_spoken_script: clipData.assembled_spoken_script || computedScript,
        signal_justification: clipData.signal_justification || {},
        total_segments: enrichedSegs.length
      }
    });
  });
});

return allOut;`,
    };

    @node({
        id: '353a3f05-5e2a-43fd-958d-1ba1957a996b',
        name: 'Cut & Concat All Segments',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-85000, 26240],
    })
    CutConcatAllSegments = {
        jsCode: `const all = $input.all().map(item => item.json).sort((a, b) => a.segment_order - b.segment_order);
const clipTitle = all[0].clip_title;
const streamFile = $('Edit Fields').first().json.stream_file;

// Drop segments shorter than 0.15s - keeps quick punchlines/reactions without ffmpeg choking
const segments = all.filter(s => (s.end - s.start) >= 0.15);
if (segments.length === 0) {
    // Emergency fallback: take first 30 seconds
    segments.push({ ...all[0], start: 0, end: 30 });
}

// Fast seek directly to keyframe before clip start to prevent decoding delay & NAL unit corruption
const minStart = Math.min(...segments.map(s => s.start));
const maxEnd = Math.max(...segments.map(s => s.end));
const seekStart = Math.max(0, Math.floor(minStart - 3));
const seekDuration = Math.ceil(maxEnd - seekStart + 3);

let filterComplex = "";
let concatInputs = "";
let partIdx = 0;

segments.forEach((seg) => {
    const relStart = Math.max(0, seg.start - seekStart);
    const relEnd = Math.max(relStart + 0.1, seg.end - seekStart);
    const segDur = Math.max(0.1, relEnd - relStart);
    const fadeDur = Math.min(0.025, segDur / 4);
    const outStart = Math.max(0, segDur - fadeDur);

    filterComplex += `[0:v]trim=start=${relStart.toFixed(3)}:end=${relEnd.toFixed(3)},setpts=PTS-STARTPTS[v${partIdx}];`;
    filterComplex += `[0:a]atrim=start=${relStart.toFixed(3)}:end=${relEnd.toFixed(3)},asetpts=PTS-STARTPTS,afade=t=in:ss=0:d=${fadeDur.toFixed(3)},afade=t=out:st=${outStart.toFixed(3)}:d=${fadeDur.toFixed(3)}[a${partIdx}];`;
    concatInputs += `[v${partIdx}][a${partIdx}]`;
    partIdx++;
});

const ffmpegCmd = \`ffmpeg -loglevel error -y -ss \${seekStart} -t \${seekDuration} -i "/files/inputs/\${streamFile}" -filter_complex "\${filterComplex}\${concatInputs}concat=n=\${partIdx}:v=1:a=1[v_out][a_out]" -map "[v_out]" -map "[a_out]" -c:v libx264 -preset fast -crf 16 -c:a aac -movflags +faststart "/files/temp/concatenated_clip.mp4"\`;

return [{ pairedItem: { item: 0 }, json: { command: ffmpegCmd, clip_title: clipTitle, parts: partIdx } }];
`,
    };

    @node({
        id: '44831329-2ce1-4da0-aa00-fe06b91732e3',
        name: 'Execute Cut & Concat',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-84800, 26240],
    })
    ExecuteCutConcat = {
        command: '={{ $json.command }}',
    };

    @node({
        id: '1f4b6274-6d6c-47c4-ba1d-a430a9c7bec7',
        name: '7b. Extract Clip Audio',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-84600, 26240],
    })
    _7bExtractClipAudio = {
        command:
            'ffmpeg -loglevel error -y -i "/files/temp/concatenated_clip.mp4" -vn -acodec libmp3lame -q:a 5 "/files/temp/temp_audio.mp3" && python3 /files/scream_detector.py "/files/temp/temp_audio.mp3" "/files/temp/screams.json"',
    };

    @node({
        id: 'e6da088d-decd-4472-ac66-65a5e08db04b',
        name: '7c. Read Audio',
        type: 'n8n-nodes-base.readBinaryFile',
        version: 1,
        position: [-84400, 26240],
    })
    _7cReadAudio = {
        filePath: '/files/temp/temp_audio.mp3',
    };

    @node({
        id: '80fa3522-c3c6-4735-b4a0-190ce1b3706c',
        name: '7d. Get Subtitles (SRT)',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [-84200, 26240],
        credentials: { groqApi: { id: 'PF1ZMT03O2E5waqU', name: 'Groq account 2' } },
        retryOnFail: true,
        maxTries: 4,
        waitBetweenTries: 60000,
    })
    _7dGetSubtitlesSrt = {
        method: 'POST',
        url: 'https://api.groq.com/openai/v1/audio/transcriptions',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'groqApi',
        sendBody: true,
        contentType: 'multipart-form-data',
        bodyParameters: {
            parameters: [
                {
                    name: 'model',
                    value: 'whisper-large-v3-turbo',
                },
                {
                    parameterType: 'formBinaryData',
                    name: 'file',
                    inputDataFieldName: 'data',
                },
                {
                    name: 'response_format',
                    value: 'verbose_json',
                },
                {
                    name: 'timestamp_granularities[]',
                    value: 'word',
                },
                {
                    name: 'prompt',
                    value: 'Roblox gaming, Lucky Blocks, Divine Mutation, Strawberry Elephant, Taco Combinacion, 10x Luck, streamer reacting, gaming chaos.',
                },
            ],
        },
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: 'a161758e-b59c-4f7d-8b98-494b36e598bd',
        name: 'Get Meme List',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-84040, 26240],
    })
    GetMemeList = {
        command:
            'mkdir -p /files/inputs/fonts && cp -n /files/inputs/*.ttf /files/inputs/fonts/ 2>/dev/null || true; ls -1 /files/memes && echo "---DIMENSIONS---" && ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "/files/temp/concatenated_clip.mp4" || echo "1920x1080"',
    };

    @node({
        id: '727de56b-e2bf-4cce-9dd8-dc7fdc62e4b1',
        name: 'Create Subtitle Binary',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-82080, 26080],
    })
    CreateSubtitleBinary = {
        jsCode: `const NL = String.fromCharCode(10);
const FONT_SIZE = 48;
const MAIN_COLOR = "&HFFFFFF&";

// High-Impact Categorical Dictionaries for Dynamic Word Highlighting
const DANGER_WORDS = new Set(["DEAD", "DIE", "DIED", "KILL", "KILLED", "RUN", "ESCAPE", "MONSTER", "GHOST", "BACKROOMS", "JUMPSCARE", "DANGER", "CAUGHT", "TRAPPED", "ARRESTED", "BUSTED", "BLUNDER", "FALL", "LOST", "FAIL", "FAILED", "SHOT", "EXPLODE", "NO", "NOO", "NOOO", "HELP", "STOP"]);
const WIN_WORDS = new Set(["WIN", "WON", "INSANE", "CRAZY", "GOD", "SECRET", "RARE", "MONEY", "RICH", "UNLOCKED", "MAX", "UPGRADE", "BEST", "HUGE", "PRO", "CLUTCH", "LEGENDARY", "MILLION", "JACKPOT"]);
const SHOCK_WORDS = new Set(["WHAT", "WHY", "HOW", "BRO", "OMG", "WAIT", "ACTUALLY", "SERIOUSLY", "NEVER", "LITERAL", "LITERALLY", "BUNGER", "LAUNCH", "HACKER", "SCAM", "EXPOSED", "IMPOSSIBLE", "HUH"]);

function formatTimeASS(seconds) {
  const sTotal = Math.max(0, parseFloat(seconds) || 0);
  const h = Math.floor(sTotal / 3600);
  const m = Math.floor((sTotal % 3600) / 60);
  const s = Math.floor(sTotal % 60);
  const cs = Math.floor((sTotal % 1) * 100);
  return h + ":" + String(m).padStart(2,'0') + ":" + String(s).padStart(2,'0') + "." + String(cs).padStart(2,'0');
}

// ── Strict Caption & Placeholder Sanitizer ───────────────────────────────
function sanitizeCaption(str, defaultFallback) {
  if (!str || typeof str !== 'string') return defaultFallback || "MUST WATCH MOMENT";
  let clean = str.trim();
  if (/[\$({]|item\.json|loop\s*clips|\{\{|\}\}|undefined|null/i.test(clean)) {
    return defaultFallback || "MUST WATCH MOMENT";
  }
  clean = clean.replace(/[{}\\x27\\x22`$()]/g, '').replace(/_/g, ' ').trim().toUpperCase();
  if (clean.length < 3 || /LOOP CLIPS|ITEM JSON/i.test(clean)) {
    return defaultFallback || "MUST WATCH MOMENT";
  }
  return clean.substring(0, 42);
}

const subInput = $('7d. Get Subtitles (SRT)').first().json;
let wordData = subInput.words || (subInput.x_groq && subInput.x_groq.words) || [];

const camConfig = $('Parse Cam Config').first().json || {};
const camW = camConfig.cam_w || 400, camH = camConfig.cam_h || 250, camX = camConfig.cam_x || 0, camY = camConfig.cam_y || 0;
const hasCam = !!(camConfig && camConfig.ai_found);
const avatarRowDetected = !!(camConfig && camConfig.avatar_row_detected);

const getMemeOutput = $('Get Meme List').first().json.stdout || "";
const parts = getMemeOutput.split("---DIMENSIONS---");
const realFiles = (parts[0] || "").split(NL).map(f => f.trim().replace(/\r/g, '')).filter(f => f.length > 3);

let isVertical = false;
if (parts.length > 1) {
  const dims = parts[1].trim().split('x');
  if (dims.length === 2 && parseInt(dims[0]) < parseInt(dims[1])) {
    isVertical = true;
  }
}

function getBestMatch(aiFile) {
  if (!aiFile) return null;
  const clean = String(aiFile).toLowerCase().replace('.mp3', '');
  if (realFiles.includes(aiFile)) return aiFile;
  return realFiles.find(f => {
    const fClean = f.toLowerCase().replace('.mp3', '');
    return fClean.includes(clean) || clean.includes(fClean);
  }) || null;
}

// ── Caption & Context Parsing ────────────────────────────────────────────
let loopItem = {};
try { loopItem = $('Loop Clips').item.json || {}; } catch(e) {
  try { loopItem = $('Loop Clips').first().json || {}; } catch(e2) {}
}
const clipData = loopItem;

const clipStart = parseFloat(clipData.start_time) || 0;
const clipEnd = parseFloat(clipData.end_time) || (clipStart + 36);
const clipDur = Math.max(1, Math.round((clipEnd - clipStart) * 10) / 10);

let rawCaption = sanitizeCaption(clipData.hook_caption || clipData.title, "MUST WATCH MOMENT");
let screams = [], memes = [], climaxQuote = "", reactionTriggers = [];

// ── Read screams.json if generated by scream_detector.py ────────────────
try {
  const fs = require('fs');
  if (fs.existsSync('/files/temp/screams.json')) {
    const screamData = JSON.parse(fs.readFileSync('/files/temp/screams.json', 'utf-8'));
    if (Array.isArray(screamData)) {
      screams = screams.concat(screamData);
    }
  }
} catch(e) {}

try {
  let raw = "";
  try { raw = $('Context Merge Agent').first().json.output || ""; } catch(e0) {}
  if (!raw) {
    try { raw = $('Context Merge Fallback').first().json.output || ""; } catch(e1) {}
  }
  if (raw) {
    const b3 = String.fromCharCode(96).repeat(3);
    raw = raw.split(b3 + 'json').join('').split(b3).join('').trim();
    const parsed = JSON.parse(raw);
    if (parsed.story_hook) rawCaption = sanitizeCaption(parsed.story_hook, rawCaption);
    if (parsed.climax_quote) climaxQuote = parsed.climax_quote;
    if (parsed.screams) screams = screams.concat(parsed.screams);
    if (parsed.screams_or_full_cam) screams = screams.concat(parsed.screams_or_full_cam);
    if (parsed.reaction_triggers && Array.isArray(parsed.reaction_triggers)) {
      reactionTriggers = reactionTriggers.concat(parsed.reaction_triggers);
    }
    if (parsed.memes && Array.isArray(parsed.memes)) memes = parsed.memes;
  }
} catch(e) {}

// ── Detect Climax Timing for Impact Zoom ─────────────────────────────────
const absolutePayoff = parseFloat(clipData.payoff_time) || 0;
let relativePayoff = (absolutePayoff > clipStart) ? (absolutePayoff - clipStart) : absolutePayoff;
if (relativePayoff <= 0 || relativePayoff >= clipDur) {
  relativePayoff = Math.max(0, clipDur - 3.5);
}

let climaxStart = relativePayoff;
if (climaxQuote && wordData.length > 0) {
  const quoteWords = String(climaxQuote).toLowerCase().replace(/[^a-z0-9\s]/g, '').trim().split(/\s+/).filter(Boolean);
  if (quoteWords.length > 0) {
    let bestIdx = -1;
    let maxMatch = 0;
    for (let i = 0; i <= wordData.length - quoteWords.length; i++) {
      let matches = 0;
      for (let k = 0; k < quoteWords.length; k++) {
        const w = String(wordData[i + k].word || "").toLowerCase().replace(/[^a-z0-9]/g, '');
        if (w === quoteWords[k]) matches++;
      }
      if (matches > maxMatch) {
        maxMatch = matches;
        bestIdx = i;
      }
    }
    if (bestIdx >= 0 && maxMatch >= Math.min(2, quoteWords.length)) {
      const matchStart = parseFloat(wordData[bestIdx].start) || 0;
      if (matchStart > 0 && matchStart < clipDur) {
        climaxStart = matchStart;
      }
    }
  }
}
if (climaxStart <= 0 || climaxStart >= clipDur) {
  if (screams.length > 0 && Array.isArray(screams[0]) && screams[0].length >= 1) {
    climaxStart = parseFloat(screams[0][0]) || (clipDur - 3.5);
  } else {
    climaxStart = Math.max(0, clipDur - 3.5);
  }
}

// ── Tactical SFX: Auto-inject vine-boom at climax if memes empty ──────────
if (!memes || memes.length === 0) {
  memes = [{
    timestamp: Math.round(climaxStart * 10) / 10,
    file: "vine-boom-sound-effect_KT89XIq.mp3",
    volume: 0.30
  }];
}

// ── Remotion Hybrid Animated Hook Generation ─────────────────────────────
let remotionOverlayFile = "";
try {
  const hookLayout = hasCam ? 'facecam' : 'full';
  const fs = require('fs');
  const tempPayload = '/files/temp/hook_payload_' + Date.now() + '.json';
  fs.writeFileSync(tempPayload, JSON.stringify({
    title: rawCaption || "MUST WATCH MOMENT",
    badge: "MUST WATCH",
    layout: hookLayout,
    durationInSeconds: 3.5
  }));
  const res = require('child_process').execSync(
    'wget --header="Content-Type: application/json" --post-file="' + tempPayload + '" -qO- http://remotion-server:3000/render-overlay || true',
    { timeout: 15000 }
  ).toString().trim();
  try { fs.unlinkSync(tempPayload); } catch(e) {}
  if (res) {
    const parsed = JSON.parse(res);
    if (parsed && parsed.success && parsed.n8nPath) {
      remotionOverlayFile = parsed.n8nPath;
    }
  }
} catch(e) {}

const overlayInput = remotionOverlayFile ? ('-loop 1 -t 3.5 -i "' + remotionOverlayFile + '"') : "";
const memeInputOffset = remotionOverlayFile ? 2 : 1;

// ── Meme Audio Mixing & Loudness Mastering ───────────────────────────────
const masterAudioFx = "acompressor=threshold=-20dB:ratio=5:attack=4:release=45,alimiter=limit=-1.5dB:attack=4:release=45,equalizer=f=3500:t=q:w=1.2:g=-3.5";

let audioInputs = [], audioFilters = "", activeMemes = 0;
if (memes && memes.length > 0) {
  memes.forEach(m => {
    if (activeMemes >= 6 || !m.file) return;
    const realFile = getBestMatch(m.file) || (realFiles.find(f => f.toLowerCase().includes('vine')) || null);
    if (realFile) {
      const time = parseFloat(m.timestamp);
      if (!isNaN(time) && time >= 0) {
        const delay = Math.floor(time * 1000);
        audioInputs.push('-i "/files/memes/' + realFile + '"');
        const memeVol = (typeof m.volume === 'number' ? m.volume : 0.30);
        const streamIdx = activeMemes + memeInputOffset;
        audioFilters += '[' + streamIdx + ':a]volume=' + memeVol + ',adelay=' + delay + '|' + delay + '[meme' + (activeMemes+1) + '];';
        activeMemes++;
      }
    }
  });
}

let audioMixFilter = "";
if (activeMemes > 0) {
  let mixInputs = "[a_raw_norm]";
  for (let k = 1; k <= activeMemes; k++) mixInputs += '[meme' + k + ']';
  audioMixFilter = '[0:a]' + masterAudioFx + '[a_raw_norm];' + audioFilters + mixInputs + 'amix=inputs=' + (activeMemes + 1) + ':duration=first:normalize=0,' + masterAudioFx + '[a_out]';
} else {
  audioMixFilter = '[0:a]' + masterAudioFx + '[a_out]';
}

// ── Reaction Triggers (115% Aggressive Punch Zoom for Screams & Kills) ────
let reactionBlocks = [];

// 1. Process explicit scream intervals from audio detector / AI
if (Array.isArray(screams)) {
  screams.forEach(s => {
    if (Array.isArray(s) && s.length >= 1) {
      const s0 = Math.max(0, parseFloat(s[0]));
      const s1 = Math.min(clipDur, s.length >= 2 ? Math.min(parseFloat(s[1]), s0 + 2.0) : s0 + 1.5);
      if (s1 > s0) {
        reactionBlocks.push('between(t,' + s0.toFixed(2) + ',' + s1.toFixed(2) + ')');
      }
    }
  });
}

// 2. Process reaction trigger timestamps
if (Array.isArray(reactionTriggers)) {
  reactionTriggers.forEach(t => {
    const tr = parseFloat(t);
    if (!isNaN(tr) && tr >= 0 && tr < clipDur) {
      const tEnd = Math.min(clipDur, tr + 1.5);
      reactionBlocks.push('between(t,' + tr.toFixed(2) + ',' + tEnd.toFixed(2) + ')');
    }
  });
}

// 3. Scan transcript for screaming / high energy audio tokens (ALL CAPS + exclamation)
if (wordData && wordData.length > 0) {
  wordData.forEach(w => {
    const text = String(w.word || "").trim();
    const clean = text.replace(/[^A-Za-z]/g, '');
    if (clean.length >= 3 && clean === clean.toUpperCase() && (DANGER_WORDS.has(clean) || text.includes('!'))) {
      const wStart = Math.max(0, parseFloat(w.start) || 0);
      const wEnd = Math.min(clipDur, Math.max(wStart + 1.2, (parseFloat(w.end) || 0) + 0.6));
      if (wStart < clipDur) {
        reactionBlocks.push('between(t,' + wStart.toFixed(2) + ',' + wEnd.toFixed(2) + ')');
      }
    }
  });
}

// Deduplicate and formulate reactionEnable
const reactionEnable = reactionBlocks.length > 0 ? reactionBlocks.slice(0, 5).join("+") : "0";

// ── Dynamic Multi-Beat Camera Motion ────────────────────────────────────
const climaxEnd = Math.min(clipDur, Math.round((climaxStart + 3.0) * 10) / 10);
const climaxEnable = 'between(t,' + climaxStart.toFixed(2) + ',' + climaxEnd.toFixed(2) + ')';

const hookEnd = Math.min(clipDur, 1.8);
const hookEnable = 'between(t,0,' + hookEnd.toFixed(2) + ')';
const camZoomEnable = climaxEnable;

// ── Non-Overlapping 3-Zone Vertical Layout ────────────────────────────────
// Zone 1: Persistent Top Hook Banner at y=75 (safe top zone, away from gameplay)
// Zone 2: Untouched Gameplay Action Zone (y=380 to y=820, zero text collisions)
// Zone 3: Dynamic Spoken Subtitles at y=880 (safe lower third, above YouTube/TikTok UI)
const subY = 880;
const captionY = 75;

let assContent = [
  '[Script Info]',
  'ScriptType: v4.00+',
  'PlayResX: 720',
  'PlayResY: 1280',
  '',
  '[V4+ Styles]',
  'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
  'Style: ViralSubs,Lilita One,' + FONT_SIZE + ',' + MAIN_COLOR + ',&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,2,20,20,10,1',
  'Style: ViralCaption,Lilita One,40,&H00D7FF&,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,2,20,20,10,1',
  '',
  '[Events]',
  'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
].join(NL) + NL;

// ── Semantic Phrase Grouping Subtitles with High-Impact Word Highlighting & Emojis ───
if (wordData.length > 0) {
  const SENTENCE_END_RE = /[.!?]$/;
  const groups = [];
  let current = [];

  for (let i = 0; i < wordData.length; i++) {
    const w = wordData[i];
    const word = String(w.word || "").trim();
    if (!word) continue;

    current.push(w);

    const currentChars = current.reduce((s, x) => s + String(x.word || "").length, 0);
    const nextW = wordData[i + 1];
    const gapToNext = nextW ? (nextW.start - w.end) : 9999;

    const hasMinWords = current.length >= 2;
    const isHardBreak = gapToNext > 0.60;
    const isSentenceEnd = SENTENCE_END_RE.test(word);

    const shouldBreak =
      current.length >= 4 ||
      currentChars >= 22 ||
      (hasMinWords && (isHardBreak || isSentenceEnd)) ||
      (i === wordData.length - 1);

    if (shouldBreak && current.length > 0) {
      if (current.length === 1 && i < wordData.length - 1 && gapToNext <= 0.60) {
        continue;
      }
      groups.push([...current]);
      current = [];
    }
  }
  if (current.length > 0) {
    if (groups.length > 0 && current.length === 1) {
      const prev = groups[groups.length - 1];
      if (prev.length < 4) {
        prev.push(current[0]);
      } else {
        groups.push(current);
      }
    } else {
      groups.push(current);
    }
  }

  // Active word-level highlighting with high-impact color highlights & contextual emojis
  for (const group of groups) {
    const cStart = group[0].start;
    const cEnd = group[group.length - 1].end;
    const displayEnd = cEnd;

    // Detect high-impact keyword & select contextual emoji
    let groupEmoji = "";
    for (const gw of group) {
      const cleanUpper = String(gw.word || "").toUpperCase().replace(/[^A-Z]/g, '');
      if (DANGER_WORDS.has(cleanUpper)) {
        groupEmoji = cleanUpper === "MONSTER" || cleanUpper === "BACKROOMS" ? " 😱" : " 💀";
        break;
      } else if (WIN_WORDS.has(cleanUpper)) {
        groupEmoji = " 🔥";
        break;
      } else if (SHOCK_WORDS.has(cleanUpper)) {
        groupEmoji = cleanUpper === "WAIT" ? " ⏳" : " 😂";
        break;
      }
    }

    for (let j = 0; j < group.length; j++) {
      const wStart = Math.max(cStart, group[j].start);
      const wEnd = j < group.length - 1 ? group[j + 1].start : displayEnd;

      const lineText = group.map((w, idx) => {
        const rawW = String(w.word || "").trim();
        const cleanUpper = rawW.toUpperCase().replace(/[^A-Z]/g, '');
        const txt = rawW.toUpperCase();

        if (idx === j) {
          // Dynamic high-impact color highlighting:
          let highlightColor = "&H00D7FF&"; // Ka-ching Gold
          let bounceTag = "\\t(0,40,\\fscx120\\fscy120)\\t(40,110,\\fscx100\\fscy100)";

          if (DANGER_WORDS.has(cleanUpper)) {
            highlightColor = "&H003333FF&"; // Vibrant Crimson/Red
            bounceTag = "\\t(0,45,\\fscx130\\fscy130)\\t(45,120,\\fscx100\\fscy100)";
          } else if (WIN_WORDS.has(cleanUpper)) {
            highlightColor = "&H0000FF55&"; // Electric Neon Green
            bounceTag = "\\t(0,45,\\fscx125\\fscy125)\\t(45,120,\\fscx100\\fscy100)";
          } else if (SHOCK_WORDS.has(cleanUpper)) {
            highlightColor = "&H00FFFF00&"; // Electric Cyan
            bounceTag = "\\t(0,45,\\fscx125\\fscy125)\\t(45,120,\\fscx100\\fscy100)";
          }

          return '{\\c' + highlightColor + bounceTag + '}' + txt + '{\\c' + MAIN_COLOR + '}';
        }
        return txt;
      }).join(" ") + (j === group.length - 1 ? groupEmoji : "");

      assContent += 'Dialogue: 1,' + formatTimeASS(wStart) + ',' + formatTimeASS(wEnd) + ',ViralSubs,,0,0,0,,{\\pos(360,' + subY + ')}' + lineText + NL;
    }
  }
}

// ── Hook Banner in Top Zone (y=75) ─────────────────────────────────────────
if (rawCaption) {
  const cleanCaption = rawCaption.replace(/[{}\\x27\\x22`]/g, '').trim().toUpperCase();
  const capStart = "0:00:00.00";
  const capEnd = formatTimeASS(clipDur);
  assContent += 'Dialogue: 2,' + capStart + ',' + capEnd + ',ViralCaption,,0,0,0,,{\\pos(360,' + captionY + ')}' + cleanCaption + NL;
}

// ── FFmpeg Filter Graph with Standardized 9:16 Vertical Stacking ──────────
const overlayGraph = remotionOverlayFile
  ? "[1:v]fade=in:st=0:d=0.25:alpha=1,fade=out:st=3.0:d=0.5:alpha=1[hook];[base][hook]overlay=0:0:enable='between(t,0,3.5)'[v_hook];[v_hook]ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v]"
  : "[base]ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v]";

// Offset vertical crop to bypass static avatar rows or follower goals
const gameYRatio = avatarRowDetected ? "0.20" : "0.10";

let filter = "";
if (isVertical) {
  filter = '[0:v]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2[base];' + overlayGraph;
} else if (hasCam) {
  // ZERO-GAP SPLIT SCREEN: Top Cam (720x380) [~30%] + Bottom Game (720x900) [~70%] = 1280, clean 4px divider at y=380
  const cwRatio = (camW / 1920).toFixed(4);
  const chRatio = (camH / 1080).toFixed(4);
  const cxRatio = (camX / 1920).toFixed(4);
  const cyRatio = (camY / 1080).toFixed(4);

  const bgPart = "[0:v]split=3[v_bg][v_game][v_cam];[v_bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:5[bg]";
  
  // Tightly cropped webcam centered on face/shoulders with 115% reaction punch zoom and 1.35x climax zoom
  const camPart = "[v_cam]crop=trunc(iw*" + cwRatio + "/2)*2:trunc(ih*" + chRatio + "/2)*2:trunc(iw*" + cxRatio + "/2)*2:trunc(ih*" + cyRatio + "/2)*2,split=2[c_fg_raw][c_bg_raw];" +
    "[c_bg_raw]scale=720:380:force_original_aspect_ratio=increase,crop=720:380,boxblur=25:5[c_bg_blur];" +
    "[c_fg_raw]scale=720:380:force_original_aspect_ratio=decrease[c_fit];" +
    "[c_bg_blur][c_fit]overlay=(W-w)/2:(H-h)/2,split=3[c_norm][c_react_src][c_punch_src];" +
    "[c_react_src]scale=trunc(720*1.15/2)*2:-1,crop=720:380:(iw-ow)/2:(ih-oh)/2[c_react];" +
    "[c_punch_src]scale=trunc(720*1.35/2)*2:-1,crop=720:380:(iw-ow)/2:(ih-oh)/2[c_punch];" +
    "[c_norm][c_react]overlay=0:0:enable='" + reactionEnable + "'[c_after_react];" +
    "[c_after_react][c_punch]overlay=0:0:enable='" + camZoomEnable + "'[c_final];" +
    "[c_final]drawbox=x=0:y=0:w=720:h=380:color=white:t=4[cam_bordered]";

  // Gameplay cropped to 720:900 with 10% vertical offset (or avatar bar bypass)
  // Stacked with 1.12x hook zoom, 1.15x reaction zoom, and 1.45x climax punch zoom
  const gamePart = "[v_game]crop='trunc(ih*0.85*(720/900)/2)*2':'trunc(ih*0.85/2)*2':(iw-ow)/2:'trunc(ih*0.10/2)*2'," +
    "scale=720:900:force_original_aspect_ratio=increase,crop=720:900:(iw-ow)/2:(ih-oh)/2,split=4[g_base][g_hk_src][g_react_src][g_cl_src];" +
    "[g_hk_src]scale=trunc(720*1.12/2)*2:-1,crop=720:900:(iw-ow)/2:(ih-oh)/2[g_hk];" +
    "[g_react_src]scale=trunc(720*1.15/2)*2:-1,crop=720:900:(iw-ow)/2:(ih-oh)/2[g_react];" +
    "[g_cl_src]scale=trunc(720*1.45/2)*2:-1,crop=720:900:(iw-ow)/2:(ih-oh)/2[g_cl];" +
    "[g_base][g_hk]overlay=0:0:enable='" + hookEnable + "'[g_after_hk];" +
    "[g_after_hk][g_react]overlay=0:0:enable='" + reactionEnable + "'[g_after_react];" +
    "[g_after_react][g_cl]overlay=0:0:enable='" + climaxEnable + "'[g_final];" +
    "[g_final]drawbox=x=0:y=0:w=720:h=900:color=white:t=4[game_bordered]";

  const overlayPart = "[bg][cam_bordered]overlay=0:0[bg2];[bg2][game_bordered]overlay=0:380[base_raw];[base_raw]drawbox=x=0:y=378:w=720:h=4:color=white:t=fill[base];" + overlayGraph;
  filter = bgPart + ";" + camPart + ";" + gamePart + ";" + overlayPart;
} else {
  // FULL SCREEN GAMEPLAY NO-CAM: 720x1280 frame with top HUD/follower goal bypass, 1.15x reaction zoom & 1.45x punch zoom
  const gamePart = "[0:v]crop='trunc(ih*0.86*(720/1280)/2)*2':'trunc(ih*0.86/2)*2':(iw-ow)/2:'trunc(ih*0.11/2)*2'," +
    "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2:(ih-oh)/2,split=4[g_base][g_hk_src][g_react_src][g_cl_src];" +
    "[g_hk_src]scale=trunc(720*1.12/2)*2:-1,crop=720:1280:(iw-ow)/2:(ih-oh)/2[g_hk];" +
    "[g_react_src]scale=trunc(720*1.15/2)*2:-1,crop=720:1280:(iw-ow)/2:(ih-oh)/2[g_react];" +
    "[g_cl_src]scale=trunc(720*1.45/2)*2:-1,crop=720:1280:(iw-ow)/2:(ih-oh)/2[g_cl];" +
    "[g_base][g_hk]overlay=0:0:enable='" + hookEnable + "'[g_after_hk];" +
    "[g_after_hk][g_react]overlay=0:0:enable='" + reactionEnable + "'[g_after_react];" +
    "[g_after_react][g_cl]overlay=0:0:enable='" + climaxEnable + "'[base];";
  filter = gamePart + overlayGraph;
}

const title = (clipData.title || "output_clip").replace(/[\/\\"'<>|&;:]/g, '_').trim();
const outputFile = "/files/outputs/" + title + ".mp4";
const extraInputs = overlayInput ? (' ' + overlayInput) : "";

const cmd = 'ffmpeg -loglevel error -y -i "/files/temp/concatenated_clip.mp4"' + extraInputs + (audioInputs.length > 0 ? (' ' + audioInputs.join(" ")) : "") + ' -filter_complex "' + filter + ';' + audioMixFilter + '" -map "[v]" -map "[a_out]" -c:v libx264 -preset medium -crf 18 -c:a aac "' + outputFile + '"';

try {
  const fs = require('fs');
  if (!fs.existsSync('/files/temp')) fs.mkdirSync('/files/temp', { recursive: true });
  fs.writeFileSync('/files/temp/subs.ass', assContent, 'utf-8');
} catch(e) {}

return [{json: {command: cmd}, binary: {data: {data: Buffer.from(assContent).toString('base64'), mimeType: 'text/plain', fileName: 'subs.ass'}}}];
`,
    };

    @node({
        id: '6ef14988-e91f-4925-bd17-9b03634f100b',
        name: 'Read/Write Files from Disk',
        type: 'n8n-nodes-base.readWriteFile',
        version: 1,
        position: [-81840, 26340],
    })
    ReadWriteFilesFromDisk = {
        operation: 'write',
        fileName: '=/files/temp/{{ $binary.data.fileName }}',
        options: {},
    };

    @node({
        id: 'ea22bd11-71d2-4a29-b240-6e76b5b911d4',
        name: '7f. Final Render',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-81640, 26640],
    })
    _7fFinalRender = {
        command: '={{ $json.command }}',
    };

    @node({
        id: 'f6edf73b-369d-4de4-b6ec-f8e5cc7539df',
        name: 'Delete Source VOD',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-85280, 26080],
    })
    DeleteSourceVod = {
        command: '=rm -f "/files/inputs/{{ $(\'Edit Fields\').first().json.stream_file }}"',
    };

    @node({
        id: '5959dc03-cb5a-4dde-bc83-8537352e890a',
        name: 'Get Reference Frame',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-96200, 26100],
    })
    GetReferenceFrame = {
        command:
            '=rm -f /files/temp/ref_*.jpg /files/temp/cam_config.json /files/temp/cam_ref_grid.jpg; file="/files/inputs/{{ $(\'Edit Fields\').first().json.stream_file }}"; ffmpeg -loglevel error -y -ss 00:03:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/ref_1.jpg" || true; ffmpeg -loglevel error -y -ss 00:07:30 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/ref_2.jpg" || true; ffmpeg -loglevel error -y -ss 00:12:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/ref_3.jpg" || true; ffmpeg -loglevel error -y -ss 00:16:30 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/ref_4.jpg" || true; ffmpeg -loglevel error -y -ss 00:21:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/ref_5.jpg" || true; python3 /files/cam_detector.py "/files/temp/ref_*.jpg" "/files/temp/cam_config.json" "$file"',
    };

    @node({
        id: 'dc7ef757-3107-45a3-b001-7a42944b1ed4',
        name: '1. Global Summary AI',
        type: '@n8n/n8n-nodes-langchain.agent',
        version: 1.7,
        position: [-90820, 25700],
        onError: 'continueErrorOutput',
    })
    _1GlobalSummaryAi = {
        promptType: 'define',
        text: "={{ $('3. Groq Whisper').first().json.text ? $('3. Groq Whisper').first().json.text.substring(0,40000) : '' }}",
        options: {
            systemMessage: `You are the Lead Narrative Director for a top gaming creator. Your task is to analyze the entire VOD transcript and provide a profound, hallucination-free Global Summary.

TASK:
1. Identify the specific Game being played.
2. Summarize the overarching narrative/goal of the entire VOD in 3-4 sentences.
3. Define the precise "Vibe" (e.g., Chaotic, Educational, Story-driven).
4. Extract key recurring themes or inside jokes.

OUTPUT JSON FORMAT EXACTLY AND ONLY JSON. NO MARKDOWN:
{
  "game": "Name of Game",
  "global_summary": "Streamer is trying to...",
  "vibe": "High-energy rage",
  "key_themes": ["dying to fall damage", "lag complaining"]
}`,
        },
    };

    @node({
        id: '270b118f-cf07-4559-9922-5de2171f0fab',
        name: 'Gemini Model 1',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-90820, 25920],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiModel1 = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.1,
        },
    };

    @node({
        id: '045c2797-5d88-4dfa-ab22-e3c76242a114',
        name: 'Context Merge Agent',
        type: '@n8n/n8n-nodes-langchain.agent',
        version: 1.7,
        position: [-83880, 26240],
        onError: 'continueErrorOutput',
    })
    ContextMergeAgent = {
        promptType: 'define',
        text: `PROPOSED HOOK BANNER FROM DIRECTOR:
{{ $('Loop Clips').item.json.hook_caption || $('Loop Clips').item.json.title }}

CLIP TITLE:
{{ $('Loop Clips').item.json.title }}

CLIP THEME:
{{ $('Loop Clips').item.json.theme }}

AVAILABLE SOUNDS (pick from these exact filenames):
{{ $('Get Meme List').first().json.stdout ? $('Get Meme List').first().json.stdout.replace(/\\n/g, ', ') : 'vine-boom-sound-effect_KT89XIq.mp3, huh_37bAoRo.mp3, fartmeme.mp3' }}

FULL TIMECODED TRANSCRIPT OF THE CLIP (read every word before placing ANY effects):
{{ (function(){ const w=$('7d. Get Subtitles (SRT)').first().json.words; return w&&w.length>0?w.map(x=>'['+x.start.toFixed(1)+'s] '+x.word).join(' '):'NO WORDS'; })() }}`,
        options: {
            systemMessage: `You are an Elite YouTube Shorts Editor & Sound Designer.
You have the Director's PROPOSED HOOK BANNER and the full timecoded transcript below.

YOUR JOB — output ONLY raw JSON with these 4 fields:

1. STORY HOOK (Top Banner, 3-5 punchy words in ALL CAPS)
• PRIMARY DIRECTIVE: Keep the Director's PROPOSED HOOK BANNER as your story_hook UNLESS you can make it punchier while staying 100% FACTUAL to the spoken transcript.
• CRITICAL ANTI-HALLUCINATION RULE: NEVER invent hackers, scams, or teams if they are not explicitly spoken in the transcript! No generic clickbait (e.g. NEVER output "THE HACKER EXPOSED" or "SAVING THE WHOLE TEAM" unless those exact events occurred).
• Examples: "I CALLED TIME OUT", "THAT DOES NOT COUNT", "HE ACTUALLY FELL FOR IT", "MY WORST BLUNDER".

2. CLIMAX QUOTE (Exact 3 to 5 words spoken at the peak moment)
• Find the EXACT 3-5 words spoken at the highest-energy punchline, arrest, scream, jumpscare, or reaction in the transcript.
• Example: "bro you arrested me" or "no way you pulled that" or "why did you do that".
• This anchors our visual punch-in zoom to the exact spoken climax audio.

3. REACTION & AUDIO-ENERGY TRIGGERS
• List of timestamps where the streamer screams, yells, or gets killed in-game (screams_or_reactions).
• These command FFmpeg to scale up the gameplay or webcam by 115% for an aggressive, punchy zoom.

4. MEMES (0 TO 2 SOUNDS MAXIMUM)
• Natural audio is preferred! If dialogue is already clear and funny, return: "memes": []
• Only pick a sound effect if there is an explicit comedic blunder, sudden roast, jumpscare, or awkward shock:
  - vine-boom-sound-effect_KT89XIq.mp3 -> Heavy impact, roast landing, sudden plot twist.
  - huh_37bAoRo.mp3 -> Total confusion, bewildered reaction, awkward silence.
  - fartmeme.mp3 -> Slapstick fail, dying to a silly trap.
• Volume: 0.35.

Output ONLY valid raw JSON:
{
  "story_hook": "I CALLED TIME OUT",
  "climax_quote": "bro you arrested me",
  "reaction_triggers": [14.2],
  "memes": []
}`,
        },
    };

    @node({
        id: '2171d8ca-8886-4c5b-863a-fb15821c2619',
        name: 'Gemini Model 2',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-83900, 26440],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiModel2 = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.2,
        },
    };

    @node({
        id: '8f4fbd18-625b-4f48-8c0a-e0e771cf59ef',
        name: 'Prepare Frames',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-95940, 26120],
    })
    PrepareFrames = {
        jsCode: `const files = $input.first().json.stdout.trim().split('\\n').filter(f => f.length > 3);
if(files.length===0) return [{json:{file:"/files/temp/ref_frame.jpg"}}];
return files.map(f => ({ json: { file: f } }));`,
    };

    @node({
        id: 'f98462bc-7b70-4aae-9479-4047b773f86b',
        name: 'IF: Summary OK?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-89540, 25800],
    })
    IfSummaryOk = {
        conditions: {
            options: {
                caseSensitive: true,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ !!$json.output }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'true',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '9e74015d-4297-45ec-9e9a-6cdd63ba6aae',
        name: '1. Global Summary Fallback',
        type: '@n8n/n8n-nodes-langchain.agent',
        version: 1.7,
        position: [-89400, 26160],
        onError: 'continueErrorOutput',
    })
    _1GlobalSummaryFallback = {
        promptType: 'define',
        text: "={{ $('3. Groq Whisper').first().json.text ? $('3. Groq Whisper').first().json.text.substring(0,40000) : '' }}",
        options: {
            systemMessage: `You are the Lead Narrative Director for a top gaming creator. Your task is to analyze the entire VOD transcript and provide a profound, hallucination-free Global Summary.

TASK:
1. Identify the specific Game being played.
2. Summarize the overarching narrative/goal of the entire VOD in 3-4 sentences.
3. Define the precise "Vibe" (e.g., Chaotic, Educational, Story-driven).
4. Extract key recurring themes or inside jokes.

OUTPUT JSON FORMAT EXACTLY AND ONLY JSON. NO MARKDOWN:
{
  "game": "Name of Game",
  "global_summary": "Streamer is trying to...",
  "vibe": "High-energy rage",
  "key_themes": ["dying to fall damage", "lag complaining"]
}`,
        },
    };

    @node({
        id: '5d708cdf-058b-4dff-a7c3-fe6f77de9fab',
        name: 'Gemini Backup Model 1',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-89380, 26400],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiBackupModel1 = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.1,
        },
    };

    @node({
        id: 'a696a584-e58c-432c-9f1c-97bef4601551',
        name: 'IF: Merge OK?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-83500, 26120],
    })
    IfMergeOk = {
        conditions: {
            options: {
                caseSensitive: true,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ !!$json.output }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'true',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '4b6ab954-b58a-4134-b1ea-9b83bebbc7b9',
        name: 'Context Merge Fallback',
        type: '@n8n/n8n-nodes-langchain.agent',
        version: 1.7,
        position: [-82960, 26360],
        onError: 'continueErrorOutput',
    })
    ContextMergeFallback = {
        promptType: 'define',
        text: `PROPOSED HOOK BANNER FROM DIRECTOR:
{{ $('Loop Clips').item.json.hook_caption || $('Loop Clips').item.json.title }}

CLIP TITLE:
{{ $('Loop Clips').item.json.title }}

CLIP THEME:
{{ $('Loop Clips').item.json.theme }}

AVAILABLE SOUNDS (pick from these exact filenames):
{{ $('Get Meme List').first().json.stdout ? $('Get Meme List').first().json.stdout.replace(/\\n/g, ', ') : 'vine-boom-sound-effect_KT89XIq.mp3, huh_37bAoRo.mp3, fartmeme.mp3' }}

FULL TIMECODED TRANSCRIPT OF THE CLIP (read every word before placing ANY effects):
{{ (function(){ const w=$('7d. Get Subtitles (SRT)').first().json.words; return w&&w.length>0?w.map(x=>'['+x.start.toFixed(1)+'s] '+x.word).join(' '):'NO WORDS'; })() }}`,
        options: {
            systemMessage: `You are an Elite YouTube Shorts Editor & Sound Designer.
You have the Director's PROPOSED HOOK BANNER and the full timecoded transcript below.

YOUR JOB — output ONLY raw JSON with these 4 fields:

1. STORY HOOK (Top Banner, 3-5 punchy words in ALL CAPS)
• PRIMARY DIRECTIVE: Keep the Director's PROPOSED HOOK BANNER as your story_hook UNLESS you can make it punchier while staying 100% FACTUAL to the spoken transcript.
• CRITICAL ANTI-HALLUCINATION RULE: NEVER invent hackers, scams, or teams if they are not explicitly spoken in the transcript! No generic clickbait (e.g. NEVER output "THE HACKER EXPOSED" or "SAVING THE WHOLE TEAM" unless those exact events occurred).
• Examples: "I CALLED TIME OUT", "THAT DOES NOT COUNT", "HE ACTUALLY FELL FOR IT", "MY WORST BLUNDER".

2. CLIMAX QUOTE (Exact 3 to 5 words spoken at the peak moment)
• Find the EXACT 3-5 words spoken at the highest-energy punchline, arrest, scream, jumpscare, or reaction in the transcript.
• Example: "bro you arrested me" or "no way you pulled that" or "why did you do that".
• This anchors our visual punch-in zoom to the exact spoken climax audio.

3. REACTION & AUDIO-ENERGY TRIGGERS
• List of timestamps where the streamer screams, yells, or gets killed in-game (screams_or_reactions).
• These command FFmpeg to scale up the gameplay or webcam by 115% for an aggressive, punchy zoom.

4. MEMES (0 TO 2 SOUNDS MAXIMUM)
• Natural audio is preferred! If dialogue is already clear and funny, return: "memes": []
• Only pick a sound effect if there is an explicit comedic blunder, sudden roast, jumpscare, or awkward shock:
  - vine-boom-sound-effect_KT89XIq.mp3 -> Heavy impact, roast landing, sudden plot twist.
  - huh_37bAoRo.mp3 -> Total confusion, bewildered reaction, awkward silence.
  - fartmeme.mp3 -> Slapstick fail, dying to a silly trap.
• Volume: 0.35.

Output ONLY valid raw JSON:
{
  "story_hook": "I CALLED TIME OUT",
  "climax_quote": "bro you arrested me",
  "reaction_triggers": [14.2],
  "memes": []
}`,
        },
    };

    @node({
        id: '13b45eaf-4cb8-4ea8-a9ab-63655445afab',
        name: 'Gemini Backup Model 3',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-82920, 26500],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiBackupModel3 = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.2,
        },
    };

    @node({
        id: '5fc97116-6695-403a-9335-e9bd4a654b01',
        name: '3. Groq Whisper Fallback',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [-90980, 25700],
        credentials: { groqApi: { id: 'PF1ZMT03O2E5waqU', name: 'Groq account 2' } },
        retryOnFail: true,
        maxTries: 4,
        waitBetweenTries: 5000,
    })
    _3GroqWhisperFallback = {
        method: 'POST',
        url: 'https://api.groq.com/openai/v1/audio/transcriptions',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'groqApi',
        sendBody: true,
        contentType: 'multipart-form-data',
        bodyParameters: {
            parameters: [
                {
                    name: 'model',
                    value: 'whisper-large-v3-turbo',
                },
                {
                    parameterType: 'formBinaryData',
                    name: 'file',
                    inputDataFieldName: 'data',
                },
                {
                    name: 'response_format',
                    value: 'verbose_json',
                },
                {
                    name: 'timestamp_granularities[]',
                    value: 'word',
                },
                {
                    name: 'prompt',
                    value: 'Roblox gaming, Lucky Blocks, Divine Mutation, Strawberry Elephant, Taco Combinacion, 10x Luck, streamer reacting, gaming chaos.',
                },
            ],
        },
        options: {
            timeout: 300000,
        },
    };

    @node({
        id: 'ba963f8a-b5d6-40f1-afa0-e722995b2584',
        name: 'IF: Whisper OK?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-92200, 25940],
    })
    IfWhisperOk = {
        conditions: {
            options: {
                caseSensitive: true,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: "={{ $json.text ? 'ok' : '' }}",
                    rightValue: 'ok',
                    operator: {
                        type: 'string',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'ca072c3b-c487-433c-9986-27a57a6578bd',
        webhookId: '017cc4b5-fe1d-4c08-ae5a-1e794a91d20f',
        name: 'Wait Before Fallback',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-91700, 26000],
    })
    WaitBeforeFallback = {
        unit: 'minutes',
    };

    @node({
        id: '0bb9ce26-5ec5-49cc-b1f9-71e023d0c916',
        name: 'Read Audio For Fallback',
        type: 'n8n-nodes-base.readBinaryFile',
        version: 1,
        position: [-91500, 26000],
    })
    ReadAudioForFallback = {
        filePath: '/files/temp/audio.mp3',
    };

    @node({
        id: 'd7ccb05d-cddd-43bd-9178-85d70aea5672',
        name: '1. Prepare Scout Prompt',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-88480, 26120],
    })
    _1PrepareScoutPrompt = {
        jsCode: `const fs = require('fs');
let whisperData = null;

try {
  const items = $input.all();
  if (items && items[0] && items[0].json && (items[0].json.text || (items[0].json.annotated_sentences && items[0].json.annotated_sentences.length))) {
    whisperData = items[0].json;
  }
} catch(e) {}

if (!whisperData) {
  try {
    const lct = $('Load Cached Telemetry').first().json;
    if (lct && (lct.text || (lct.words && lct.words.length))) whisperData = lct;
  } catch(e) {}
}
if (!whisperData) {
  try {
    const w = $('3. Groq Whisper').first().json;
    if (w && w.text && w.text.length > 10) whisperData = w;
  } catch(e) {}
}
if (!whisperData) {
  try {
    const w2 = $('3. Groq Whisper Fallback').first().json;
    if (w2 && w2.text && w2.text.length > 10) whisperData = w2;
  } catch(e) {}
}

if (!whisperData || (!whisperData.text && !(whisperData.annotated_sentences && whisperData.annotated_sentences.length))) {
    throw new Error('CRITICAL ERROR: Transcript text is missing. Run Whisper node or Load Cached Telemetry first.');
}

const isDryRun = Boolean(whisperData.dry_run);
const rawText = whisperData.text || '';
const durationMinutes = (whisperData.duration || 1800) / 60;

// Load Unified Multimodal Timeline Index (disk fallback for both Production and Sandbox)
let indexDoc = null;
if (fs.existsSync('/files/temp/unified_timeline_index.json')) {
  try {
    indexDoc = JSON.parse(fs.readFileSync('/files/temp/unified_timeline_index.json', 'utf8'));
  } catch(e) {}
}

// Use pre-annotated cadence/telemetry sentences when available, otherwise build from Whisper words
let annotatedSentences = whisperData.annotated_sentences || (indexDoc && indexDoc.annotated_sentences) || [];
let whisperWords = whisperData.words || (whisperData.x_groq && whisperData.x_groq.words) || [];

// Filter Whisper prompt hallucinations (repeated intro music loops)
const isHallucination = (txt) => {
  const low = String(txt || '').toLowerCase();
  const keys = ['roblox gaming', 'lucky blocks', 'divine mutation', '10x luck', 'streamer reacting', 'gaming chaos'];
  const hits = keys.filter(k => low.includes(k)).length;
  return hits >= 2;
};

let sentences = [];
if (annotatedSentences.length > 0) {
  sentences = annotatedSentences.map(s => \`[\${Number(s.start).toFixed(1)}s - \${Number(s.end).toFixed(1)}s]\${(s.tags && s.tags.length) ? ' ' + s.tags.join(' ') : ''} \${s.text}\`);
} else {
  let currSentence = "";
  let currStart = -1;
  let currEnd = -1;
  for (let w of whisperWords) {
    if (currStart === -1) currStart = w.start;
    currSentence += w.word;
    currEnd = w.end;
    if (/[.!?]$/.test(w.word.trim())) {
      if (!isHallucination(currSentence)) {
        sentences.push(\`[\${currStart.toFixed(1)}s - \${currEnd.toFixed(1)}s] \${currSentence.trim()}\`);
      }
      currSentence = "";
      currStart = -1;
    }
  }
  if (currSentence && !isHallucination(currSentence)) {
    sentences.push(\`[\${currStart.toFixed(1)}s - \${currEnd.toFixed(1)}s] \${currSentence.trim()}\`);
  }
}

const numberedLines = sentences.length > 0 ? sentences : (rawText.match(/[^.!?]+[.!?]+/g) || [rawText]).map((s, i) => '[L' + (i+1) + '] ' + s.trim());

// Multimodal Viral Anchors Extraction
let viralAnchors = whisperData.anchors || [];
if (viralAnchors.length === 0) {
  try {
    const fusionItem = $('Run Multimodal Fusion').first();
    if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
      const parsed = JSON.parse(fusionItem.json.stdout);
      if (parsed && parsed.anchors && parsed.anchors.length > 0) {
        viralAnchors = parsed.anchors;
      }
    }
  } catch(e) {}
}
if (viralAnchors.length === 0 && indexDoc && indexDoc.anchors) {
  viralAnchors = indexDoc.anchors;
}

const macroTimeline = whisperData.macro_high_signal_timeline || (indexDoc && indexDoc.macro_high_signal_timeline) || '';

let multimodalHeader = "";
if (viralAnchors.length > 0) {
  multimodalHeader = "\n=== [PROVEN MULTIMODAL VIRAL PEAKS (AUDIENCE CHAT, FACECAM & VOCAL ENERGY)] ===\n" +
    "The following moments across the full 1+ hour VOD have been empirically pre-verified by live chat velocity bursts (LMAO, 💀, WTF), streamer face reactions (laughter/shock), vocal dB spikes, and WPM bursts.\n" +
    "YOU MUST PRIORITIZE SELECTING MOMENTS AROUND THESE PROVEN PEAKS AND LINKING LONG-RANGE CALLBACKS ACROSS THE STREAM:\n\n";

  for (let a of viralAnchors.slice(0, 18)) {
    multimodalHeader += \`• [ANCHOR #\${a.anchor_id}] [\${a.start}s - \${a.end}s] (Peak at \${a.peak_time}s | Score: \${a.virality_score}/100 | Fit: \${a.recommended_archetype || 'NARRATIVE'})\n\` +
      \`  - Audience Chat: \${a.chat_signal}\n\` +
      \`  - Streamer Facecam: \${a.face_signal}\n\` +
      \`  - Audio Energy: \${a.audio_signal}\n\` +
      (a.why_chat_laughed ? \`  - Why Chat Laughed: \${a.why_chat_laughed}\n\` : '') +
      (a.comedy_mechanism ? \`  - Comedic Catalyst: \${a.comedy_mechanism}\n\` : '') +
      (a.setup_tension_hook ? \`  - Setup Tension Hook (In-Media-Res): \${a.setup_tension_hook}\n\` : '') +
      (a.callback_links && a.callback_links.length ? \`  - Cross-Stream Callback Links: \${a.callback_links.map(cb => cb.tc + ' ("' + cb.keyword + '"): ' + cb.text).join(' | ')}\n\` : '') +
      (a.is_multi_beat && a.beat_2 ? \`  - Compound Multi-Beat Callback: Beat 2 at \${a.beat_2.peak_time}s ("it happened again")\n\` : '') +
      (a.recommended_structure ? \`  - Recommended Arc: \${a.recommended_structure}\n\` : '') +
      (a.transcript_snippet ? \`  - Transcript Preview: "\${a.transcript_snippet.substring(0, 180)}"\n\` : '') +
      \`\n\`;
  }
}

// In Sandbox mode, run a single fast macro pass so <10s iteration completes cleanly without 2-minute waits
let numChunks = isDryRun ? 1 : Math.min(4, Math.max(1, Math.round(durationMinutes / 7.5)));
const linesPerChunk = Math.ceil(numberedLines.length / numChunks);
const overlap = 10;
const MAX_CHUNK_CHARS = isDryRun ? 16000 : 10000;

const results = [];
for (let i = 0; i < numChunks; i++) {
  let chunkText = '';
  if (isDryRun && macroTimeline) {
    chunkText = "=== HIGH-SIGNAL ANNOTATED TIMELINE ACROSS FULL VOD ===\n" + macroTimeline.substring(0, 10000) +
      "\n\n=== SAMPLED RAW SENTENCE CONTEXT ===\n" + numberedLines.slice(0, 180).join('\n').substring(0, 6000);
  } else {
    const start = Math.max(0, i * linesPerChunk - overlap);
    const end = Math.min(numberedLines.length, (i + 1) * linesPerChunk + overlap);
    chunkText = numberedLines.slice(start, end).join('\n');
    if (chunkText.length > MAX_CHUNK_CHARS) {
      chunkText = chunkText.substring(0, MAX_CHUNK_CHARS) + '\n[... chunk trimmed to fit token limit ...]';
    }
  }

  const prompt =
    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout. Read the multimodal transcript index and identify the top 4 most explosive, high-retention gaming moments.\n\n' +
    (multimodalHeader ? multimodalHeader + '\n' : '') +
    '=== CRITICAL ANTI-ADMIN, ANTI-IDLE & ANTI-BROWSER FILTER ===\n' +
    'The streamer frequently Alt-Tabs out of Roblox into Chrome, Notepad, or OBS, or idles between matches. You MUST REJECT any segments containing:\n' +
    '• Typing player usernames into search bars, accepting friend requests on the Roblox website, Discord DMs, or settings.\n' +
    '• Reading long lists of $3 donations or subscriber names while idling in menus ([STRICT ANTI-CONVERSATIONAL BANTER & DONATION AFTERMATH]).\n' +
    '• [STRICT ANTI-IDLE & ANTI-STATIC]: REJECT segments where the character is standing still in a lobby waiting for a match, reading chat idly, or staring at a wall!\n' +
    '• [STRICT ANTI-LOADING SCREEN]: NEVER start a clip at [0.0s - 3.0s] or on intro music/loading screens.\n' +
    '• [STRICT ANTI-SLOW-UI & TRADE MENUS]: REJECT segments where the streamer spends 10+ seconds clicking buttons inside inventory/trade UI panels.\n' +
    '• [STRICT ANTI-GRIND & ANTI-FARMING]: REJECT repetitive grinding, farming coins/potatoes, or boring waiting.\n\n' +
    '=== VIRAL NARRATIVE ARCHITECTURES & RETENTION RULES ===\n' +
    'Evaluate candidates against these 5 Viral Shorts Models:\n' +
    '1. IN_MEDIA_RES_FLASHFORWARD (Peak shock/scream cut 0.3s before punchline -> rewind to confident setup -> full payoff)\n' +
    '2. DOUBLE_DOWN_ESCALATION (Boast/Fail 1 -> jump cut past dead air (+10s or minutes later) -> Double Down -> Bigger Fail 2)\n' +
    '3. HUBRIS_INSTANT_KARMA (Arrogant boast -> 0.5s beat -> instant collapse + stunned reaction)\n' +
    '4. MYSTERY_OPEN_LOOP (Weird anomaly/question -> tight chronological clues -> twist reveal)\n' +
    '5. REVERSE_PAYOFF_LOOP (Final sentence flows seamlessly back into 0:00 opening line)\n\n' +
    '• [ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE]: REJECT clips that start mid-thought or with casual filler ("Speaking of...", "Um...").\n' +
    '• [CAUSE-EFFECT NARRATIVE THROUGH-LINE & ANTI-CHAOS]: Every candidate MUST pair a clear setup/boast/context (even if 15m earlier) with its comedic/intense payoff.\n' +
    '• ZERO IRRELEVANT PREAMBLE: Start directly at the catalyst or setup.\n' +
    '• [SATISFYING CLIMAX ONLY]: Climax must deliver clear visual/emotional impact followed by strictly 2.0-3.5s of aftermath. NEVER cut mid-word!\n\n' +
    'OUTPUT: Plain text only. For each of the moments, provide:\n' +
    '- Tag & Recommended Archetype: [TAG NAME] | Archetype: [ONE OF THE 5 MODELS]\n' +
    '- Hook/Climax Tease Timestamp: [X.Xs - Y.Ys] (cut 0.3s before final punchline for flashforward)\n' +
    '- Causal Setup Timestamp(s): [X.Xs - Y.Ys] (can be earlier in the VOD for cold-viewer context)\n' +
    '- Payoff / Escalation Timestamp(s): [X.Xs - Y.Ys]\n' +
    '- Multimodal Signal Drivers: (Chat Z-score, dB spike, Emotion, WPM)\n' +
    '- Exact Quotes for Hook, Setup & Payoff\n\n' +
    '--- CHUNK ' + (i+1) + '/' + numChunks + ' ---\n' +
    chunkText;

  results.push({ json: { prompt, chunk_index: i+1, dry_run: isDryRun } });
}

return results;`,
    };

    @node({
        id: '235ad0b2-bf2d-4feb-8cd2-2148eb3678bb',
        name: 'Gemini Model (Scout)',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-87680, 26580],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiModelScout = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.4,
        },
    };

    @node({
        id: '7103ac68-8941-45ad-b8e2-316fc5da376a',
        name: '2. Basic LLM Chain (Scout)',
        type: '@n8n/n8n-nodes-langchain.chainLlm',
        version: 1.4,
        position: [-87700, 26380],
        onError: 'continueErrorOutput',
    })
    _2BasicLlmChainScout = {
        promptType: 'define',
        text: '={{ $json.prompt }}',
    };

    @node({
        id: 'scout-loop',
        name: 'Scout Loop',
        type: 'n8n-nodes-base.splitInBatches',
        version: 3,
        position: [-88080, 26240],
    })
    ScoutLoop = {
        options: {},
    };

    @node({
        id: 'scout-wait',
        webhookId: '2f6fc711-3d06-4fc7-b26e-cda2f33f745a',
        name: 'Scout Wait',
        type: 'n8n-nodes-base.wait',
        version: 1,
        position: [-87880, 26360],
    })
    ScoutWait = {
        amount: 2,
        unit: 'minutes',
    };

    @node({
        id: 'scout-accumulate',
        name: 'Scout Accumulate',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-86660, 26120],
    })
    ScoutAccumulate = {
        jsCode: `const allItems = [];
let runIdx = 0;
while (true) {
  try {
    const items = $items("2. Basic LLM Chain (Scout)", 0, runIdx);
    if (!items || items.length === 0) break;
    allItems.push(...items);
    runIdx++;
  } catch (e) {
    break;
  }
}
const out = allItems.length > 0 ? allItems : $items("2. Basic LLM Chain (Scout)");
let isDryRun = false;
try { isDryRun = Boolean($('1. Prepare Scout Prompt').first().json.dry_run); } catch(e) {}
return out.map(it => ({ json: { ...it.json, dry_run: isDryRun } }));`,
    };

    @node({
        id: '59c847f1-0354-4acd-9aef-3c3bea58643b',
        name: '3. Prepare Director Prompt',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-86500, 26120],
    })
    _3PrepareDirectorPrompt = {
        jsCode: `const fs = require('fs');
const items = $input.all();
let allSnippets = "";

items.forEach((item, index) => {
  allSnippets += \`\n\n=== SCOUTED MOMENTS CHUNK \${index + 1} ===\n\`;
  allSnippets += item.json.text || item.json.output || "";
});

let isDryRun = items.some(it => Boolean(it.json && it.json.dry_run));
if (!isDryRun) {
  try { isDryRun = Boolean($('1. Prepare Scout Prompt').first().json.dry_run); } catch(e) {}
}

// Pull Proven Multimodal Anchors (with disk fallback for <10s Sandbox runs)
let anchorsList = [];
try {
  const fusionItem = $('Run Multimodal Fusion').first();
  if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
    const parsed = JSON.parse(fusionItem.json.stdout);
    if (parsed && parsed.anchors) anchorsList = parsed.anchors;
  }
} catch(e) {}

if (anchorsList.length === 0) {
  try {
    const lct = $('Load Cached Telemetry').first().json;
    if (lct && lct.anchors) anchorsList = lct.anchors;
  } catch(e) {}
}
if (anchorsList.length === 0 && fs.existsSync('/files/temp/unified_timeline_index.json')) {
  try {
    const idx = JSON.parse(fs.readFileSync('/files/temp/unified_timeline_index.json', 'utf8'));
    if (idx && idx.anchors) anchorsList = idx.anchors;
  } catch(e) {}
}

let viralContext = "";
if (anchorsList.length > 0) {
  viralContext = "\n=== PROVEN AUDIENCE & REACTION ANCHORS ===\n" +
    anchorsList.slice(0, 18).map(a => \`[ANCHOR #\${a.anchor_id}] Peak at \${a.peak_time}s (\${a.peak_tc || ''}) | Score: \${a.virality_score}/100 | Model Fit: \${a.recommended_archetype || a.comedy_mechanism || 'Comedy'}\n\` +
      \`  - Audio: \${a.audio_signal || ''} | Chat: \${a.chat_signal || ''} | Face: \${a.face_signal || ''}\n\` +
      (a.why_chat_laughed ? \`  - Why They Laughed: \${a.why_chat_laughed}\n\` : '') +
      (a.setup_tension_hook ? \`  - Tension Hook: \${a.setup_tension_hook}\n\` : '') +
      (a.callback_links && a.callback_links.length ? \`  - Callback Candidates: \${a.callback_links.map(cb => cb.time + 's ("' + cb.keyword + '"): ' + cb.text).join(' | ')}\n\` : '') +
      (a.is_multi_beat && a.beat_2 ? \`  - Multi-Beat Callback: Beat 2 at \${a.beat_2.peak_time}s\n\` : '') +
      (a.annotated_context ? \`  - Exact Float-Second Context: \${String(a.annotated_context).substring(0, 600).replace(/\\n/g, ' | ')}\n\` : '')
    ).join("\n") + "\n";
}

let streamContext = "";
try {
  const summaryRaw = $('1. Global Summary AI').first().json.output || $('1. Global Summary Fallback').first().json.output || "{}";
  const summary = JSON.parse(summaryRaw.replace(/\`\`\`json/gi,'').replace(/\`\`\`/g,'').trim());
  streamContext = [
    summary.game ? "GAME: " + summary.game : "",
    summary.global_summary ? "STREAM SUMMARY: " + summary.global_summary : "",
    summary.vibe ? "VIBE: " + summary.vibe : "",
    (summary.key_themes && summary.key_themes.length) ? "KEY THEMES: " + summary.key_themes.join(", ") : ""
  ].filter(Boolean).join("\n");
} catch(e) {}

const targetClips = 5;

const jsonSchema = '{"clips":[{"clip_number":1,"narrative_archetype":"IN_MEDIA_RES_FLASHFORWARD","estimated_vod_segment":"X-Y minutes","title":"3-4 Word Curiosity Teaser 💀","hook_caption":"3-5 WORDS IN ALL CAPS","theme":"Core viral theme","structure_type":"Flash-Forward","start_time":105.2,"end_time":142.0,"payoff_time":138.5,"cold_open_start":137.0,"cold_open_end":138.6,"segments":[{"start":137.0,"end":138.6,"role":"HOOK_CLIMAX"},{"start":105.2,"end":116.5,"role":"SETUP"},{"start":133.0,"end":141.5,"role":"PAYOFF"}],"assembled_spoken_script":"Full stitched spoken lines in exact EDL playback order...","signal_justification":{"chat_burst":"Z=3.4 sigma / top laugh quote","db_spike":"+11.2dB scream at X:XX","face_emotion":"Surprise/Joy X%"},"cause_and_effect_setup":"Clear setup explaining cold-viewer narrative arc"}]}';

const prompt =
  'SYSTEM: You are the #1 Elite YouTube Shorts Creative Director & Narrative Architect. You are editing non-linear, ultra-high-retention YouTube Shorts from a 1+ hour gaming livestream.\n\n' +
  (streamContext ? '=== STREAM CONTEXT ===\n' + streamContext + '\n\n' : '') +
  (viralContext ? viralContext + '\n' : '') +

  '=== 5 VIRAL YOUTUBE SHORTS NARRATIVE FRAMEWORKS (SELECT BEST MODEL PER CLIP) ===\n' +
  'Evaluate each candidate moment against ALL 5 proven frameworks and diversify archetypes across your selected clips:\n' +
  '1. IN_MEDIA_RES_FLASHFORWARD (CLIMAX_TEASE -> REWIND_SETUP -> FULL_PAYOFF):\n' +
  '   - Start at 0:00-0:02.5 with a HOOK_CLIMAX segment cut strictly 0.3s BEFORE the final reveal/punchline so nothing is spoiled!\n' +
  '   - Hard-cut to SETUP (can rewind earlier in the VOD), then play ESCALATION/PAYOFF through the full climax & reaction.\n' +
  '2. DOUBLE_DOWN_ESCALATION (SETUP -> FAIL_1 -> JUMP_CUT -> DOUBLE_DOWN -> FAIL_2):\n' +
  '   - Stitch initial claim/failure (SETUP) + immediate laugh -> jump-cut past dead air (+10s to +35s OR minutes later in VOD) -> ESCALATION double-down -> bigger PAYOFF.\n' +
  '3. HUBRIS_INSTANT_KARMA (BOAST -> 0.5s_BEAT -> INSTANT_PUNISHMENT):\n' +
  '   - Zero fluff! Open at 0:00 directly on streamer\'s boldest/most arrogant claim (SETUP), smash-cut straight to frame of collapse (PAYOFF), hold 2.5s stunned reaction.\n' +
  '4. MYSTERY_OPEN_LOOP (QUESTION/ANOMALY -> ESCALATING_CLUES -> TWIST_REVEAL):\n' +
  '   - Open with an intriguing question, weird glitch, or strange encounter (HOOK_CLIMAX/SETUP), stitch 3-4 tight clues trimming all silence, end on sharp PAYOFF twist.\n' +
  '5. REVERSE_PAYOFF_LOOP (ENDING_SETUP_LINE -> STORY -> CUT_RIGHT_BEFORE_ENDING_LINE):\n' +
  '   - Pick start/end words so the final truncated clause at the end of PAYOFF flows grammatically & rhythmically straight into the 0:00 opening words (>100% AVD infinite loop).\n\n' +

  '=== STRICT RETENTION & COLD-VIEWER SCRIPTING RULES ===\n' +
  '• ZERO-CONTEXT COLD VIEWER RULE: Assume the viewer knows NOTHING about this stream. If a 2-second SETUP line from 15 minutes earlier is needed to understand why the joke is funny, stitch that early SETUP segment first into segments[]!\n' +
  '• NO SPOILERS AT 0:00: A hook must create an information gap (tension/curiosity/shock), NEVER spoil the final outcome at 0:00. For IN_MEDIA_RES_FLASHFORWARD & MYSTERY_OPEN_LOOP, segments[0] MUST have role "HOOK_CLIMAX" (1.8-2.4s non-spoilering teaser cut BEFORE the reveal).\n' +
  '• ZERO OVERLAPPING TIMESTAMPS: SETUP, ESCALATION, and PAYOFF MUST have strictly non-overlapping timestamps (SETUP.end < ESCALATION.start < PAYOFF.start). Never repeat identical lines across segments!\n' +
  '• DISTINCT SCENES (>= 120s APART): Each clip MUST cover a completely different stream highlight at least 120s apart, rejecting superchat thank-yous and giveaway bot spam.\n' +
  '• RUTHLESS DEAD-AIR REMOVAL: Every segment in segments[] MUST advance tension, setup, or payoff. Total stitched duration across all segments should be 16s to 38s.\n\n' +

  '=== RULE 1: STRICT ANTI-ADMIN, ANTI-MENU & ANTI-BROWSER FILTER ===\n' +
  '• NEVER include desktop/browser screens, notepad, OBS, or admin housekeeping in any clip!\n' +
  '• NEVER include slow UI menus, trade request dialogues, inventory browsing, or passive donation roll calls.\n\n' +

  '=== RULE 2: ZERO-SECOND RETENTION & COLD OPEN RETENTION TRAP (First 0-3 Seconds) ===\n' +
  '• ZERO DEAD TIME AT HOOK: The first 3 seconds are make-or-break for Shorts retention.\n' +
  '• ZERO-SECOND RETENTION & STRICT ANTI-MID-THOUGHT PREAMBLE: REJECT clips that start mid-thought or with casual hesitation banter.\n' +
  '• COLD OPEN RETENTION TRAP & ZERO-SECOND HOOK: For linear clips use cold_open_start/cold_open_end; for Flash-Forward/Loop clips put the exact HOOK_CLIMAX segment first in segments[]!\n' +
  '• TIGHT SETUP BEFORE CLIMAX: Individual linear buildup should be tight (8s-16s before payoff); multi-beat jumps must use separate entries in segments[].\n\n' +

  '=== RULE 3: SINGLE PREMISE NARRATIVE COHESION & CAUSE-EFFECT EDL (ANTI-CHAOS) ===\n' +
  '• SINGLE PREMISE NARRATIVE COHESION: Every Short must tell ONE unified micro-story fulfilling the hook banner and title.\n' +
  '• CAUSE-EFFECT EDL (ANTI-CHAOS): DISQUALIFY raw isolated screams without context. Pair every reaction with its setup.\n\n' +

  '=== RULE 4: PAYOFF IMPACT & ANTI-CLIMAX FILTER ===\n' +
  '• PAYOFF IMPACT & ANTI-CLIMAX FILTER: Climax MUST deliver real comedic/dramatic impact. Allow strictly 2.0-3.5s reaction aftermath, never 20s of chatter.\n' +
  '• NATURAL CLIP DURATION: Target punchy high-retention windows between 18s and 38s across your stitched EDL.\n' +
  '• CLEAN RESOLUTION: Every cut must respect spoken thoughts/laughs.\n\n' +

  '=== RULE 5: TITLES & HOOK CAPTIONS ===\n' +
  '1. TITLE: Curiosity Gap 3-4 words + emoji (💀, 😭, 😱, 🤯), <=25 chars.\n' +
  '2. HOOK_CAPTION: 3-5 WORDS IN ALL CAPS, 100% factual to screen.\n\n' +

  '=== RULE 6: COMPOUND MULTI-BEAT & NON-SEQUENTIAL EDL SEGMENTS ===\n' +
  '• Always populate "segments": [{"start": float, "end": float, "role": "HOOK_CLIMAX"|"SETUP"|"ESCALATION"|"PAYOFF"}] with exact VOD seconds from the transcript.\n' +
  '• You MAY order segments non-chronologically (e.g., HOOK_CLIMAX from 420s -> SETUP from 120s -> PAYOFF from 418s->425s).\n\n' +

  '=== OUTPUT FORMAT ===\n' +
  'Return strictly valid JSON only. No markdown formatting, no explanations.\n' +
  'Output exactly ' + targetClips + ' diverse clips across different narrative_archetype values:\n' +
  jsonSchema + '\n\n' +
  '--- SCOUTED SNIPPETS ---\n' +
  allSnippets;

return [{ pairedItem: { item: 0 }, json: { prompt, targetClips, dry_run: isDryRun } }];`,
    };

    @node({
        id: '4418209d-3aa9-46d8-a4fd-03c46dc71c1f',
        name: 'Gemini Model (Director)',
        type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
        version: 1,
        position: [-86220, 26320],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 5,
        waitBetweenTries: 65000,
    })
    GeminiModelDirector = {
        modelName: 'models/gemini-3.5-flash-lite',
        options: {
            temperature: 0.1,
        },
    };

    @node({
        id: 'de4b9212-cf26-4e54-86db-60d717d8ae99',
        name: '4. Basic LLM Chain (Director)',
        type: '@n8n/n8n-nodes-langchain.chainLlm',
        version: 1.4,
        position: [-86260, 26140],
        onError: 'continueErrorOutput',
    })
    _4BasicLlmChainDirector = {
        promptType: 'define',
        text: '={{ $json.prompt }}',
    };

    @node({
        id: '22aa75de-03e5-4354-bcde-032b4a6101cd',
        name: '5. Split Clips',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-85740, 26140],
    })
    _5SplitClips = {
        jsCode: `const items = $input.all();
let allClips = [];

let streamerName = "Streamer";
try { streamerName = $('Config').item.json.streamer_name || "Streamer"; } catch(e) {}
if (streamerName === "Streamer") {
  try { streamerName = $('Load Cached Telemetry').first().json.streamer_name || "Streamer"; } catch(e) {}
}

let isDryRun = false;
try { isDryRun = Boolean($('3. Prepare Director Prompt').first().json.dry_run); } catch(e) {}
if (!isDryRun) {
  try { isDryRun = Boolean($('Load Cached Telemetry').first().json.dry_run); } catch(e) {}
}

let lastContent = "";
for (const item of items) {
  let content = item.json.output || item.json.text || '{}';
  lastContent = content;

  // 1. Clean markdown formatting
  const b3 = String.fromCharCode(96).repeat(3);
  content = content.split(b3 + 'json').join('').split(b3).join('').trim();

  // 2. Auto-Fix common AI JSON typos
  content = content.replace(/\}\}\}\,\,/g, '}},');
  content = content.replace(/\}\}\]\}/g, '}}]}');
  content = content.replace(/\]\]/g, ']');
  content = content.replace(/\}\,\]/g, '}]');

  try {
    const aiData = JSON.parse(content);
    if (aiData.clips && Array.isArray(aiData.clips)) {
      allClips = allClips.concat(aiData.clips);
    } else if (Array.isArray(aiData)) {
      allClips = allClips.concat(aiData);
    }
    continue;
  } catch (e) {
    // Try extracting embedded JSON object
    const jsonMatch = content.match(/\{[\s\S]*"clips"\s*:\s*\[[\s\S]*\]\s*\}/);
    if (jsonMatch) {
      try {
        const recovered = JSON.parse(jsonMatch[0]);
        if (recovered.clips && Array.isArray(recovered.clips)) {
          allClips = allClips.concat(recovered.clips);
          continue;
        }
      } catch(e2) {}
    }

    const clipBlocks = content.split(/"clip_number"\s*:/i);
    if (clipBlocks.length > 1) {
      for (let i = 1; i < clipBlocks.length; i++) {
        const block = clipBlocks[i];
        const titleMatch = block.match(/"title"\s*:\s*"([^"]+)"/i);
        const hookMatch = block.match(/"hook_caption"\s*:\s*"([^"]+)"/i);
        const archMatch = block.match(/"narrative_archetype"\s*:\s*"([^"]+)"/i);
        const startMatch = block.match(/"start_time"\s*:\s*([\d.]+)/i);
        const endMatch = block.match(/"end_time"\s*:\s*([\d.]+)/i);
        const payoffMatch = block.match(/"payoff_time"\s*:\s*([\d.]+)/i);
        const coStartMatch = block.match(/"cold_open_start"\s*:\s*([\d.]+)/i);
        const coEndMatch = block.match(/"cold_open_end"\s*:\s*([\d.]+)/i);

        if (startMatch && endMatch) {
          const s = parseFloat(startMatch[1]);
          const e = parseFloat(endMatch[1]);
          const p = payoffMatch ? parseFloat(payoffMatch[1]) : e - 3.5;
          allClips.push({
            title: titleMatch ? titleMatch[1] : (streamerName + '_Clip_' + i),
            hook_caption: hookMatch ? hookMatch[1] : "",
            narrative_archetype: archMatch ? archMatch[1] : "HUBRIS_INSTANT_KARMA",
            start_time: s,
            end_time: e,
            payoff_time: p,
            cold_open_start: coStartMatch ? parseFloat(coStartMatch[1]) : p,
            cold_open_end: coEndMatch ? parseFloat(coEndMatch[1]) : Math.min(e, p + 1.8)
          });
        }
      }
    } else {
      const allTimeMatches = [...content.matchAll(/\[([\d\.]+)[sS]?\s*-\s*([\d\.]+)[sS]?\]/g)];
      if (allTimeMatches.length > 0) {
        let currentClipStart = parseFloat(allTimeMatches[0][1]);
        let currentClipEnd = parseFloat(allTimeMatches[0][2]);
        let clipCount = 1;

        for (let i = 1; i < allTimeMatches.length; i++) {
          let start = parseFloat(allTimeMatches[i][1]);
          let end = parseFloat(allTimeMatches[i][2]);
          if (start - currentClipEnd <= 8 && start >= currentClipStart) {
            currentClipEnd = Math.max(currentClipEnd, end);
          } else {
            if (currentClipEnd - currentClipStart > 2) {
              allClips.push({
                title: 'Extracted_Clip_' + (clipCount++),
                hook_caption: "VIRAL MOMENT",
                start_time: currentClipStart,
                end_time: currentClipEnd,
                payoff_time: Math.max(0, currentClipEnd - 3.5),
                cold_open_start: Math.max(0, currentClipEnd - 3.5),
                cold_open_end: Math.max(0, currentClipEnd - 1.7)
              });
            }
            currentClipStart = start;
            currentClipEnd = end;
          }
        }
        if (currentClipEnd - currentClipStart > 2) {
          allClips.push({
            title: 'Extracted_Clip_' + (clipCount++),
            hook_caption: "VIRAL MOMENT",
            start_time: currentClipStart,
            end_time: currentClipEnd,
            payoff_time: Math.max(0, currentClipEnd - 3.5),
            cold_open_start: Math.max(0, currentClipEnd - 3.5),
            cold_open_end: Math.max(0, currentClipEnd - 1.7)
          });
        }
      }
    }
  }
}

if (allClips.length === 0) {
  return [{ pairedItem: { item: 0 }, json: { dry_run: isDryRun, start_time: 2.5, end_time: 36, payoff_time: 32.5, cold_open_start: 32.5, cold_open_end: 34.3, title: streamerName + "_Backup_Clip", hook_caption: "INSANE MOMENT", narrative_archetype: "HUBRIS_INSTANT_KARMA", virality_score: 0, structure_type: "Standard", DEBUG_RAW_AI: lastContent } }];
}

return allClips.map((clip, index) => {
  // Validate discrete multi-beat / non-sequential segments if supplied
  let validSegs = [];
  if (clip.segments && Array.isArray(clip.segments)) {
    validSegs = clip.segments
      .map(s => ({
        start: Math.max(3.0, Number(parseFloat(s.start).toFixed(2)) || 0),
        end: Math.max(3.5, Number(parseFloat(s.end).toFixed(2)) || 0),
        role: String(s.role || 'STORY_BEAT').toUpperCase()
      }))
      .filter(s => s.end > s.start && (s.end - s.start) >= 0.8);
  }

  let sTime = parseFloat(clip.start_time) || (validSegs[0] ? validSegs[0].start : 0);
  let eTime = parseFloat(clip.end_time) || (validSegs.length ? validSegs[validSegs.length - 1].end : (sTime + 36));
  let pTime = parseFloat(clip.payoff_time) || (eTime - 3.5);

  if (validSegs.length <= 1) {
    // ANTI-LOADING SCREEN RULE:
    if (sTime < 3.0) {
        sTime = 3.0;
    }

    // TIGHT HOOK & SETUP: Modern Shorts require fast setup (8s to 16s before climax).
    if (pTime > sTime && (pTime - sTime) > 18.0) {
        sTime = Math.round((pTime - 15.0) * 10) / 10;
        if (sTime < 3.0) sTime = 3.0;
    }

    // PUNCHY AFTERMATH:
    if (pTime > sTime && (eTime - pTime) > 3.5) {
        eTime = Math.round((pTime + 3.0) * 10) / 10;
    }

    // PACING DURATION:
    let dur = eTime - sTime;
    if (dur < 16) {
        if (sTime > 4.0) {
            sTime = Math.max(3.0, Math.round((eTime - 18.0) * 10) / 10);
        }
    } else if (dur > 40) {
        if (pTime > sTime && (pTime - sTime) > 20) {
            sTime = Math.round((pTime - 18.0) * 10) / 10;
        }
        eTime = Math.min(eTime, sTime + 38.0);
    }

    if (validSegs.length === 1) {
      validSegs[0].start = sTime;
      validSegs[0].end = eTime;
    }
  } else {
    // Cap total stitched duration of multi-segment non-linear EDLs to <= 44s cleanly
    let totalSegDur = validSegs.reduce((acc, s) => acc + (s.end - s.start), 0);
    if (totalSegDur > 44.0) {
      const ratio = 42.0 / totalSegDur;
      validSegs = validSegs.map(s => ({
        ...s,
        end: Number((s.start + Math.max(1.2, (s.end - s.start) * ratio)).toFixed(2))
      }));
    }
    sTime = validSegs[0].start;
    eTime = validSegs[validSegs.length - 1].end;
  }

  let coStart = typeof clip.cold_open_start === 'number' ? clip.cold_open_start : pTime;
  let coEnd = typeof clip.cold_open_end === 'number' ? clip.cold_open_end : Math.min(eTime, coStart + 1.8);
  if (validSegs.length <= 1) {
    if (coStart < sTime || coStart >= eTime) coStart = Math.max(sTime, pTime);
    if (coEnd <= coStart || coEnd > eTime) coEnd = Math.min(eTime, coStart + 1.8);
  }

  let hookCaption = (clip.hook_caption || "").trim().toUpperCase();
  if (!hookCaption || hookCaption.length < 3) {
    hookCaption = (clip.title || "").replace(/[^a-zA-Z0-9\s]/g, "").trim().toUpperCase();
    const words = hookCaption.split(/\s+/).slice(0, 5);
    hookCaption = words.join(" ");
  }

  return { json: {
    dry_run: isDryRun,
    clip_number: clip.clip_number || (index + 1),
    start_time: sTime,
    end_time: eTime,
    payoff_time: pTime,
    cold_open_start: Math.round(coStart * 10) / 10,
    cold_open_end: Math.round(coEnd * 10) / 10,
    segments: validSegs,
    narrative_archetype: clip.narrative_archetype || "HUBRIS_INSTANT_KARMA",
    title: clip.title || (streamerName + '_Clip_' + (index + 1)),
    hook_caption: hookCaption,
    virality_score: clip.virality_score || 0,
    theme: clip.theme || "Gaming",
    structure_type: clip.structure_type || clip.narrative_archetype || "Narrative Arc",
    assembled_spoken_script: clip.assembled_spoken_script || "",
    signal_justification: clip.signal_justification || {},
    cause_and_effect_setup: clip.cause_and_effect_setup || "",
    estimated_segment: clip.estimated_vod_segment || "Unknown"
  }};
});`,
    };

    @node({
        id: '1634f843-faa7-432b-9ef3-bf37a298d2ad',
        name: 'Write Sidecar JSON',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-81420, 26840],
    })
    WriteSidecarJson = {
        command: `={{ (function(){ let loopItem = {}; try { loopItem = $('Loop Clips').item.json || {}; } catch(e) { try { loopItem = $('Loop Clips').first().json || {}; } catch(e2) {} } const title = (loopItem.title || 'clip').replace(/[\\/\\\\"'<>|&;:]/g, '_').trim(); const sidecarFile = '/files/outputs/' + title + '.json'; let summary = {}; try { summary = JSON.parse($('1. Global Summary AI').first().json.output || '{}'); } catch(e) {} let caption = title; try { let raw = ($('Context Merge Agent').first().json.output || '{}').replace(/\`\`\`json/gi,'').replace(/\`\`\`/g,'').trim(); caption = JSON.parse(raw).story_hook || title; } catch(e) {} const meta = { viral_caption: caption, game: summary.game || 'Gaming', global_summary: summary.global_summary || '', vibe: summary.vibe || '', theme: loopItem.theme || '', key_themes: summary.key_themes || [] }; const jsonStr = JSON.stringify(meta); return \`cat <<'SIDECAR_EOF' > "\${sidecarFile}"
\${jsonStr}
SIDECAR_EOF\`; })() }}`,
    };

    @node({
        id: 'pick-random-streamer',
        name: 'Pick Random Streamer',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-96360, 26480],
    })
    PickRandomStreamer = {
        jsCode: `const streamers = [
  'https://www.youtube.com/@KreekCraft/streams',
  'https://www.youtube.com/@LankyBox/streams',
  'https://www.youtube.com/@RussoPlays/streams',
  'https://www.youtube.com/@Sketch/streams',
  'https://www.youtube.com/@flamingo/streams',
  'https://www.youtube.com/@ItsFunneh/streams',
  'https://www.youtube.com/@MeganPlays/streams',
  'https://www.youtube.com/@Poke/streams',
  'https://www.youtube.com/@LeahAshe/streams',
  'https://www.youtube.com/@IBella/streams',
  'https://www.youtube.com/@Chaseroony/streams',
  'https://www.youtube.com/@Folty/streams',
  'https://www.twitch.tv/kreekcraft',
  'https://www.twitch.tv/bandites'
];
const randomUrl = streamers[Math.floor(Math.random() * streamers.length)];
return [{ pairedItem: { item: 0 }, json: { url: randomUrl } }];`,
    };

    @node({
        id: 'fallback-download',
        name: 'Fallback Download',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-96160, 26480],
        onError: 'continueErrorOutput',
    })
    FallbackDownload = {
        command:
            '=sleep 600 && if ! command -v python3 &> /dev/null; then apk add --no-cache python3 || echo "Warning: apk add failed"; fi && if [ ! -f /files/yt-dlp ]; then wget -O /files/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp && chmod a+rx /files/yt-dlp; fi && python3 /files/yt-dlp --download-archive "/files/downloaded.txt" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" --playlist-items 1-50 --match-filter "is_live != true & duration <= 14400" -o "/files/inputs/%(title)s.%(ext)s" "{{ $json.url }}"',
    };

    @node({
        id: 'wait-before-scout-node-id',
        webhookId: 'aab8ae8c-3baf-427d-9b15-c701c91609a9',
        name: 'Wait Before Scout',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-89280, 26000],
    })
    
    @node({
        id: 'run-multimodal-fusion-id',
        name: 'Run Multimodal Fusion',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-88880, 26000],
        onError: 'continueRegularOutput',
    })
    RunMultimodalFusion = {
        command:
            '=python3 /files/multimodal_analyzer.py "/files/inputs/{{ $(\'Edit Fields\').first().json.stream_file }}" "/files/temp/audio.mp3" "/files/temp/cam_config.json" "/files/temp/viral_anchors.json"',
    };

    WaitBeforeScout = {
        amount: 1,
    };

    @node({
        id: 'wait-inside-loop-node-id',
        webhookId: '12d23354-fac1-487e-ad89-9e8906365270',
        name: 'Wait Inside Loop',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-85340, 26240],
    })
    WaitInsideLoop = {
        amount: 1,
    };

    @node({
        id: 'b9c69031-3668-45b5-9ae9-2d12c4d9c5b5',
        name: '1. Extract Audio',
        type: 'n8n-nodes-base.executeCommand',
        version: 1,
        position: [-92740, 25900],
    })
    _1ExtractAudio = {
        command:
            '=rm -f "/files/temp/audio.mp3" && ffmpeg -loglevel error -y -i "/files/inputs/{{ $(\'Edit Fields\').first().json.stream_file }}" -vn -acodec libmp3lame -b:a 16k -ac 1 -ar 16000 "/files/temp/audio.mp3"',
    };

    @node({
        id: 'c6719c7a-676e-4598-817b-b03e57f5dfc6',
        name: 'Groq Vision Analyzer',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [-93240, 26460],
        onError: 'continueErrorOutput',
    })
    GroqVisionAnalyzer = {
        method: 'POST',
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={{ $env.GEMINI_API_KEY }}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ $json.vision_payload }}',
        options: {},
    };

    @node({
        id: '814039ad-b3da-4a65-a386-ca700f7ae9f0',
        webhookId: '3191aaa5-eacf-4f3d-82c4-61302cc2d6a3',
        name: 'Wait Summary Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-90220, 25860],
    })
    WaitSummaryError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: '38a839b9-edfd-4248-be53-513b7e4bc5ed',
        webhookId: 'bde66e7f-1ca0-4412-af35-5e26b3783164',
        name: 'Wait Summary Fallback Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-89660, 26080],
    })
    WaitSummaryFallbackError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: 'ce39fb14-e6a4-4804-b37b-2d7e2a6e8708',
        webhookId: '340ecf6f-c8f1-46c3-b267-8407a0c90a2e',
        name: 'Wait Merge Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-83420, 26380],
    })
    WaitMergeError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: 'bb5a74d7-1b07-48dc-af9b-ce0fa77f2c49',
        webhookId: 'f9f9ab12-d6ab-410c-95bf-4b7837f4ef9c',
        name: 'Wait Merge Fallback Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-82320, 26460],
    })
    WaitMergeFallbackError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: 'e2edbe01-ce1f-43a4-ada4-0d33731d2638',
        webhookId: '506b74c0-050d-4688-92a5-cd9089194b8a',
        name: 'Wait Scout Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-87040, 26400],
    })
    WaitScoutError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: 'c7d9e8f1-bbd1-4b50-a110-368f3433a5ef',
        webhookId: '572c00d7-b6cb-43f4-8bdc-ca1fe7f051ba',
        name: 'Wait Director Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-85720, 26360],
    })
    WaitDirectorError = {
        amount: 2.5,
        unit: 'minutes',
    };

    @node({
        id: '635e4fad-1182-402f-8ed8-b7ca90beccc7',
        name: 'Restore Scout Prompt',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [-86880, 26400],
    })
    RestoreScoutPrompt = {
        assignments: {
            assignments: [
                {
                    id: 'prompt_restore',
                    name: 'prompt',
                    value: "={{ $('Scout Loop').item.json.prompt }}",
                    type: 'string',
                },
            ],
        },
        options: {},
    };

    @node({
        id: 'd8db1e5e-e451-4ec3-8ec3-c3092f01dc2c',
        name: 'Restore Director Prompt',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [-85580, 26380],
    })
    RestoreDirectorPrompt = {
        assignments: {
            assignments: [
                {
                    id: 'director_prompt_restore',
                    name: 'prompt',
                    value: "={{ $('3. Prepare Director Prompt').item.json.prompt }}",
                    type: 'string',
                },
            ],
        },
        options: {},
    };

    @node({
        id: '97e773c1-1304-44b7-899f-b136558bff76',
        webhookId: 'da53239e-396d-45fd-b161-b6a1c550fd13',
        name: 'Wait HfFace Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-94880, 26180],
    })
    WaitHffaceError = {
        amount: 20,
    };

    @node({
        id: '9736647b-717b-4230-b462-64f37a100d4d',
        name: 'Restore HfFace Input',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [-94620, 26520],
    })
    RestoreHffaceInput = {
        assignments: {
            assignments: [
                {
                    id: 'file_restore',
                    name: 'file',
                    value: "={{ $('Prepare Frames').item.json.file }}",
                    type: 'string',
                },
            ],
        },
        options: {},
    };

    @node({
        id: '1a02f617-3b9e-4a4c-9148-3e9ec1691042',
        webhookId: '8b66f6b9-5bf6-47a2-87b8-4bba3ae40246',
        name: 'Wait Groq Vision Error',
        type: 'n8n-nodes-base.wait',
        version: 1.1,
        position: [-93720, 26260],
    })
    WaitGroqVisionError = {
        amount: 20,
    };

    @node({
        id: 'd7092f89-f76c-46f3-8524-198e354a283e',
        name: 'If Summary 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-90460, 25840],
    })
    IfSummary429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '91fa46c6-1b59-4b1d-82e8-23b35d72949f',
        name: 'If Summary Fallback 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-89900, 26140],
    })
    IfSummaryFallback429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '6f4b8990-2a09-4e4f-aca0-76e68e21774c',
        name: 'If Merge 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-83560, 26320],
    })
    IfMerge429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '1da623de-669d-4a0e-a776-b0135ce19d4f',
        name: 'If Merge Fallback 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-82500, 26460],
    })
    IfMergeFallback429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '1e2137e1-14ba-42d8-909e-9f6289cbd48b',
        name: 'If Scout 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-87300, 26440],
    })
    IfScout429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '58a99f32-3649-45c4-8bd0-b7234b952f9f',
        name: 'If Director 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-85900, 26260],
    })
    IfDirector429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: '78e1fb7b-e108-4668-9f1a-fd322b0d6de3',
        name: 'If HfFace 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-95160, 26400],
    })
    IfHfface429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    @node({
        id: 'c84535b7-8917-4b12-9bd4-8191286007fe',
        name: 'If Groq Vision 429',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-94100, 26400],
    })
    IfGroqVision429 = {
        conditions: {
            options: {
                caseSensitive: false,
                typeValidation: 'strict',
            },
            conditions: [
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: '429',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'quota',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
                {
                    leftValue: '={{ JSON.stringify($json) }}',
                    rightValue: 'Too many requests',
                    operator: {
                        type: 'string',
                        operation: 'contains',
                    },
                },
            ],
            combinator: 'or',
        },
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @node({
        id: 'sandbox-trigger-script-edl',
        name: 'Sandbox: Test Script & EDL',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [-89280, 26300],
    })
    SandboxTestScriptEdl = {};

    @node({
        id: 'load-cached-telemetry-id',
        name: 'Load Cached Telemetry',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-88880, 26300],
    })
    LoadCachedTelemetry = {
        jsCode: `const fs = require('fs');

const pinned = ($input.first() && $input.first().json) || {};
let indexDoc = null;
let whisperDoc = null;

// Prefer pinned data if user pinned a full cached payload in n8n UI
if (pinned.words && Array.isArray(pinned.words) && pinned.words.length > 0) {
  whisperDoc = pinned;
}

if (!indexDoc && fs.existsSync('/files/temp/unified_timeline_index.json')) {
  try {
    indexDoc = JSON.parse(fs.readFileSync('/files/temp/unified_timeline_index.json', 'utf8'));
  } catch (e) {}
}

// Discover best cached Whisper transcript
const txCandidates = [
  '/files/temp/transcript.json',
  '/files/outputs/whisper_28754.json',
  '/files/temp/whisper_raw.json',
  '/files/outputs/whisper_28696.json',
];
if (!whisperDoc) {
  for (const p of txCandidates) {
    if (fs.existsSync(p)) {
      try {
        const d = JSON.parse(fs.readFileSync(p, 'utf8'));
        const words = d.words || (d.x_groq && d.x_groq.words) || [];
        if (words.length > 0 || (d.text && d.text.length > 50)) {
          whisperDoc = d;
          break;
        }
      } catch (e) {}
    }
  }
}

if (!whisperDoc && !indexDoc) {
  throw new Error('SANDBOX ERROR: No cached telemetry found in /files/temp/. Run telemetry_fusion_indexer.py or pin telemetry JSON.');
}

// Optional secondary caches if unified_timeline_index wasn't built yet
let audioEnergy = null;
let chatClusters = null;
let comedicBeats = null;
let faceEmotions = null;

try { if (fs.existsSync('/files/temp/audio_energy.json')) audioEnergy = JSON.parse(fs.readFileSync('/files/temp/audio_energy.json', 'utf8')); } catch (e) {}
try { if (fs.existsSync('/files/temp/chat_laughter_clusters.json')) chatClusters = JSON.parse(fs.readFileSync('/files/temp/chat_laughter_clusters.json', 'utf8')); } catch (e) {}
try { if (fs.existsSync('/files/temp/comedic_beats.json')) comedicBeats = JSON.parse(fs.readFileSync('/files/temp/comedic_beats.json', 'utf8')); } catch (e) {}
try { if (fs.existsSync('/files/temp/face_emotions.json')) faceEmotions = JSON.parse(fs.readFileSync('/files/temp/face_emotions.json', 'utf8')); } catch (e) {}

const words = (whisperDoc && (whisperDoc.words || (whisperDoc.x_groq && whisperDoc.x_groq.words))) || [];
const duration = (whisperDoc && whisperDoc.duration) || (indexDoc && indexDoc.stream_duration_sec) || (words.length ? words[words.length - 1].end : 3600);

return [{
  pairedItem: { item: 0 },
  json: {
    dry_run: pinned.dry_run !== undefined ? Boolean(pinned.dry_run) : true,
    streamer_name: pinned.streamer_name || 'KreekCraft',
    stream_file: pinned.stream_file || 'sandbox_cached_stream.mp4',
    duration,
    text: (whisperDoc && whisperDoc.text) || '',
    words,
    anchors: (indexDoc && indexDoc.anchors) || pinned.anchors || [],
    macro_high_signal_timeline: (indexDoc && indexDoc.macro_high_signal_timeline) || '',
    annotated_sentences: (indexDoc && indexDoc.annotated_sentences) || [],
    audio_energy: audioEnergy,
    chat_laughter_clusters: chatClusters,
    comedic_beats: comedicBeats,
    face_emotions: faceEmotions,
  }
}];`,
    };

    @node({
        id: 'if-sandbox-skip-wait-id',
        name: 'If Sandbox Skip Wait',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-87920, 26300],
    })
    IfSandboxSkipWait = {
        conditions: {
            options: { caseSensitive: true, typeValidation: 'strict' },
            conditions: [{
                leftValue: '={{ Boolean($json.dry_run) === true }}',
                rightValue: true,
                operator: { type: 'boolean', operation: 'true' },
            }],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'if-bypass-loop-sandbox-id',
        name: 'If Bypass Loop Sandbox',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-85540, 26140],
    })
    IfBypassLoopSandbox = {
        conditions: {
            options: { caseSensitive: true, typeValidation: 'strict' },
            conditions: [{
                leftValue: '={{ Boolean($json.dry_run) === true }}',
                rightValue: true,
                operator: { type: 'boolean', operation: 'true' },
            }],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'is-dry-run-script-sandbox-id',
        name: 'Is Dry Run / Script Sandbox?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [-85080, 26240],
    })
    IsDryRunScriptSandbox = {
        conditions: {
            options: { caseSensitive: true, typeValidation: 'strict' },
            conditions: [{
                leftValue: '={{ Boolean($json.dry_run) === true }}',
                rightValue: true,
                operator: { type: 'boolean', operation: 'true' },
            }],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'dry-run-script-only-id',
        name: 'DRY_RUN_SCRIPT_ONLY',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-84860, 26440],
    })
    DryRunScriptOnly = {
        jsCode: `const fs = require('fs');
const items = $input.all().map(i => i.json);

const fmtTC = (sec) => {
  const sTot = Math.max(0, Number(sec) || 0);
  const m = Math.floor(sTot / 60);
  const s = (sTot % 60).toFixed(2).padStart(5, '0');
  return \`\${String(m).padStart(2, '0')}:\${s}\`;
};

const grouped = new Map();
for (const it of items) {
  const key = \`\${it.clip_number || 1}::\${it.clip_title || 'Clip'}\`;
  if (!grouped.has(key)) {
    grouped.set(key, {
      dry_run: true,
      clip_number: it.clip_number || 1,
      narrative_archetype: it.narrative_archetype || 'HUBRIS_INSTANT_KARMA',
      title: it.clip_title,
      hook_caption: it.hook_caption,
      theme: it.theme,
      cause_and_effect_setup: it.cause_and_effect_setup,
      signal_justification: it.signal_justification || {},
      assembled_spoken_script: it.assembled_spoken_script || '',
      total_duration_sec: 0,
      edl_segments: []
    });
  }
  const entry = grouped.get(key);
  entry.edl_segments.push({
    segment_order: it.segment_order,
    start: it.start,
    end: it.end,
    start_tc: fmtTC(it.start),
    end_tc: fmtTC(it.end),
    duration: it.duration,
    role: it.role || 'STORY_BEAT',
    spoken_text: it.spoken_text || ''
  });
  entry.total_duration_sec = Number((entry.total_duration_sec + (Number(it.duration) || 0)).toFixed(2));
}

const previews = Array.from(grouped.values()).map(p => {
  p.edl_segments.sort((a, b) => a.segment_order - b.segment_order);
  if (!p.assembled_spoken_script) {
    p.assembled_spoken_script = p.edl_segments
      .map(s => \`[\${s.role} \${s.start_tc}-\${s.end_tc}] "\${s.spoken_text}"\`)
      .join(' -> ');
  }
  return p;
});

try {
  fs.writeFileSync('/files/temp/n8n_sandbox_edl_preview.json', JSON.stringify(previews, null, 2));
} catch(e) {}

return previews.map(p => ({ json: p }));`,
    };

    @links()
    defineRouting() {
        this.ScheduleTrigger.out(0).to(this.FindStream.in(0));
        this.WhenClickingTestWorkflow.out(0).to(this.FindStream.in(0));
        this.ExecuteWorkflowTrigger.out(0).to(this.FindStream.in(0));
        this.Webhook.out(0).to(this.FindStream.in(0));
        this.FindStream.out(0).to(this.IfStreamExists.in(0));
        this.IfStreamExists.out(0).to(this.EditFields.in(0));
        this.IfStreamExists.out(1).to(this.PickRandomStreamer.in(0));
        this.EditFields.out(0).to(this.GetReferenceFrame.in(0));
        this.IfHfface429.out(0).to(this.WaitHffaceError.in(0));
        this.IfHfface429.out(1).to(this.ParseCamConfig.in(0));
        this.ReadReference.out(0).to(this.CamVisionPrep.in(0));
        this.CamVisionPrep.out(0).to(this.CamVisionCall.in(0));
        this.GetReferenceFrame.out(0).to(this.ParseCamConfig.in(0));
        this.ParseCamConfig.out(0).to(this.Config.in(0));
        this.Config.out(0).to(this._1ExtractAudio.in(0));
        this._2ReadAudioFile.out(0).to(this._3GroqWhisper.in(0));
        this._3GroqWhisper.out(0).to(this.IfWhisperOk.in(0));
        this.LoopClips.out(0).to(this.DeleteSourceVod.in(0));
        this.LoopClips.out(1).to(this.WaitInsideLoop.in(0));
        this.WaitInsideLoop.out(0).to(this._6ExtractViralSegments.in(0));
        this._6ExtractViralSegments.out(0).to(this.IsDryRunScriptSandbox.in(0));
        this.IsDryRunScriptSandbox.out(0).to(this.DryRunScriptOnly.in(0));
        this.IsDryRunScriptSandbox.out(1).to(this.CutConcatAllSegments.in(0));
        this.CutConcatAllSegments.out(0).to(this.ExecuteCutConcat.in(0));
        this.ExecuteCutConcat.out(0).to(this._7bExtractClipAudio.in(0));
        this._7bExtractClipAudio.out(0).to(this._7cReadAudio.in(0));
        this._7cReadAudio.out(0).to(this._7dGetSubtitlesSrt.in(0));
        this._7dGetSubtitlesSrt.out(0).to(this.GetMemeList.in(0));
        this.GetMemeList.out(0).to(this.ContextMergeAgent.in(0));
        this.CreateSubtitleBinary.out(0).to(this.ReadWriteFilesFromDisk.in(0));
        this.ReadWriteFilesFromDisk.out(0).to(this._7fFinalRender.in(0));
        this._7fFinalRender.out(0).to(this.WriteSidecarJson.in(0));
        this._1GlobalSummaryAi.out(0).to(this.IfSummaryOk.in(0));
        this._1GlobalSummaryAi.out(1).to(this.IfSummary429.in(0));
        this.IfSummary429.out(0).to(this.WaitSummaryError.in(0));
        this.IfSummary429.out(1).to(this._1GlobalSummaryFallback.in(0));
        this.ContextMergeAgent.out(0).to(this.IfMergeOk.in(0));
        this.ContextMergeAgent.out(1).to(this.IfMerge429.in(0));
        this.IfMerge429.out(0).to(this.WaitMergeError.in(0));
        this.IfMerge429.out(1).to(this.ContextMergeFallback.in(0));
        this.PrepareFrames.out(0).to(this.ReadReference.in(0));
        this.IfSummaryOk.out(0).to(this.WaitBeforeScout.in(0));
        this.IfSummaryOk.out(1).to(this._1GlobalSummaryFallback.in(0));
        this.WaitBeforeScout.out(0).to(this.RunMultimodalFusion.in(0));
        this.RunMultimodalFusion.out(0).to(this._1PrepareScoutPrompt.in(0));
        this._1GlobalSummaryFallback.out(0).to(this.RunMultimodalFusion.in(0));
        this._1GlobalSummaryFallback.out(1).to(this.IfSummaryFallback429.in(0));
        this.IfSummaryFallback429.out(0).to(this.WaitSummaryFallbackError.in(0));
        this.IfSummaryFallback429.out(1).to(this.WaitBeforeScout.in(0));
        this.IfMergeOk.out(0).to(this.CreateSubtitleBinary.in(0));
        this.IfMergeOk.out(1).to(this.ContextMergeFallback.in(0));
        this.ContextMergeFallback.out(0).to(this.CreateSubtitleBinary.in(0));
        this.ContextMergeFallback.out(1).to(this.IfMergeFallback429.in(0));
        this.IfMergeFallback429.out(0).to(this.WaitMergeFallbackError.in(0));
        this.IfMergeFallback429.out(1).to(this.CreateSubtitleBinary.in(0));
        this._3GroqWhisperFallback.out(0).to(this._1GlobalSummaryAi.in(0));
        this.IfWhisperOk.out(0).to(this._1GlobalSummaryAi.in(0));
        this.IfWhisperOk.out(1).to(this.WaitBeforeFallback.in(0));
        this.WaitBeforeFallback.out(0).to(this.ReadAudioForFallback.in(0));
        this.ReadAudioForFallback.out(0).to(this._3GroqWhisperFallback.in(0));
        this._1PrepareScoutPrompt.out(0).to(this.ScoutLoop.in(0));
        this.ScoutLoop.out(0).to(this.ScoutAccumulate.in(0));
        this.ScoutLoop.out(1).to(this.IfSandboxSkipWait.in(0));
        this.IfSandboxSkipWait.out(0).to(this._2BasicLlmChainScout.in(0));
        this.IfSandboxSkipWait.out(1).to(this.ScoutWait.in(0));
        this.ScoutWait.out(0).to(this._2BasicLlmChainScout.in(0));
        this._2BasicLlmChainScout.out(0).to(this.ScoutLoop.in(0));
        this._2BasicLlmChainScout.out(1).to(this.IfScout429.in(0));
        this.IfScout429.out(0).to(this.WaitScoutError.in(0));
        this.IfScout429.out(1).to(this.ScoutLoop.in(0));
        this.ScoutAccumulate.out(0).to(this._3PrepareDirectorPrompt.in(0));
        this._3PrepareDirectorPrompt.out(0).to(this._4BasicLlmChainDirector.in(0));
        this._4BasicLlmChainDirector.out(0).to(this._5SplitClips.in(0));
        this._4BasicLlmChainDirector.out(1).to(this.IfDirector429.in(0));
        this.IfDirector429.out(0).to(this.WaitDirectorError.in(0));
        this.IfDirector429.out(1).to(this._5SplitClips.in(0));
        this.SandboxTestScriptEdl.out(0).to(this.LoadCachedTelemetry.in(0));
        this.LoadCachedTelemetry.out(0).to(this._1PrepareScoutPrompt.in(0));
        this._5SplitClips.out(0).to(this.IfBypassLoopSandbox.in(0));
        this.IfBypassLoopSandbox.out(0).to(this._6ExtractViralSegments.in(0));
        this.IfBypassLoopSandbox.out(1).to(this.LoopClips.in(0));
        this.WriteSidecarJson.out(0).to(this.LoopClips.in(0));
        this.PickRandomStreamer.out(0).to(this.FallbackDownload.in(0));
        this.FallbackDownload.out(0).to(this.FindStream.in(0));
        this.FallbackDownload.out(1).to(this.FindStream.in(0));
        this._1ExtractAudio.out(0).to(this._2ReadAudioFile.in(0));
        this.WaitSummaryError.out(0).to(this._1GlobalSummaryAi.in(0));
        this.WaitSummaryFallbackError.out(0).to(this._1GlobalSummaryFallback.in(0));
        this.WaitMergeError.out(0).to(this.ContextMergeAgent.in(0));
        this.WaitMergeFallbackError.out(0).to(this.ContextMergeFallback.in(0));
        this.WaitScoutError.out(0).to(this.RestoreScoutPrompt.in(0));
        this.RestoreScoutPrompt.out(0).to(this._2BasicLlmChainScout.in(0));
        this.WaitDirectorError.out(0).to(this.RestoreDirectorPrompt.in(0));
        this.RestoreDirectorPrompt.out(0).to(this._4BasicLlmChainDirector.in(0));
        this.WaitHffaceError.out(0).to(this.RestoreHffaceInput.in(0));
        this.RestoreHffaceInput.out(0).to(this.ReadReference.in(0));
        this.WaitGroqVisionError.out(0).to(this.VisionPrep1.in(0));

        this._1GlobalSummaryAi.uses({
            ai_languageModel: this.GeminiModel1.output,
        });
        this.ContextMergeAgent.uses({
            ai_languageModel: this.GeminiModel2.output,
        });
        this._1GlobalSummaryFallback.uses({
            ai_languageModel: this.GeminiBackupModel1.output,
        });
        this.ContextMergeFallback.uses({
            ai_languageModel: this.GeminiBackupModel3.output,
        });
        this._2BasicLlmChainScout.uses({
            ai_languageModel: this.GeminiModelScout.output,
        });
        this._4BasicLlmChainDirector.uses({
            ai_languageModel: this.GeminiModelDirector.output,
        });
    }
}
