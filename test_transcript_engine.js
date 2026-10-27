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
    // Dead air gap (736.0 to 1165.0) -> streamer walking / reading chat (429s)
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
    // Another jump to climax at 1182.0 (1172.5 to 1182.0 = 9.5s)
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

// Master word list
const masterWords = [];
mockWhisperData.segments.forEach(s => {
  if (s.words) masterWords.push(...s.words);
});

// --- Step 1: Pre-Processor Function ---
function preProcessTranscript(rawSegments) {
  if (!rawSegments || !Array.isArray(rawSegments) || rawSegments.length === 0) return "";
  const compactLines = [];

  for (let idx = 0; idx < rawSegments.length; idx++) {
    const seg = rawSegments[idx];
    const start = parseFloat(seg.start).toFixed(1);
    const end = parseFloat(seg.end).toFixed(1);
    const duration = Math.max(0.1, seg.end - seg.start);
    const text = String(seg.text || '').trim();
    const words = text.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    const wps = (wordCount / duration).toFixed(1);

    let tag = "";
    if (wps > 5.2) tag += "[HYPER_SPEED] ";
    else if (wps > 4.2) tag += "[FAST/PANIC] ";

    if (/[!?]{2,}|\b(NO+|WAIT+|BRO+|WHAT+|OMG|AH+|HELP|YOO+|YO+|WHY+|LMAO+|WTF|DUDE+|STOP+|RUN+)\b/i.test(text)) {
      tag += "[HIGH_ENERGY] ";
    }
    if (/\b(ha(ha)+|he(he)+|lol|lmao)\b/i.test(text)) {
      tag += "[LAUGHTER] ";
    }

    if (idx > 0 && (seg.start - rawSegments[idx - 1].end) > 10.0) {
      const gap = (seg.start - rawSegments[idx - 1].end).toFixed(0);
      compactLines.push(`[... ${gap}s dead air / silent gameplay ...]`);
    }

    compactLines.push(`[${start}-${end}] ${tag}${text}`);
  }

  return compactLines.join("\n");
}

const preprocessed = preProcessTranscript(mockWhisperData.segments);
console.log("=== PREPROCESSED TRANSCRIPT OUTPUT ===");
console.log(preprocessed);

assert(preprocessed.includes("[HIGH_ENERGY]"), "Must detect [HIGH_ENERGY]");
assert(preprocessed.includes("[... 429s dead air / silent gameplay ...]"), "Must detect large dead air gaps");
assert(preprocessed.includes("[724.0-730.5]"), "Timestamp format matches [start-end]");

// --- Step 2: Simulated Gemini EDL Output ---
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

// --- Step 3: Parse and Filter EDL Output ---
function parseAndFilterEdl(rawAiContent, minScore = 85) {
  let content = String(rawAiContent || "").trim();
  content = content.replace(/^```[a-z]*\s*/i, '').replace(/\s*```$/i, '').trim();
  content = content.replace(/,\s*([}\]])/g, '$1');

  let parsed = null;
  try {
    parsed = JSON.parse(content);
  } catch (e) {
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

  if (!parsed || !Array.isArray(parsed.clips)) return [];

  const validClips = [];
  for (const c of parsed.clips) {
    if (!c || !Array.isArray(c.segments) || c.segments.length === 0) continue;
    const score = parseInt(c.viral_score, 10) || 75;
    if (score < minScore && validClips.length >= 3) continue;

    const segs = c.segments
      .filter(s => typeof s.start_sec === 'number' && typeof s.end_sec === 'number' && s.end_sec > s.start_sec)
      .sort((a, b) => (a.order || 0) - (b.order || 0));

    if (segs.length === 0) continue;

    let dur = segs.reduce((sum, s) => sum + (s.end_sec - s.start_sec), 0);
    const payoff = segs.find(s => s.role === 'PAYOFF_CLIMAX');
    if (payoff) dur += 1.5;

    if (dur >= 18 && dur <= 55) {
      validClips.push({
        ...c,
        viral_score: score,
        total_duration_sec: Math.round(dur * 10) / 10,
        segments: segs
      });
    }
  }

  return validClips;
}

