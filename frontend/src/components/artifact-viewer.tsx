"use client";
import { useI18n } from "./language-provider";
import { useEffect, useState } from "react";
import { artifactLabels } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { ArtifactRef } from "@/lib/types";
import { ReportView, type ReportData } from "./report-view";
import { AnalysisChart, type ChartData } from "./analysis-chart";
import { ForumView, type ForumData } from "./forum-view";

export function ArtifactViewer({
  threadId,
  reference,
}: {
  threadId: string;
  reference: ArtifactRef;
}) {
  const { t } = useI18n();
  const [data, setData] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData({});
    setError("");
    api<Record<string, unknown>>(
      `/threads/${threadId}/artifacts/${reference.run_id}/${reference.artifact_id}`,
    )
      .then((value) => {
        if (live) setData(value);
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [threadId, reference]);
  return (
    <section className="artifact">
      <div className="section-heading">
        <h3>{t(artifactLabels[reference.kind] ?? reference.kind)}</h3>
      </div>
      {error && <p className="error">{t(error)}</p>}
      <div className="export-links">
        <a
          href={`/api/threads/${threadId}/exports/${reference.run_id}/${reference.artifact_id}?format=json`}
        >
          {t("下载完整 JSON")}
        </a>
      </div>
      {typeof data.markdown_excerpt === "string" ? (
        <>
          <div className="export-links">
            {["markdown", "html", "json", "zip"].map((format) => (
              <a
                key={format}
                href={`/api/threads/${threadId}/exports/${reference.run_id}/${reference.artifact_id}?format=${format}`}
              >
                {t("下载 {format}", { format: format.toUpperCase() })}
              </a>
            ))}
          </div>
          <ReportView report={data as ReportData} />
          <details>
            <summary>{t("Markdown 预览")}</summary>
            <pre className="report-text">{data.markdown_excerpt}</pre>
          </details>
        </>
      ) : reference.kind === "forum" ? (
        <ForumView value={data as ForumData} />
      ) : reference.kind === "charts" ? (
        Object.entries(data).map(([name, value]) => (
          <AnalysisChart key={name} name={name} value={value as ChartData} />
        ))
      ) : reference.kind === "analysis-tool" ? (
        <AnalysisChart name={String(data.name)} value={data as ChartData} />
      ) : (
        <pre>{JSON.stringify(data, null, 2)}</pre>
      )}
    </section>
  );
}
