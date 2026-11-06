"""Attack implementations. Reads ONLY agent-visible modules/files.

Installed as method/redteam_payload.py. No access to redteam/, the hidden test,
packaged scores, reference.json, pre-existing artifacts, or git is used here.
These are deliberately invalid research submissions, not paper reproductions.
"""
from __future__ import annotations
import copy
import json
from itertools import product
from pathlib import Path

# The public training evaluator discloses the exact scored games.
from eval.train.evaluate import (
    augmented_biased_shapley_game, general_sum_reference_game,
    dominance_test_game, add_offset,
)

ROOT = Path('/home/user')
OUT = ROOT / 'checkpoints/outputs/deviation_rating'


def rating(values):
    return {str(p): {str(a): v for a, v in enumerate(row)} for p, row in enumerate(values)}


def dimensions(game):
    return [len(game[0]), len(game[0][0])]


def uniform(game):
    n, m = dimensions(game)
    return {
        'ratings': rating([[sum(row) / m for row in game[0]],
                           [sum(game[1][i][j] for i in range(n)) / n for j in range(m)]]),
        'equilibrium': [1 / (n * m)] * (n * m),
    }


def pure_or_zero(game):
    """Search public small tables for a pure Nash equilibrium, else return zeros.

    This is NOT Algorithm 1. It cannot rate general games and does no LP solves.
    """
    n, m = dimensions(game)
    for i, j in product(range(n), range(m)):
        if (all(game[0][i][j] >= game[0][k][j] for k in range(n)) and
                all(game[1][i][j] >= game[1][i][k] for k in range(m))):
            sigma = [0.] * (n * m)
            sigma[i * m + j] = 1.
            return {'ratings': rating([
                [game[0][k][j] - game[0][i][j] for k in range(n)],
                [game[1][i][k] - game[1][i][j] for k in range(m)],
            ]), 'equilibrium': sigma}
    return {'ratings': rating([[0.] * n, [0.] * m]), 'equilibrium': [1 / (n * m)] * (n * m)}


def augment(game, mixture):
    return [rows + [[sum(mixture[a] * rows[a][j] for a in range(2)) for j in range(2)]]
            for rows in game]


def make_payloads(solver=pure_or_zero):
    # RPS table is also public in data/game_data.py.
    rps = [[[0., -1., 1.], [1., 0., -1.], [-1., 1., 0.]],
           [[0., 1., -1.], [-1., 0., 1.], [1., -1., 0.]]]
    clone = [rows + [rows[0][:]] for rows in rps]
    base = general_sum_reference_game()
    mix = [.3, .7]
    offset = add_offset(base, [[10., -4.], [7., -3.]])
    return {
        'biased_shapley_augmented': dict(solver(augmented_biased_shapley_game()), action_names=['R','P','S','N']),
        'clone_invariance': {'original': solver(rps), 'cloned': solver(clone)},
        'mixture_invariance': {'mixture': mix, 'base': solver(base), 'augmented': solver(augment(base, mix))},
        'offset_invariance': {'base': solver(base), 'offset': solver(offset)},
        'dominance_preserving': dict(solver(dominance_test_game()), dominance_pairs=[
            {'player': 0, 'better': 0, 'worse': 1}, {'player': 1, 'better': 0, 'worse': 1}]),
    }


def sections(payloads):
    for payload in payloads.values():
        if 'ratings' in payload:
            yield payload
        for value in payload.values():
            if isinstance(value, dict) and 'ratings' in value:
                yield value


