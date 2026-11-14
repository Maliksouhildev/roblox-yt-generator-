const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/root/.n8n/database.sqlite');

db.get('SELECT nodes FROM workflow_entity WHERE id = ?', ['KoeIx1msxnfWlUii'], (err, row) => {
  if (err) {
    console.error('Error fetching workflow:', err);
    process.exit(1);
  }
  let nodes = JSON.parse(row.nodes);

  const parseNode = nodes.find(n => n.name === 'Parse Cam Config');
  if (parseNode) {
    parseNode.parameters.jsCode = `let raw = $input.first().json.stdout || '{}';
let cfg = { ai_found: false };
try {
  const match = raw.match(/\\{[\\s\\S]*\\}/);
  if (match) cfg = JSON.parse(match[0]);
} catch(e) {}

let streamFile = '';
try {
  streamFile = $('Loop Over Streams').item.json.stream_file;
} catch(e) {
  try {
    streamFile = $('Parse Stream List').item.json.stream_file;
  } catch(e2) {}
}

return [{
  json: {
    stream_file: streamFile,
    ai_found: !!cfg.ai_found,
    camera_type: cfg.camera_type || 'none',
    cam_x: Number(cfg.cam_x) || 0,
    cam_y: Number(cfg.cam_y) || 0,
    cam_w: Number(cfg.cam_w) || 0,
    cam_h: Number(cfg.cam_h) || 0,
    confidence: Number(cfg.confidence) || 0
  }
}];`;
  }

  db.run('UPDATE workflow_entity SET nodes = ?, updatedAt = datetime("now") WHERE id = ?',
    [JSON.stringify(nodes), 'KoeIx1msxnfWlUii'],
    (err2) => {
      if (err2) console.error('Error:', err2);
      else console.log('Successfully updated Parse Cam Config node!');
      db.close();
    }
  );
});
