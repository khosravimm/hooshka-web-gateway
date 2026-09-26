# HWG 1.0 Requirements Register — لیست درخواست‌ها

- document_id: HWG-REQREG-20260920
- version: 1.0.0-dev
- date: 2026-09-20
- type: REQUIREMENTS_REGISTER (لیست درخواست مالک و مأموریت)
- status: RECORDED — ثبت به‌عنوان لیست درخواست؛ `implementation_action: NONE`
- scope: Hooshka Web Gateway (hwg-next)، ریشه `D:\Code\hwg-next\hwg-next-0.9.3`
- sources:
  - A — HWG-OWNER-REQUIREMENTS-20260920 (درخواست‌های اصلی و خاص مالک) → annex: `docs/HWG_1.0_OWNER_REQUIREMENTS_20260920.md`
  - B — `HWG-MISSION-NG-001 v1.0.0` (HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md)
  - C — `HWG-KT-WEBCHAT-001 v1.0.0` (WEBCHAT_PROVIDER_INTEGRATION_KNOWLEDGE_TRANSFER_V1.md)
- cross-cutting priority (owner): رعایت استانداردها و الزامات زبان فارسی، مستندسازی، ثبت نسخه

> این سند صرفاً رجیستری درخواست‌هاست. شروع هر پیاده‌سازی نیازمند دستور مالک، نسخه‌دارسازی و انطباق با قوانین Research/Reuse-First است.

## 00 — هدف اصلی برنامه (شفاف‌سازی مالک، 2026-09-20)

**هدف اصلی:** نوشتن یک **رابط API استاندارد برای وب‌چت‌ها** تا سایر Agentها بتوانند با ابزارهای استاندارد از آن استفاده کنند. مثال معنی‌دار مالک: افزونه‌ی kilo در VS Code باید بتواند از طریق API این برنامه، به‌راحتی کدنویسی کند.

پیامدها (برای مبنای همه‌ی بخش‌های A/B/C):
- HWG یک **Gateway/واسط استاندارد** است، نه یک چت‌باکس مستقل؛ کار اصلی، API مصرف‌پذیر استاندارد است.
- مصرف‌کننده هرگز به مرورگر، Profile، DOM یا پروتکل اختصاصی وب‌چت متصل نمی‌شود (هماهنگ با NG-SDK-001 و NG-PROHIBIT).
- اولویت ارزیابی همه‌ی درخواست‌ها: «این مورد چگونه به یک API استاندارد و قابلاستفاده برای Agent بیرونی تبدیل می‌شود؟».

## A — درخواست‌های اصلی و خاص مالک

متن کامل verbatim + نقشه به منابع موجود HWG در annex ثبت شده است. خلاصه‌ها:

