# HWG WU-UI-001 — طراحی (Design Study) بازطراحی UI کنترل‌پنل

- document_id: HWG-WU-UI-001-DESIGN-STUDY
- version: 0.1.0-draft
- date: 2026-09-20
- status: DRAFT — در انتظار تأیید مالک
- repo: hwg-next `D:\Code\hwg-next\hwg-next-1.0.0` (برنچ `v1.0.0-dev`)
- parent_mission: HWG-MISSION-NG-001 v1.0.0 (§11 Management UI، §12 Embedded Chat، §19 گیت ۱۰)
- owner_requirements: HWG-OWNER-REQUIREMENTS-20260920 (نکات ۱، ۲، ۹، ۱۳، ۱۴، ۱۷، ۱۸، ۱۹، ۲۰، ۲۱)
- relates_to: `docs/CONTROL_PANEL.md`، `control_panel.py`، `main.py`، `core/runtime_inventory.py`، `core/feature_settings.py`

---

## 1. خلاصه مالک (واقعیت‌محور)

مالک صریحاً اعلام کرده است:

- «UI نسخه فعلی اصلاً کامل و حرفه‌ای نیست و مورد تأیید من نیست.»
- «UI باید حرفه‌ای و کاملاً منطبق بر ابزارها و قابلیت‌های پروژه باشد؛ همه فعالیت‌های مدیریتی و نظارتی در اینترفیس مطابق حرفه‌ای‌ترین متدها و استانداردها پیاده‌سازی شود.»
- «تست صحت عملکرد UI یکی از مهم‌ترین و اصلی‌ترین تست‌های پایانی و تأیید صحت عملکرد نرم‌افزار است.»

بنابراین UI یک Deliverable درجه یک مأموریت است، نه یک لایه تزئینی. هر قابلیت runtime باید نمای UI متناظر داشته باشد و هر کنترل UI باید پشت API runtime (منبع حقیقت) کار کند.

---

## 2. روش (Method — Research-First)

بر اساس NG-MISSION §18 و نیازمندی ۱۰ (منع اختراع دوباره)، پیش از هر طراحی این منابع بررسی شد:

1. `HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md` — §11/§12/§13/§19/§20/§21 (IA الزامی، Embedded Chat، API Key، گیت‌های تست، ممنوعیت‌ها).
2. «درخواست‌ها و نیازمندی‌ها برای توسعه» (مالک) — ۲۱ نیاز شماره‌گذاری‌شده در رجیستری.
3. ممیزی کامل کد UI فعلی: `control_panel.py` (۲۲۴۸ خط، تک‌فایل با `render_template_string`، ۷ تب، ۲۱ مسیر `/panel/api/*`).
4. ممیزی Runtime API (منبع حقیقت): `main.py` — ۱۱ مسیر `/health`,`/ready`,`/health/deep`,`/modes`,`/v1/providers`,`/v1/capabilities`,`/v1/providers/<id>/features`,`/v1/models`,`/v1/chat/completions`,`/v1/chat/code`,`/v1/chat/conversation`.
5. `core/runtime_inventory.py` — مدل runtime مرورگر هر provider (kind=chrome_cdp، cdp_url، port، profile dir، home_url، label).
6. `core/feature_settings.py` — ساختار features (defaults/controls برای thinking و search).
7. دانش پیشین UI در مخزن قبلی 0.9.3 (research/reuse):
   - `HWG_1.0_UI_PHASE_EXECUTION.md` — «Runtime/Profile/Discovery state به‌عنوان منبع حقیقت واحد UI» و معیار پذیرش: expose state/action/progress/result/evidence/audit.
   - `HWG_1.0_UI_IMPLEMENTATION_STATUS.md` — IA هدف ۱۳ ناحیه.
   - `HWG_1.0_UI_EMBEDDED_CHAT_PHASE_STATUS.md` — وضعیت Embedded Chat و گپ‌های آن (capability-driven، certified-only، multimodal، profile/account، کنترل مکالمه، پیوند شواهد).
   - `HWG_1.0_UI_CHAT_002/003/004_*.md` — قرارداد payload با profile_id/account_id.
   - `HWG_1.0_UI_VERSIONING_POLICY.md` — UI باید `UI_VERSION.json` + CHANGELOG + مستند پیاده‌سازی + شواهد گواهی داشته باشد.
   - `HWG_UI_CHAT_PERSIAN_RICH_RENDER_CHANGE_20260919.md` — رندر RTL/فارسی پیام‌ها.

---

## 3. موجودی وضعیت فعلی (Baseline Inventory)

### 3-1. IA فعلی (کنترل‌پنل `/panel/`)

