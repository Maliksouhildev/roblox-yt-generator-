// Test harness for Transcript Pre-Processor, Timeline Math, and Hormozi Subtitles
const assert = require('assert');

// 1. Mock Raw Whisper Segments from a 1-hour Roblox Livestream
const mockWhisperData = {
  text: "Chat today we are beating Tower of Hell blindfolded. Easy win. Wait what? NO NO NO! Bro what is that?!",
  segments: [
    {
      id: 0,
      start: 724.0,
      end: 730.5,
      text: " Chat stop saying I am gonna fall. I literally beat Tower of Hell blindfolded.",
      words: [
        { word: "Chat", start: 724.0, end: 724.4 },
        { word: "stop", start: 724.5, end: 724.8 },
        { word: "saying", start: 724.9, end: 725.3 },
        { word: "I", start: 725.4, end: 725.6 },
        { word: "am", start: 725.7, end: 725.9 },
        { word: "gonna", start: 726.0, end: 726.3 },
        { word: "fall.", start: 726.4, end: 726.8 },
        { word: "I", start: 727.2, end: 727.4 },
        { word: "literally", start: 727.5, end: 728.0 },
        { word: "beat", start: 728.1, end: 728.4 },
        { word: "Tower", start: 728.5, end: 728.8 },
        { word: "of", start: 728.9, end: 729.0 },
        { word: "Hell", start: 729.1, end: 729.4 },
        { word: "blindfolded.", start: 729.5, end: 730.4 }
      ]
    },
    {
      id: 1,
      start: 731.0,
      end: 736.0,
      text: " Watch this 200 IQ skip on the laser stage. Easy.",
      words: [
        { word: "Watch", start: 731.0, end: 731.4 },
        { word: "this", start: 731.5, end: 731.7 },
        { word: "200", start: 731.8, end: 732.2 },
        { word: "IQ", start: 732.3, end: 732.6 },
        { word: "skip", start: 732.7, end: 733.1 },
        { word: "on", start: 733.2, end: 733.4 },
        { word: "the", start: 733.5, end: 733.7 },
        { word: "laser", start: 733.8, end: 734.2 },
        { word: "stage.", start: 734.3, end: 734.8 },
        { word: "Easy.", start: 735.1, end: 735.8 }
      ]
    },
    // Dead air gap (736.0 to 1165.0) -> streamer walking / reading chat
    {
      id: 2,
      start: 1165.0,
      end: 1172.5,
      text: " Okay we made it to section 5. Just gotta jump right here.",
      words: [
        { word: "Okay", start: 1165.0, end: 1165.4 },
        { word: "we", start: 1165.5, end: 1165.7 },
        { word: "made", start: 1165.8, end: 1166.1 },
        { word: "it", start: 1166.2, end: 1166.4 },
        { word: "to", start: 1166.5, end: 1166.7 },
        { word: "section", start: 1166.8, end: 1167.3 },
        { word: "5.", start: 1167.4, end: 1167.8 },
        { word: "Just", start: 1168.5, end: 1168.8 },
        { word: "gotta", start: 1168.9, end: 1169.2 },
        { word: "jump", start: 1169.3, end: 1169.7 },
        { word: "right", start: 1169.8, end: 1170.1 },
        { word: "here.", start: 1170.2, end: 1170.7 }
      ]
    },
    // Another jump to climax at 1182.0
    {
      id: 3,
      start: 1182.0,
      end: 1187.0,
      text: " WAIT WAIT WAIT NO NO NO! BRO WHAT?! HOW DID THAT HIT ME?!",
      words: [
        { word: "WAIT", start: 1182.0, end: 1182.4 },
        { word: "WAIT", start: 1182.5, end: 1182.8 },
        { word: "WAIT", start: 1182.9, end: 1183.3 },
        { word: "NO", start: 1183.4, end: 1183.7 },
        { word: "NO", start: 1183.8, end: 1184.1 },
        { word: "NO!", start: 1184.2, end: 1184.6 },
        { word: "BRO", start: 1184.8, end: 1185.2 },
        { word: "WHAT?!", start: 1185.3, end: 1185.8 },
        { word: "HOW", start: 1185.9, end: 1186.1 },
        { word: "DID", start: 1186.2, end: 1186.4 },
        { word: "THAT", start: 1186.5, end: 1186.7 },
        { word: "HIT", start: 1186.8, end: 1187.0 },
        { word: "ME?!", start: 1187.1, end: 1187.5 }
      ]
    },
    {
      id: 4,
      start: 1187.2,
      end: 1195.0,
      text: " I fell all the way back to the start! LMAO NO WAY!",
      words: [
        { word: "I", start: 1187.6, end: 1187.8 },
        { word: "fell", start: 1187.9, end: 1188.3 },
        { word: "all", start: 1188.4, end: 1188.6 },
        { word: "the", start: 1188.7, end: 1188.9 },
        { word: "way", start: 1189.0, end: 1189.3 },
        { word: "back", start: 1189.4, end: 1189.7 },
        { word: "to", start: 1189.8, end: 1190.0 },
        { word: "the", start: 1190.1, end: 1190.3 },
        { word: "start!", start: 1190.4, end: 1191.0 },
        { word: "LMAO", start: 1191.5, end: 1192.1 },
        { word: "NO", start: 1192.2, end: 1192.5 },
        { word: "WAY!", start: 1192.6, end: 1193.2 }
      ]
    }
  ]
};

