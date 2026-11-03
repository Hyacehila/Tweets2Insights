"""Durable local inventory worker. Does not perform paid inference or collection."""
import argparse
import threading
import uuid
from opinion_gateway.jobs import TransitionConflict
from opinion_gateway.mcp_server import DomainService
from opinion_core.reporting.ir_markdown import render_blocks_to_markdown


class InventoryWorker:
    def __init__(self, root, lease_seconds=60):
        if lease_seconds <= 0:
            raise ValueError('lease must be positive')
        self.service = DomainService(root)
        self.worker_id = uuid.uuid4().hex
        self.lease_seconds = lease_seconds

    def run_once(self):
        store = self.service.jobs
        job = store.claim(self.worker_id, self.lease_seconds, kinds=['inventory_report'])
        if job is None:
            return None
        stopped = threading.Event()
        def heartbeat():
            while not stopped.wait(self.lease_seconds / 3):
                try:
                    store.heartbeat(job.job_id, job.worker, self.lease_seconds, lease_token=job.lease_token)
                except (TransitionConflict, OSError):
                    return
        keeper = threading.Thread(target=heartbeat, daemon=True)
        keeper.start()
        try:
            parameters = store.parameters(job.job_id)
            if parameters['code_version'] != self.service.code_version:
                raise ValueError('worker source version differs from submitted job')
            args = (job.event_id, parameters['dataset_id'], job.run_id)
            done = store.batches(job.job_id)
            for stage, compute in (
                ('statistics', lambda: self.service.describe_dataset(*args)),
                ('evidence', lambda: self.service.read_evidence(*args, limit=5)),
            ):
                store.set_stage(job, stage)
                if stage not in done:
                    done[stage] = compute()
                    store.commit_batch(job.job_id, job.worker, stage, done[stage], lease_token=job.lease_token)
            store.set_stage(job, 'report')
            stats, evidence = done['statistics'], done['evidence']
            lines = [f"记录总数：{stats['count']}；可解析发布时间：{stats['published_count']}。[S:statistics]",
                     '本报告是上传资料概览，尚未执行先导检索、标签评测或立场推断。']
            lines.extend(f"来源记录 [{item['reference']}]，正文见证据工具。" for item in evidence['items'])
            markdown = '# 上传资料概览\n\n' + render_blocks_to_markdown([
                {'type': 'paragraph', 'inlines': [{'text': line}]} for line in lines])
            store.finish(job, {'markdown': markdown, 'statistics': stats, 'evidence': evidence,
                               'manifest': {'event_id': job.event_id, 'run_id': job.run_id, **parameters}})
        except Exception as exc:
            try:
                store.stop_owned(job, error_type=type(exc).__name__)
            except TransitionConflict:
                pass  # A replacement worker or completed cancellation owns the state now.
        finally:
            stopped.set()
            keeper.join(timeout=2)
        return store.get(job.job_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.opinion-assets')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    worker = InventoryWorker(args.root)
    idle = threading.Event()
    try:
        while True:
            result = worker.run_once()
            if args.once:
                return 1 if result and result.status == 'failed' else 0
            if result is None:
                idle.wait(1)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
