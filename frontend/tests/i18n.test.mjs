import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(
  new URL("../src/lib/i18n.ts", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
});
const { translate, normalizeLocale } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

test("switching locale translates controls while preserving research content", () => {
  assert.equal(translate("zh-CN", "研究工作台"), "研究工作台");
  assert.equal(translate("en-US", "研究工作台"), "Research workspace");
  assert.equal(translate("en-US", "阿里 Decision"), "Alibaba Decision");
  assert.equal(
    translate("en-US", "城市暴雨事件 A：用户填写的标题"),
    "城市暴雨事件 A：用户填写的标题",
  );
  assert.equal(translate("en-US", "constructor"), "constructor");
});

test("counts and dynamic values retain the correct order in each language", () => {
  assert.equal(
    translate("zh-CN", "已导入 {count} 条记录", { count: 12 }),
    "已导入 12 条记录",
  );
  assert.equal(
    translate("en-US", "已导入 {count} 条记录", { count: 12 }),
    "Imported 12 records",
  );
  assert.equal(translate("en-US", "第 {page} 页", { page: 2 }), "Page 2");
});

test("invalid or missing saved preferences fall back to Chinese", () => {
  assert.equal(normalizeLocale("en-US"), "en-US");
  assert.equal(normalizeLocale("zh-CN"), "zh-CN");
  assert.equal(normalizeLocale(null), "zh-CN");
  assert.equal(normalizeLocale("unknown"), "zh-CN");
});
