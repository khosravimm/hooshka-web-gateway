# Project Profile — Hooshka Web Gateway / درگاه وب هوشکا

## هویت
- نام رسمی: Hooshka Web Gateway
- Technical id: `hooshka-web-gateway`
- Hooshka module id: `web_gateway`
- Repository: `khosravimm/hooshka-web-gateway`

## مأموریت
یک درگاه governed و واحد برای اتصال Hooshka و clientهای محلی به Web-chat providerها از طریق API محلی سازگار با OpenAI، بدون وابسته کردن Hooshka به DOM، session، transport یا رفتار اختصاصی هر provider.

## دامنه
- session/authentication واقعی provider
- provider adapterها
- model discovery/routing
- chat و compatibility API
- browser lifecycle
- parsing/retry/rate/health
- service management
- evidence سطح E1/E2/E3

## الزام امنیتی
استفاده از provider در حالت Guest نباید به‌عنوان مسیر عملیاتی معتبر تلقی شود. sessionهای احراز هویت‌شده باید به‌صورت کنترل‌شده مدیریت شوند و credential/session material نباید وارد Git یا لاگ ناامن شود.

## منابع حقیقت
1. `HOOSHKA_WEB_GATEWAY_START_HERE.md`
2. `docs/README.md`
3. `docs/ARCHITECTURE_CURRENT.md`
4. `docs/PROVIDERS.md`
5. `docs/SECURITY_GOVERNANCE.md`
6. `docs/OPERATIONS_RUNBOOK.md`
7. code/tests/config

## ارتباط با AWA
طبق تصمیم مالک در 2026-09-11، **Hooshka Web Gateway جایگزین AWA برای مأموریت Web-AI Gateway شده است**. AWA اکنون predecessor و منبع دانش/ADR/evidence است. قابلیت‌های مفید AWA باید با provenance بررسی و در صورت نیاز reuse شوند؛ توسعه جدید این مأموریت روی Hooshka Web Gateway انجام می‌شود.
