import type { ChartData } from "@/components/analysis-chart";
import type { ArtifactRef } from "./types";

export type WorkspaceView = "overview" | "research" | "forecast" | "reports" | "settings";
export type CanvasPage = WorkspaceView | "progress" | "datasets";
export type DataFilters = { dataset_id?: string; start?: string; end?: string; platform?: string };
export type IntelligenceContext = {
  thread_id: string; event_id: string; title: string; total_posts: number;
  dataset: { dataset_id: string; metrics: Record<string, number>; charts: Record<string, ChartData>; top_posts: { post_id: string; content: string; published_at: string | null; score: number; source_url?: string }[] } | null;
  charts: Record<string, ChartData>;
  chart_catalog: { key: string; title: string; scope: string }[];
  platforms: string[]; run_id?: string; report?: ArtifactRef;
  model_runs: { job_id: string; run_id: string; algorithm: string }[];
};
export type UIMessage = { id: number; role: string; content: string; status: string; timestamp?: string; usage?: Record<string, number>; error?: { message: string; error_type: string } | null; filters?: DataFilters };
export type Simulation = { id?: number; timestamp?: string; source_run_id: string; charts: Record<string, ChartData>; parameters: { horizon: number; shift: number; dimension: string; assumption: string }; artifact: ArtifactRef; metrics: Record<string, number> };