// Flatten all words into master words array
const masterWords = [];
mockWhisperData.segments.forEach(s => {
  if (s.words) masterWords.push(...s.words);
});

// --- Test Step 1: Pre-Processor Function ---
function preProcessTranscript(rawSegments) {
  const compactLines = rawSegments.map((seg, idx) => {
    const start = seg.start.toFixed(1);
    const end = seg.end.toFixed(1);
    const duration = Math.max(0.1, seg.end - seg.start);
    const text = seg.text.trim();
    const words = text.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    const wps = (wordCount / duration).toFixed(1);

    let tag = "";
    if (wps > 5.5) tag += "[HYPER_SPEED] ";
    else if (wps > 4.0) tag += "[FAST/PANIC] ";

    if (/[!?]{2,}|\b(NO+|WAIT+|BRO+|WHAT+|OMG|AH+|HELP|YOO+|YO+|WHY+|LMAO+|WTF|DUDE+|STOP+|RUN+)\b/i.test(text)) {
      tag += "[HIGH_ENERGY] ";
    }
    if (/\b(ha(ha)+|he(he)+|lol|lmao)\b/i.test(text)) {
      tag += "[LAUGHTER] ";
    }

    if (idx > 0 && (seg.start - rawSegments[idx - 1].end) > 10.0) {
      const gap = (seg.start - rawSegments[idx - 1].end).toFixed(0);
      return `[... ${gap}s gameplay / dead air ...]\n[${start}s-${end}s] ${tag}${text}`;
    }

    return `[${start}s-${end}s] ${tag}${text}`;
  });

  return compactLines.join("\n");
}

const preprocessed = preProcessTranscript(mockWhisperData.segments);
console.log("=== PREPROCESSED TRANSCRIPT OUTPUT ===");
console.log(preprocessed);

assert(preprocessed.includes("[HIGH_ENERGY]"), "Must detect [HIGH_ENERGY]");
assert(preprocessed.includes("[... 429s gameplay / dead air ...]"), "Must detect large dead air gaps");

