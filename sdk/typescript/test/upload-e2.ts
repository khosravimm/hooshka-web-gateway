import assert from "node:assert/strict";
import { HwgClient } from "../src/index.ts";

const marker="HWG_TS_UPLOAD_E2_J8D4";
const c=new HwgClient({baseUrl:"http://127.0.0.1:5080",timeoutMs:180000});
const up=await c.upload([{name:"sdk_upload_marker_ts.txt",blob:new Blob([marker],{type:"text/plain"})}],"deepseek-web") as any;
const uid=up.data[0].id;
const r=await c.chat(
  "deepseek-web",
  [{role:"user",content:"Read the attached file and return only the exact verification marker contained in it."}],
  {upload_ids:[uid]},
  {provider:"deepseek-web",profileId:"deepseek-web:default",accountId:"deepseek-web:default-account"},
) as any;
assert.equal(r.choices?.[0]?.message?.content,marker);
assert.equal(r.provider_meta?.inference_target?.account_id,"deepseek-web:default-account");
const deleted=await c.deleteUpload(uid) as any;
assert.equal(deleted.deleted,true);
console.log(JSON.stringify({upload_id:uid,content:r.choices[0].message.content,target:r.provider_meta.inference_target,deleted:deleted.deleted}));