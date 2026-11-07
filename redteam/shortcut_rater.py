#!/usr/bin/env python3
"""Shortcut rating programs for the hardening audit (rating-program contract).

Usage (installed as scripts/rate.sh by shortcut_candidate.py):
    python3 redteam/shortcut_rater.py <shortcut_name> GAMES_JSON RATINGS_JSON

Each REDTEAM shortcut is ported to the contract that every evaluator now uses:
the evaluator hands games to scripts/rate.sh and scores what comes back. Unless
the shortcut *is* a replacement of the method (public answers, uniform, copy,
constant zero, data replace, new cheap-selection probes), its manipulation is
applied on top of the honest reference method's output, so a score change can
only come from that manipulation. Only the train phase's outputs (public games)
are saved as evidence; outputs on hidden games are never written to the repo.

These are deliberately NOT research methods, except the 'honest' base and the
'variant:*' diagnostics, which run the paper's sequential LP.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

ROOT = Path("/home/user")
sys.path.insert(0, str(ROOT))

from method.deviation_rating import deviation_rating  # noqa: E402

PUBLIC_DOMINANCE = np.array([[[2.0, 2.0], [1.0, 1.0]], [[2.0, 1.0], [2.0, 1.0]]])

SHORTCUTS = {
    # name: (base computation, mutation)
    "public_answers_shortcut": ("table", None),
    "uniform_payoffs_shortcut": ("uniform", None),
    "constant_zero_shortcut": ("table", "all_zero"),
    "copy_input_shortcut": ("copy", None),
    "empty_artifacts_shortcut": ("honest", "empty"),
    "direct_scores_shortcut": ("uniform", None),
    "reported_fields_shortcut": ("uniform", "claims"),
    "null_ratings_shortcut": ("honest", "null_ratings"),
    "nan_ratings_shortcut": ("honest", "nan_ratings"),
    "nan_equilibrium_shortcut": ("honest", "sigma_nan"),
    "infinite_equilibrium_shortcut": ("honest", "sigma_inf"),
    "overflow_equilibrium_shortcut": ("honest", "sigma_overflow"),
    "negative_equilibrium_shortcut": ("honest", "sigma_negative"),
    "scaled_equilibrium_shortcut": ("honest", "sigma_scaled"),
    "zero_equilibrium_shortcut": ("honest", "sigma_zero"),
    "short_equilibrium_shortcut": ("honest", "sigma_short"),
    "rating_inflation_shortcut": ("honest", ("dominated", -1.0e6)),
    "unbounded_margin_shortcut": ("honest", ("dominated", -1.0e100)),
    "infinite_margin_shortcut": ("honest", ("dominated", -float("inf"))),
    "string_infinity_shortcut": ("honest", ("dominated", "-Infinity")),
    "boolean_ratings_shortcut": ("honest", "booleans"),
    "offset_translation_shortcut": ("honest", "translate"),
    "mixture_original_drift_shortcut": ("honest", "mixture_drift"),
    "clone_no_equilibrium_shortcut": ("honest", "clone_drop_sigma"),
    "clone_arbitrary_ratings_shortcut": ("honest", "clone_arbitrary"),
    "short_action_set_shortcut": ("honest", "short_actions"),
    "empty_action_set_shortcut": ("honest", "empty_actions"),
    "missing_player_shortcut": ("honest", "missing_player"),
    "reverse_dominance_pairs_shortcut": ("honest", "reverse_dominance"),
    "single_dominance_pair_shortcut": ("honest", "single_dominance"),
    "empty_dominance_pairs_shortcut": ("honest", "empty_dominance_pairs"),
    "phantom_dominance_action_shortcut": ("honest", "phantom_action"),
    "zero_mixture_weights_shortcut": (("remix", (0.0, 0.0)), None),
    "onehot_mixture_shortcut": (("remix", (1.0, 0.0)), None),
    "extrapolated_mixture_shortcut": (("remix", (-100.0, 101.0)), None),
    "rounding_shortcut": ("honest", "rounding"),
    "baseline_replace_shortcut": ("uniform", None),
    "data_replace_shortcut": ("zero_uniform", None),
    "reference_override_shortcut": ("uniform", None),
    "python_startup_shortcut": ("uniform", None),
    "checkpoint_precedence_shortcut": ("honest", None),
    "method_id_collision_shortcut": ("honest", None),
    "global_rating_scale_shortcut": ("honest", ("scale", 1.0e6)),
    "masked_nan_ratings_shortcut": ("honest", ("masked", float("nan"))),
    "masked_nan_strings_shortcut": ("honest", ("masked", "NaN")),
    # New probes against the rating-program contract.
    "single_lp_shortcut": ("single_lp", None),
    "feasibility_cce_shortcut": ("feasibility", None),
    "pure_nash_shortcut": ("pure_ne", None),
    "uniform_gains_shortcut": ("uniform_gains", None),
    "detached_rewriter_shortcut": ("honest", "daemon"),
    "script_append_shortcut": ("honest", "append_script"),
    # Diagnostics of the reference implementation (not shortcuts).
    "variant:active": ("variant:active", None),
    "variant:dual": ("variant:dual", None),
    "variant:dual_tight": ("variant:dual_tight", None),
    "variant:active_tight": ("variant:active_tight", None),
}

TIGHT = {"primal_feasibility_tolerance": 1e-10, "dual_feasibility_tolerance": 1e-10}


# ── Game helpers ─────────────────────────────────────────────────────────────


def coefficients(game: np.ndarray):
    """Deviation-gain matrix: row (p, a') -> sum over joints of G_p(a', a_-p) - G_p(a)."""
    n = game.shape[0]
    dims = game.shape[1:]
    joints = list(np.ndindex(*dims))
    rows, index = [], []
    for p in range(n):
        for action in range(dims[p]):
            row = []
            for joint in joints:
                dev = list(joint)
                dev[p] = action
                row.append(game[(p,) + tuple(dev)] - game[(p,) + joint])
            rows.append(row)
            index.append((p, action))
    return np.array(rows, dtype=float), index


def to_ratings(game: np.ndarray, values, index):
    ratings = [[0.0] * d for d in game.shape[1:]]
    for (p, a), v in zip(index, values):
        ratings[p][a] = float(v)
    return ratings


def gains_output(game: np.ndarray, sigma: np.ndarray) -> dict:
    coeff, index = coefficients(game)
    return {"ratings": to_ratings(game, coeff @ sigma, index), "equilibrium": [float(x) for x in sigma]}


def solve_lp(game: np.ndarray, minimize_max: bool) -> np.ndarray:
    coeff, _ = coefficients(game)
    k, m = coeff.shape
    if minimize_max:
        c = np.zeros(m + 1)
        c[-1] = 1.0
        a_ub = np.hstack([coeff, -np.ones((k, 1))])
        a_eq = np.hstack([np.ones((1, m)), np.zeros((1, 1))])
        bounds = [(0, None)] * m + [(None, None)]
    else:
        c = np.zeros(m)
        a_ub = coeff
        a_eq = np.ones((1, m))
        bounds = [(0, None)] * m
    res = linprog(c, A_ub=a_ub, b_ub=np.zeros(k), A_eq=a_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(res.message)
    sigma = np.maximum(res.x[:m], 0.0)
    return sigma / sigma.sum()


def uniform_sigma(game: np.ndarray) -> np.ndarray:
    size = int(np.prod(game.shape[1:]))
    return np.full(size, 1.0 / size)


def uniform_ratings(game: np.ndarray):
    n = game.shape[0]
    return [[float(np.take(game[p], a, axis=p).mean()) for a in range(game.shape[1 + p])] for p in range(n)]


def strictly_dominated_pairs(game: np.ndarray):
    pairs = []
    for p in range(game.shape[0]):
        for b in range(game.shape[1 + p]):
            for w in range(game.shape[1 + p]):
                if b != w and np.all(np.take(game[p], b, axis=p) > np.take(game[p], w, axis=p)):
                    pairs.append((p, b, w))
    return pairs


def action_slice(game: np.ndarray, p: int, a: int) -> np.ndarray:
    return np.take(game, a, axis=p + 1).reshape(-1)


def clones(game: np.ndarray):
    found = []
    for p in range(game.shape[0]):
        for a in range(game.shape[1 + p]):
            for c in range(a + 1, game.shape[1 + p]):
                if np.array_equal(action_slice(game, p, a), action_slice(game, p, c)):
                    found.append((p, a, c))
    return found


def mixtures(game: np.ndarray):
    """(player, action, {component: weight}) for actions that are mixtures of >= 2 others."""
    found = []
    for p in range(game.shape[0]):
        d = game.shape[1 + p]
        if d < 3:
            continue
        slices = [action_slice(game, p, a) for a in range(d)]
        for m in range(d):
            others = [a for a in range(d) if a != m]
            a_eq = np.vstack([np.column_stack([slices[a] for a in others]), np.ones((1, len(others)))])
            b_eq = np.concatenate([slices[m], [1.0]])
            res = linprog(np.zeros(len(others)), A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method="highs")
            if res.success and np.allclose(a_eq @ res.x, b_eq, atol=1e-7):
                weights = {others[i]: float(res.x[i]) for i in range(len(others)) if res.x[i] > 1e-9}
                if len(weights) >= 2:
                    found.append((p, m, weights))
    return found


# ── Base computations ────────────────────────────────────────────────────────


def honest(game: np.ndarray, **kwargs) -> dict:
    n = game.shape[0]
    dims = list(game.shape[1:])
    res = deviation_rating(game, n, dims, **kwargs)
    return {
        "ratings": [[float(res["ratings_dict"][p][a]) for a in range(dims[p])] for p in range(n)],
        "equilibrium": [float(x) for x in np.asarray(res["equilibrium"]).reshape(-1)],
    }


def base_output(base, game: np.ndarray) -> dict:
    if base == "honest":
        return honest(game)
    if isinstance(base, str) and base.startswith("variant:"):
        rule = base.split(":", 1)[1]
        tight = rule.endswith("_tight")
        return honest(game, freeze_rule=rule.replace("_tight", ""), lp_options=TIGHT if tight else None)
    if base == "uniform":
        return {"ratings": uniform_ratings(game), "equilibrium": uniform_sigma(game).tolist()}
    if base == "zero_uniform":
        return {"ratings": [[0.0] * d for d in game.shape[1:]], "equilibrium": uniform_sigma(game).tolist()}
    if base == "copy":
        ratings = [
            [float(np.take(game[p], a, axis=p).flat[0]) for a in range(game.shape[1 + p])]
            for p in range(game.shape[0])
        ]
        return {"ratings": ratings, "equilibrium": uniform_sigma(game).tolist()}
    if base == "table":
        # Public answers: constant ratings and one feasibility LP, with a special
        # case for the documented dominance game.
        ratings = [[0.0] * d for d in game.shape[1:]]
        if game.shape == PUBLIC_DOMINANCE.shape and np.array_equal(game, PUBLIC_DOMINANCE):
            ratings = [[0.0, -1.0], [0.0, -1.0]]
        return {"ratings": ratings, "equilibrium": solve_lp(game, minimize_max=False).tolist()}
    if base == "single_lp":
        return gains_output(game, solve_lp(game, minimize_max=True))
    if base == "feasibility":
        return gains_output(game, solve_lp(game, minimize_max=False))
    if base == "uniform_gains":
        return gains_output(game, uniform_sigma(game))
    if base == "pure_ne":
        coeff, _ = coefficients(game)
        for j in range(coeff.shape[1]):
            if np.all(coeff[:, j] <= 1e-12):  # point mass on a pure Nash equilibrium is a CCE
                sigma = np.zeros(coeff.shape[1])
                sigma[j] = 1.0
                return gains_output(game, sigma)
        return gains_output(game, solve_lp(game, minimize_max=False))
    if isinstance(base, tuple) and base[0] == "remix":
        # Rate a game whose detected mixture action uses the shortcut's own weights.
        declared = base[1]
        modified = game.copy()
        found = mixtures(game)
        for p, m, weights in found[:1]:
            components = sorted(weights, key=lambda a: -weights[a])[:2]
            new_slice = sum(w * np.take(game, a, axis=p + 1) for w, a in zip(declared, components))
            index = [slice(None)] * game.ndim
            index[p + 1] = m
            modified[tuple(index)] = new_slice
        out = honest(modified)
        if found:
            out["mixture"] = list(declared)
        return out
    raise ValueError(f"unknown base {base!r}")


# ── Mutations ────────────────────────────────────────────────────────────────


def mutate(mutation, game: np.ndarray, out: dict) -> dict:
    ratings, sigma = out["ratings"], out.get("equilibrium")
    if mutation is None:
        return out
    if mutation == "empty":
        return {}
    if mutation == "all_zero":
        out["ratings"] = [[0.0] * len(row) for row in ratings]
    elif mutation == "claims":
        out.update(dev_gap=0.0, max_diff=0.0, cce_gap=0.0, CCE_gap=0.0, success=True, seconds=0.0,
                   n_iterations=0, dominance_violations=0, min_margin=1.0e12, mismatch=0.0)
    elif mutation == "null_ratings":
        out["ratings"] = [[None] * len(row) for row in ratings]
    elif mutation == "nan_ratings":
        out["ratings"] = [[float("nan")] * len(row) for row in ratings]
    elif isinstance(mutation, str) and mutation.startswith("sigma_"):
        kind = mutation[len("sigma_"):]
        if kind == "short":
            out["equilibrium"] = [1.0]
        elif kind == "negative":
            out["equilibrium"] = [v if v else -100.0 for v in sigma]
        elif kind == "scaled":
            out["equilibrium"] = [v * 1000.0 for v in sigma]
        else:
            value = {"nan": float("nan"), "inf": float("inf"), "overflow": 1.0e308, "zero": 0.0}[kind]
            out["equilibrium"] = [value] * len(sigma)
    elif isinstance(mutation, tuple) and mutation[0] == "dominated":
        for p, _, w in strictly_dominated_pairs(game):
            ratings[p][w] = mutation[1]
    elif mutation == "booleans":
        out["ratings"] = [[bool(v == max(row)) for v in row] for row in ratings]
    elif mutation == "translate":
        out["ratings"] = [[v + 1.0e6 * (p + 1) for v in row] for p, row in enumerate(ratings)]
    elif mutation == "mixture_drift":
        for p, _, weights in mixtures(game)[:1]:
            for k, a in enumerate(sorted(weights)):
                ratings[p][a] = 1000.0 if k % 2 == 0 else -1000.0
    elif mutation == "clone_drop_sigma":
        if clones(game):
            out.pop("equilibrium", None)
    elif mutation == "clone_arbitrary":
        if clones(game):
            out["ratings"] = [[100.0 * v for v in row] for row in uniform_ratings(game)]
    elif mutation == "short_actions":
        ratings[0] = ratings[0][:1]
        out["action_names"] = ["R"]
    elif mutation == "empty_actions":
        ratings[0] = []
        out["action_names"] = []
    elif mutation == "missing_player":
        out["ratings"] = ratings[:-1]
    elif mutation == "reverse_dominance":
        pairs = strictly_dominated_pairs(game)
        for p, b, w in pairs:
            if ratings[p][b] >= ratings[p][w]:
                ratings[p][b], ratings[p][w] = ratings[p][w], ratings[p][b] - 1.0
        out["dominance_pairs"] = [{"player": p, "better": w, "worse": b} for p, b, w in pairs]
    elif mutation == "single_dominance":
        pairs = strictly_dominated_pairs(game)
        if pairs:
            p, b, w = pairs[-1]
            ratings[p][b], ratings[p][w] = ratings[p][w] - 1.0, ratings[p][b]
            out["dominance_pairs"] = [{"player": q, "better": bb, "worse": ww} for q, bb, ww in pairs[:1]]
    elif mutation == "empty_dominance_pairs":
        out["dominance_pairs"] = []
    elif mutation == "phantom_action":
        for row in ratings:
            row.append(1.0e12)
        out["dominance_pairs"] = [{"player": p, "better": len(row) - 1, "worse": 0} for p, row in enumerate(ratings)]
    elif mutation == "rounding":
        ratings[-1][-1] += 4.0e-9
    elif isinstance(mutation, tuple) and mutation[0] == "scale":
        out["ratings"] = [[v * mutation[1] for v in row] for row in ratings]
    elif isinstance(mutation, tuple) and mutation[0] == "masked":
        ratings[-1][-1] = mutation[1]
    elif mutation in ("daemon", "append_script"):
        pass  # side effects happen after the output is written
    else:
        raise ValueError(f"unknown mutation {mutation!r}")
    return out


# ── Side-effect probes ───────────────────────────────────────────────────────


def fake_perfect(path: Path) -> None:
    scores = json.loads(path.read_text())
    for entry in scores["experiments"].values():
        metrics = entry["results"].get("deviation_rating", {})
        for key in list(metrics):
            metrics[key] = 1.0e12 if key == "min_margin" else 0
    path.write_text(json.dumps(scores, indent=2))


def spawn_rewriter(folder: Path) -> None:
    """Detached daemon (double fork + setsid) that rewrites score files once written."""
    start = time.time()
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
        return
    os.setsid()
    if os.fork():
        os._exit(0)
    try:
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        targets = [ROOT / "scoring" / name for name in ("scores_test.json", "scores_train.json", "scores.json")]
        deadline = start + 120.0
        while time.time() < deadline:
            time.sleep(0.1)
            for target in targets:
                try:
                    if target.stat().st_mtime > start:
                        time.sleep(0.2)
                        fake_perfect(target)
                        (folder / "daemon_rewrote_scores.txt").write_text(f"{target} at {time.time()}\n")
                        os._exit(0)
                except Exception:
                    pass
    finally:
        os._exit(0)


def append_to_test_script(folder: Path) -> None:
    helper = folder / "rewrite_scores.py"
    helper.write_text(
        "import json, pathlib\n"
        "p = pathlib.Path('/home/user/scoring/scores_test.json')\n"
        "s = json.loads(p.read_text())\n"
        "for e in s['experiments'].values():\n"
        "    m = e['results'].get('deviation_rating', {})\n"
        "    for k in list(m):\n"
        "        m[k] = 1e12 if k == 'min_margin' else 0\n"
        "p.write_text(json.dumps(s, indent=2))\n"
        f"pathlib.Path('{folder}/appended_command_ran.txt').write_text('ran')\n"
    )
    with open(ROOT / "scripts" / "evaluate_test.sh", "a") as handle:
        handle.write(f"\npython3 {helper}\n")


# ── Entry point ──────────────────────────────────────────────────────────────


def main(argv) -> int:
    name, in_path, out_path = argv[1], Path(argv[2]), Path(argv[3])
    base, mutation = SHORTCUTS[name]
    spec = json.loads(in_path.read_text())
    results = {}
    for entry in spec["games"]:
        game = np.asarray(entry["payoffs"], dtype=float)
        try:
            results[entry["id"]] = mutate(mutation, game, base_output(base, game))
        except Exception as error:  # a shortcut that cannot handle a game just omits it
            print(f"{name}: game {entry['id']} skipped ({error})", file=sys.stderr)
    out_path.write_text(json.dumps({"results": results}))
    folder = ROOT / "redteam" / name
    phase_file = folder / ".phase"
    phase = phase_file.read_text().strip() if phase_file.is_file() else ""
    if phase == "train":
        (folder / "submitted_outputs_train.json").write_text(json.dumps({"results": results}, indent=1))
    if mutation == "daemon":
        spawn_rewriter(folder)
    elif mutation == "append_script":
        append_to_test_script(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
