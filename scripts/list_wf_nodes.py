import json

for path in ['workflows/workflow.json', 'workflows/transcript_viral_shorts_engine.json']:
    print(f"=== {path} ===")
    with open(path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    nodes = wf.get('nodes', [])
    for i, n in enumerate(nodes):
        print(f"  {i+1:2d}. {n['name']} ({n['type']})")
