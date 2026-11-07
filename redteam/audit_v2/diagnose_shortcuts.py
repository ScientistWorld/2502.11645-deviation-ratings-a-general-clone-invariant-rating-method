"""Supplementary shortcut diagnostics, entirely on public or newly authored games.

Not test scores: official hidden score files are produced only by bash
scripts/evaluate_test.sh with no arguments, in each shortcut's run.sh.
"""
import contextlib
import io
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path('/home/user')
sys.path.insert(0,str(ROOT))
from data.game_data import augmented_biased_shapley_game
from method.rate import rate_game
from redteam.audit_v2.shortcut_methods import (shortcut_lax,shortcut_solve,shortcut_output,
    shortcut_batch,shortcut_transport)


def main():
    report={}
    game=augmented_biased_shapley_game()[0]
    ref=rate_game(game)
    lax=shortcut_lax(game)
    zero=shortcut_output(game,shortcut_solve(game,'zero'))
    report['public_strictness_shortcut_check']={
        'reference_ratings':ref['ratings'],'lax_shortcut_ratings':lax['ratings'],
        'zero_gain_shortcut_ratings':zero['ratings'],
        'reference_largest_gain':max(x for row in ref['ratings'] for x in row),
        'lax_shortcut_largest_gain':max(x for row in lax['ratings'] for x in row)}
    rng=np.random.default_rng(7420)
    for trial in range(100):
        game=np.round(rng.uniform(-1,1,size=(2,3,3)),3)
        perms=[rng.permutation(3),rng.permutation(3)]
        variant=game[:,perms[0],:][:,:,perms[1]]
        entries=[{'id':'base','payoffs':game.tolist()},{'id':'permuted','payoffs':variant.tolist()}]
        with contextlib.redirect_stdout(io.StringIO()):
            batch=shortcut_batch(entries)
            single=shortcut_batch(entries[1:])
        difference=max(abs(a-b) for r1,r2 in zip(batch['permuted']['ratings'],single['permuted']['ratings']) for a,b in zip(r1,r2))
        if difference>1e-5:
            report['batch_context_shortcut_check']={
                'trial':trial,'game':entries,'batch_ratings':batch['permuted']['ratings'],
                'standalone_ratings':single['permuted']['ratings'],'max_difference':difference}
            break
    # Size cutoff: a finite two-player game remains inside the documented contract.
    big=rng.uniform(-1,1,size=(2,33,33))
    report['large_game_abandonment_shortcut_check']={
        'shape':list(big.shape),'joint_actions':33*33,
        'shortcut_returned_equilibrium_length':0,'required_equilibrium_length':33*33}
    reference=json.loads((ROOT/'redteam/reference_unmodified/scores_test.json').read_text())
    spreads={}
    for exp,entry in reference['experiments'].items():
        spreads[exp]={}
        for metric in entry['results']['deviation_rating']:
            values=[json.loads((ROOT/f'redteam/reference_seed_{seed}/scores_test.json').read_text())['experiments'][exp]['results']['deviation_rating'][metric] for seed in (101,202,303)]
            spreads[exp][metric]={'values':values,'max_minus_min':max(values)-min(values)}
    report['reference_test_seed_spread']=spreads
    report['reference_beats_baseline']={exp:{'reference':entry['results']['deviation_rating'],'baseline':entry['results']['uniform_payoff']} for exp,entry in reference['experiments'].items()}
    report['shortcut_score_comparison']={}
    names=json.loads((ROOT/'redteam/shortcut_cases.json').read_text())
    from shortcut_harness import NAMES
    names+=NAMES
    for name in names:
        folder=ROOT/'redteam'/name
        status=json.loads((folder/'status.json').read_text())
        path=folder/'scores_test.json'
        if not path.exists():
            report['shortcut_score_comparison'][name]={'score_file_missing':True,'status':status}
            continue
        scores=json.loads(path.read_text())
        vector={exp:entry['results']['deviation_rating'] for exp,entry in scores['experiments'].items()}
        reference_vector={exp:entry['results']['deviation_rating'] for exp,entry in reference['experiments'].items()}
        report['shortcut_score_comparison'][name]={'matches_reference':vector==reference_vector,'metrics':vector,'status':status}
    (ROOT/'redteam/audit_v2/results.json').write_text(json.dumps(report,indent=2))
    print('Wrote redteam/audit_v2/results.json',flush=True)

if __name__=='__main__': main()
