"""Deterministic single-label demo metrics; consumes real gold data supplied by the operator."""
import argparse
import hashlib
import json
from pathlib import Path

FIELDS = ('topic', 'publisher', 'emotion', 'sentiment', 'stance')
COMPARISON_TOLERANCE = 1e-12


def _index(rows):
    result = {}
    for row in rows:
        key = row['post_id']
        if key in result:
            raise ValueError('duplicate post_id')
        result[key] = row
    return result


def _macro(truth, output, classes):
    if not truth:
        return None
    scores = []
    for label in classes:
        tp = sum(t == label and p == label for t, p in zip(truth, output))
        fp = sum(t != label and p == label for t, p in zip(truth, output))
        fn = sum(t == label and p != label for t, p in zip(truth, output))
        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.)
    return sum(scores) / len(scores)


def _metrics(rows, predictions, field, classes):
    truth, output, accepted_truth, accepted_output = [], [], [], []
    states = {'accepted':0, 'abstained':0, 'failed':0, 'missing':0}
    for row in rows:
        target = row['labels'][field]
        raw = predictions.get(row['post_id'], {}).get(field, {'status':'missing','value':None})
        status, value = raw['status'], raw.get('value')
        if field == 'stance' and status == 'accepted' and predictions[row['post_id']].get('target_id') != row['target_id']:
            raise ValueError('stance target differs from gold target')
        if status not in states or (status == 'accepted' and value not in classes) or (status != 'accepted' and value is not None):
            raise ValueError('invalid prediction status or label')
        states[status] += 1
        truth.append(target)
        output.append(value if status == 'accepted' else None)
        if status == 'accepted':
            accepted_truth.append(target)
            accepted_output.append(value)
    per_class = {}
    matrix = {}
    for label in classes:
        support = sum(t == label for t in truth)
        accepted = sum(t == label and p is not None for t,p in zip(truth,output))
        per_class[str(label)] = {'support':support, 'coverage': accepted/support if support else None}
        matrix[str(label)] = {str(pred):sum(t == label and p == pred for t,p in zip(truth,output)) for pred in classes}
        matrix[str(label)]['__no_output__'] = sum(t == label and p is None for t,p in zip(truth,output))
    return {'macro_f1':_macro(accepted_truth, accepted_output, classes),
            'end_to_end_macro_f1':_macro(truth, output, classes),
            'coverage': len(accepted_truth)/len(rows) if rows else 0., 'states':states,
            'per_class':per_class, 'confusion_matrix':matrix}


def evaluate_demo(gold, candidate, baseline, labels_by_field):
    if not gold or set(labels_by_field) != set(FIELDS):
        raise ValueError('nonempty gold and all five field vocabularies required')
    _index(gold)
    candidate, baseline = _index(candidate), _index(baseline)
    counts = {'calibration':0, 'test':0}
    groups = {}
    for row in gold:
        split = row['split']
        if split not in counts:
            raise ValueError('invalid split')
        counts[split] += 1
        if not row.get('target_id'):
            raise ValueError('gold stance target_id required')
        group = row['group_id']
        if not group or (group in groups and groups[group] != split):
            raise ValueError('group leakage between calibration and test')
        groups[group] = split
        for field in FIELDS:
            classes = labels_by_field[field]
            if not classes or None in classes or len(set(classes)) != len(classes) or row['labels'][field] not in classes:
                raise ValueError('invalid gold label or vocabulary')
    test = [row for row in gold if row['split'] == 'test']
    test_ids = {row['post_id'] for row in test}
    if not set(candidate) <= test_ids or not set(baseline) <= test_ids:
        raise ValueError('predictions must only contain independent test IDs')
    fields = {}
    for field in FIELDS:
        classes = labels_by_field[field]
        metrics = _metrics(test, candidate, field, classes)
        reference = _metrics(test, baseline, field, classes)
        common = [row for row in test if candidate.get(row['post_id'], {}).get(field, {}).get('status') == 'accepted'
                  and baseline.get(row['post_id'], {}).get(field, {}).get('status') == 'accepted']
        paired_candidate = _metrics(common, candidate, field, classes)['macro_f1']
        paired_baseline = _metrics(common, baseline, field, classes)['macro_f1']
        score, base = metrics['macro_f1'], reference['macro_f1']
        loss = base-score if base is not None and score is not None else None
        baseline_complete = reference['states']['missing'] == 0 and reference['states']['failed'] == 0
        fields[field] = {**metrics, 'baseline': reference, 'baseline_minus_candidate': loss,
                         'baseline_complete': baseline_complete,
                         'paired': {'count':len(common), 'candidate_macro_f1':paired_candidate, 'baseline_macro_f1':paired_baseline},
                         'passed': baseline_complete and score is not None and score >= .80 - COMPARISON_TOLERANCE
                         and metrics['coverage'] >= .85 - COMPARISON_TOLERANCE
                         and loss is not None and loss <= .03 + COMPARISON_TOLERANCE}
    scale_passed = counts == {'calibration':200,'test':400}
    fingerprint = hashlib.sha256(json.dumps([gold, candidate, baseline, labels_by_field], ensure_ascii=False,
                                           sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {'protocol_version':'demo-v1', 'input_sha256':fingerprint, 'sample_counts':counts,
            'scale_passed':scale_passed, 'fields':fields,
            'passed':scale_passed and all(value['passed'] for value in fields.values()),
            'scope':'provided_demo_test_set_only', 'zero_division':0,
            'comparison_tolerance':COMPARISON_TOLERANCE,
            'production_human_review_required':False}


def main():
    parser = argparse.ArgumentParser(description='Offline demo scoring; never calls a model or asks for production review.')
    parser.add_argument('--gold', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--vocabulary', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
    def annotations(value): return value['annotations'] if isinstance(value, dict) else value
    report = evaluate_demo(read(args.gold), annotations(read(args.candidate)), annotations(read(args.baseline)), read(args.vocabulary))
    from opinion_gateway.dataset_repository import atomic_json
    atomic_json(Path(args.output), report)
    print(json.dumps({'passed':report['passed'], 'scale_passed':report['scale_passed'], 'sample_counts':report['sample_counts']}))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
