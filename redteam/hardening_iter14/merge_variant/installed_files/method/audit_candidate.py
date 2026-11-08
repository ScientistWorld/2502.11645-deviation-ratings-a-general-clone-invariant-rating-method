"""Installed candidate for the iteration-14 hardening replays (adapted from redteam/audit_20261107).

Public inputs and improve-mode implementation only.

No candidate reads hidden files, evaluator state, test seeds or score files.
Shortcut names are explicit. Certificate modes abort if a universal statement
about an incoming 8x8 CCE polytope cannot be certified by LP.
"""
from __future__ import annotations
import hashlib
import json
import random
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import linprog


def coefficients(payoffs, num_players, action_dims):
    size = int(np.prod(action_dims))
    index = np.arange(size)
    joints = np.stack(np.unravel_index(index, action_dims), axis=1)
    coeff = np.zeros((num_players, max(action_dims), size))
    for p, d in enumerate(action_dims):
        stride = int(np.prod(action_dims[p + 1:]))
        target = index[None, :] + (np.arange(d)[:, None] - joints[:, p][None, :]) * stride
        flat = payoffs[p].reshape(-1)
        coeff[p, :d] = flat[target] - flat[None, :]
    return coeff, joints


def matrix(payoffs):
    dims = list(payoffs.shape[1:])
    coeff, _ = coefficients(payoffs, len(dims), dims)
    return np.concatenate([coeff[p, :d] for p, d in enumerate(dims)])


def output(payoffs, sigma):
    sigma = np.asarray(sigma, dtype=float).reshape(-1)
    dims = payoffs.shape[1:]
    values = matrix(payoffs) @ sigma
    cuts = np.cumsum([0] + list(dims))
    return {'ratings': [values[cuts[p]:cuts[p+1]].tolist() for p in range(len(dims))],
            'equilibrium': sigma.tolist()}


def reference(payoffs, mode='reference'):
    import method.deviation_rating as module
    options = {}
    if mode == 'vectorized_solver':
        module._build_deviation_coefficients = coefficients
    if mode == 'weaker_one_lp':
        options['max_iterations'] = 1
    if mode == 'cap32_shortcut':
        options['max_iterations'] = 32
    if mode == 'cap12_shortcut':
        options['max_iterations'] = 12
    dims = list(payoffs.shape[1:])
    result = module.deviation_rating(payoffs, len(dims), dims, **options)
    return output(payoffs, result['equilibrium'])


def cce_lp(payoffs, objective=None, epsilon=0.):
    D = matrix(payoffs)
    scale = max(1., float(np.abs(payoffs).max()))
    m = D.shape[1]
    result = linprog(np.zeros(m) if objective is None else objective,
                     A_ub=D / scale, b_ub=np.full(len(D), epsilon),
                     A_eq=np.ones((1, m)), b_eq=[1.], bounds=(0., None),
                     method='highs', options={'primal_feasibility_tolerance': 1e-9,
                                              'dual_feasibility_tolerance': 1e-9})
    if not result.success:
        raise RuntimeError(result.message)
    return result


