import assert from "node:assert/strict";
import { HwgClient, HwgError } from "../src/index.ts";

const BASE = process.env.HWG_BASE_URL ?? "http://127.0.0.1:5080";
const client = new HwgClient({ baseUrl: BASE, timeoutMs: 120000 });

const models = (await client.models()) as Array<{ id: string }>;
assert.ok(Array.isArray(models) && models.length >= 3, "models >= 3");
console.log(`[PASS] models n=${models.length}`);

const providers = (await client.providers()) as Array<{ id: string }>;
assert.ok(providers.length >= 3, "providers >= 3");
console.log(`[PASS] providers n=${providers.length} (${providers.map((p) => p.id).join(",")})`);

const caps = (await client.capabilities()) as Record<string, unknown>;
assert.ok(caps && typeof caps === "object", "capabilities object");
console.log(`[PASS] capabilities keys=${Object.keys(caps).length}`);

let bad: HwgError | null = null;
try {
  await client.chat("no-such-model", [{ role: "user", content: "hi" }]);
} catch (e) {
  bad = e as HwgError;
}
assert.ok(bad && bad.status === 404, "unknown model -> 404");
console.log(`[PASS] error envelope status=${bad?.status}`);

let seen = 0;
for await (const delta of client.chatStream("chatgpt-web", [
  { role: "user", content: "HWG_TS_CHECK" },
])) {
  seen++;
}
assert.ok(seen >= 1, "stream deltas");
console.log(`[PASS] chatgpt-web stream chunks=${seen}`);

const resp = (await client.respond("chatgpt-web", "HWG_TS_CHECK")) as Record<string, unknown>;
assert.ok(resp && typeof resp === "object", "responses ok");
console.log("[PASS] /v1/responses ok");