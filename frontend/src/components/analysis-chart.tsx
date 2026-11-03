"use client";
import { useState } from "react";
export type ChartRow=Record<string,unknown>;
export type ChartData={title?:string;description?:string;data?:ChartRow[];table?:ChartRow[];data_total?:number;table_total?:number;bins?:number[];chart?:{kind?:string}|null;coverage?:unknown;notes?:string[]};
const colors=["#277f84","#b46a46","#7078ad","#76913c","#ba688b","#a29344"];

export function AnalysisChart({name,value}:{name:string;value:ChartData}){
  const [chosen,setChosen]=useState("all"),[page,setPage]=useState(0),[hover,setHover]=useState("");
  const source=value.data??value.table??[];
  const distribution=source.some(r=>"mass" in r);
  const rows:ChartRow[]=distribution?source.flatMap(r=>Array.isArray(r.mass)?r.mass.map((v,i)=>({label:String(r.start),series:`${value.bins?.[i]?.toFixed(1)??i}…${value.bins?.[i+1]?.toFixed(1)??i+1}`,value:v})):[]):source;
  const allSeries=Array.from(new Set(rows.map(r=>String(r.series??"value"))));
  const filtered=rows.filter(r=>chosen==="all"||String(r.series??"value")===chosen);
  const plotted=filtered.filter(r=>typeof r.value==="number"&&Number.isFinite(r.value)).slice(0,200);
  const labels=Array.from(new Set(filtered.map(r=>String(r.label))));
  const groups=allSeries.filter(g=>chosen==="all"||g===chosen);
  const extent=plotted.flatMap(r=>[r.value,r.lower,r.upper].filter((v):v is number=>typeof v==="number"&&Number.isFinite(v)));
  const minimum=Math.min(0,...extent),maximum=Math.max(0.01,...extent);
  const x=(label:unknown)=>60+labels.indexOf(String(label))*650/Math.max(1,labels.length-1);
  const y=(v:unknown)=>240-(Number(v)-minimum)/(maximum-minimum)*200;
  const kind=distribution?"heatmap":value.chart?.kind??"bar";
  const total=plotted.reduce((sum,r)=>sum+Math.max(0,Number(r.value)),0)||1;
  const nodes=Array.from(new Set(plotted.flatMap(r=>[String(r.label),String(r.series)])));
  const position=(node:string)=>{const i=nodes.indexOf(node),a=i/Math.max(nodes.length,1)*Math.PI*2;return [385+175*Math.cos(a),145+110*Math.sin(a)];};
  const tip=(row:ChartRow)=>`${row.label}${row.series?" / "+row.series:""}: ${Number(row.value).toPrecision(4)}${row.n!==undefined?" · n="+row.n:""}`;
  const columns=Array.from(new Set(source.slice(0,60).flatMap(r=>Object.keys(r).filter(k=>k!=="post_ids"))));
  return <article className="analysis-chart"><div className="section-heading"><h3>{value.title??value.description??name}</h3>{groups.length>1||chosen!=="all"?<select aria-label="选择图表序列" value={chosen} onChange={e=>setChosen(e.target.value)}><option value="all">所有序列</option>{allSeries.map(s=><option key={s}>{s}</option>)}</select>:null}</div>
    {!plotted.length?<p className="caption">当前范围没有可绘制的有效数值。请检查字段覆盖与来源表。</p>:<svg viewBox="0 0 780 290" role="img" aria-label={value.title??value.description??name}>
      {kind==="heatmap"?plotted.map((r,i)=>{const col=labels.indexOf(String(r.label)),row=groups.indexOf(String(r.series??"value"));const width=650/Math.max(labels.length,1),height=210/Math.max(groups.length,1);return <rect key={i} x={70+col*width} y={25+row*height} width={Math.max(1,width-1)} height={Math.max(1,height-1)} fill={`rgba(39,127,132,${0.1+0.9*(Number(r.value)-minimum)/(maximum-minimum)})`} onMouseEnter={()=>setHover(tip(r))}><title>{tip(r)}</title></rect>;}):kind==="network"?<>{plotted.map((r,i)=>{const a=position(String(r.label)),b=position(String(r.series));return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#91b6b1" strokeWidth={1+Math.log1p(Number(r.value))} onMouseEnter={()=>setHover(tip(r))}><title>{tip(r)}</title></line>;})}{nodes.map((n,i)=>{const p=position(n);return <g key={n}><circle cx={p[0]} cy={p[1]} r={6} fill={colors[i%colors.length]}/><text x={p[0]+8} y={p[1]+4} fontSize="10">{n.slice(0,18)}</text></g>;})}</>:kind==="wordcloud"?plotted.map((r,i)=><text key={i} x={30+(i%5)*145} y={35+Math.floor(i/5)*45} fontSize={12+20*Number(r.value)/maximum} fill={colors[i%colors.length]} onMouseEnter={()=>setHover(tip(r))}>{String(r.label).slice(0,12)}<title>{tip(r)}</title></text>):kind==="pie"?(()=>{let angle=0;return plotted.map((r,i)=>{const next=angle+Number(r.value)/total*Math.PI*2,a=[250+95*Math.cos(angle),140+95*Math.sin(angle)],b=[250+95*Math.cos(next),140+95*Math.sin(next)];const path=`M250 140 L${a[0]} ${a[1]} A95 95 0 ${next-angle>Math.PI?1:0} 1 ${b[0]} ${b[1]} Z`;angle=next;return <g key={i}>{Number(r.value)/total>.999?<circle cx={250} cy={140} r={95} fill={colors[i%colors.length]}/>:<path d={path} fill={colors[i%colors.length]} onMouseEnter={()=>setHover(tip(r))}><title>{tip(r)}</title></path>}<text x={400} y={45+i*20} fontSize={12} fill={colors[i%colors.length]}>{String(r.label)} · {(100*Number(r.value)/total).toFixed(1)}%</text></g>;});})():<>
      <line x1={55} y1={y(0)} x2={735} y2={y(0)} stroke="#aab5af"/>{[minimum,(minimum+maximum)/2,maximum].map((v,i)=><text key={i} x={5} y={y(v)+4} fontSize={10}>{v.toPrecision(3)}</text>)}
      {kind==="line"?groups.map((g,gi)=>{const points=filtered.filter(r=>String(r.series??"value")===g);let drawing=false;const path=points.map(r=>{if(typeof r.value!=="number"){drawing=false;return "";}const part=`${drawing?"L":"M"}${x(r.label)} ${y(r.value)}`;drawing=true;return part;}).join(" ");return <g key={g}><path d={path} fill="none" stroke={colors[gi%colors.length]} strokeWidth={2}/>{points.filter(r=>typeof r.value==="number").map((r,i)=><g key={i}>{typeof r.lower==="number"&&typeof r.upper==="number"&&<line x1={x(r.label)} x2={x(r.label)} y1={y(r.lower)} y2={y(r.upper)} stroke={colors[gi%colors.length]} strokeOpacity={0.4} strokeWidth={7}/>}<circle cx={x(r.label)} cy={y(r.value)} r={3.5} fill={colors[gi%colors.length]} onMouseEnter={()=>setHover(tip(r))}><title>{tip(r)}</title></circle></g>)}</g>;}):plotted.map((r,i)=>{const w=650/plotted.length;return <rect key={i} x={65+i*w} y={Math.min(y(0),y(r.value))} width={Math.max(1,w-2)} height={Math.abs(y(r.value)-y(0))} fill={colors[i%colors.length]} onMouseEnter={()=>setHover(tip(r))}><title>{tip(r)}</title></rect>;})}</>}
      {kind!=="network"&&kind!=="wordcloud"&&kind!=="pie"&&<><text x={60} y={270} fontSize={10}>{labels[0]?.slice(0,26)}</text><text x={710} y={270} textAnchor="end" fontSize={10}>{labels.at(-1)?.slice(0,26)}</text></>}
    </svg>}
    <p className="chart-hover" aria-live="polite">{hover||"悬停查看数值；图表最多显示二百项，完整数据可下载。"}</p>
    {value.notes?.map((n,i)=><p className="caption" key={i}>{n}</p>)}
    <details><summary>数据与覆盖 · {value.data_total??value.table_total??source.length} 行</summary>{value.coverage!==undefined&&<pre>{JSON.stringify(value.coverage,null,2)}</pre>}<div className="table-scroll"><table><thead><tr>{columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{source.slice(page*10,(page+1)*10).map((r,i)=><tr key={i}>{columns.map(c=><td key={c}>{typeof r[c]==="object"?JSON.stringify(r[c]):String(r[c]??"缺失")}</td>)}</tr>)}</tbody></table></div><div className="actions"><button disabled={page===0} onClick={()=>setPage(page-1)}>上一页</button><button disabled={(page+1)*10>=source.length} onClick={()=>setPage(page+1)}>下一页</button></div></details>
  </article>;
}