// --- Test Step 2: Simulated Gemini EDL Output ---
const simulatedGeminiOutput = {
  clips: [
    {
      clip_id: "clip_01",
      archetype: "JUXTAPOSITION_CALLBACK",
      viral_score: 95,
      title_idea: "Bro thought he was a Parkour God 💀",
      why_it_works: "Classic ego claim at minute 12 followed by catastrophic rage fail at minute 19.",
      total_duration_sec: 32.5,
      on_screen_hook_banner: "WAIT FOR KARMA TO HIT 😭",
      segments: [
        {
          order: 1,
          role: "SETUP_HOOK",
          start_sec: 724.0,
          end_sec: 736.0,
          transcript_excerpt: "Chat stop saying I am gonna fall. I literally beat Tower of Hell blindfolded. Watch this 200 IQ skip on the laser stage. Easy.",
          transition_after: "WHIP_PAN",
          visual_directive: "ZOOM_FACECAM_120",
          overlay_asset_query: "confident gigachad meme overlay"
        },
        {
          order: 2,
          role: "ACTION_BRIDGE",
          start_sec: 1165.0,
          end_sec: 1172.0,
          transcript_excerpt: "Okay we made it to section 5. Just gotta jump right here.",
          transition_after: "GLITCH_CUT",
          visual_directive: "FULL_GAMEPLAY_FOCUS",
          overlay_asset_query: "none"
        },
        {
          order: 3,
          role: "PAYOFF_CLIMAX",
          start_sec: 1182.0,
          end_sec: 1195.0,
          transcript_excerpt: "WAIT WAIT WAIT NO NO NO! BRO WHAT?! HOW DID THAT HIT ME?! I fell all the way back to the start! LMAO NO WAY!",
          transition_after: "NONE",
          visual_directive: "SHAKE_AND_RED_TINT",
          overlay_asset_query: "roblox oof death skull emoji"
        }
      ]
    }
  ]
};

// --- Test Step 3: Timeline Math & Hormozi Subtitles Function ---
function computeTimelineAndSubtitles(clip, allWords, hasCam = false) {
  const segments = [...clip.segments].sort((a, b) => a.order - b.order);
  let currentTimeline = 0;
  const stitchedSegments = [];
  const alignedWords = [];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    let startSec = Math.max(0, parseFloat(seg.start_sec));
    let endSec = Math.max(startSec + 0.5, parseFloat(seg.end_sec));

    // Pad payoff climax by +1.5s for comedic ragdoll/aftermath timing
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

  // Generate Hormozi-style .ass subtitles
  const FONT_SIZE = 48;
  const MAIN_COLOR = "&HFFFFFF&";
  const subY = hasCam ? 460 : 1040;
  const captionY = hasCam ? 70 : 95;

  function formatTimeASS(seconds) {
    const sTotal = Math.max(0, parseFloat(seconds) || 0);
    const h = Math.floor(sTotal / 3600);
    const m = Math.floor((sTotal % 3600) / 60);
    const s = Math.floor(sTotal % 60);
    const cs = Math.floor((sTotal % 1) * 100);
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
  }

  let assContent = '[Script Info]\n' +
    'ScriptType: v4.00+\n' +
    'PlayResX: 720\n' +
    'PlayResY: 1280\n' +
    '[V4+ Styles]\n' +
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n' +
    `Style: ViralSubs,Lilita One,${FONT_SIZE},${MAIN_COLOR},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\n` +
    'Style: ViralCaption,Lilita One,42,&H00D7FF&,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,20,20,10,1\n' +
    '[Events]\n' +
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n';

  // Persistent Top Hook Banner
  const hookBanner = (clip.on_screen_hook_banner || clip.title_idea || "").toUpperCase();
  if (hookBanner) {
    assContent += `Dialogue: 2,0:00:00.00,${formatTimeASS(currentTimeline)},ViralCaption,,0,0,0,,{\\pos(360,${captionY})\\t(0,80,\\fscx108\\fscy108)\\t(80,180,\\fscx100\\fscy100)}${hookBanner}\n`;
  }

  // Active word-level highlighting
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
            return `{\\c${randColor}\\t(0,40,\\fscx115\\fscy115)\\t(40,120,\\fscx100\\fscy100)}${txt}{\\c${MAIN_COLOR}}`;
          }
          return txt;
        }).join(" ");

        assContent += `Dialogue: 1,${formatTimeASS(wStart)},${formatTimeASS(wEnd)},ViralSubs,,0,0,0,,{\\pos(360,${subY})}${lineText}\n`;
      }
    }
  }

  return {
    stitchedSegments,
    alignedWords,
    totalDuration: currentTimeline,
    assContent
  };
}

