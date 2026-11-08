let sqlite3;
try {
  sqlite3 = require('sqlite3').verbose();
} catch (e) {
  try {
    sqlite3 = require('/home/node/node_modules/sqlite3').verbose();
  } catch (e2) {
    sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3').verbose();
  }
}
const fs = require('fs');

const DB_PATH = '/root/.n8n/database.sqlite';
const BACKUP_JSON = '/root/.n8n/workflows_backup_prepatch.json';

// Read new workflow files from /tmp
const wf1 = JSON.parse(fs.readFileSync('/tmp/workflow.json', 'utf8'));
const wf2 = JSON.parse(fs.readFileSync('/tmp/transcript_viral_shorts_engine.json', 'utf8'));

console.log('[INFO] Loaded workflow files from /tmp.');

const db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READWRITE, (err) => {
  if (err) {
    console.error('Failed to open database:', err);
    process.exit(1);
  }
});

const now = new Date().toISOString();

db.serialize(() => {
  // 1. Backup only the targeted workflow entities to a lightweight JSON file
  db.all(
    "SELECT id, name, nodes, connections, updatedAt FROM workflow_entity WHERE id IN ('D2hITsyjP5dVsqBZ', '25doQLpFZrkfiYG2')",
    (err, rows) => {
      if (err) {
        console.error('Backup query failed:', err);
        process.exit(1);
      }
      fs.writeFileSync(BACKUP_JSON, JSON.stringify(rows, null, 2));
      console.log(`[OK] Backed up ${rows.length} workflows to ${BACKUP_JSON}`);

      // 2. Update D2hITsyjP5dVsqBZ
      const stmt1 = db.prepare(`
        UPDATE workflow_entity
        SET nodes = ?, connections = ?, updatedAt = ?
        WHERE id = ?
      `);

      stmt1.run(
        JSON.stringify(wf1.nodes),
        JSON.stringify(wf1.connections),
        now,
        'D2hITsyjP5dVsqBZ',
        function(err1) {
          if (err1) console.error('Error updating D2hITsyjP5dVsqBZ:', err1);
          else console.log(`[OK] Updated D2hITsyjP5dVsqBZ (YouTube Short Automation): ${this.changes} row updated.`);
        }
      );
      stmt1.finalize();

      // 3. Update 25doQLpFZrkfiYG2
      const stmt2 = db.prepare(`
        UPDATE workflow_entity
        SET nodes = ?, connections = ?, updatedAt = ?
        WHERE id = ?
      `);

      stmt2.run(
        JSON.stringify(wf2.nodes),
        JSON.stringify(wf2.connections),
        now,
        '25doQLpFZrkfiYG2',
        function(err2) {
          if (err2) console.error('Error updating 25doQLpFZrkfiYG2:', err2);
          else console.log(`[OK] Updated 25doQLpFZrkfiYG2 (Transcript Viral Shorts Engine): ${this.changes} row updated.`);
        }
      );
      stmt2.finalize();

      // 4. Verification read-back
      db.get('SELECT nodes, updatedAt FROM workflow_entity WHERE id = ?', ['D2hITsyjP5dVsqBZ'], (errV1, rowV1) => {
        if (errV1) {
          console.error('Verification error D2hITsyjP5dVsqBZ:', errV1);
          process.exit(1);
        }
        const nodes = JSON.parse(rowV1.nodes);
        const loopClips = nodes.find(n => n.name === 'Loop Clips');
        const scoutAcc = nodes.find(n => n.name === 'Scout Accumulate');
        const splitClips = nodes.find(n => n.name === '5. Split Clips');
        const createSubs = nodes.find(n => n.name === 'Create Subtitle Binary');

        console.log('[VERIFY] D2hITsyjP5dVsqBZ:');
        console.log(' - updatedAt:', rowV1.updatedAt);
        console.log(' - Loop Clips batchSize:', loopClips?.parameters?.batchSize);
        console.log(' - Scout Accumulate multi-run loop:', scoutAcc?.parameters?.jsCode?.includes('while (true)'));
        console.log(' - 5. Split Clips fallback synthesis:', splitClips?.parameters?.jsCode?.includes('Multi-Clip Guarantee'));
        console.log(' - Create Subtitle Binary sanitizeCaption:', createSubs?.parameters?.jsCode?.includes('sanitizeCaption'));
      });

      db.get('SELECT nodes, updatedAt FROM workflow_entity WHERE id = ?', ['25doQLpFZrkfiYG2'], (errV2, rowV2) => {
        if (errV2) {
          console.error('Verification error 25doQLpFZrkfiYG2:', errV2);
          process.exit(1);
        }
        const nodes = JSON.parse(rowV2.nodes);
        const splitViral = nodes.find(n => n.name === 'Split & Filter Viral Clips');
        console.log('[VERIFY] 25doQLpFZrkfiYG2:');
        console.log(' - updatedAt:', rowV2.updatedAt);
        console.log(' - Split & Filter Viral Clips multi-clip guarantee:', splitViral?.parameters?.jsCode?.includes('outputClips = validClips.slice(0, Math.min(5'));

        db.close((errClose) => {
          if (errClose) console.error('Close error:', errClose);
          else console.log('[OK] Database closed successfully.');
        });
      });
    }
  );
});