// --- Step 4: Timeline Math & Hormozi Subtitles Function ---
function computeTimelineAndSubtitles(clip, allWords, hasCam = false) {
  const segments = [...clip.segments].sort((a, b) => a.order - b.order);
  let currentTimeline = 0;
  const stitchedSegments = [];
  const alignedWords = [];
  const allGroups = [];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    let startSec = Math.max(0, parseFloat(seg.start_sec));
    let endSec = Math.max(startSec + 0.5, parseFloat(seg.end_sec));

    // Pad payoff climax by +1.5s for comedic ragdoll/aftermath timing
    if (seg.role === "PAYOFF_CLIMAX") {
      endSec += 1.5;
    }

    // Check if transition occurs before this segment (distant jump or explicit transition)
    let transitionBefore = null;
    if (i > 0) {
      const prevSeg = segments[i - 1];
      const gap = Math.abs(seg.start_sec - prevSeg.end_sec);
      const prevTransition = prevSeg.transition_after;
      if (gap > 30.0 || (prevTransition && prevTransition !== "NONE")) {
        const transDuration = 0.5;
        transitionBefore = {
          duration: transDuration,
          type: (prevTransition && prevTransition !== "NONE") ? prevTransition : "TIME_JUMP_GLITCH"
        };
        currentTimeline = Math.round((currentTimeline + transDuration) * 1000) / 1000;
      }
    }

    const segDuration = Math.round((endSec - startSec) * 1000) / 1000;
    const timelineStart = Math.round(currentTimeline * 1000) / 1000;
    const timelineEnd = Math.round((currentTimeline + segDuration) * 1000) / 1000;

    stitchedSegments.push({
      order: seg.order,
      role: seg.role,
      source_start: startSec,
      source_end: endSec,
      duration: segDuration,
      timeline_start: timelineStart,
      timeline_end: timelineEnd,
      transition_before: transitionBefore,
      transition_after: seg.transition_after || "NONE",
      visual_directive: seg.visual_directive || "FULL_GAMEPLAY_FOCUS",
      overlay_asset_query: seg.overlay_asset_query || "none"
    });

    // Re-align Whisper words in this segment
    const segWords = allWords
      .filter(w => w.end >= startSec && w.start <= endSec)
      .sort((a, b) => a.start - b.start);

    const segAligned = [];
    segWords.forEach(w => {
      const relStart = Math.max(0, w.start - startSec);
      const relEnd = Math.max(relStart + 0.08, w.end - startSec);
      const wStart = Math.round((timelineStart + relStart) * 1000) / 1000;
      const wEnd = Math.round(Math.min(timelineEnd, timelineStart + relEnd) * 1000) / 1000;
      const aligned = {
        word: String(w.word || "").trim(),
        start: wStart,
        end: Math.max(wStart + 0.08, wEnd),
        role: seg.role,
        seg_order: seg.order
      };
      segAligned.push(aligned);
      alignedWords.push(aligned);
    });

    // Group words strictly per-segment (fixes cross-cut caption contamination)
    const PAUSE_BREAK = 0.40;
    const MAX_CHARS = 16;
    const MAX_WORDS = 4;
    const PUNCT_RE = /[.!?,;:]$/;

    let current = [];
    for (let j = 0; j < segAligned.length; j++) {
      const w = segAligned[j];
      if (!w.word) continue;
      current.push(w);
      const currentChars = current.reduce((s, x) => s + x.word.length, 0);
      const nextW = segAligned[j + 1];
      const gapToNext = nextW ? (nextW.start - w.end) : 9999;
      const endsPhrase = PUNCT_RE.test(w.word);
      const shouldBreak = current.length >= MAX_WORDS || currentChars >= MAX_CHARS || gapToNext > PAUSE_BREAK || endsPhrase;
      if (shouldBreak && current.length > 0) {
        allGroups.push([...current]);
        current = [];
      }
    }
    if (current.length > 0) allGroups.push(current);

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
  for (const group of allGroups) {
    const cStart = group[0].start;
    const cEnd = group[group.length - 1].end;

    for (let j = 0; j < group.length; j++) {
      const wStart = Math.max(cStart, group[j].start);
      const wEnd = Math.max(wStart + 0.08, j < group.length - 1 ? group[j + 1].start : cEnd);

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

  return {
    stitchedSegments,
    alignedWords,
    groups: allGroups,
    totalDuration: currentTimeline,
    assContent
  };
}

// --- Step 5: Multi-Segment Assembly & FFmpeg Filter Builder ---
function buildFFmpegRenderCommand(clip, streamFile, timelineData, camConfig = { ai_found: false }) {
  const segments = timelineData.stitchedSegments;
  const hasCam = !!(camConfig && camConfig.ai_found);
  const title = (clip.title_idea || clip.clip_id || "short_clip").replace(/[\/\\"'<>|&;:]/g, '_').trim();
  const outputFile = `/files/outputs/${title}.mp4`;

  let filterComplex = "";
  let vConcatList = [];
  let aConcatList = [];

  segments.forEach((seg, idx) => {
    // 1. If there is a transition before this segment, insert transition generator into concat
    if (seg.transition_before) {
      const transV = `trans${idx}_v`;
      const transA = `trans${idx}_a`;
      // High-energy 0.5s glitch/static generator + white noise SFX
      filterComplex += `nullsrc=s=720x1280:d=0.5,geq=random(1)*255:128:128[${transV}];`;
      filterComplex += `anullsrc=r=44100:cl=stereo,atrim=d=0.5,volume=0.20[${transA}];`;
      vConcatList.push(`[${transV}]`);
      aConcatList.push(`[${transA}]`);
    }

    const sStart = seg.source_start.toFixed(3);
    const sEnd = seg.source_end.toFixed(3);
    const segDur = seg.duration;

    // 2. Video Trim & Visual Directives
    let vFilter = `[0:v]trim=start=${sStart}:end=${sEnd},setpts=PTS-STARTPTS`;
    if (seg.visual_directive === "ZOOM_FACECAM_120") {
      vFilter += `,scale=trunc(iw*1.20/2)*2:-1,crop=iw/1.2:ih/1.2:(iw-ow)/2:(ih-oh)/2`;
    } else if (seg.visual_directive === "SHAKE_AND_RED_TINT") {
      vFilter += `,crop=in_w-16:in_h-16:8+sin(t*25)*8:8+cos(t*20)*8,eq=saturation=1.25`;
    }
    vFilter += `[v${idx}];`;
    filterComplex += vFilter;
    vConcatList.push(`[v${idx}]`);

    // 3. Audio Trim with 0.15s anti-popping edge crossfade
    const fadeEnd = Math.max(0.08, segDur - 0.08).toFixed(3);
    let aFilter = `[0:a]atrim=start=${sStart}:end=${sEnd},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.08,afade=t=out:st=${fadeEnd}:d=0.08[a${idx}];`;
    filterComplex += aFilter;
    aConcatList.push(`[a${idx}]`);
  });

  const totalParts = vConcatList.length;
  filterComplex += `${vConcatList.join('')}concat=n=${totalParts}:v=1:a=0[v_cat];`;
  filterComplex += `${aConcatList.join('')}concat=n=${totalParts}:v=0:a=1[a_cat];`;

  // 4. Scale to 720:1280 (9:16 vertical), apply meme overlay if requested, and burn ASS subtitles
  let overlayDraw = "";
  segments.forEach(seg => {
    if (seg.overlay_asset_query && seg.overlay_asset_query !== "none") {
      const q = seg.overlay_asset_query.toLowerCase();
      let emoji = "💀";
      if (q.includes("gigachad") || q.includes("chad")) emoji = "🗿";
      else if (q.includes("clown")) emoji = "🤡";
      else if (q.includes("shock") || q.includes("scream")) emoji = "😱";
      else if (q.includes("karma") || q.includes("oof")) emoji = "😭";

      overlayDraw += `,drawtext=text='${emoji}':fontsize=72:x=(w-text_w)/2:y=180:enable='between(t,${seg.timeline_start.toFixed(2)},${(seg.timeline_start + 1.5).toFixed(2)})'`;
    }
  });

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
    filterComplex += `[layer2]drawbox=x=0:y=457:w=720:h=6:color=white:t=fill${overlayDraw},ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v_final]`;
  } else {
    filterComplex += `[v_cat]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2:(ih-oh)/2${overlayDraw},ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts[v_final]`;
  }

  const cmd = `mkdir -p /files/outputs /files/temp && ffmpeg -loglevel error -y -i "/files/inputs/${streamFile}" -filter_complex "${filterComplex}" -map "[v_final]" -map "[a_cat]" -c:v libx264 -preset fast -crf 17 -c:a aac -b:a 192k -movflags +faststart "${outputFile}"`;
  return cmd;
}

// --- RUN TESTS ---
const parsedClips = parseAndFilterEdl(JSON.stringify(simulatedGeminiOutput), 85);
assert.equal(parsedClips.length, 1, "Must parse 1 clip with viral_score >= 85");

const timelineResult = computeTimelineAndSubtitles(parsedClips[0], masterWords, false);
console.log("\n=== TIMELINE RESULT ===");
console.log("Stitched segments count:", timelineResult.stitchedSegments.length);
console.log("Total timeline duration:", timelineResult.totalDuration.toFixed(2), "seconds");
console.log("Aligned words count:", timelineResult.alignedWords.length);
console.log("Groups count:", timelineResult.groups.length);

assert.equal(timelineResult.stitchedSegments.length, 3, "Must have 3 stitched segments");
// Notice: Segment 1 (12s) + Transition 1 (0.5s) + Segment 2 (7s) + Transition 2 (0.5s) + Segment 3 (13s + 1.5s payoff pad = 14.5s) = 34.5s
assert.equal(timelineResult.totalDuration, 34.5, "Total duration must accurately include transition padding");
assert.equal(timelineResult.stitchedSegments[1].timeline_start, 12.5, "Segment 2 must start at 12.5s (after 0.5s transition)");
assert.equal(timelineResult.stitchedSegments[2].timeline_start, 20.0, "Segment 3 must start at 20.0s (after second 0.5s transition)");

const ffmpegCmd = buildFFmpegRenderCommand(parsedClips[0], "stream.mp4", timelineResult, { ai_found: false });
console.log("\n=== GENERATED FFMPEG COMMAND ===");
console.log(ffmpegCmd);

assert(ffmpegCmd.includes("trim=start=724.000:end=736.000"), "Must trim segment 1");
assert(ffmpegCmd.includes("trim=start=1165.000:end=1172.000"), "Must trim segment 2");
assert(ffmpegCmd.includes("trim=start=1182.000:end=1196.500"), "Must trim padded segment 3 (+1.5s)");
assert(ffmpegCmd.includes("scale=trunc(iw*1.20/2)*2:-1"), "Must apply ZOOM_FACECAM_120 directive");
assert(ffmpegCmd.includes("crop=in_w-16:in_h-16:8+sin(t*25)*8:8+cos(t*20)*8"), "Must apply SHAKE_AND_RED_TINT directive");
assert(ffmpegCmd.includes("afade=t=in:st=0:d=0.08"), "Must apply anti-pop audio fade in");
assert(ffmpegCmd.includes("afade=t=out"), "Must apply anti-pop audio fade out");
assert(ffmpegCmd.includes("nullsrc=s=720x1280:d=0.5,geq=random(1)*255:128:128[trans1_v]"), "Must generate transition video stream between distant segments");
assert(ffmpegCmd.includes("anullsrc=r=44100:cl=stereo,atrim=d=0.5,volume=0.20[trans1_a]"), "Must generate transition audio stream");
assert(ffmpegCmd.includes("concat=n=5:v=1:a=0[v_cat]"), "Concat must have n=5 (3 video segments + 2 transition clips)");
assert(ffmpegCmd.includes("drawtext=text='🗿'"), "Must apply gigachad meme overlay for segment 1");
assert(ffmpegCmd.includes("drawtext=text='😭'"), "Must apply oof/karma meme overlay for segment 3");
assert(ffmpegCmd.includes("ass=/files/temp/subs.ass:fontsdir=/files/inputs/fonts"), "Must burn ASS subtitles");

// --- STEP 6: Edge Case Testing (Reviewer Attack Scenarios) ---
console.log("\n=== RUNNING REVIEWER ATTACK SCENARIOS ===");

// Scenario A: Out-of-order flash-forward hook
// Segment 1 (order 1): minute 45 scream (2700s - 2701.8s)
// Segment 2 (order 2): minute 2 calm setup (120s - 123.0s)
const flashForwardClip = {
  clip_id: "flash_forward_01",
  viral_score: 96,
  title_idea: "Tower of Hell Fails",
  on_screen_hook_banner: "KARMA IS REAL 💀",
  segments: [
    {
      order: 1,
      role: "FLASH_FORWARD",
      start_sec: 2700.0,
      end_sec: 2701.8,
      transcript_excerpt: "WAIT NO NO",
      transition_after: "GLITCH_CUT",
      visual_directive: "SHAKE_AND_RED_TINT",
      overlay_asset_query: "shock"
    },
    {
      order: 2,
      role: "SETUP_HOOK",
      start_sec: 120.0,
      end_sec: 123.0,
      transcript_excerpt: "Today we play Tower of Hell",
      transition_after: "NONE",
      visual_directive: "ZOOM_FACECAM_120",
      overlay_asset_query: "none"
    }
  ]
};

const attackWords = [
  { word: "Today", start: 120.0, end: 120.4 },
  { word: "we", start: 120.5, end: 120.7 },
  { word: "play", start: 120.8, end: 121.2 },
  { word: "Tower", start: 121.3, end: 121.6 },
  { word: "of", start: 121.7, end: 121.8 },
  { word: "Hell", start: 121.9, end: 122.3 },
  { word: "WAIT", start: 2700.0, end: 2700.5 },
  { word: "NO", start: 2700.6, end: 2701.0 },
  { word: "NO", start: 2701.1, end: 2701.5 }
];

const ffRes = computeTimelineAndSubtitles(flashForwardClip, attackWords);
assert.equal(ffRes.groups.length, 3, "Must create separate subtitle groups per segment");
assert.deepEqual(ffRes.groups[0].map(w => w.word), ['WAIT', 'NO', 'NO'], "Group 0 must strictly contain flash forward scream words");
assert.deepEqual(ffRes.groups[1].map(w => w.word), ['Today', 'we', 'play', 'Tower'], "Group 1 must strictly contain setup words");
assert.equal(ffRes.stitchedSegments[1].timeline_start, 2.3, "Segment 2 must start at 2.3s after 0.5s transition");
assert.equal(ffRes.groups[1][0].start, 2.3, "Word 'Today' must start at exactly 2.3s");

// Scenario B: Words-only Whisper input fallback
function preProcessFromWordsOrSegments(whisperData) {
  let segments = whisperData.segments;
  if (!segments || !Array.isArray(segments) || segments.length === 0) {
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
        const endsSent = /[.!?]$/.test(String(w.word || '').trim());
        if (endsSent || curWords.length >= 8 || gap > 0.8) {
          segments.push({ start: curStart, end: w.end, text: curWords.join(" ") });
          curWords = [];
          if (next) curStart = next.start;
        }
      }
      if (curWords.length > 0) {
        segments.push({ start: curStart, end: words[words.length - 1].end, text: curWords.join(" ") });
      }
    } else if (whisperData.text) {
      const sentences = whisperData.text.match(/[^.!?]+[.!?]+/g) || [whisperData.text];
      segments = sentences.map((s, idx) => ({ start: idx * 5.0, end: (idx + 1) * 5.0, text: s.trim() }));
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
assert(wordsOnlyRes.includes("[10.0-11.5]"), "Words grouped into [10.0-11.5]");
assert(wordsOnlyRes.includes("[HIGH_ENERGY]"), "OMG tagged as [HIGH_ENERGY]");

console.log("\nALL TESTS, EDGE CASES, AND REVIEWER ATTACK ASSERTIONS PASSED WITH ZERO ERRORS!");
