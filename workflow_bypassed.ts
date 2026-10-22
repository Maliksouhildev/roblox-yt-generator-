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
            'file=$(ls -1 /files/inputs/ | grep "\\.mp4$" | grep -v "\\.processing\\.mp4$" | head -n 1); if [ -n "$file" ]; then mv "/files/inputs/$file" "/files/inputs/${file%.mp4}.processing.mp4"; echo "${file%.mp4}.processing.mp4"; else echo ""; fi',
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
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyDqACFpgY2IsbUFoul7D62V17DPTXGkTrQ',
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
            { text: "This is a gaming livestream frame. Find the streamer's webcam PiP (Picture-in-Picture) overlay. It may be a person, vtuber avatar, or emoji. Return ONLY JSON: {"found": true, "xmin": 10, "ymin": 10, "xmax": 150, "ymax": 100} with pixel coords in a 480x270 image. If no PiP exists return {"found": false}." },
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
        jsCode: `const clipData = $input.first().json;
const start = clipData.start_time;
const end = clipData.end_time;
if (typeof start !== 'number' || typeof end !== 'number') return [{ pairedItem: { item: 0 }, json: { error: "No timestamps", clip_title: clipData.title } }];

const BUFFER=0.2; // tighter buffer for faster pacing
let finalSegs = [];

// Try to get words from Whisper transcript to cut silences dynamically
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

if (words.length > 0) {
  const clipWords = words.filter(w => w.end >= start && w.start <= end);
  
  if (clipWords.length > 0) {
    let currentSegStart = Math.max(0, clipWords[0].start - BUFFER);
    let lastWordEnd = clipWords[0].end;
    
    for (let i = 1; i < clipWords.length; i++) {
      const w = clipWords[i];
      // If gap is more than 0.8s, jump cut it!
      if (w.start - lastWordEnd > 0.8) {
        finalSegs.push({
          name: 'MainClip_part',
          start: currentSegStart,
          end: lastWordEnd + BUFFER
        });
        currentSegStart = Math.max(lastWordEnd + BUFFER, w.start - BUFFER);
      }
      lastWordEnd = w.end;
    }
    finalSegs.push({
      name: 'MainClip_part',
      start: currentSegStart,
      end: Math.min(end, lastWordEnd + BUFFER)
    });
  }
}

// Fallback if no words found
if (finalSegs.length === 0) {
  finalSegs = [{
    name: 'MainClip',
    start: Math.max(0, start - BUFFER),
    end: end + BUFFER
  }];
}

return finalSegs.map((seg,i)=>({ json:{
    segment_name:seg.name, segment_order:i+1,
    start:seg.start, end:seg.end, duration:seg.end-seg.start,
    payoff_time: clipData.payoff_time || seg.end - 5,
    clip_title:clipData.title, theme:clipData.theme||"None",
    structure_type:clipData.structure_type||"Standard"
}}));

`,
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

