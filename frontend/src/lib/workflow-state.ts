function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function strings(value: unknown): string[] | undefined {
  return Array.isArray(value) && value.every(item => typeof item === "string") ? value : undefined;
}
function text(value: unknown): string | undefined { return typeof value === "string" ? value : undefined; }
function number(value: unknown): number | undefined { return typeof value === "number" && Number.isFinite(value) ? value : undefined; }
function date(value: unknown): string | undefined {
  const raw = text(value);
  return raw && Number.isFinite(Date.parse(raw)) ? new Date(raw).toISOString().slice(0, 16) : undefined;
}

export function workflowState(request: unknown) {
  if (!request || typeof request !== "object" || Array.isArray(request)) return null;
  const r = object(request), event = object(r.event), labels = object(r.labels), observations = object(r.observations);
  const analysis = object(r.analysis), model = object(r.model), crawl = object(r.crawl);
  const scenario = object(Array.isArray(r.scenarios) ? r.scenarios[0] : null);
  return {
    dataset: text(event.dataset_ref), keywords: strings(event.keywords)?.join("，"), searchProvider: text(event.search_provider),
    input: text(event.input_mode), phases: strings(event.objectives), roles: strings(analysis.forum_roles),
    start: date(observations.start), end: date(observations.end), labelProvider: text(labels.provider), model: text(labels.model),
    mediaMode: text(r.media_mode), maxImages: number(labels.max_images_per_post), maxCalls: number(labels.max_calls),
    rounds: number(r.forum_rounds), horizon: number(model.horizon), maxPosts: number(crawl.max_posts), platforms: strings(crawl.platforms)?.join(","),
    instruction: text(analysis.instruction), mechanism: text(scenario.mechanism), measure: text(scenario.measure),
    magnitude: number(scenario.parameter_value) ?? number(scenario.shift), cost: number(scenario.resource_cost),
    assumption: strings(scenario.assumptions)?.join("；"),
  };
}
