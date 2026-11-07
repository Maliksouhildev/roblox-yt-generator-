import urllib.request, json, base64

with open('/files/openai_key.txt') as f:
    api_key = f.read().strip()

def test_vision(img_path):
    with open(img_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    prompt = (
        "Analyze this gaming stream frame to detect the streamer's camera layout.\n"
        "Identify:\n"
        "1. Camera type: 'box' (streamer is in a distinct rectangular webcam box with their bedroom/room background) "
        "OR 'green_screen' (streamer is cutout with transparent/green screen background directly over gameplay/desktop).\n"
        "2. Exact normalized coordinates [ymin, xmin, ymax, xmax] (0 to 1000 scale) for the camera crop.\n"
        "   - If 'box': return the bounding box of the entire physical webcam rectangle (NOT just the face!).\n"
        "   - If 'green_screen': return the bounding box covering the streamer from head to bottom edge, centered on body.\n"
        "Return ONLY JSON: {\"type\": \"box\"|\"green_screen\", \"coords\": [ymin, xmin, ymax, xmax]}"
    )
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}}
            ]
        }],
        'temperature': 0.1
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res['choices'][0]['message']['content']

print('--- Russo ---')
print(test_vision('/files/temp/ref_1.jpg'))
print('--- Kreek ---')
print(test_vision('/files/temp/kreek_ref_test.jpg'))
