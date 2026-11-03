"""Persistent upload jobs with event-scoped reconnect, cancellation and retry."""
import json
import uuid
import streamlit as st
from opinion_gateway.mcp_server import DomainService
from dashboard.logic.opinion_workbench_logic import default_asset_root

st.title('舆情工作台：上传资料概览')
st.caption('标准记录上传后自动排队。当前生成资料概览，尚未执行模型标注和完整舆情复盘。')
service = DomainService(default_asset_root())
event_id = st.text_input('事件 ID', value=st.query_params.get('event', 'event-1'), key='event_id')
upload = st.file_uploader('上传标准记录 JSON', type=['json'])
if st.button('校验并提交概览任务', disabled=upload is None):
    try:
        dataset = service.register_dataset(event_id, json.loads(upload.getvalue()))
        result = service.submit_inventory_job(event_id, dataset['dataset_id'], uuid.uuid4().hex)
        st.query_params.update(event=event_id, job=result['job_id'])
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))
st.button('刷新任务状态')
jobs = service.list_jobs(event_id)
if not jobs:
    st.info('当前事件暂无任务。')
else:
    lookup = {job['job_id']: job for job in jobs}
    identifiers = list(lookup)
    preferred = st.query_params.get('job')
    index = identifiers.index(preferred) if preferred in lookup else 0
    selected = st.selectbox('已保存的任务', identifiers, index=index,
                            format_func=lambda key: f"{lookup[key]['run_id']} · {lookup[key]['status']} · {key[:8]}")
    st.query_params.update(event=event_id, job=selected)
    job = lookup[selected]
    st.json({key: job[key] for key in ('job_id', 'run_id', 'status', 'stage', 'error_type', 'stop_reason', 'retry_of')})
    if job['status'] in {'queued', 'running', 'waiting_for_auth'}:
        if st.button('取消任务', key='cancel_job'):
            try:
                service.cancel_job(event_id, selected)
                st.rerun()
            except ValueError:
                st.info('任务状态已更新，请刷新查看。')
    if job['status'] in {'failed', 'cancelled', 'partial'} and job['kind'] == 'inventory_report':
        if st.button('重试未完成阶段', key='retry_job'):
            new_job = service.retry_job(event_id, selected)
            st.query_params.update(event=event_id, job=new_job['job_id'])
            st.rerun()
    if job['status'] == 'completed' and job['kind'] == 'inventory_report':
        artifact = service.read_job_artifact(event_id, selected)
        st.markdown(artifact['markdown'])
        st.download_button('下载 Markdown', artifact['markdown'], file_name='inventory.md')
        st.download_button('下载运行证据', json.dumps(artifact, ensure_ascii=False, indent=2), file_name='inventory.json')
        with st.expander('来源证据'):
            st.json(artifact['evidence'])
    elif job['status'] == 'queued':
        st.info('任务已保存，等待后台执行。可以关闭页面，稍后按事件 ID 返回查看。')
