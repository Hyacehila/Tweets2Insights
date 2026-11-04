export type Message = { role: string; content: string };
export type Thread = { thread_id: string; event_id: string; title: string; created_at: string; messages?: Message[]; latest_execution?: { execution_id: string; status: string; error_type: string } | null };
export type Dataset = { dataset_id: string; count: number };
export type Job = { job_id: string; event_id: string; run_id: string; status: string; stage: string; error_type: string };
export type ArtifactRef = { artifact_id: string; kind: string; event_id: string; run_id: string };
export type MediaInput = { supports_images: boolean; requested_mode: string; effective_mode: string; max_images_per_post: number; available_images: number; selected_images: number; ignored_images: number; notices: string[] };
export type DomainResult = { artifacts?: Record<string, ArtifactRef>; usage?: Record<string, unknown>; media_input?: MediaInput | null };
export type AgentUpdate = { node?: string; status?: string; reply?: string; plan?: unknown; job?: Job; run_request?: unknown; execution_id?: string; error_type?: string; message?: string; traceback?: string; timestamp?: string };
