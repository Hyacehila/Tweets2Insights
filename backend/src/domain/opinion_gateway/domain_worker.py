"""Persistent executor for complete event plans. Runs outside the UI/MCP request."""
import argparse
import threading
import uuid
from .application import ApplicationService
from .jobs import TransitionConflict
from .runtime import Execution, IncompleteStage
from .connectors import WaitingForAuthentication
from .budget import BudgetExceeded


class DomainWorker:
    def __init__(self,root,lease_seconds=90):
        self.service=ApplicationService(root)
        self.identity=uuid.uuid4().hex
        self.lease_seconds=lease_seconds

    def run_once(self):
        store=self.service.jobs
        job=store.claim(self.identity,self.lease_seconds,kinds=['analysis_run','analysis_tool'])
        if job is None:
            return None
        stopped=threading.Event()
        def check():
            current=store.get(job.job_id)
            if current.status!='running' or current.lease_token!=job.lease_token:
                raise TransitionConflict('job cancelled or ownership lost')
        def heartbeat():
            while not stopped.wait(self.lease_seconds/3):
                try:
                    store.heartbeat(job.job_id,job.worker,self.lease_seconds,lease_token=job.lease_token)
                except Exception:
                    return
        keeper=threading.Thread(target=heartbeat,daemon=True); keeper.start()
        execution=None
        try:
            params=store.parameters(job.job_id)
            if params['code_version']!=self.service.code_version:
                raise ValueError('worker source changed; create a new run')
            request=self.service.assets.read(job.event_id,job.run_id,params['request_ref'],'request')
            execution=Execution(self.service,request,check)
            if job.kind=='analysis_tool':
                for key in ('input','schema','labels'):
                    ref=params['source_artifacts'][key]
                    execution.values[key]=self.service.assets.read(job.event_id,job.run_id,ref['artifact_id'],key)
                value=execution.toolbox.execute(params['tool'],params['parameters'])
                check()
                ref=self.service.assets.put(job.event_id,job.run_id,'analysis-tool',value)
                store.finish(job,{'event_id':job.event_id,'run_id':job.run_id,'artifacts':{'analysis-tool':ref},'usage':execution.ledger.summary()})
                return store.get(job.job_id)
            checkpoints=store.batches(job.job_id)
            reuse=True
            partial=[]
            for index,task in enumerate(params['plan']['tasks']):
                key=task['task_id']
                store.set_stage(job,key)
                if reuse and key in checkpoints:
                    ref=checkpoints[key]
                    value=self.service.assets.read(job.event_id,job.run_id,ref['artifact_id'],key)
                else:
                    if reuse:
                        store.discard_batches(job,[t['task_id'] for t in params['plan']['tasks'][index:]])
                    reuse=False
                    value=execution.execute(task['operation'])
                    check()
                    ref=self.service.assets.put(job.event_id,job.run_id,key,value)
                    if value.get('status')=='partial':
                        partial.append(key)
                    else:
                        store.commit_batch(job.job_id,job.worker,key,ref,lease_token=job.lease_token)
                execution.values[key],execution.refs[key]=value,ref
            result={'event_id':job.event_id,'run_id':job.run_id,'artifacts':execution.refs,
                    'plan':params['plan'],'usage':execution.ledger.summary(),'partial_stages':partial,
                    'code_version':params['code_version'],'human_review_required':False}
            store.finish(job,result,status='partial' if partial else 'completed')
        except WaitingForAuthentication:
            try: store.wait_for_auth(job)
            except TransitionConflict: pass
        except (IncompleteStage,BudgetExceeded) as exc:
            try:
                store.finish(job,{'event_id':job.event_id,'run_id':job.run_id,
                    'artifacts':execution.refs if execution else {},'reason':type(exc).__name__,
                    'detail':str(exc),'usage':execution.ledger.summary() if execution else {}},status='partial')
            except TransitionConflict: pass
        except Exception as exc:
            try: store.stop_owned(job,error_type=type(exc).__name__)
            except TransitionConflict: pass
        finally:
            stopped.set(); keeper.join(timeout=2)
        return store.get(job.job_id)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Domain plan worker')
    parser.add_argument('--root',default='.opinion-assets')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args(argv)
    worker=DomainWorker(args.root)
    from .worker import InventoryWorker
    inventory=InventoryWorker(args.root)
    try:
        while True:
            result=worker.run_once() or inventory.run_once()
            if args.once:
                return 1 if result and result.status=='failed' else 0
            if result is None:
                threading.Event().wait(1)
    except KeyboardInterrupt:
        return 0


if __name__=='__main__':
    raise SystemExit(main())
