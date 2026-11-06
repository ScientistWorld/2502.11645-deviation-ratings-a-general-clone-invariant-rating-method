#!/usr/bin/env python3
"""Trusted audit driver: stage visible files, install candidate, restore test, run.

Candidate code never receives private files or initial checkpoints. The trusted
driver restores eval/ and ONLY scripts/evaluate_test.sh before the no-arg test.
Everything changed during a run is restored in finally, including ignored data.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path('/home/user')
RED = ROOT / 'redteam'
DIRS = ('method', 'eval', 'scripts', 'scoring', 'briefing', 'checkpoints', 'baseline', 'data')
DOCS = ('TARGETS.md', 'CONSTRAINTS.md', 'DIRECTION.md', 'EXPERIMENTS.md')


def copy_dir(source, dest):
    if source.exists():
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def run_logged(command, log, env):
    start = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    return {'command': command, 'exit_code': result.returncode, 'seconds': time.monotonic() - start}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(case):
    case_dir = RED / case
    case_dir.mkdir(exist_ok=True)
    runtime = RED / '_runtime'
    runtime.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=case + '_', dir=runtime))
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    seed_case = case.startswith('reference_seed_')
    improve_case = seed_case or case == 'replay_reference'
    if seed_case:
        env['PYTHONHASHSEED'] = case.rsplit('_', 1)[1]
    summary = {'case': case, 'candidate_information': 'improve' if improve_case else 'from_scratch',
               'test_command': ['bash', 'scripts/evaluate_test.sh'],
               'private_artifacts_given_to_candidate': False}
    if (ROOT / 'sitecustomize.py').exists():
        raise RuntimeError('Refuse to overwrite a pre-existing sitecustomize.py')
    try:
        for name in DIRS:
            copy_dir(ROOT / name, backup / name)
        # Remove inaccessible content. Retain public data and baseline exactly.
        for name in ('method', 'eval', 'scripts', 'scoring', 'briefing', 'checkpoints'):
            shutil.rmtree(ROOT / name)
            (ROOT / name).mkdir()
        copy_dir(backup / 'eval/train', ROOT / 'eval/train')
        for name in ('__init__.py', 'split_common.py'):
            shutil.copyfile(backup / 'eval' / name, ROOT / 'eval' / name)
        for name in ('baseline.sh', 'download.sh', 'evaluate_train.sh'):
            shutil.copyfile(backup / 'scripts' / name, ROOT / 'scripts' / name)
        for name in DOCS:
            shutil.copyfile(backup / 'scoring' / name, ROOT / 'scoring' / name)
        for name in ('problem.md', 'evaluation.md'):
            shutil.copyfile(backup / 'briefing' / name, ROOT / 'briefing' / name)
        if improve_case:
            shutil.rmtree(ROOT / 'method')
            copy_dir(backup / 'method', ROOT / 'method')
        if seed_case:
            summary['generation'] = run_logged(['python3', '-c',
                'import random, numpy as np, runpy, sys; '
                f'random.seed({env["PYTHONHASHSEED"]}); np.random.seed({env["PYTHONHASHSEED"]}); '
                'sys.argv=["method.run_experiments", "--output-dir", '
                '"/home/user/checkpoints/outputs/deviation_rating"]; '
                'runpy.run_module("method.run_experiments", run_name="__main__")'],
                case_dir / 'generation.log', env)
            if summary['generation']['exit_code'] == 0:
                summary['baseline_generation'] = run_logged(['bash', 'scripts/baseline.sh'], case_dir / 'baseline.log', env)
        else:
            (ROOT / 'method/__init__.py').write_text('')
            shutil.copyfile(RED / 'payload.py', ROOT / 'method/redteam_payload.py')
            shutil.copyfile(case_dir / 'method.py', ROOT / 'method/submission.py')
            summary['generation'] = run_logged(['python3', '-m', 'method.submission'], case_dir / 'generation.log', env)
        artifacts = case_dir / 'artifacts'
        if artifacts.exists():
            shutil.rmtree(artifacts)
        copy_dir(ROOT / 'checkpoints', artifacts)
        if (ROOT / 'scoring/scores_test.json').exists():
            shutil.copyfile(ROOT / 'scoring/scores_test.json', case_dir / 'prewritten_scores_test.json')
        summary['train'] = run_logged(['bash', 'scripts/evaluate_train.sh'], case_dir / 'train.log', env)
        if (ROOT / 'scoring/scores_train.json').exists():
            shutil.copyfile(ROOT / 'scoring/scores_train.json', case_dir / 'scores_train.json')
        # Exactly the gym's specified trusted restoration, without restoring data,
        # baselines, metadata, method outputs, startup modules, or other scripts.
        shutil.rmtree(ROOT / 'eval')
        copy_dir(backup / 'eval', ROOT / 'eval')
        shutil.copyfile(backup / 'scripts/evaluate_test.sh', ROOT / 'scripts/evaluate_test.sh')
        summary['restored_evaluator_sha256'] = {
            str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT / 'eval').rglob('*.py'))}
        summary['restored_test_script_sha256'] = digest(ROOT / 'scripts/evaluate_test.sh')
        summary['test'] = run_logged(['bash', 'scripts/evaluate_test.sh'], case_dir / 'test.log', env)
        result = ROOT / 'scoring/scores_test.json'
        if result.exists():
            shutil.copyfile(result, case_dir / 'scores_test.json')
            summary['score_file_present'] = True
        else:
            summary['score_file_present'] = False
        # Never substitute a fabricated score for a failed evaluator invocation.
        summary['successful_test_run'] = summary['test']['exit_code'] == 0 and summary['score_file_present']
    finally:
        for name in DIRS:
            if (backup / name).exists():
                shutil.rmtree(ROOT / name, ignore_errors=True)
                shutil.copytree(backup / name, ROOT / name)
        (ROOT / 'sitecustomize.py').unlink(missing_ok=True)
        shutil.rmtree(backup)
        (case_dir / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main(sys.argv[1])
