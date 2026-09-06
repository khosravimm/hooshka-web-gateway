import re


def parse_sse_chunks(body: str):
    events = []
    current_event = None
    current_data = None

    for raw_line in body.splitlines():
        line = raw_line.strip()

        if line.startswith("event:"):
            if current_event is not None or current_data is not None:
                events.append({"event": current_event, "data": current_data})
            current_event = line[len("event:"):].strip()
            current_data = ""
        elif line.startswith("data:"):
            current_data = line[len("data:"):].strip()
        elif line == "":
            if current_event is not None or current_data is not None:
                events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    if current_event is not None or current_data is not None:
        events.append({"event": current_event, "data": current_data})

    return events


def extract_text_from_sse_events(events):
    texts = []
    for ev in events:
        data = ev.get("data", "")
        if not data:
            continue
        try:
            import json
            obj = json.loads(data)
        except Exception:
            continue

        if isinstance(obj, dict):
            obj_type = obj.get("type", "")
            if obj_type == "delta" or obj_type.startswith("delta"):
                delta = obj.get("delta", {})
                if isinstance(delta, dict):
                    text = delta.get("content", "")
                    if text:
                        texts.append(text)
    return "".join(texts)
