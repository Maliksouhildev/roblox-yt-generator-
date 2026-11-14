import urllib.request
import os
import sys

URL = "https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx"
TARGET = "scripts/emotion-ferplus-8.onnx"

print(f"Downloading {URL} -> {TARGET}...")
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp, open(TARGET, "wb") as f:
    f.write(resp.read())

size = os.path.getsize(TARGET)
print(f"Successfully downloaded {TARGET}: {size} bytes ({size / (1024*1024):.2f} MB)")
