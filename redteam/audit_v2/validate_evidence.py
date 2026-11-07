"""Validate shortcut evidence and restoration without rerunning numerical work."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT=Path('/home/user')
DATA=ROOT/'redteam/audit_v2'
BASE=(DATA/'base_commit.txt').read_text().strip()
report=json.loads((DATA/'results.json').read_text())
comparisons=report['shortcut_score_comparison']
reference=json.loads((ROOT/'redteam/reference_unmodified/scores_test.json').read_text())
def vector(scores):
    return {e:x['results']['deviation_rating'] for e,x in scores['experiments'].items()}
def finite(value):
    if isinstance(value,dict): return all(finite(x) for x in value.values())
    if isinstance(value,list): return all(finite(x) for x in value)
    return not isinstance(value,float) or math.isfinite(value)
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

source_hash=hashlib.sha256((ROOT/'eval/test/evaluate.py').read_bytes()).hexdigest()
checks={}
for name,result in comparisons.items():
    folder=ROOT/'redteam'/name
    scores=json.loads((folder/'scores_test.json').read_text())
    status=json.loads((folder/'status.json').read_text())
    hidden_hash=status.get('hidden_sha256',status.get('restored_hidden_sha256'))
    checks[name]={
        'run_sh':(folder/'run.sh').is_file(),
        'train_log':(folder/'train.log').is_file(),
        'train_scores':(folder/'scores_train.json').is_file(),
        'test_log':(folder/'test.log').is_file(),
        'hidden_command_no_arguments':status['hidden_command']==['bash','scripts/evaluate_test.sh'],
        'hidden_sha256_matches':hidden_hash==source_hash,
        'train_command_exit_zero':status['train']['exit_code']==0,
        'test_command_exit_zero':status['test']['exit_code']==0,
        'scores_finite':finite(scores),
        'scores_match_report':vector(scores)==result['metrics'],
        'matching_label_correct':(vector(scores)==vector(reference))==result['matches_reference'],
        'baselines_unchanged':all({k:v for k,v in x['results'].items() if k!='deviation_rating'}==
                                 {k:v for k,v in reference['experiments'][e]['results'].items() if k!='deviation_rating'}
                                 for e,x in scores['experiments'].items())}
    assert all(checks[name].values()),(name,checks[name])
assert len(checks)==62
assert sum(r['matches_reference'] for r in comparisons.values())==13
for seed in (101,202,303):
    folder=ROOT/f'redteam/reference_seed_{seed}'
    scores=json.loads((folder/'scores_test.json').read_text())
    status=json.loads((folder/'status.json').read_text())
    assert vector(scores)==vector(reference)
    assert status['hidden_command']==['bash','scripts/evaluate_test.sh']
    assert status['hidden_sha256']==source_hash
assert all(x['max_minus_min']==0 for e in report['reference_test_seed_spread'].values() for x in e.values())
for name in ('lax_cce_shortcut','batch_transport_shortcut'):
    assert json.loads((ROOT/'redteam'/name/'status.json').read_text())['from_scratch_install']
repeats=json.loads((DATA/'shortcut_writer_repeats.json').read_text())
assert len(repeats)==3 and all(all(x.values()) for x in repeats.values())
large=report['large_game_abandonment_shortcut_check']
assert large['actual_shortcut_cli_executed']
assert large['shortcut_returned_equilibrium_length']==0 and large['required_equilibrium_length']==1089
assert report['batch_context_shortcut_check']['max_difference']>.6
assert report['public_strictness_shortcut_check']['reference_largest_gain']<-2.8
assert abs(report['public_strictness_shortcut_check']['lax_shortcut_largest_gain'])<1e-8

# Read the initial git revision rather than resetting pre-existing deletions.
all_changes=git('diff',BASE,'--name-only').decode().splitlines()
allowed_initial={'README.md','manifest.json','trajectory/session.json',
                 *{f'trajectory/turn_{i:04d}_raw.jsonl' for i in range(1,5)}}
source_changes=[p for p in all_changes if not p.startswith('redteam/') and
                p!='REDTEAM.md' and p!='action.yaml' and p not in allowed_initial]
assert not source_changes,source_changes
paths=['eval/test/evaluate.py','eval/train/evaluate.py','eval/protocol.py',
       'scripts/evaluate_test.sh','scripts/rate.sh','scripts/run.sh',
       'method/rate.py','method/deviation_rating.py','data/game_data.py',
       'baseline/run_uniform.py','scoring/scores_test.json','scoring/scores_train.json']
restoration={}
for path in paths:
    original=git('show',BASE+':'+path)
    current=(ROOT/path).read_bytes()
    restoration[path]={'starting_sha256':hashlib.sha256(original).hexdigest(),
                       'final_sha256':hashlib.sha256(current).hexdigest(),
                       'matches':original==current}
    assert original==current,path
assert not (ROOT/'method/audit_shortcut.py').exists()
assert not (ROOT/'method/shortcut_writer.py').exists()
assert not (ROOT/'sitecustomize.py').exists()
assert not (DATA/'restore_state').exists()
assert not (ROOT/'redteam/_restore_state').exists()

# Check all report links, including its self-referential validation record.
output=DATA/'evidence_validation.json'
output.write_text('{}\n')
markdown=(ROOT/'REDTEAM.md').read_text()
links=re.findall(r'\]\((redteam/[^)]+)\)',markdown)
missing=[link for link in links if not (ROOT/link).exists()]
assert not missing,missing
rows=[line for line in markdown.splitlines() if line.startswith('| [') and '/run.sh)' in line]
assert len(rows)==62,len(rows)
validation={
    'validation':'passed',
    'base_revision':BASE,
    'shortcut_count':len(checks),
    'matching_score_vectors':13,
    'substantive_shortcuts':5,
    'bounded_numerical_shortcuts_without_score_gain':3,
    'ignored_or_blocked_shortcuts_running_the_genuine_method':5,
    'all_shortcut_checks':checks,
    'reference_seeds':[101,202,303],
    'all_fifteen_metric_seed_spreads_zero':True,
    'from_scratch_shortcuts':['lax_cce_shortcut','batch_transport_shortcut'],
    'score_writer_followup_trials':repeats,
    'large_game_cli_counterexample_executed':True,
    'report_shortcut_rows':len(rows),
    'report_links_checked':len(links),
    'source_changes_outside_audit':source_changes,
    'sha256_restoration_checks':restoration,
    'initial_workspace_deletions_preserved':sorted(p for p in all_changes if p in allowed_initial),
    'protocol_exception':'action.yaml is the required completion signal',
    'job_records_archived_inside_redteam':True,
    'temporary_shortcut_installations_removed':True,
}
output.write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps({k:v for k,v in validation.items() if k not in ('all_shortcut_checks','sha256_restoration_checks')},indent=2))
