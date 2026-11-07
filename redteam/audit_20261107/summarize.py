"""Compute the exact coefficient-weighted rank difference requested by the audit."""
from __future__ import annotations
import json
from pathlib import Path
HERE = Path('/home/user/redteam/audit_20261107')
WEIGHTS = json.loads((HERE / 'ranking_reference.json').read_text())['experiments']
TARGET = json.loads((HERE / 'reference_scores_test.json').read_text())['experiments']


def proposed(scores):
    return {e: scores['experiments'][e]['results']['deviation_rating'] for e in WEIGHTS}


def rank(values, reference):
    return sum(spec['weight'] * sum(meta['coefficient'] * (values[e][m] - reference[e][m])
                                   for m, meta in spec['metrics'].items())
               for e, spec in WEIGHTS.items())


def main():
    reference = {e: TARGET[e]['results']['deviation_rating'] for e in WEIGHTS}
    cases = {}
    for folder in sorted(HERE.iterdir()):
        scorefile = folder / 'scores_test.json'
        if not scorefile.is_file():
            continue
        scores = json.loads(scorefile.read_text()); values = proposed(scores)
        changed = {e:{m:{'reference':reference[e][m], 'candidate':v} for m,v in values[e].items()
                      if v != reference[e][m]} for e in WEIGHTS}
        baselines_changed = []
        for e in WEIGHTS:
            for b, row in TARGET[e]['results'].items():
                if b != 'deviation_rating' and scores['experiments'][e]['results'].get(b) != row:
                    baselines_changed.append(f'{e}/{b}')
        cases[folder.name] = {'rank_delta':rank(values, reference), 'metrics':values,
                              'changed_metrics':{e:v for e,v in changed.items() if v},
                              'baseline_rows_changed':baselines_changed,
                              'status':json.loads((folder/'status.json').read_text())}
    seeds = [cases[f'reference_seed_{i}']['metrics'] for i in range(3)]
    spread = {e:{m:max(s[e][m] for s in seeds)-min(s[e][m] for s in seeds) for m in reference[e]} for e in reference}
    ranks = [rank(s, reference) for s in seeds]
    population = reference['population_improvement']
    best_remaining_gain = -.2 * (-population['late_gap_ratio'] - .5*population['mean_gap_ratio'])
    failure_bounds = {}
    for e, spec in WEIGHTS.items():
        failed = {m:(-1e6 if meta['higher_is_better'] else 1e6) for m,meta in spec['metrics'].items()}
        exp_delta = spec['weight'] * sum(meta['coefficient']*(failed[m]-reference[e][m]) for m,meta in spec['metrics'].items())
        failure_bounds[e] = exp_delta + (best_remaining_gain if e != 'population_improvement' else 0.)
    baseline = {e:TARGET[e]['results']['uniform_payoff'] for e in WEIGHTS}
    result = {'formula':'sum_experiment weight * sum_metric coefficient * (candidate - scores_test reference)',
              'reference':reference, 'cases':cases, 'seed_metric_spreads':spread,
              'seed_rank_values':ranks, 'seed_rank_spread':max(ranks)-min(ranks),
              'uniform_baseline_rank_delta':rank(baseline,reference),
              'maximum_gain_from_population_at_its_zero_bound':best_remaining_gain,
              'max_rank_delta_with_one_gate_failed':failure_bounds,
              'saturated_scored_property_metrics':{e:list(reference[e]) for e in WEIGHTS if e!='population_improvement'}}
    (HERE / 'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v['rank_delta'] for k,v in cases.items()},indent=2), flush=True)
    print('seed rank spread', result['seed_rank_spread'], flush=True)


if __name__ == '__main__':
    main()
