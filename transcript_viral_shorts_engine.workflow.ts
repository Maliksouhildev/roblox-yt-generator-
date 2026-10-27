import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Transcript Viral Shorts Engine (Roblox Edition)
// Nodes    : 7  |  Connections: 6
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                         Node type (short)
// TranscriptTrigger                     manualTrigger / webhook
// TranscriptPreProcessor                code
// GeminiViralDirector                   httpRequest
// SplitAndFilterClips                   code
// LoopClips                             splitInBatches
// TimelineMathAndSubtitles              code
// MultiSegmentAssemblyBuilder           code
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// TranscriptTrigger
//    → TranscriptPreProcessor
//      → GeminiViralDirector
//        → SplitAndFilterClips
//          → LoopClips
//            .out(1) → TimelineMathAndSubtitles
//              → MultiSegmentAssemblyBuilder
//                → LoopClips (↩ loop)
// </workflow-map>

@workflow({
    id: 'TranscriptViralShortsEngineRoblox',
    name: 'Transcript Viral Shorts Engine (Roblox Edition)',
    active: true,
    settings: { executionOrder: 'v1' },
})
export class TranscriptViralShortsEngineRobloxWorkflow {

    @node({
        id: 'trigger-01',
        name: 'Transcript Webhook & Manual Trigger',
        type: 'n8n-nodes-base.webhook',
        version: 2,
        position: [200, 300],
        webhookDescription: 'Receives full Whisper verbose_json transcript or segment array',
    })
    TranscriptTrigger = {
        httpMethod: 'POST',
        path: 'viral-shorts-transcript',
        responseMode: 'onReceived',
        options: {},
    };

    @node({
        id: 'pre-processor-02',
        name: 'Transcript Pre-Processor',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [440, 300],
    })
    TranscriptPreProcessor = {
        jsCode: `// n8n Code Node: Pre-process Whisper segments into a compact, energy-tagged transcript
// Compacts a full 1-hour stream (~12k-18k tokens) for Gemini Flash 1M context window

const inputJson = $input.first().json;

// 1. Resolve raw segments from various upstream formats
let rawSegments = inputJson.segments;

if (!rawSegments || !Array.isArray(rawSegments) || rawSegments.length === 0) {
  // If only words are provided, group words into ~4-8 word conversational segments
  const words = inputJson.words || (inputJson.x_groq && inputJson.x_groq.words) || [];
  if (words.length > 0) {
    rawSegments = [];
    let curWords = [];
    let curStart = words[0].start;
    for (let i = 0; i < words.length; i++) {
      const w = words[i];
      curWords.push(w.word);
      const next = words[i + 1];
      const gap = next ? (next.start - w.end) : 999;
      const endsSentence = /[.!?]$/.test(String(w.word || '').trim());
      if (endsSentence || curWords.length >= 8 || gap > 0.8) {
        rawSegments.push({
          start: curStart,
          end: w.end,
          text: curWords.join(' ')
        });
        curWords = [];
        if (next) curStart = next.start;
      }
    }
    if (curWords.length > 0) {
      rawSegments.push({
        start: curStart,
        end: words[words.length - 1].end,
        text: curWords.join(' ')
      });
    }
  } else if (inputJson.text) {
    // Fallback: split raw text by sentences
    const sentences = inputJson.text.match(/[^.!?]+[.!?]+/g) || [inputJson.text];
    rawSegments = sentences.map((s, idx) => ({
      start: idx * 4.5,
      end: (idx + 1) * 4.5,
      text: s.trim()
    }));
  } else {
    rawSegments = [];
  }
}

if (rawSegments.length === 0) {
  throw new Error('CRITICAL: No transcript segments or text found in input payload.');
}

// 2. Compact transcript and tag speech energy/density
const compactLines = [];
let totalWords = 0;

for (let idx = 0; idx < rawSegments.length; idx++) {
  const seg = rawSegments[idx];
  const start = parseFloat(seg.start).toFixed(1);
  const end = parseFloat(seg.end).toFixed(1);
  const duration = Math.max(0.1, seg.end - seg.start);
  const text = String(seg.text || '').trim();
  const words = text.split(/\\s+/).filter(Boolean);
  totalWords += words.length;
  const wps = (words.length / duration).toFixed(1); // Words per second

  // Flag high-intensity speech, panic, hype, repetition, or laughter
  let tag = "";
  if (wps > 5.2) {
    tag += "[HYPER_SPEED] ";
  } else if (wps > 4.2) {
    tag += "[FAST/PANIC] ";
  }

  if (/[!?]{2,}|\b(NO+|WAIT+|BRO+|WHAT+|OMG|AH+|HELP|YOO+|YO+|WHY+|LMAO+|WTF|DUDE+|STOP+|RUN+)\b/i.test(text)) {
    tag += "[HIGH_ENERGY] ";
  }

  if (/\\b(ha(ha)+|he(he)+|lol|lmao)\\b/i.test(text)) {
    tag += "[LAUGHTER] ";
  }

  // Annotate long silence / walking gaps (>10s)
  if (idx > 0 && (seg.start - rawSegments[idx - 1].end) > 10.0) {
    const gap = (seg.start - rawSegments[idx - 1].end).toFixed(0);
    compactLines.push(\`[... \${gap}s dead air / silent gameplay ...]\`);
  }

  compactLines.push(\`[\${start}s-\${end}s] \${tag}\${text}\`);
}

const fullTranscript = compactLines.join("\\n");
const masterWords = inputJson.words || (inputJson.x_groq && inputJson.x_groq.words) || [];
const streamFile = inputJson.stream_file || 'stream.mp4';
const streamerName = inputJson.streamer_name || 'Streamer';

return [{
  json: {
    full_transcript: fullTranscript,
    total_segments: rawSegments.length,
    total_words: totalWords,
    stream_file: streamFile,
    streamer_name: streamerName,
    words: masterWords
  }
}];
`,
    };