| تب | منبع داده | تغذیه از Runtime API؟ |
|---|---|---|
| Overview — کارت‌های آمار + System Health + Provider Runtime Readiness + Request Breakdown + Model Usage + نمودار درخواست/دقیقه | `/panel/api/*` | ✅ |
| Providers — جدول با Capability chip، Thinking/Search toggle، Default Model، Open/Start-Restart/Test | `/panel/api/providers` + PUT features/model + POST runtime/open/test | ✅ |
| Sessions — جدول مکالمات فعال + حذف | `/panel/api/sessions` | ✅ |
| API Keys — تولید، حذف، روشن/خاموش auth | `/panel/api/auth/*` | ✅ |
| Service — Start/Stop/Restart سرویس ویندوز + وضعیت + خروجی | `/panel/api/service/*` | ✅ |
| Config — فرم تنظیمات انسانی + Raw YAML | `/panel/api/config*` | ✅ |
| Logs — bridge/audit/service_stdout/service_stderr | `/panel/api/logs/<type>` | ✅ |

### 3-2. مشکلات ساختاری (شواهد ممیزی)

- تک‌فایل ۲۲۴۸ خطی: HTML+CSS+JS+backend در یک رشته خام → نگهداری/نسخه‌بندی/تست مشکل.
- `Мeta.evidence` هاردکد «E2 Thinking/Search 4x4» (رشته ثابت، نه از manifest).
- `_get_panel_meta` به `Path("D:/Code/mcp-web-bridge")` و مسیرهای هاردکد قدیمی وابسته است (با قانون reuse/config-driven ناسازگار).
- تب «Runtimes/Browser Tabs»، «Profiles»، «Accounts»، «Discovery/Certification»، «Models/Capabilities» و «Embedded Chat» وجود ندارد.
- اکشن‌های مخاطره‌آمیز (Stop/Restart، حذف key/سشن) فقط `confirm()` بومی دارند؛ پروتکل «state → progress → result → evidence → confirmation مناسب ریسک → post-action verification» (§11) کامل نیست.
- قابلیت‌های runtime که UI هنوز نمای تمام‌عیار ندارند: `search` و `reasoning` و `files` و `streaming_mode` و `transport_mode` در `capabilities` (فقط chip در Providers)، `max_concurrency/inflight/rejected/timeouts` در `/v1/models` (provider_runtime)، `loopback_policy` در `/v1/capabilities`.

---

## 4. شکاف IA (Gap Analysis) — نگاشت به NG-MISSION §11

| ناحیه مأموریت (§11) | وضعیت فعلی UI | پشتوانه runtime امروز | اقدام |
|---|---|---|---|
| Overview / Health | ✅ موجود (کارت + Health + نمودار) | `/panel/api/health`, `/stats`, `/model_usage` | بازطراحی بصری + افزودن Provider Concurrency/Inflight |
| Providers | ✅ موجود | `/v1/providers`, `/panel/api/providers` | یکپارچه‌سازی با Models/Capabilities |
| Profiles | ⛔ غایب | بکلاگ (مدل Profile هنوز در runtime نیست) | placeholder capability-gated (غیرفعال با وضعیت «در نقشه راه») |
| Accounts | ⛔ غایب | بکلاگ (نیاز NG-ACC-002 لاگین/لاگ‌اوت از پنل) | placeholder + وابسته به backend |
| Runtimes / Browser Tabs | ◑ جزئی (ستون Runtime در Providers + Open/Start) | `core/runtime_inventory.py` (cdp_url/port/profile/home_url/label per provider) | تب مستقل «Runtimes» با وضعیت هر Chrome/CDP/Profile + عمل Open/Start/Restart/Repair |
| Discovery / Certification | ⛔ غایب | بکلاگ (موتور کاوشگر هنوز در 1.0.0 نیست) | placeholder + ذخیره contract با مرجع NG-DISC-004 |
| Models / Capabilities | ◑ جزئی (Default Model در Providers) | `/v1/models`, `/v1/capabilities`, `capabilities.*` (search/reasoning/files/streaming_mode/transport_mode) | تب مستقل «Models & Capabilities» با ماتریس کامل هر provider |
| API Keys / Access | ✅ موجود | `/panel/api/auth/*`, `/v1/capabilities.access` | بازطراحی + One-time Secret Display + Label/Scope + metadata (NG-AUTH-001) |
| Sessions / Conversations | ✅ موجود | `/panel/api/sessions` | بازطراحی + abandon/pause نشانه |
| Request/Usage Telemetry | ◑ جزئی (Breakdown + Model Usage + نمودار) | `/panel/api/stats`, `/model_usage` | افزودن Provider Concurrency panel + تاریخچه‌های بیشتر |
| Logs / Evidence | ✅ موجود | `/panel/api/logs/*` | بازطراحی + فیلتر سطح + خط برجسته + دانلود |
| Configuration | ✅ موجود | `/panel/api/config*` | بازطراحی + تقسیم Server/Governance/Provider |
| Services / Restart / Release / Rollback | ◑ جزئی (Service + Restart) | `service_manager.ps1`, restart_state | پروتکل کامل اکشن با Confirmation/Verification؛ Release/Rollback بکلاگ (placeholder) |
| Embedded Chat | ⛔ غایب (در 1.0.0) | `/v1/chat/*` (completions/code/conversation) | WU-UI-002 (سری جداگانه) |

