import assert from "node:assert/strict";
import { HwgClient } from "../src/index.ts";
assert.deepEqual(HwgClient.textPart("x"), {type:"text", text:"x"});
assert.equal(HwgClient.imagePart("data:image/png;base64,AA==").type, "input_image");
assert.equal(HwgClient.filePart("D:/x.pdf").type, "input_file");
const c = new HwgClient({baseUrl:"http://127.0.0.1:5080"});
assert.equal(c.baseUrl,"http://127.0.0.1:5080");
console.log("[PASS] TypeScript SDK contract helpers");
