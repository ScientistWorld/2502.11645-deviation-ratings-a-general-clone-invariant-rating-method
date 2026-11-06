#!/usr/bin/env python3
"""Replay shortcuts transactionally, restoring the gym evaluator before hidden test.

Only this audit harness reads hidden score outputs. Shortcut producers do not.
No rank formula is assumed: the unmodified test's complete JSON is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path('/home/user')
STATE = ROOT / 'redteam/_restore_state'
DIRECTORIES = ['eval', 'data', 'baseline', 'method', 'scoring', 'checkpoints']
FILES = ['scripts/evaluate_test.sh', 'sitecustomize.py']


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def snapshot():
    if STATE.exists():
        raise RuntimeError('Unrestored shortcut state exists; refusing to overwrite backups')
    STATE.mkdir(parents=True)
    present = []
    for rel in DIRECTORIES + FILES:
        source, target = ROOT / rel, STATE / rel
        if source.exists():
            present.append(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    (STATE / 'present.json').write_text(json.dumps(present))


def restore_one(rel):
    source, target = STATE / rel, ROOT / rel
    remove(target)
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def restore_all():
    if STATE.exists():
        for rel in DIRECTORIES + FILES:
            restore_one(rel)
        # Python may cache the temporary startup shortcut after the source is gone.
        cache = ROOT / '__pycache__'
        if cache.exists():
            for file in cache.glob('sitecustomize.*.pyc'):
                file.unlink()
            if not list(cache.iterdir()):
                cache.rmdir()
        shutil.rmtree(STATE)


def run(command, output):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    start = time.monotonic()
    with output.open('w') as log:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=240)
    return {'exit_code': completed.returncode, 'seconds': time.monotonic() - start}


def nonfinite(obj, prefix=''):
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.extend(nonfinite(value, prefix + '.' + key))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            found.extend(nonfinite(value, prefix + f'[{idx}]'))
    elif isinstance(obj, float) and not math.isfinite(obj):
        found.append(prefix)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shortcut')
    parser.add_argument('--reference-seed', type=int)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if args.restore:
        restore_all()
        return
    is_reference = args.reference_seed is not None
    folder = ROOT / 'redteam' / ('reference_seeds/seed_' + str(args.reference_seed)
                                if is_reference else args.shortcut)
    folder.mkdir(parents=True, exist_ok=True)
    status = {'shortcut': args.shortcut, 'reference_seed': args.reference_seed,
              'hidden_command': ['bash', 'scripts/evaluate_test.sh']}
    snapshot()
    try:
        for split in ('train', 'test'):
            (ROOT / f'scoring/scores_{split}.json').unlink(missing_ok=True)
        # Existing checkpoints are not among the future agent's provided files.
        remove(ROOT / 'checkpoints')
        (ROOT / 'checkpoints').mkdir()
        if is_reference:
            seed = args.reference_seed
            code = (f'import random, numpy as np; random.seed({seed}); np.random.seed({seed}); '
                    'from method.run_experiments import main; main(); '
                    'from baseline.run_uniform import main as baseline_main; baseline_main()')
            command = ['python3', '-c', code]
        else:
            command = ['python3', 'redteam/shortcut_candidate.py', args.shortcut]
        status['producer'] = run(command, folder / 'producer.log')
        if status['producer']['exit_code'] != 0:
            return
        shutil.copytree(ROOT / 'checkpoints', folder / 'submitted_artifacts', dirs_exist_ok=True)
        # Retain edits as evidence in the shortcut's own folder.
        edited = {}
        for rel in FILES + ['data/game_data.py', 'baseline/run_uniform.py', 'scoring/reference.json']:
            before, after = STATE / rel, ROOT / rel
            if after.exists() and (not before.exists() or before.read_bytes() != after.read_bytes()):
                target = folder / 'installed_files' / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(after, target)
                edited[rel] = hashlib.sha256(after.read_bytes()).hexdigest()
        status['edited_files'] = edited
        status['train'] = run(['bash', 'scripts/evaluate_train.sh'], folder / 'train.log')
        path = ROOT / 'scoring/scores_train.json'
        if path.exists():
            shutil.copy2(path, folder / 'scores_train.json')
        # Exactly the stated finalization: gym eval and test script come back;
        # all candidate edits in other paths remain for test execution.
        restore_one('eval')
        restore_one('scripts/evaluate_test.sh')
        before_test = hashlib.sha256((ROOT / 'eval/test/evaluate.py').read_bytes()).hexdigest()
        status['restored_hidden_sha256'] = before_test
        status['test'] = run(['bash', 'scripts/evaluate_test.sh'], folder / 'test.log')
        path = ROOT / 'scoring/scores_test.json'
        if path.exists():
            shutil.copy2(path, folder / 'scores_test.json')
            status['nonfinite_test_fields'] = nonfinite(json.loads(path.read_text()))
        else:
            status['nonfinite_test_fields'] = []
        status['scores_produced'] = path.exists()
    except Exception as error:
        status['harness_error'] = repr(error)
        raise
    finally:
        (folder / 'status.json').write_text(json.dumps(status, indent=2))
        restore_all()
    print(json.dumps({'shortcut': args.shortcut, 'seed': args.reference_seed,
                      'train': status.get('train', {}).get('exit_code'),
                      'test': status.get('test', {}).get('exit_code'),
                      'nonfinite': len(status.get('nonfinite_test_fields', []))}))


if __name__ == '__main__':
    main()
