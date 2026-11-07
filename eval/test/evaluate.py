#!/usr/bin/env python3
"""Hidden test for the deviation-rating benchmark.

Self-contained (standard library only) and run as ``python3 -I`` so nothing a
submission can edit (PYTHONPATH, sitecustomize, eval/protocol.py, data/,
scoring/reference.json, checkpoints/) is imported or trusted.

The test games are generated here at test time from a seed that exists only in
this file. The method under test is the program ``scripts/rate.sh``; it is run
once on the shuffled, anonymised games in a fresh temporary directory, all of
its processes are killed before anything is scored, and every scored number is
recomputed from the payoffs and the submitted equilibria. Baselines, the
transformations (clones, mixtures and their weights, offsets, permutations),
the dominance relations, tolerances and the test size are fixed here.

The contract and the validity gates are the same as in eval/protocol.py.
"""

from __future__ import annotations

import ctypes
import itertools
import json
import math
import operator
import os
import random
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from array import array
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path("/home/user")
RATER = ROOT / "scripts" / "rate.sh"
PROPOSED_ID = "deviation_rating"

TOL = 1.0e-6
DECIMALS = 6
FAIL_LOWER = 1.0e6
FAIL_HIGHER = -1.0e6
RATER_TIMEOUT_SECONDS = 1800
MAX_OUTPUT_BYTES = 64 * 1024 * 1024

EXPERIMENT_METRICS: Dict[str, Tuple[str, ...]] = {
    "biased_shapley_augmented": ("dev_gap", "all_player_dev_gap", "player_symmetry_gap", "CCE_gap"),
    "clone_invariance": ("max_diff", "all_players_max_diff", "clone_source_gap"),
    "mixture_invariance": ("original_max_diff", "mixture_error", "max_CCE_gap"),
    "offset_invariance": ("max_diff", "max_CCE_gap"),
    "dominance_preserving": ("dominance_violations", "min_margin", "CCE_gap"),
    "population_improvement": ("final_gap_ratio", "mean_gap_ratio", "invariance_violation"),
}
HIGHER_IS_BETTER = frozenset({"min_margin"})
INTEGER_METRICS = frozenset({"dominance_violations"})
BASELINES: Dict[str, Tuple[str, ...]] = {
    "biased_shapley_augmented": ("uniform_payoff",),
    "clone_invariance": ("uniform_payoff",),
    "mixture_invariance": ("uniform_payoff",),
    "offset_invariance": ("uniform_payoff",),
    "dominance_preserving": ("uniform_payoff", "zero_rating", "negative_uniform_payoff"),
    "population_improvement": ("uniform_payoff", "random_selection"),
}


# ── Games ────────────────────────────────────────────────────────────────────


