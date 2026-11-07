"""Iteration-14 hardening replays: sequential, resumable, each an unchanged no-argument hidden test.

Cases: the reference (seed 0, and seed 1 with every game's action labels permuted
before solving), the better variant (merging near-copies within the noise bound),
the weaker one-LP ablation, and the shortcuts this iteration fixed (32-round cap,
abandoning games above 4,096 joint actions) plus the new noise-bound gate.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path
ROOT = Path('/home/user'); HERE = ROOT / 'redteam/hardening_iter14'
CASES = ['reference_seed_0', 'merge_variant', 'weaker_one_lp', 'cap32_shortcut', 'size_limit_shortcut',
         'band_violation_shortcut', 'reference_seed_1']
TRAIN = {'reference_seed_0', 'merge_variant', 'weaker_one_lp'}


def main():
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    states = []
    for name in CASES:
        folder = HERE / name
        if (folder / 'status.json').exists() and (folder / 'scores_test.json').exists():
            state = json.loads((folder / 'status.json').read_text())
            if not state.get('harness_error'):
                print(f'SKIP completed {name}', flush=True)
                continue
        print(f'START {name}, elapsed={time.monotonic()-started:.0f}s', flush=True)
        command = ['bash', str(folder / 'run.sh')]
        if name in TRAIN:
            command.append('--train')
        with (folder / 'harness.log').open('w') as stream:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        states.append({'name': name, 'returncode': proc.returncode, 'elapsed_seconds': round(time.monotonic() - started, 3)})
        (HERE / 'bundle_status.json').write_text(json.dumps(states, indent=2))
        print(f'END {name} rc={proc.returncode}', flush=True)
        if proc.returncode:
            print((folder / 'harness.log').read_text()[-3000:], flush=True)
    subprocess.run(['python3', str(HERE / 'summarize.py')], cwd=ROOT, env=env, check=False)


if __name__ == '__main__':
    main()
