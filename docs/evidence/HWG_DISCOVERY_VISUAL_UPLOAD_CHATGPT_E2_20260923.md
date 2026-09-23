
## Explorer Engine 1.1.0 observations
The same qualification cycle exercised and extended HWG's own Explorer Engine. Read-only discovery now records `upload_surface`, `composer_selector`, and `assistant_surface`, and reports upload-class drift explicitly.

Live discovery observations during this slice:
- ChatGPT: three file inputs were observed; two media-specific inputs and one unrestricted `Attach files` input.
- Z.ai: one multiple file input advertised all eight qualification classes.
- Qwen: no file input was observed on the current live page; this is E1 absence only and is not treated as proof that Qwen can never upload files.

ChatGPT UI drift was also diagnosed through Explorer evidence: stale draft state, changed Send semantics, virtualized assistant response nodes, and conversation URL transition. The adapter now uses Explorer evidence for stateless composer preparation and selector-drift recovery.
