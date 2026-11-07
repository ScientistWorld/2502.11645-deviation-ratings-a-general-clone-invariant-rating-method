"""Measure a real implementation improvement on public problem instances."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path('/home/user')
sys.path.insert(0, str(ROOT))
from method.deviation_rating import _build_deviation_coefficients, deviation_rating
from redteam.current_audit.rating_program import coefficients

rng = np.random.default_rng(7341)
measurements = []
for dims in ([8, 8], [11, 11, 9], [33, 33]):
    payoffs = rng.normal(size=(len(dims), *dims))
    start = time.perf_counter()
    original = _build_deviation_coefficients(payoffs, len(dims), dims)
    t_original = time.perf_counter() - start
    start = time.perf_counter()
    improved = coefficients(payoffs, len(dims), dims)
    t_improved = time.perf_counter() - start
    equal = bool(np.array_equal(original[0], improved[0]) and np.array_equal(original[1], improved[1]))
    if not equal:
        raise AssertionError('Vectorization changed a coefficient or joint-action index')
    measurements.append({'dims': dims, 'coefficients_bitwise_equal': equal,
                         'reference_seconds': t_original, 'vectorized_seconds': t_improved,
                         'coefficient_speedup': t_original / t_improved})
Path('/home/user/redteam/current_audit/efficiency_check.json').write_text(json.dumps(measurements, indent=2))
print(json.dumps(measurements), flush=True)