---

## 5. اصول طراحی (Design Principles)

1. **Runtime API منبع حقیقت است** (§11). UI هرگز وضعیتی را از backend جدا نمایش نمی‌دهد؛ هر سلول/بج/کنترل از یک endpoint تغذیه می‌شود. IgnoredState حذف.
2. **Capability-gated UI** (§12): فقط قابلیت‌هایی که runtime واقعاً supports/certified هستند فعال/قابل‌انتخاب‌اند؛ بقیه با وضعیت صریح «unavailable/backlog» نمایش داده می‌شوند (منع Fabricated Capability Success — §21).
3. **پروتکل اکشن مدیریتی** (از HWG_1.0_UI_PHASE_EXECUTION): هر اکشن (شروع، ری‌استارت، نجات، حذف، ذخیره، تولید کلید) این ۶ وجه را به‌صورت قابل‌مشاهده دارد: state → action → progress → result → evidence → audit trail؛ و confirmation متناسب با ریسک (اکشن‌های مخاطره‌آمیز تایید دومرحله‌ای)، سپس post-action verification.
4. **Persian/RTL اول** (نیاز مالک): زبان پیش‌فرض UI فارسی استاندارد، با حفظ اصطلاحات فنی انگلیسی؛ پشتیبانی RTL کامل و همگام با موتور رندر پیام چت (تجربه 0.9.3).
5. **بدون وابستگی خارجی/CDN** (سیاست موجود): CSS به‌صورت custom properties (پوسته light/dark)، JS بدون فریم‌ورک خارجی، نمودارها Canvas بومی. گواهی نهایی باید صفر درخواست خارجی را اثبات کند.
6. **نسخه‌بندی و مستندات** (HWG_1.0_UI_VERSIONING_POLICY): `UI_VERSION.json` (SemVer) + CHANGELOG + مستند پیاده‌سازی + شواهد گواهی برای هر تغییر UI.
7. **Safe Operation**: گواهی UI با پروفایل مرورگر ایزوله موقت (façade/headless)، نه تب‌های کاری/چت (docs/CONTROL_PANEL.md — «Safe operation rule»).
8. **No-Focus-Stealing** (NG-BRW-002): هیچ عملیات پس‌زمینه UI نباید مرورگر ظاهر را foreground کند.

---

## 6. معماری اطلاعات هدف (Target IA)

پوسته (Shell) با ناوبری گروه‌بندی‌شده؛ هر گروه یا «واقعی» است (runtime-backing امروز) یا «placeholder» با وضعیت صریح:

**گروه A — احوال و آمادگی (Operate)**
1. **Overview / Health**
2. **Runtimes / Browser Tabs** ← از `runtime_inventory` (cdp_url/port/profile/home_url/label) + Open/Start/Restart/Repair + وضعیت page‌های تب
3. **Providers**

**گروه B — قابلیت‌ها و مدل**
4. **Models & Capabilities** ← ماتریس provider × capability (chat/streaming+streaming_mode/tools/vision/embeddings/search/reasoning/files/transport_mode/max_context_tokens/supported_models) + selects مدل/رفچرها
5. **Profiles** (placeholder؛ contract NG-PROF)
6. **Accounts** (placeholder؛ NG-ACC-002 لاگین/لاگ‌اوت از پنل)

**گروه C — گفتگو و مصرف**
7. **Sessions / Conversations**
8. **Telemetry / Usage** (آمار، شکست، token accounting، concurrency)
9. **Embedded Chat** ← WU-UI-002 (در گروه خود با سطح اولیه)

**گروه D — مدیریت و کلید**
10. **API Keys / Access** (+ One-time secret display، label، revoke، audit)
11. **Config** (Server/Governance/Provider)
12. **Services / Restart / Release / Rollback** (Release/Rollback درباره placeholder)

