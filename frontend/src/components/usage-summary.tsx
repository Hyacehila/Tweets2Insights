"use client";

import { summarizeUsage } from "@/lib/usage-summary";
import { artifactLabels } from "@/lib/i18n";
import { useI18n } from "./language-provider";
import { Card } from "./tremor/Card";

export function UsageSummary({ value }: { value?: Record<string, unknown> }) {
  const { t, locale } = useI18n();
  if (!value) return null;
  const summary = summarizeUsage(value);
  const format = (n: number | null) => n === null ? "—" : n.toLocaleString(locale);
  return <Card className="surface section-card">
    <div className="section-heading"><h2>{t("用量与费用")}</h2><span>{t("已记录 {count} 次调用", { count: summary.calls })}</span></div>
    <p className="muted">{summary.cost === null ? t("服务商未返回完整费用。下表显示已返回的 Token 用量，金额请查看服务商账单。") : t("服务商返回费用：{amount}", { amount: summary.cost })}</p>
    <div className="table-scroll"><table>
      <thead><tr><th>{t("阶段")}</th><th>{t("模型 / 服务")}</th><th>{t("调用次数")}</th><th>{t("输入 Token")}</th><th>{t("输出 Token")}</th><th>{t("其中缓存 Token")}</th><th>{t("未返回 Token 的调用")}</th></tr></thead>
      <tbody>{summary.groups.map(group => <tr key={`${group.stage}:${group.provider}`}>
        <td>{t(artifactLabels[group.stage] ?? group.stage)}</td><td>{group.provider}</td><td>{format(group.calls)}</td><td>{format(group.input)}</td><td>{format(group.output)}</td><td>{format(group.cached)}</td><td>{format(group.missingUsage)}</td>
      </tr>)}</tbody>
    </table></div>
    <details className="advanced-settings"><summary>{t("原始用量记录")}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
  </Card>;
}
