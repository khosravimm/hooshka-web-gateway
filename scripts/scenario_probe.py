"""Scenario probe runner: S1..S5 per provider with evidence output."""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:5080"
LONG_TEXT = ("In exactly three words, reply with: LONG TEXT RECEIVED. "
             "Background context (ignore for the answer, only to enlarge the prompt): "
             + " ".join(f"filler-sentence-number-{i} about web gateway testing and monitoring."
                        for i in range(60)))

scenario = sys.argv[1] if len(sys.argv) > 1 else "S1"
model = sys.argv[2] if len(sys.argv) > 2 else "chatgpt-web"

if scenario == "S6":
    content = ("Explain in at least 5 full paragraphs what Hafez is known for. "
               "Each paragraph must be at least 3 sentences.")
    stream, thinking, search = False, False, False
    expect = None  # long answer: verify length instead of exact match
elif scenario == "S5":
    content, stream, thinking, search = LONG_TEXT, False, False, False
    expect = "LONG TEXT RECEIVED"
elif scenario == "S4":
    content, stream, thinking, search = "Reply exactly: HWG_E2_OK", True, False, False
    expect = "HWG_E2_OK"
elif scenario == "S3":
    content, stream, thinking, search = "Reply exactly: HWG_E2_OK", False, False, True
    expect = "HWG_E2_OK"
elif scenario == "S2":
    content, stream, thinking, search = "Reply exactly: HWG_E2_OK", False, True, False
    expect = "HWG_E2_OK"
else:
    content, stream, thinking, search = "Reply exactly: HWG_E2_OK", False, False, False
    expect = "HWG_E2_OK"

body = json.dumps({"model": model,
                   "messages": [{"role": "user", "content": content}],
                   "thinking": thinking, "search": search,
                   "stream": stream}).encode()
t = time.monotonic()
req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=500) as r:
        if stream:
            raw = r.read().decode("utf-8", "replace")
            ok = "[DONE]" in raw
            print("%s %s thinking=%s search=%s stream=True" % (scenario, model, thinking, search))
            print("status=200 elapsed=%.0fs done=%s chunks=%d" % (time.monotonic() - t, ok, raw.count("\n")))
        else:
            d = json.load(r)
            txt = d["choices"][0]["message"]["content"] or ""
            if expect is None:
                print("%s %s thinking=%s search=%s stream=False" % (scenario, model, thinking, search))
                print("status=200 elapsed=%.0fs len=%d long_answer=%s content=%r"
                      % (time.monotonic() - t, len(txt), len(txt) > 500, txt[:60]))
            else:
                print("status=200 elapsed=%.0fs len=%d exact=%s content=%r"
                      % (time.monotonic() - t, len(txt), expect in txt, txt[:60]))
            print("META " + json.dumps(d.get("provider_meta", {}), ensure_ascii=False)[:300])
except Exception as e:
    print("%s %s ERROR %r elapsed=%.0fs" % (scenario, model, e, time.monotonic() - t))
