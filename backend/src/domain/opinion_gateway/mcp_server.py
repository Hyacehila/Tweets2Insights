"""Explicit asset-ID domain tools. Run with uv run python -m opinion_gateway.mcp_server."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from fastmcp import FastMCP
from opinion_core.schemas.records import PostRecord
from opinion_core.schemas.run import RunManifest
from opinion_gateway.dataset_repository import DatasetRepository, atomic_json
from opinion_gateway.jobs import JobStore


class DomainService:
    def __init__(self, root):
        self.repo = DatasetRepository(root)
        self.jobs = JobStore(self.repo.root / 'jobs.sqlite')
        source_root = Path(__file__).resolve().parents[1]
        sources = sorted((source_root / 'opinion_core').rglob('*.py')) + sorted((source_root / 'opinion_gateway').rglob('*.py'))
        sources += sorted((source_root / 'crawler_worker').rglob('*.py'))
        sources += sorted((source_root / 'opinion_core/labeling/vocabularies').glob('*.json'))
        sources += sorted((source_root / 'opinion_core/reporting').glob('*.md'))
        digest = hashlib.sha256()
        for source in sources:
            digest.update(str(source.relative_to(source_root)).replace('\\', '/').encode())
            digest.update(source.read_bytes())
        self.code_version = 'sha256:' + digest.hexdigest()

    def register_dataset(self, event_id: str, records: list[dict]) -> dict:
        """Validate uploaded standard records; never starts collection or annotation."""
        parsed = [PostRecord.model_validate(record).model_dump(mode='json') for record in records]
        if len({p['post_id'] for p in parsed}) != len(parsed):
            raise ValueError('duplicate post_id')
        return self.repo.register(event_id, parsed)

    def describe_dataset(self, event_id: str, dataset_id: str, run_id: str) -> dict:
        """Compute deterministic inventory statistics, without interpreting missing labels."""
        posts = self.repo.read(event_id, dataset_id)
        directory = self.repo.run_dir(event_id, dataset_id, run_id)
        result = {'event_id': event_id, 'dataset_id': dataset_id, 'run_id': run_id,
                  'count': len(posts), 'published_count': sum(p['published_at'] is not None for p in posts),
                  'platforms': dict(Counter(p['platform'] for p in posts)),
                  'label_status': 'not_evaluated', 'evidence_ref': 'statistics'}
        atomic_json(directory / 'statistics.json', result)
        return result

    def read_evidence(self, event_id: str, dataset_id: str, run_id: str, offset: int = 0, limit: int = 20) -> dict:
        """Read bounded source excerpts with stable post references (untrusted data)."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError('offset >= 0 and limit in 1..100 required')
        posts = self.repo.read(event_id, dataset_id)
        return {'items': [{'post_id': p['post_id'], 'reference': 'P:' + p['post_id'],
                           'excerpt': p['content'][:500], 'source_url': p['source_url'],
                           'published_at': p['published_at']} for p in posts[offset:offset+limit]],
                'total': len(posts), 'offset': offset}

    def render_report(self, event_id: str, dataset_id: str, run_id: str) -> dict:
        """Render a short source inventory report after deterministic statistics exist."""
        directory = self.repo.run_dir(event_id, dataset_id, run_id)
        stats_path = directory / 'statistics.json'
        if not stats_path.exists():
            raise ValueError('describe_dataset must succeed before render_report')
        stats = json.loads(stats_path.read_text(encoding='utf-8'))
        job = self.jobs.submit(event_id, run_id, 'short_report', {'dataset_id': dataset_id, 'renderer': 'inventory-v1'})
        if job.status == 'completed':
            return {**job.model_dump(), 'artifact_id': 'report'}
        if job.status != 'queued':
            raise ValueError('report job already running or stopped')
        job = self.jobs.transition(job.job_id, 'running', expected_revision=job.revision)
        try:
            from opinion_core.reporting.ir_markdown import render_blocks_to_markdown
            evidence = self.read_evidence(event_id, dataset_id, run_id, limit=5)
            blocks = [{'type': 'paragraph', 'text': f"记录总数：{stats['count']}；可解析发布时间：{stats['published_count']}。[S:statistics]"},
                      {'type': 'paragraph', 'text': '本报告仅描述上传资料。尚未执行先导检索、标签质量验收或立场推断。'}]
            for item in evidence['items']:
                blocks.append({'type': 'paragraph', 'text': f"来源记录 [{item['reference']}]，正文见证据工具。"})
            blocks = [{'type': 'paragraph', 'inlines': [{'text': block['text']}]} for block in blocks]
            markdown = '# 上传资料概览\n\n' + render_blocks_to_markdown(blocks)
            atomic_json(directory / 'report.json', {'markdown': markdown, 'statistics': stats, 'evidence': evidence})
            manifest = RunManifest(run_id=run_id, event_id=event_id, dataset_id=dataset_id,
                                   data_version=dataset_id.removeprefix('ds-'), code_version=self.code_version)
            atomic_json(directory / 'manifest.json', manifest.model_dump(mode='json'))
            job = self.jobs.transition(job.job_id, 'completed', expected_revision=job.revision)
            return {**job.model_dump(), 'artifact_id': 'report'}
        except Exception:
            current = self.jobs.get(job.job_id)
            if current.status == 'running':
                self.jobs.transition(job.job_id, 'failed', expected_revision=current.revision, error_type='render_error')
            elif current.status == 'cancel_requested':
                self.jobs.transition(job.job_id, 'cancelled', expected_revision=current.revision, stop_reason='user_cancelled')
            raise

    def read_artifact(self, event_id: str, dataset_id: str, run_id: str, artifact_id: str) -> dict:
        """Read an allowlisted artifact; accepts no filesystem paths."""
        if artifact_id not in {'statistics', 'report', 'manifest'}:
            raise ValueError('unknown artifact')
        directory = self.repo.run_dir(event_id, dataset_id, run_id)
        if artifact_id == 'report':
            job = self.jobs.find(event_id, run_id, 'short_report', {'dataset_id': dataset_id, 'renderer': 'inventory-v1'})
            if job is None or job.status != 'completed':
                raise ValueError('report is not committed')
        return json.loads((directory / (artifact_id + '.json')).read_text(encoding='utf-8'))

    def job_status(self, event_id: str, job_id: str) -> dict:
        """Read a persisted job belonging to the selected event."""
        job = self.jobs.get(job_id)
        if job.event_id != event_id:
            raise ValueError('job does not belong to event')
        return job.model_dump(mode='json')

    def submit_inventory_job(self, event_id: str, dataset_id: str, run_id: str) -> dict:
        """Queue an inventory report; a separate local worker performs the stages."""
        self.repo.read(event_id, dataset_id)
        job = self.jobs.submit(event_id, run_id, 'inventory_report',
                               {'dataset_id': dataset_id, 'code_version': self.code_version, 'renderer': 'inventory-v2'})
        return job.model_dump(mode='json')

    def list_jobs(self, event_id: str, limit: int = 50) -> list[dict]:
        """Reconnect to persisted jobs after refresh; newest first."""
        return [job.model_dump(mode='json') for job in self.jobs.list_jobs(event_id, limit)]

    def retry_job(self, event_id: str, job_id: str) -> dict:
        """Retry a stopped inventory job as a linked new job, preserving committed stages."""
        job = self.job_status(event_id, job_id)
        if job['kind'] != 'inventory_report':
            raise ValueError('retry supported only for inventory jobs')
        return self.jobs.retry(job_id).model_dump(mode='json')

    def read_job_artifact(self, event_id: str, job_id: str) -> dict:
        """Read the atomically committed result of a completed domain job."""
        self.job_status(event_id, job_id)
        return self.jobs.result(job_id)

    def cancel_job(self, event_id: str, job_id: str) -> dict:
        """Request cancellation using optimistic concurrency; terminal jobs stay terminal."""
        job = self.job_status(event_id, job_id)
        if job['status'] in {'completed', 'cancelled', 'partial', 'failed', 'cancel_requested'}:
            return job
        target = 'cancelled' if job['status'] == 'queued' else 'cancel_requested'
        return self.jobs.transition(job_id, target, expected_revision=job['revision']).model_dump(mode='json')


def create_server(root):
    from .application import ApplicationService
    service = ApplicationService(root)
    server = FastMCP('Opinion Domain Tool Service')
    for name in ('register_dataset', 'describe_dataset', 'read_evidence', 'render_report', 'read_artifact', 'job_status', 'cancel_job',
                 'submit_inventory_job', 'list_jobs', 'retry_job', 'read_job_artifact', 'preview_plan', 'submit_run',
                 'list_datasets','list_artifacts','read_domain_artifact','resume_job', 'analysis_tool_catalog','submit_analysis_tool'):
        server.tool()(getattr(service, name))
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.opinion-assets')
    args = parser.parse_args()
    create_server(Path(args.root)).run()
