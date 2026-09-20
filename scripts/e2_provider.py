import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5080"
PROMPT = "Reply exactly: HWG_E2_OK"


def default_model_from_config(config_path=None) -> str:
    config_path = Path(config_path or (ROOT / "config.yaml"))
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for p in data.get("providers", []) or []:
        if p.get("enabled", True) and p.get("id"):
            return p["id"]
    raise SystemExit("no enabled provider declared in config")


def _request(base, path, payload=None, timeout=180):
    url = f"{base}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--model", default=default_model_from_config())
    parser.add_argument("--prompt", default=PROMPT)
    args = parser.parse_args()

    steps = []

    def step(name, ok, detail=""):
        steps.append({"name": name, "pass": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}"[:300])

    try:
        status, raw = _request(args.base, "/v1/models")
        models = json.loads(raw).get("data", [])
        step("models-200", status == 200 and any(m.get("id") == args.model for m in models))

        status, raw = _request(args.base, "/v1/providers")
        body = json.loads(raw)
        step("providers-200", status == 200 and body.get("object") == "list")

        status, raw = _request(args.base, "/v1/capabilities")
        caps = json.loads(raw)
        step(
            "capabilities-200",
            status == 200 and caps.get("compatibility_baseline") == "openai-2026-09-20",
        )

        status, raw = _request(
            args.base,
            "/v1/chat/completions",
            {
                "model": args.model,
                "messages": [{"role": "user", "content": args.prompt}],
            },
        )
        body = json.loads(raw)
        content = ""
        if body.get("choices"):
            content = body["choices"][0].get("message", {}).get("content") or ""
        non_stream_content = (content or "").strip()
        step(
            "completion-200",
            status == 200 and bool(non_stream_content),
            f"status={status} len={len(non_stream_content)}",
        )

        status, raw = _request(
            args.base,
            "/v1/chat/completions",
            {
                "model": args.model,
                "messages": [{"role": "user", "content": args.prompt}],
                "stream": True,
            },
        )
        text = raw.decode("utf-8", "replace")
        step(
            "stream-done",
            status == 200 and "[DONE]" in text,
            f"status={status} chunks={text.count(chr(10))} done={('[DONE]' in text)}",
        )
    except Exception as e:
        step("e2-exception", False, repr(e))

    passed = sum(1 for s in steps if s["pass"])
    print(f"RESULT {passed}/{len(steps)}")
    sys.exit(0 if passed == len(steps) else 1)


if __name__ == "__main__":
    main()