    @node({
        id: 'gemini-director-03',
        name: 'Gemini Viral Shorts Director',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [680, 300],
        credentials: { googlePalmApi: { id: '9NtnnUmLQ5Ydiu6q', name: 'Google Gemini(PaLM) Api account 2' } },
        retryOnFail: true,
        maxTries: 4,
        waitBetweenTries: 5000,
    })
    GeminiViralDirector = {
        method: 'POST',
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'googlePalmApi',
        sendHeaders: true,
        headerParameters: {
            parameters: [
                {
                    name: 'Content-Type',
                    value: 'application/json',
                },
            ],
        },
        sendBody: true,
        specifyBody: 'json',
        jsonBody: `={
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "text": "SYSTEM: You are an elite viral YouTube Shorts and TikTok director specializing in Roblox gaming livestreams.\\nYour job is to analyze this full livestream transcript and construct 5 to 8 high-retention vertical shorts (target duration: 25 to 45 seconds each).\\n\\nWHY MOST AI CLIPS FAIL (DO NOT DO THIS):\\n- Do NOT pick segments where the streamer is just explaining basic game mechanics, reading routine chat messages, or talking monotonously.\\n- Do NOT output a single continuous 40-second block if there is dead air or boring walking in the middle.\\n- Do NOT include desktop admin, Alt-Tabbing into browser/Discord, reading donor lists, or typing usernames.\\n\\nHOW TO BUILD VIRAL ROBLOX SHORTS:\\nYou must look for these viral clip archetypes:\\n1. \\"COMEDIC JUXTAPOSITION / MULTI-SEGMENT STITCH\\" (Non-Linear):\\n   - Find a moment where the streamer makes a bold claim, flexes skill, makes a promise, or sets a rule (e.g. \\"I am literally the best parkour player in this server\\", \\"Watch this 200 IQ play\\", \\"If I die here I gift a sub\\").\\n   - Scan ahead in the transcript (seconds or 30 minutes later!) for the ironic payoff: where they fail miserably, get betrayed, rage, or die instantly.\\n   - Stitch the Setup Segment + an optional fast Action Bridge + the Payoff Climax Segment into one cohesive 25-45s Short.\\n\\n2. \\"STANDALONE STORY / HIGH-EMOTION ARC\\" (Tightly Trimmed):\\n   - Streamer tells a hilarious, embarrassing, or emotional story, OR experiences an intense escalation of chaos in-game.\\n   - Cut out all filler pauses so the story flows at high speed.\\n\\n3. \\"FLASH FORWARD HOOK\\":\\n   - Start with a 2-second flash forward of the scream/fail as Order 1 (FLASH_FORWARD), then cut to Order 2 (SETUP_HOOK), Order 3 (ACTION_BRIDGE), and Order 4 (PAYOFF_CLIMAX).\\n\\nWHAT TO LOOK FOR IN THE TRANSCRIPT:\\n- Look for [HIGH_ENERGY] and [FAST/PANIC] tags.\\n- Look for sudden status reversals: confidence (\\"Easy\\", \\"Watch this\\", \\"Trust me\\") followed by panic (\\"Wait wait wait\\", \\"No no no\\", \\"Bro what?!\\").\\n- Cold Open Hook Rule: The very first segment (first 3s of the Short) MUST start with a punchy statement, a bold claim, a weird out-of-context quote, or peak panic.\\n\\nOUTPUT FORMAT:\\nReturn ONLY valid JSON matching this schema:\\n{\\n  \\"clips\\": [\\n    {\\n      \\"clip_id\\": \\"clip_01\\",\\n      \\"archetype\\": \\"JUXTAPOSITION_CALLBACK | STORYTELLING_ARC | CHAOS_ESCALATION | FLASH_FORWARD_HOOK\\",\\n      \\"viral_score\\": 94,\\n      \\"title_idea\\": \\"Bro thought he was a Parkour God 💀\\",\\n      \\"why_it_works\\": \\"Classic ego-to-instant-karma arc.\\",\\n      \\"total_duration_sec\\": 34.5,\\n      \\"on_screen_hook_banner\\": \\"WAIT FOR KARMA TO HIT 😭\\",\\n      \\"segments\\": [\\n        {\\n          \\"order\\": 1,\\n          \\"role\\": \\"SETUP_HOOK\\",\\n          \\"start_sec\\": 724.0,\\n          \\"end_sec\\": 736.5,\\n          \\"transcript_excerpt\\": \\"Chat, stop saying I'm gonna fall...\\",\\n          \\"transition_after\\": \\"SPONGEBOB_TIME_CARD_OR_WHIP_PAN\\",\\n          \\"visual_directive\\": \\"ZOOM_FACECAM_120\\",\\n          \\"overlay_asset_query\\": \\"confident gigachad meme overlay\\"\\n        },\\n        {\\n          \\"order\\": 2,\\n          \\"role\\": \\"ACTION_BRIDGE\\",\\n          \\"start_sec\\": 1165.0,\\n          \\"end_sec\\": 1173.0,\\n          \\"transition_after\\": \\"GLITCH_CUT\\",\\n          \\"visual_directive\\": \\"FULL_GAMEPLAY_FOCUS\\",\\n          \\"overlay_asset_query\\": \\"none\\"\\n        },\\n        {\\n          \\"order\\": 3,\\n          \\"role\\": \\"PAYOFF_CLIMAX\\",\\n          \\"start_sec\\": 1182.0,\\n          \\"end_sec\\": 1196.0,\\n          \\"transition_after\\": \\"NONE\\",\\n          \\"visual_directive\\": \\"SHAKE_AND_RED_TINT\\",\\n          \\"overlay_asset_query\\": \\"roblox oof death skull emoji\\"\\n        }\\n      ]\\n    }\\n  ]\\n}\\n\\n--- FULL TRANSCRIPT ---\\n" + $json.full_transcript
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.2,
    "responseMimeType": "application/json"
  }
}`,
    };

