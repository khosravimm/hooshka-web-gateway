# HWG TypeScript client (NG-SDK-003)

Zero-dependency, standard-only surface mirroring `sdk/python/hwg_client.py`:
models, chat completions (incl. SSE streaming), responses, providers, capabilities.

## Usage

```ts
import { HwgClient } from "hwg-client";

const c = new HwgClient({ baseUrl: "http://127.0.0.1:5080", apiKey: "<optional>" });

const models = await c.models();
const reply = await c.chat("chatgpt-web", [{ role: "user", content: "Hi" }]);

for await (const delta of c.chatStream("deepseek-web", [{ role: "user", content: "Hi" }])) {
  // yield SSE data payloads (dicts) until [DONE]
}
```

## Verify

```sh
npm run typecheck        # tsc --noEmit (requires typescript installed locally)
node --experimental-strip-types test/smoke.ts   # live smoke vs HWG_BASE_URL
```