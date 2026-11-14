const fs = require('fs');
const path = require('path');

const wfJsonPath = path.resolve(__dirname, '../workflows/workflow.json');
const wfTsPath = path.resolve(__dirname, '../workflows/workflow_bypassed.ts');

console.log('[Multimodal Injector] Reading workflow.json and workflow_bypassed.ts...');
const wf = JSON.parse(fs.readFileSync(wfJsonPath, 'utf8'));
let tsContent = fs.readFileSync(wfTsPath, 'utf8');

// 1. Add "Run Multimodal Fusion" node to workflow.json if not present
const nodeName = "Run Multimodal Fusion";
let fusionNode = wf.nodes.find(n => n.name === nodeName);
if (!fusionNode) {
  fusionNode = {
    parameters: {
      command: '=python3 /files/multimodal_analyzer.py "/files/inputs/{{ $(\'Edit Fields\').first().json.stream_file }}" "/files/temp/audio.mp3" "/files/temp/cam_config.json" "/files/temp/viral_anchors.json"'
    },
    id: "run-multimodal-fusion-id",
    name: nodeName,
    type: "n8n-nodes-base.executeCommand",
    typeVersion: 1,
    position: [-88880, 26000],
    onError: "continueRegularOutput"
  };
  wf.nodes.push(fusionNode);
  console.log('[Multimodal Injector] Added Run Multimodal Fusion node to workflow.json.');
}

// 2. Rewire connections in workflow.json
// Wait Before Scout -> Run Multimodal Fusion -> 1. Prepare Scout Prompt
// 1. Global Summary Fallback -> Run Multimodal Fusion
if (wf.connections["Wait Before Scout"]) {
  wf.connections["Wait Before Scout"].main = [[{
    node: nodeName,
    type: "main",
    index: 0
  }]];
}
if (wf.connections["1. Global Summary Fallback"]) {
  wf.connections["1. Global Summary Fallback"].main[0] = [{
    node: nodeName,
    type: "main",
    index: 0
  }];
}
wf.connections[nodeName] = {
  main: [[{
    node: "1. Prepare Scout Prompt",
    type: "main",
    index: 0
  }]]
};
console.log('[Multimodal Injector] Rewired connections in workflow.json.');

// 3. Update 1. Prepare Scout Prompt in workflow.json
const scoutNode = wf.nodes.find(n => n.name === "1. Prepare Scout Prompt");
if (scoutNode && scoutNode.parameters && scoutNode.parameters.jsCode) {
  let js = scoutNode.parameters.jsCode;
  
  if (!js.includes("Run Multimodal Fusion")) {
    const anchorExtraction = `
// ── Multimodal Viral Anchors Extraction ──────────────────────
let viralAnchors = [];
try {
  const fusionItem = $('Run Multimodal Fusion').first();
  if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
    const parsed = JSON.parse(fusionItem.json.stdout);
    if (parsed && parsed.anchors && parsed.anchors.length > 0) {
      viralAnchors = parsed.anchors;
    }
  }
} catch(e) {}

let multimodalHeader = "";
if (viralAnchors.length > 0) {
  multimodalHeader = "\\n=== [PROVEN MULTIMODAL VIRAL PEAKS (AUDIENCE CHAT, FACECAM & VOCAL ENERGY)] ===\\n" +
    "The following moments have been empirically pre-verified by live chat velocity bursts (LMAO, 💀, WTF), streamer face reactions (laughter/shock), and vocal scream spikes.\\n" +
    "YOU MUST PRIORITIZE SELECTING YOUR 3 MOMENTS FROM OR DIRECTLY AROUND THESE PROVEN PEAKS:\\n\\n";

  for (let a of viralAnchors) {
    multimodalHeader += \`• [ANCHOR #\${a.anchor_id}] [\${a.start}s - \${a.end}s] (Peak at \${a.peak_time}s | Score: \${a.virality_score}/100)\\n\` +
      \`  - Audience Chat: \${a.chat_signal}\\n\` +
      \`  - Streamer Facecam: \${a.face_signal}\\n\` +
      \`  - Audio Energy: \${a.audio_signal}\\n\\n\`;
  }
}
`;
    // Insert right before const prompt =
    js = js.replace("const prompt = \n    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout.", anchorExtraction + "\n  const prompt = \n    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout.");
    js = js.replace("identify the top 3 most explosive, high-retention gaming moments.\\n\\n' +", "identify the top 3 most explosive, high-retention gaming moments.\\n\\n' + (multimodalHeader ? multimodalHeader + '\\n' : '') +");
    scoutNode.parameters.jsCode = js;
    console.log('[Multimodal Injector] Updated 1. Prepare Scout Prompt in workflow.json.');
  }
}

