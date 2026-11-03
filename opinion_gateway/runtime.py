"""Stage handlers for the new architecture. Legacy PocketFlow is never imported."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime
import subprocess
import sys
import time
from opinion_core.schemas.workflow import RunRequest
from opinion_core.labeling.glm_provider import GLMJsonProvider,GLMSchemaBuilder
from opinion_core.labeling.event_preparation import EventPreparation
from opinion_core.labeling.pipeline import WeakLabeler
from opinion_core.analytics.observations import build_observations,summarize
from opinion_core.analytics.charts import build_charts
from opinion_core.evidence.providers import search as provider_search
from opinion_core.evidence.cards import web_cards,post_cards
from opinion_core.evidence.forum import discuss
from opinion_core.evidence.media import analyze_media
from opinion_core.dynamics.engine import fit_assimilate,forecast
from opinion_core.dynamics.backtest import rolling_backtest
from opinion_core.scenarios.paired import compare_scenarios
from opinion_core.reporting.content import build_content
from opinion_core.reporting.structure import build_structure
from opinion_core.reporting.render import render_report
from .connectors import DecisionConnector,invoke_connector,WaitingForAuthentication,ConnectorUnavailable
from .budget import CallLedger
from .label_workflow import DurableLabelBudget
from .dataset_repository import storage_id


class MeteredGLM(GLMJsonProvider):
    def __init__(self,ledger,**kwargs):
        super().__init__(**kwargs)
        self.ledger,self.stage=ledger,'model'

    def request(self,instruction,payload):
        call=self.ledger.reserve(self.stage,self.version)
        try:
            result,usage=super().request(instruction,payload)
            self.ledger.settle(call,usage)
            return result,usage
        except Exception:
            self.ledger.settle(call,status='uncertain')
            raise


class IncompleteStage(RuntimeError):
    pass


class Execution:
    def __init__(self,service,request,check_cancel):
        self.service=service
        self.req=RunRequest.model_validate(request)
        self.check_cancel=check_cancel
        self.values,self.refs={},{}
        self.scope=hashlib.sha256((self.req.event.event_id+'\0'+self.req.run_id).encode()).hexdigest()
        self.ledger=CallLedger(service.repo.root,self.scope,self.req.max_total_calls,self.req.max_cost)
        self._model=None

    @property
    def model(self):
        if self._model is None:
            self._model=MeteredGLM(self.ledger,model=self.req.labels.model)
        return self._model

    def search(self,query,**options):
        self.check_cancel()
        provider=self.req.event.search_provider
        if options.get('provider',provider)!=provider:
            raise ValueError('search provider cannot change inside a run')
        reservation=self.ledger.reserve('search',provider)
        try:
            response=provider_search(query,provider=provider,max_results=options.get('max_results',5),timeout_seconds=20)
            self.ledger.settle(reservation,status='failed' if response.get('error') else 'returned')
            ref=self.service.assets.put(self.req.event.event_id,self.req.run_id,'search-response',response)
            return response
        except Exception:
            self.ledger.settle(reservation,status='uncertain')
            raise

    def collect(self):
        checkpoint=self.service.repo.path(storage_id(self.req.event.event_id),'crawl',storage_id(self.req.run_id)+'.json')
        payload=json.dumps({'event':self.req.event.model_dump(mode='json'),'crawl':self.req.crawl.model_dump(mode='json'),
                            '_checkpoint_path':str(checkpoint)},ensure_ascii=False)
        process=subprocess.Popen([sys.executable,'-m','crawler_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            # communicate(timeout) drains pipes in a background reader on Windows.
            while True:
                self.check_cancel()
                try:
                    output,_=process.communicate(input=payload,timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    payload=None
            if process.returncode:
                raise RuntimeError('isolated crawler failed')
            result=json.loads(output)
            if result['status']=='waiting_for_auth':
                raise WaitingForAuthentication('collection needs local session')
            if result['status']=='connector_unavailable':
                raise ConnectorUnavailable('configure a platform connector')
            if not result.get('records'):
                raise IncompleteStage('collection returned no records; coverage is incomplete')
            dataset=self.service.register_dataset(self.req.event.event_id,result.pop('records'))
            return {**result,**dataset}
        finally:
            if process.poll() is None:
                process.kill(); process.communicate()

    def posts(self):
        return self.service.repo.read(self.req.event.event_id,self.values['input']['dataset_id'])

    def execute(self,operation):
        self.check_cancel()
        req=self.req
        if operation=='collect':
            return self.collect()
        if operation=='load_dataset':
            return {'dataset_id':req.event.dataset_ref,'count':len(self.service.repo.read(req.event.event_id,req.event.dataset_ref)),'status':'completed'}
        if operation=='prepare_schema':
            self.model.stage='schema'
            library=json.loads((Path(__file__).resolve().parents[1]/'opinion_core/labeling/vocabularies/common-v1.json').read_text(encoding='utf-8'))
            event=req.event.model_copy(update={'input_mode':'existing','dataset_ref':self.values['input']['dataset_id']})
            result=EventPreparation(self.service.repo.root,search=self.search,builder=GLMSchemaBuilder(self.model),
                        builder_version=GLMSchemaBuilder(self.model).version).prepare(event,library,max_total_calls=req.labels.max_schema_calls)
            if result['status']!='frozen':
                raise IncompleteStage(result['error_type'])
            return result
        if operation=='label':
            self.model.stage='label'
            if req.labels.provider=='connector':
                if not req.labels.connector:
                    raise ConnectorUnavailable('label connector ID required')
                provider=DecisionConnector(req.labels.connector,req.media_mode,self.ledger)
            else:
                if req.media_mode!='text_only':
                    raise ValueError('image labeling requires an explicit multimodal connector')
                provider=self.model
            labeler=WeakLabeler(self.service.repo.root,provider,prompt_version='weak-json-v1',
                               confidence_threshold=req.labels.confidence_threshold,batch_size=req.labels.batch_size)
            budget=DurableLabelBudget(self.service.repo.root/'label-budget.sqlite',self.scope,req.labels.max_calls)
            return labeler.label(self.posts(),self.values['schema']['schema'],budget=budget,check_cancel=self.check_cancel)
        if operation=='observations':
            return build_observations(self.posts(),self.values['labels']['annotations'],self.values['schema']['schema'],req.observations,self.check_cancel)
        if operation=='charts':
            return build_charts(self.values['observations'])
        if operation=='evidence':
            return {'cards':web_cards(self.values['schema']['evidence'],req.event.as_of)+post_cards(self.posts())}
        if operation=='media':
            def invoke(payload):
                call=self.ledger.reserve('media','media-default')
                try:
                    answer=invoke_connector('media','default',payload)
                    self.ledger.settle(call,answer.get('usage'),answer.get('cost'))
                    return answer
                except Exception:
                    self.ledger.settle(call,status='uncertain'); raise
            return analyze_media(self.posts(),invoke)
        if operation=='forum':
            self.model.stage='forum'
            context=summarize(self.values['observations'])
            context['window_total']=len(context['windows'])
            context['windows']=context['windows'][-30:]
            return discuss(context,self.values['evidence']['cards']+self.values.get('media',{}).get('evidence',[]),
                self.model,lambda q:web_cards(self.search(q),req.event.as_of),req.forum_rounds,self.check_cancel)
        if operation=='assimilate':
            available=any(w['joint_n'] and datetime.fromisoformat(w['end'])<=req.model.training_cutoff for w in self.values['observations']['windows'])
            if not available:
                return {'status':'partial','reason':'insufficient_joint_observations'}
            return fit_assimilate(self.values['observations'],req.model,self.check_cancel)
        if operation=='forecast':
            if 'ensemble' not in self.values['state']:
                return {'status':'partial','reason':'model_state_unavailable','steps':[]}
            return forecast(self.values['state'],check_cancel=self.check_cancel)
        if operation=='backtest':
            return rolling_backtest(self.values['observations'],req.model,self.check_cancel)
        if operation=='simulate':
            if 'ensemble' not in self.values['state']:
                return {'status':'partial','reason':'model_state_unavailable','branches':[]}
            return compare_scenarios(self.values['state'],req.scenarios,self.check_cancel)
        if operation=='content':
            evidence=self.values.get('forum',{}).get('evidence',self.values['evidence']['cards'])
            return build_content(req.event.event_id,req.run_id,self.values['observations'],evidence,
                {key:ref['artifact_id'] for key,ref in self.refs.items()},self.values.get('forum'),self.values.get('forecast'),self.values.get('scenarios'))
        if operation=='structure':
            return build_structure(self.values['content'])
        if operation=='render':
            return render_report(self.values['content'],self.values['structure'],self.values['charts'])
        raise ValueError('unknown operation')
