"use client";
import { useState } from "react";
import { api, post } from "@/lib/api";

const phaseLabels: Record<string,string> = {retrospective:"事件复盘",forecast:"训练与预测",scenario:"调控模拟与建议",backtest:"滚动诊断"};
const roleLabels: Record<string,string> = {data:"数据分析",search:"搜索补证",visual:"图表解读",insight:"综合解释",methodology:"方法检查"};

export function WorkflowBuilder({eventId,dataset,keywords,searchProvider,onBuild,onDirty}: {
  eventId:string;dataset:string;keywords:string;searchProvider:string;onBuild:(text:string)=>void;onDirty:()=>void;
}) {
  const [input,setInput]=useState("existing");
  const [phases,setPhases]=useState(["retrospective"]);
  const [roles,setRoles]=useState(Object.keys(roleLabels));
  const [start,setStart]=useState(new Date(Date.now()-14*86400000).toISOString().slice(0,16));
  const [end,setEnd]=useState(new Date().toISOString().slice(0,16));
  const [labelProvider,setLabelProvider]=useState("jev");
  const [model,setModel]=useState("jev-latest");
  const [platforms,setPlatforms]=useState("x");
  const [rounds,setRounds]=useState(3);
  const [horizon,setHorizon]=useState(7);
  const [maxPosts,setMaxPosts]=useState(500);
  const [maxCalls,setMaxCalls]=useState(600);
  const [instruction,setInstruction]=useState("");
  const [mechanism,setMechanism]=useState("state_shift");
  const [measure,setMeasure]=useState("信息澄清情景");
  const [magnitude,setMagnitude]=useState(0.1);
  const [cost,setCost]=useState(0);
  const [assumption,setAssumption]=useState("假设该措施通过所选模型机制起作用，强度仅作敏感性分析。");
  const [error,setError]=useState("");
  function build(){
    try {
      if(!phases.length || !keywords.trim() || (input==="existing" && !dataset)) throw new Error("请选择阶段，并填写关键词及输入数据。");
      const begin=new Date(start+"Z"), finish=new Date(end+"Z");
      if(!(begin<finish) || finish>new Date()) throw new Error("时间范围须有效，结束时间不得晚于当前时间。");
      const numeric=phases.some(p=>p!=="retrospective");
      const request={event:{event_id:eventId,input_mode:input,dataset_ref:input==="existing"?dataset:null,
        keywords:keywords.split(/[,，]/).map(s=>s.trim()).filter(Boolean),start:begin.toISOString(),end:finish.toISOString(),
        as_of:finish.toISOString(),search_provider:searchProvider,objectives:phases},run_id:`run-${Date.now()}`,
        crawl:input==="keywords"?{platforms:platforms.split(/[,，]/).map(s=>s.trim()).filter(Boolean),max_posts:maxPosts,max_comments:0}:null,
        labels:{provider:labelProvider,model,batch_size:labelProvider==="glm"?10:1,max_calls:maxCalls,confidence_threshold:0.7,probability_margin:0.1},
        agent_model:"glm-4.5-air",observations:{start:begin.toISOString(),end:finish.toISOString(),window_seconds:86400},
        sampling:{sample_size:30,high_read_quantile:0.75,seed:42,missing_reads:"uniform"},
        analysis:{forum_roles:roles,instruction,max_tool_calls:24},forum_rounds:rounds,
        model:numeric?{algorithm:"latent_hk_enkf",latent_dimensions:6,calibrate:true,training_cutoff:finish.toISOString(),horizon}:null,
        scenarios:phases.includes("scenario")?[{scenario_id:"measure-1",measure,mechanism,dimension:"stance",start_step:1,duration:Math.min(3,horizon),
          shift:mechanism==="state_shift"?magnitude:0,parameter_value:mechanism==="state_shift"?null:magnitude,resource_cost:cost,assumptions:[assumption]}]:[],
        max_total_calls:maxCalls+60};
      onBuild(JSON.stringify(request,null,2));setError("");
    } catch(e){setError((e as Error).message);}
  }
  const toggle=(items:string[],key:string)=>items.includes(key)?items.filter(v=>v!==key):[...items,key];
  return <div className="workflow-builder" onChangeCapture={onDirty}>
    <label>输入方式<select value={input} onChange={e=>setInput(e.target.value)}><option value="existing">上传 / 已有数据</option><option value="keywords">关键词与时间范围采集</option></select></label>
    {input==="keywords"&&<><label>平台 ID<input value={platforms} onChange={e=>setPlatforms(e.target.value)}/></label><p className="caption">内置 X 官方归档搜索；其他平台使用本机安装的采集连接器。</p><label>采集上限<input type="number" min={1} max={100000} value={maxPosts} onChange={e=>setMaxPosts(+e.target.value)}/></label></>}
    <fieldset><legend>执行阶段</legend>{Object.entries(phaseLabels).map(([key,label])=><label className="check-label" key={key}><input type="checkbox" checked={phases.includes(key)} onChange={()=>setPhases(toggle(phases,key))}/>{label}</label>)}</fieldset>
    <label>起始时间（UTC）<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>截止时间（UTC）<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label>
    <label>弱标注模型<select value={labelProvider} onChange={e=>{setLabelProvider(e.target.value);setModel({jev:"jev-latest",aliyun_decision:"decision-model-preview",glm:"glm-4.5-air"}[e.target.value]??"");}}><option value="jev">TypeSafe Jev</option><option value="aliyun_decision">阿里 decision</option><option value="glm">GLM JSON</option></select></label>
    <label>模型 ID<input value={model} onChange={e=>setModel(e.target.value)}/></label><label>标注调用上限<input type="number" min={1} max={9940} value={maxCalls} onChange={e=>setMaxCalls(+e.target.value)}/></label>
    {phases.includes("retrospective")&&<details><summary>论坛角色与研究要求</summary>{Object.entries(roleLabels).map(([key,label])=><label className="check-label" key={key}><input type="checkbox" checked={roles.includes(key)} onChange={()=>setRoles(toggle(roles,key))}/>{label}</label>)}<label>最多讨论轮数<input type="number" min={0} max={8} value={rounds} onChange={e=>setRounds(+e.target.value)}/></label><label>分析关注点<textarea value={instruction} onChange={e=>setInstruction(e.target.value)} placeholder="希望比较的群体、阶段、话题或问题"/></label></details>}
    {phases.some(p=>p!=="retrospective")&&<label>预测窗口数<input type="number" min={1} max={100} value={horizon} onChange={e=>setHorizon(+e.target.value)}/></label>}
    {phases.includes("scenario")&&<details open><summary>首个调控情景</summary><label>措施描述<input value={measure} onChange={e=>setMeasure(e.target.value)}/></label><label>模型作用机制<select value={mechanism} onChange={e=>setMechanism(e.target.value)}><option value="state_shift">立场状态偏移</option><option value="confidence_change">改变置信邻域</option><option value="relaxation_change">改变互动松弛率</option></select></label><label>偏移 / 参数值<input type="number" step={0.05} value={magnitude} onChange={e=>setMagnitude(+e.target.value)}/></label><label>资源成本（自行定义单位）<input type="number" min={0} value={cost} onChange={e=>setCost(+e.target.value)}/></label><label>机制假设<textarea value={assumption} onChange={e=>setAssumption(e.target.value)}/></label><p className="caption">可在下方 JSON 中添加多个情景。比较目标为降低立场方差和资源成本，不解释为已证实的现实效果。</p></details>}
    <button className="primary" onClick={build}>将阶段与参数写入运行配置</button>{error&&<p className="error">{error}</p>}
  </div>;
}

