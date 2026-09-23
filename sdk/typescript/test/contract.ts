import assert from "node:assert/strict";
import { HwgClient } from "../src/index.ts";

assert.deepEqual(HwgClient.textPart("x"), {type:"text", text:"x"});
assert.equal(HwgClient.imagePart("data:image/png;base64,AA==").type, "input_image");
assert.equal(HwgClient.filePart("D:/x.pdf").type, "input_file");
const c = new HwgClient({baseUrl:"http://127.0.0.1:5080"});
assert.equal(c.baseUrl,"http://127.0.0.1:5080");

let captured: {url?: string; body?: string} = {};
const originalFetch = globalThis.fetch;
globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
  captured = {url:String(url), body:String(init?.body ?? "")};
  return new Response(JSON.stringify({object:"chat.cancel.result",cancelled:true}), {status:200,headers:{"content-type":"application/json"}});
}) as typeof fetch;
const cancel = await c.cancel({conversationId:"conv-ts",reason:"user_stop"}) as {cancelled:boolean};
assert.equal(cancel.cancelled,true);
assert.ok(captured.url?.endsWith("/v1/chat/cancel"));
assert.equal(JSON.parse(captured.body ?? "{}").conversation_id,"conv-ts");
globalThis.fetch = originalFetch;
console.log("[PASS] TypeScript SDK contract helpers + cancellation");
assert.deepEqual(HwgClient.target({provider:"deepseek-web",profileId:"deepseek-web:default",accountId:"deepseek-web:default-account"}), {
  provider:"deepseek-web",
  profile_id:"deepseek-web:default",
  account_id:"deepseek-web:default-account",
});

let uploadForm: FormData | null = null;
globalThis.fetch = (async (_url: string | URL | Request, init?: RequestInit) => {
  uploadForm = init?.body as FormData;
  return new Response(JSON.stringify({data:[{id:"up-ts"}]}), {status:201,headers:{"content-type":"application/json"}});
}) as typeof fetch;
const uploaded = await c.upload([{name:"marker.txt",blob:new Blob(["MARKER"],{type:"text/plain"})}],"deepseek-web") as any;
assert.equal(uploaded.data[0].id,"up-ts");
assert.ok(uploadForm instanceof FormData);
assert.equal(uploadForm?.get("provider"),"deepseek-web");
globalThis.fetch = originalFetch;

let respondBody = "";
globalThis.fetch = (async (_url: string | URL | Request, init?: RequestInit) => {
  respondBody = String(init?.body ?? "");
  return new Response(JSON.stringify({object:"response",output:[]}), {status:200,headers:{"content-type":"application/json"}});
}) as typeof fetch;
await c.respond("deepseek-web","hi",{}, {provider:"deepseek-web",profileId:"deepseek-web:default",accountId:"deepseek-web:default-account"});
const parsedRespond=JSON.parse(respondBody);
assert.equal(parsedRespond.provider,"deepseek-web");
assert.equal(parsedRespond.profile_id,"deepseek-web:default");
assert.equal(parsedRespond.account_id,"deepseek-web:default-account");
globalThis.fetch = originalFetch;
