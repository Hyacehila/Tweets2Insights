import pytest
from opinion_core.evaluation.demo import evaluate_demo

FIELDS = ['topic', 'publisher', 'emotion', 'sentiment', 'stance']


def fixture(n=600):
    labels = {field:['a','b'] for field in FIELDS}
    gold = [{'post_id':f'p{i}', 'group_id':f'g{i}', 'target_id':'target', 'split':'calibration' if i<200 else 'test',
             'labels':{field:('a' if i%2==0 else 'b') for field in FIELDS}} for i in range(n)]
    predicted = [{'post_id':row['post_id'], 'target_id':'target', **{field:{'status':'accepted','value':row['labels'][field]} for field in FIELDS}}
                 for row in gold if row['split']=='test']
    return gold, predicted, labels


def test_exact_demo_scale_and_perfect_predictions():
    gold, predicted, labels = fixture()
    report = evaluate_demo(gold, predicted, predicted, labels)
    assert report['passed'] and report['scale_passed']
    assert report['fields']['stance']['macro_f1'] == 1
    assert report['fields']['topic']['coverage'] == 1
    assert report['sample_counts'] == {'calibration':200, 'test':400}


def test_abstention_does_not_inflate_quality_acceptance():
    gold, predicted, labels = fixture()
    baseline = fixture()[1]
    for row in predicted[:80]:
        row['stance'] = {'status':'abstained', 'value':None}
    report = evaluate_demo(gold, predicted, baseline, labels)
    field = report['fields']['stance']
    assert field['macro_f1'] == 1 and field['coverage'] == .8
    assert field['end_to_end_macro_f1'] < 1
    assert not report['passed'] and not field['passed']


def test_missing_predictions_are_in_denominator_and_empty_never_passes():
    gold, _, labels = fixture()
    report = evaluate_demo(gold, [], [], labels)
    assert not report['passed']
    assert report['fields']['topic']['macro_f1'] is None
    assert report['fields']['topic']['coverage'] == 0
    with pytest.raises(ValueError):
        evaluate_demo([], [], [], labels)


def test_leakage_duplicates_and_unknown_labels_are_rejected():
    gold, predicted, labels = fixture()
    gold[200]['group_id'] = gold[0]['group_id']
    with pytest.raises(ValueError, match='group'):
        evaluate_demo(gold, predicted, predicted, labels)
    gold, predicted, labels = fixture()
    with pytest.raises(ValueError, match='duplicate'):
        evaluate_demo(gold, predicted + predicted[:1], predicted, labels)
    predicted[0]['topic']['value'] = 'unknown'
    with pytest.raises(ValueError, match='label'):
        evaluate_demo(gold, predicted, [], labels)


def test_small_fixture_reports_metrics_but_not_demo_acceptance():
    gold, predicted, labels = fixture(210)
    report = evaluate_demo(gold, predicted, predicted, labels)
    assert report['fields']['topic']['macro_f1'] == 1
    assert not report['scale_passed'] and not report['passed']


def test_stance_for_different_target_cannot_pass_demo():
    gold, predicted, labels = fixture()
    predicted[0]['target_id'] = 'another-proposition'
    with pytest.raises(ValueError, match='target'):
        evaluate_demo(gold, predicted, [], labels)
