from pathlib import Path
from streamlit.testing.v1 import AppTest
from opinion_gateway.mcp_server import DomainService
from opinion_gateway.worker import InventoryWorker


def test_fresh_session_reconnects_cancels_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr('dashboard.logic.opinion_workbench_logic.default_asset_root', lambda: tmp_path)
    service = DomainService(tmp_path)
    dataset = service.register_dataset('demo', [{'post_id': 'p', 'raw_id': '1', 'platform': 'test', 'content': 'x'}])
    job = service.submit_inventory_job('demo', dataset['dataset_id'], 'run')
    app = AppTest.from_file(str(Path('dashboard/pages/opinion_workbench.py')), default_timeout=15)
    app.query_params['event'] = 'demo'
    app.run()
    assert not app.exception
    assert app.selectbox[0].value == job['job_id']
    app.button(key='cancel_job').click().run()
    assert not app.exception
    assert service.job_status('demo', job['job_id'])['status'] == 'cancelled'
    fresh = AppTest.from_file(str(Path('dashboard/pages/opinion_workbench.py')), default_timeout=15)
    fresh.query_params['event'] = 'demo'
    fresh.run()
    assert not fresh.exception
    fresh.button(key='retry_job').click().run()
    assert service.list_jobs('demo')[0]['status'] == 'queued'
    InventoryWorker(tmp_path).run_once()
    fresh.run()
    assert not fresh.exception
    assert any('上传资料概览' in element.value for element in fresh.markdown)
