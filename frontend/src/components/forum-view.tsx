"use client";
import { useI18n } from "./language-provider";
import { AnalysisChart, type ChartData } from "./analysis-chart";
type Review = {
  role: string;
  claims: { text: string; evidence_refs: string[] }[];
  gaps: string[];
};
type Round = {
  round: number;
  reviews: Review[];
  host?: {
    narrative: string;
    agreements: string[];
    conflicts: string[];
    gaps: string[];
  };
  actions?: {
    action: string;
    status: string;
    tool_id?: string;
    query?: string;
  }[];
  decision_error?: string;
};
export type ForumData = {
  termination?: string;
  roles?: string[];
  unresolved?: string[];
  rounds?: Round[];
  tool_results?: ChartData[];
};
export function ForumView({ value }: { value: ForumData }) {
  const { t } = useI18n();
  const roleName = (role: string) =>
    t(
      (
        {
          data: "数据分析",
          search: "搜索补证",
          visual: "图表解读",
          insight: "综合解释",
          methodology: "方法检查",
        } as Record<string, string>
      )[role] ?? role,
    );
  return (
    <div>
      <p>
        {t("停止原因：{reason}", {
          reason: t(
            (
              {
                evidence_sufficient: "证据充分",
                round_limit: "达到讨论轮数",
                no_new_evidence: "没有新增证据",
                invalid_host_decision: "主持决策未完成",
              } as Record<string, string>
            )[value.termination ?? ""] ??
              value.termination ??
              "—",
          ),
        })}
      </p>
      <p className="caption">
        {t("角色：{roles}", {
          roles: value.roles?.map(roleName).join(" · ") ?? "—",
        })}
      </p>
      {value.rounds?.map((r) => (
        <details key={r.round} open>
          <summary>{t("第 {round} 轮", { round: r.round })}</summary>
          {r.reviews.map((review) => (
            <article key={review.role}>
              <h3>{roleName(review.role)}</h3>
              {review.claims.map((c, i) => (
                <p key={i}>
                  {c.text}
                  <small>
                    {" "}
                    · {t("{count} 条依据", { count: c.evidence_refs.length })}
                  </small>
                </p>
              ))}
              {review.gaps?.length > 0 && (
                <p className="caption">
                  {t("待补：")}
                  {review.gaps.join("；")}
                </p>
              )}
            </article>
          ))}
          {r.host && (
            <article>
              <h3>{t("论坛主持")}</h3>
              <p>{r.host.narrative}</p>
              <p>
                {t("共识：")}
                {r.host.agreements.join("；") || t("尚未形成")}
              </p>
              <p>
                {t("分歧：")}
                {r.host.conflicts.join("；") || t("无记录")}
              </p>
            </article>
          )}
          {r.decision_error && (
            <p className="error">{t("主持决策未完成，请查看任务记录。")}</p>
          )}
          {r.actions?.map((a, i) => (
            <p className="caption" key={i}>
              {a.action} · {a.status} · {a.query ?? a.tool_id}
            </p>
          ))}
        </details>
      ))}
      {value.unresolved?.length ? (
        <p className="error">
          {t("未解决：")}
          {value.unresolved.join("；")}
        </p>
      ) : null}
      {value.tool_results?.map((result, i) => (
        <AnalysisChart
          key={i}
          name={result.description ?? t("分析")}
          value={result}
        />
      ))}
    </div>
  );
}