def certify(payoffs, out, tolerant=False):
    """Necessary assertions for this diagnostic to receive passing test scores.

    Exact mode: the reference is pure and every exact CCE puts unit mass on
    that same profile. Tolerant mode additionally certifies that all accepted
    epsilon-CCEs choose the same two bottom actions, with no tie at the cut.
    Each LP's dual objective and primal residual are checked independently.
    """
    sigma = np.asarray(out['equilibrium'])
    peak = int(np.argmax(sigma))
    if sigma[peak] < 1. - 1e-8:
        raise RuntimeError('CERTIFICATE FAIL: reference is not pure')
    objective = np.zeros(len(sigma)); objective[peak] = 1.
    result = cce_lp(payoffs, objective)
    exact_dual = float(result.eqlin.marginals[0])
    if abs(result.fun - exact_dual) > 1e-8 or exact_dual < 1. - 1e-7:
        raise RuntimeError(f'CERTIFICATE FAIL: nonunique exact CCE, min mass={result.fun}')
    if tolerant:
        D = matrix(payoffs)
        scale = max(1., float(np.abs(payoffs).max()))
        # For any accepted normalized distribution: D sigma / scale <= 1e-6.
        for p in range(2):
            ordering = np.argsort(out['ratings'][p])
            for low in ordering[:2]:
                for high in ordering[2:]:
                    obj = (D[p*8+high] - D[p*8+low]) / scale
                    sol = cce_lp(payoffs, obj, epsilon=1e-6)
                    dual = float(np.sum(sol.ineqlin.marginals) * 1e-6 + sol.eqlin.marginals[0])
                    residual = np.max(D / scale @ sol.x - 1e-6)
                    if abs(sol.fun - dual) > 1e-8 or residual > 1e-8 or dual <= 1.01e-6:
                        raise RuntimeError(f'CERTIFICATE FAIL: population cut can move, '
                                           f'player={p}, low={low}, high={high}, bound={dual}, '
                                           f'primal={sol.fun}, residual={residual}')
    return out


def merge_near_copies(payoffs, bound):
    """Estimate the true game from a noisy observation with redundant actions.

    Two actions of a player are treated as copies of one true action when every pair of
    corresponding observed payoffs (all players, every opponent profile) is within
    2 * bound, i.e. some common true payoff is consistent with both observations. Joint
    actions made of copies of the same true actions are merged, each payoff set to the
    midpoint of the interval consistent with all their observations (the midrange,
    within ``bound`` of every observation). Copies become exact clones of each other,
    so the deviation rating of the estimate treats them as the clones they measure
    (Property 6), and their repeated observations average out measurement noise.
    """
    dims = payoffs.shape[1:]
    n = len(dims)
    labels = []
    for p in range(n):
        rows = np.moveaxis(payoffs, p + 1, 1).reshape(n, dims[p], -1).transpose(1, 0, 2).reshape(dims[p], -1)
        groups = []
        for a in range(dims[p]):
            for group in groups:
                if all(np.max(np.abs(rows[a] - rows[c])) <= 2 * bound for c in group):
                    group.append(a)
                    break
            else:
                groups.append([a])
        label = np.empty(dims[p], dtype=int)
        for index, group in enumerate(groups):
            label[group] = index
        labels.append(label)
    keys = np.stack(np.meshgrid(*labels, indexing='ij'), axis=-1).reshape(-1, n)
    _, classes = np.unique(keys, axis=0, return_inverse=True)
    classes = np.asarray(classes).reshape(-1)
    flat = payoffs.reshape(n, -1)
    merged = flat.copy()
    for cls in range(int(classes.max()) + 1):
        members = np.flatnonzero(classes == cls)
        if len(members) < 2:
            continue
        for q in range(n):
            low, high = flat[q, members].max() - bound, flat[q, members].min() + bound
            if low <= high:
                merged[q, members] = 0.5 * (low + high)
    return merged.reshape(payoffs.shape)


def fingerprint(payoffs):
    return hashlib.sha256(json.dumps(payoffs, separators=(',', ':')).encode()).hexdigest()


