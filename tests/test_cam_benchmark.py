import subprocess
import json
import os
import sys

tests = [
    ("MeganPlays", "/files/temp/audit_megan_ref_*.jpg"),
    ("Headless Kreek", "/files/temp/audit_headless_ref_*.jpg"),
    ("Hacked Kreek", "/files/temp/audit_hacked_ref_*.jpg"),
    ("MM2 Subscribers", "/files/temp/facecam_lab_out/mm2_subscribers_f*_raw.jpg"),
    ("Horror Stream", "/files/temp/facecam_lab_out/horror_stream_f*_raw.jpg"),
    ("RB Battles (No Cam)", "/files/temp/peek_Roblox RB BATTLES CHAMPIONSHIP FINALE LIVE STREAM.mp4.jpg")
]

print("="*70)
print("RUNNING CAM DETECTOR BENCHMARK ON ALL TEST STREAMS")
print("="*70)

all_passed = True
for name, pat in tests:
    res = subprocess.run(["python3", "/files/cam_detector.py", pat, f"/files/temp/test_out_{name}.json"], capture_output=True, text=True)
    out_json = res.stdout.strip()
    try:
        parsed = json.loads(out_json)
        print(f"[{name}]")
        print(f"  ai_found: {parsed.get('ai_found')}")
        print(f"  camera_type: {parsed.get('camera_type')}")
        print(f"  crop: {parsed.get('cam_w')}x{parsed.get('cam_h')} at ({parsed.get('cam_x')},{parsed.get('cam_y')})")
        print(f"  confidence: {parsed.get('confidence')}")
        
        # Sanity assertions
        if name == "RB Battles (No Cam)":
            if parsed.get("ai_found"):
                print("  [FAIL] Expected ai_found=False for pure gameplay")
                all_passed = False
            else:
                print("  [PASS] Correctly identified pure gameplay (no cam)")
        else:
            if not parsed.get("ai_found"):
                print("  [FAIL] Expected ai_found=True")
                all_passed = False
            else:
                if parsed.get("cam_w") <= 0 or parsed.get("cam_h") <= 0:
                    print("  [FAIL] Invalid dimensions")
                    all_passed = False
                else:
                    print("  [PASS] Valid crop coordinates")
    except Exception as e:
        print(f"[{name}] ERROR: {e}")
        print(res.stderr)
        all_passed = False
    print("-" * 50)

if all_passed:
    print("\nALL STREAMS PASSED THE BENCHMARK!")
else:
    print("\nSOME STREAMS FAILED THE BENCHMARK!")
    sys.exit(1)