const result = computeTimelineAndSubtitles(simulatedGeminiOutput.clips[0], masterWords, false);

console.log("=== TIMELINE RESULT ===");
console.log("Stitched segments count:", result.stitchedSegments.length);
console.log("Total timeline duration:", result.totalDuration.toFixed(2), "seconds");
console.log("Aligned words count:", result.alignedWords.length);
console.log("\nSample ASS Subtitle Content:\n" + result.assContent.substring(0, 800) + "...\n");

assert.equal(result.stitchedSegments.length, 3, "Must have 3 stitched segments");
assert(result.totalDuration >= 25 && result.totalDuration <= 45, "Total duration must be within 25-45s");
assert(result.alignedWords.length > 20, "Words must be aligned successfully");
assert(result.assContent.includes("WAIT FOR KARMA TO HIT"), "Must include top banner caption");

console.log("ALL TESTS PASSED SUCCESSFULLY!");

// --- Test Step 4: Edge Cases for Pre-Processor ---
console.log("\n=== TESTING EDGE CASES ===");

// Edge Case 1: Empty segments array -> should return empty or fallback gracefully
const emptyRes = preProcessTranscript([]);
assert.equal(emptyRes, "", "Empty input must return empty string");

// Edge Case 2: Whisper with ONLY words (no segments array)
function preProcessFromWordsOrSegments(whisperData) {
  let segments = whisperData.segments;
  if (!segments || !Array.isArray(segments) || segments.length === 0) {
    // Reconstruct segments from words!
    const words = whisperData.words || (whisperData.x_groq && whisperData.x_groq.words) || [];
    if (words.length > 0) {
      segments = [];
      let curWords = [];
      let curStart = words[0].start;
      for (let i = 0; i < words.length; i++) {
        const w = words[i];
        curWords.push(w.word);
        const next = words[i + 1];
        const gap = next ? (next.start - w.end) : 999;
        const endsSent = /[.!?]$/.test(w.word.trim());
        if (endsSent || curWords.length >= 8 || gap > 0.8) {
          segments.push({
            start: curStart,
            end: w.end,
            text: curWords.join(" ")
          });
          curWords = [];
          if (next) curStart = next.start;
        }
      }
      if (curWords.length > 0) {
        segments.push({
          start: curStart,
          end: words[words.length - 1].end,
          text: curWords.join(" ")
        });
      }
    } else if (whisperData.text) {
      // Last resort: split raw text by sentences
      const sentences = whisperData.text.match(/[^.!?]+[.!?]+/g) || [whisperData.text];
      segments = sentences.map((s, idx) => ({
        start: idx * 5.0,
        end: (idx + 1) * 5.0,
        text: s.trim()
      }));
    } else {
      segments = [];
    }
  }
  return preProcessTranscript(segments);
}

const wordsOnlyInput = {
  words: [
    { word: "Bro,", start: 10.0, end: 10.4 },
    { word: "look", start: 10.5, end: 10.8 },
    { word: "at", start: 10.9, end: 11.0 },
    { word: "this!", start: 11.1, end: 11.5 },
    { word: "OMG!", start: 13.0, end: 13.6 }
  ]
};

const wordsOnlyRes = preProcessFromWordsOrSegments(wordsOnlyInput);
console.log("Words-only reconstruct output:\n", wordsOnlyRes);
assert(wordsOnlyRes.includes("[10.0s-11.5s]"), "Must group words into segment");
assert(wordsOnlyRes.includes("[HIGH_ENERGY]"), "Must detect OMG as high energy");