    @node({
        id: 'split-filter-04',
        name: 'Split & Filter Viral Clips',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [920, 300],
    })
    SplitAndFilterClips = {
        jsCode: `// Parses Gemini EDL output, validates micro-segments, and enforces strict duration rules
const firstItem = $input.first().json;
let rawText = "";

try {
  if (firstItem.candidates && firstItem.candidates[0] && firstItem.candidates[0].content && firstItem.candidates[0].content.parts) {
    rawText = firstItem.candidates[0].content.parts[0].text || "";
  } else if (firstItem.output || firstItem.text) {
    rawText = firstItem.output || firstItem.text || "";
  } else {
    rawText = JSON.stringify(firstItem);
  }
} catch(e) {
  rawText = "{}";
}

// 1. Strip markdown code fences
let clean = rawText.replace(/^\\\`\\\`\\\`[a-z]*\\s*/i, '').replace(/\\s*\\\`\\\`\\\`$/i, '').trim();
clean = clean.replace(/,\\s*([}\\]])/g, '$1'); // Auto-fix trailing commas

let parsed = null;
try {
  parsed = JSON.parse(clean);
} catch(e) {
  // Regex recovery
  const clipRegex = /\\{[\\s\\S]*?"clip_id"[\\s\\S]*?"segments"\\s*:\\s*\\[[\\s\\S]*?\\]\\s*\\}/gi;
  const matches = clean.match(clipRegex);
  if (matches && matches.length > 0) {
    parsed = { clips: [] };
    for (const m of matches) {
      try { parsed.clips.push(JSON.parse(m.replace(/,\\s*([}\\]])/g, '$1'))); } catch(e2) {}
    }
  }
}

if (!parsed || !Array.isArray(parsed.clips) || parsed.clips.length === 0) {
  throw new Error('CRITICAL: Failed to parse valid clips array from Gemini output. Raw: ' + rawText.substring(0, 300));
}

// Upstream metadata passthrough
const preProc = $('Transcript Pre-Processor').first().json;
const streamFile = preProc.stream_file || 'stream.mp4';
const streamerName = preProc.streamer_name || 'Streamer';
const masterWords = preProc.words || [];

const validClips = [];

for (const c of parsed.clips) {
  if (!c || !Array.isArray(c.segments) || c.segments.length === 0) continue;
  const score = parseInt(c.viral_score, 10) || 75;

  // Filter segments with valid timestamps
  const segs = c.segments
    .filter(s => typeof s.start_sec === 'number' && typeof s.end_sec === 'number' && s.end_sec > s.start_sec)
    .sort((a, b) => (a.order || 0) - (b.order || 0));

  if (segs.length === 0) continue;

  // Calculate actual duration
  let dur = segs.reduce((sum, s) => sum + (s.end_sec - s.start_sec), 0);
  const payoff = segs.find(s => s.role === 'PAYOFF_CLIMAX');
  if (payoff) dur += 1.5; // +1.5s ragdoll aftermath padding

  // Enforce viral duration window: 20s to 55s
  if (dur >= 18 && dur <= 58) {
    validClips.push({
      clip_id: c.clip_id || ('clip_' + (validClips.length + 1)),
      archetype: c.archetype || 'COMEDIC_JUXTAPOSITION',
      viral_score: score,
      title_idea: c.title_idea || (streamerName + ' Moment 💀'),
      why_it_works: c.why_it_works || 'High-retention moment',
      total_duration_sec: Math.round(dur * 10) / 10,
      on_screen_hook_banner: (c.on_screen_hook_banner || c.title_idea || '').toUpperCase().trim(),
      segments: segs,
      stream_file: streamFile,
      streamer_name: streamerName,
      master_words: masterWords
    });
  }
}

// Keep clips with viral_score >= 80, or top 5 clips
let outputClips = validClips.filter(c => c.viral_score >= 80);
if (outputClips.length === 0) {
  outputClips = validClips.slice(0, 5);
}

return outputClips.map(clip => ({ json: clip }));
`,
    };

