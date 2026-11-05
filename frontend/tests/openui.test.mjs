import assert from "node:assert/strict";
import test from "node:test";
import { createLibrary, createParser, defineComponent } from "@openuidev/lang-core";
import { componentSpecs, starterProgram } from "../src/lib/openui-schema.mjs";

const library = createLibrary({ root: "ResearchView", components: Object.values(componentSpecs).map(spec => defineComponent({ ...spec, component: () => null })) });
const parser = createParser(library.toJSONSchema(), "ResearchView");

test("both starter programs parse with the installed OpenUI runtime", () => {
  for (const locale of ["zh-CN", "en-US"]) {
    const result = parser.parse(starterProgram(locale));
    assert.ok(result.root);
    assert.deepEqual(result.meta.errors, []);
  }
});

test("generated UI only accepts registered research components", () => {
  const invalid = parser.parse('root = ResearchView([HtmlView("<script>alert(1)</script>")])');
  assert.ok(invalid.meta.errors.length);
  const valid = parser.parse('root = ResearchView([Grid([Metric("posts"), Metric("images")]), Chart("daily"), Filters(), Evidence(), Navigate("Forecast", "forecast")])');
  assert.ok(valid.root);
  assert.deepEqual(valid.meta.errors, []);
});
