
# Hooshka Web Gateway — Next Generation Production Mission

- Document ID: HWG-MISSION-NG-001
- Version: 1.0.0
- Status: Mandatory development mission
- Effective date: 2026-09-18
- Applies to: next production release after current HWG 0.7.x baseline
- Parent architecture: HWG-ARCH-001 v1.0.0

## 1. Mission

نسل جدید Hooshka Web Gateway باید به‌عنوان یک Gateway حرفه‌ای، نسخه‌دار، Research-first، Profile-driven، Multi-account و Multimodal تولید شود. نسخه جدید باید رفتارهای معتبر نسخه فعلی را حفظ کند و مدیریت اختصاصی Providerها را به Profile Contract، Discovery Engine، Runtime/Account Model، SDK استاندارد، UI حرفه‌ای و Compatibility Manifest قابل‌آزمون تبدیل کند.

توسعه فقط در محیط Development/Candidate ایزوله انجام می‌شود و تا قبل از عبور Release Candidate از تمام Acceptance Gateها و تأیید Cutover، نباید مأموریت یا Runtime نسخه عملیاتی مختل شود.

## 2. Non-negotiable product goals

1. یک قرارداد استاندارد HWG برای همه برنامه‌های مصرف‌کننده.
2. محصورسازی رفتار Provider پشت Profile/Adapter نسخه‌دار.
3. چند Account مستقل برای هر Provider.
4. Research/Reuse قبل از Custom Development.
5. Functional Readiness واقعی به جای Process-only Health.
6. Version و Change History برای هر Artifact مهم.
7. Evidence و Traceability کامل.
8. Management UI حرفه‌ای و Embedded Multimodal Chat.
9. SDK و Machine-readable Contract برای پروژه‌های دیگر.
10. Security/Privacy/Audit/Rollback به‌عنوان Release Gate.

## 3. Browser UX and isolation

### NG-BRW-001 — Unified visible browser UX
هدف UX این است که Provider/Accountهای قابل مشاهده در یک Browser Window و Tabهای مستقل نمایش داده شوند تا تعدد Windowها مزاحم کاربر نباشد. قبل از پیاده‌سازی باید Design Study و Prototype انجام شود. One-window UX نباید باعث Shared Cookies/Storage/Session میان Profileها شود. اگر Platform مرورگر جداسازی واقعی چند Profile را در یک Window تضمین نکند، Isolation مقدم است و معماری Broker/Partition/Context یا راهکار بالغ دیگری باید انتخاب شود.

### NG-BRW-002 — No focus stealing
Message injection، extraction، stream polling، health check و background navigation نباید Browser را foreground کند یا Focus کاربر را بگیرد. Focus فقط برای اقدام صریح کاربر مانند Open Browser، Login، CAPTCHA یا Interactive Certification مجاز است.

### NG-BRW-003 — Per-account isolation
هر Account Instance باید Session/Storage/Persistent State مستقل داشته باشد. Account A نباید Cookie، Entitlement، Model State یا Session Account B را دریافت کند.

## 4. Provider Profile requirements

### NG-PROF-001 — Versioned profile schema
یک JSON Schema نسخه‌دار برای Web Chat Profile ایجاد شود و مستندات انسانی از آن قابل تولید باشد.

### NG-PROF-002 — Behavior passport
شناسنامه هر Web Chat باید حداقل این موارد را ثبت کند: CAPTCHA/challenge، login/logout، server/account restrictions، quotas/rate signals، model catalog، model selection، context/input/output limits، thinking modes/levels و روش تشخیص، web search، provider-native tools/plugins، file/image/audio/video، streaming، completion، cancellation، session behavior، error/risk signals، silence/thinking/stalled classification، readiness و evidence.

### NG-PROF-003 — Account overlays
Profile عمومی Provider از Account Instance جدا باشد. هر Account بتواند Capability/Entitlement Snapshot خودش را داشته باشد.

### NG-PROF-004 — Version everything
Profile schema، Provider Profile، Account Capability Snapshot، Adapter، Transport، Discovery Recipe و Discovery Result همگی Version، Timestamp، Source/Evidence و Change Log داشته باشند.

## 5. Web Chat Discovery Engine

