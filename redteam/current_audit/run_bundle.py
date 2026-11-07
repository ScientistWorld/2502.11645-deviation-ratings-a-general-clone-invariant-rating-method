"""One CPU job, sequential exact tests, no evaluator/environment modifications."""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path('/home/user')
HERE = ROOT / 'redteam/current_audit'
CASES = [
    'reference_seed_0', 'reference_seed_1', 'reference_seed_2',
    'vectorized_solver', 'precision_solver', 'weaker_one_lp',
    'two_lp_shortcut', 'three_lp_shortcut', 'size_abandonment_shortcut',
    'visible_answers_shortcut', 'reported_fields_shortcut', 'direct_scores_shortcut',
    'baseline_move_shortcut', 'artifact_replace_shortcut', 'constant_ratings_shortcut',
    'empty_output_shortcut', 'nonfinite_shortcut',
]


def main():
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    result = []
    subprocess.run(['python3', str(HERE / 'efficiency_check.py')], cwd=ROOT, env=env, check=True)
    for name in CASES:
        folder = HERE / name
        folder.mkdir(exist_ok=True)
        print(f'START {name}, elapsed={time.monotonic()-started:.0f}s', flush=True)
        command = ['bash', str(folder / 'run.sh')]
        if name in ('reference_seed_0', 'vectorized_solver', 'weaker_one_lp'):
            command.append('--train')
        with (folder / 'harness.log').open('w') as stream:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        result.append({'name': name, 'returncode': proc.returncode, 'elapsed': round(time.monotonic()-started, 2)})
        (HERE / 'bundle_status.json').write_text(json.dumps(result, indent=2))
        print(f'END {name}, returncode={proc.returncode}', flush=True)
        if proc.returncode:
            print((folder / 'harness.log').read_text()[-3000:], flush=True)
            raise SystemExit(proc.returncode)
    print('Audit bundle complete', flush=True)


if __name__ == '__main__':
    main()
