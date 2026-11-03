from opinion_gateway.mcp_server import DomainService
from opinion_gateway.label_workflow import run_label_workflow
from opinion_core.schemas.event import EventSpec


def test_search_schema_batch_labels_persist_without_human_gate(tmp_path):
    service = DomainService(tmp_path)
    data = service.register_dataset('e', [{'post_id':'p', 'raw_id':'1', 'platform':'test', 'content':'支持措施'}])
    event = EventSpec(event_id='e', input_mode='existing', dataset_ref=data['dataset_id'], keywords=['rain'],
                      as_of='2026-11-03T00:00:00Z', search_provider='deepseek')
    library = {name:[{'id':f'{name}{i}', 'definition':f'{name} {i}'} for i in range(n)]
               for name,n in [('topics',5),('publishers',5),('emotions',10)]}
    def builder(evidence, vocab):
        return {**vocab, 'targets':[{'id':'rescue','definition':'支持救援措施'}]}
    builder.version = 'test-builder'
    class Provider:
        version = 'test-labeler'
        def predict(self, posts, schema):
            fields = {name:{'value':value,'confidence':.9} for name,value in {
                'topic':'topics0','publisher':'publishers0','emotion':'emotions0','sentiment':0.,'stance':'support'}.items()}
            fields['stance']['target_id'] = 'rescue'
            return {'records':[{'post_id':'p','fields':fields}]}
    result = run_label_workflow(tmp_path, event, library, run_id='run', provider=Provider(), builder=builder,
        search=lambda *a,**k: {'provider':'deepseek','error':'','results':[{'url':'https://example.com'}]}, max_label_calls=1)
    assert result['status'] == 'completed' and result['annotations'][0]['stance']['value'] == 'support'
    assert result['human_review_required'] is False
    assert result['manifest']['code_version'].startswith('sha256:')
    result2 = run_label_workflow(tmp_path, event, library, run_id='run', provider=Provider(), builder=builder,
        search=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected search')), max_label_calls=1)
    assert result2['cache_hits'] == 1 and result2['calls'] == 0
    import pytest
    with pytest.raises(ValueError, match='configuration'):
        run_label_workflow(tmp_path, event, library, run_id='run', provider=Provider(), builder=builder,
            search=lambda *a, **k: None, max_label_calls=1, confidence_threshold=.8)


def test_persistent_label_budget_counts_across_instances(tmp_path):
    from opinion_gateway.label_workflow import DurableLabelBudget
    from concurrent.futures import ThreadPoolExecutor
    budgets = [DurableLabelBudget(tmp_path / 'budget.sqlite', 'run-key', 2) for _ in range(4)]
    with ThreadPoolExecutor(4) as pool:
        assert sum(pool.map(lambda budget: budget.reserve(), budgets)) == 2