// 4. Update 3. Prepare Director Prompt in workflow.json
const directorNode = wf.nodes.find(n => n.name === "3. Prepare Director Prompt");
if (directorNode && directorNode.parameters && directorNode.parameters.jsCode) {
  let js = directorNode.parameters.jsCode;
  if (!js.includes("Run Multimodal Fusion")) {
    const directorExtraction = `
// Pull Proven Multimodal Anchors
let viralContext = "";
try {
  const fusionItem = $('Run Multimodal Fusion').first();
  if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
    const parsed = JSON.parse(fusionItem.json.stdout);
    if (parsed && parsed.anchors && parsed.anchors.length > 0) {
      viralContext = "\\n=== PROVEN AUDIENCE & REACTION ANCHORS ===\\n" +
        parsed.anchors.map(a => \`[ANCHOR #\${a.anchor_id}] Peak at \${a.peak_time}s | Score: \${a.virality_score}/100 | Chat: \${a.chat_signal} | Face: \${a.face_signal}\`).join("\\n") + "\\n";
    }
  }
} catch(e) {}
`;
    js = js.replace("let streamContext = \"\";", directorExtraction + "\nlet streamContext = \"\";");
    js = js.replace("const directorPrompt =", "const directorPrompt = (viralContext ? viralContext + '\\n' : '') +");
    directorNode.parameters.jsCode = js;
    console.log('[Multimodal Injector] Updated 3. Prepare Director Prompt in workflow.json.');
  }
}

// Write updated workflow.json
fs.writeFileSync(wfJsonPath, JSON.stringify(wf, null, 2), 'utf8');
console.log('[Multimodal Injector] Saved updated workflow.json.');

// 5. Update workflow_bypassed.ts to keep in sync
if (!tsContent.includes("RunMultimodalFusion = {")) {
  const nodeDef = `
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
            '=python3 /files/multimodal_analyzer.py "/files/inputs/{{ $(\\'Edit Fields\\').first().json.stream_file }}" "/files/temp/audio.mp3" "/files/temp/cam_config.json" "/files/temp/viral_anchors.json"',
    };
`;
  tsContent = tsContent.replace("WaitBeforeScout = {", nodeDef + "\n    WaitBeforeScout = {");

  // Update connections in TS
  tsContent = tsContent.replace(
    "this.WaitBeforeScout.out(0).to(this._1PrepareScoutPrompt.in(0));",
    "this.WaitBeforeScout.out(0).to(this.RunMultimodalFusion.in(0));\n        this.RunMultimodalFusion.out(0).to(this._1PrepareScoutPrompt.in(0));"
  );
  tsContent = tsContent.replace(
    "this._1GlobalSummaryFallback.out(0).to(this._1PrepareScoutPrompt.in(0));",
    "this._1GlobalSummaryFallback.out(0).to(this.RunMultimodalFusion.in(0));"
  );

  // Update prompt code in TS
  const anchorExtractionTS = `
// ── Multimodal Viral Anchors Extraction ──────────────────────
let viralAnchors = [];
try {
  const fusionItem = $('Run Multimodal Fusion').first();
  if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
    const parsed = JSON.parse(fusionItem.json.stdout);
    if (parsed && parsed.anchors && parsed.anchors.length > 0) {
      viralAnchors = parsed.anchors;
    }
  }
} catch(e) {}

let multimodalHeader = "";
if (viralAnchors.length > 0) {
  multimodalHeader = "\\n=== [PROVEN MULTIMODAL VIRAL PEAKS (AUDIENCE CHAT, FACECAM & VOCAL ENERGY)] ===\\n" +
    "The following moments have been empirically pre-verified by live chat velocity bursts (LMAO, 💀, WTF), streamer face reactions (laughter/shock), and vocal scream spikes.\\n" +
    "YOU MUST PRIORITIZE SELECTING YOUR 3 MOMENTS FROM OR DIRECTLY AROUND THESE PROVEN PEAKS:\\n\\n";

  for (let a of viralAnchors) {
    multimodalHeader += \`• [ANCHOR #\${a.anchor_id}] [\${a.start}s - \${a.end}s] (Peak at \${a.peak_time}s | Score: \${a.virality_score}/100)\\n\` +
      \`  - Audience Chat: \${a.chat_signal}\\n\` +
      \`  - Streamer Facecam: \${a.face_signal}\\n\` +
      \`  - Audio Energy: \${a.audio_signal}\\n\\n\`;
  }
}
`;
  tsContent = tsContent.replace("const prompt = \n    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout.", anchorExtractionTS + "\n  const prompt = \n    'SYSTEM: You are an elite YouTube Shorts Viral Content Scout.");
  tsContent = tsContent.replace("identify the top 3 most explosive, high-retention gaming moments.\\n\\n' +", "identify the top 3 most explosive, high-retention gaming moments.\\n\\n' + (multimodalHeader ? multimodalHeader + '\\n' : '') +");

  const directorExtractionTS = `
// Pull Proven Multimodal Anchors
let viralContext = "";
try {
  const fusionItem = $('Run Multimodal Fusion').first();
  if (fusionItem && fusionItem.json && fusionItem.json.stdout) {
    const parsed = JSON.parse(fusionItem.json.stdout);
    if (parsed && parsed.anchors && parsed.anchors.length > 0) {
      viralContext = "\\n=== PROVEN AUDIENCE & REACTION ANCHORS ===\\n" +
        parsed.anchors.map(a => \`[ANCHOR #\${a.anchor_id}] Peak at \${a.peak_time}s | Score: \${a.virality_score}/100 | Chat: \${a.chat_signal} | Face: \${a.face_signal}\`).join("\\n") + "\\n";
    }
  }
} catch(e) {}
`;
  tsContent = tsContent.replace("let streamContext = \"\";", directorExtractionTS + "\nlet streamContext = \"\";");
  tsContent = tsContent.replace("const directorPrompt =", "const directorPrompt = (viralContext ? viralContext + '\\n' : '') +");

  fs.writeFileSync(wfTsPath, tsContent, 'utf8');
  console.log('[Multimodal Injector] Updated workflow_bypassed.ts.');
}