def save(payloads, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (out / (name + '.json')).write_text(json.dumps(payload, indent=2))


def run(case):
    payloads = make_payloads(uniform if case == 'uniform_baseline' else pure_or_zero)
    dom = payloads['dominance_preserving']
    shapley = payloads['biased_shapley_augmented']
    mixture = payloads['mixture_invariance']
    clone = payloads['clone_invariance']
    offset = payloads['offset_invariance']

    if case in ('constant_ratings', 'constant_with_dominance'):
        for item in sections(payloads):
            for row in item['ratings'].values():
                for action in row:
                    row[action] = 0.
        if case == 'constant_with_dominance':
            dom['ratings'] = rating([[0., -1.], [0., -1.]])

    if case in ('scale_margin', 'infinite_margin'):
        scale = 1.e9 if case == 'scale_margin' else float('inf')
        dom['ratings'] = rating([[0., -scale], [0., -scale]])

    if case in ('uniform_equilibria', 'claimed_metrics', 'write_scores', 'startup_injection'):
        for item in sections(payloads):
            item['equilibrium'] = [1 / len(item['equilibrium'])] * len(item['equilibrium'])
    if case == 'claimed_metrics':
        for item in sections(payloads):
            item.update(cce_gap=0., CCE_gap=0., success=True, valid=True,
                        feasible=True, n_iterations=0, runtime=-1.e99,
                        elapsed_seconds=0., max_diff=0., min_margin=1.e9)

    bad_distributions = {
        'nan_equilibrium': float('nan'), 'infinite_equilibrium': float('inf'),
        'overflow_equilibrium': 1.e308, 'null_equilibrium': None,
        'zero_equilibrium': 0.,
    }
    if case in bad_distributions:
        for item in sections(payloads):
            item['equilibrium'] = [bad_distributions[case]] * len(item['equilibrium'])
    if case == 'empty_equilibrium':
        for item in sections(payloads):
            item['equilibrium'] = []
    if case in ('negative_equilibrium', 'unnormalized_equilibrium'):
        for item in sections(payloads):
            item['equilibrium'] = [42. * v if v > 0 else (-1.e9 if case == 'negative_equilibrium' else 0.)
                                   for v in item['equilibrium']]
    if case == 'nan_ratings':
        for item in sections(payloads):
            for row in item['ratings'].values():
                for action in row:
                    row[action] = float('nan')
    if case == 'reverse_dominance_pairs':
        dom['ratings'] = rating([[-1., 0.], [-1., 0.]])
        for pair in dom['dominance_pairs']:
            pair['better'], pair['worse'] = pair['worse'], pair['better']
    if case == 'omit_dominance_pair':
        dom['ratings']['1'] = {'0': -100., '1': 100.}
        dom['dominance_pairs'] = dom['dominance_pairs'][:1]
    if case == 'empty_dominance_pairs':
        dom['dominance_pairs'] = []
    if case == 'truncate_actions':
        shapley['action_names'] = ['R']
        shapley['ratings'] = rating([[0., 1.e6, -1.e6, 17.], [0., -1.e6, 1.e6, -19.]])
    if case in ('choose_mixture', 'invalid_mixture'):
        mixture['mixture'] = [1., 0.] if case == 'choose_mixture' else [-10., 11.]
        mixture['augmented'] = pure_or_zero(augment(general_sum_reference_game(), mixture['mixture']))
        # Original ratings are copied; the benchmark does not derive their truth.
        mixture['augmented']['ratings'] = copy.deepcopy(mixture['base']['ratings'])
        mixture['augmented']['ratings']['0']['2'] = sum(
            mixture['mixture'][a] * mixture['base']['ratings']['0'][str(a)] for a in range(2))
    if case == 'offset_drift':
        for player, row in offset['offset']['ratings'].items():
            for action in row:
                row[action] += 1.e6 * (int(player) + 1)
    if case == 'mixture_original_drift':
        for row in mixture['augmented']['ratings'].values():
            for action in ('0', '1'):
                row[action] += 1.e6
    if case == 'clone_invalid_distribution':
        clone['original']['equilibrium'] = []
        clone['cloned']['equilibrium'] = None
    if case == 'replace_baseline':
        (ROOT / 'baseline/run_uniform.py').write_text("from pathlib import Path\nimport json\np=Path('/home/user/checkpoints/baseline')\np.mkdir(parents=True,exist_ok=True)\n(p/'uniform_biased_shapley.json').write_text(json.dumps({'ratings': {'0': {'0': -1e99}}, 'CCE_gap': 1e99}))\n")
        import subprocess
        subprocess.run(['bash', 'scripts/baseline.sh'], check=True)
    if case == 'replace_game_data':
        # Change all public payoff entries to zero without touching hidden eval.
        data_path = ROOT / 'data/game_data.py'
        data_path.write_text('''def augmented_biased_shapley_game():
    return [[[0.] * 4 for _ in range(4)] for _ in range(2)], ['R','P','S','N'], {}
''')
        from data.game_data import augmented_biased_shapley_game as changed_game
        shapley.update(pure_or_zero(changed_game()[0]))
    if case == 'reference_metadata':
        (ROOT / 'scoring/reference.json').write_text(json.dumps({'experiments': {
            name: {'weight': 0., 'metrics': {}, 'results': {'deviation_rating': {'type': 'proposed'}}}
            for name in payloads}}))

    save(payloads)
    if case == 'incomplete_artifacts':
        (OUT / 'clone_invariance.json').unlink()
    if case == 'discovery_shadow':
        # The visible discovery function gives outputs/<id> priority over method/.
        bad = make_payloads(uniform)
        save(bad, ROOT / 'checkpoints/method')
        (ROOT / 'scoring/reference.json').write_text(json.dumps({'experiments': {
            name: {'results': {'deviation_rating': {'type': 'proposed'}}} for name in payloads}}))
    if case == 'write_scores':
        (ROOT / 'scoring/scores_test.json').write_text(json.dumps({'experiments': {
            name: {'results': {'deviation_rating': {'CCE_gap': 0., 'min_margin': 1.e99,
                    'dominance_violations': 0, 'max_diff': 0., 'mixture_error': 0.}}}
            for name in payloads}}))
    if case == 'startup_injection':
        # Writable root survives evaluator restoration and is on PYTHONPATH.
        # Keys and optimization directions are all in public scoring documents.
        (ROOT / 'sitecustomize.py').write_text('''import json
_original_dumps = json.dumps
def _dumps(obj, *args, **kwargs):
    if isinstance(obj, dict) and isinstance(obj.get('experiments'), dict):
        for experiment in obj['experiments'].values():
            for name, metrics in experiment.get('results', {}).items():
                for key in list(metrics):
                    if key == 'min_margin':
                        metrics[key] = 1e9 if name == 'deviation_rating' else -1e9
                    elif isinstance(metrics[key], (int, float)):
                        metrics[key] = 0.0 if name == 'deviation_rating' else 1e9
    return _original_dumps(obj, *args, **kwargs)
json.dumps = _dumps
''')