    @node({
        id: 'loop-clips-05',
        name: 'Loop Clips',
        type: 'n8n-nodes-base.splitInBatches',
        version: 3,
        position: [1140, 300],
    })
    LoopClips = {
        options: {},
    };

    @node({
        id: 'timeline-math-06',
        name: 'Timeline Math & Hormozi Subtitles',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1360, 360],
    })
    TimelineMathAndSubtitles = {
        jsCode: `// n8n Code Node: Timeline Math & Hormozi-Style ASS Subtitles
// Re-aligns original Whisper word timestamps across non-adjacent stitched segments (NO re-whisper needed!)

const clip = $input.first().json;
const segments = [...clip.segments].sort((a, b) => a.order - b.order);
const allWords = clip.master_words || [];

let currentTimeline = 0;
const stitchedSegments = [];
const alignedWords = [];

for (let i = 0; i < segments.length; i++) {
  const seg = segments[i];
  let startSec = Math.max(0, parseFloat(seg.start_sec));
  let endSec = Math.max(startSec + 0.5, parseFloat(seg.end_sec));

  // Add +1.5s padding to PAYOFF_CLIMAX so ragdoll / respawn screen is captured
  if (seg.role === "PAYOFF_CLIMAX") {
    endSec += 1.5;
  }

  const segDuration = endSec - startSec;
  const timelineStart = currentTimeline;
  const timelineEnd = currentTimeline + segDuration;

  stitchedSegments.push({
    order: seg.order,
    role: seg.role,
    source_start: startSec,
    source_end: endSec,
    duration: segDuration,
    timeline_start: timelineStart,
    timeline_end: timelineEnd,
    transition_after: seg.transition_after || "NONE",
    visual_directive: seg.visual_directive || "FULL_GAMEPLAY_FOCUS",
    overlay_asset_query: seg.overlay_asset_query || "none"
  });

  // Re-align Whisper words in this segment to the new stitched timeline
  const segWords = allWords.filter(w => w.end >= startSec && w.start <= endSec);
  segWords.forEach(w => {
    const relStart = Math.max(0, w.start - startSec);
    const relEnd = Math.max(relStart + 0.1, w.end - startSec);
    alignedWords.push({
      word: String(w.word || "").trim(),
      start: timelineStart + relStart,
      end: Math.min(timelineEnd, timelineStart + relEnd),
      role: seg.role
    });
  });

  currentTimeline = timelineEnd;
}

// Generate Hormozi-style ASS subtitle content
const FONT_SIZE = 48;
const MAIN_COLOR = "&HFFFFFF&";
const subY = 1040; // bottom center for 9:16
const captionY = 95;  // top banner zone

function formatTimeASS(seconds) {
  const sTotal = Math.max(0, parseFloat(seconds) || 0);
  const h = Math.floor(sTotal / 3600);
  const m = Math.floor((sTotal % 3600) / 60);
  const s = Math.floor(sTotal % 60);
  const cs = Math.floor((sTotal % 1) * 100);
  return \`\${h}:\${String(m).padStart(2, '0')}:\${String(s).padStart(2, '0')}.\${String(cs).padStart(2, '0')}\`;
}

let assContent = '[Script Info]\\n' +
  'ScriptType: v4.00+\\n' +
  'PlayResX: 720\\n' +
  'PlayResY: 1280\\n' +
  '[V4+ Styles]\\n' +
  'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\\n' +
  \`Style: ViralSubs,Lilita One,\${FONT_SIZE},\${MAIN_COLOR},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\\n\` +
  'Style: ViralCaption,Lilita One,42,&H00D7FF&,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\\n' +
  '[Events]\\n' +
  'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\\n';

// Persistent Top Hook Banner
const hookBanner = (clip.on_screen_hook_banner || clip.title_idea || "").toUpperCase();
if (hookBanner) {
  assContent += \`Dialogue: 2,0:00:00.00,\${formatTimeASS(currentTimeline)},ViralCaption,,0,0,0,,{\\\\pos(360,\${captionY})\\\\t(0,80,\\\\fscx108\\\\fscy108)\\\\t(80,180,\\\\fscx100\\\\fscy100)}\${hookBanner}\\n\`;
}

// Active word-level highlighting with pop-in scale transforms
if (alignedWords.length > 0) {
  const PAUSE_BREAK = 0.40;
  const MAX_CHARS = 16;
  const MAX_WORDS = 4;
  const PUNCT_RE = /[.!?,;:]$/;

  const groups = [];
  let current = [];

  for (let i = 0; i < alignedWords.length; i++) {
    const w = alignedWords[i];
    if (!w.word) continue;
    current.push(w);

    const currentChars = current.reduce((s, x) => s + x.word.length, 0);
    const nextW = alignedWords[i + 1];
    const gapToNext = nextW ? (nextW.start - w.end) : 9999;
    const endsPhrase = PUNCT_RE.test(w.word);

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

    for (let j = 0; j < group.length; j++) {
      const wStart = Math.max(cStart, group[j].start);
      const wEnd = j < group.length - 1 ? group[j + 1].start : cEnd;

      const lineText = group.map((w, idx) => {
        const txt = w.word.toUpperCase();
        if (idx === j) {
          const colors = ["&H00FFFF&", "&H00FF00&", "&H00D7FF&"];
          const randColor = colors[txt.length % colors.length];
          return \`{\\\\c\${randColor}\\\\t(0,40,\\\\fscx115\\\\fscy115)\\\\t(40,120,\\\\fscx100\\\\fscy100)}\${txt}{\\\\c\${MAIN_COLOR}}\`;
        }
        return txt;
      }).join(" ");

      assContent += \`Dialogue: 1,\${formatTimeASS(wStart)},\${formatTimeASS(wEnd)},ViralSubs,,0,0,0,,{\\\\pos(360,\${subY})}\${lineText}\\n\`;
    }
  }
}

return [{
  json: {
    clip_id: clip.clip_id,
    title: clip.title_idea,
    hook_banner: hookBanner,
    viral_score: clip.viral_score,
    why_it_works: clip.why_it_works,
    total_duration: currentTimeline,
    stitched_segments: stitchedSegments,
    stream_file: clip.stream_file
  },
  binary: {
    data: {
      data: Buffer.from(assContent).toString('base64'),
      mimeType: 'text/plain',
      fileName: 'subs.ass'
    }
  }
}];
`,
    };

    @node({
        id: 'assembly-builder-07',
        name: 'Multi-Segment Assembly FFmpeg Builder',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1580, 360],
    })
    MultiSegmentAssemblyBuilder = {
        jsCode: `// Builds dynamic multi-segment FFmpeg assembly command with visual directives, zoom/shake, and subtitle burning
const item = $input.first().json;
const segments = item.stitched_segments || [];
const streamFile = item.stream_file || 'stream.mp4';
const title = (item.title || item.clip_id || 'roblox_short').replace(/[\\/\\\\"'<>|&;:]/g, '_').trim();
const outputFile = \`/files/outputs/\${title}.mp4\`;

let filterComplex = "";
let vStreams = "";
let aStreams = "";

segments.forEach((seg, idx) => {
  const sStart = seg.source_start.toFixed(3);
  const sEnd = seg.source_end.toFixed(3);

  // Visual Directives
  let vFilter = \`[0:v]trim=start=\${sStart}:end=\${sEnd},setpts=PTS-STARTPTS\`;
  if (seg.visual_directive === "ZOOM_FACECAM_120") {
    // 20% punch-in zoom for punchline or bold flex
    vFilter += \`,scale=trunc(iw*1.20/2)*2:-1,crop=iw/1.2:ih/1.2:(iw-ow)/2:(ih-oh)/2\`;
  } else if (seg.visual_directive === "SHAKE_AND_RED_TINT") {
    // Camera shake and color punch for rage / climax
    vFilter += \`,crop=in_w-16:in_h-16:8+sin(t*25)*8:8+cos(t*20)*8,eq=saturation=1.25\`;
  }
  vFilter += \`[v\${idx}];\`;
  filterComplex += vFilter;

  // Audio trim
  filterComplex += \`[0:a]atrim=start=\${sStart}:end=\${sEnd},asetpts=PTS-STARTPTS[a\${idx}];\`;
  vStreams += \`[v\${idx}]\`;
  aStreams += \`[a\${idx}]\`;
});

// Concatenate micro-segments
filterComplex += \`\${vStreams}concat=n=\${segments.length}:v=1:a=0[v_cat];\`;
filterComplex += \`\${aStreams}concat=n=\${segments.length}:v=0:a=1[a_cat];\`;

// Scale to 720x1280 (9:16 vertical) and burn Hormozi ASS subtitles
filterComplex += \`[v_cat]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2:(ih-oh)/2,ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v_final]\`;

const cmd = \`mkdir -p /files/outputs /files/temp && ffmpeg -loglevel error -y -i "/files/inputs/\${streamFile}" -filter_complex "\${filterComplex}" -map "[v_final]" -map "[a_cat]" -c:v libx264 -preset fast -crf 17 -c:a aac -b:a 192k -movflags +faststart "\${outputFile}"\`;

return [{
  json: {
    command: cmd,
    title: item.title,
    output_file: outputFile,
    total_duration: item.total_duration,
    segments_count: segments.length
  }
}];
`,
    };

    @links()
    defineRouting() {
        this.TranscriptTrigger.out(0).to(this.TranscriptPreProcessor.in(0));
        this.TranscriptPreProcessor.out(0).to(this.GeminiViralDirector.in(0));
        this.GeminiViralDirector.out(0).to(this.SplitAndFilterClips.in(0));
        this.SplitAndFilterClips.out(0).to(this.LoopClips.in(0));
        this.LoopClips.out(1).to(this.TimelineMathAndSubtitles.in(0));
        this.TimelineMathAndSubtitles.out(0).to(this.MultiSegmentAssemblyBuilder.in(0));
        this.MultiSegmentAssemblyBuilder.out(0).to(this.LoopClips.in(0));
    }
}
