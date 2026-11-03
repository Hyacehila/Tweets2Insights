"""Minimal upload inventory workbench; no collection or paid inference."""
import json
import uuid
from pathlib import Path
import streamlit as st
from opinion_gateway.mcp_server import DomainService

st.title('舆情工作台：上传资料概览')
st.caption('标准 PostRecord JSON；此入口只做资料统计和证据预览，尚非正式标注复盘。')
service = DomainService(Path(__file__).resolve().parents[2] / '.opinion-assets')
event_id = st.text_input('事件 ID', value='event-1')
upload = st.file_uploader('上传标准记录 JSON', type=['json'])
if st.button('校验并生成概览', disabled=upload is None):
    try:
        dataset = service.register_dataset(event_id, json.loads(upload.getvalue()))
        args = dict(event_id=event_id, dataset_id=dataset['dataset_id'], run_id=uuid.uuid4().hex)
        service.describe_dataset(**args)
        result = service.render_report(**args)
        st.session_state['opinion_run'] = args
        st.session_state['opinion_job'] = result['job_id']
    except (ValueError, OSError) as exc:
        st.error(str(exc))
if 'opinion_run' in st.session_state:
    args = st.session_state['opinion_run']
    st.json(service.job_status(args['event_id'], st.session_state['opinion_job']))
    st.markdown(service.read_artifact(**args, artifact_id='report')['markdown'])
    st.json(service.read_evidence(**args))
