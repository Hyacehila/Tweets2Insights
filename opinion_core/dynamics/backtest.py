"""Rolling-origin diagnostics, explicitly conditional on the supplied label provenance."""
from datetime import datetime
import numpy as np
from .engine import fit_assimilate, forecast
from opinion_core.schemas.workflow import ModelSpec


def rolling_backtest(observations, config, check_cancel=lambda:None):
    config = ModelSpec.model_validate(config)
    windows = [w for w in observations['windows'] if datetime.fromisoformat(w['end']) <= config.training_cutoff]
    scores = []
    for i in range(1,len(windows)):
        check_cancel()
        prior, actual = windows[i-1], windows[i]
        if not prior['joint_n'] or not actual['joint_n']:
            continue
        candidate = config.model_copy(update={'training_cutoff':datetime.fromisoformat(prior['end']),'horizon':1})
        predictions = {}
        for algorithm in ('joint_hk_enkf','coordinate_hk_enkf','hk_without_assimilation'):
            state = fit_assimilate(observations,candidate.model_copy(update={'algorithm':algorithm}),check_cancel)
            predictions[algorithm] = forecast(state,check_cancel=check_cancel)['steps'][0]['fields']
        for field in ('sentiment','stance'):
            truth = np.asarray(actual['fields'][field]['mass'])
            persistence = np.asarray(prior['fields'][field]['mass'])
            linear = persistence.copy()
            if i >= 2 and windows[i-2]['fields'][field]['mass'] is not None:
                linear = np.maximum(2*persistence-np.asarray(windows[i-2]['fields'][field]['mass']),0)
                linear /= linear.sum()
            masses = {name:np.asarray(result[field]['mass']) for name,result in predictions.items()}
            masses.update(persistence=persistence,linear_distribution=linear)
            for name,mass in masses.items():
                scores.append({'origin':prior['end'],'target':actual['end'],'field':field,'model':name,
                               'wasserstein_binned':float(np.abs(np.cumsum(mass)-np.cumsum(truth)).sum()*2/len(truth)),
                               'l1':float(np.abs(mass-truth).sum()),'n':actual['fields'][field]['valid_n']})
    return {'scores':scores,'origin_count':len({s['origin'] for s in scores}),
            'historical_availability_verified':observations['historical_availability_verified'],
            'scope':'rolling diagnostics on supplied labels; historical availability requires separate evidence',
            'validation_status':'not_scientifically_validated'}