def candidate(payoffs, mode, cache, bound=0.):
    dims = list(payoffs.shape[1:])
    size = int(np.prod(dims))
    if mode == 'merge_variant':
        if bound > 0:
            estimate = merge_near_copies(payoffs, bound)
            out = reference(estimate)
            out['payoffs'] = estimate.tolist()
            return out
        return reference(payoffs)
    if mode == 'band_violation_shortcut':
        # Rates a game moved by twice the noise bound (outside the allowed band).
        if bound > 0:
            moved = payoffs + 2 * bound * np.sign(payoffs)
            out = reference(moved)
            out['payoffs'] = moved.tolist()
            return out
        return reference(payoffs)
    if mode in ('reference', 'vectorized_solver', 'weaker_one_lp', 'cap32_shortcut', 'cap12_shortcut'):
        return reference(payoffs, mode)
    if mode in ('exact_cce_certificate', 'tolerant_cce_certificate'):
        out = reference(payoffs)
        if payoffs.shape == (2, 8, 8):
            certify(payoffs, out, tolerant=mode.startswith('tolerant'))
        return out
    if mode == 'feasibility_only_shortcut':
        if payoffs.shape == (2, 8, 8):
            D = matrix(payoffs)
            pure = np.flatnonzero(np.max(D, axis=0) <= 1e-10)
            if len(pure):
                sigma = np.zeros(size); sigma[pure[0]] = 1.
                return output(payoffs, sigma)
            return output(payoffs, cce_lp(payoffs).x)
        return reference(payoffs)
    if mode == 'welfare_cce_variant':
        # A genuine alternative equilibrium-selection objective, used on all games.
        # It seeks larger joint expected payoff while respecting every CCE constraint.
        objective = -sum(payoffs[p].reshape(-1) for p in range(len(dims)))
        objective /= max(1., float(np.abs(objective).max()))
        return output(payoffs, cce_lp(payoffs, objective).x)
    if mode == 'size_limit_shortcut':
        if size > 4096:
            return {'ratings': [[0.] * d for d in dims], 'equilibrium': []}
        return reference(payoffs)
    if mode == 'visible_answers_shortcut':
        answer = cache.get(fingerprint(payoffs.tolist()))
        if answer is not None:
            return answer
    out = output(payoffs, np.full(size, 1. / size))
    if mode == 'constant_zero_shortcut':
        out['ratings'] = [[0.] * d for d in dims]
    elif mode == 'copy_input_shortcut':
        out['ratings'] = [payoffs[p].reshape(-1)[:d].tolist() for p, d in enumerate(dims)]
    elif mode == 'empty_output_shortcut':
        return {}
    elif mode == 'impossible_values_shortcut':
        out['ratings'][0][0] = float('nan')
        out['equilibrium'][0] = float('inf')
    elif mode == 'reported_fields_shortcut':
        out.update(success=True, CCE_gap=0., strictness_gap=0., seconds=0.,
                   min_margin=1e100, test_size=0, tolerance=1e100,
                   dominance_pairs=[], ground_truth=[], flags=None)
    return out


def main():
    mode, source, dest = sys.argv[1:]
    seed = 0
    if mode.startswith('reference_seed_'):
        seed = int(mode.rsplit('_', 1)[1]); mode = 'reference'
    random.seed(seed); np.random.seed(seed)
    cache = {}
    if mode == 'visible_answers_shortcut':
        cache = json.loads(Path(__file__).with_name('visible_shortcut_cache.json').read_text())
    results = {}
    for entry in json.loads(Path(source).read_text())['games']:
        payoffs = np.asarray(entry['payoffs'], dtype=float)
        if mode == 'reference' and seed:
            digest = int(fingerprint(entry['payoffs'])[:12], 16)
            rng = np.random.default_rng(seed + digest)
            perms = [rng.permutation(d) for d in payoffs.shape[1:]]
            transformed = payoffs
            for p, perm in enumerate(perms):
                transformed = np.take(transformed, perm, axis=p+1)
            out = reference(transformed)
            sigma = np.asarray(out['equilibrium']).reshape(payoffs.shape[1:])
            for p, perm in enumerate(perms):
                sigma = np.take(sigma, np.argsort(perm), axis=p)
            out = output(payoffs, sigma)
        else:
            out = candidate(payoffs, mode, cache, float(entry.get('noise_bound') or 0.))
        results[entry['id']] = out
    Path(dest).write_text(json.dumps({'results': results}))


if __name__ == '__main__':
    main()