class Game:
    """Normal-form game stored as one flat C-order payoff table per player."""

    __slots__ = ("dims", "n", "size", "strides", "tables", "_own", "_scale")

    def __init__(self, dims: Sequence[int], tables: Sequence[Sequence[float]]):
        self.dims = tuple(int(d) for d in dims)
        self.n = len(self.dims)
        size = 1
        for d in self.dims:
            size *= d
        self.size = size
        strides = [1] * self.n
        acc = 1
        for p in range(self.n - 1, -1, -1):
            strides[p] = acc
            acc *= self.dims[p]
        self.strides = tuple(strides)
        if len(tables) != self.n or any(len(t) != size for t in tables):
            raise ValueError("payoff tables do not match the action dimensions")
        self.tables = [[float(v) for v in t] for t in tables]
        self._own = [
            [(j // self.strides[p]) % self.dims[p] for j in range(size)] for p in range(self.n)
        ]
        self._scale = max(1.0, max(abs(v) for t in self.tables for v in t))

    @classmethod
    def from_function(cls, dims: Sequence[int], fn: Callable[[int, Tuple[int, ...]], float]) -> "Game":
        dims = tuple(int(d) for d in dims)
        joints = list(itertools.product(*[range(d) for d in dims]))
        return cls(dims, [[float(fn(p, joint)) for joint in joints] for p in range(len(dims))])

    def index(self, joint: Sequence[int]) -> int:
        return sum(a * s for a, s in zip(joint, self.strides))

    def value(self, player: int, joint: Sequence[int]) -> float:
        return self.tables[player][self.index(joint)]

    def scale(self) -> float:
        return self._scale

    def payload(self) -> list:
        def nest(table: List[float], depth: int, offset: int):
            if depth == self.n:
                return table[offset]
            return [nest(table, depth + 1, offset + a * self.strides[depth]) for a in range(self.dims[depth])]

        return [nest(self.tables[p], 0, 0) for p in range(self.n)]


def identity_maps(game: Game) -> List[List[int]]:
    return [list(range(d)) for d in game.dims]


def compose_maps(first: List[List[int]], second: List[List[int]]) -> List[List[int]]:
    """Map original actions through ``first`` and then ``second``."""
    return [[second[p][pos] for pos in first[p]] for p in range(len(first))]


def permute_actions(game: Game, perms: List[List[int]]) -> Tuple[Game, List[List[int]]]:
    """``perms[p][new_position] = old_action``; returns the game and old->new maps."""
    new = Game.from_function(
        game.dims, lambda p, joint: game.value(p, tuple(perms[q][joint[q]] for q in range(game.n)))
    )
    inverse = [[0] * d for d in game.dims]
    for q in range(game.n):
        for new_pos, old in enumerate(perms[q]):
            inverse[q][old] = new_pos
    return new, inverse


def insert_action(
    game: Game,
    player: int,
    position: int,
    payoff_fn: Callable[[int, Tuple[int, ...]], float],
) -> Tuple[Game, List[List[int]]]:
    """Insert one new action for ``player`` at ``position``.

    ``payoff_fn(q, joint)`` gives player ``q``'s payoff when ``player`` plays the
    new action (``joint[player]`` is ignored).
    """
    new_dims = list(game.dims)
    new_dims[player] += 1

    def fn(q: int, joint: Tuple[int, ...]) -> float:
        action = joint[player]
        if action == position:
            return payoff_fn(q, joint)
        old = list(joint)
        old[player] = action if action < position else action - 1
        return game.value(q, tuple(old))

    maps = identity_maps(game)
    maps[player] = [a if a < position else a + 1 for a in range(game.dims[player])]
    return Game.from_function(new_dims, fn), maps


def clone_action(game: Game, player: int, source: int, position: int) -> Tuple[Game, List[List[int]]]:
    def payoff(q: int, joint: Tuple[int, ...]) -> float:
        src = list(joint)
        src[player] = source
        return game.value(q, tuple(src))

    return insert_action(game, player, position, payoff)


def mixture_action(
    game: Game, player: int, weights: Dict[int, float], position: int
) -> Tuple[Game, List[List[int]]]:
    def payoff(q: int, joint: Tuple[int, ...]) -> float:
        terms = []
        for action, weight in weights.items():
            src = list(joint)
            src[player] = action
            terms.append(weight * game.value(q, tuple(src)))
        return math.fsum(terms)

    return insert_action(game, player, position, payoff)


def add_offsets(game: Game, offsets: List[Dict[Tuple[int, ...], float]]) -> Game:
    """``offsets[p][a_-p]`` is added to player ``p``'s payoff."""
    return Game.from_function(
        game.dims,
        lambda p, joint: game.value(p, joint) + offsets[p][tuple(joint[:p]) + tuple(joint[p + 1 :])],
    )


# ── Game-theoretic quantities (recomputed by the evaluator) ─────────────────


def deviation_gains(game: Game, sigma: Sequence[float]) -> List[List[float]]:
    support = [(j, s) for j, s in enumerate(sigma) if s != 0.0]
    gains = []
    for p in range(game.n):
        table = game.tables[p]
        stride = game.strides[p]
        own = game._own[p]
        current = math.fsum(s * table[j] for j, s in support)
        row = []
        for action in range(game.dims[p]):
            deviated = math.fsum(s * table[j + (action - own[j]) * stride] for j, s in support)
            row.append(deviated - current)
        gains.append(row)
    return gains


def cce_gap(gains: List[List[float]]) -> float:
    """Total CCE regret: sum over players of the largest positive deviation gain."""
    return math.fsum(max(0.0, max(row)) for row in gains)


def uniform_ratings(game: Game) -> List[List[float]]:
    ratings = []
    for p in range(game.n):
        own = game._own[p]
        row = []
        for action in range(game.dims[p]):
            values = [game.tables[p][j] for j in range(game.size) if own[j] == action]
            row.append(math.fsum(values) / len(values))
        ratings.append(row)
    return ratings


def uniform_distribution(game: Game) -> List[float]:
    return [1.0 / game.size] * game.size


def strict_dominance_pairs(game: Game) -> List[Tuple[int, int, int, float]]:
    """All (player, better, worse, smallest payoff advantage) strict dominance pairs."""
    pairs = []
    for p in range(game.n):
        stride = game.strides[p]
        own = game._own[p]
        table = game.tables[p]
        base_rows = [j for j in range(game.size) if own[j] == 0]
        for better in range(game.dims[p]):
            for worse in range(game.dims[p]):
                if better == worse:
                    continue
                gaps = [table[j + better * stride] - table[j + worse * stride] for j in base_rows]
                smallest = min(gaps)
                if smallest > 1.0e-9 * game.scale():
                    pairs.append((p, better, worse, smallest))
    return pairs


# ── Rater execution ─────────────────────────────────────────────────────────


def _enable_subreaper() -> bool:
    """Become the reaper of every orphaned descendant (Linux PR_SET_CHILD_SUBREAPER)."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(36, 1, 0, 0, 0) == 0
    except Exception:
        return False


def _child_pids() -> List[int]:
    me = os.getpid()
    children = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return children
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "r") as handle:
                fields = handle.read().rsplit(")", 1)[-1].split()
        except OSError:
            continue
        if len(fields) > 1 and fields[1].isdigit() and int(fields[1]) == me:
            children.append(int(entry))
    return children


def _kill_descendants() -> None:
    """Kill and reap every remaining descendant, including detached daemons."""
    for _ in range(200):
        children = _child_pids()
        if not children:
            return
        for pid in children:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for pid in children:
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass


def _reject_constant(name: str):
    raise ValueError(f"non-finite JSON constant {name}")


def _parse_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number {text}")
    return value


def run_rater(
    games: Dict[str, Game],
    order: Sequence[str],
    command: Optional[Sequence[str]] = None,
    timeout: float = RATER_TIMEOUT_SECONDS,
) -> Tuple[Optional[dict], str, str]:
    """Run a rating program on ``games``; return (results, error, log tail)."""
    command = list(command) if command is not None else ["bash", str(RATER)]
    workdir = Path(tempfile.mkdtemp(prefix="rating_eval_"))
    log_tail = ""
    try:
        in_path = workdir / "games.json"
        out_path = workdir / "ratings.json"
        log_path = workdir / "rater.log"
        in_path.write_text(json.dumps({"games": [{"id": gid, "payoffs": games[gid].payload()} for gid in order]}))
        if command[:1] == ["bash"] and len(command) > 1 and not Path(command[1]).is_file():
            return None, f"rating program {command[1]} not found", log_tail
        _enable_subreaper()
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(ROOT),
            "LANG": "C.UTF-8",
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        timed_out = False
        with open(log_path, "wb") as log_handle:
            proc = subprocess.Popen(
                command + [str(in_path), str(out_path)],
                cwd=str(ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                returncode = None
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                _kill_descendants()
        try:
            log_tail = log_path.read_bytes()[-4000:].decode("utf-8", errors="replace")
        except OSError:
            log_tail = ""
        if timed_out:
            return None, f"rating program timed out after {timeout:.0f} s", log_tail
        if returncode != 0:
            return None, f"rating program exited with status {returncode}", log_tail
        try:
            info = os.lstat(out_path)
        except OSError:
            return None, "rating program wrote no output file", log_tail
        if not stat.S_ISREG(info.st_mode):
            return None, "rating output is not a regular file", log_tail
        if info.st_size > MAX_OUTPUT_BYTES:
            return None, "rating output is too large", log_tail
        try:
            data = json.loads(
                out_path.read_bytes().decode("utf-8"),
                parse_constant=_reject_constant,
                parse_float=_parse_float,
            )
        except Exception as error:  # malformed JSON, NaN/Infinity, deep nesting, bad UTF-8
            return None, f"rating output is not valid finite JSON ({type(error).__name__}: {error})", log_tail
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, dict):
            return None, "rating output has no 'results' object", log_tail
        return results, "", log_tail
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ── Output validation ───────────────────────────────────────────────────────


def _real(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_result(game: Game, entry) -> dict:
    """Check one game's output. Returns {'ok', 'reason', 'ratings', 'cce_gap', ...}."""
    if not isinstance(entry, dict):
        return {"ok": False, "reason": "no result object for this game"}
    ratings = entry.get("ratings")
    if not isinstance(ratings, list) or len(ratings) != game.n:
        return {"ok": False, "reason": f"'ratings' must be a list with one list per player ({game.n})"}
    submitted = []
    for p, row in enumerate(ratings):
        if not isinstance(row, list) or len(row) != game.dims[p]:
            return {"ok": False, "reason": f"player {p} needs exactly {game.dims[p]} ratings"}
        values = [_real(v) for v in row]
        if any(v is None for v in values):
            return {"ok": False, "reason": f"player {p} has a rating that is not a finite real number"}
        submitted.append(values)
    equilibrium = entry.get("equilibrium")
    if not isinstance(equilibrium, list) or len(equilibrium) != game.size:
        return {"ok": False, "reason": f"'equilibrium' must be a flat list of {game.size} probabilities"}
    sigma = [_real(v) for v in equilibrium]
    if any(v is None for v in sigma):
        return {"ok": False, "reason": "equilibrium has an entry that is not a finite real number"}
    if min(sigma) < -TOL or max(sigma) > 1.0 + TOL:
        return {"ok": False, "reason": "equilibrium has an entry outside [0, 1]"}
    sigma = [max(v, 0.0) for v in sigma]
    total = math.fsum(sigma)
    if abs(total - 1.0) > TOL:
        return {"ok": False, "reason": f"equilibrium probabilities sum to {total!r}, not 1"}
    sigma = [v / total for v in sigma]
    gains = deviation_gains(game, sigma)
    scale = game.scale()
    max_gain = max(max(row) for row in gains)
    mismatch = max(abs(submitted[p][a] - gains[p][a]) for p in range(game.n) for a in range(game.dims[p]))
    info = {"max_gain": max_gain, "mismatch": mismatch, "scale": scale}
    if max_gain > TOL * scale:
        return dict(info, ok=False, reason=f"equilibrium is not a CCE (largest deviation gain {max_gain:.3e})")
    if mismatch > TOL * scale:
        return dict(
            info,
            ok=False,
            reason=f"ratings are not the deviation gains of the submitted equilibrium (mismatch {mismatch:.3e})",
        )
    return dict(info, ok=True, reason="", ratings=gains, cce_gap=cce_gap(gains))


# ── Metrics ─────────────────────────────────────────────────────────────────


View = Callable[[str], Tuple[List[List[float]], float]]


def _err(value: float, scale: float) -> float:
    """Absolute error, with differences below the numerical tolerance reported as 0."""
    value = abs(value)
    return 0.0 if value <= TOL * scale else value


def _gap(value: float, game: Game) -> float:
    return 0.0 if value <= TOL * game.scale() * game.n else value


def _spread(values: Iterable[float]) -> float:
    values = list(values)
    return max(values) - min(values)


def shapley_metrics(instances: List[dict], games: Dict[str, Game], view: View) -> Dict[str, float]:
    """Equality checks over the two players of the cyclic game (``inst["players"]``)."""
    out = {"dev_gap": 0.0, "all_player_dev_gap": 0.0, "player_symmetry_gap": 0.0, "CCE_gap": 0.0}
    for inst in instances:
        game = games[inst["game"]]
        scale = game.scale()
        ratings, gap = view(inst["game"])
        first, second = inst.get("players", (0, 1))
        cyclic = [ratings[first], ratings[second]]
        out["dev_gap"] = max(out["dev_gap"], _err(_spread(cyclic[0]), scale))
        out["all_player_dev_gap"] = max(
            out["all_player_dev_gap"], _err(_spread(v for row in cyclic for v in row), scale)
        )
        labels = inst["labels"]
        for a0, label0 in enumerate(labels[0]):
            for a1, label1 in enumerate(labels[1]):
                if label0 == label1:
                    out["player_symmetry_gap"] = max(
                        out["player_symmetry_gap"], _err(cyclic[0][a0] - cyclic[1][a1], scale)
                    )
        out["CCE_gap"] = max(out["CCE_gap"], _gap(gap, game))
    return out


def clone_metrics(instances: List[dict], games: Dict[str, Game], view: View) -> Dict[str, float]:
    out = {"max_diff": 0.0, "all_players_max_diff": 0.0, "clone_source_gap": 0.0}
    for inst in instances:
        base, variant = games[inst["base"]], games[inst["variant"]]
        scale = max(base.scale(), variant.scale())
        rb, _ = view(inst["base"])
        rv, _ = view(inst["variant"])
        player, maps = inst["player"], inst["maps"]
        for q in range(base.n):
            for action in range(base.dims[q]):
                diff = _err(rv[q][maps[q][action]] - rb[q][action], scale)
                out["all_players_max_diff"] = max(out["all_players_max_diff"], diff)
                if q != player:
                    out["max_diff"] = max(out["max_diff"], diff)
        source_gap = _err(rv[player][inst["clone_pos"]] - rv[player][maps[player][inst["source"]]], scale)
        out["clone_source_gap"] = max(out["clone_source_gap"], source_gap)
    return out


def mixture_metrics(instances: List[dict], games: Dict[str, Game], view: View) -> Dict[str, float]:
    out = {"original_max_diff": 0.0, "mixture_error": 0.0, "max_CCE_gap": 0.0}
    for inst in instances:
        base, variant = games[inst["base"]], games[inst["variant"]]
        scale = max(base.scale(), variant.scale())
        rb, gb = view(inst["base"])
        rv, gv = view(inst["variant"])
        player, maps = inst["player"], inst["maps"]
        for q in range(base.n):
            for action in range(base.dims[q]):
                out["original_max_diff"] = max(
                    out["original_max_diff"], _err(rv[q][maps[q][action]] - rb[q][action], scale)
                )
        expected = math.fsum(w * rb[player][a] for a, w in inst["weights"].items())
        out["mixture_error"] = max(out["mixture_error"], _err(rv[player][inst["mix_pos"]] - expected, scale))
        out["max_CCE_gap"] = max(out["max_CCE_gap"], _gap(gb, base), _gap(gv, variant))
    return out


def offset_metrics(instances: List[dict], games: Dict[str, Game], view: View) -> Dict[str, float]:
    out = {"max_diff": 0.0, "max_CCE_gap": 0.0}
    for inst in instances:
        base, variant = games[inst["base"]], games[inst["variant"]]
        scale = max(base.scale(), variant.scale())
        rb, gb = view(inst["base"])
        rv, gv = view(inst["variant"])
        maps = inst["maps"]
        for q in range(base.n):
            for action in range(base.dims[q]):
                out["max_diff"] = max(out["max_diff"], _err(rv[q][maps[q][action]] - rb[q][action], scale))
        out["max_CCE_gap"] = max(out["max_CCE_gap"], _gap(gb, base), _gap(gv, variant))
    return out


def dominance_metrics(instances: List[dict], games: Dict[str, Game], view: View) -> Dict[str, float]:
    violations = 0
    min_margin = math.inf
    worst_gap = 0.0
    for inst in instances:
        game = games[inst["game"]]
        ratings, gap = view(inst["game"])
        for player, better, worse, smallest in strict_dominance_pairs(game):
            margin = ratings[player][better] - ratings[player][worse]
            if margin <= TOL * game.scale():
                violations += 1
            min_margin = min(min_margin, margin / smallest)
        worst_gap = max(worst_gap, _gap(gap, game))
    return {
        "dominance_violations": violations,
        "min_margin": 0.0 if min_margin == math.inf else min_margin,
        "CCE_gap": worst_gap,
    }


METRIC_FUNCTIONS = {
    "biased_shapley_augmented": shapley_metrics,
    "clone_invariance": clone_metrics,
    "mixture_invariance": mixture_metrics,
    "offset_invariance": offset_metrics,
    "dominance_preserving": dominance_metrics,
}


def instance_game_ids(experiment: str, instances: List[dict]) -> List[str]:
    keys = ("game",) if experiment in ("biased_shapley_augmented", "dominance_preserving") else ("base", "variant")
    ids: List[str] = []
    for inst in instances:
        for key in keys:
            if inst[key] not in ids:
                ids.append(inst[key])
    return ids


def baseline_view(name: str, games: Dict[str, Game]) -> View:
    cache: Dict[str, Tuple[List[List[float]], float]] = {}

    def view(gid: str):
        if gid not in cache:
            game = games[gid]
            uniform = uniform_ratings(game)
            gap = cce_gap(deviation_gains(game, uniform_distribution(game)))
            if name == "uniform_payoff":
                ratings = uniform
            elif name == "zero_rating":
                ratings = [[0.0] * d for d in game.dims]
            elif name == "negative_uniform_payoff":
                ratings = [[-v for v in row] for row in uniform]
            else:
                raise KeyError(name)
            cache[gid] = (ratings, gap)
        return cache[gid]

    return view


def _finish(metrics: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for name, value in metrics.items():
        if name in INTEGER_METRICS:
            out[name] = int(value)
        else:
            out[name] = round(float(value), DECIMALS) + 0.0
    return out


def failed_metrics(experiment: str) -> Dict[str, float]:
    """Scores of an experiment whose outputs failed a validity gate: worst by a wide margin."""
    return _finish(
        {m: (FAIL_HIGHER if m in HIGHER_IS_BETTER else FAIL_LOWER) for m in EXPERIMENT_METRICS[experiment]}
    )


def score_suite(
    games: Dict[str, Game],
    instances: Dict[str, List[dict]],
    results: Optional[dict],
    error: str,
) -> Tuple[dict, dict]:
    """Return (scores, diagnostics) for one rater run on one suite."""
    checks = {}
    if results is not None:
        for gid, game in games.items():
            checks[gid] = validate_result(game, results.get(gid))
    valid_view: View = lambda gid: (checks[gid]["ratings"], checks[gid]["cce_gap"])
    scores = {"experiments": {}}
    diagnostics = {"rater_error": error, "experiments": {}}
    for experiment, insts in instances.items():
        gids = instance_game_ids(experiment, insts)
        if results is None:
            failures = [("*", error)]
        else:
            failures = [(gid, checks[gid]["reason"]) for gid in gids if not checks[gid]["ok"]]
        exp_results = {}
        if failures:
            exp_results[PROPOSED_ID] = failed_metrics(experiment)
        else:
            exp_results[PROPOSED_ID] = _finish(METRIC_FUNCTIONS[experiment](insts, games, valid_view))
        for baseline in BASELINES[experiment]:
            exp_results[baseline] = _finish(METRIC_FUNCTIONS[experiment](insts, games, baseline_view(baseline, games)))
        scores["experiments"][experiment] = {"results": exp_results}
        valid_infos = [checks[g] for g in gids if g in checks and "mismatch" in checks[g]]
        diagnostics["experiments"][experiment] = {
            "games": len(gids),
            "instances": len(insts),
            "failed_games": len(failures),
            "failure_reasons": sorted({reason for _, reason in failures})[:10],
            "max_rating_mismatch": max((c["mismatch"] for c in valid_infos), default=None),
            "max_deviation_gain": max((c["max_gain"] for c in valid_infos), default=None),
        }
    return scores, diagnostics


def print_report(scores: dict, diagnostics: dict, title: str) -> None:
    print(f"== {title} ==")
    if diagnostics.get("rater_error"):
        print(f"rating program failed: {diagnostics['rater_error']}")
    for experiment, entry in scores["experiments"].items():
        diag = diagnostics["experiments"][experiment]
        status = "FAILED" if diag["failed_games"] else "ok"
        print(f"[{experiment}] {diag['instances']} instances, {diag['games']} games, proposed method: {status}")
        for reason in diag["failure_reasons"]:
            print(f"    gate failure: {reason}")
        for method, metrics in entry["results"].items():
            print(f"    {method:<26} {json.dumps(metrics)}")


def write_scores(path: Path, scores: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        path.unlink()
    path.write_text(json.dumps(scores, indent=2))


# ── Benchmark game constructions ────────────────────────────────────────────


SHAPLEY_Q = 241.0
BIASED_SHAPLEY = [[-8.0, -2.0, 4.0], [2.0, -8.0, -1.0], [-4.0, 1.0, -8.0]]
SHAPLEY_NASH = [87.0 / SHAPLEY_Q, 100.0 / SHAPLEY_Q, 54.0 / SHAPLEY_Q]


def symmetric_population_game(matrix: List[List[float]], population: List[List[float]]) -> Game:
    """Symmetric two-player game where both players choose among mixtures of ``matrix``'s actions."""
    k = len(matrix)

    def value(x: List[float], y: List[float]) -> float:
        return math.fsum(x[i] * y[j] * matrix[i][j] for i in range(k) for j in range(k) if x[i] and y[j])

    size = len(population)
    return Game.from_function(
        (size, size),
        lambda p, joint: value(population[joint[0]], population[joint[1]])
        if p == 0
        else value(population[joint[1]], population[joint[0]]),
    )


def biased_shapley_augmented() -> Game:
    """Paper Table 2: biased Shapley game augmented with its Nash mixture N."""
    q = SHAPLEY_Q
    player0 = [
        [-8.0, -2.0, 4.0, -680.0 / q],
        [2.0, -8.0, -1.0, -680.0 / q],
        [-4.0, 1.0, -8.0, -680.0 / q],
        [-712.0 / q, -920.0 / q, -184.0 / q, -680.0 / q],
    ]
    return Game.from_function((4, 4), lambda p, j: player0[j[0]][j[1]] if p == 0 else player0[j[1]][j[0]])


def rock_paper_scissors() -> Game:
    m = [[0.0, -1.0, 1.0], [1.0, 0.0, -1.0], [-1.0, 1.0, 0.0]]
    return Game.from_function((3, 3), lambda p, j: m[j[0]][j[1]] if p == 0 else -m[j[0]][j[1]])


def general_sum_reference_game() -> Game:
    g0 = [[3.0, 0.0], [2.0, 1.0]]
    g1 = [[0.0, 1.0], [2.0, 3.0]]
    return Game.from_function((2, 2), lambda p, j: (g0 if p == 0 else g1)[j[0]][j[1]])


def dominance_test_game() -> Game:
    g0 = [[2.0, 2.0], [1.0, 1.0]]
    g1 = [[2.0, 1.0], [2.0, 1.0]]
    return Game.from_function((2, 2), lambda p, j: (g0 if p == 0 else g1)[j[0]][j[1]])

# ── Hidden test suite: generated here at test time; the seed lives only here ──


HIDDEN_SEED = 7_311_942_665
RPS_MATRIX = [[0.0, -1.0, 1.0], [1.0, 0.0, -1.0], [-1.0, 1.0, 0.0]]
# gs2/gs3: random general-sum 2/3-player games; zs2: zero-sum; cc2: common interest;
# by3: a random 2-player game plus a bystander (see _with_bystander).
CLONE_KINDS = ("gs2", "by3", "zs2", "gs3", "gs2", "cc2", "by3", "gs3", "zs2", "gs2", "by3", "gs3", "gs2",
               "cc2", "by3", "gs3", "zs2", "gs2", "by3", "gs3", "gs2", "by3", "gs2", "gs2", "gs3", "gs2")
MIXTURE_KINDS = ("gs2", "gs3", "by3", "zs2", "gs2", "cc2", "by3", "gs3", "gs2", "by3", "gs2", "zs2", "gs3",
                 "by3", "gs2", "gs2", "cc2", "gs3", "by3", "gs2", "zs2", "gs2", "gs3", "by3", "gs2", "gs2")
OFFSET_KINDS = ("gs2", "zs2", "by3", "gs3", "gs2", "cc2", "by3", "gs3", "gs2", "zs2", "by3", "gs2", "gs3",
                "gs2", "by3", "gs3", "cc2", "gs2", "by3", "zs2", "gs3", "gs2", "by3", "gs2", "gs2", "gs3")
DOMINANCE_KINDS = ("gs2", "gs3", "by3", "gs2", "gs2", "gs3", "by3", "gs2", "gs3", "gs2", "by3", "gs2",
                   "gs3", "gs2")


def _uniform_payoff(rng) -> float:
    return round(rng.uniform(-1.0, 1.0), 3) + 0.0


def _bystander_payoffs(rng, k: int) -> List[float]:
    while True:
        payoffs = [_uniform_payoff(rng) for _ in range(k)]
        if payoffs.count(max(payoffs)) == 1:
            return payoffs


def _with_bystander(rng, game: Game) -> Tuple[Game, int]:
    """Seat an extra player whose payoff depends only on its own action (1-3 actions).

    Its unique best action has deviation gain 0 at every CCE, which pins the first LP
    of Algorithm 1 at epsilon = 0; the other players' strictest CCE is then only found
    by the later iterations. Deviation ratings of the other players are unchanged by
    such a player, so every invariance and equality check still applies exactly.
    """
    k = rng.choice((1, 2, 3))
    seat = rng.randrange(game.n + 1)
    own = _bystander_payoffs(rng, k)
    dims = list(game.dims)
    dims.insert(seat, k)

    def payoff(p: int, joint: Tuple[int, ...]) -> float:
        if p == seat:
            return own[joint[seat]]
        return game.value(p if p < seat else p - 1, tuple(joint[:seat]) + tuple(joint[seat + 1 :]))

    return Game.from_function(dims, payoff), seat


def _random_game(rng, kind: str) -> Game:
    if kind == "by3":
        return _with_bystander(rng, _random_game(rng, "gs2"))[0]
    if kind == "gs3":
        dims = tuple(rng.choice((2, 3)) for _ in range(3))
    else:
        dims = (rng.choice((2, 3, 4)), rng.choice((2, 3, 4)))
    size = 1
    for d in dims:
        size *= d
    first = [_uniform_payoff(rng) for _ in range(size)]
    if kind == "zs2":
        tables = [first, [-v + 0.0 for v in first]]
    elif kind == "cc2":
        tables = [first, list(first)]
    else:
        tables = [first] + [[_uniform_payoff(rng) for _ in range(size)] for _ in range(len(dims) - 1)]
    return Game(dims, tables)


def _random_perms(rng, dims: Sequence[int]) -> List[List[int]]:
    perms = []
    for d in dims:
        perm = list(range(d))
        rng.shuffle(perm)
        perms.append(perm)
    return perms


def _composition(rng, k: int, total: int = 1000, minimum: int = 50) -> List[int]:
    free = total - k * minimum
    cuts = sorted(rng.randint(0, free) for _ in range(k - 1))
    edges = [0] + cuts + [free]
    return [edges[i + 1] - edges[i] + minimum for i in range(k)]


def _random_offsets(rng, game: Game) -> List[Dict[Tuple[int, ...], float]]:
    offsets = []
    for p in range(game.n):
        others = [range(d) for q, d in enumerate(game.dims) if q != p]
        offsets.append({joint: round(rng.uniform(-5.0, 5.0), 3) + 0.0 for joint in itertools.product(*others)})
    return offsets


class _Suite:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.id_rng = random.Random(seed ^ 0x5DEECE66D)
        self.games: Dict[str, Game] = {}
        self.instances: Dict[str, List[dict]] = {name: [] for name in METRIC_FUNCTIONS}

    def add(self, game: Game) -> str:
        while True:
            gid = f"{self.id_rng.getrandbits(48):012x}"
            if gid not in self.games:
                self.games[gid] = game
                return gid


def _shapley_family(suite: _Suite) -> None:
    rng = suite.rng
    pure3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def mixture3() -> List[float]:
        return [x / 1000.0 for x in _composition(rng, 3)]

    def add(matrix, population, labels, offsets=False, scale=None, clone=False, bystander=False):
        game = symmetric_population_game(matrix, population)
        labs = [list(labels), list(labels)]
        players = [0, 1]
        if scale is not None:
            game = Game(game.dims, [[v * scale for v in t] for t in game.tables])
        if bystander:
            game, seat = _with_bystander(rng, game)
            labs.insert(seat, [f"b{a}" for a in range(game.dims[seat])])
            players = [p if p < seat else p + 1 for p in players]
        if offsets:
            game = add_offsets(game, _random_offsets(rng, game))
        if clone:
            p = rng.choice(players)
            source = rng.randrange(game.dims[p])
            position = rng.randrange(game.dims[p] + 1)
            game, maps = clone_action(game, p, source, position)
            new_labels = [None] * game.dims[p]
            for action, label in enumerate(labs[p]):
                new_labels[maps[p][action]] = label
            new_labels[position] = labs[p][source]
            labs[p] = new_labels
        perms = _random_perms(rng, game.dims)
        game, _ = permute_actions(game, perms)
        labs = [[labs[p][perms[p][pos]] for pos in range(game.dims[p])] for p in range(game.n)]
        suite.instances["biased_shapley_augmented"].append(
            {"game": suite.add(game), "players": players, "labels": [labs[p] for p in players]}
        )

    rpsn = pure3 + [SHAPLEY_NASH]
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"])
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"], offsets=True)
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"], scale=round(rng.uniform(0.5, 3.0), 2))
    add(BIASED_SHAPLEY, pure3, ["R", "P", "S"])
    add(BIASED_SHAPLEY, pure3 + [mixture3() for _ in range(3)], ["R", "P", "S", "m0", "m1", "m2"])
    add(BIASED_SHAPLEY, rpsn + [mixture3() for _ in range(2)], ["R", "P", "S", "N", "m0", "m1"], offsets=True)
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"], clone=True)
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"], bystander=True)
    add(BIASED_SHAPLEY, pure3 + [mixture3() for _ in range(2)], ["R", "P", "S", "m0", "m1"],
        offsets=True, bystander=True)
    add(BIASED_SHAPLEY, rpsn, ["R", "P", "S", "N"], clone=True, bystander=True)
    add(RPS_MATRIX, pure3, ["R", "P", "S"])
    for with_offsets in (False, True):
        a, b, c = (round(rng.uniform(0.5, 3.0), 2) for _ in range(3))
        weighted = [[0.0, -a, b], [a, 0.0, -c], [-b, c, 0.0]]
        add(weighted, pure3, ["R", "P", "S"], offsets=with_offsets)
    rpsls = [[0.0 if i == j else (1.0 if (i - j) % 5 in (1, 2) else -1.0) for j in range(5)] for i in range(5)]
    add(rpsls, [[1.0 if i == k else 0.0 for i in range(5)] for k in range(5)], ["a0", "a1", "a2", "a3", "a4"])
    a, b, c = (round(rng.uniform(0.5, 3.0), 2) for _ in range(3))
    weighted = [[0.0, -a, b], [a, 0.0, -c], [-b, c, 0.0]]
    add(weighted, pure3 + [mixture3() for _ in range(2)], ["R", "P", "S", "m0", "m1"])


def _clone_family(suite: _Suite) -> None:
    rng = suite.rng
    for kind in CLONE_KINDS:
        base = _random_game(rng, kind)
        player = rng.randrange(base.n)
        source = rng.randrange(base.dims[player])
        position = rng.randrange(base.dims[player] + 1)
        cloned, first = clone_action(base, player, source, position)
        variant, second = permute_actions(cloned, _random_perms(rng, cloned.dims))
        suite.instances["clone_invariance"].append(
            {
                "base": suite.add(base),
                "variant": suite.add(variant),
                "player": player,
                "source": source,
                "clone_pos": second[player][position],
                "maps": compose_maps(first, second),
            }
        )


def _mixture_family(suite: _Suite) -> None:
    rng = suite.rng
    for kind in MIXTURE_KINDS:
        base = _random_game(rng, kind)
        player = rng.choice([p for p in range(base.n) if base.dims[p] >= 2])
        k = rng.randint(2, base.dims[player])
        support = sorted(rng.sample(range(base.dims[player]), k))
        weights = {a: w / 1000.0 for a, w in zip(support, _composition(rng, k))}
        position = rng.randrange(base.dims[player] + 1)
        mixed, first = mixture_action(base, player, weights, position)
        variant, second = permute_actions(mixed, _random_perms(rng, mixed.dims))
        suite.instances["mixture_invariance"].append(
            {
                "base": suite.add(base),
                "variant": suite.add(variant),
                "player": player,
                "weights": weights,
                "mix_pos": second[player][position],
                "maps": compose_maps(first, second),
            }
        )


def _offset_family(suite: _Suite) -> None:
    rng = suite.rng
    for kind in OFFSET_KINDS:
        base = _random_game(rng, kind)
        shifted = add_offsets(base, _random_offsets(rng, base))
        variant, maps = permute_actions(shifted, _random_perms(rng, shifted.dims))
        suite.instances["offset_invariance"].append(
            {"base": suite.add(base), "variant": suite.add(variant), "maps": maps}
        )


def _plant_dominated_action(rng, game: Game) -> Game:
    """Add an action that is strictly dominated, by a constant gap, by an existing one."""
    player = rng.randrange(game.n)
    better = rng.randrange(game.dims[player])
    delta = round(rng.uniform(0.25, 2.0), 2)
    position = rng.randrange(game.dims[player] + 1)
    others = [range(d) for q, d in enumerate(game.dims) if q != player]
    fresh = {
        q: {joint: _uniform_payoff(rng) for joint in itertools.product(*others)}
        for q in range(game.n)
        if q != player
    }

    def payoff(q, joint, game=game, player=player, better=better, delta=delta, fresh=fresh):
        if q == player:
            source = list(joint)
            source[player] = better
            return game.value(player, tuple(source)) - delta
        return fresh[q][tuple(joint[:player]) + tuple(joint[player + 1 :])]

    planted, _ = insert_action(game, player, position, payoff)
    return planted


def _dominance_family(suite: _Suite) -> None:
    rng = suite.rng
    for kind in DOMINANCE_KINDS:
        game = _random_game(rng, kind)
        for _ in range(rng.choice((1, 2))):
            game = _plant_dominated_action(rng, game)
        game, _ = permute_actions(game, _random_perms(rng, game.dims))
        suite.instances["dominance_preserving"].append({"game": suite.add(game)})
    public, _ = permute_actions(dominance_test_game(), _random_perms(rng, (2, 2)))
    suite.instances["dominance_preserving"].append({"game": suite.add(public)})


# ── Population improvement (paper Section 5.3) ──────────────────────────────
#
# A rating drives a simple population search in an extensive-form game: start
# with POP_SIZE random stochastic policies per player; every iteration build the
# meta-game of expected payoffs between the policies, rate it, discard each
# player's POP_DROP lowest-rated policies (the bottom quarter) and replace them
# by fresh random policies. Progress is the CCE gap of the population in the
# full game, measured under the meta-game's maximum-entropy CCE (paper footnote
# 6), relative to the gap of the initial population. Everything except the
# ratings (game, policies, replacement stream, tie-breaking, meta-game
# distribution, the scored gap) is fixed here, and every method sees the same
# stream of candidate policies.
#
# Every meta-game the method rates is presented with its actions relabeled and
# together with a clone-, mixture- or offset-transformed copy. The selection
# must use a rating that is invariant on the very games it rates: a violation
# beyond the tolerance fails the experiment, like any other gate.


POPULATION_EXPERIMENT = "population_improvement"
POP_SIZE = 8
POP_DROP = 2
POP_ITERATIONS = 128
POP_CHECKPOINT_EVERY = 16
POP_RUNS = 8
MECCE_EPS_REL = 1.0e-4
POP_CALL_TIMEOUT_SECONDS = 300
POP_TOTAL_SECONDS = 1800
# Paper Appendix C.1: item penalty 1, item value 5, max bribe 2, max items 10,
# 2 rounds, sheriff penalty 1 (OpenSpiel "sheriff" rules).
SHERIFF_PARAMETERS = {"item_penalty": 1.0, "item_value": 5.0, "sheriff_penalty": 1.0,
                      "max_bribe": 2, "max_items": 10, "num_rounds": 2}


def _mix(*parts: int) -> int:
    value = 0x9E3779B97F4A7C15
    for part in parts:
        value = (value * 1_000_003 + int(part) + 0x632BE59BD9B4E019) % (1 << 61)
    return value


class Sheriff:
    """Two-player general-sum bargaining game (OpenSpiel ``sheriff``, Farina et al. 2019).

    Player 0 (smuggler) loads 0..max_items illegal items, unseen by player 1
    (sheriff). Each of num_rounds rounds: the smuggler announces a bribe in
    0..max_bribe, the sheriff announces not-inspect (0) or inspect (1). Only the
    last round counts: not inspected -> (items*value - bribe, bribe); inspected
    with items -> (-items*penalty, items*penalty); inspected and empty ->
    (sheriff_penalty, -sheriff_penalty).
    """

    def __init__(self, item_penalty: float, item_value: float, sheriff_penalty: float,
                 max_bribe: int, max_items: int, num_rounds: int):
        self.params = (float(item_penalty), float(item_value), float(sheriff_penalty),
                       int(max_bribe), int(max_items), int(num_rounds))
        self._keys: List[Dict[tuple, int]] = [{}, {}]
        self.info_actions: List[List[int]] = [[], []]
        self.node_player: List[int] = []
        self.node_info: List[int] = []
        self.node_children: List[List[int]] = []
        self.node_depth: List[int] = []
        self.node_terminal: List[int] = []
        self.term_paths: List[List[List[Tuple[int, int]]]] = [[], []]
        self.term_payoffs: List[List[float]] = [[], []]
        self._build(0, None, (), (), ())
        self.num_terminals = len(self.term_payoffs[0])
        self._levels: Dict[int, List[int]] = {}
        for node, depth in enumerate(self.node_depth):
            self._levels.setdefault(depth, []).append(node)

    def _info(self, player: int, key: tuple, actions: int) -> int:
        table = self._keys[player]
        if key not in table:
            table[key] = len(self.info_actions[player])
            self.info_actions[player].append(actions)
        return table[key]

    def _node(self, player: int, info: int, depth: int) -> int:
        self.node_player.append(player)
        self.node_info.append(info)
        self.node_children.append([])
        self.node_depth.append(depth)
        self.node_terminal.append(-1)
        return len(self.node_player) - 1

    def _build(self, depth, items, bribes, feedback, path) -> int:
        penalty, value, sheriff_penalty, max_bribe, max_items, rounds = self.params
        if items is None:
            info = self._info(0, ("items",), max_items + 1)
            node = self._node(0, info, depth)
            for n in range(max_items + 1):
                self.node_children[node].append(self._build(depth + 1, n, (), (), path + ((0, info, n),)))
            return node
        if len(bribes) == len(feedback):
            if len(bribes) == rounds:
                node = self._node(-1, -1, depth)
                self.node_terminal[node] = len(self.term_payoffs[0])
                bribe, inspect = bribes[-1], feedback[-1]
                if inspect:
                    pay = (-items * penalty, items * penalty) if items > 0 else (sheriff_penalty, -sheriff_penalty)
                else:
                    pay = (items * value - bribe, float(bribe))
                for p in (0, 1):
                    self.term_payoffs[p].append(float(pay[p]) + 0.0)
                    self.term_paths[p].append([(i, a) for q, i, a in path if q == p])
                return node
            info = self._info(0, ("bribe", items, bribes, feedback), max_bribe + 1)
            node = self._node(0, info, depth)
            for b in range(max_bribe + 1):
                self.node_children[node].append(
                    self._build(depth + 1, items, bribes + (b,), feedback, path + ((0, info, b),))
                )
            return node
        info = self._info(1, ("inspect", bribes, feedback), 2)
        node = self._node(1, info, depth)
        for f in (0, 1):
            self.node_children[node].append(
                self._build(depth + 1, items, bribes, feedback + (f,), path + ((1, info, f),))
            )
        return node

    def random_policy(self, rng: random.Random, player: int) -> List[List[float]]:
        """A behaviour policy with each information set's distribution uniform on the simplex."""
        policy = []
        for actions in self.info_actions[player]:
            draws = [-math.log(1.0 - rng.random()) for _ in range(actions)]
            total = math.fsum(draws)
            policy.append([d / total for d in draws])
        return policy

    def realization(self, player: int, policy: List[List[float]]) -> array:
        """Probability that ``player``'s own actions lead to each terminal history."""
        out = array("d")
        for path in self.term_paths[player]:
            prob = 1.0
            for info, action in path:
                prob *= policy[info][action]
            out.append(prob)
        return out

    def best_response_value(self, player: int, opponent_reach: Sequence[float]) -> float:
        """max over deterministic policies of sum_z own(z) * opponent_reach(z) * u_player(z)."""
        values = [0.0] * len(self.node_player)
        payoff = self.term_payoffs[player]
        for depth in sorted(self._levels, reverse=True):
            nodes = self._levels[depth]
            q: Dict[int, List[float]] = {}
            for node in nodes:
                terminal = self.node_terminal[node]
                if terminal >= 0:
                    values[node] = opponent_reach[terminal] * payoff[terminal]
                elif self.node_player[node] == player:
                    row = q.setdefault(self.node_info[node], [0.0] * len(self.node_children[node]))
                    for action, child in enumerate(self.node_children[node]):
                        row[action] += values[child]
                else:
                    values[node] = math.fsum(values[child] for child in self.node_children[node])
            best = {info: max(range(len(row)), key=row.__getitem__) for info, row in q.items()}
            for node in nodes:
                if self.node_terminal[node] < 0 and self.node_player[node] == player:
                    values[node] = values[self.node_children[node][best[self.node_info[node]]]]
        return values[0]


def _cce_rows(game: Game) -> List[List[float]]:
    rows = []
    for p in range(game.n):
        table, stride, own = game.tables[p], game.strides[p], game._own[p]
        for action in range(game.dims[p]):
            rows.append([table[j + (action - own[j]) * stride] - table[j] for j in range(game.size)])
    return rows


def _solve_spd(matrix: List[List[float]], rhs: List[float]) -> Optional[List[float]]:
    size = len(rhs)
    low = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1):
            total = matrix[i][j] - math.fsum(low[i][k] * low[j][k] for k in range(j))
            if i == j:
                if not total > 0.0:
                    return None
                low[i][i] = math.sqrt(total)
            else:
                low[i][j] = total / low[j][j]
    y = [0.0] * size
    for i in range(size):
        y[i] = (rhs[i] - math.fsum(low[i][k] * y[k] for k in range(i))) / low[i][i]
    x = [0.0] * size
    for i in range(size - 1, -1, -1):
        x[i] = (y[i] - math.fsum(low[k][i] * x[k] for k in range(i + 1, size))) / low[i][i]
    return x


def max_entropy_cce(game: Game, eps_rel: float = MECCE_EPS_REL, max_iter: int = 400) -> List[float]:
    """Maximum-entropy eps-CCE of ``game`` (eps = eps_rel * payoff scale).

    Solves the dual min_{lam >= 0} log sum_a exp(-sum_c lam_c A_c(a)) + eps * sum(lam)
    by projected Newton with a trust region on the change of log-probabilities.
    The small eps keeps the problem strictly feasible; the paper uses eps = 0.
    """
    rows = _cce_rows(game)
    m, size = len(rows), game.size
    cols = [[rows[c][j] for c in range(m)] for j in range(size)]
    eps = eps_rel * game.scale()
    tol = 1.0e-9 * game.scale()
    mul = operator.mul

    def evaluate(lam):
        logits = [-sum(map(mul, lam, col)) for col in cols]
        top = max(logits)
        weights = [math.exp(v - top) for v in logits]
        total = math.fsum(weights)
        sigma = [w / total for w in weights]
        mean = [sum(map(mul, row, sigma)) for row in rows]
        return math.log(total) + top + eps * math.fsum(lam), [eps - v for v in mean], sigma, mean

    lam = [0.0] * m
    value, grad, sigma, mean = evaluate(lam)
    for _ in range(max_iter):
        if max(abs(grad[c]) if lam[c] > 0.0 else max(0.0, -grad[c]) for c in range(m)) <= tol:
            break
        free = [c for c in range(m) if not (lam[c] == 0.0 and grad[c] > 0.0)]
        step = [0.0] * m
        if free:
            weighted = [[sigma[j] * rows[c][j] for j in range(size)] for c in free]
            hess = [[sum(map(mul, weighted[a], rows[free[b]])) - mean[free[a]] * mean[free[b]]
                     for b in range(len(free))] for a in range(len(free))]
            ridge = 1.0e-12 * max(max(hess[a][a] for a in range(len(free))), 1.0e-300)
            solution = None
            while solution is None:
                shifted = [[hess[a][b] + (ridge if a == b else 0.0) for b in range(len(free))]
                           for a in range(len(free))]
                solution = _solve_spd(shifted, [-grad[c] for c in free])
                ridge *= 100.0
            for a, c in enumerate(free):
                step[c] = solution[a]
            if math.fsum(grad[c] * step[c] for c in free) >= 0.0:
                step = [(-grad[c] if c in free else 0.0) for c in range(m)]
        change = [-sum(map(mul, step, col)) for col in cols]
        spread = max(change) - min(change)
        t = 1.0 if spread <= 4.0 else 4.0 / spread
        accepted = False
        for _ in range(60):
            trial = [max(0.0, lam[c] + t * step[c]) for c in range(m)]
            t_value, t_grad, t_sigma, t_mean = evaluate(trial)
            decrease = math.fsum(grad[c] * (lam[c] - trial[c]) for c in range(m))
            if t_value <= value - 1.0e-4 * decrease and t_value <= value:
                accepted = True
                break
            t *= 0.5
        if not accepted:
            break
        lam, value, grad, sigma, mean = trial, t_value, t_grad, t_sigma, t_mean
    return sigma


class _CandidatePool:
    """Stream of random candidate policies for one run, shared by every method."""

    def __init__(self, sheriff: Sheriff, seed: int, count: int):
        self.reach: List[List[array]] = [[], []]
        self.weighted: List[List[array]] = []  # smuggler realization times each player's payoff
        for player in (0, 1):
            rng = random.Random(_mix(seed, player))
            for _ in range(count):
                self.reach[player].append(sheriff.realization(player, sheriff.random_policy(rng, player)))
        payoffs = sheriff.term_payoffs
        self.weighted = [
            [array("d", map(operator.mul, r, payoffs[p])) for p in (0, 1)] for r in self.reach[0]
        ]


class _Population:
    def __init__(self, pool: _CandidatePool):
        self.pool = pool
        self.members = [list(range(POP_SIZE)), list(range(POP_SIZE))]
        self.next = [POP_SIZE, POP_SIZE]
        self.tables = [[0.0] * (POP_SIZE * POP_SIZE) for _ in (0, 1)]
        for i in range(POP_SIZE):
            for j in range(POP_SIZE):
                self._entry(i, j)

    def _entry(self, i: int, j: int) -> None:
        smuggler = self.pool.weighted[self.members[0][i]]
        sheriff = self.pool.reach[1][self.members[1][j]]
        for p in (0, 1):
            self.tables[p][i * POP_SIZE + j] = sum(map(operator.mul, smuggler[p], sheriff)) + 0.0

    def game(self) -> Game:
        return Game((POP_SIZE, POP_SIZE), self.tables)

    def replace(self, player: int, slots: Sequence[int]) -> None:
        for slot in slots:
            self.members[player][slot] = self.next[player]
            self.next[player] += 1
            for other in range(POP_SIZE):
                self._entry(slot, other) if player == 0 else self._entry(other, slot)

    def full_game_gap(self, sheriff: Sheriff) -> float:
        """CCE gap in the full game of the meta-game's maximum-entropy CCE."""
        game = self.game()
        sigma = max_entropy_cce(game)
        marg = [[math.fsum(sigma[i * POP_SIZE + j] for j in range(POP_SIZE)) for i in range(POP_SIZE)],
                [math.fsum(sigma[i * POP_SIZE + j] for i in range(POP_SIZE)) for j in range(POP_SIZE)]]
        gap = 0.0
        for p in (0, 1):
            opponent = 1 - p
            reach = [0.0] * sheriff.num_terminals
            for slot, member in enumerate(self.members[opponent]):
                weight = marg[opponent][slot]
                if weight > 0.0:
                    vec = self.pool.reach[opponent][member]
                    reach = [r + weight * v for r, v in zip(reach, vec)]
            current = math.fsum(s * v for s, v in zip(sigma, game.tables[p]))
            gap += max(0.0, sheriff.best_response_value(p, reach) - current)
        return gap


def _drop_slots(ratings: Sequence[float], keys: Sequence[float], scale: float) -> List[int]:
    """The POP_DROP lowest-rated slots; ratings within the tolerance tie, ties are broken by ``keys``."""
    order = sorted(range(len(ratings)), key=lambda a: ratings[a])
    groups: List[List[int]] = []
    for slot in order:
        if groups and ratings[slot] - ratings[groups[-1][0]] <= TOL * scale:
            groups[-1].append(slot)
        else:
            groups.append([slot])
    ranked = [slot for group in groups for slot in sorted(group, key=lambda a: keys[a])]
    return ranked[:POP_DROP]


def _present(game: Game, rng: random.Random) -> dict:
    """Relabel the meta-game and build one clone-, mixture- or offset-transformed copy."""
    perms = _random_perms(rng, game.dims)
    presented, to_presented = permute_actions(game, perms)
    kind = rng.choice(("clone", "mixture", "offset"))
    player = rng.randrange(game.n)
    inst = {"game": game, "presented": presented, "to_presented": to_presented, "kind": kind, "player": player}
    if kind == "clone":
        source = rng.randrange(game.dims[player])
        position = rng.randrange(game.dims[player] + 1)
        variant, first = clone_action(game, player, source, position)
        inst["source"] = source
    elif kind == "mixture":
        k = rng.choice((2, 3))
        support = sorted(rng.sample(range(game.dims[player]), k))
        inst["weights"] = {a: w / 1000.0 for a, w in zip(support, _composition(rng, k))}
        position = rng.randrange(game.dims[player] + 1)
        variant, first = mixture_action(game, player, inst["weights"], position)
    else:
        bound = round(game.scale(), 3)
        offsets = []
        for p in range(game.n):
            others = [range(d) for q, d in enumerate(game.dims) if q != p]
            offsets.append({joint: round(rng.uniform(-bound, bound), 3) + 0.0 for joint in itertools.product(*others)})
        variant, first, position = add_offsets(game, offsets), identity_maps(game), None
    inst["variant"], second = permute_actions(variant, _random_perms(rng, variant.dims))
    inst["maps"] = compose_maps(first, second)
    if position is not None:
        inst["new_pos"] = second[player][position]
    return inst


def _invariance_violation(inst: dict, original: List[List[float]], variant: List[List[float]]) -> float:
    game = inst["game"]
    scale = max(game.scale(), inst["variant"].scale())
    worst = 0.0
    for p in range(game.n):
        for action in range(game.dims[p]):
            worst = max(worst, _err(variant[p][inst["maps"][p][action]] - original[p][action], scale))
    player = inst["player"]
    if inst["kind"] == "clone":
        worst = max(worst, _err(variant[player][inst["new_pos"]] - original[player][inst["source"]], scale))
    elif inst["kind"] == "mixture":
        expected = math.fsum(w * original[player][a] for a, w in inst["weights"].items())
        worst = max(worst, _err(variant[player][inst["new_pos"]] - expected, scale))
    return worst


class PopulationFailure(Exception):
    pass


def _rate_with_program(call: Callable[[Dict[str, Game], List[str]], Tuple[Optional[dict], str]], seed: int):
    """Rating step for a rating program: ``call(games, order) -> (results, error)``."""
    id_rng = random.Random(_mix(seed, 0x1D))

    def rate(batch: List[dict]) -> Tuple[List[List[List[float]]], float]:
        games: Dict[str, Game] = {}
        for inst in batch:
            for key in ("presented", "variant"):
                while True:
                    gid = f"{id_rng.getrandbits(48):012x}"
                    if gid not in games:
                        break
                games[gid] = inst[key]
                inst[key + "_id"] = gid
        order = list(games)
        id_rng.shuffle(order)
        results, error = call(games, order)
        if results is None:
            raise PopulationFailure(error)
        out, worst = [], 0.0
        for inst in batch:
            checks = {}
            for key in ("presented", "variant"):
                checks[key] = validate_result(inst[key], results.get(inst[key + "_id"]))
                if not checks[key]["ok"]:
                    raise PopulationFailure(checks[key]["reason"])
            to_presented = inst["to_presented"]
            presented = checks["presented"]["ratings"]
            original = [[presented[p][to_presented[p][a]] for a in range(inst["game"].dims[p])]
                        for p in range(inst["game"].n)]
            violation = _invariance_violation(inst, original, checks["variant"]["ratings"])
            if violation > 0.0:
                raise PopulationFailure(
                    f"ratings change under a {inst['kind']} of a population meta-game (by {violation:.3e})"
                )
            out.append(original)
        return out, worst

    return rate


def _rate_uniform(batch: List[dict]) -> Tuple[List[List[List[float]]], float]:
    out, worst = [], 0.0
    for inst in batch:
        original = uniform_ratings(inst["game"])
        worst = max(worst, _invariance_violation(inst, original, uniform_ratings(inst["variant"])))
        out.append(original)
    return out, worst


def _rate_random(batch: List[dict]) -> Tuple[List[List[List[float]]], float]:
    return [[[0.0] * d for d in inst["game"].dims] for inst in batch], 0.0


def population_loop(sheriff: Sheriff, pools: List[_CandidatePool], seed: int, rate) -> Tuple[List[List[float]], float]:
    """Run the improvement loop on every run in lockstep; returns (gap curves, invariance violation)."""
    populations = [_Population(pool) for pool in pools]
    curves = [[pop.full_game_gap(sheriff)] for pop in populations]
    worst = 0.0
    for iteration in range(1, POP_ITERATIONS + 1):
        batch = []
        for run, pop in enumerate(populations):
            batch.append(_present(pop.game(), random.Random(_mix(seed, run, iteration, 1))))
        ratings, violation = rate(batch)
        worst = max(worst, violation)
        for run, pop in enumerate(populations):
            scale = batch[run]["game"].scale()
            key_rng = random.Random(_mix(seed, run, iteration, 2))
            for player in (0, 1):
                keys = [key_rng.random() for _ in range(POP_SIZE)]
                pop.replace(player, _drop_slots(ratings[run][player], keys, scale))
        if iteration % POP_CHECKPOINT_EVERY == 0:
            for run, pop in enumerate(populations):
                curves[run].append(pop.full_game_gap(sheriff))
    return curves, worst


def population_metrics(curves: List[List[float]], violation: float) -> Dict[str, float]:
    initial = math.fsum(curve[0] for curve in curves) / len(curves)
    final = math.fsum(curve[-1] for curve in curves) / len(curves)
    later = [v for curve in curves for v in curve[1:]]
    return {
        "final_gap_ratio": final / initial,
        "mean_gap_ratio": math.fsum(later) / len(later) / initial,
        "invariance_violation": violation,
    }


def make_pools(seed: int, runs: int = POP_RUNS) -> Tuple[Sheriff, List[_CandidatePool]]:
    sheriff = Sheriff(**SHERIFF_PARAMETERS)
    count = POP_SIZE + POP_DROP * POP_ITERATIONS
    return sheriff, [_CandidatePool(sheriff, _mix(seed, run), count) for run in range(runs)]


def evaluate_population(seed: int, command: Optional[Sequence[str]] = None) -> Tuple[dict, dict]:
    """Score the rating program and the evaluator's baselines on the improvement loop."""
    sheriff, pools = make_pools(seed)
    deadline = time.monotonic() + POP_TOTAL_SECONDS
    calls = {"count": 0}

    def call(games, order):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, f"population experiment exceeded {POP_TOTAL_SECONDS} s"
        calls["count"] += 1
        results, error, log_tail = run_rater(games, order, command=command,
                                             timeout=min(POP_CALL_TIMEOUT_SECONDS, remaining))
        if error and log_tail:
            print("rating program output (tail):")
            print(log_tail)
        return results, error

    results = {}
    diagnostics = {"rater_calls": 0, "failure": ""}
    try:
        curves, violation = population_loop(sheriff, pools, seed, _rate_with_program(call, seed))
        results[PROPOSED_ID] = _finish(population_metrics(curves, violation))
        diagnostics["curves"] = {PROPOSED_ID: _mean_curve(curves)}
    except PopulationFailure as failure:
        results[PROPOSED_ID] = failed_metrics(POPULATION_EXPERIMENT)
        diagnostics["failure"] = str(failure)
        diagnostics["curves"] = {}
    diagnostics["rater_calls"] = calls["count"]
    for name, rate in (("uniform_payoff", _rate_uniform), ("random_selection", _rate_random)):
        curves, violation = population_loop(sheriff, pools, seed, rate)
        results[name] = _finish(population_metrics(curves, violation))
        diagnostics["curves"][name] = _mean_curve(curves)
    return {"results": results}, diagnostics


def _mean_curve(curves: List[List[float]]) -> List[float]:
    return [round(math.fsum(c[i] for c in curves) / len(curves), 4) for i in range(len(curves[0]))]


def build_hidden_suite(seed: int = HIDDEN_SEED) -> Tuple[Dict[str, Game], Dict[str, List[dict]], List[str]]:
    suite = _Suite(seed)
    _shapley_family(suite)
    _clone_family(suite)
    _mixture_family(suite)
    _offset_family(suite)
    _dominance_family(suite)
    order = list(suite.games)
    suite.rng.shuffle(order)
    return suite.games, suite.instances, order


def evaluate_hidden(seed: int = HIDDEN_SEED, command: Optional[Sequence[str]] = None) -> Tuple[dict, dict]:
    games, instances, order = build_hidden_suite(seed)
    results, error, log_tail = run_rater(games, order, command=command)
    if error and log_tail:
        print("rating program output (tail):")
        print(log_tail)
    scores, diagnostics = score_suite(games, instances, results, error)
    population, pop_diag = evaluate_population(_mix(seed, 0x50), command=command)
    scores["experiments"][POPULATION_EXPERIMENT] = population
    diagnostics["population"] = pop_diag
    return scores, diagnostics


def print_population(scores: dict, diagnostics: dict) -> None:
    diag = diagnostics["population"]
    status = "FAILED" if diag["failure"] else "ok"
    print(f"[{POPULATION_EXPERIMENT}] Sheriff, {POP_RUNS} runs x {POP_ITERATIONS} iterations, "
          f"{diag['rater_calls']} rating-program calls, proposed method: {status}")
    if diag["failure"]:
        print(f"    gate failure: {diag['failure']}")
    for method, metrics in scores["experiments"][POPULATION_EXPERIMENT]["results"].items():
        print(f"    {method:<26} {json.dumps(metrics)}")
    for method, curve in diag["curves"].items():
        print(f"    mean full-game CCE gap every {POP_CHECKPOINT_EVERY} iterations, {method}: {curve}")


def main() -> dict:
    scores_path = ROOT / "scoring" / "scores_test.json"
    if scores_path.exists() or scores_path.is_symlink():
        scores_path.unlink()
    scores, diagnostics = evaluate_hidden()
    print_report(
        {"experiments": {k: v for k, v in scores["experiments"].items() if k != POPULATION_EXPERIMENT}},
        diagnostics,
        "hidden test",
    )
    print_population(scores, diagnostics)
    write_scores(scores_path, scores)
    print(f"Test evaluation complete. Results written to {scores_path}")
    return scores


if __name__ == "__main__":
    main()