| # | type | ID | موضوع |
|---|---|---|---|
| A1 | Browser UX | HWG-REQ-001 | تک‌مرورگر؛ هر پروایدر در تب مستقل |
| A2 | Browser UX | HWG-REQ-002 | تزریق بدون بالا آمدن/مزاحمت |
| A3 | Profile | HWG-REQ-003 | پروفایل اختصاصی/انحصاری هر وب‌چت + رابط استاندارد با هسته |
| A4 | Profile | HWG-REQ-004 | موتور ساخت/به‌روزرسانی پروفایل |
| A5 | Profile | HWG-REQ-005 | شناسنامه رفتار: کپچا، لاگین/لاگ‌اوت، محدودیت سرور/مدل/توکن/مصرف، thinking و سطح، جستجوی وب، پلاگین‌ها (@LCP)، مدل‌ها، محدودیت پنجره، تفکیک thinking از سکوت/بی‌پاسخی + پروتکل استاندارد |
| A6 | Readiness | HWG-REQ-006 | استارت/ری‌استارت: لود کامل + پیام آزمایشی + معرفی سالم/آماده |
| A7 | Accounts | HWG-REQ-007 | چند پروفایل در هر پروایدر (اکانت‌های متفاوت) |
| A8 | Accounts | HWG-REQ-008 | ثبت و نگهداری دقیق اکانت بعد از اولین ثبت |
| A9 | UI | HWG-REQ-009 | لاگین/لاگ‌اوت در پنل مدیریت |
| A10 | Discovery | HWG-REQ-010 | موتور کاوشگر هوشمند/دقیق + Research در مستندات/فروم‌ها/سایت‌های فنی/نمونه‌های APIسازی + منع اختراع دوباره |
| A11 | SDK | HWG-REQ-011 | ابزار Import و استفاده در پروژه‌های دیگر مطابق قابلیت‌های کامل HWG و بر مبنای اسناد |
| A12 | Discovery | HWG-REQ-012 | گام نهایی تأیید کاوشگر = تست تعاملی واقعی با نظارت/تأیید کاربر |
| A13 | Versioning | HWG-REQ-013 | همه چیز نسخه‌دار |
| A14 | Documentation | HWG-REQ-014 | همه چیز ثبت و مستند |
| A15 | Multimodal | HWG-REQ-015 | صدا/تصویر/ویدئو/فایل/عکس + پروفایل و رابط استاندارد + مستندات ماشین‌خوان + نسخه جزءها |
| A16 | Versioning | HWG-REQ-016 | نسخه + مستندات تغییرات پروفایل/رابط پروفایل/موتور کاوشگر |
| A17 | UI | HWG-REQ-017 | UI حرفه‌ای و کاملاً منطبق بر قابلیت‌ها؛ مدیریت/نظارت در اینترفیس |
| A18 | UI | HWG-REQ-018 | محیط چت داخلی در UI: مارک‌داون، ایموجی، جدول، نمایش عکس، آپلود فایل/عکس |
| A19 | Auth | HWG-REQ-019 | تولید API Key + بخش تولید/مدیریت کلید در UI |
| A20 | Auth | HWG-REQ-020 | دسترسی خارج از لوکال‌هاست فقط با کلید؛ اتصالات داخلی بدون کلید |
| A21 | Compatibility | HWG-REQ-021 | سازگاری ۱۰۰٪ با آخرین استانداردهای موردتأیید OpenAI + ثبت نسخه‌ی استاندارد رعایت‌شده |

## B — مأموریت Next-Generation (مأموریت الزامی HWG)

### اهداف غیرقابل مذاکره محصول

| ID | نیاز |
|---|---|
| NG-GOAL-001 | قرارداد استاندارد واحد HWG برای همه برنامه‌های مصرف‌کننده |
| NG-GOAL-002 | محصورسازی رفتار Provider پشت Profile/Adapter نسخه‌دار |
| NG-GOAL-003 | چند Account مستقل برای هر Provider |
| NG-GOAL-004 | Research/Reuse پیش از Custom Development |
| NG-GOAL-005 | Functional Readiness واقعی (نه Health شکلی) |
| NG-GOAL-006 | نسخه و Change History برای هر Artifact مهم |
| NG-GOAL-007 | Evidence و Traceability کامل |
| NG-GOAL-008 | Management UI حرفه‌ای + Embedded Multimodal Chat |
| NG-GOAL-009 | SDK و Machine-readable Contract برای پروژه‌های دیگر |
| NG-GOAL-010 | Security/Privacy/Audit/Rollback به‌عنوان Release Gate |

### Browser UX و ایزوله‌سازی (NG-BRW)

| ID | نیاز |
|---|---|
| NG-BRW-001 | UX یک مرورگر و تب‌های مستقل؛ جداسازی واقعی Cookie/Storage/Session بین Profileها؛ Design Study + Prototype پیش از پیاده‌سازی؛ در غیرآن Isolation مقدم است |
| NG-BRW-002 | بدون Focus Stealing در تزریق/استخراج/poll/health/navigation؛ Focus فقط برای اقدام صریح کاربر (Open/Login/CAPTCHA/Certification) |
| NG-BRW-003 | ایزوله‌سازی کامل per-account: Session/Storage/Persistent State مستقل |

### Profile ارائه‌دهنده (NG-PROF)

