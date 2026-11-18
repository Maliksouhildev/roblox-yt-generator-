#!/usr/bin/env python3
"""Structural and isolated Node/n8n-sandbox dry-run tests for Short Publisher (B331oWlVWY0Q8s2n)."""

import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_PATH = os.path.join(ROOT, "workflows", "gta6_smart_publisher.json")


class TestShortPublisherStructure(unittest.TestCase):
    def setUp(self):
        with open(WF_PATH, "r", encoding="utf-8") as f:
            self.wf = json.load(f)
        self.nodes_by_name = {n["name"]: n for n in self.wf["nodes"]}
        self.conns = self.wf["connections"]

    def test_identity_settings_and_triggers(self):
        self.assertEqual(self.wf["id"], "B331oWlVWY0Q8s2n")
        self.assertEqual(self.wf["name"], "Short Publisher (Bypassed Version)")
        self.assertIs(self.wf["active"], True)
        self.assertEqual(self.wf["settings"], {"timezone": "Africa/Algiers", "executionOrder": "v1"})

        sched = self.nodes_by_name["Schedule Trigger"]
        self.assertEqual(sched["type"], "n8n-nodes-base.scheduleTrigger")
        self.assertGreaterEqual(float(sched["typeVersion"]), 1.2)
        intervals = sched["parameters"]["rule"]["interval"]
        exprs = [r.get("expression") for r in intervals if r.get("field") == "cronExpression"]
        self.assertIn("0,30 12-23 * * *", exprs)
        self.assertIn("0 0-11 * * *", exprs)

        manual = self.nodes_by_name["Test Publisher Manually"]
        self.assertEqual(manual["type"], "n8n-nodes-base.manualTrigger")
        self.assertEqual(self.conns["Schedule Trigger"]["main"][0][0]["node"], "Scan & Rank Output Queue")
        self.assertEqual(self.conns["Test Publisher Manually"]["main"][0][0]["node"], "Scan & Rank Output Queue")

    def test_no_legacy_broken_nodes_and_clean_connections(self):
        forbidden = {"Loop Over Items", "Execute Command1", "Code", "Read Sidecar", "Parse Sidecar"}
        self.assertEqual(set(), forbidden.intersection(set(self.nodes_by_name.keys())))
        wf_str = json.dumps(self.wf)
        self.assertNotIn("shuf", wf_str)

        valid_names = set(self.nodes_by_name.keys())
        reachable = set()

        def dfs(name):
            if name in reachable:
                return
            reachable.add(name)
            for ctype_branches in self.conns.get(name, {}).values():
                for br in ctype_branches:
                    for edge in br:
                        tgt = edge["node"]
                        self.assertIn(tgt, valid_names, f"Broken target node: {tgt}")
                        dfs(tgt)

        for src in self.conns:
            self.assertIn(src, valid_names, f"Broken source node: {src}")
        dfs("Schedule Trigger")
        dfs("Test Publisher Manually")
        self.assertEqual(reachable, valid_names)

    def test_credentials_emails_and_error_branches(self):
        email_nodes = [
            "Email Queue Empty & Auto-Trigger",
            "Send Manual Upload Alert Email",
            "Send Upload Error Email",
            "Send Published Confirmation Email",
        ]
        for ename in email_nodes:
            node = self.nodes_by_name[ename]
            self.assertEqual(node["type"], "n8n-nodes-base.emailSend")
            self.assertEqual(node["credentials"], {"smtp": {"id": "y9GfhJenJPSfkVno", "name": "SMTP account"}})
            self.assertEqual(node["parameters"]["fromEmail"], "mlkmehdid@gmail.com")
            self.assertEqual(node["parameters"]["toEmail"], "mlkmehdid@gmail.com")
            self.assertEqual(node["parameters"]["emailFormat"], "html")
            self.assertTrue(node["parameters"]["html"])

        for yt_node in ("Initiate YouTube Upload", "Upload Video to YouTube"):
            node = self.nodes_by_name[yt_node]
            self.assertEqual(
                node["credentials"],
                {"youTubeOAuth2Api": {"id": "uZZfE7BMA1T5wyqf", "name": "YouTube account"}},
            )
            self.assertEqual(node.get("onError"), "continueErrorOutput")
            err_edges = self.conns[yt_node]["main"][1]
            self.assertEqual(err_edges[0]["node"], "Handle YouTube Upload Error")

        trig_cmd = self.nodes_by_name["Trigger GTA6 Generator"]["parameters"]["command"]
        self.assertTrue(trig_cmd.startswith("="))
        self.assertIn("Gta6VisionShortsV1", trig_cmd)
        self.assertIn("NODE_FUNCTION_ALLOW_BUILTIN=*", trig_cmd)
        self.assertIn("NODE_FUNCTION_ALLOW_EXTERNAL=*", trig_cmd)

        prep_js = self.nodes_by_name["Prepare YouTube Upload"]["parameters"]["jsCode"]
        self.assertIn("privacyStatus: 'public'", prep_js)
        self.assertIn("selfDeclaredMadeForKids: false", prep_js)
        self.assertIn("categoryId: '20'", prep_js)


