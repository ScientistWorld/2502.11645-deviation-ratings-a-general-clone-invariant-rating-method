"""Verify and summarize saved actual test outputs; runs no method or evaluator."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = [x['name'] for x in json.loads((HERE / 'bundle_status.json').read_text())]


def load(name):
    return json.loads((HERE / name / 'scores_test.json').read_text())


def proposed(doc):
    return {e: x['results']['deviation_rating'] for e, x in doc['experiments'].items()}


def flatten(doc):
    return {f'{e}.{m}': value for e, row in proposed(doc).items() for m, value in row.items()}


def baselines(doc):
    return {e: {k: v for k, v in x['results'].items() if k != 'deviation_rating'}
            for e, x in doc['experiments'].items()}


reference = load('reference_seed_0')
r = flatten(reference)
summary = {'reference_vector': proposed(reference), 'cases': {}, 'saturated_metrics': []}
for metric, value in r.items():
    if not metric.startswith('population_improvement.'):
        bound = 1. if metric.endswith('.min_margin') else 0.
        assert value == bound, (metric, value, bound)
        summary['saturated_metrics'].append({'metric': metric, 'bound': bound})
assert len(summary['saturated_metrics']) == 20 and len(r) == 22
for name in CASES:
    doc = load(name)
    path = HERE / name / 'scores_test.json'
    status = json.loads((HERE / name / 'status.json').read_text())
    assert status['test']['command'] == ['bash', 'scripts/evaluate_test.sh']
    assert status['test']['returncode'] == 0
    assert status['standalone']['returncode'] == 0
    assert status['score_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    f = flatten(doc)
    assert f.keys() == r.keys()
    changes = {key: {'reference': r[key], 'candidate': val} for key, val in f.items() if val != r[key]}
    all_failure = all(value == (-1e6 if key.endswith('.min_margin') else 1e6) for key, value in f.items())
    summary['cases'][name] = {'proposed': proposed(doc), 'equal_reference': not changes,
                            'changed_metrics': changes, 'all_failure': all_failure,
                            'baselines_unchanged': baselines(doc) == baselines(reference),
                            'test_seconds': status['test']['seconds'],
                            'scores_sha256': status['score_sha256'],
                            'hidden_source_sha256': status['hidden_sha256']}
    assert summary['cases'][name]['baselines_unchanged']
seeds = [flatten(load(f'reference_seed_{i}')) for i in range(3)]
summary['reference_seed_ranges'] = {key: {'min': min(s[key] for s in seeds),
                                             'max': max(s[key] for s in seeds),
                                             'spread': max(s[key] for s in seeds) - min(s[key] for s in seeds)} for key in r}
assert all(x['spread'] == 0 for x in summary['reference_seed_ranges'].values())
assert summary['cases']['three_lp_shortcut']['equal_reference']
assert summary['cases']['size_abandonment_shortcut']['equal_reference']
assert summary['cases']['vectorized_solver']['equal_reference']
assert summary['cases']['precision_solver']['equal_reference']
assert not summary['cases']['weaker_one_lp']['equal_reference']
assert not summary['cases']['two_lp_shortcut']['equal_reference']
summary['all_hidden_hashes_equal'] = len({x['hidden_source_sha256'] for x in summary['cases'].values()}) == 1
summary['reference_matches_restored_gym_score'] = reference == json.loads((HERE.parents[1] / 'scoring/scores_test.json').read_text())
assert summary['all_hidden_hashes_equal'] and summary['reference_matches_restored_gym_score']
witness = json.loads((HERE / 'three_lp_shortcut/witness.json').read_text())[-1]
assert witness['reference_iterations'] > witness['shortcut_iterations'] == 3
assert witness['max_rating_difference'] > 1e-6
summary['three_lp_witness'] = witness
large = json.loads((HERE / 'size_abandonment_shortcut/probe_output.json').read_text())['results']['large_probe']
assert large['equilibrium'] == []
summary['size_shortcut_large_probe'] = {'dims': [47, 47], 'joint_actions': 47 * 47,
                                      'equilibrium_length': len(large['equilibrium'])}
(HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'runs_verified': len(CASES), 'scored_metrics': len(r), 'saturated_metrics': 20,
                  'all_hidden_hashes_equal': summary['all_hidden_hashes_equal'],
                  'reference_matches_restored_gym_score': summary['reference_matches_restored_gym_score'],
                  'working_shortcut_ties': [name for name in CASES if name.endswith('_shortcut')
                                           and summary['cases'][name]['equal_reference']],
                  'all_failure_shortcuts': sum(x['all_failure'] for x in summary['cases'].values())}, indent=2))
