"use client";

import Link from "next/link";
import { ArrowRight, BarChart3, ChartNoAxesCombined, Database, FileChartColumn, Languages } from "lucide-react";
import { useI18n } from "./language-provider";

const steps = [
  { icon: Database, title: "数据与标注", note: "上传数据 / 关键词采集" },
  { icon: BarChart3, title: "复盘与预测", note: "Agent 分析 / 意见动力学" },
  { icon: FileChartColumn, title: "模拟与报告", note: "情景比较 / 结果解读" },
];

export function LaunchPage() {
  const { t, locale, toggleLocale } = useI18n();
  return <div className="launch-page">
    <header className="launch-header">
      <Link href="/" className="brand"><ChartNoAxesCombined size={26} />TWEETS2INSIGHTS</Link>
      <button className="language-switch" aria-label={t("切换显示语言")} onClick={toggleLocale}>
        <Languages size={16} /><span className={locale === "zh-CN" ? "current" : ""}>中文</span>
        <span className="language-divider">/</span><span className={locale === "en-US" ? "current" : ""}>EN</span>
      </button>
    </header>
    <main className="launch-main">
      <div className="launch-intro">
        <h1>{t("智能舆情研判与情景推演平台")}</h1>
        <p>{t("融合多源社交媒体数据与多智能体协作，支持事件复盘、趋势分析、条件情景推演与可追溯研究报告。")}</p>
        <Link className="launch-cta" href="/workspace">{t("开始舆情研究")}<ArrowRight size={20} /></Link>
      </div>
      <section className="launch-workflow" aria-label={t("研究流程")}>
        {steps.map(({ icon: Icon, title, note }, index) => <article key={title}>
          <div className="launch-step-top"><span className="step-icon"><Icon size={25} /></span><span className="launch-step-number">0{index + 1}</span></div>
          <h2>{t(title)}</h2><p>{t(note)}</p>
        </article>)}
      </section>
    </main>
  </div>;
}