| ID | نیاز |
|---|---|
| NG-PROF-001 | JSON Schema نسخه‌دار Profile + مستندات انسانی قابل تولید |
| NG-PROF-002 | Behavior Passport: کپچا، لاگین/لاگ‌اوت، محدودیت‌ها، quota/rate، کاتالوگ مدل، انتخاب مدل، محدودیت متن ورودی/خروجی، thinking mode/level + روش تشخیص، جستجوی وب، tools/plugins بومی، فایل/تصویر/صدا/ویدئو، streaming، completion، cancellation، رفتار نشست، سیگنال خطا/ریسک، طبقه‌بندی silence/thinking/stalled، readiness و evidence |
| NG-PROF-003 | تفکیک Profile عمومی ارائه‌دهنده از Account Instance + Capability/Entitlement Snapshot هر Account |
| NG-PROF-004 | نسخه/Timestamp/Source/Evidence/ChangeLog برای Profile Schema، Provider Profile، Account Snapshot، Adapter، Transport، Discovery Recipe و Result |

### موتور کشف Web Chat (NG-DISC)

| ID | نیاز |
|---|---|
| NG-DISC-001 | Research-first: مستندات رسمی ← کد/رانتایم خودِ Provider ← پروژه‌های متن‌باز Web-to-API بالغ ← Issue/Forum فنی ← آزمایش کنترل‌شده؛ اختراع از صفر آخرین گزینه |
| NG-DISC-002 | اکتشاف خودکار: DOM/Accessibility، Network، SSE/WebSocket، JS/Frontend، Model Selectors، Feature Controls، Upload Paths، Errors، Session Transitions |
| NG-DISC-003 | هر Property دارای Evidence Type و Confidence؛ ارتقا به Operational Capability فقط با Evidence واقعی |
| NG-DISC-004 | Interactive Certification با نظارت کاربر؛ اعمال و بررسی وضعیت دقیق Provider/Account/Model/Thinking/Search/Tool؛ ارسال Prompt واقعی؛ نمایش پاسخ و Evidence؛ تأیید صریح کاربر برای Production-Certified |
| NG-DISC-005 | Drift Detection: تغییر رفتار ← تولید Profile Drift + Update Candidate با نسخه/Evidence؛ منع Patch پنهان |

### Startup و Readiness (NG-RDY)

| ID | نیاز |
|---|---|
| NG-RDY-001 | انتظار برای Browser launch، CDP readiness، صفحه interactive، احراز و وضعیت صحیح model/feature |
| NG-RDY-002 | آماده شدن Provider/Account فقط پس از ارسال پیام آزمایشی غیرحساس (bounded) و دریافت پاسخ معتبر؛ Probe Rate-aware |
| NG-RDY-003 | تفکیک Thinking واقعی، تأخیر عادی، stalled stream/UI، سکوت، blocked، خطای سرور/اکانت؛ Rules در Profile |

### مدیریت نشست و اکانت (NG-ACC)

| ID | نیاز |
|---|---|
| NG-ACC-001 | نگهداری صحیح/پایدار Session و Metadata پس از Login اولیه؛ منع Secret در Git/Log صریح؛ استفاده از OS-protected storage در صورت نیاز |
| NG-ACC-002 | UI برای Login، Logout، Re-authentication و Session Validation |
| NG-ACC-003 | پشتیبانی Target Account / Policy-selected در API؛ منع Account Substitution پنهان |

### چندوجهی (Multimodal) — NG-MM-001
Canonical API و Profile Contract باید Text، Image (in/out)، File/Document Upload، Audio، Video و سایر Media را کشف و نمایش دهد؛ هر Media Type با constraints (MIME/size/duration-resolution/lifecycle/privacy)؛ Unsupported صریحاً Fail می‌شود.

### Tools/Plaugins و قابلیت‌های Agent — NG-TOOL-001
جداسازی Tools بومی Provider از Function Tools کلاینتی؛ ثبت نام/دسترسی/روش فعال‌سازی/وابستگی به account-model/تشخیص فراخوانی-نتیجه/Evidence در Profile؛ Tool Calling خارجی schema-validated و normalized؛ نپذیرفتن Prose معمولی به‌عنوان Tool Execution موفق.

