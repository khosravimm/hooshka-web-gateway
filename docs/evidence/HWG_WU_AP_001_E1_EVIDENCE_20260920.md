# شواهد — WU-AP-001 (E1 محلی، بدون پروایدر)

- work_unit: WU-AP-001 — تأیید E1 محلی
- date: 2026-09-20
- result: **PASS**
- version_under_test: 1.0.0-dev.0 (commit 2dfcf9e)
- python: 3.13.6 (venv `.venv` در همین مخزن)

## ۱. بارگذاری و اتصال محلی (smoke با Flask test_client)

```text
GET /health    -> 200 {"legacy_service":"mcp-web-bridge","provider_runtime":{...},"service":"hooshka-web-gateway",...}
GET /ready     -> 200 {"mode":"fast","provider_runtime":{...},"providers":[...],...}
GET /v1/models -> 200 {"data":[{"id":"deepseek-web",...},{"id":"zai-web",...},...]}
GET /panel/    -> 200 <!DOCTYPE html> ... Hooshka Web Gateway - Control Panel
```

بدون دسترسی به CDP/مرورگر/اینترنت پروایدر؛ صرفاً بارگذاری `create_app('config.yaml')`.

## ۲. آزمون‌های واحد (pytest)

```text
$ .\.venv\Scripts\python -m pytest tests/test_agent_boundary_static.py \
    tests/test_feature_settings.py tests/test_tool_compat.py tests/test_tool_protocol.py \
    tests/test_runtime_inventory.py tests/test_stream_cancellation_static.py \
    tests/test_control_panel_model_settings.py tests/test_core.py \
    tests/test_action_candidate_bridge.py tests/test_retry_boundary.py \
    tests/test_provider_risk.py tests/test_upstream_response.py \
    -q -p no:cacheprovider --basetemp=...

110 passed in 0.88s
```

## ۳. نتیجه

- کد seed 0.7.29 در محیط ایزوله‌ی جدید (پورت 5080) بدون خطا بارگذاری و اجرا می‌شود.
- قرارداد پایه (health/ready/models/panel) مطابق انتظار پاسخ می‌دهد.
- E1 تثبیت شد؛ گام بعدی WU-AP-002 (اعتبارسنجی دقیق قرارداد با این spec) و WU-AP-004 (E2 روی پروایدر واقعی).