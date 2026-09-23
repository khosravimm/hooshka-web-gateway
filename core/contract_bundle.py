from __future__ import annotations

from pathlib import Path
import json

CONTRACT_VERSION = "1.0.0"
OPENAPI_VERSION = "3.1.0"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

SCHEMA_FILES = {
    "ProviderProfile": "hwg-provider-profile-v1.schema.json",
    "AccountInstance": "hwg-account-instance-v1.schema.json",
    "Capabilities": "hwg-capabilities-v1.schema.json",
    "Error": "hwg-error-v1.schema.json",
    "Event": "hwg-event-v1.schema.json",
    "CompatibilityManifest": "hwg-compatibility-manifest-v1.schema.json",
}

def load_schema_bundle() -> dict:
    schemas = {}
    for name, filename in SCHEMA_FILES.items():
        schemas[name] = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8-sig"))
    return {"contract_version": CONTRACT_VERSION, "schemas": schemas}

def compatibility_manifest() -> dict:
    return {
        "manifest_version": "1.0.0",
        "baseline": "openai-2026-09-20",
        "classification_values": ["native", "normalized", "reconstructed", "emulated", "unsupported", "uncertified"],
        "features": {
            "chat_completions": "normalized",
            "responses_api": "normalized",
            "streaming_events": "reconstructed",
            "function_tool_calling": "normalized",
            "structured_schemas": "normalized",
            "multimodal_inputs": "uncertified",
            "files_uploads": "uncertified",
            "auth_conventions": "normalized",
            "error_conventions": "normalized",
        },
    }

def build_openapi(app) -> dict:
    bundle = load_schema_bundle()
    paths = {}
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint == "static" or rule.rule.startswith("/flasgger_static") or rule.rule == "/apispec.json" or rule.rule == "/docs/":
            continue
        methods = sorted(set(rule.methods or ()) - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        path = rule.rule.replace("<path:", "{").replace("<string:", "{").replace("<int:", "{").replace("<", "{").replace(">", "}")
        item = paths.setdefault(path, {})
        for method in methods:
            operation_id = (rule.endpoint.replace(".", "_") + "_" + method.lower()).replace("-", "_")
            entry = {
                "operationId": operation_id,
                "summary": rule.endpoint.replace("_", " ").replace(".", " / "),
                "responses": {
                    "200": {"description": "Successful response"},
                    "400": {"description": "Invalid request", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
            params=[]
            for arg in sorted(rule.arguments):
                params.append({"name":arg,"in":"path","required":True,"schema":{"type":"string"}})
            if params:
                entry["parameters"] = params
            if method in {"POST","PUT","PATCH"}:
                entry["requestBody"] = {"required": False, "content": {"application/json": {"schema": {"type":"object","additionalProperties":True}}}}
            if path == "/v1/uploads" and method == "POST":
                entry["summary"] = "Create temporary media uploads"
                entry["requestBody"] = {
                    "required": True,
                    "content": {"multipart/form-data": {"schema": {
                        "type": "object", "required": ["files"],
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string", "format": "binary"}, "maxItems": 8},
                            "provider": {"type": "string"},
                        },
                    }}},
                }
                entry["responses"] = {
                    "201": {"description": "Upload IDs created"},
                    "400": {"description": "Invalid or uncertified media", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "413": {"description": "Upload exceeds configured size limit"},
                }
            elif path == "/v1/uploads/{upload_id}" and method == "DELETE":
                entry["summary"] = "Delete a temporary upload"
                entry["responses"] = {"200": {"description": "Deletion result"}}
            item[method.lower()] = entry
    return {
        "openapi": OPENAPI_VERSION,
        "info": {"title":"Hooshka Web Gateway API","version":CONTRACT_VERSION, "description":"Versioned HWG management and agent contract."},
        "servers": [{"url":"http://127.0.0.1:5080"}],
        "paths": paths,
        "components": {"schemas": bundle["schemas"]},
        "x-hwg-contract-version": CONTRACT_VERSION,
        "x-hwg-compatibility": compatibility_manifest(),
    }