### یکپارچه‌سازی استاندارد و SDK

| ID | نیاز |
|---|---|
| NG-SDK-001 | منع بازپیاده‌سازی per-project؛ مصرف‌کننده فقط از HWG Client/SDK |
| NG-SDK-002 | مستندات ماشین‌خوان نسخه‌دار: OpenAPI + JSON Schema (Profiles، Capabilities، Request/Response، Streaming Events، Errors، Management APIs) |
| NG-SDK-003 | Reference SDK نسخه‌دار (حداقل Python و JS/TS) با پوشش Auth، Chat/Responses، Streaming، Media Upload، Tool Calls، Capability Discovery، انتخاب Provider/Profile/Account، Cancellation، Structured Errors |
| NG-SDK-004 | Contract Tests در CI علیه Conformance Test Server و Candidate HWG |

### مدیریت UI

| ID | نیاز |
|---|---|
| NG-UI-001 | بازطراحی حرفه‌ای؛ IA حداقلی: Overview/Health، Providers، Profiles، Accounts، Runtimes/Browser Tabs، Discovery/Certification، Models/Capabilities، API Keys، Sessions/Conversations، Telemetry، Logs/Evidence، Configuration، Services/Restart/Release/Rollback، Embedded Chat |
| NG-UI-002 | Administrative Actions دارای Progress/State/Confirmation بر اساس Risk + Post-action Verification؛ Runtime API منبع حقیقت UI |

### چت تعبیه‌شده — NG-CHAT-001
Chat Surface مستقل با Markdown، Code Block، Table، Emoji، Image Rendering، File/Image Upload، Multimodal Message، Streaming، انتخاب Provider/Model/Profile/Account، Capability Indicators، Conversation Controls؛ فعال‌سازی فقط Capabilityهای available/certified.

### API Key و دسترسی

| ID | نیاز |
|---|---|
| NG-AUTH-001 | چرخه عمر کلید: تولید قوی، Create/Label/Scope، نمایش یک‌باره، Listing، Revoke، Audit؛ کلیدها Verify-only/Hash؛ عدم بازیابی Secret |
| NG-AUTH-002 | Loopback/Internal فقط تحت Local Trust Policy صریح و configurable؛ عدم تلقی اشتباه LAN به‌عنوان Local Trusted |
| NG-AUTH-003 | Non-loopback حداقل API Key؛ Exposure با TLS/ACL/rate-limit/audit؛ منع Bind مستقیم روی همه‌ی اینترفیس‌ها بدون کنترل |

### سازگاری OpenAI — NG-COMP-001
Compatibility Manifest نسخه‌دار/تاریخ‌دار؛ بررسی مستندات رسمی OpenAI در هر Release و ثبت Baseline؛ پوشش Responses API، Chat Completions، Streaming Events، Function/Tool Calling، Structured Schemas، Multimodal Inputs، Files/Uploads، Auth/Error؛ «compatible» فقط با Scope و Manifest Version؛ وضعیت هر Endpoint/Field/Event = native/normalized/emulated/unsupported/uncertified؛ منع Silent Contract Violation.

### نسخه‌بندی — NG-VER-001
همه‌ی اجزای مهم نسخه‌دار (HWG App، API Contract، Compatibility Manifest، Profile Schema، Provider Profiles، Account Snapshots، Adapters/Transports، Discovery Engine/Recipes، SDKs، UI، Config/Evidence Schema، Migration Scripts، Release Records). SemVer در جای مناسب؛ Breaking Change با Major + Migration Notes.

### مستندسازی — NG-DOC-001
Documentation بخشی از Definition of Done؛ همگام‌سازی Canonical: Architecture، Profile Spec، Discovery Method، Security/Governance، API/OpenAPI Reference، SDK Guide، UI/Operations، Account/Session، Evidence/Certification، Compatibility Manifest، Release Notes، Migration/Rollback.

