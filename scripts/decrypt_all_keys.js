const CryptoJS = require('/usr/local/lib/node_modules/n8n/node_modules/crypto-js');
const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const fs = require('fs');

let encKey = null;
try {
  encKey = JSON.parse(fs.readFileSync('/root/.n8n/config')).encryptionKey;
} catch (e) {
  try {
    encKey = JSON.parse(fs.readFileSync('/home/node/.n8n/config')).encryptionKey;
  } catch (e2) {}
}

const dbPaths = ['/root/.n8n/database.sqlite', '/home/node/.n8n/database.sqlite'];
let dbPath = dbPaths.find(p => fs.existsSync(p));

console.log('Using DB:', dbPath, 'Key exists:', !!encKey);

const db = new sqlite3.Database(dbPath);

db.all("SELECT id, name, type, data FROM credentials_entity", (err, rows) => {
  if (err) return console.error('DB error:', err);
  console.log(`Found ${rows.length} credential entities.`);
  
  const decryptedAll = {};

  rows.forEach(r => {
    try {
      const bytes = CryptoJS.AES.decrypt(r.data, encKey);
      const dec = bytes.toString(CryptoJS.enc.Utf8);
      const parsed = JSON.parse(dec);
      decryptedAll[r.name] = { type: r.type, keys: Object.keys(parsed) };
      
      const apiKey = parsed.apiKey || parsed.apiKeyHeader || parsed.key || parsed.token || parsed.api_key;
      if (apiKey) {
        decryptedAll[r.name].apiKeyMasked = apiKey.slice(0, 4) + '...' + apiKey.slice(-4);
        
        // Save specific key files if matched
        if (r.type.toLowerCase().includes('google') || r.type.toLowerCase().includes('gemini') || r.name.toLowerCase().includes('gemini')) {
          fs.writeFileSync('/files/gemini_key.txt', apiKey.trim());
          console.log(`[DECRYPT] Wrote Gemini key from '${r.name}' (${r.type}) to /files/gemini_key.txt`);
        }
        if (r.type.toLowerCase().includes('openai')) {
          fs.writeFileSync('/files/openai_key.txt', apiKey.trim());
          console.log(`[DECRYPT] Wrote OpenAI key from '${r.name}' to /files/openai_key.txt`);
        }
      }
    } catch (e) {
      console.log(`Could not decrypt ${r.name} (${r.type}): ${e.message}`);
    }
  });

  console.log('Decrypted summary:', JSON.stringify(decryptedAll, null, 2));
  db.close();
});
