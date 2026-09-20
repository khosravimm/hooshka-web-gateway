# گواهی WU-AP-002/003 — اعتبارسنجی قرارداد و افزودن Endpointهای کشف

- شناسه گواهی: `HWG-WU-AP-002-003`
- تاریخ: 2026-09-20
- نسخه محیط: `hwg-next-1.0.0` (VERSION=1.0.0-dev.0)
- وضعیت: **PASS**

## WU-AP-002 — اعتبارسنجی قرارداد موجود (seed 0.7.29) در برابر `HWG_1.0_AGENT_API_SPEC`

### Observed (مطابق `main.py`)

| آیتم | یافته | وضعیت |
| --- | --- | --- |
| `/v1/models` | خروجی `data[]` با فیلدهای اضافی `mode`/`provider_runtime` | سازگار (اکستنشن مجاز) |
| `/v1/chat/completions` | اعتبارسنجی messages؛ روتینگ `provider_router.select_provider`؛ streaming شبیه OpenAI + keepalive + ترمینیتار `[DONE]` | سازگار |
| نگاشت خطا | `_http_status_for_error` مقادیر وارونه به `code` | پیش‌تر 400 برای همه → اصلاح شد |
| خطای مدل/پروایدر ناشناس | `provider_features` : 404 (درست)؛ chat_completions : 400 | **اصلاح → 404** |
| Auth | `auth_middleware`: loopback بدون کلید؛ غیر-loopback نیاز به `Bearer` معتبر (`api_keys`)؛ pathهای سلامت معاف | مطابق NG-AUTH-002/003 |
| Rate limit | `rate_limiter` پرورشدهنده per-provider (RPM از config) | مطابق |

### تغییرات کد (minimal، همراه با تست)

- `main.py`: `_http_status_for_error` اکنون `invalid_model`/`model_not_found` → `404`,
  `authentication_failed`/`auth_required` → `401`, بقیه → 400/500.
- `main.py` chat_completions: پروایدر ناشناس → `404` `unknown_provider`؛ عدم تطابق مدل →
  `404` `model_not_found` (جای `unknown_or_unsupported_model`). پیام ابزار Kilo/Qwen/Zai حفظ شد.

## WU-AP-003 — افزودن Endpointهای کشف (استاندارد برای عامل‌ها)

### پیاده‌سازی (main.py)

- `GET /v1/providers` → `{"object":"list","providers":[{id,type,enabled,priority,capabilities,features}],"default"}`
  با انتقال کد `/modes` به هلپر مشترک `_providers_summary()` در `create_app`.
- `GET /v1/capabilities` → `{manifest_version:"1.0", spec_version, compatibility_baseline:"openai-2026-09-20",
  generated_at, providers[], access:{loopback_without_key, non_loopback, auth_enabled}}`.

### آزمون‌ها — `tests/test_agent_api_contract.py` (۶ آزمون جدید)

| تست | انتظار | نتیجه |
| --- | --- | --- |
| `test_v1_providers_lists_registered_providers` | 200، شامل `chatgpt-web`، فیلدهای capabilities | PASS |
| `test_v1_capabilities_manifest` | manifest 1.0 + baseline + access | PASS |
| `test_modes_still_works` | سازگاری عقب‌گرد `/modes` | PASS |
| `test_chat_completions_unknown_model_is_404` | 404 + `model_not_found` | PASS |
| `test_chat_completions_unknown_provider_is_404` | 404 + `unknown_provider` | PASS |
| `test_chat_completions_missing_messages_is_400` | 400 + `invalid_request_error` | PASS |

### نتایج اجرا

```
116 passed in 0.80s   (110 قبلی + 6 جديد؛ بدون تماس با پروایدر/CDP)
```

## ثبت نسخه

- `CHANGELOG.md`: بخش 1.0.0-dev.0 به‌روز شد (WU-AP-002/003 + نتیجه آزمون).
- `MANIFEST.json`: gate `contract_apt = PASS` (tests: 116).
- `docs/HWG_1.0_AGENT_API_SPEC_v1.0.0-dev.0.md`: جدول §3 (دو endpoint «پیاده‌سازی‌شده») و §9 به‌روز شد.
- کار بعدی: WU-AP-004 — گواهی E2 با پروایدر واقعی (نیازمند تأیید مالک).