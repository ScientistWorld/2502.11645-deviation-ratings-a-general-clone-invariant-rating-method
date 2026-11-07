"""Heavy job diagnostics: public population identifiability and public witnesses."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path('/home/user'); sys.path.insert(0, str(ROOT))
HERE = ROOT / 'redteam/audit_20261107'
from redteam.audit_20261107.rating_program import reference, candidate, matrix, cce_lp, coefficients
from method.deviation_rating import _build_deviation_coefficients
from eval.protocol import make_pools, PopulationLoop, TRAIN_SEED, _mix, POP_ITERATIONS


def efficiency():
    rng = np.random.default_rng(7341)
    measures = []
    for dims in ([8, 8], [13, 13, 13], [48, 48]):
        pay = rng.normal(size=(len(dims), *dims))
        original = _build_deviation_coefficients(pay, len(dims), dims)
        other = coefficients(pay, len(dims), dims)
        assert np.array_equal(original[0], other[0]) and np.array_equal(original[1], other[1])
        times = [[], []]
        for i in range(7):
            for index in ([0, 1] if i % 2 else [1, 0]):
                fn = [_build_deviation_coefficients, coefficients][index]
                start = time.perf_counter(); fn(pay, len(dims), dims)
                times[index].append(time.perf_counter() - start)
        measures.append({'dims': dims, 'coefficients_bitwise_equal': True,
                         'reference_seconds': times[0], 'vectorized_seconds': times[1],
                         'median_coefficient_speedup': float(np.median(times[0]) / np.median(times[1]))})
    (HERE / 'efficiency.json').write_text(json.dumps(measures, indent=2))


def witnesses():
    from data.game_data import augmented_biased_shapley_game
    from method.deviation_rating import deviation_rating
    base, _, _ = augmented_biased_shapley_game()
    for name in ('cap32_shortcut', 'feasibility_only_shortcut'):
        if name == 'cap32_shortcut':
            pay = np.zeros((3, 4, 4, 40)); pay[:2] = base[..., None]
            pay[2] = -0.01 * np.arange(40)[None, None, :]
        else:
            pay = np.repeat(np.repeat(base, 2, axis=1), 2, axis=2)
        dims = list(pay.shape[1:])
        full = deviation_rating(pay, len(dims), dims)
        expected = reference(pay)
        actual = candidate(pay, name, {})
        folder = HERE / name; folder.mkdir(exist_ok=True)
        (folder / 'witness_input.json').write_text(json.dumps({'games': [{'id':'public_witness','payoffs':pay.tolist()}]}))
        (folder / 'witness_reference_output.json').write_text(json.dumps(expected))
        (folder / 'witness_shortcut_output.json').write_text(json.dumps(actual))
        diff = max(abs(x-y) for xs, ys in zip(expected['ratings'],actual['ratings']) for x, y in zip(xs,ys))
        (folder / 'witness.json').write_text(json.dumps({'dims': dims, 'reference_lp_iterations':full['n_iterations'],
           'max_rating_difference':diff, 'reference_first_player_ratings':expected['ratings'][0],
           'shortcut_first_player_ratings':actual['ratings'][0],
           'shortcut_max_deviation_gain':max(map(max, actual['ratings'])),
           'reference_max_deviation_gain':max(map(max, expected['ratings']))}, indent=2))


def population():
    # Public data only. This trace is not a substitute for the exact hidden test.
    sheriff, pools = make_pools(_mix(TRAIN_SEED, 0x50))
    loop = PopulationLoop(sheriff, pools, _mix(TRAIN_SEED, 0x50))
    records = []
    started = time.monotonic()
    for iteration in range(POP_ITERATIONS):
        rows = []
        for run, game in enumerate(loop.meta_games()):
            pay = np.asarray(game.payload(), dtype=float)
            out = reference(pay, 'vectorized_solver')
            sigma = np.asarray(out['equilibrium'])
            peak = int(np.argmax(sigma))
            objective = np.zeros(len(sigma)); objective[peak] = 1.
            sol = cce_lp(pay, objective)
            records.append({'iteration':iteration, 'run':run, 'largest_mass':float(sigma[peak]),
                            'min_CCE_mass_on_peak':float(sol.fun),
                            'CCE_mass_dual_bound':float(sol.eqlin.marginals[0]),
                            'ratings':out['ratings']})
            rows.append(out['ratings'])
        loop.advance(rows)
        if (iteration+1) % 16 == 0:
            print(f'public population diagnostic {iteration+1}/96, {time.monotonic()-started:.0f}s', flush=True)
            (HERE / 'public_population_trace.json').write_text(json.dumps(records))
    result = {'games':len(records), 'pure_reference_games':sum(r['largest_mass']>1.-1e-8 for r in records),
              'unique_pure_CCE_games':sum(r['largest_mass']>1.-1e-8 and r['CCE_mass_dual_bound']>1.-1e-7 for r in records),
              'population_metrics':loop.metrics(), 'curve':loop.mean_curve(),
              'minimum_dual_mass':min(r['CCE_mass_dual_bound'] for r in records)}
    (HERE / 'public_population_summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    efficiency(); witnesses(); population()