// Drop segments shorter than 0.5s - ffmpeg chokes on near-zero durations
const segments = all.filter(s => (s.end - s.start) >= 0.5);
if (segments.length === 0) {
    // Emergency fallback: just take first 40 seconds
    segments.push({ ...all[0], start: 0, end: 40 });
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
    filterComplex += \`[0:v]trim=start=\${relStart.toFixed(3)}:end=\${relEnd.toFixed(3)},setpts=PTS-STARTPTS[v\${partIdx}];\`;
    filterComplex += \`[0:a]atrim=start=\${relStart.toFixed(3)}:end=\${relEnd.toFixed(3)},asetpts=PTS-STARTPTS[a\${partIdx}];\`;
    concatInputs += \`[v\${partIdx}][a\${partIdx}]\`;
    partIdx++;
});

const ffmpegCmd = \`ffmpeg -loglevel error -y -ss \${seekStart} -t \${seekDuration} -i "/files/inputs/\${streamFile}" -filter_complex "\${filterComplex}\${concatInputs}concat=n=\${partIdx}:v=1:a=1[v_out][a_out]" -map "[v_out]" -map "[a_out]" -c:v libx264 -preset fast -crf 16 -c:a aac -movflags +faststart "/files/temp/concatenated_clip.mp4"\`;

return [{ pairedItem: { item: 0 }, json: { command: ffmpegCmd, clip_title: clipTitle, parts: partIdx } }];`,
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
            'mkdir -p /files/inputs/fonts && cp -n /files/inputs/*.ttf /files/inputs/fonts/ 2>/dev/null || true; ls /files/memes && echo "---DIMENSIONS---" && ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "/files/temp/concatenated_clip.mp4" || echo "1920x1080"',
    };

    @node({
        id: '727de56b-e2bf-4cce-9dd8-dc7fdc62e4b1',
        name: 'Create Subtitle Binary',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-82080, 26080],
    })
    CreateSubtitleBinary = {
        jsCode: `const FONT_SIZE = 48;
const HIGHLIGHT_COLOR = "&H00FFFF&";
const MAIN_COLOR = "&HFFFFFF&";
function formatTimeASS(seconds) {
  const sTotal = Math.max(0, parseFloat(seconds) || 0);
  const h = Math.floor(sTotal / 3600);
  const m = Math.floor((sTotal % 3600) / 60);
  const s = Math.floor(sTotal % 60);
  const cs = Math.floor((sTotal % 1) * 100);
  return h + ":" + String(m).padStart(2,'0') + ":" + String(s).padStart(2,'0') + "." + String(cs).padStart(2,'0');
}

const subInput = $('7d. Get Subtitles (SRT)').first().json;
let wordData = subInput.words || (subInput.x_groq && subInput.x_groq.words) || [];

const camConfig = $('Parse Cam Config').first().json;
const camW = camConfig.cam_w, camH = camConfig.cam_h, camX = camConfig.cam_x, camY = camConfig.cam_y;
const hasCam = !!(camConfig && camConfig.ai_found);

const getMemeOutput = $('Get Meme List').first().json.stdout || "";
const parts = getMemeOutput.split("---DIMENSIONS---");
const realFiles = (parts[0] || "").split('\\n').map(f => f.trim()).filter(f => f.length > 3);

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
const clipEnd = parseFloat(clipData.end_time) || (clipStart + 45);
const clipDur = Math.max(1, Math.round((clipEnd - clipStart) * 10) / 10);

let rawCaption = (clipData.hook_caption || clipData.title || '').substring(0, 42).toUpperCase().replace(/_/g, ' ');
let screams = [], memes = [], climaxQuote = "";

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
    if (parsed.story_hook) rawCaption = parsed.story_hook.toUpperCase();
    if (parsed.climax_quote) climaxQuote = parsed.climax_quote;
    if (parsed.screams) screams = parsed.screams;
    if (parsed.screams_or_full_cam) screams = screams.concat(parsed.screams_or_full_cam);
    if (parsed.memes && Array.isArray(parsed.memes)) memes = parsed.memes;
  }
} catch(e) {}

// ── Detect Climax Timing for Impact Zoom ─────────────────────────────────
const absolutePayoff = parseFloat(clipData.payoff_time) || 0;
let relativePayoff = (absolutePayoff > clipStart) ? (absolutePayoff - clipStart) : absolutePayoff;
if (relativePayoff <= 0 || relativePayoff >= clipDur) {
  relativePayoff = Math.max(0, clipDur - 5.0);
}

let climaxStart = relativePayoff;
if (climaxQuote && wordData.length > 0) {
  const quoteWords = String(climaxQuote).toLowerCase().replace(/[^a-z0-9\\s]/g, '').trim().split(/\\s+/).filter(Boolean);
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
  climaxStart = Math.max(0, clipDur - 5.0);
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
    durationInSeconds: 4.5
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

const overlayInput = remotionOverlayFile ? ('-loop 1 -t 4.5 -i "' + remotionOverlayFile + '"') : "";
const memeInputOffset = remotionOverlayFile ? 2 : 1;

// ── Meme Audio Mixing ────────────────────────────────────────────────────
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
  let mixInputs = "[0:a]";
  for (let k = 1; k <= activeMemes; k++) mixInputs += '[meme' + k + ']';
  audioMixFilter = audioFilters + mixInputs + 'amix=inputs=' + (activeMemes + 1) + ':duration=first:normalize=0,alimiter=limit=-3dB:attack=5:release=50[a_out]';
}

// ── Dynamic Multi-Beat Camera Motion ────────────────────────────────────
// Climax zoom strictly 3.5s (eliminates infinite zoom bug)
const climaxEnd = Math.min(clipDur, Math.round((climaxStart + 3.5) * 10) / 10);

let screamBlocks = [];
if (Array.isArray(screams)) {
  screams.forEach(s => {
    if (Array.isArray(s) && s.length === 2) {
      const s0 = Math.max(0, parseFloat(s[0]));
      const s1 = Math.min(clipDur, Math.min(parseFloat(s[1]), s0 + 2.5));
      if (s1 > s0) {
        screamBlocks.push('between(t,' + s0.toFixed(2) + ',' + s1.toFixed(2) + ')');
      }
    }
  });
}

let climaxBlocks = ['between(t,' + climaxStart.toFixed(2) + ',' + climaxEnd.toFixed(2) + ')'];
if (screamBlocks.length > 0) {
  climaxBlocks = climaxBlocks.concat(screamBlocks);
}
const climaxEnable = climaxBlocks.join("+");

// 2.0s Hook Punch Zoom (1.12x)
const hookEnd = Math.min(clipDur, 2.0);
const hookEnable = 'between(t,0,' + hookEnd.toFixed(2) + ')';
const camZoomEnable = climaxEnable;

// ── Dynamic Subtitle & Caption Framing ──────────────────────────────────
// In Facecam: Subtitles straddle divider seam at y=460; Intro caption at y=70
// In Full-Screen No-Cam: Subtitles cleanly near bottom at y=1040; Persistent banner at top at y=95
const subY = hasCam ? 460 : 1040;
const captionY = hasCam ? 70 : 95;

let assContent = '[Script Info]\\n' +
  'ScriptType: v4.00+\\n' +
  'PlayResX: 720\\n' +
  'PlayResY: 1280\\n' +
  '[V4+ Styles]\\n' +
  'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\\n' +
  'Style: ViralSubs,Lilita One,' + FONT_SIZE + ',' + MAIN_COLOR + ',&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\\n' +
  'Style: ViralCaption,Lilita One,42,&H00D7FF&,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\\n' +
  '[Events]\\n' +
  'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\\n';

// ── Semantic Phrase Grouping Subtitles ────────────────────────────────────
if (wordData.length > 0) {
  const PAUSE_BREAK = 0.35;    
  const MAX_CHARS = 16;         
  const MAX_WORDS = 4;          
  const PUNCT_RE = /[.!?,;:]$/; 

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
    const endsPhrase = PUNCT_RE.test(word);

    const shouldBreak =
      current.length >= MAX_WORDS ||
      currentChars >= MAX_CHARS ||
      gapToNext > PAUSE_BREAK ||
      endsPhrase;

    if (shouldBreak && current.length > 0) {
      groups.push([...current]);
      current = [];
    }
  }
  if (current.length > 0) groups.push(current);

  for (const group of groups) {
    const cStart = group[0].start;
    const cEnd = group[group.length - 1].end;
    const displayEnd = cEnd; 

    for (let j = 0; j < group.length; j++) {
      const wStart = Math.max(cStart, group[j].start);
      const wEnd = j < group.length - 1 ? group[j + 1].start : displayEnd;

      const lineText = group.map((w, idx) => {
        const txt = String(w.word || "").trim().toUpperCase();
        if (idx === j) {
          const colors = ["&H00FFFF&", "&H00FF00&", "&H00D7FF&"];
          const randColor = colors[txt.length % colors.length];
          return '{\\\\c' + randColor + '\\\\t(0,40,\\\\fscx115\\\\fscy115)\\\\t(40,120,\\\\fscx100\\\\fscy100)}' + txt + '{\\\\c' + MAIN_COLOR + '}';
        }
        return txt;
      }).join(" ");

      assContent += 'Dialogue: 1,' + formatTimeASS(wStart) + ',' + formatTimeASS(wEnd) + ',ViralSubs,,0,0,0,,{\\\\pos(360,' + subY + ')}' + lineText + '\\n';
    }
  }
}

// ── Hook Banner & Persistent Top Header ───────────────────────────────────
if (rawCaption) {
  const cleanCaption = rawCaption.replace(/['"\\\`]/g, '').trim().toUpperCase();
  if (!hasCam) {
    // Cinema No-Cam: Persistent banner across entire video in top banner zone (y=0 to y=180)
    // If Remotion overlay rendered, start banner after Remotion completes at 4.5s
    const capStart = remotionOverlayFile ? "0:00:04.50" : "0:00:00.00";
    const capEnd = formatTimeASS(clipDur);
    assContent += 'Dialogue: 2,' + capStart + ',' + capEnd + ',ViralCaption,,0,0,0,,{\\\\pos(360,' + captionY + ')\\\\t(0,80,\\\\fscx108\\\\fscy108)\\\\t(80,180,\\\\fscx100\\\\fscy100)}' + cleanCaption + '\\n';
  } else {
    // Facecam mode: 4.5s intro punch hook banner (only if Remotion did not already provide it)
    if (!remotionOverlayFile) {
      assContent += 'Dialogue: 2,0:00:00.00,0:00:04.50,ViralCaption,,0,0,0,,{\\\\pos(360,' + captionY + ')\\\\fad(0,400)\\\\t(0,80,\\\\fscx110\\\\fscy110)\\\\t(80,200,\\\\fscx100\\\\fscy100)}' + cleanCaption + '\\n';
    }
  }
}

// ── FFmpeg Filter Graph with Zero-Gap Split & Cinema Framing ──────────────
const overlayGraph = remotionOverlayFile
  ? "[1:v]fade=in:st=0:d=0.25:alpha=1,fade=out:st=4.0:d=0.5:alpha=1[hook];[base][hook]overlay=0:0:enable='between(t,0,4.5)'[v_hook];[v_hook]ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v]"
  : "[base]ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v]";

let filter = "";
if (isVertical) {
  filter = '[0:v]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2[base];' + overlayGraph;
} else if (hasCam) {
  // ZERO-GAP SPLIT SCREEN: Top Cam (720x460) + Bottom Game (720x820) = 1280, clean 6px divider at y=460
  const cwRatio = (camW / 1920).toFixed(4);
  const chRatio = (camH / 1080).toFixed(4);
  const cxRatio = (camX / 1920).toFixed(4);
  const cyRatio = (camY / 1080).toFixed(4);

  const bgPart = "[0:v]split=3[v_bg][v_game][v_cam];[v_bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:5[bg]";
  const camPart = "[v_cam]crop=trunc(iw*" + cwRatio + "/2)*2:trunc(ih*" + chRatio + "/2)*2:trunc(iw*" + cxRatio + "/2)*2:trunc(ih*" + cyRatio + "/2)*2,scale=720:460:force_original_aspect_ratio=increase,crop=720:460:(iw-ow)/2:(ih-oh)/2,split=2[c_norm][c_punch_src];[c_punch_src]scale=trunc(720*1.22/2)*2:-1,crop=720:460:(iw-ow)/2:(ih-oh)/2[c_punch];[c_norm][c_punch]overlay=0:0:enable='" + camZoomEnable + "'[c_final];[c_final]drawbox=x=0:y=0:w=720:h=460:color=white:t=6[cam_bordered]";
  const gamePart = "[v_game]crop='trunc(min(iw,ih*0.88)/2)*2':'trunc(ih/2)*2':(iw-ow)/2:0,scale=720:820,split=3[g_base][g_hk_src][g_cl_src];[g_hk_src]scale=trunc(720*1.12/2)*2:-1,crop=720:820:(iw-ow)/2:(ih-oh)/2[g_hk];[g_cl_src]scale=trunc(720*1.22/2)*2:-1,crop=720:820:(iw-ow)/2:(ih-oh)/2[g_cl];[g_base][g_hk]overlay=0:0:enable='" + hookEnable + "'[g_after_hk];[g_after_hk][g_cl]overlay=0:0:enable='" + climaxEnable + "'[g_final];[g_final]drawbox=x=0:y=0:w=720:h=820:color=white:t=6[game_bordered]";
  const overlayPart = "[bg][cam_bordered]overlay=0:0[bg2];[bg2][game_bordered]overlay=0:460[base_raw];[base_raw]drawbox=x=0:y=457:w=720:h=6:color=white:t=fill[base];" + overlayGraph;
  filter = bgPart + ";" + camPart + ";" + gamePart + ";" + overlayPart;
} else {
  // FULL SCREEN GAMEPLAY NO-CAM: 720x1280 full frame, zero borders, zero margins
  const gamePart = "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2:(ih-oh)/2,split=3[g_base][g_hk_src][g_cl_src];" +
    "[g_hk_src]scale=trunc(720*1.12/2)*2:-1,crop=720:1280:(iw-ow)/2:(ih-oh)/2[g_hk];" +
    "[g_cl_src]scale=trunc(720*1.22/2)*2:-1,crop=720:1280:(iw-ow)/2:(ih-oh)/2[g_cl];" +
    "[g_base][g_hk]overlay=0:0:enable='" + hookEnable + "'[g_after_hk];" +
    "[g_after_hk][g_cl]overlay=0:0:enable='" + climaxEnable + "'[base];";
  filter = gamePart + overlayGraph;
}

const title = (clipData.title || "output_clip").replace(/[\/\\"'<>|&;:]/g, '_').trim();
const outputFile = "/files/outputs/" + title + ".mp4";
const extraInputs = overlayInput ? (' ' + overlayInput) : "";

const cmd = activeMemes > 0
  ? ('ffmpeg -loglevel error -y -i "/files/temp/concatenated_clip.mp4"' + extraInputs + ' ' + audioInputs.join(" ") + ' -filter_complex "' + filter + ';' + audioMixFilter + '" -map "[v]" -map "[a_out]" -c:v libx264 -preset medium -crf 18 -c:a aac "' + outputFile + '"')
  : ('ffmpeg -loglevel error -y -i "/files/temp/concatenated_clip.mp4"' + extraInputs + ' -filter_complex "' + filter + '" -map "[v]" -map 0:a -c:v libx264 -preset medium -crf 18 -c:a aac "' + outputFile + '"');

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

YOUR JOB — output ONLY raw JSON with these 3 fields:

1. STORY HOOK (Top Banner, 3-5 punchy words in ALL CAPS)
• PRIMARY DIRECTIVE: Keep the Director's PROPOSED HOOK BANNER as your story_hook UNLESS you can make it punchier while staying 100% FACTUAL to the spoken transcript.
• CRITICAL ANTI-HALLUCINATION RULE: NEVER invent hackers, scams, or teams if they are not explicitly spoken in the transcript! No generic clickbait (e.g. NEVER output "THE HACKER EXPOSED" or "SAVING THE WHOLE TEAM" unless those exact events occurred).
• Examples: "I CALLED TIME OUT", "THAT DOES NOT COUNT", "HE ACTUALLY FELL FOR IT", "MY WORST BLUNDER".

2. CLIMAX QUOTE (Exact 3 to 5 words spoken at the peak moment)
• Find the EXACT 3-5 words spoken at the highest-energy punchline, arrest, scream, or reaction in the transcript.
• Example: "bro you arrested me" or "no way you pulled that" or "why did you do that".
• This anchors our visual punch-in zoom to the exact spoken climax audio.

3. MEMES (0 TO 2 SOUNDS MAXIMUM)
• Natural audio is preferred! If dialogue is already clear and funny, return: "memes": []
• Only pick a sound effect if there is an explicit comedic blunder, sudden roast, or awkward shock:
  - vine-boom-sound-effect_KT89XIq.mp3 -> Heavy impact, roast landing, sudden plot twist.
  - huh_37bAoRo.mp3 -> Total confusion, bewildered reaction, awkward silence.
  - fartmeme.mp3 -> Slapstick fail, dying to a silly trap.
• Volume: 0.35.

Output ONLY valid raw JSON:
{
  "story_hook": "I CALLED TIME OUT",
  "climax_quote": "bro you arrested me",
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

YOUR JOB — output ONLY raw JSON with these 3 fields:

1. STORY HOOK (Top Banner, 3-5 punchy words in ALL CAPS)
• PRIMARY DIRECTIVE: Keep the Director's PROPOSED HOOK BANNER as your story_hook UNLESS you can make it punchier while staying 100% FACTUAL to the spoken transcript.
• CRITICAL ANTI-HALLUCINATION RULE: NEVER invent hackers, scams, or teams if they are not explicitly spoken in the transcript! No generic clickbait (e.g. NEVER output "THE HACKER EXPOSED" or "SAVING THE WHOLE TEAM" unless those exact events occurred).
• Examples: "I CALLED TIME OUT", "THAT DOES NOT COUNT", "HE ACTUALLY FELL FOR IT", "MY WORST BLUNDER".

2. CLIMAX QUOTE (Exact 3 to 5 words spoken at the peak moment)
• Find the EXACT 3-5 words spoken at the highest-energy punchline, arrest, scream, or reaction in the transcript.
• Example: "bro you arrested me" or "no way you pulled that" or "why did you do that".
• This anchors our visual punch-in zoom to the exact spoken climax audio.

3. MEMES (0 TO 2 SOUNDS MAXIMUM)
• Natural audio is preferred! If dialogue is already clear and funny, return: "memes": []
• Only pick a sound effect if there is an explicit comedic blunder, sudden roast, or awkward shock:
  - vine-boom-sound-effect_KT89XIq.mp3 -> Heavy impact, roast landing, sudden plot twist.
  - huh_37bAoRo.mp3 -> Total confusion, bewildered reaction, awkward silence.
  - fartmeme.mp3 -> Slapstick fail, dying to a silly trap.
• Volume: 0.35.

Output ONLY valid raw JSON:
{
  "story_hook": "I CALLED TIME OUT",
  "climax_quote": "bro you arrested me",
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
        jsCode: `let whisperData = null;

try {
  const items = $input.all();
  if (items && items[0] && items[0].json && items[0].json.text) {
    whisperData = items[0].json;
  }
} catch(e) {}

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

if (!whisperData || !whisperData.text) {
    throw new Error('CRITICAL ERROR: Transcript text is missing. Run Whisper node first.');
}

const rawText = whisperData.text;
const durationMinutes = (whisperData.duration || 1800) / 60;

// Break into sentences and add Line Numbers and Timestamps
let whisperWords = whisperData.words || (whisperData.x_groq && whisperData.x_groq.words) || [];
let sentences = [];
let currSentence = "";
let currStart = -1;
let currEnd = -1;
for (let w of whisperWords) {
  if (currStart === -1) currStart = w.start;
  currSentence += w.word;
  currEnd = w.end;
  if (/[.!?]$/.test(w.word.trim())) {
    sentences.push(\`[\${currStart.toFixed(1)}s - \${currEnd.toFixed(1)}s] \${currSentence.trim()}\`);
    currSentence = "";
    currStart = -1;
  }
}
if (currSentence) sentences.push(\`[\${currStart.toFixed(1)}s - \${currEnd.toFixed(1)}s] \${currSentence.trim()}\`);

const numberedLines = sentences.length > 0 ? sentences : (rawText.match(/[^.!?]+[.!?]+/g) || [rawText]).map((s, i) => '[L' + (i+1) + '] ' + s.trim());

// Calculate chunks — cap at 4 to limit parallel Groq calls
let numChunks = Math.max(1, Math.round(durationMinutes / 7.5));
numChunks = Math.min(numChunks, 4);

const linesPerChunk = Math.ceil(numberedLines.length / numChunks);
const overlap = 10; // Reduced from 20 to keep chunks smaller

// TOKEN BUDGET: openai/gpt-oss-120b = 12,000 TPM limit
// Prompt overhead ≈ 300 tokens, output ≈ 600 tokens → 11,100 tokens left for input text
// 1 token ≈ 4 chars → safe char cap = 10,000 chars per chunk
const MAX_CHUNK_CHARS = 10000;

const results = [];
for (let i = 0; i < numChunks; i++) {
  const start = Math.max(0, i * linesPerChunk - overlap);
  const end = Math.min(numberedLines.length, (i + 1) * linesPerChunk + overlap);
  
  // Build chunk text and HARD-CAP at 10,000 chars
  let chunkText = numberedLines.slice(start, end).join('\\n');
  if (chunkText.length > MAX_CHUNK_CHARS) {
    // Trim from the end — keep the start (line numbers stay sequential)
    chunkText = chunkText.substring(0, MAX_CHUNK_CHARS) + '\\n[... chunk trimmed to fit token limit ...]';
  }

  const prompt = 
    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout. Read the numbered transcript chunk and identify the top 3 most explosive, high-retention gaming moments.\\n\\n' +
    '=== CRITICAL ANTI-ADMIN & ANTI-BROWSER FILTER ===\\n' +
    'The streamer frequently Alt-Tabs out of Roblox into Chrome, Notepad, or OBS. You MUST REJECT any segments containing stream housekeeping or desktop admin:\\n' +
    '• Typing player usernames into search bars, accepting friend requests on the Roblox website.\\n' +
    '• Reading long lists of $3 donations or subscriber names while idling in prison cells or menus.\\n' +
    '• Setting up VIP server links, Discord DMs, or troubleshooting settings.\\n' +
    '• If a great in-game moment precedes browser/admin talk, STOP THE MOMENT 3 to 5 seconds after the in-game reaction/laugh! NEVER include the desktop/browser transition.\\n\\n' +
    '=== WHAT TO SCOUT FOR (VIRAL ARCHETYPES) ===\\n' +
    '- [VIRAL STORY/LORE]: Streamer sharing a personal story, childhood embarrassment ("Cringe Era"), or confession.\\n' +
    '- [BET / CHALLENGE]: High-stakes dare (e.g. "if I get caught I do X").\\n' +
    '- [BETRAYAL / ARREST]: Dramatic in-game arrest, backstab, heist gone wrong, sudden ambush.\\n' +
    '- [HILARIOUS FAIL]: Instant karma, accidental blunder, sudden screaming chaos.\\n\\n' +
    '=== PACING & RESOLUTION ===\\n' +
    '• The climax (punchline, arrest, scream) must occur at the peak of the moment, followed by 3-5s of aftermath.\\n' +
    '• Must end on a complete thought, sentence, or laughter. NEVER cut off mid-word or mid-sentence!\\n\\n' +
    'OUTPUT: Plain text only. For each of the 3 moments, write:\\n' +
    '- Tag: [TAG NAME] (e.g. [BETRAYAL / ARREST], [CRINGE LORE], [HILARIOUS FAIL])\\n' +
    '- Exact Climax Quote: "..."\\n' +
    '- Start & End Timestamps: [X.Xs - Y.Ys]\\n' +
    '- 4 lines of context before climax [Lx]\\n' +
    '- 2-3 lines of reaction after climax [Lx]\\n\\n' +
    '--- CHUNK ' + (i+1) + '/' + numChunks + ' ---\\n' +
    chunkText;

  results.push({ json: { prompt, chunk_index: i+1 } });
}

return results;
`,
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
        jsCode: 'return $items("2. Basic LLM Chain (Scout)");',
    };

    @node({
        id: '59c847f1-0354-4acd-9aef-3c3bea58643b',
        name: '3. Prepare Director Prompt',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [-86500, 26120],
    })
    _3PrepareDirectorPrompt = {
        jsCode: `const items = $input.all();
let allSnippets = "";

// Gather all the plain text snippets from the Scout pass
items.forEach((item, index) => {
  allSnippets += \`\\n\\n=== SCOUTED MOMENTS CHUNK \${index + 1} ===\\n\`;
  allSnippets += item.json.text || item.json.output || "";
});

// Pull the Global Summary for title context
let streamContext = "";
try {
  const summaryRaw = $('1. Global Summary AI').first().json.output || $('1. Global Summary Fallback').first().json.output || "{}";
  const summary = JSON.parse(summaryRaw.replace(/\`\`\`json/gi,'').replace(/\`\`\`/g,'').trim());
  streamContext = [
    summary.game ? "GAME: " + summary.game : "",
    summary.global_summary ? "STREAM SUMMARY: " + summary.global_summary : "",
    summary.vibe ? "VIBE: " + summary.vibe : "",
    (summary.key_themes && summary.key_themes.length) ? "KEY THEMES: " + summary.key_themes.join(", ") : ""
  ].filter(Boolean).join("\\n");
} catch(e) {}

// Target top clips
const targetClips = 6; 

const jsonSchema = '{"clips":[{"clip_number":1,"estimated_vod_segment":"X-Y minutes","title":"3-4 Word Curiosity Teaser 💀","hook_caption":"3-5 WORDS IN ALL CAPS","theme":"Core viral theme","structure_type":"Narrative Arc","start_time":105.2,"end_time":152.0,"payoff_time":146.5}]}';

const prompt = 
  'SYSTEM: You are the #1 Elite YouTube Shorts Creative Director & Narrative Architect. You are selecting and pacing the absolute best viral clips from a gaming stream.\\n\\n' +

  (streamContext ? '=== STREAM CONTEXT ===\\n' + streamContext + '\\n\\n' : '') +

  '=== RULE 1: STRICT ANTI-ADMIN & ANTI-BROWSER FILTER ===\\n' +
  'The streamer frequently Alt-Tabs out of Roblox into Google Chrome, Notepad, or OBS to look up usernames, accept friend requests, configure VIP links, or read donor names.\\n' +
  '• NEVER include desktop/browser screens or admin housekeeping in any clip!\\n' +
  '• If an in-game climax (e.g. arrest, heist, rare trade) is followed by the streamer sitting in a prison cell reading donor lists or opening Chrome, SET end_time EXACTLY 3 TO 5 SECONDS AFTER THE IN-GAME REACTION/LAUGH!\\n' +
  '• Cut BEFORE they switch windows or start reading donor roll calls.\\n\\n' +

  '=== RULE 2: PACING ARC & CLIMAX PLACEMENT ===\\n' +
  '• CLIMAX IN FINAL 20-30%: The payoff_time (the arrest, betrayal, scream, punchline, or rare drop) MUST occur in the final 20% to 30% of the clip (e.g., between second 32 and second 42 of a 45s clip).\\n' +
  '• PUNCHY AFTERMATH: Allow at most 4 to 6 seconds of high-energy reaction/laugh after payoff_time, then CUT CLEANLY. Never leave 20-30 seconds of slow aftermath!\\n' +
  '• NATURAL CLIP DURATION: Do NOT force a rigid 65s-75s window! Allow raw windows between 42s and 68s (end_time - start_time between 42 and 68) as long as the narrative arc is 100% self-contained.\\n' +
  '• CLEAN RESOLUTION: Every clip must end on a complete thought, sentence, or natural laugh. NEVER cut off mid-word or mid-sentence!\\n\\n' +

  '=== RULE 3: TITLES & HOOK CAPTIONS ===\\n' +
  '1. TITLE (CURIOSITY GAP — 3-4 WORDS + EMOJI):\\n' +
  '   • Tease the mystery or stakes without spoiling the ending: "He Actually Did It 💀", "My Worst Mistake 😭", "The Secret Trade 🤯".\\n' +
  '   • Under 25 characters. End with 💀, 😭, 😱, or 🤯.\\n' +
  '2. HOOK_CAPTION (TOP BANNER — 3-5 WORDS IN ALL CAPS):\\n' +
  '   • The top banner pinned at the start of the Short.\\n' +
  '   • STRICTLY 100% FACTUAL to what is happening: "I CALLED TIME OUT", "THAT DOES NOT COUNT", "HE FELL FOR IT".\\n' +
  '   • FORBIDDEN: Generic clichés ("WAIT FOR THE END", "BRO REGRETS THIS") and hallucinated clickbait ("THE HACKER EXPOSED", "SAVING THE WHOLE TEAM").\\n\\n' +

  '=== OUTPUT FORMAT ===\\n' +
  'Return strictly valid JSON only. No markdown formatting, no explanations.\\n' +
  'Output exactly ' + targetClips + ' clips:\\n' +
  jsonSchema + '\\n\\n' +
  '--- SCOUTED SNIPPETS ---\\n' +
  allSnippets;

return [{ pairedItem: { item: 0 }, json: { prompt, targetClips } }];
`,
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
try {
  streamerName = $('Config').item.json.streamer_name || "Streamer";
} catch(e) {}

let lastContent = "";
for (const item of items) {
  let content = item.json.output || item.json.text || '{}';
  lastContent = content;
  
  // 1. Clean markdown formatting
  const b3 = String.fromCharCode(96).repeat(3);
  content = content.split(b3 + 'json').join('').split(b3).join('').trim();
  
  // 2. Auto-Fix common AI JSON typos
  content = content.replace(/\\}\\}\\},\\{/g, '}},{');
  content = content.replace(/\\}\\}\\]\\}/g, '}}]}');
  content = content.replace(/\\]\\]/g, ']'); 
  content = content.replace(/\\}\\,\\]/g, '}]'); 
  
  try { 
    // 3. Try parsing the repaired JSON
    const aiData = JSON.parse(content); 
    if (aiData.clips && Array.isArray(aiData.clips)) {
      allClips = allClips.concat(aiData.clips);
    } else if (Array.isArray(aiData)) {
      allClips = allClips.concat(aiData);
    }
    continue; 
  } catch (e) {
    // 4. BULLETPROOF FALLBACK: If JSON is STILL broken, forcefully extract using Regex
    const clipBlocks = content.split(/"clip_number"\\s*:/i);
    
    if (clipBlocks.length > 1) {
        for (let i = 1; i < clipBlocks.length; i++) {
            const block = clipBlocks[i];
            
            const titleMatch = block.match(/"title"\\s*:\\s*"([^"]+)"/i);
            const hookMatch = block.match(/"hook_caption"\\s*:\\s*"([^"]+)"/i);
            const startMatch = block.match(/"start_time"\\s*:\\s*([\\d.]+)/i);
            const endMatch = block.match(/"end_time"\\s*:\\s*([\\d.]+)/i);
            const payoffMatch = block.match(/"payoff_time"\\s*:\\s*([\\d.]+)/i);
            
            if (startMatch && endMatch) {
                const s = parseFloat(startMatch[1]);
                const e = parseFloat(endMatch[1]);
                const p = payoffMatch ? parseFloat(payoffMatch[1]) : e - 4.5;
                allClips.push({
                    title: titleMatch ? titleMatch[1] : (streamerName + '_Clip_' + i),
                    hook_caption: hookMatch ? hookMatch[1] : "",
                    start_time: s,
                    end_time: e,
                    payoff_time: p
                });
            }
        }
    } else {
        // 5. TEXT FALLBACK: Super aggressive timestamp extraction
        const allTimeMatches = [...content.matchAll(/\\[([\\d\\.]+)[sS]?\\s*-\\s*([\\d\\.]+)[sS]?\\]/g)];
        if (allTimeMatches.length > 0) {
            let currentClipStart = parseFloat(allTimeMatches[0][1]);
            let currentClipEnd = parseFloat(allTimeMatches[0][2]);
            let clipCount = 1;

            for (let i = 1; i < allTimeMatches.length; i++) {
                let start = parseFloat(allTimeMatches[i][1]);
                let end = parseFloat(allTimeMatches[i][2]);
                
                if (start - currentClipEnd <= 10 && start >= currentClipStart) {
                    currentClipEnd = Math.max(currentClipEnd, end);
                } else {
                    if (currentClipEnd - currentClipStart > 2) {
                        allClips.push({
                            title: 'Extracted_Clip_' + (clipCount++),
                            hook_caption: "VIRAL MOMENT",
                            start_time: currentClipStart,
                            end_time: currentClipEnd,
                            payoff_time: Math.max(0, currentClipEnd - 4.5)
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
                    payoff_time: Math.max(0, currentClipEnd - 4.5)
                });
            }
        }
    }
  }
}

