import { z } from "zod/v4";

// Shared by the React library and the server prompt generator; argument order is part of OpenUI Lang.
export const componentSpecs = {
  ResearchView: { name: "ResearchView", props: z.object({ children: z.array(z.any()) }), description: "Root vertical research canvas. Arrange a concise answer using the registered components." },
  Grid: { name: "Grid", props: z.object({ children: z.array(z.any()) }), description: "Responsive two-column layout for related metrics or charts." },
  Summary: { name: "Summary", props: z.object({ text: z.string() }), description: "Plain text interpretation grounded in the supplied event context. Never invent numerical findings." },
  Heading: { name: "Heading", props: z.object({ text: z.string() }), description: "Short section heading." },
  Metric: { name: "Metric", props: z.object({ metric: z.enum(["posts", "images", "image_posts", "interactions", "authors", "days"]) }), description: "Live metric from the selected dataset and filters. Values are resolved by the application, never supplied by the model." },
  Chart: { name: "Chart", props: z.object({ source: z.string() }), description: "Interactive chart resolved from context.chart_catalog. Use exactly an available key, such as daily or engagement; never supply fabricated chart data." },
  Filters: { name: "Filters", props: z.object({}), description: "Working date and platform controls that refetch real dataset statistics and evidence. Analysis artifact charts retain their own source scope." },
  Evidence: { name: "Evidence", props: z.object({}), description: "Top posts from the selected dataset with content, timestamps and interaction counts, respecting the current filters." },
  Scenario: { name: "Scenario", props: z.object({}), description: "Real scenario controls: choose a fitted model run, horizon, dimension and conditional shift; recompute paired HK trajectories on the server after the user clicks Run." },
  Navigate: { name: "Navigate", props: z.object({ label: z.string(), page: z.enum(["overview", "research", "forecast", "reports", "progress", "datasets", "settings"]) }), description: "Button to open an event page without changing the selected event." },
};

export function starterProgram(locale = "zh-CN") {
  const title = locale === "en-US" ? "Explore this event" : "探索当前事件";
  return `root = ResearchView([Heading(${JSON.stringify(title)}), Filters(), Grid([Metric("posts"), Metric("interactions")]), Chart("daily"), Evidence()])`;
}
