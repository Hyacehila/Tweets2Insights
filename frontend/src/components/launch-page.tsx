"use client";

import Link from "next/link";
import { ArrowRight, BarChart3, Database, FileChartColumn, Languages } from "lucide-react";
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
      <Link href="/" className="brand"><span className="brand-mark"><BarChart3 size={22} /></span>Tweets2Insights</Link>
      <button className="language-switch" aria-label={t("切换显示语言")} onClick={toggleLocale}>
        <Languages size={16} /><span className={locale === "zh-CN" ? "current" : ""}>中文</span>
        <span className="language-divider">/</span><span className={locale === "en-US" ? "current" : ""}>EN</span>
      </button>
    </header>
    <main className="launch-main">
      <div className="launch-intro">
        <span className="launch-eyebrow">TWEETS2INSIGHTS</span>
        <h1>{t("多智能体舆情研究工作台")}</h1>
        <Link className="launch-cta" href="/workspace">{t("开始研究")}<ArrowRight size={20} /></Link>
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
