"use client";
import { Component, createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { createLibrary, defineComponent, Renderer } from "@openuidev/react-lang";
import { reportSpecs, reportProgram } from "@/lib/report-schema.mjs";
import { useI18n } from "./language-provider";
import { AnalysisChart, type ChartData } from "./analysis-chart";

type Block = { block_id: string; kind: string; title: string; text: string; evidence_refs: string[] };
type Section = { title: string; block_ids: string[]; chart_ids?: string[]; presentation?: string; chart_position?: string };
export type ReportData = {
  content?: { blocks: Block[]; metrics: Record<string, unknown>; evidence: { evidence_id: string; title: string; source_url?: string; excerpt: string }[] };
  layout?: { title: string; sections: Section[] };
  charts?: Record<string, ChartData>; openui?: string; pdf_pages?: number;
};
type Context = { report: ReportData; selected: string; labels: Record<string, string> };
const ReportContext = createContext<Context | null>(null);
function useReport() { const value = useContext(ReportContext); if (!value) throw new Error("Report context missing"); return value; }

function ParagraphBlock({ id }: { id: string }) {
  const { report, labels } = useReport(); const { t } = useI18n();
  const block = report.content?.blocks.find(b => b.block_id === id);
  if (!block) return null;
  const text = block.text.replace(/\{\{([^}]+)\}\}/g, (_, key) => {
    const value = report.content?.metrics[key];
    return typeof value === "number" && !Number.isInteger(value) ? Number(value.toPrecision(6)).toString() : String(value ?? "—");
  });
  return <article className="report-paragraph">
    <h4>{block.title}</h4><p>{text}</p>
    {block.evidence_refs.length > 0 && <details className="report-citations"><summary>{block.evidence_refs.map(ref => `[${labels[ref]}]`).join(" ")} · {t("查看依据")}</summary>{block.evidence_refs.map(ref => {
      const card = report.content?.evidence.find(c => c.evidence_id === ref);
      return <div key={ref}><strong>[{labels[ref]}] {card?.title || ref}</strong><p>{card?.excerpt}</p>{card?.source_url && /^https?:\/\//i.test(card.source_url) && <a href={card.source_url} target="_blank" rel="noopener noreferrer">{t("查看来源")} ↗</a>}</div>;
    })}</details>}
  </article>;
}

const library = createLibrary({ root: "ReportPage", components: [
  defineComponent({ ...reportSpecs.ReportPage, component: ({ props, renderNode }) => <div className="report-document">{renderNode(props.children)}</div> }),
  defineComponent({ ...reportSpecs.ReportSection, component: function Section({ props, renderNode }) {
    const { report, selected } = useReport();
    const section = report.layout?.sections[Number(props.section)];
    if (!section || selected !== "all" && selected !== props.section) return null;
    return <section id={`report-section-${props.section}`} className={`report-chapter ${props.presentation}`}><header><span>{String(Number(props.section) + 1).padStart(2, "0")}</span><h3>{section.title}</h3></header><div className="report-chapter-content">{renderNode(props.children)}</div></section>;
  } }),
  defineComponent({ ...reportSpecs.ReportBlock, component: ({ props }) => <ParagraphBlock id={props.block}/> }),
  defineComponent({ ...reportSpecs.ReportChart, component: function Chart({ props }) {
    const { report } = useReport(); const chart = report.charts?.[props.chart];
    return chart ? <div className="report-figure"><AnalysisChart name={props.chart} value={chart}/></div> : null;
  } }),
] });

class ReportBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export function ReportView({ report }: { report: ReportData }) {
  const { t } = useI18n(); const [selected, setSelected] = useState("all");
  const [search, setSearch] = useState("");
  const normalized = useMemo(() => {
    if (!report.layout) return report;
    const sections = report.layout.sections.map(s => ({ ...s, chart_ids: [...(s.chart_ids || [])] }));
    const placed = new Set(sections.flatMap(s => s.chart_ids));
    if (sections.length) sections[sections.length - 1].chart_ids.push(...Object.keys(report.charts || {}).filter(key => !placed.has(key)));
    return { ...report, layout: { ...report.layout, sections } };
  }, [report]);
  if (!normalized.content || !normalized.layout) return null;
  const used = new Set(normalized.content.blocks.flatMap(b => b.evidence_refs));
  const labels = Object.fromEntries(normalized.content.evidence.filter(e => used.has(e.evidence_id)).map((e, i) => [e.evidence_id, `E${i+1}`]));
  const filtered = normalized.layout.sections.map((s, i) => ({ ...s, i })).filter(s => !search || (s.title + s.block_ids.map(id => normalized.content!.blocks.find(b => b.block_id === id)?.text || "").join(" ")).toLowerCase().includes(search.toLowerCase()));
  // Compile the validated layout to the SDK grammar; content and data remain frozen by ID.
  const program = reportProgram(normalized.layout);
  return <ReportContext.Provider value={{ report: normalized, selected, labels }}><div className="report-view intelligent-report">
    <header className="report-hero"><span>TWEETS2INSIGHTS · {t("研究报告")}</span><h2>{normalized.layout.title}</h2><div className="report-facts"><span>{t("{count} 个章节", { count: normalized.layout.sections.length })}</span><span>{t("{count} 张图表", { count: Object.keys(report.charts || {}).length })}</span>{report.pdf_pages && <span>PDF · {report.pdf_pages} {t("页")}</span>}</div></header>
    <div className="report-reading-layout"><aside className="report-contents"><label>{t("搜索报告")}<input value={search} onChange={e => setSearch(e.target.value)} placeholder={t("章节或关键词")}/></label><button className={selected === "all" ? "selected" : ""} onClick={() => setSelected("all")}>{t("完整报告")}</button>{filtered.map(s => <button key={s.i} className={selected === String(s.i) ? "selected" : ""} onClick={() => setSelected(String(s.i))}><span>{String(s.i+1).padStart(2, "0")}</span>{s.title}</button>)}</aside>
      <ReportBoundary fallback={<p role="alert" className="error">{t("报告页面未能加载，请下载 PDF 阅读")}</p>}><Renderer response={program} library={library} publishObservability={false}/></ReportBoundary>
    </div>
  </div></ReportContext.Provider>;
}