**گروه E — شواهد**
13. **Logs / Evidence**
14. **Discovery / Certification** (placeholder؛ NG-DISC)

سربرگ ثابت: HWG نسخه (VERSION) + commit + branch + UI Version + Compatibility Manifest نسخه (از `/v1/capabilities`) + شاخص سلامت سرویس.

---

## 7. محدوده WU-UI-001 و معیار پذیرش

**در این آیتم (فاز مطالعه+پیاده‌سازی پوسته) انجام می‌شود:**

1. استخراج UI از تک‌فایل به ساختار حرفه‌ای: پوسته‌ی ماژولار `control_panel_ui/` با `panel.html/css/js` به‌عنوان static (عکس‌سازگار با سیاست بدون CDN)، بدون تغییر قرارداد `/panel/api/*` (Backward Compatible؛ regression از تب فعلی حفظ شود).
2. پیاده‌سازی گروه‌های A تا E برای مواردی که runtime-backing دارند (جدول §4)؛ placeholder‌ها با نشان «در نقشه راه».
3. پروتکل اکشن ۶‌وجهی + confirmation دومرحله‌ای برای مخاطره‌آمیزها + post-action verification.
4. حذف وابستگی‌های هاردکد (`D:/Code/mcp-web-bridge`) و تعویض `evidence` هاردکد با مقدار از manifest.
5. افزودن `UI_VERSION.json` + رکورد CHANGELOG.
6. متادیتای سربرگ: نسخه/commit/برنچ/UI_Version (+ نسخه Compatibility Manifest در دسترس).

**معیار پذیرش (DoD گیت §19-10 + تأیید قابلیت‌محور پیشین):**
- هر قابلیت runtime یک سطح UI متناظر دارد و وضعیت تنها از Runtime API خوانده می‌شود.
- هیچ قابلیتی بدون پشتوانه runtime «فعال» نمایش داده نمی‌شود.
- اکشن‌ها state/progress/result/evidence/audit را نمایش می‌دهند.
- رندر بدون هیچ درخواست خارجی (شواهد Network جزو گواهی).
- گواهی با پروفایل ایزوله موقت + تأیید تعاملی مالک.

---

## 8. وابستگی و ترتیب با سایر آیتم‌های UI

- WU-UI-002 (Embedded Chat) ساخته‌ی مستقل ولی هم‌پوسته با این طراحی؛ مصرف‌کننده `/v1/chat/*` + capability-gated (فقط مدل/پرایدرهای قابل‌انتخاب واقعی).
- WU-UI-003 (UX تک‌مرورگر/تب) وابسته به تصمیم معماری رانتایم (NG-BRW-001) است؛ UI فقط رابط مشاهده/کنترل Tab را فراهم می‌کند و خودش تغییر مرورگر انجام نمی‌دهد.
- WU-UI-004 گیت تست عملکردی نهایی است و شامل: render headless ایزوله، قرارداد `/panel/api/*`، هم‌راستایی IA فعلی/هدف، و تأیید تعاملی مالک.

---

## 9. سوالات باز نیازمند تصمیم مالک (پیش از پیاده‌سازی)

1. **زبان و جهت UI**: فارسی/RTL پیش‌فرض (با حفظ اصطلاحات فنی انگلیسی)؟ یا دوزبانه با تغییر زبان؟
2. **تم**: پیش‌فرض روشن + تم تاریک (toggle)؟ پالت رنگی مطلوب؟
3. **مسیر محصول**: UI جدید سرور-رندر بماند مثل امروز (بدون build step) یا transition به باندل static (در حد سیاست بدون CDN)؟
4. **Placeholder دامنه‌های بکلاگ** (Profiles/Accounts/Discovery/Certification/Release-Rollback): نمایش با صفحه خالی «در نقشه راه» تأیید می‌شود یا از ناوبری فعلاً حذف شوند تا پیاده شوند؟
5. **گفتگوهای Session**: قابلیت «ادامه/کپی/پاک کردن» مکالمه از UI تا چه حد در این چرخه لازم است؟
6. **Embedded Chat اولویت انتشار**: هم‌زمان با این بازطراحی یا چرخه بعد (WU-UI-002)؟

---

## 10. رکورد نسخه (Version Record)

| version | تاریخ | تغییر | وضعیت |
|---|---|---|---|
| 0.1.0-draft | 2026-09-20 | مطالعه طراحی + شکاف §4 + اصول §5 + IA §6 | DRAFT (منتظر تأیید مالک) |
| 1.0.0 | TBD | تصویب مالک | PENDING |

پس از تصویب، به `MANIFEST.json` و `CHANGELOG.md` نیز ارجاع داده می‌شود.