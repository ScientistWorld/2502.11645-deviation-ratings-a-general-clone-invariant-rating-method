"""Lightweight saved-evidence and workspace verification; no method execution."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT = Path('/home/user')
HERE = ROOT/'redteam/audit_20261107'
BASE = (HERE/'base_commit.txt').read_text().strip()
s = json.loads((HERE/'summary.json').read_text())
assert len(s['cases']) == 21
sha = hashlib.sha256((ROOT/'eval/test/evaluate.py').read_bytes()).hexdigest()
for name, c in s['cases'].items():
    assert c['status']['test']['command'] == ['bash','scripts/evaluate_test.sh'], name
    assert c['status']['test']['returncode'] == 0, name
    assert c['status']['hidden_sha256'] == sha, name
    assert not c['status'].get('harness_error'), name
    assert sum(map(len,c['metrics'].values())) == 22, name
    assert not c['baseline_rows_changed'], name
    assert 'stopped 0 leftover process(es)' in (HERE/name/'test.log').read_text(), name
    assert (HERE/name/'run.sh').is_file(), name
assert s['seed_rank_spread'] == 0
for name in ['cap32_shortcut','size_limit_shortcut','vectorized_solver']:
    assert not s['cases'][name]['changed_metrics'], name
probe=json.loads((HERE/'cap32_shortcut/probe_output.json').read_text())['results']['public_witness']
witness=json.loads((HERE/'cap32_shortcut/witness_shortcut_output.json').read_text())
assert probe == witness
assert json.loads((HERE/'size_limit_shortcut/probe_output.json').read_text())['results']['large_probe']['equilibrium'] == []

def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True).strip()
index_paths = command('git','diff','--cached','--name-only',BASE).splitlines()
index_unexpected = [p for p in index_paths if not (p.startswith('redteam/') or p in ('REDTEAM.md','action.yaml'))]
assert not index_unexpected,index_unexpected
worktree_paths=command('git','diff',BASE,'--name-only').splitlines()
external_masks=['README.md','manifest.json'] + command('git','ls-tree','-r','--name-only',BASE,'trajectory').splitlines()
unexpected=[p for p in worktree_paths if not (p.startswith('redteam/') or p in ('REDTEAM.md','action.yaml') or p in external_masks)]
assert not unexpected,unexpected
for p in external_masks:
    assert command('git','rev-parse',':'+p) == command('git','rev-parse',BASE+':'+p),p
result={'base_commit':BASE,'completed_hidden_tests':21,'explicit_shortcuts':13,'scored_metrics_per_test':22,
        'test_sha256':sha,'seed_rank_spread':0,'all_baseline_rows_unchanged':True,
        'cap32_standalone_witness_replayed_exactly':True,'size_limit_standalone_empty_equilibrium_verified':True,
        'unexpected_index_changes_outside_audit':index_unexpected,
        'unexpected_workspace_changes_outside_audit':unexpected,
        'required_control_file_exception':'action.yaml completion signal',
        'external_readonly_masks':external_masks,
        'external_masks_original_git_blobs_in_index':True,
        'restoration_error':'README.md and manifest.json are /dev/null read-only mounts; trajectory is an empty read-only mount. git restore cannot replace them.',
        'mount_evidence':[line for line in Path('/proc/self/mountinfo').read_text().splitlines() if any(' /home/user/'+p+' ' in line for p in ('README.md','manifest.json','trajectory'))]}
(HERE/'workspace_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