### NG-DISC-001 — Research-first
پیش از ساخت یا تغییر Integration هر Provider، تحقیق بیرونی الزام‌آور است: ابتدا مستندات رسمی Provider، سپس کد/Runtime و Evidence خود Provider، پروژه‌های متن‌باز بالغ Web-to-API، Issue/Forumهای فنی و در نهایت آزمایش کنترل‌شده. اختراع از صفر آخرین گزینه است.

### NG-DISC-002 — Automated exploration
موتور کاوشگر باید DOM/Accessibility، Network، SSE/WebSocket، Frontend JavaScript/Controllers، Model Selectors، Feature Controls، Upload Paths، Errors و Session Transitions را بررسی کند.

### NG-DISC-003 — Evidence discipline
هر Property دارای Evidence Type و Confidence است. E0/E1 بدون E2 واقعی به Operational Capability ارتقا نمی‌یابد.

### NG-DISC-004 — Interactive certification
مرحله نهایی Certification باید واقعی و با نظارت کاربر باشد. سیستم باید دقیقاً اعلام کند چه Provider/Account/Model/Thinking Level/Search/Tool State انتظار می‌رود، آن را اعمال کند، Prompt واقعی ارسال کند، پاسخ و Evidence را نمایش دهد و فقط با تأیید صریح کاربر نتیجه را Production-Certified کند.

### NG-DISC-005 — Drift detection
تغییر رفتار UI/Backend Provider باید Profile Drift تولید کند و Update Candidate بسازد؛ Production نباید با Patch پنهان و بدون Version/Evidence تغییر کند.

## 6. Startup and readiness

### NG-RDY-001
Startup/Restart باید تا Browser launch، CDP readiness، page interactive state، authentication و model/feature state صحیح صبر کند.

### NG-RDY-002
Provider/Account فقط پس از ارسال bounded non-sensitive test message و دریافت پاسخ معتبر READY می‌شود. Probe باید Rate-aware و قابل تنظیم باشد.

### NG-RDY-003
سیستم باید Thinking واقعی، normal latency، stalled stream/UI، silence، blocked request و server/account error را از هم تفکیک کند. Rules در Profile ثبت می‌شوند.

## 7. Session and account management

### NG-ACC-001
پس از Login اولیه کاربر، Session State و Metadata لازم برای استفاده بعدی به شکل صحیح و پایدار نگهداری شود. Secret صریح در Git/Plain Log ممنوع است و در صورت نیاز باید از OS-protected secret storage استفاده شود.

### NG-ACC-002
UI باید Login، Logout، Re-authentication و Session Validation برای Provider/Account ارائه کند.

### NG-ACC-003
API/Routing باید Target Account مشخص یا Policy-selected Account را پشتیبانی کند و Account Substitution پنهان ممنوع باشد.

## 8. Multimodal capability requirements

Canonical API و Profile Contract باید قابلیت کشف و نمایش Text، Image input/output، File/Document upload، Audio input/output، Video و سایر Mediaهای Provider را داشته باشد. هر Media Type باید constraints شامل MIME، size، duration/resolution در صورت وجود، lifecycle و privacy controls داشته باشد. Unsupported media صریحاً Fail می‌شود.

## 9. Tools, plugins and agent capabilities

Provider-native Tools/Plugins از Client-defined Function Tools جدا هستند. Profile باید نام، availability، enablement method، dependency به account/model، invocation/result detection و Evidence هر Provider-native tool را ثبت کند. Tool/function calling خارجی باید schema-validated و normalized باشد و Prose معمولی Tool Execution موفق محسوب نشود.

## 10. Standard integration and SDK

### NG-SDK-001 — No per-project reimplementation
پروژه‌های مصرف‌کننده نباید Connector اختصاصی Browser/Provider تولید کنند؛ فقط از HWG Client/SDK استفاده می‌کنند.

### NG-SDK-002 — Machine-readable documentation
OpenAPI و JSON Schema برای Provider Profiles، Capabilities، Request/Response، Streaming Events، Errors و Management APIs تولید و Version شوند.

