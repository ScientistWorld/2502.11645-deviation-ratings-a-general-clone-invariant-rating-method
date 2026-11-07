"""Rank of every replay against the reference, with the coefficients and weights of scoring/reference.json.

rank = sum_experiment weight * sum_metric coefficient * (candidate - reference), on
scores_test.json (and scores_train.json where present). Also paired per-instance
statistics for the noisy-redundancy experiment, recomputed from the hidden test's
own diagnostics file when available.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path('/home/user'); HERE = ROOT / 'redteam/hardening_iter14'
SPEC = json.loads((ROOT / 'scoring/reference.json').read_text())['experiments']


def proposed(scores):
    return {e: scores['experiments'][e]['results']['deviation_rating'] for e in SPEC}


def rank(values, reference):
    return sum(spec['weight'] * sum(meta['coefficient'] * (values[e][m] - reference[e][m])
                                   for m, meta in spec['metrics'].items()) for e, spec in SPEC.items())


def per_experiment(values, reference):
    return {e: spec['weight'] * sum(meta['coefficient'] * (values[e][m] - reference[e][m])
                                    for m, meta in spec['metrics'].items()) for e, spec in SPEC.items()}


def main():
    out = {'formula': 'sum_experiment weight * sum_metric coefficient * (candidate - reference seed 0)', 'splits': {}}
    for split in ('test', 'train'):
        ref_file = HERE / 'reference_seed_0' / f'scores_{split}.json'
        if not ref_file.is_file():
            continue
        ref_scores = json.loads(ref_file.read_text())
        reference = proposed(ref_scores)
        cases = {}
        for folder in sorted(HERE.iterdir()):
            f = folder / f'scores_{split}.json'
            if not f.is_file():
                continue
            values = proposed(json.loads(f.read_text()))
            cases[folder.name] = {'rank_delta': rank(values, reference),
                                  'per_experiment': per_experiment(values, reference),
                                  'changed': {e: {m: [reference[e][m], v] for m, v in values[e].items() if v != reference[e][m]}
                                              for e in SPEC if values[e] != reference[e]}}
        baselines = {}
        for e in SPEC:
            for b, row in ref_scores['experiments'][e]['results'].items():
                if b != 'deviation_rating':
                    baselines.setdefault(b, {})[e] = row
        uniform = {e: baselines.get('uniform_payoff', {}).get(e) for e in SPEC}
        out['splits'][split] = {'reference': reference, 'cases': cases,
                                'uniform_rank_delta': rank(uniform, reference) if all(uniform.values()) else None,
                                'baselines': baselines}
        print(split, json.dumps({k: round(v['rank_delta'], 6) for k, v in cases.items()}, indent=1), flush=True)
    (HERE / 'summary.json').write_text(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