export function ProviderSettings(){
  const [provider,setProvider]=useState("jev"),[key,setKey]=useState(""),[endpoint,setEndpoint]=useState(""),[message,setMessage]=useState("");
  const [states,setStates]=useState<{provider:string;configured:boolean}[]>([]);
  async function refresh(){try{setStates(await api("/providers"));}catch(e){setMessage((e as Error).message);}}
  async function save(){try{await post("/providers",{provider,api_key:key,endpoint:provider==="aliyun_decision"?endpoint:null});setKey("");setMessage("凭据已保存到本机，后续运行可用。");await refresh();}catch(e){setMessage((e as Error).message);}}
  return <details onToggle={e=>{if(e.currentTarget.open)void refresh();}}><summary>模型与数据 API 配置</summary><p className="caption">凭据仅保存在本机，不写入运行参数和报告。Agent 推理使用 GLM；弱标注可独立选择决策模型。</p>{states.map(s=><small key={s.provider}>{s.provider}: {s.configured?"已配置":"未配置"} · </small>)}<label>服务<select value={provider} onChange={e=>{setProvider(e.target.value);setKey("");setMessage("");}}>{["jev","aliyun_decision","glm","tavily","deepseek","x"].map(s=><option key={s}>{s}</option>)}</select></label><label>API Key<input type="password" autoComplete="new-password" value={key} onChange={e=>setKey(e.target.value)}/></label>{provider==="aliyun_decision"&&<label>业务空间 System One 地址<input value={endpoint} onChange={e=>setEndpoint(e.target.value)} placeholder="https://空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone"/></label>}<button disabled={!key} onClick={save}>保存本机配置</button><p className="caption">{message}</p></details>;
}