// Edge Case 3: EDL Parser resilience (markdown backticks, trailing commas, scores)
function parseAndFilterEdl(rawAiContent, minScore = 80) {
  let content = String(rawAiContent || "").trim();
  // Strip markdown code fences
  content = content.replace(/^```[a-z]*\s*/i, '').replace(/\s*```$/i, '').trim();

  // Auto-fix common LLM JSON syntax errors (trailing commas)
  content = content.replace(/,\s*([}\]])/g, '$1');

  let parsed = null;
  try {
    parsed = JSON.parse(content);
  } catch (e) {
    // Regex recovery for clips array
    const clipRegex = /\{[\s\S]*?"clip_id"[\s\S]*?"segments"\s*:\s*\[[\s\S]*?\]\s*\}/gi;
    const matches = content.match(clipRegex);
    if (matches && matches.length > 0) {
      parsed = { clips: [] };
      for (const m of matches) {
        try {
          parsed.clips.push(JSON.parse(m.replace(/,\s*([}\]])/g, '$1')));
        } catch (e2) {}
      }
    }
  }

  if (!parsed || !Array.isArray(parsed.clips)) {
    return [];
  }

  const validClips = [];
  for (const c of parsed.clips) {
    if (!c || !Array.isArray(c.segments) || c.segments.length === 0) continue;
    const score = parseInt(c.viral_score, 10) || 75;
    if (score < minScore && validClips.length >= 3) continue; // Keep top ones if not enough

    // Sort segments
    const segs = c.segments
      .filter(s => typeof s.start_sec === 'number' && typeof s.end_sec === 'number' && s.end_sec > s.start_sec)
      .sort((a, b) => (a.order || 0) - (b.order || 0));

    if (segs.length === 0) continue;

    // Check duration
    let dur = segs.reduce((sum, s) => sum + (s.end_sec - s.start_sec), 0);
    // Add payoff padding (+1.5s)
    const payoff = segs.find(s => s.role === 'PAYOFF_CLIMAX');
    if (payoff) dur += 1.5;

    // Durations between 20s and 50s are acceptable
    if (dur >= 18 && dur <= 55) {
      validClips.push({
        ...c,
        total_duration_sec: Math.round(dur * 10) / 10,
        segments: segs
      });
    }
  }

  return validClips;
}

const rawAiWithMarkdownAndTrailingComma = "```json\n" + JSON.stringify(simulatedGeminiOutput).replace('}]}', '},]}') + "\n```";
const parsedClips = parseAndFilterEdl(rawAiWithMarkdownAndTrailingComma);
assert.equal(parsedClips.length, 1, "Must successfully parse markdown-fenced and trailing comma JSON");
assert.equal(parsedClips[0].clip_id, "clip_01");

