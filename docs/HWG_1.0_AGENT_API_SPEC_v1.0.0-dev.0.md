# HWG Agent API Specification — نسخه 1.0.0-dev.0

- document_id: HWG-AGENT-API-SPEC-1
- version: 1.0.0-dev.0
- date: 2026-09-20
- status: DRAFT — در حال تدوین، بدون ادعای تضمین سازگاری
- compatibility_claim: `openai-2026-09-20` — تنها با این scope و این نسخه از Manifest، لفظ «سازگار» مجاز است
- project: Hooshka Web Gateway Next (`hwg-next-1.0.0`)
- port (dev): 5080

> **هدف اصلی برنامه (شفاف‌سازی مالک):** یک رابط API استاندارد برای وب‌چت‌ها تا سایر Agentها با ابزارهای استاندارد از آن استفاده کنند (مثال: افزونه kilo در VS Code). این سند، قرارداد آن رابط است.

## ۱. اصل طراحی

- مصرف‌کننده هرگز به مرورگر، Profile، DOM یا پروتکل اختصاصی وب‌چت متصل نمی‌شود.
- HWG یک Gateway/واسط است؛ رفتار Provider (session/transport/capability) پشت Profile و Router fail-closed قرار دارد.
- لفظ «سازگار» فقط همراه Scope و نسخه‌ی این Manifest مجاز است.

## ۲. مرجع سازگاری OpenAI

- baseline این نسخه: **Responses API / Chat Completions + Streaming (SSE) + Function/Tool Calling + `/v1/models`** با قرارداد رسمی OpenAI مورد تأیید مالک در تاریخ 2026-09-20.
- هر Release جدید باید مستندات رسمی OpenAI را بررسی و baseline جدید را در Manifest ثبت کند.

## ۳. Endpointهای تعریف‌شده (نسخه‌ی قرارداد در این سند)

| Endpoint | روش | وضعیت در این نسخه | هدف برای Agent |
|---|---|---|---|
| `GET /health` | GET | پیاده‌سازی موجود (seed 0.7.29)؛ نیازمند سند | کفایت سرویس (liveness) |
| `GET /ready` | GET | موجود | آمادگی عملیاتی (readiness) |
| `GET /v1/models` | GET | موجود | کشف مدل/پروایدر (استاندارد OpenAI) |
| `POST /v1/chat/completions` | POST | موجود؛ نیازمند اعتبارسنجی دقیق قرارداد | چت/کدنویسی Agent (استاندارد OpenAI) |
| `POST /v1/chat/completions?stream=true` | POST | موجود (buffered compatibility)؛ نیازمند گواهی SSE | استریم پاسخ |
| `GET /v1/providers/<id>/features` | GET/PUT | موجود | بازخوانی/تنظیم ویژگی‌ها (thinking/search) |
| `GET /v1/providers` | GET | پیاده‌سازی‌شده (WU-AP-003) | فهرست و وضعیت در دسترس پروایدرها + capabilities |
| `GET /v1/capabilities` | GET | پیاده‌سازی‌شده (WU-AP-003) | Manifest توانمندی نسخه‌دار برای کشف خودکار |
| `POST /v1/files` | POST | جدید — placeholder | آپلود فایل/تصویر (مرحله‌ی چندوجهی) |

## ۴. قرارداد درخواست/پاسخ هسته

### ۴.۱ `POST /v1/chat/completions`

بدنه (مطابق قرارداد OpenAI):

```json
{
  "model": "chatgpt-web",
  "messages": [{"role": "user", "content": "..."}],
  "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {...}}}],
  "tool_choice": "auto",
  "stream": false,
  "temperature": 0.2
}
```

- `model`: فقط شناسه‌های اعلام‌شده در `/v1/models` و `supported_models` پروایدر؛ شناسه‌ی ناشناس ⇒ fail-closed خطای `model_not_found`.
- `provider > 1` هم‌پوشانی نام مدل: حالت `zai:glm-5.3` (زیررشته با prefix پروایدر) پشتیبانی می‌شود؛ بدون prefix، مسیر به پروایدر دارای آن مدل (exact routing) محدود است.
- `tools`: فقط ابزارهای تابعی با JSON Schema؛ `tool_call` معتبر فقط ارجاع به ابزار اعلام‌شده در همین درخواست.

