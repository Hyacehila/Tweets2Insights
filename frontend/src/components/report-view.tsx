"use client";
import { useState } from "react";
import { AnalysisChart, type ChartData } from "./analysis-chart";
type Block={block_id:string;kind:string;title:string;text:string;evidence_refs:string[]};
export type ReportData={content?:{blocks:Block[];metrics:Record<string,unknown>;evidence:{evidence_id:string;title:string;source_url?:string;excerpt:string}[]};layout?:{title:string;sections:{title:string;block_ids:string[]}[]};charts?:Record<string,ChartData>};
export function ReportView({report}:{report:ReportData}){
  const [section,setSection]=useState("all");
  if(!report.content||!report.layout)return null;
  const {content,layout}=report;
  const blocks=Object.fromEntries(content.blocks.map(b=>[b.block_id,b]));
  const text=(value:string)=>value.replace(/\{\{([^}]+)\}\}/g,(_,key)=>String(content.metrics[key]??"未提供"));
  return <div className="report-view"><h2>{layout.title}</h2><nav className="report-nav"><button onClick={()=>setSection("all")}>完整报告</button>{layout.sections.map((s,i)=><button key={i} onClick={()=>setSection(String(i))}>{s.title}</button>)}</nav>
    {layout.sections.map((s,i)=>(section==="all"||section===String(i))&&<section key={i}><h3>{s.title}</h3>{s.block_ids.map(id=>{const b=blocks[id];return b?<article key={id}><span className={`badge ${b.kind}`}>{({observed:"观测",forecast:"预测",simulated:"模拟",interpretation:"解释"} as Record<string,string>)[b.kind]??b.kind}</span><p>{text(b.text)}</p>{b.evidence_refs.length>0&&<details><summary>依据 · {b.evidence_refs.length} 条</summary>{b.evidence_refs.map(ref=>{const card=content.evidence.find(c=>c.evidence_id===ref);return <p key={ref}>{card?.title??ref}{card?.source_url&&/^https?:\/\//.test(card.source_url)&&<> · <a href={card.source_url} target="_blank" rel="noreferrer">来源</a></>}</p>;})}</details>}</article>:null;})}</section>)}
    <div className="report-charts">{Object.entries(report.charts??{}).map(([name,value])=><AnalysisChart key={name} name={name} value={value}/>)}</div>
    <p className="caption">图表来源表为分页预览。预测区间表示模型集合离散范围；科学有效性和覆盖率需另行评测。</p>
  </div>;
}
