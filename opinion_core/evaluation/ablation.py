"""Post-implementation comparison of supplied real text/image/multimodal predictions."""
from .demo import evaluate_demo


def evaluate_ablation(gold, predictions, baseline, vocabulary):
    if set(predictions)!={'text_only','image_only','text_image'}:
        raise ValueError('all three modality runs are required')
    reports={mode:evaluate_demo(gold,rows,baseline,vocabulary) for mode,rows in predictions.items()}
    differences={field:{'f1_gain':reports['text_image']['fields'][field]['macro_f1']-reports['text_only']['fields'][field]['macro_f1']
                 if reports['text_image']['fields'][field]['macro_f1'] is not None and reports['text_only']['fields'][field]['macro_f1'] is not None else None,
                 'coverage_gain':reports['text_image']['fields'][field]['coverage']-reports['text_only']['fields'][field]['coverage']}
                 for field in vocabulary}
    return {'reports':reports,'text_image_minus_text':differences,'scope':'provided_gold_only',
            'cost_comparison':'join provider ledgers for the corresponding fixed modality runs'}
