import urllib.request, json, time, re

pid = '6c705007-69e0-4a8c-9bca-bb5c2947fccd'
text = "It's Saturday evening, 6:56 PM, Australian Eastern Standard Time  Sunday the 12th of September... just kidding, it's Saturday the 12th. You're in Queensland, so that's your local time right now."

text_clean = text.replace(":", ", ").replace(";", ", ")
for ch in ['*', '#', '`', '[', ']', '(', ')', '{', '}', '<', '>', '|', '\\', '/', '"', '_', '~']:
    text_clean = text_clean.replace(ch, " ")
text_clean = re.sub(r'\s+', ' ', text_clean).strip()

print("Clean text:", text_clean)
print("Length:", len(text_clean))

t0 = time.time()
body = json.dumps({'profile_id': pid, 'text': text_clean, 'model_size': '1.7B'}).encode()
req = urllib.request.Request('http://127.0.0.1:17493/generate/stream', data=body, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=75) as r:
        data = r.read()
    dur = time.time() - t0
    print(f"Generated {len(data)} bytes in {dur:.2f}s ({len(data)/48000:.1f}s audio)")
except Exception as e:
    print(f"Error after {time.time()-t0:.2f}s: {e}")
