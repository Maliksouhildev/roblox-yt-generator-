const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/root/.n8n/database.sqlite');

db.get('SELECT nodes FROM workflow_entity WHERE id = ?', ['KoeIx1msxnfWlUii'], (err, row) => {
  if (err) {
    console.error('Error fetching workflow:', err);
    process.exit(1);
  }
  const nodes = JSON.parse(row.nodes);

  const runDet = nodes.find(n => n.name === 'Run Facecam Detector');
  if (runDet) {
    runDet.parameters.command = '=file="/files/inputs/{{ $json.stream_file }}"; rm -f /files/temp/test_ref_*.jpg /files/temp/test_cam_config.json; ffmpeg -loglevel error -y -ss 00:02:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/test_ref_1.jpg" || true; ffmpeg -loglevel error -y -ss 00:05:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/test_ref_2.jpg" || true; ffmpeg -loglevel error -y -ss 00:08:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/test_ref_3.jpg" || true; ffmpeg -loglevel error -y -ss 00:11:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/test_ref_4.jpg" || true; ffmpeg -loglevel error -y -ss 00:14:00 -i "$file" -vf "scale=960:540" -vframes 1 -q:v 2 "/files/temp/test_ref_5.jpg" || true; python3 /files/cam_detector.py "/files/temp/test_ref_*.jpg" "/files/temp/test_cam_config.json" "$file"';
  }

  const cropNode = nodes.find(n => n.name === 'Extract Short Preview Crop');
  if (cropNode) {
    cropNode.parameters.command = '=if [ "{{ $json.ai_found }}" = "true" ]; then file="/files/inputs/{{ $json.stream_file }}"; out_file="/files/temp/test_crop_{{ $json.stream_file }}.jpg"; ffmpeg -loglevel error -y -ss 00:07:30 -i "$file" -vf "crop=trunc(iw*{{ $json.cam_w }}/1920/2)*2:trunc(ih*{{ $json.cam_h }}/1080/2)*2:trunc(iw*{{ $json.cam_x }}/1920/2)*2:trunc(ih*{{ $json.cam_y }}/1080/2)*2,split=2[c_fg][c_bg];[c_bg]scale=720:400:force_original_aspect_ratio=increase,crop=720:400,boxblur=25:5[c_blur];[c_fg]scale=720:400:force_original_aspect_ratio=decrease[c_fit];[c_blur][c_fit]overlay=(W-w)/2:(H-h)/2" -vframes 1 -q:v 2 "$out_file" && echo "SUCCESS: Saved crop $out_file ({{ $json.cam_w }}x{{ $json.cam_h }} at {{ $json.cam_x }},{{ $json.cam_y }})"; else echo "NO WEBCAM: Full gameplay mode"; fi';
  }

  db.run('UPDATE workflow_entity SET nodes = ?, updatedAt = datetime("now") WHERE id = ?', [JSON.stringify(nodes), 'KoeIx1msxnfWlUii'], (err2) => {
    if (err2) console.error('Error updating workflow:', err2);
    else console.log('Successfully updated workflow KoeIx1msxnfWlUii in n8n database!');
    db.close();
  });
});