### امنیت و حریم خصوصی — NG-SEC-001
Security یک Release Gate است: Least Privilege، Runtime Ownership، Account/Profile Isolation، Secret Management، Fail-closed Routing/Capabilities، Input/File Validation، Safe Logging، Rate Controls، Challenge/Risk Handling، Dependency Checks، Rollback. وجود قابلیت فنی مجوز ارسال داده‌ی سازمانی نیست؛ Data Governance Approval مستقل لازم دارد.

### مهندسی و Reuse — NG-ENG-001
پیش از توسعه هر Subsystem: Internal Evidence Review + External Research؛ مقایسه Reuse/Config/Adaptation با Custom و ثبت ADR؛ Regression Test پیش از Refactor؛ Backward Compatibility مگر Breaking Change نسخه‌دار تصویب‌شده.

### Testing/Evidence Gates — NG-TEST-001
۱۵ گیت RC (static/schema، unit، regression، API/conformance، SDK contract، runtime/profile isolation، no-focus-stealing، multi-account isolation، startup/restart readiness، UI functional، security/secret، failure/retry/commitment، rollback، real-provider E2، interactive user certification).
**NG-EVIDENCE-001:** تک‌موفقیت = E2؛ ادعای Reliability نیازمند E3 تکرارشده با معیار از پیش تعیین‌شده.

### مهاجرت و Cutover — NG-CUT-001
جداسازی Dev/Candidate از Production (ports، browser/session، restart)؛ RC با Version+Commit؛ ثبت Baseline/Config/Inventory/Rollback Point قبل از Cutover؛ Liveness/Readiness/Functional Probe/UI Smoke بعد از Cutover؛ Critical Failure ← Rollback به Baseline ثبت‌شده.

### ممنوعیت‌های صریح — NG-PROHIBIT-001
۹ مورد (bypass کپچا/WAF/Suspension، Account Substitution پنهان، Fabricated Capability، وابستگی مصرف‌کننده به DOM/Selector، تغییر Profile/Schema بی‌نسخه، ثبت Secret بی‌شکل، Focus Stealing، Experiment درجا، اختراع پیش از Research/Reuse).

### تعریف انجام — NG-DOD-001 و ترتیب تحویل — NG-SEQ-001..015
DoD: کارکرد کامل Chat کافی نیست؛ تکمیل با Profile/Discovery Contracts، مهاجرت Providerها به Profile نسخه‌دار، ایزوله multi-account، Functional Readiness، Multimodal عملیاتی، UI و Embedded Chat پذیرفته، SDK/OpenAPI/Schema تحویل، OpenAIC Compatibility با Manifest/Conformance، Security Gates، Docs همگام، Cutover/Rollback اثبات‌شده. ترتیب ۱۵ مرحله (Freeze ← Research/Reuse аудит ← Schema/ADR ← Profile+Runtime/Account ← Discovery MVP ← Pilot Provider ← Readiness/Cert Pipeline ← Control Plane/UI+Chat ← SDK/Compatibility ← سایر Providerها ← Multimodal/Tool ← Hardening ← RC+User Cert ← Cutover ← Post-review/Knowledge Return).

## C — نیازمندی‌های حفظ‌شده از دانش‌انتقال (مواردی که باید حفظ/بازطراحی شوند)

