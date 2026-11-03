"use client";
import { AnalysisChart, type ChartData } from "./analysis-chart";
type Review={role:string;claims:{text:string;evidence_refs:string[]}[];gaps:string[]};
type Round={round:number;reviews:Review[];host?:{narrative:string;agreements:string[];conflicts:string[];gaps:string[]};actions?:{action:string;status:string;tool_id?:string;query?:string}[];decision_error?:string};
export type ForumData={termination?:string;roles?:string[];unresolved?:string[];rounds?:Round[];tool_results?:ChartData[]};
export function ForumView({value}:{value:ForumData}){
  return <div><p>停止原因：{value.termination}</p><p className="caption">角色：{value.roles?.join(" · ")}</p>{value.rounds?.map(r=><details key={r.round} open><summary>第 {r.round} 轮</summary>{r.reviews.map(review=><article key={review.role}><h3>{review.role}</h3>{review.claims.map((c,i)=><p key={i}>{c.text}<small> · {c.evidence_refs.length} 条依据</small></p>)}{review.gaps?.length>0&&<p className="caption">待补：{review.gaps.join("；")}</p>}</article>)}{r.host&&<article><h3>ForumHost</h3><p>{r.host.narrative}</p><p>共识：{r.host.agreements.join("；")||"尚未形成"}</p><p>分歧：{r.host.conflicts.join("；")||"无记录"}</p></article>}{r.decision_error&&<p className="error">主持决策无效，未认定证据充分。</p>}{r.actions?.map((a,i)=><p className="caption" key={i}>{a.action} · {a.status} · {a.query??a.tool_id}</p>)}</details>)}{value.unresolved?.length? <p className="error">未解决：{value.unresolved.join("；")}</p>:null}{value.tool_results?.map((result,i)=><AnalysisChart key={i} name={result.description??"分析"} value={result}/>)}</div>;
}
