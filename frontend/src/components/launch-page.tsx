"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowRight, BarChart3, Database, FileChartColumn, Languages } from "lucide-react";
import { useI18n } from "./language-provider";

const steps = [
  { id: "data", icon: Database, title: "数据与标注", note: "上传数据 / 关键词采集" },
  { id: "insight", icon: BarChart3, title: "复盘与预测", note: "Agent 分析 / 意见动力学" },
  { id: "report", icon: FileChartColumn, title: "模拟与报告", note: "情景比较 / 结果解读" },
];

export function LaunchPage() {
  const { t, locale, toggleLocale } = useI18n();
  return <div className="launch-page">
    <div className="launch-artwork" aria-hidden="true">
      <Image src="/images/opinion-flow-v1.png" alt="" fill sizes="100vw" preload draggable={false} />
    </div>
    <header className="launch-header">
      <Link href="/" className="brand"><span className="brand-mark"><BarChart3 size={22} /></span>Tweets2Insights</Link>
      <button className="language-switch" aria-label={t("切换显示语言")} onClick={toggleLocale}>
        <Languages size={16} /><span className={locale === "zh-CN" ? "current" : ""}>中文</span>
        <span className="language-divider">/</span><span className={locale === "en-US" ? "current" : ""}>EN</span>
      </button>
    </header>
    <main className="launch-main">
      <div className="launch-intro">
        <span className="launch-eyebrow">TWEETS2INSIGHTS</span>
        <h1>{t("智能舆情研判与情景推演平台")}</h1>
        <p>{t("融合多源社交媒体数据与多智能体协作，支持事件复盘、趋势分析、条件情景推演与可追溯研究报告。")}</p>
        <Link className="launch-cta" href="/workspace">{t("开始舆情研究")}<ArrowRight size={20} /></Link>
      </div>
      <section className="launch-workflow" aria-label={t("研究流程")}>
        <svg className="workflow-current" viewBox="0 0 1100 230" preserveAspectRatio="none" aria-hidden="true">
          <defs><linearGradient id="workflow-current-color"><stop stopColor="#71baff" stopOpacity="0"/><stop offset=".45" stopColor="#558fe8" stopOpacity=".55"/><stop offset="1" stopColor="#4ec2bf" stopOpacity="0"/></linearGradient></defs>
          <path d="M 110 154 C 290 162, 335 46, 550 62 S 830 168, 1000 138" stroke="url(#workflow-current-color)" strokeWidth="1.4" fill="none" strokeDasharray="4 9" />
        </svg>
        {steps.map(({ id, icon: Icon, title, note }) => <article className={`workflow-item workflow-item--${id}`} key={id}>
          <div className="workflow-glyph" aria-hidden="true"><span className="workflow-orbit"/><Icon size={30} strokeWidth={1.6}/><i className="workflow-signal"/></div>
          <div className="workflow-copy"><h2>{t(title)}</h2><p>{t(note)}</p></div>
        </article>)}
      </section>
    </main>
  </div>;
}
