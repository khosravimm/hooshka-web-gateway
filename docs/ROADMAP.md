# Hooshka Web Gateway — Roadmap

## اصل
Roadmap بر اساس capability و evidence رشد می‌کند، نه تعداد provider یا ادعای UI.

## مسیرهای کاری
1. **Session Integrity:** login رسمی/واقعی، persistence کنترل‌شده، تشخیص expiry و account-state.
2. **Provider Reliability:** health، timeout، retry، parsing و recovery مستقل برای هر provider.
3. **Capability Contract:** model discovery، chat/stream/tools فقط در سطح آزموده‌شده advertise شوند.
4. **Security:** حفاظت browser profile/session، loopback boundary، log redaction و abuse controls.
5. **Observability:** trace درخواست تا provider و evidence قابل تکرار.
6. **Client Compatibility:** Kilo/VS Code/OpenAI-compatible clients با test matrix مشخص.
7. **AWA Succession:** تصمیم مالک در 2026-09-11 بسته شد: Hooshka Web Gateway جایگزین AWA برای مأموریت Web-AI Gateway است. کار باقیمانده فقط انتقال/reuse دانش و capabilityهای مفید AWA با provenance است، نه تصمیم‌گیری مجدد درباره coexistence.

## Gateهای بلوغ
- E1: deterministic/synthetic
- E2: real provider end-to-end
- E3: اجرای تکرارشده با معیار و پنجره‌های مستقل

عبور به E3 فقط با reliability criteria از پیش تعریف‌شده مجاز است.