class TestShortPublisherDockerDryRun(unittest.TestCase):
    def test_isolated_node_and_n8n_sandbox_logic(self):
        """Executes publisher Code nodes inside ai_clipper-n8n-1's n8n JavaScriptSandbox on an isolated /tmp directory."""
        js_harness = r"""
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const assert = require('assert');

const { JavaScriptSandbox } = require('/usr/local/lib/node_modules/n8n/node_modules/n8n-nodes-base/dist/nodes/Code/JavaScriptSandbox');
const wf = JSON.parse(fs.readFileSync('/files/workflows/gta6_smart_publisher.json', 'utf8'));
const byName = Object.fromEntries(wf.nodes.map(n => [n.name, n]));

const tmpRoot = fs.mkdtempSync('/tmp/pub_test_');
const outputsDir = path.join(tmpRoot, 'outputs');
const inputsDir = path.join(tmpRoot, 'inputs');
const tempDir = path.join(tmpRoot, 'temp');
fs.mkdirSync(outputsDir, { recursive: true });
fs.mkdirSync(inputsDir, { recursive: true });
fs.mkdirSync(tempDir, { recursive: true });

const quotaPath = path.join(tempDir, 'yt_quota_state.json');
const excessPath = path.join(tempDir, 'yt_excess_alert_state.json');
const historyPath = path.join(outputsDir, 'published_history.json');

async function runCodeNode(nodeName, items, extraNodes = {}) {
  const ctx = {
    $input: {
      all: () => items,
      first: () => items[0],
      last: () => items[items.length - 1],
    },
    $: (name) => ({
      first: () => extraNodes[name],
      last: () => extraNodes[name],
      item: extraNodes[name],
      all: () => extraNodes[name] ? [extraNodes[name]] : [],
    }),
  };
  const sb = new JavaScriptSandbox(
    ctx,
    byName[nodeName].parameters.jsCode,
    { normalizeItems: (res) => (Array.isArray(res) ? res : [res]) }
  );
  const out = await sb.runCodeAllItems();
  return out;
}

(async () => {
  try {
    // 1. Setup synthetic files: orphan JSONs, protected files, priority clips, >95 title, deduped clips
    fs.writeFileSync(path.join(outputsDir, 'orphan_clip.json'), JSON.stringify({ viral_caption: 'ORPHAN' }));
    fs.writeFileSync(path.join(outputsDir, 'broken_orphan.json'), '{bad json');
    fs.writeFileSync(path.join(outputsDir, 'scoreboard.csv'), 'header\n');
    fs.writeFileSync(path.join(outputsDir, 'ANTIGRAVITY_EDL_BREAKDOWN_REPORT.md'), '# report');
    fs.writeFileSync(path.join(outputsDir, 'ANTIGRAVITY_ITERATIONS_FULL_LOG.json'), '{"ok":true}');
    fs.writeFileSync(path.join(outputsDir, 'player_blacklist.json'), '["Test"]');

    // Already published clip (match by filename) + content duplicate (match by sha256)
    const dupBytes = Buffer.from('duplicate-video-bytes-12345');
    const dupHash = crypto.createHash('sha256').update(dupBytes).digest('hex');
    fs.writeFileSync(path.join(outputsDir, 'already_pub_by_name.mp4'), Buffer.from('unique-by-name'));
    fs.writeFileSync(path.join(outputsDir, 'already_pub_by_name.json'), JSON.stringify({ virality_score: 9.9 }));
    fs.writeFileSync(path.join(outputsDir, 'renamed_dup.mp4'), dupBytes);
    fs.writeFileSync(path.join(outputsDir, 'renamed_dup.json'), JSON.stringify({ virality_score: 9.9 }));
    fs.writeFileSync(historyPath, JSON.stringify([
      { filename: 'already_pub_by_name.mp4', sha256: '0000', videoId: 'old1' },
      { filename: 'original_name.mp4', sha256: dupHash, videoId: 'old2' },
    ]));

    // Active ranked clips
    // Clip A: 9.1 older
    fs.writeFileSync(path.join(outputsDir, 'clip_a.mp4'), Buffer.from('video-a'));
    fs.writeFileSync(path.join(outputsDir, 'clip_a.json'), JSON.stringify({
      virality_score: 9.14,
      created_at_epoch: 1000000,
      viral_caption: 'CLIP A OLDER HIGH',
      narrative_archetype: 'OPEN_WORLD_CHAOS',
      creator_credit: '🎥 @DarkViperAU',
    }));
    // Clip B: 8.8 newer (diff 0.3 <= 0.4 -> MUST rank above Clip A!)
    fs.writeFileSync(path.join(outputsDir, 'clip_b.mp4'), Buffer.from('video-b'));
    fs.writeFileSync(path.join(outputsDir, 'clip_b.json'), JSON.stringify({
      virality_score: 8.82,
      created_at_epoch: 2000000,
      viral_caption: 'CLIP B NEWER TIE BAND',
      youtube_title: 'THIS <EXTREME> TITLE IS WAY TOO LONG\u0007 FOR YOUTUBE API SO IT MUST BE CLAMPED CLEANLY UNDER 95 CHARS INCLUDING EMOJIS 😱💀 AND STAY VALID #Shorts',
      youtube_description: 'Custom <desc> B',
      narrative_archetype: 'STORY_CUTSCENE',
      creator_credit: '🎥 @TypicalGamer',
    }));
    // Clip C: 8.2 newest (9.1 - 8.2 = 0.9 > 0.4 -> ranks below A and B)
    fs.writeFileSync(path.join(outputsDir, 'clip_c.mp4'), Buffer.from('video-c'));
    fs.writeFileSync(path.join(outputsDir, 'clip_c.json'), JSON.stringify({
      virality_score: 8.2,
      created_at_epoch: 3000000,
      viral_caption: 'CLIP C LOWER',
    }));
    // Clip D: no sidecar JSON -> default score 5.0
    fs.writeFileSync(path.join(outputsDir, 'clip_d_nosidecar.mp4'), Buffer.from('video-d'));
    // Ignored temp/processing files in outputs
    fs.writeFileSync(path.join(outputsDir, 'ignore.tmp.mp4'), Buffer.from('tmp'));
    fs.writeFileSync(path.join(outputsDir, 'ignore.processing.mp4'), Buffer.from('proc'));

    // Quota state: 2026-11-17 day with 6 uploads; test at 07:55 Algiers (still 2026-11-17) then 08:05 Algiers (reset!)
    const t0755Algiers = Date.parse('2026-11-18T06:55:00Z'); // 07:55 UTC+1
    const t0805Algiers = Date.parse('2026-11-18T07:05:00Z'); // 08:05 UTC+1
    fs.writeFileSync(quotaPath, JSON.stringify({
      uploads_today: 6,
      last_upload_epoch: t0755Algiers - 60 * 60000,
      quota_day: '2026-11-17',
    }));

    const baseInput = {
      _test_outputs_dir: outputsDir,
      _test_inputs_dir: inputsDir,
      _test_quota_state_path: quotaPath,
      _test_excess_state_path: excessPath,
      _test_history_path: historyPath,
      _test_now_ms: t0755Algiers,
    };

    // Run before 08:00 AM reset
    let res = await runCodeNode('Scan & Rank Output Queue', [{ json: baseInput }]);
    let j = res[0].json;
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'orphan_clip.json')), false, 'orphan_clip.json deleted');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'broken_orphan.json')), false, 'broken_orphan.json deleted');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'scoreboard.csv')), true, 'scoreboard.csv preserved');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'ANTIGRAVITY_EDL_BREAKDOWN_REPORT.md')), true, 'ANTIGRAVITY report preserved');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'ANTIGRAVITY_ITERATIONS_FULL_LOG.json')), true, 'ANTIGRAVITY log preserved');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'player_blacklist.json')), true, 'player_blacklist preserved');

    assert.strictEqual(j.queue_empty, false);
    assert.strictEqual(j.queue_count, 4, '4 non-published clips');
    assert.strictEqual(j.top_clip.filename, 'clip_b.mp4', 'score diff <=0.4 breaks by newest');
    assert.ok(j.top_clip.youtube_title.length <= 95, 'youtube_title <= 95 chars');
    assert.ok(j.top_clip.youtube_title.endsWith('#Shorts'), 'youtube_title ends with #Shorts');
    assert.ok(!/[<>\x00-\x1F\x7F]/.test(j.top_clip.youtube_title), 'title stripped of <> and control chars');
    assert.ok(!/[<>]/.test(j.top_clip.youtube_description), 'description stripped of <>');
    assert.strictEqual(j.top_clip.sha256.length, 64);
    assert.strictEqual(j.uploads_today, 6, 'still 6 before 08:00 Algiers');
    assert.strictEqual(j.slots_remaining, 0);
    assert.strictEqual(j.can_api_publish, false, 'locked at 6/6 before 08:00');
    assert.strictEqual(j.excess_for_manual, true);
    assert.strictEqual(j.should_send_excess_email, true);
    assert.strictEqual(j.excess_clips_list.length, 4);
    assert.strictEqual(j.excess_clips_list[1].filename, 'clip_a.mp4');
    assert.strictEqual(j.excess_clips_list[2].filename, 'clip_c.mp4');
    assert.strictEqual(j.excess_clips_list[3].filename, 'clip_d_nosidecar.mp4');
    assert.strictEqual(j.excess_clips_list[3].virality_score, 5.0);
    assert.strictEqual(j.is_generator_processing, false);

    // Run after 08:00 AM Algiers -> quota resets to 0!
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0805Algiers } }]);
    j = res[0].json;
    assert.strictEqual(j.uploads_today, 0, 'reset to 0 at 08:00 AM Africa/Algiers');
    assert.strictEqual(j.slots_remaining, 6);
    assert.strictEqual(j.can_api_publish, true);
    assert.strictEqual(j.excess_for_manual, false, '4 <= 6 remaining slots');
    assert.strictEqual(j.should_send_excess_email, false);

    // Check 45-min cooldown
    fs.writeFileSync(quotaPath, JSON.stringify({
      uploads_today: 2,
      last_upload_epoch: t0805Algiers - 30 * 60000,
      quota_day: '2026-11-18',
    }));
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0805Algiers } }]);
    j = res[0].json;
    assert.strictEqual(j.minutes_since_last_upload, 30);
    assert.strictEqual(j.can_api_publish, false, 'blocked by 45m spacing');
    assert.strictEqual(j.excess_for_manual, false, '4 == 4 slots_remaining, not strictly >');

    // Cooldown elapsed (>= 45m) + excess throttle test (5 clips > 4 slots)
    fs.writeFileSync(path.join(outputsDir, 'clip_e.mp4'), Buffer.from('video-e'));
    const t0900Algiers = t0805Algiers + 55 * 60000;
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers } }]);
    j = res[0].json;
    assert.strictEqual(j.queue_count, 5);
    assert.strictEqual(j.can_api_publish, true);
    assert.strictEqual(j.excess_for_manual, true);
    assert.strictEqual(j.should_send_excess_email, true);
    assert.strictEqual(j.excess_clips_list.length, 1, '5 - 4 = 1 excess clip');

    // Update Excess Alert State -> immediate re-scan shouldn't resend, count change resends, >=2h resends
    await runCodeNode('Update Excess Alert State', [{ json: j }]);
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers + 30 * 60000 } }]);
    assert.strictEqual(res[0].json.should_send_excess_email, false, 'throttled within 2h with same count');

    fs.writeFileSync(path.join(outputsDir, 'clip_f.mp4'), Buffer.from('video-f'));
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers + 30 * 60000 } }]);
    assert.strictEqual(res[0].json.should_send_excess_email, true, 'fires within 2h when queue count changes');
    fs.unlinkSync(path.join(outputsDir, 'clip_f.mp4'));

    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers + 125 * 60000 } }]);
    assert.strictEqual(res[0].json.should_send_excess_email, true, 'fires after >= 2h');

    // Test Branch C: Prepare YouTube Upload -> Extract Upload URL -> Error (500 + quotaExceeded) -> Success (Record Publish & Delete Clip)
    const fakeBinary = { data: { data: Buffer.from('video-b').toString('base64'), mimeType: 'video/mp4', fileName: 'clip_b.mp4' } };
    const prepOut = await runCodeNode(
      'Prepare YouTube Upload',
      [{ json: j, binary: fakeBinary }],
      { 'Scan & Rank Output Queue': { json: j }, 'Read Clip Binary': { json: j, binary: fakeBinary } }
    );
    assert.ok(prepOut[0].json.yt_request_body.snippet.title.length <= 95);
    assert.strictEqual(prepOut[0].json.yt_request_body.status.privacyStatus, 'public');
    assert.ok(prepOut[0].binary && prepOut[0].binary.data);

    const extOut = await runCodeNode(
      'Extract Upload URL',
      [{ json: { headers: { Location: 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=XYZ' } } }],
      { 'Prepare YouTube Upload': prepOut[0] }
    );
    assert.strictEqual(extOut[0].json.uploadUrl, 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=XYZ');
    assert.ok(extOut[0].binary && extOut[0].binary.data);

    // Non-quota 500 error (error.httpCode + HTML payload escaping): does NOT lock quota to 6, preserves files
    const err500 = await runCodeNode(
      'Handle YouTube Upload Error',
      [{ json: { error: { httpCode: 503, message: 'Transient <backend> failure' } } }],
      { 'Prepare YouTube Upload': prepOut[0] }
    );
    assert.strictEqual(err500[0].json.http_status, 503);
    assert.strictEqual(err500[0].json.is_quota_error, false);
    assert.strictEqual(err500[0].json.uploads_today, 2);
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'clip_b.mp4')), true, 'clip_b.mp4 preserved on 500 error');

    // Quota error handling: locks uploads_today = 6, preserves clip_b.mp4 and clip_b.json
    const errOut = await runCodeNode(
      'Handle YouTube Upload Error',
      [{ json: { httpCode: 403, error: { message: 'The request cannot be completed because you have exceeded your quotaExceeded.' } } }],
      { 'Prepare YouTube Upload': prepOut[0] }
    );
    assert.strictEqual(errOut[0].json.is_quota_error, true);
    assert.strictEqual(errOut[0].json.uploads_today, 6);
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'clip_b.mp4')), true, 'clip_b.mp4 NOT deleted on error');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'clip_b.json')), true, 'clip_b.json NOT deleted on error');
    assert.strictEqual(JSON.parse(fs.readFileSync(quotaPath, 'utf8')).uploads_today, 6);

    // Reset quota to 2 and test Record Publish & Delete Clip
    fs.writeFileSync(quotaPath, JSON.stringify({
      uploads_today: 2,
      last_upload_epoch: t0900Algiers - 55 * 60000,
      quota_day: '2026-11-18',
    }));
    const recOut = await runCodeNode(
      'Record Publish & Delete Clip',
      [{ json: { id: 'YT_SHORT_999' } }],
      { 'Prepare YouTube Upload': prepOut[0] }
    );
    assert.strictEqual(recOut[0].json.videoId, 'YT_SHORT_999');
    assert.strictEqual(recOut[0].json.url, 'https://www.youtube.com/shorts/YT_SHORT_999');
    assert.strictEqual(recOut[0].json.uploads_today, 3);
    assert.strictEqual(recOut[0].json.deleted_mp4, true);
    assert.strictEqual(recOut[0].json.deleted_json, true);
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'clip_b.mp4')), false, 'clip_b.mp4 deleted after publish');
    assert.strictEqual(fs.existsSync(path.join(outputsDir, 'clip_b.json')), false, 'clip_b.json deleted after publish');
    const histAfter = JSON.parse(fs.readFileSync(historyPath, 'utf8'));
    assert.strictEqual(histAfter.length, 3);
    assert.strictEqual(histAfter[2].videoId, 'YT_SHORT_999');
    assert.strictEqual(histAfter[2].sha256, prepOut[0].json.top_clip.sha256);

    // Evaluate all key n8n expression strings cleanly
    function evalExpr(exprStr, $json, extra = {}) {
      const code = String(exprStr).replace(/^=/, '').replace(/^\{\{/, '').replace(/\}\}$/, '').trim();
      const $ = (name) => ({ first: () => extra[name] || { json: {} } });
      return (new Function('$json', '$', 'return (' + code + ');'))($json, $);
    }
    assert.ok(evalExpr(byName['Send Published Confirmation Email'].parameters.subject, recOut[0].json).includes('3/6 Today'));
    assert.ok(evalExpr(byName['Send Published Confirmation Email'].parameters.html, recOut[0].json).includes('https://www.youtube.com/shorts/YT_SHORT_999'));
    assert.ok(evalExpr(byName['Send Upload Error Email'].parameters.subject, errOut[0].json).startsWith('❌ YouTube Upload Failed:'));
    const err500Html = evalExpr(byName['Send Upload Error Email'].parameters.html, err500[0].json);
    assert.ok(err500Html.includes('Transient &lt;backend&gt; failure'), 'error HTML escaped');
    assert.ok(evalExpr(byName['Send Manual Upload Alert Email'].parameters.subject, j).includes('5 in /files/outputs/'));

    // Empty queue & processing.mp4 detection + real BusyBox sh -c pgrep self-match regression check
    const { execFileSync } = require('child_process');
    for (const f of ['clip_a.mp4', 'clip_c.mp4', 'clip_d_nosidecar.mp4', 'clip_e.mp4']) {
      fs.unlinkSync(path.join(outputsDir, f));
    }
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers + 130 * 60000 } }]);
    assert.strictEqual(res[0].json.queue_empty, true);
    assert.strictEqual(res[0].json.is_generator_processing, false);
    const cmdIdle = evalExpr(byName['Trigger GTA6 Generator'].parameters.command, res[0].json);
    assert.ok(cmdIdle.includes('WF_ID=Gta6VisionShortsV1'), 'uses shell variable WF_ID');
    assert.ok(cmdIdle.includes('"[n]8n execute --id=$WF_ID"'), 'uses bracketed pgrep pattern');
    assert.ok(!cmdIdle.includes('n8n execute --id=Gta6VisionShortsV1'), 'avoids literal self-match string in sh -c');
    // Execute the exact guard inside Alpine BusyBox sh -c (swapping only the nohup launch payload + test pidfile)
    const testPidFile = path.join(tempDir, 'test_trigger.pid');
    const guardCmd = cmdIdle
      .replace('/files/temp/gta6_auto_trigger.pid', testPidFile)
      .replace(/nohup .*?echo "LAUNCHED_PID:\$!"/, 'echo "WOULD_LAUNCH"');
    const shOut = execFileSync('sh', ['-c', guardCmd], { encoding: 'utf8' }).trim();
    assert.strictEqual(shOut, 'WOULD_LAUNCH', 'BusyBox pgrep -f must NOT self-match sh -c');

    const emptyEmailHtml = evalExpr(
      byName['Email Queue Empty & Auto-Trigger'].parameters.html,
      { stdout: 'LAUNCHED_PID:12345' },
      { 'Scan & Rank Output Queue': { json: res[0].json } }
    );
    assert.ok(emptyEmailHtml.includes('LAUNCHED_PID:12345'));

    fs.writeFileSync(path.join(inputsDir, 'stream_active.processing.mp4'), Buffer.from('proc'));
    res = await runCodeNode('Scan & Rank Output Queue', [{ json: { ...baseInput, _test_now_ms: t0900Algiers + 130 * 60000 } }]);
    assert.strictEqual(res[0].json.queue_empty, true);
    assert.strictEqual(res[0].json.is_generator_processing, true);
    const cmdBusy = evalExpr(byName['Trigger GTA6 Generator'].parameters.command, res[0].json);
    assert.ok(cmdBusy.includes('SKIPPED_PROCESSING'));
    assert.ok(!cmdBusy.includes('n8n execute'));

    console.log('ALL_SANDBOX_ASSERTIONS_PASSED');
  } finally {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  }
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""
        proc = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "-e",
                "NODE_FUNCTION_ALLOW_BUILTIN=*",
                "-e",
                "NODE_FUNCTION_ALLOW_EXTERNAL=*",
                "ai_clipper-n8n-1",
                "node",
                "-",
            ],
            input=js_harness,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Sandbox dry-run failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertIn("ALL_SANDBOX_ASSERTIONS_PASSED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
