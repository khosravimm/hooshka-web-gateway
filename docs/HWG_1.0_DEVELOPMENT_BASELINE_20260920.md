# HWG Next 1.0.0 — خط مبنای توسعه (Development Baseline)

- document_id: HWG-NG-BASELINE-20260920
- version: 1.0.0-dev.0
- date: 2026-09-20
- status: ACTIVE — توسعه در جریان (WIP)
- port: 5080 (توسعه)، 5000 (تولید دست‌نخورده)

## هدف

تولید «رابط API استاندارد برای وب‌چت‌ها» تا سایر Agentها (مثل افزونه kilo در VS Code) با ابزارهای استاندارد و از طریق یک OpenAI-compatible API، از HWG استفاده کنند — با رعایت مستندات و ثبت نسخه.

## منشأ (Seed)

- کپی از **`D:\Code\hooshka-web-gateway` v0.7.29** (نمونه‌ی عملیاتی در حال اجرا روی ۵۰۰۰) منتقل شد:
  `adapters/` (چت‌گپت/کیون/حإی/دیپ‌سک)، `core/`، `tools/`، `tests/`، `docs/`، `main.py`، `control_panel.py`، `manage.py`، `desktop_runtime_agent.py`.
- `.venv`، `.runtime`، `logs`، `.env`، `__pycache__` کپی نشد (حریم/پسماند).
- گیت‌هستوری seed حفظ شد و فقط remote تولیدی حذف خواهد شد تا push ناخواسته رخ ندهد.

## ایزوله‌سازی نسبت به تولید

| مؤلفه | تولیدی (دست‌نخورده) | این مخزن (توسعه) |
|---|---|---|
| پورت سرور | 5000 | **5080** |
| CDP | 9223/9224/9226 | 9323/9324/9325/9326 |
| پروفایل مرورگر | `.runtime\*` | `.runtime-dev\*` |
| نام سرویس | HooshkaWebGateway | HooshkaHWGNGDevGateway |
| سلامت | `http://127.0.0.1:5000/health` | `http://127.0.0.1:5080/health` |

## ساختار سندها

- `docs/requirements/HWG_1.0_REQUIREMENTS_REGISTER_20260920.md` — لیست درخواست (مالک + مأموریت NG + دانش‌انتقال)
- `docs/requirements/HWG_1.0_OWNER_REQUIREMENTS_20260920.md` — الحاقیه‌ی متن مالک
- `docs/HWG_1.0_AGENT_API_SPEC_v1.0.0-dev.0.md` — قرارداد API عامل‌ها
- `docs/HWG_1.0_DEVELOPMENT_BASELINE_20260920.md` — همین سند

## نقشه‌ی اجرا (Work Units)

1. **WU-AP-000** — بوت‌استرپ نسخه‌دار مخزن (این کار)؛ `VERSION`، `MANIFEST.json`، `CHANGELOG`، اسناد. ✅ انجام‌شده
2. **WU-AP-001** — تأیید E1 محلی: نصب وابستگی در venv اختصاصی، import/بارگذاری app، تست‌های unit و فلاسک بدون تماس با پروایدر.
3. **WU-AP-002** — اعتبارسنجی قرارداد موجود (seed): مطابقت `main.py` با مشخصات API (۴.۱، ۴.۲، خطاها، SSE).
4. **WU-AP-003** — افزودن `GET /v1/providers` و `GET /v1/capabilities` (Manifest نسخه‌دار).
5. **WU-AP-004** — گواهی E2 با یک پروایدر واقعی (chatgpt-web روی CDP 9324): `chat`، `stream`، `tools`؛ ثبت شواهد نگارشی در `docs/evidence/`.
6. **WU-AP-005** — اسناد استفاده‌ی Agent (مثال kilo/OpenAI SDK) + مقایسه با استاندارد.
7. **WU-AP-999** — گزارش نسخه و مرحله، بازبینی مالک.

## قواعد ثبت نسخه در این مخزن

- هر تغییر → `CHANGELOG.md` + اگر رفتار API عوض شود → نسخه‌ی spec.
- شواهد آزمون → `docs/evidence/` با timestamp و شماره نسخه.
- هر واحد کاری در انتها یک گزارش موقت مکتوب فارسی دارد.
- زبان مستندات: فارسی با اصطلاحات استاندارد.

## ممنوعیت‌ها (مستنسخ از رجیستری)

- لمس/توقف سرویس تولیدی ۵۰۰۰ و چون‌هاپروفایل 922x ممنوع.
- push به remote تولیدی ممنوع (remote حذف می‌شود).
- بدون Research/Reuse اولین گزینه، پیاده‌سازی نکن.
- اتصال/تست روی حساب‌های واقعی فقط concurrency=۱ و با آگاهی کاربر؛ بدون stress/بایپس.