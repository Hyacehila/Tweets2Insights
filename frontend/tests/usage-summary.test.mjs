import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function load() {
  const source = await readFile(new URL("../src/lib/usage-summary.ts", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

test("unknown billed cost stays unknown, and both token schemas aggregate", async () => {
  const { summarizeUsage } = await load();
  const result = summarizeUsage({calls:3,known_cost:0,cost_complete:false,records:[
    {stage:"labels",provider:"decision",status:"returned",usage:{input_tokens:100,output_tokens:8,input_tokens_details:{cached_tokens:20}}},
    {stage:"labels",provider:"decision",status:"returned",usage:{prompt_tokens:200,completion_tokens:10,prompt_cache_hit_tokens:50}},
    {stage:"search",provider:"tavily",status:"returned",usage:{}},
  ]});
  assert.equal(result.cost, null);
  assert.equal(result.groups[0].input, 300);
  assert.equal(result.groups[0].output, 18);
  assert.equal(result.groups[0].cached, 70);
  assert.equal(result.groups[1].input, null);
  assert.equal(result.calls, 3);
});

test("returned zero cost is distinguished from missing usage", async () => {
  const { summarizeUsage } = await load();
  assert.equal(summarizeUsage({calls:0,known_cost:0,cost_complete:true,records:[]}).cost, 0);
  assert.equal(summarizeUsage({}).cost, null);
});
