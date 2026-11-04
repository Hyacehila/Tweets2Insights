import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function load() {
  const source = await readFile(new URL("../src/lib/dataset-import.ts", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

test("paired images replace matching references once and preserve order and text", async () => {
  const { importDatasetFiles } = await load();
  const posts = [{post_id:"a",content:"文字",media_refs:["images/a.png","https://example.com/b.jpg"]},{post_id:"b",content:"另一条",media_refs:["a.png"]}];
  const files = [new File([JSON.stringify(posts)],"posts.json"),new File(["image"],"a.png",{type:"image/png"})];
  const calls=[];
  const imported = await importDatasetFiles(files, async f=>{calls.push(f.name); return "dataset-image:abc";});
  assert.equal(imported[0].content,"文字");
  assert.deepEqual(imported[0].media_refs,["dataset-image:abc","https://example.com/b.jpg"]);
  assert.deepEqual(imported[1].media_refs,["dataset-image:abc"]);
  assert.deepEqual(calls,["a.png"]);
});

test("JSON-only input preserves references for text-only models and remote images", async () => {
  const { importDatasetFiles } = await load();
  const posts=[{post_id:"a",content:"text",media_refs:["missing.png"]}];
  assert.deepEqual(await importDatasetFiles([new File([JSON.stringify(posts)],"posts.json")],async()=>{throw Error("unexpected upload");}),posts);
});

test("ambiguous image names and multiple JSON documents are rejected before uploading", async () => {
  const { importDatasetFiles } = await load();
  const json = new File(['[{"media_refs":["a.png"]}]'],"posts.json");
  await assert.rejects(importDatasetFiles([json,json],async()=>""));
  await assert.rejects(importDatasetFiles([json,new File(["1"],"a.png"),new File(["2"],"a.png")],async()=>""));
});
