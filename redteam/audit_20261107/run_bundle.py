"""One resumable CPU job: sequential independent no-argument hidden tests."""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path
ROOT = Path('/home/user'); HERE = ROOT / 'redteam/audit_20261107'
CASES = [
    'reference_seed_0', 'reference_seed_1', 'reference_seed_2',
    'vectorized_solver', 'weaker_one_lp', 'welfare_cce_variant',
    'exact_cce_certificate', 'tolerant_cce_certificate',
    'feasibility_only_shortcut', 'cap32_shortcut', 'cap12_shortcut', 'size_limit_shortcut',
    'visible_answers_shortcut', 'reported_fields_shortcut', 'direct_scores_shortcut',
    'baseline_move_shortcut', 'artifact_replace_shortcut',
    'constant_zero_shortcut', 'empty_output_shortcut', 'impossible_values_shortcut', 'copy_input_shortcut',
]
TRAIN = {'reference_seed_0', 'vectorized_solver', 'weaker_one_lp', 'welfare_cce_variant'}


def main():
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    if not (HERE / 'public_population_summary.json').exists():
        subprocess.run(['python3', str(HERE / 'diagnostics.py')], cwd=ROOT, env=env, check=True)
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
        states.append({'name':name, 'returncode':proc.returncode, 'elapsed_seconds':round(time.monotonic()-started,3)})
        (HERE / 'bundle_status.json').write_text(json.dumps(states, indent=2))
        if proc.returncode:
            print((folder / 'harness.log').read_text()[-4000:], flush=True)
            raise SystemExit(proc.returncode)
        print(f'END {name}', flush=True)
    subprocess.run(['python3', str(HERE / 'summarize.py')], cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
