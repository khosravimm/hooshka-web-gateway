import assert from "node:assert/strict";
import { HwgClient } from "../src/index.ts";

const c = new HwgClient({baseUrl:"http://127.0.0.1:5080", timeoutMs:180000});
const r = await c.chat(
  "deepseek-web",
  [{role:"user",content:"Reply exactly: HWG_TS_TARGET_E2_Q4B8"}],
  {},
  {provider:"deepseek-web", profileId:"deepseek-web:default", accountId:"deepseek-web:default-account"},
) as any;
assert.equal(r.choices?.[0]?.message?.content,"HWG_TS_TARGET_E2_Q4B8");
assert.equal(r.provider_meta?.inference_target?.account_id,"deepseek-web:default-account");
assert.equal(r.provider_meta?.inference_target?.profile_id,"deepseek-web:default");
console.log(JSON.stringify({content:r.choices[0].message.content,target:r.provider_meta.inference_target}));