import { z } from "zod/v4";

export const reportSpecs = {
  ReportPage: { name: "ReportPage", props: z.object({ children: z.array(z.any()) }), description: "Complete report from an immutable analysis run." },
  ReportSection: { name: "ReportSection", props: z.object({ section: z.string(), presentation: z.enum(["narrative", "spotlight", "columns"]), children: z.array(z.any()) }), description: "Agent-arranged report chapter." },
  ReportBlock: { name: "ReportBlock", props: z.object({ block: z.string() }), description: "Agent-authored paragraph resolved by ID, with measured values and citations." },
  ReportChart: { name: "ReportChart", props: z.object({ chart: z.string() }), description: "Interactive chart from this report's frozen source data." },
};

export function reportProgram(layout) {
  return "root = ReportPage([" + layout.sections.map((section, index) => {
    const blocks = section.block_ids.map(key => `ReportBlock(${JSON.stringify(key)})`);
    const charts = (section.chart_ids || []).map(key => `ReportChart(${JSON.stringify(key)})`);
    const children = section.chart_position === "before" ? [...charts, ...blocks] : [...blocks, ...charts];
    return `ReportSection(${JSON.stringify(String(index))}, ${JSON.stringify(section.presentation || "narrative")}, [${children.join(", ")}])`;
  }).join(", ") + "])";
}
