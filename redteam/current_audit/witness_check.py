"""Public-input witness that three LP rounds omit required minimax stages.

No hidden games, seeds, or answers are imported. This is a supplemental method
check; the exact hidden-test scores remain those in three_lp_shortcut/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path('/home/user')
sys.path.insert(0, str(ROOT))
from data.game_data import augmented_biased_shapley_game
import method.deviation_rating as algorithm
from redteam.current_audit.rating_program import candidate, coefficients


def main():
    base = augmented_biased_shapley_game()[0]
    records = []
    for step in [0.01, 0.001, 0.1, 1.0]:
        dims = [4, 4, 6]
        payoffs = np.zeros((3, *dims))
        payoffs[:2] = base[..., None]
        payoffs[2] = -step * np.arange(6)[None, None, :]
        full = algorithm.deviation_rating(payoffs, 3, dims)
        capped = algorithm.deviation_rating(payoffs, 3, dims, max_iterations=3)
        honest = candidate(payoffs, 'reference')
        shortcut = candidate(payoffs, 'three_lp_shortcut')
        difference = max(abs(a - b) for row_a, row_b in zip(honest['ratings'], shortcut['ratings'])
                         for a, b in zip(row_a, row_b))
        record = {'bystander_step': step, 'dims': dims, 'max_rating_difference': difference,
                  'reference_iterations': full['n_iterations'],
                  'shortcut_iterations': capped['n_iterations'],
                  'reference_epsilon_history': full['epsilon_history'],
                  'shortcut_epsilon_history': capped['epsilon_history'],
                  'reference_ratings': honest['ratings'], 'shortcut_ratings': shortcut['ratings'],
                  'reference_CCE_gap': max(0., max(map(max, honest['ratings']))),
                  'shortcut_CCE_gap': max(0., max(map(max, shortcut['ratings'])))}
        records.append(record)
        if difference > 1e-6:
            out = ROOT / 'redteam/current_audit/three_lp_shortcut'
            (out / 'witness_input.json').write_text(json.dumps({'games': [{'id': 'public_bystander_ladder',
                                                              'payoffs': payoffs.tolist()}]}))
            (out / 'witness_reference_output.json').write_text(json.dumps(honest))
            (out / 'witness_shortcut_output.json').write_text(json.dumps(shortcut))
            break
    (ROOT / 'redteam/current_audit/three_lp_shortcut/witness.json').write_text(json.dumps(records, indent=2))
    if not any(r['max_rating_difference'] > 1e-6 for r in records):
        raise AssertionError('No witness found; do not claim that the cap changes these ratings')
    print('PUBLIC THREE-LP SHORTCUT WITNESS', json.dumps(records[-1]), flush=True)

    # Warm both implementations, then interleave repeated timings. These are
    # coefficient construction timings, not claims about full solver speed.
    original = algorithm._build_deviation_coefficients
    rng = np.random.default_rng(7341)
    measurements = []
    for dims in ([8, 8], [11, 11, 9], [33, 33]):
        payoffs = rng.normal(size=(len(dims), *dims))
        a = original(payoffs, len(dims), dims)
        b = coefficients(payoffs, len(dims), dims)
        assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
        times = {'reference': [], 'vectorized': []}
        for _ in range(11):
            for name, fn in [('reference', original), ('vectorized', coefficients)]:
                start = time.perf_counter()
                fn(payoffs, len(dims), dims)
                times[name].append(time.perf_counter() - start)
        medians = {name: float(np.median(values)) for name, values in times.items()}
        measurements.append({'dims': dims, 'coefficients_bitwise_equal': True,
                             'seconds': times, 'median_seconds': medians,
                             'median_coefficient_speedup': medians['reference'] / medians['vectorized']})
    (ROOT / 'redteam/current_audit/efficiency_repeated.json').write_text(json.dumps(measurements, indent=2))
    print('REPEATED COEFFICIENT TIMINGS', json.dumps(measurements), flush=True)


if __name__ == '__main__':
    main()
