# Hooshka Web Gateway — Knowledge Lifecycle

## هدف
دانش providerها سریع تغییر می‌کند. selector، endpoint، session behavior، frontend flow و anti-abuse behavior نباید به حافظه عامل یا logهای موقت محدود بماند.

## چرخه
`Observe → Capture Evidence → Classify → Validate → Decide → Implement → Retest → Record → Supersede`

## انواع دانش
- Provider behavior
- authentication/session behavior
- transport/backend findings
- DOM/frontend fallback
- client compatibility
- failure/recovery patterns
- security constraints
- rejected approaches

## قواعد
- observation یک Fact قطعی نیست تا evidence کافی داشته باشد.
- یافته provider-specific به provider دیگر تعمیم داده نشود.
- evidence حساس نباید cookie/token/session secret را افشا کند.
- سند قدیمی باید superseded/deprecated شود، نه بی‌صدا نادیده گرفته شود.
- تغییر architecture از research note مستقیم وارد canonical behavior نشود؛ ADR/decision لازم است.

## نگهداری
`docs/PROVIDERS.md` و architecture جاری باید summary canonical باشند؛ evidenceهای تاریخی باید قابل ردیابی باقی بمانند.
