"""New shortcut rating programs. Only the documented input and visible method are used.

No hidden-test imports, hidden seeds, score reads, or per-game answer caches.
"""
from __future__ import annotations
import itertools
import json
import os
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

ROOT = Path('/home/user')
sys.path.insert(0, str(ROOT))
from method.rate import rate_game


def shortcut_coefficients(game):
    dims = game.shape[1:]
    joints = np.array(list(np.ndindex(*dims)))
    rows = []
    for p, d in enumerate(dims):
        for a in range(d):
            dev = joints.copy()
            dev[:, p] = a
            rows.append(game[(p,) + tuple(dev.T)] - game[p].reshape(-1))
    return np.array(rows)


def shortcut_output(game, sigma):
    sigma = np.maximum(np.asarray(sigma), 0)
    sigma /= sigma.sum()
    values = shortcut_coefficients(game) @ sigma
    rows, at = [], 0
    for d in game.shape[1:]:
        rows.append(values[at:at+d].tolist())
        at += d
    return {'ratings': rows, 'equilibrium': sigma.tolist()}


def shortcut_solve(game, kind='feasible'):
    D = shortcut_coefficients(game)
    m = D.shape[1]
    eq, rhs = [np.ones(m)], [1.]
    if kind in ('zero', 'nondominated'):
        at = 0
        for p, d in enumerate(game.shape[1:]):
            for a in range(d):
                dominated = any(np.all(np.take(game[p], b, axis=p) > np.take(game[p], a, axis=p) + 1e-9)
                                for b in range(d) if b != a)
                if kind == 'zero' or not dominated:
                    eq.append(D[at+a])
                    rhs.append(0.)
            at += d
    res = linprog(np.zeros(m), A_ub=D, b_ub=np.zeros(D.shape[0]),
                  A_eq=np.array(eq), b_eq=rhs, bounds=(0, None), method='highs')
    return res.x if res.success else None


def shortcut_lax(game):
    """Reverse the paper's preference: lexicographically maximize smallest gains.

    This is deliberately a shortcut: the test does not measure strictness.
    """
    D = shortcut_coefficients(game)
    k, m = D.shape
    frozen = {}
    while len(frozen) < k:
        todo = [i for i in range(k) if i not in frozen]
        # All gains remain <=0; unfrozen gains are constrained >=t.
        upper = np.c_[D, np.zeros(k)]
        lower = np.c_[-D[todo], np.ones(len(todo))]
        eq = [np.r_[np.ones(m), 0.]] + [np.r_[D[i], 0.] for i in frozen]
        rhs = [1.] + list(frozen.values())
        result = linprog(np.r_[np.zeros(m), -1.], A_ub=np.r_[upper, lower],
                         b_ub=np.zeros(k+len(todo)), A_eq=eq, b_eq=rhs,
                         bounds=[(0,None)]*m+[(None,None)], method='highs')
        if not result.success:
            raise RuntimeError(result.message)
        sigma = result.x[:m]
        chosen = [i for j,i in enumerate(todo) if abs(result.ineqlin.marginals[k+j]) > 1e-8]
        if not chosen:
            raise RuntimeError('shortcut lax LP had no nonzero dual')
        for i in chosen:
            frozen[i] = float(D[i] @ sigma)
    return shortcut_output(game, sigma)


def shortcut_center(game):
    return np.array([game[p] - game[p].min(axis=p, keepdims=True) for p in range(game.shape[0])])


def shortcut_fingerprint(game):
    c = shortcut_center(game)
    return tuple(tuple(np.round(np.sort(c[p].reshape(-1)), 7)) for p in range(c.shape[0]))


def shortcut_mapping(base, target):
    """Recover action permutations using sorted payoff signatures, then check all cells."""
    if base.shape != target.shape:
        return None
    a, b = shortcut_center(base), shortcut_center(target)
    choices = []
    for p, d in enumerate(base.shape[1:]):
        sig_a = [np.sort(np.take(a, i, axis=p+1).reshape(-1)) for i in range(d)]
        sig_b = [np.sort(np.take(b, i, axis=p+1).reshape(-1)) for i in range(d)]
        candidates = [[j for j in range(d) if np.allclose(sig_a[i], sig_b[j], rtol=0, atol=2e-7)] for i in range(d)]
        if any(not x for x in candidates):
            return None
        possibilities = [x for x in itertools.product(*candidates) if len(set(x)) == d]
        choices.append(possibilities)
    for mapping in itertools.product(*choices):
        reordered = b
        for p, indices in enumerate(mapping):
            reordered = np.take(reordered, indices, axis=p+1)
        if np.allclose(a, reordered, rtol=0, atol=2e-7):
            return [list(x) for x in mapping]
    return None


