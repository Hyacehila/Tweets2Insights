type Group = { stage: string; provider: string; calls: number; input: number | null; output: number | null; cached: number | null; missingUsage: number };

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function summarizeUsage(summary: Record<string, unknown>) {
  const groups = new Map<string, Group>();
  const records = Array.isArray(summary.records) ? summary.records : [];
  for (const value of records) {
    const record = object(value), usage = object(record.usage);
    const stage = String(record.stage ?? "unknown"), provider = String(record.provider ?? "unknown");
    const key = JSON.stringify([stage, provider]);
    const group = groups.get(key) ?? { stage, provider, calls: 0, input: null, output: null, cached: null, missingUsage: 0 };
    const input = number(usage.input_tokens) ?? number(usage.prompt_tokens);
    const output = number(usage.output_tokens) ?? number(usage.completion_tokens);
    const details = object(usage.input_tokens_details ?? usage.prompt_tokens_details);
    const cached = number(details.cached_tokens) ?? number(usage.prompt_cache_hit_tokens);
    group.calls += 1;
    if (input !== null) group.input = (group.input ?? 0) + input;
    if (output !== null) group.output = (group.output ?? 0) + output;
    if (cached !== null) group.cached = (group.cached ?? 0) + cached;
    if (input === null && output === null) group.missingUsage += 1;
    groups.set(key, group);
  }
  return { calls: number(summary.calls) ?? records.length, cost: summary.cost_complete === true ? number(summary.known_cost) : null, groups: [...groups.values()] };
}
