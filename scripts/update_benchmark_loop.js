const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/root/.n8n/database.sqlite');

db.get('SELECT nodes, connections FROM workflow_entity WHERE id = ?', ['KoeIx1msxnfWlUii'], (err, row) => {
  if (err) {
    console.error('Error fetching workflow:', err);
    process.exit(1);
  }
  let nodes = JSON.parse(row.nodes);
  let connections = JSON.parse(row.connections);

  let loopNode = nodes.find(n => n.name === 'Loop Over Streams');
  if (!loopNode) {
    loopNode = {
      id: 'loop-over-streams-id',
      name: 'Loop Over Streams',
      type: 'n8n-nodes-base.splitInBatches',
      typeVersion: 3,
      position: [400, 300],
      parameters: {
        batchSize: 1,
        options: {}
      }
    };
    nodes.push(loopNode);
  }

  connections['Parse Stream List'] = {
    main: [
      [
        {
          node: 'Loop Over Streams',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  connections['Loop Over Streams'] = {
    main: [
      [], // output 0: done
      [   // output 1: loop
        {
          node: 'Run Facecam Detector',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  connections['Run Facecam Detector'] = {
    main: [
      [
        {
          node: 'Parse Cam Config',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  connections['Parse Cam Config'] = {
    main: [
      [
        {
          node: 'Extract Short Preview Crop',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  connections['Extract Short Preview Crop'] = {
    main: [
      [
        {
          node: 'Loop Over Streams',
          type: 'main',
          index: 0
        }
      ]
    ]
  };

  db.run('UPDATE workflow_entity SET nodes = ?, connections = ?, updatedAt = datetime("now") WHERE id = ?',
    [JSON.stringify(nodes), JSON.stringify(connections), 'KoeIx1msxnfWlUii'],
    (err2) => {
      if (err2) {
        console.error('Error updating workflow:', err2);
      } else {
        console.log('Successfully wired splitInBatches loop output 1 to Run Facecam Detector!');
      }
      db.close();
    }
  );
});
