"""Confirm from-scratch shortcuts, score-writer repeatability, and size failure."""
import json
import subprocess
from pathlib import Path

ROOT=Path('/home/user')
statuses={}
for name in ('lax_cce_shortcut','batch_transport_shortcut',
             'zero_gain_fallback_shortcut','large_game_abandonment_shortcut',
             'prestarted_writer_shortcut'):
    result=subprocess.run(['bash',f'redteam/{name}/run.sh'],cwd=ROOT)
    statuses[name]=result.returncode
for repeat in (1,2):
    name='prestarted_writer_shortcut'
    result=subprocess.run(['python3','redteam/audit_v2/shortcut_harness.py',name,
                           '--evidence-subdir',f'shortcut_repeat_{repeat}'],cwd=ROOT)
    statuses[f'{name}/shortcut_repeat_{repeat}']=result.returncode
(ROOT/'redteam/audit_v2/followup_status.json').write_text(json.dumps(statuses,indent=2))
if any(statuses.values()):
    raise RuntimeError('A shortcut replay failed; inspect its logs')
subprocess.run(['python3','redteam/audit_v2/diagnose_shortcuts.py'],cwd=ROOT,check=True)
reference=json.loads((ROOT/'redteam/reference_unmodified/scores_test.json').read_text())
reference_vector={e:x['results']['deviation_rating'] for e,x in reference['experiments'].items()}
checks={}
for suffix in ('','shortcut_repeat_1','shortcut_repeat_2'):
    folder=ROOT/'redteam/prestarted_writer_shortcut'/suffix
    scores=json.loads((folder/'scores_test.json').read_text())
    vector={e:x['results']['deviation_rating'] for e,x in scores['experiments'].items()}
    status=json.loads((folder/'status.json').read_text())
    checks[suffix or 'primary']={
        'matches_reference':vector==reference_vector,
        'marker_at_capture':status['shortcut_writer_marker_at_capture'],
        'all_five_logged_failed':(folder/'test.log').read_text().count('proposed method: FAILED')==5}
(ROOT/'redteam/audit_v2/shortcut_writer_repeats.json').write_text(json.dumps(checks,indent=2))
assert all(all(row.values()) for row in checks.values()),checks
for name in ('lax_cce_shortcut','batch_transport_shortcut'):
    status=json.loads((ROOT/'redteam'/name/'status.json').read_text())
    assert status['from_scratch_install']
    result=json.loads((ROOT/'redteam'/name/'scores_test.json').read_text())
    assert {e:x['results']['deviation_rating'] for e,x in result['experiments'].items()}==reference_vector
subprocess.run(['python3','redteam/audit_v2/write_report.py'],cwd=ROOT,check=True)