| ID | نیاز |
|---|---|
| KT-CORE-001 | استانداردسازی معنایی در هسته (روتینگ fail-closed، stream-state، commitment، tool-normalization، error/evidence schema، readiness contract، certification workflow)؛ نگه‌داشتن جزئیات در Provider (selectors، endpoints، proofهای anti-bot، معناهای native، upload mechanics) |
| KT-CORE-002 | Commitment boundary: `not_sent→maybe_sent→committed→terminal`؛ منع Replay پس از ارسال احتمالی |
| KT-CORE-003 | State machine جریان: CONNECTING/HEADERS/WAITING_FIRST_EVENT/STREAMING/TOOL_AMBIGUOUS/COMPLETED/FAILED/CANCELLED؛ تفکیک timeouts |
| KT-CORE-004 | HTTP 200 ≠ موفقیت؛ طبقه‌بندی Content-Type/Application Envelope پیش از Stream Parser |
| KT-CORE-005 | پارس tool با allowlist، parse متوازن، repair محدود شناخته‌شده، fail صریح؛ مجموعه‌ی خالی Tool هرگز wildcard نیست |
| KT-CORE-006 | یک Profile/Account = مرز امنیتی؛ یک مالک runtime؛ CDP identity verified؛ منع killing با URL |
| KT-CORE-007 | Risk-Control: concurrency=۱، spacing، session reuse، منع stress/rotation/bypass، توقف بر سیگنال ریسک، تفکیک خطای account-local از provider-wide |
| KT-CORE-008 | مراحل Readiness صریح تا READY با Probe واقعی (RUNTIME…→FUNCTIONAL_PROBE_RUNNING→READY/DEGRADED/BLOCKED/FAILED) |
| KT-CORE-009 | تفکیک Thinking / صبر اولیه / جریان بدون متن (reasoning) / stalled / quota / challenge / تکمیل بدون متن / خطای транспорт از روی State+evidence نه صرف زمان |
| KT-CORE-010 | Observability: فراداده‌ی محدود بدون raw prompt/response/cookie/token |
| KT-CORE-011 | نردبان Evidence E0-E3 با مقادیر صادق در Claims |
| KT-CORE-012 | Regression corpus حفظ‌شدنی: ۲۳ مورد آموخته‌شده (React drift، Thinking به‌جای خروجی، Silent Routing، HTTP-200 JSON، IDP logout، Retry پس از Commit، Focus Stealing، …) |
| KT-CORE-013 | عدم کپی‌کور Selectorها در Adapter بزرگ؛ عدم وابستگی account در Profile عام؛ عدم فرض one-profile-per-provider؛ صداقت Stream Provenance |
| KT-CORE-014 | Knowledge Return در هر تغییر (Profile/Adapter/Evidence/Playbook/Regression/ADR)؛ رفع بدون مستندسازی ناقص است |

## D — محدودیت‌های ثبت

- وضعیت همه‌ی موارد: `RECORDED`؛ `implementation_action: NONE` تا دستور مالک.
- اولویت مالک (cross-cutting) بر همه‌ی موارد: **استانداردها/الزامات زبان فارسی، مستندسازی، ثبت نسخه**.
- پیش از هر گام پیاده‌سازی: نسخه‌دارسازی، Research/Reuse-First (NG-DISC-001/NG-ENG-001) و ثبت ADR در موارد مهم.
## Owner clarification — 2026-09-26 / Connection Profile & Integrated Explorer

| ID | Area | Owner requirement | Status | Primary trace |
|---|---|---|---|---|
| A22 / HWG-REQ-022 | Profile/Account UX | Multi-account Provider must expose explicit user-facing Connection Profiles; same-origin accounts require isolated Browser Profile/Runtime. | PARTIAL/E2 — DeepSeek multi-account proven; generalized UX continues | `HWG-WORK-026`, `HWG-WORK-030` |
| A23 / HWG-REQ-023 | Profile UX | Suggest human-readable profile name from Provider/account evidence; user edits/confirms; no silent overwrite after confirmation. | E1 + automated visual E2 / HUMAN ACCEPTANCE PENDING | `HWG-WORK-030`, `HWG_CONNECTION_PROFILE_ACCEPTANCE_AUTOMATED_E2_20260926.md` |
| A24 / HWG-REQ-024 | Explorer UX | Real Provider target remains visible/interactable inside Wizard workspace with safe native-tab fallback. | PARTIAL/E2 | `HWG-WORK-029`, `HWG_INTEGRATED_EXPLORER_WORKSPACE_E2_20260924.md` |
| A25 / HWG-REQ-025 | Control Plane IA | Primary navigation is mission/workspace-driven and makes Provider→Connection Profile→Account→Runtime/Readiness/Certification traceable. | E1 + automated scenario audit / HUMAN ACCEPTANCE PENDING | `HWG-WORK-030`, `HWG_CONNECTION_PROFILE_ACCEPTANCE_AUTOMATED_E2_20260926.md` |