### NG-SDK-003 — Reference SDKs
Reference Client نسخه‌دار حداقل برای Python و JavaScript/TypeScript تهیه شود مگر Evidence اولویت دیگری را توجیه کند. SDK باید Auth، Chat/Responses، Streaming، Media Upload، Tool Calls، Capability Discovery، Provider/Profile/Account Selection، Cancellation و Structured Errors را پوشش دهد.

### NG-SDK-004 — Contract tests
هر SDK باید در CI/Verification Gate علیه Conformance Test Server و Candidate HWG تست شود.

## 11. Management UI

UI فعلی Target پذیرفته‌شده نیست و باید بازطراحی حرفه‌ای شود. Information Architecture حداقل شامل Overview/Health، Providers، Profiles، Accounts، Runtimes/Browser Tabs، Discovery/Certification، Models/Capabilities، API Keys/Access، Sessions/Conversations، Request/Usage Telemetry، Logs/Evidence، Configuration، Services/Restart/Release/Rollback و Embedded Chat است.

Administrative Actionها باید Progress، State، Confirmation متناسب با Risk و Post-action Verification داشته باشند. Runtime API منبع حقیقت UI است.

## 12. Embedded Chat

یک Chat Surface مستقل داخل HWG ساخته شود که Markdown، Code Block، Table، Emoji، Image Rendering، File/Image Upload، Multimodal Message، Streaming، Provider/Model/Profile/Account Selection، Capability Indicators و Conversation Controls داشته باشد. UI فقط Capabilityهای واقعاً available/certified را فعال می‌کند.

## 13. API key and access

### NG-AUTH-001 — Key lifecycle
HWG باید API Key قوی تولید کند. UI باید Create، Label/Scope در صورت طراحی، One-time Secret Display، Metadata Listing، Revoke و Audit را پشتیبانی کند. Keyهای ذخیره‌شده در صورت امکان Verify-only و Hash شده باشند و Secret بعد از Creation قابل بازیابی نمایش داده نشود.

### NG-AUTH-002 — Local trust
Loopback/Internal Local Connection می‌تواند فقط تحت Local Trust Policy صریح و configurable بدون API Key وصل شود. Policy نباید LAN interface را به اشتباه Local Trusted تلقی کند.

### NG-AUTH-003 — Remote access
هر Non-loopback Access حداقل API Key می‌خواهد. Production Remote Exposure باید TLS termination، network ACL/firewall، rate limiting و audit داشته باشد. Bind مستقیم روی همه Interfaceها بدون این کنترل‌ها ممنوع است.

## 14. OpenAI compatibility

HWG باید OpenAI Compatibility Manifest نسخه‌دار و تاریخ‌دار داشته باشد. هر Release باید مستندات رسمی OpenAI را بررسی و Baseline را ثبت کند. Compatibility scope باید شامل مفاهیم مرتبط Responses API، Chat Completions، Streaming Events، Function/Tool Calling، Structured Schemas، Multimodal Inputs، Files/Uploads و Auth/Error conventions باشد.

کلمه «compatible» فقط همراه Scope و Manifest Version مجاز است. وضعیت هر Endpoint/Field/Event/Capability باید native، normalized، reconstructed/emulated، unsupported یا uncertified باشد. محدودیت Provider نباید به Silent Contract Violation تبدیل شود.

## 15. Versioning

همه اجزای مهم Version دارند: HWG Application، API Contract، Compatibility Manifest، Profile Schema، Provider Profiles، Account Capability Snapshots، Adapters/Transports، Discovery Engine، Discovery Recipes، SDKs، UI، Configuration Schema، Evidence Schema، Migration Scripts و Release/Candidate Records.

Semantic Versioning در جای مناسب ترجیح دارد. Breaking Change نیازمند Major Version/Explicit Migration Notes است.

## 16. Documentation

Documentation بخشی از Definition of Done است. Architecture، Profile Specification، Discovery Method، Security/Governance، API/OpenAPI Reference، SDK Guide، UI/Operations Guide، Account/Session Operations، Evidence/Certification Records، Compatibility Manifest، Release Notes، Migration و Rollback Guide باید Canonical و همگام باشند.

## 17. Security and privacy

Security Release Gate است. Least Privilege، Runtime Ownership، Account/Profile Isolation، Secret Management، Fail-closed Routing/Capabilities، Input/File Validation، Safe Logging، Rate Controls، Challenge/Account-risk Handling، Dependency/Supply-chain checks و Rollback باید تست شوند.

