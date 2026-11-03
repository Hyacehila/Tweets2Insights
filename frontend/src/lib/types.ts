export type Message = { role: string; content: string };
export type Thread = { thread_id: string; event_id: string; title: string; created_at: string; messages?: Message[]; latest_execution?: { execution_id: string; status: string; error_type: string } | null };
export type Dataset = { dataset_id: string; count: number };
export type Job = { job_id: string; event_id: string; run_id: string; status: string; stage: string; error_type: string };
export type ArtifactRef = { artifact_id: string; kind: string; event_id: string; run_id: string };
export type DomainResult = { artifacts?: Record<string, ArtifactRef>; usage?: Record<string, unknown> };
export type AgentUpdate = { node?: string; status?: string; reply?: string; plan?: unknown; job?: Job; run_request?: unknown; execution_id?: string; error_type?: string };