### ۴.۲ اشکال استاندارد خطا (پاس‌نشده در تولیدی، اجباری)

```json
{"error": {"type": "invalid_request_error | model_not_found | provider_unavailable | server_overloaded | unsupported_feature | unsupported_tools", "code": "string"},
 "detail": "description",
 "request_id": "correlation-id"}
```

- کد وضعیت: `400` ورودی نامعتبر، `404` مدل/پروایدر ناشناس، `503` ناموجود/حجیم، `401/403` احراز/مجوز.

### ۴.۳ احراز (API Key)

- دسترسی non-loopback (غیر از 127.0.0.1) الزاماً کلید `Authorization: Bearer sk-...` می‌خواهد.
- اتصال loopback داخلی بدون کلید فقط تحت Local Trust Policy صریح مجاز است (پیش‌فرض تنظیم‌شدنی).
- کلیدها Verify-only/Hash ذخیره می‌شوند؛ Secret پس از ساخت قابل بازیابی نیست.

## ۵. استریم (SSE) — contract

- فرمت خط‌ها مطابق SSE استاندارد OpenAI: `data: {...}\n\n` و پایان `data: [DONE]`.
- چانک: `{"id","object":"chat.completion.chunk","choices":[{"delta":{"content":"..."},"index":0}]}`.
- گفت‌وگوی فعلی seed از «buffered compatibility streaming» استفاده می‌کند؛ provenance صادقانه در پاسخ/دیتا ثبت شود و در UI/Capabilities درج گردد.

## ۶. Tool Calling

- ابزارها در request تعریف و با allowlist اعتبار می‌شوند.
- هر `tool_call` با `id` و نام حاضر در allowlist؛ پاسخ‌ها با `role:"tool"` و `tool_call_id` پیوست می‌شوند.
- اعلام وضعیت هر tool در Capability Manifest: `supported/normalized/unsupported/uncertified`.
- Unsupported درخواست ابزار ⇒ خطای صریح `unsupported_tools`؛ هیچ پروایدر/مدل جایگزین پنهان نمی‌شود.

## ۷. Capability Manifest (`GET /v1/capabilities`) — قرارداد جدید

```json
{
  "manifest_version": "1.0.0",
  "compatibility_baseline": "openai-2026-09-20",
  "providers": [
    {"id": "chatgpt-web", "enabled": true,
     "models": ["chatgpt-web"],
     "capabilities": {"chat": true, "streaming": true, "streaming_mode": "buffered",
                      "tools": true, "visions": false, "files": false, "reasoning": true, "search": true,
                      "transport": "browser_ui"}}
  ],
  "access": {"loopback_without_key": "configurable", "non_loopback": "api_key_required"}
}
```

## ۸. قواعد مهندسی (ثبت‌شده در رجیستری)

- Research/Reuse-First پیش از هر پیاده‌سازی جدید (NG-DISC-001، NG-ENG-001).
- نسخه‌دارسازی و مستندات تغییر برای هر جزء (HWG-REQ-013/014/016، NG-VER-001، NG-DOC-001).
- رعایت استانداردها و الزامات زبان فارسی در همه‌ی مستندات و گزارش‌ها.
- E2 هر موفقیت واقعی = یک مورد؛ ادعای Reliability فقط با E3 تکرارشده.

## ۹. وضعیت اجرا در این نسخه

- WU-AP-002 (اعتبارسنجی قرارداد) و WU-AP-003 (افزودن `/v1/providers` و `/v1/capabilities`) کامل شد:
  - مدل/پروایدر ناشناس → `404` + کد `model_not_found` / `unknown_provider`.
  - `GET /v1/providers` (فهرست + capabilities + features) و `GET /v1/capabilities`
    (manifest نسخه‌دار + `compatibility_baseline: openai-2026-09-20` + خط‌مشی دسترسی) فعال شد.
  - آزمون‌های قرارداد در `tests/test_agent_api_contract.py` (پاس؛ مجموع 116 آزمون سبز).
- Endpointهای «موجود از seed» با گواهی E2 (پروایدر واقعی) هنوز اعتبارسنجی نشده‌اند (کار بعدی).