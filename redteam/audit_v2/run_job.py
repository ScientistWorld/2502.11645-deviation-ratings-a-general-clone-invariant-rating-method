"""Run all shortcut trials; failures are retained and do not suppress other trials."""
import json
import subprocess
from pathlib import Path
ROOT=Path('/home/user')
job=[]
for seed in ('unmodified',101,202,303):
    name='reference_unmodified' if seed=='unmodified' else f'reference_seed_{seed}'
    (ROOT/'redteam'/name).mkdir(exist_ok=True)
    script=ROOT/'redteam'/name/'run.sh'
    script.write_text('#!/bin/bash\nset -euo pipefail\ncd /home/user\nexec python3 redteam/audit_v2/shortcut_harness.py '+name+'\n')
    job.append(name)
from shortcut_harness import NAMES
for name in NAMES:
    (ROOT/'redteam'/name).mkdir(exist_ok=True)
    (ROOT/'redteam'/name/'run.sh').write_text('#!/bin/bash\n# '+name+' installation, method run, hidden test, restoration.\nset -euo pipefail\ncd /home/user\nexec python3 redteam/audit_v2/shortcut_harness.py '+name+'\n')
    job.append(name)
statuses={}
for name in job:
    print('Running '+name,flush=True)
    result=subprocess.run(['bash',f'redteam/{name}/run.sh'],cwd=ROOT)
    statuses[name]=result.returncode
# Rerun all existing shortcuts against the current gym, never reuse old scores.
for name in json.loads((ROOT/'redteam/shortcut_cases.json').read_text()):
    print('Running '+name,flush=True)
    result=subprocess.run(['bash',f'redteam/{name}/run.sh'],cwd=ROOT)
    statuses[name]=result.returncode
(ROOT/'redteam/audit_v2/job_status.json').write_text(json.dumps(statuses,indent=2))
subprocess.run(['python3','redteam/audit_v2/diagnose_shortcuts.py'],cwd=ROOT,check=True)
