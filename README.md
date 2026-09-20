# Hooshka Web Gateway Next — 1.0.0

**Canonical id:** `hooshka-web-gateway-next`
**نسخه:** `1.0.0-dev.0` (توسعه)
**وضعیت:** IN_DEVELOPMENT — روی پرت 5080 (تولیدیِ 5000 دست‌نخورده)

هدف اصلی: **رابط API استاندارد برای وب‌چت‌ها** تا سایر Agentها (مثل افزونه kilo در VS Code) با ابزارهای استاندارد و از طریق یک OpenAI-compatible API، از HWG استفاده کنند.

## مسیرها

- `main.py` — برنامه‌ی سرور Flask (پورت از `config.yaml`، پیش‌فرض 5080)
- `control_panel.py` — control panel در `/panel/` (blueprint همان app)
- `adapters/` — پل‌های پروایدر (chatgpt/deepseek/zai/qwen web)
- `core/` — تنظیم، ثبت پروایدر، gouvernance، mcp، feature، مرز agent
- `docs/` — اسناد نسخه‌دار (نیازمندی‌ها، مشخصات API، baseline، شواهد)
- `manage.py` — مدیریت سرویس/پروایدر/نشست/آمار
- `tests/` — آزمون‌ها

## راه‌اندازی (توسعه)

```powershell
# ۱) venv + وابستگی‌ها
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
# ۲) اجرا (بدون سرویس ویندوز، در ترمینال)
.\.venv\Scripts\python main.py
# ۳) پنل و API
#    http://127.0.0.1:5080/panel/
#    http://127.0.0.1:5080/v1/models
#    http://127.0.0.1:5080/health
```

## مستندات کلیدی

| سند | موضوع |
|---|---|
| `docs/requirements/HWG_1.0_REQUIREMENTS_REGISTER_20260920.md` | لیست درخواست‌ها (رجیستری) |
| `docs/HWG_1.0_AGENT_API_SPEC_v1.0.0-dev.0.md` | قرارداد API عامل‌ها (OpenAI-compatible) |
| `docs/HWG_1.0_DEVELOPMENT_BASELINE_20260920.md` | خط مبنای توسعه و ایزوله‌سازی |
| `CHANGELOG.md` · `VERSION` · `MANIFEST.json` | نسخه‌گذاری |

## نکته‌ی امنیتی

- این مخزن برای توسعه است؛ سرویس تولیدی روی 5000 را لمس نکنید.
- API remote از مخزن‌گیت seed حذف شده تا push ناخواسته به `khosravimm/hooshka-web-gateway` رخ ندهد.
- دسترسی غیر loopback فقط با کلید مجاز است.