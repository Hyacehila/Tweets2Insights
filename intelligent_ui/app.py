from datetime import datetime,time,timedelta,timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from opinion_gateway.application import ApplicationService


def read_result(service,event,job):
    result=service.read_job_artifact(event,job['job_id'])
    artifacts={key:service.assets.read(event,job['run_id'],ref['artifact_id'])
               for key,ref in result.get('artifacts',{}).items()}
    return result,artifacts


def entry(service,event):
    mode=st.selectbox('数据入口',['upload','existing','keywords'],format_func=lambda x:{'upload':'上传标准数据','existing':'使用已有数据','keywords':'按关键词采集'}[x])
    with st.form('new_event_run'):
        run=st.text_input('运行 ID',value='run-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        upload=st.file_uploader('标准 PostRecord JSON',type=['json']) if mode=='upload' else None
        existing=service.list_datasets(event) if event else []
        dataset=st.selectbox('已有数据版本',[x['dataset_id'] for x in existing],index=None) if mode=='existing' else None
        keywords=st.text_input('事件关键词（逗号分隔）')
        provider=st.selectbox('本次唯一搜索引擎',['tavily','deepseek'])
        dates=st.date_input('分析时间范围',value=(datetime.now().date()-timedelta(days=7),datetime.now().date()))
        window=st.number_input('窗口小时数',min_value=1,max_value=720,value=24)
        label_provider=st.selectbox('标注适配器',['glm','connector'])
        connector=st.text_input('决策模型连接器 ID（使用 connector 时填写）')
        model=st.text_input('通用模型名称',value='glm-4.5-air')
        threshold=st.slider('字段置信度阈值（未经校准的初始值）',0.,1.,.7)
        media=st.selectbox('模态输入',['text_only','image_only','text_image'])
        platforms,session,max_posts='',None,500
        if mode=='keywords':
            platforms=st.text_input('采集平台 ID（逗号分隔）')
            session=st.text_input('本机会话引用（可选，不填写密钥或 Cookie）')
            max_posts=st.number_input('采集帖子上限',1,100000,500)
        calls=st.number_input('全流程外部调用上限',1,10000,120)
        forecast_enabled=st.checkbox('生成实验性预测')
        backtest=st.checkbox('计算滚动回测诊断')
        horizon=st.number_input('预测窗口数',1,100,7)
        shift=st.slider('条件情景：立场偏移（零为不添加分支）',-1.,1.,0.)
        assumptions=st.text_input('情景假设',value='其他模型参数固定，仅在首个预测窗口施加统一立场偏移')
        preview=st.form_submit_button('查看任务计划')
        submit=st.form_submit_button('提交任务',type='primary')
    if not (preview or submit):
        return
    try:
        if not event or len(dates)!=2:
            raise ValueError('填写事件 ID 和完整时间范围')
        zone=ZoneInfo('Asia/Shanghai')
        start=datetime.combine(dates[0],time(),zone).astimezone(timezone.utc)
        end=datetime.combine(dates[1]+timedelta(days=1),time(),zone).astimezone(timezone.utc)
        as_of=datetime.now(timezone.utc)
        end=min(end,as_of)
        if mode=='upload':
            if upload is None:
                raise ValueError('请选择标准 JSON 数据')
            if preview:
                from opinion_core.schemas.records import PostRecord
                records=[PostRecord.model_validate(p).model_dump(mode='json') for p in json.loads(upload.getvalue())]
                dataset='preview-upload'
            else:
                dataset=service.register_dataset(event,json.loads(upload.getvalue()))['dataset_id']
        event_spec={'event_id':event,'input_mode':mode,'dataset_ref':dataset if mode!='keywords' else None,
                    'keywords':[k.strip() for k in keywords.split(',') if k.strip()],
                    'platforms':[p.strip() for p in platforms.split(',') if p.strip()] if mode=='keywords' else [],
                    'start':start.isoformat(),'end':end.isoformat(),'as_of':as_of.isoformat(),'search_provider':provider,
                    'objectives':['retrospective']+(['forecast'] if forecast_enabled else [])+(['backtest'] if backtest else [])}
        request={'event':event_spec,'run_id':run,'labels':{'model':model,'provider':label_provider,'connector':connector or None,
                 'confidence_threshold':threshold,'max_calls':int(calls)},
                 'observations':{'start':start.isoformat(),'end':end.isoformat(),'window_seconds':int(window*3600)},
                 'media_mode':media,'max_total_calls':int(calls)}
        if mode=='keywords':
            request['crawl']={'platforms':event_spec['platforms'],'max_posts':int(max_posts),'session_ref':session or None}
        if forecast_enabled or backtest:
            request['model']={'training_cutoff':end.isoformat(),'horizon':int(horizon)}
        if shift:
            request['scenarios']=[{'scenario_id':'stance-shift','shift':shift,'assumptions':[assumptions]}]
        if preview:
            st.json(service.preview_plan(request))
        else:
            job=service.submit_run(request)
            st.query_params['job']=job['job_id']
            st.success('任务已入队，独立 Worker 将执行各阶段。')
    except Exception as exc:
        st.error(str(exc))


def show_observations(obs):
    st.caption('窗口按 UTC 存储；以下时间显示为 Asia/Shanghai。空窗口与不可判定字段保留缺失状态。')
    field=st.selectbox('分布维度',['sentiment','stance'])
    rows=[]
    hist=[]
    for w in obs['windows']:
        date=pd.Timestamp(w['start']).tz_convert('Asia/Shanghai')
        values=w['fields'][field]
        rows.append({'time':date,'mean':values['mean'],'coverage':values['coverage'],'raw_n':w['raw_n'],'valid_n':values['valid_n']})
        quantiles=values['quantiles'] or [None]*5
        rows[-1].update(q10=quantiles[0],q50=quantiles[2],q90=quantiles[4])
        hist.append({'time':date,**{str(round(b,2)):v for b,v in zip(obs['bins'][:-1],values['mass'] or [None]*(len(obs['bins'])-1))}})
    if rows:
        frame=pd.DataFrame(rows).set_index('time')
        st.line_chart(frame[['mean','q10','q50','q90']])
        st.dataframe(frame,width='stretch')
        st.dataframe(pd.DataFrame(hist).set_index('time').style.background_gradient(cmap='Blues'),width='stretch')
    st.json({'input_n':obs['input_n'],'missing_time_n':obs['missing_time_n'],'spec':obs['spec']})
    topics=sorted({t for w in obs['windows'] for t in w['topic_sentiment']})
    if topics:
        topic=st.selectbox('主题条件情感分布',topics)
        st.dataframe([{'start':w['start'],**w['topic_sentiment'].get(topic,{})} for w in obs['windows']],width='stretch')


def main():
    st.set_page_config(page_title='Tweets2Insights 智能工作台',layout='wide')
    st.title('Tweets2Insights 智能工作台')
    service=ApplicationService(Path(os.environ.get('T2I_ASSET_ROOT','.opinion-assets')))
    event=st.sidebar.text_input('事件 ID',value=st.query_params.get('event','demo'))
    if event: st.query_params['event']=event
    pages=st.tabs(['事件与数据','任务','分布复盘','预测与回测','情景','证据与报告'])
    with pages[0]: entry(service,event)
    jobs=service.list_jobs(event) if event else []
    with pages[1]:
        st.caption('执行服务：uv run python -m opinion_gateway.domain_worker --root .opinion-assets')
        if st.button('刷新任务'): st.rerun()
        if not jobs:
            st.info('当前事件尚无任务。'); return
        ids=[j['job_id'] for j in jobs]
        selected=st.selectbox('运行任务',ids,index=ids.index(st.query_params['job']) if st.query_params.get('job') in ids else 0,
                              format_func=lambda v:next(j['run_id']+' · '+j['status'] for j in jobs if j['job_id']==v))
        st.query_params['job']=selected
        job=service.job_status(event,selected)
        st.json({k:job[k] for k in ('run_id','status','stage','error_type','stop_reason')})
        a,b,c=st.columns(3)
        if a.button('取消',disabled=job['status'] not in ('queued','running','waiting_for_auth')):
            service.cancel_job(event,selected); st.rerun()
        if b.button('重试',disabled=job['status'] not in ('failed','cancelled','partial')):
            st.query_params['job']=service.retry_job(event,selected)['job_id']; st.rerun()
        if c.button('登录就绪后恢复',disabled=job['status']!='waiting_for_auth'):
            service.resume_job(event,selected); st.rerun()
        if job['status'] not in ('completed','partial'):
            return
        result,artifacts=read_result(service,event,job)
        st.json(result.get('usage',{}))
        if job['status']=='partial': st.warning('本次仅有部分产物，请结合覆盖率、停止原因与未完成阶段使用。')
    with pages[2]:
        if 'observations' in artifacts: show_observations(artifacts['observations'])
        else: st.info('尚无分布观测产物。')
    with pages[3]:
        st.caption('数值模块为实验实现；集合区间尚未完成覆盖率校准。')
        if artifacts.get('forecast',{}).get('steps'):
            st.line_chart(pd.DataFrame([{'step':s['step'],**{f:s['fields'][f]['mean'] for f in ('stance','sentiment')}} for s in artifacts['forecast']['steps']]).set_index('step'))
            st.json(artifacts['forecast'])
        if 'backtest' in artifacts: st.dataframe(artifacts['backtest']['scores'],width='stretch')
    with pages[4]:
        st.caption('同一模型状态、配对种子下的条件差异。')
        for branch in artifacts.get('scenarios',{}).get('branches',[]):
            st.write(branch['spec']); st.line_chart(pd.DataFrame(branch['mean_differences']).set_index('step'))
    with pages[5]:
        cards=artifacts.get('forum',{}).get('evidence',artifacts.get('evidence',{}).get('cards',[]))
        st.dataframe(cards,width='stretch',column_config={'source_url':st.column_config.LinkColumn('来源')})
        with st.expander('原始帖子与标签追溯'):
            post_id=st.text_input('输入 post_id')
            if post_id and artifacts.get('input',{}).get('dataset_id'):
                posts=service.repo.read(event,artifacts['input']['dataset_id'])
                st.json(next((p for p in posts if p['post_id']==post_id),{'status':'not_found'}))
                st.json(next((a for a in artifacts.get('labels',{}).get('annotations',[]) if a['post_id']==post_id),{'status':'not_labeled'}))
        report=artifacts.get('report')
        if report:
            st.components.v1.html(report['html'],height=720,scrolling=True)
            st.download_button('Markdown',report['markdown'],'report.md')
            st.download_button('HTML',report['html'],'report.html','text/html')
            if st.button('生成 PDF'):
                from intelligent_ui.exports.pdf_generator import generate_pdf_from_html_content
                directory=service.repo.path('exports',job['job_id']); directory.mkdir(parents=True,exist_ok=True)
                try:
                    pdf=generate_pdf_from_html_content(report['html'],directory)
                    st.download_button('下载 PDF',pdf,'report.pdf','application/pdf')
                except Exception as exc: st.error('PDF 生成失败：'+type(exc).__name__)
        st.download_button('运行证据 JSON',json.dumps(result,ensure_ascii=False,indent=2),'run.json','application/json')


if __name__=='__main__':
    main()
