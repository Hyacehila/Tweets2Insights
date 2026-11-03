import asyncio
import pytest
from fastmcp import Client
from opinion_gateway.mcp_server import create_server, DomainService


def test_discovery_and_upload_to_report_contract(tmp_path):
    async def scenario():
        async with Client(create_server(tmp_path)) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert {'register_dataset', 'describe_dataset', 'read_evidence', 'render_report', 'job_status', 'cancel_job'} <= names
            result = await client.call_tool('register_dataset', {'event_id': 'rain', 'records': [
                {'post_id': 'p1', 'raw_id': '1', 'platform': 'test', 'content': 'source text'}]})
            dataset = result.data
            args = {'event_id': 'rain', 'dataset_id': dataset['dataset_id'], 'run_id': 'r1'}
            with pytest.raises(Exception):
                await client.call_tool('render_report', args)
            stats = (await client.call_tool('describe_dataset', args)).data
            assert stats['count'] == 1 and stats['published_count'] == 0
            evidence = (await client.call_tool('read_evidence', {**args, 'offset': 0, 'limit': 10})).data
            assert evidence['items'][0]['post_id'] == 'p1'
            report = (await client.call_tool('render_report', args)).data
            assert report['status'] == 'completed'
            artifact = (await client.call_tool('read_artifact', {**args, 'artifact_id': 'report'})).data
            assert '[P:p1]' in artifact['markdown']
            manifest = (await client.call_tool('read_artifact', {**args, 'artifact_id': 'manifest'})).data
            assert manifest['code_version'].startswith('sha256:')
            status = (await client.call_tool('job_status', {'event_id': 'rain', 'job_id': report['job_id']})).data
            assert status['status'] == 'completed'
            with pytest.raises(Exception):
                await client.call_tool('job_status', {'event_id': 'other', 'job_id': report['job_id']})
    asyncio.run(scenario())


def test_untrusted_paths_and_input_validation(tmp_path):
    service = DomainService(tmp_path)
    with pytest.raises(ValueError):
        service.register_dataset('x', [{'content': 'missing identifiers'}])
    with pytest.raises(ValueError):
        service.register_dataset('../x', [])


def test_cancel_during_render_cannot_publish_report(tmp_path, monkeypatch):
    service = DomainService(tmp_path)
    d = service.register_dataset('e', [{'post_id': 'p', 'raw_id': 'p', 'platform': 'test', 'content': 'x'}])
    args = dict(event_id='e', dataset_id=d['dataset_id'], run_id='r')
    service.describe_dataset(**args)
    def interrupted_render(blocks):
        job = service.jobs.submit('e', 'r', 'short_report', {'dataset_id': d['dataset_id'], 'renderer': 'inventory-v1'})
        service.cancel_job('e', job.job_id)
        return 'stale report'
    monkeypatch.setattr('opinion_core.reporting.ir_markdown.render_blocks_to_markdown', interrupted_render)
    with pytest.raises(ValueError):
        service.render_report(**args)
    job = service.jobs.submit('e', 'r', 'short_report', {'dataset_id': d['dataset_id'], 'renderer': 'inventory-v1'})
    assert job.status == 'cancelled'
    with pytest.raises(ValueError):
        service.read_artifact(**args, artifact_id='report')
