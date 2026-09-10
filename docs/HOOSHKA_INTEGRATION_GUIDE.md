# Hooshka Integration Guide — web_gateway

## Integration principle

Hooshka must depend on the **local API contract**, not on provider adapter classes or browser internals.

Module id:

```text
web_gateway
```

Service:

```text
HooshkaWebGateway
```

Base URL:

```text
http://127.0.0.1:5000
```

## Recommended Hooshka adapter contract

Hooshka-side code should expose operations equivalent to:

```text
health()
ready()
capabilities()
models()
chat(request)
chat_stream(request)
```

These map to gateway HTTP endpoints.

## Startup dependency

Hooshka should not assume that a running Windows service means every Web provider is ready.

Recommended startup logic:

1. call `/health`;
2. call `/ready`;
3. fetch `/modes`;
4. cache canonical model/capability map briefly;
5. allow workloads only for providers reporting ready and required capabilities.

## Routing

Hooshka should choose canonical models explicitly:

```json
{"model":"chatgpt-web"}
```

or:

```json
{"model":"qwen-web"}
```

or:

```json
{"model":"zai-web"}
```

Hooshka must not implement its own provider fallback unless there is a separate governance policy that explicitly selects another provider before submission. The gateway itself does not silently cross-route.

## Feature negotiation

Before sending tools/search/files/vision, inspect `/modes`.

Example logic:

```text
need tools?
  -> provider.tools == true
     yes: dispatch
     no: reject/replan before sending
```

Do not send a tool-bearing request to Qwen/Z.ai in the current baseline.

## Error handling

Classify errors into:

- gateway unavailable;
- provider not ready;
- auth failure;
- rate limit;
- provider/account state;
- timeout before commitment;
- ambiguous/post-commit failure;
- unsupported capability;
- protocol failure.

For ambiguous/post-commit failure, Hooshka must not automatically replay the same user turn.

## Observability contract

Hooshka should capture:

- its own job/request correlation id;
- selected canonical provider/model;
- gateway response id;
- provider metadata/provenance;
- latency;
- normalized error class.

Do not copy provider credentials or browser session data into Hooshka logs.

## Sensitive-data gate

Before calling `web_gateway`, Hooshka should apply its own data-classification/policy gate. The gateway is a transport boundary, not a substitute for organizational data-governance approval.

## Availability model

Provider Web interfaces are inherently drift-prone. Hooshka should treat individual provider readiness as dynamic and degrade the relevant capability rather than treating the whole Hooshka system as failed.

## Suggested future integration

A small Hooshka-side client package can wrap the HTTP API, but provider adapters must remain owned by Hooshka Web Gateway.