// --- Test Step 5: Multi-Segment Assembly & FFmpeg Filter Builder ---
function buildFFmpegRenderCommand(clip, streamFile, timelineData, camConfig = { ai_found: false }) {
  const segments = timelineData.stitchedSegments;
  const hasCam = !!(camConfig && camConfig.ai_found);
  const title = (clip.title_idea || clip.clip_id || "short_clip").replace(/[\/\\"'<>|&;:]/g, '_').trim();
  const outputFile = `/files/outputs/${title}.mp4`;

  let filterComplex = "";
  let vStreams = "";
  let aStreams = "";

  segments.forEach((seg, idx) => {
    const sStart = seg.source_start.toFixed(3);
    const sEnd = seg.source_end.toFixed(3);

    // Visual Directives
    let vFilter = `[0:v]trim=start=${sStart}:end=${sEnd},setpts=PTS-STARTPTS`;
    if (seg.visual_directive === "ZOOM_FACECAM_120") {
      // 20% punch in zoom
      vFilter += `,scale=trunc(iw*1.20/2)*2:-1,crop=iw/1.2:ih/1.2:(iw-ow)/2:(ih-oh)/2`;
    } else if (seg.visual_directive === "SHAKE_AND_RED_TINT") {
      // Subtle shake + saturation
      vFilter += `,crop=in_w-16:in_h-16:8+sin(t*25)*8:8+cos(t*20)*8,eq=saturation=1.25`;
    }
    vFilter += `[v${idx}];`;
    filterComplex += vFilter;

    // Audio trim
    filterComplex += `[0:a]atrim=start=${sStart}:end=${sEnd},asetpts=PTS-STARTPTS[a${idx}];`;
    vStreams += `[v${idx}]`;
    aStreams += `[a${idx}]`;
  });

  // Concat all trimmed micro-segments
  filterComplex += `${vStreams}concat=n=${segments.length}:v=1:a=0[v_cat];`;
  filterComplex += `${aStreams}concat=n=${segments.length}:v=0:a=1[a_cat];`;

  // Scale to 720:1280 (9:16 vertical) and burn ASS subtitles
  if (hasCam) {
    const cwRatio = (camConfig.cam_w / 1920).toFixed(4);
    const chRatio = (camConfig.cam_h / 1080).toFixed(4);
    const cxRatio = (camConfig.cam_x / 1920).toFixed(4);
    const cyRatio = (camConfig.cam_y / 1080).toFixed(4);

    filterComplex += `[v_cat]split=2[v_split_cam][v_split_game];`;
    filterComplex += `[v_split_cam]crop=trunc(iw*${cwRatio}/2)*2:trunc(ih*${chRatio}/2)*2:trunc(iw*${cxRatio}/2)*2:trunc(ih*${cyRatio}/2)*2,scale=720:460:force_original_aspect_ratio=increase,crop=720:460:(iw-ow)/2:(ih-oh)/2[cam_box];`;
    filterComplex += `[v_split_game]crop='trunc(min(iw,ih*0.88)/2)*2':'trunc(ih/2)*2':(iw-ow)/2:0,scale=720:820[game_box];`;
    filterComplex += `color=c=black:s=720x1280:d=${timelineData.totalDuration.toFixed(2)}[bg_canvas];`;
    filterComplex += `[bg_canvas][cam_box]overlay=0:0[layer1];`;
    filterComplex += `[layer1][game_box]overlay=0:460[layer2];`;
    filterComplex += `[layer2]drawbox=x=0:y=457:w=720:h=6:color=white:t=fill,ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v_final]`;
  } else {
    // Cinema full frame 720x1280
    filterComplex += `[v_cat]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2:(ih-oh)/2,ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v_final]`;
  }

  const cmd = `ffmpeg -loglevel error -y -i "/files/inputs/${streamFile}" -filter_complex "${filterComplex}" -map "[v_final]" -map "[a_cat]" -c:v libx264 -preset fast -crf 17 -c:a aac -b:a 192k -movflags +faststart "${outputFile}"`;
  return cmd;
}

const ffmpegCmd = buildFFmpegRenderCommand(parsedClips[0], "stream.mp4", result, { ai_found: false });
console.log("=== GENERATED FFMPEG COMMAND ===");
console.log(ffmpegCmd);

assert(ffmpegCmd.includes("trim=start=724.000:end=736.000"), "Must trim segment 1");
assert(ffmpegCmd.includes("trim=start=1165.000:end=1172.000"), "Must trim segment 2");
assert(ffmpegCmd.includes("trim=start=1182.000:end=1196.500"), "Must trim padded segment 3");
assert(ffmpegCmd.includes("scale=trunc(iw*1.20/2)*2:-1"), "Must apply ZOOM_FACECAM_120 directive");
assert(ffmpegCmd.includes("ass=/files/temp/subs.ass"), "Must burn ASS subtitles");

console.log("\nALL ADVANCED TESTS AND FFMPEG BUILDER PASSED!");
