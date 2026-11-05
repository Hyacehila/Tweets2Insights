import assert from "node:assert/strict";
import test from "node:test";
import { consumeUIStream } from "../src/lib/ui-stream.mjs";

test("SSE preserves Chinese deltas split across byte boundaries and surfaces errors", async () => {
  const bytes = new TextEncoder().encode('event: delta\r\ndata: {"delta":"舆情"}\r\n\r\nevent: error\ndata: {"message":"HTTP 429"}\n\n');
  const source = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); } });
  const values = [];
  await consumeUIStream(source, (event, data) => values.push({ event, data }));
  assert.deepEqual(values, [{ event: "delta", data: { delta: "舆情" } }, { event: "error", data: { message: "HTTP 429" } }]);
});