// 5. If everything completely fails, use the backup
if (allClips.length === 0) {
    return [{ pairedItem: { item: 0 }, json: { start_time: 0, end_time: 48, payoff_time: 42, title: streamerName + "_Backup_Clip", hook_caption: "INSANE MOMENT", virality_score: 0, structure_type: "Standard", DEBUG_RAW_AI: lastContent } }];
}

// 6. Format and enforce strict pacing & aftermath trimming rules
return allClips.map((clip, index) => {
    let sTime = parseFloat(clip.start_time) || 0;
    let eTime = parseFloat(clip.end_time) || (sTime + 48);
    let pTime = parseFloat(clip.payoff_time) || (eTime - 4.5);

    // ANTI-DRAG RULE: Climax must be followed by at most 4-6 seconds of aftermath
    // If the streamer spent 20+ seconds in jail reading donors, chop the trailing drag!
    if (pTime > sTime && (eTime - pTime) > 6.0) {
        eTime = Math.round((pTime + 5.0) * 10) / 10;
    }

    // PACING DURATION: Target 42s to 68s natural intake window
    let dur = eTime - sTime;
    if (dur < 40) {
        // Expand start backwards for better context setup
        sTime = Math.max(0, Math.round((eTime - 42.0) * 10) / 10);
    } else if (dur > 68) {
        // Trim earlier start or clamp end
        if (pTime > sTime && (pTime - sTime) > 55) {
            sTime = Math.round((pTime - 50.0) * 10) / 10;
        }
        eTime = Math.min(eTime, sTime + 65.0);
    }

    // Clean hook_caption fallback
    let hookCaption = (clip.hook_caption || "").trim().toUpperCase();
    if (!hookCaption || hookCaption.length < 3) {
        hookCaption = (clip.title || "").replace(/[^a-zA-Z0-9\\s]/g, "").trim().toUpperCase();
        const words = hookCaption.split(/\\s+/).slice(0, 5);
        hookCaption = words.join(" ");
    }

    return { json: {
        start_time: sTime,
        end_time: eTime,
        payoff_time: pTime,
        title: clip.title || (streamerName + '_Clip_' + (index + 1)),
        hook_caption: hookCaption,
        virality_score: clip.virality_score || 0,
        theme: clip.theme || "Gaming",
        structure_type: clip.structure_type || "Narrative Arc",
        estimated_segment: clip.estimated_vod_segment || "Unknown"
    }};
});
`,
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
  'https://www.youtube.com/@TanqR/streams',
  'https://www.youtube.com/@Sketch/streams',
  'https://www.youtube.com/@flamingo/streams',
  'https://www.youtube.com/@ItsFunneh/streams',
  'https://www.youtube.com/@MeganPlays/streams',
  'https://www.youtube.com/@Poke/streams',
  'https://www.youtube.com/@tofuu/streams',
  'https://www.youtube.com/@LeahAshe/streams',
  'https://www.youtube.com/@IBella/streams',
  'https://www.youtube.com/@MyUsernamesThis/streams',
  'https://www.youtube.com/@SharkBlox/streams',
  'https://www.youtube.com/@Chaseroony/streams',
  'https://www.youtube.com/@Folty/streams',
  'https://www.twitch.tv/kreekcraft',
  'https://www.twitch.tv/tanqr',
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
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyDqACFpgY2IsbUFoul7D62V17DPTXGkTrQ',
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
                    value: "={{ $('Scout Wait').item.json.prompt }}",
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
        this._6ExtractViralSegments.out(0).to(this.CutConcatAllSegments.in(0));
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
        this.WaitBeforeScout.out(0).to(this._1PrepareScoutPrompt.in(0));
        this._1GlobalSummaryFallback.out(0).to(this._1PrepareScoutPrompt.in(0));
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
        this.ScoutLoop.out(1).to(this.ScoutWait.in(0));
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
        this._5SplitClips.out(0).to(this.LoopClips.in(0));
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
