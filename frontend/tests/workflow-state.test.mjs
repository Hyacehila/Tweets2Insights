import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

test("saved demo configuration restores form dates, budget, modalities and dataset", async () => {
  const source = await readFile(new URL("../src/lib/workflow-state.ts", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
  const { workflowState } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
  const state = workflowState({event:{dataset_ref:"ds-demo",keywords:["夜骑", "开封"],input_mode:"existing",objectives:["retrospective"],search_provider:"tavily"},observations:{start:"2024-06-01T16:00:00Z",end:"2024-11-30T16:00:00Z"},labels:{provider:"openai_decisions",model:"gpt-6-luna",max_calls:300,max_images_per_post:3},media_mode:"text_image",forum_rounds:3});
  assert.equal(state.start, "2024-06-01T16:00");
  assert.equal(state.end, "2024-11-30T16:00");
  assert.equal(state.maxCalls, 300);
  assert.equal(state.dataset, "ds-demo");
  assert.equal(state.keywords, "夜骑，开封");
  assert.equal(state.mediaMode, "text_image");
  assert.equal(workflowState({media_mode:"text_only"}).mediaMode, "text_only");
  assert.equal(workflowState(null), null);
});
