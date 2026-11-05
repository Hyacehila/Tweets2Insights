import assert from "node:assert/strict";
import test from "node:test";
import { createLibrary, createParser, defineComponent } from "@openuidev/lang-core";
import { reportSpecs, reportProgram } from "../src/lib/report-schema.mjs";

test("report layout compiles to actual OpenUI components with stable content references", () => {
  const library = createLibrary({ root: "ReportPage", components: Object.values(reportSpecs).map(spec => defineComponent({ ...spec, component: () => null })) });
  const parser = createParser(library.toJSONSchema(), "ReportPage");
  const code = reportProgram({ sections: [{ title: '章节 "一"', block_ids: ["b1"], chart_ids: ["sentiment"], presentation: "spotlight", chart_position: "after" }] });
  const parsed = parser.parse(code);
  assert.ok(parsed.root);
  assert.deepEqual(parsed.meta.errors, []);
  assert.match(code, /ReportBlock\("b1"\)/);
  assert.match(code, /ReportChart\("sentiment"\)/);
  assert.ok(parser.parse('root = ReportPage([HtmlView("invalid")])').meta.errors.length);
});