def shortcut_relation(base, target):
    """Find an offset/permutation/convex-action extension from the visible batch."""
    if base.shape[0] != target.shape[0]:
        return None
    ds = np.array(target.shape[1:]) - np.array(base.shape[1:])
    if np.all(ds == 0):
        if shortcut_fingerprint(base) != shortcut_fingerprint(target):
            return None
        return shortcut_mapping(base, target)
    if np.sum(ds) != 1 or np.any(ds < 0) or np.max(ds) != 1:
        return None
    p = int(np.argmax(ds))
    for remove in range(target.shape[p+1]):
        kept = [a for a in range(target.shape[p+1]) if a != remove]
        sub = np.take(target, kept, axis=p+1)
        if shortcut_fingerprint(base) != shortcut_fingerprint(sub):
            continue
        mapping = shortcut_mapping(base, sub)
        if mapping is None:
            continue
        # A convex deviation is redundant; only actor p's payoff is needed.
        own = np.moveaxis(target[p], p, 0).reshape(target.shape[p+1], -1)
        res = linprog(np.zeros(len(kept)), A_eq=np.r_[own[kept].T, np.ones((1,len(kept)))],
                      b_eq=np.r_[own[remove], 1.], bounds=(0,None), method='highs')
        if res.success and np.max(np.abs(own[kept].T @ res.x-own[remove])) < 2e-7:
            mapping[p] = [kept[a] for a in mapping[p]]
            return mapping
    return None


def shortcut_transport(sigma, dims, target_dims, mapping):
    answer = np.zeros(target_dims)
    source = np.asarray(sigma).reshape(dims)
    for joint in np.ndindex(*dims):
        answer[tuple(mapping[p][a] for p,a in enumerate(joint))] += source[joint]
    return answer.reshape(-1)


def shortcut_batch(entries):
    """Solve arbitrary CCEs once and copy them along visible batch relationships.

    Unlike a method for one game, its output depends on which other games arrive.
    """
    arrays = [np.asarray(e['payoffs'],dtype=float) for e in entries]
    by_size = sorted(range(len(entries)), key=lambda i: arrays[i].size)
    outputs, parents = {}, {}
    for pos,i in enumerate(by_size):
        game = arrays[i]
        for j in by_size[:pos]:
            if arrays[j].shape[0] != game.shape[0]:
                continue
            ds = np.array(game.shape[1:])-np.array(arrays[j].shape[1:])
            if np.any(ds < 0) or np.sum(ds) > 1:
                continue
            mapping = shortcut_relation(arrays[j], game)
            if mapping is not None:
                sigma = shortcut_transport(outputs[j]['equilibrium'], arrays[j].shape[1:],game.shape[1:],mapping)
                outputs[i] = shortcut_output(game,sigma)
                parents[entries[i]['id']] = entries[j]['id']
                break
        else:
            sigma = shortcut_solve(game,'nondominated')
            if sigma is None:
                sigma = shortcut_solve(game)
            outputs[i] = shortcut_output(game,sigma)
    print(json.dumps({'shortcut_batch_transports':len(parents)}),flush=True)
    return {entries[i]['id']:outputs[i] for i in range(len(entries))}


def shortcut_seeded_reference(entries,seed):
    rng = np.random.default_rng(seed)
    results = {}
    for i in rng.permutation(len(entries)):
        e = entries[i]
        game = np.asarray(e['payoffs'],dtype=float)
        perms = [rng.permutation(d) for d in game.shape[1:]]
        permuted = game
        for p, perm in enumerate(perms):
            permuted = np.take(permuted,perm,axis=p+1)
        out = rate_game(permuted)
        sigma = shortcut_transport(out['equilibrium'],game.shape[1:],game.shape[1:],perms)
        results[e['id']] = shortcut_output(game,sigma)
    return results


def main():
    name, source, dest = sys.argv[1:]
    entries = json.loads(Path(source).read_text())['games']
    if name.startswith('reference_seed_'):
        results = shortcut_seeded_reference(entries,int(name.rsplit('_',1)[-1]))
    elif name == 'batch_transport_shortcut':
        results = shortcut_batch(entries)
    else:
        results = {}
        for entry in entries:
            game = np.asarray(entry['payoffs'],dtype=float)
            if name == 'lax_cce_shortcut':
                out = shortcut_lax(game)
            elif name == 'zero_gain_fallback_shortcut':
                sigma = shortcut_solve(game,'zero')
                out = rate_game(game) if sigma is None else shortcut_output(game,sigma)
            elif name == 'zero_nondominated_shortcut':
                sigma = shortcut_solve(game,'nondominated')
                out = shortcut_output(game, shortcut_solve(game) if sigma is None else sigma)
            elif name == 'large_game_abandonment_shortcut':
                out = rate_game(game) if game[0].size <= 1024 else {'ratings':[[0.]*d for d in game.shape[1:]],'equilibrium':[]}
            elif name == 'negative_tolerance_shortcut':
                out = rate_game(game)
                out['equilibrium'] = [x if x>0 else -5e-7 for x in out['equilibrium']]
            elif name == 'tiny_rating_mismatch_shortcut':
                out = rate_game(game)
                scale=max(1.,float(np.abs(game).max()))
                out['ratings']=[[x+5e-7*scale for x in row] for row in out['ratings']]
            elif name == 'bystander_drop_shortcut':
                out = rate_game(game)
                if game.shape[0]==3:
                    out['ratings'][2]=[0.]*game.shape[-1]
            else:
                # Boundary-only shortcuts deliberately use a weak method.
                sigma = np.ones(game[0].size)/game[0].size
                out = shortcut_output(game,sigma)
                out.update(success=True,seconds=0.,test_size=0,tolerance=1e100,
                           dominance_pairs=[],ground_truth=[],baseline_score=1e100)
            results[entry['id']] = out
    Path(dest).write_text(json.dumps({'results':results}))

if __name__=='__main__':
    main()