وجود قابلیت فنی HWG مجوز ارسال Sensitive Organizational Data به Web Chat نیست؛ Data Governance Approval مستقل لازم است.

## 18. Engineering and reuse

قبل از توسعه هر Subsystem، Internal Evidence Review و External Research انجام شود. Reuse/Configuration/Adaptation پروژه‌های بالغ با Custom Development مقایسه و تصمیم مهم در ADR ثبت شود. Existing validated capability باید قبل از Refactor Regression Test داشته باشد و Backward Compatibility حفظ شود مگر Breaking Change نسخه‌دار صریحاً تصویب شود.

## 19. Testing and evidence gates

Release Candidate حداقل باید این Gateها را پاس کند:

1. static/config/schema validation؛
2. unit tests؛
3. regression tests؛
4. API contract/conformance tests؛
5. SDK contract tests؛
6. runtime/profile isolation tests؛
7. no-focus-stealing tests؛
8. multi-account isolation tests؛
9. startup/restart readiness tests؛
10. UI functional tests؛
11. security/secret leakage tests؛
12. failure/retry/commitment tests؛
13. rollback test؛
14. targeted real-provider E2 tests؛
15. interactive user certification برای Profile جدید/تغییریافته.

Single live success فقط E2 است؛ Reliability Claim نیازمند E3 تکرارشده با معیار از پیش تعیین‌شده است.

## 20. Migration and cutover

Development/Candidate باید از Production ports، browser/session profiles و restart tasks جدا بماند. RC با Version + Commit immutable مشخص می‌شود. قبل از Cutover، Production Baseline، Config، Runtime Inventory و Rollback Point ثبت می‌شود.

پس از Cutover فوراً Liveness، Readiness، Functional Provider Probe و UI/Management Smoke Test اجرا می‌شود. Critical Gate Failure موجب Rollback به Baseline ثبت‌شده است.

## 21. Explicit prohibitions

- CAPTCHA/WAF/Suspension bypass ممنوع؛
- Silent Provider/Account Substitution ممنوع؛
- Fabricated Capability Success ممنوع؛
- Consumer dependency به DOM/Selector Provider ممنوع؛
- Unversioned Profile/Schema Change ممنوع؛
- Plaintext secret logging/commit ممنوع؛
- Focus stealing در Background Operation ممنوع؛
- In-place Production Experiment در صورت امکان Candidate isolation ممنوع؛
- Custom invention قبل از Research/Reuse analysis ممنوع.

## 22. Definition of Done

نسل جدید فقط با «کارکرد Chat» کامل نیست. تکمیل زمانی است که Profile/Discovery Contracts پیاده شده، Providerهای فعلی به Profileهای نسخه‌دار مهاجرت کرده‌اند، Multi-account/Session isolation اثبات شده، Functional Readiness وجود دارد، Multimodal Contract عملیاتی است، UI و Embedded Chat پذیرفته شده، SDK/OpenAPI/Schema تحویل شده، OpenAI Compatibility با Manifest/Conformance Suite اندازه‌گیری شده، Security Gates پاس شده، Documentation همگام است و Controlled Cutover/Rollback عملاً اثبات شده است.

## 23. Required delivery sequence

1. Freeze و Evidence current baseline؛
2. Research/Reference Architecture و Existing-project reuse audit؛
3. Schema/Contract/ADR design؛
4. Profile Schema + Runtime/Account Model؛
5. Discovery Engine MVP؛
6. Migration یک Provider به‌عنوان Pilot؛
7. Readiness/Certification Pipeline؛
8. New Control Plane/UI + Embedded Chat؛
9. SDK/OpenAPI/Compatibility Layer؛
10. Migration سایر Providerها؛
11. Multimodal/Tool/Plugin expansion؛
12. Security/Conformance/Regression hardening؛
13. RC build و User Certification؛
14. Controlled Production Cutover؛
15. Post-cutover review و Knowledge Return.

این مأموریت تابع HWG-ARCH-001 است. هر انحراف مهم نیازمند ADR ثبت‌شده و همگام‌سازی همزمان Architecture/Mission/Tests/Docs است.
