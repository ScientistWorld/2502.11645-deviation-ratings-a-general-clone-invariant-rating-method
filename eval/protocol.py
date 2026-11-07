"""Method-agnostic scoring protocol for the visible evaluators.

Standard library only. ``eval/test/evaluate.py`` carries its own copy of this
machinery so the hidden test never imports anything a submission can edit.

Rating-method contract
----------------------
A rating method is the program ``scripts/rate.sh GAMES_JSON RATINGS_JSON``.

``GAMES_JSON`` (written by the evaluator)::

    {"games": [{"id": "<opaque id>", "payoffs": P}, ...]}

``P`` is a nested list of shape ``[N, A_1, ..., A_N]``: ``P[p][a_1]...[a_N]``
is player ``p``'s payoff at joint action ``(a_1, ..., a_N)``.

``RATINGS_JSON`` (written by the method)::

    {"results": {"<id>": {"ratings": R, "equilibrium": S}, ...}}

``R[p][a]`` is the rating of player ``p``'s action ``a`` (one list per player,
one real number per action). ``S`` is the selected joint distribution as a
flat list of ``A_1 * ... * A_N`` probabilities in C (row-major) order.

Checks applied to every game before any metric is computed (a game that fails
any check fails every experiment it belongs to):

* every rating and probability is a finite JSON number (no NaN/Infinity, no
  strings, no booleans, no nulls), with exactly one rating per action;
* the distribution is non-negative (>= -1e-6) and sums to 1 within 1e-6;
* the distribution is a coarse correlated equilibrium: every deviation gain
  is <= 1e-6 * payoff scale;
* the ratings are the deviation gains of that distribution,
  ``R[p][a'] = sum_a S(a) [G_p(a', a_-p) - G_p(a)]``, within 1e-6 * payoff
  scale.

Scored numbers are always recomputed from the payoffs and the submitted
distribution; numbers the method reports are only compared, never used.
"""

from __future__ import annotations

import ctypes
import itertools
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import tempfile
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
}
HIGHER_IS_BETTER = frozenset({"min_margin"})
INTEGER_METRICS = frozenset({"dominance_violations"})
BASELINES: Dict[str, Tuple[str, ...]] = {
    "biased_shapley_augmented": ("uniform_payoff",),
    "clone_invariance": ("uniform_payoff",),
    "mixture_invariance": ("uniform_payoff",),
    "offset_invariance": ("uniform_payoff",),
    "dominance_preserving": ("uniform_payoff", "zero_rating", "negative_uniform_payoff"),
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


# ── Public (visible) benchmark games ────────────────────────────────────────


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


def public_suite() -> Tuple[Dict[str, Game], Dict[str, List[dict]], List[str]]:
    """The five documented train/visible experiments."""
    games: Dict[str, Game] = {}
    instances: Dict[str, List[dict]] = {name: [] for name in EXPERIMENT_METRICS}

    games["shapley_augmented"] = biased_shapley_augmented()
    instances["biased_shapley_augmented"].append(
        {"game": "shapley_augmented", "players": [0, 1], "labels": [["R", "P", "S", "N"], ["R", "P", "S", "N"]]}
    )

    # Clone player 1's rock: the visible max_diff is player 0, whose strategies face the clone.
    games["rps"] = rock_paper_scissors()
    games["rps_clone"], maps = clone_action(games["rps"], player=1, source=0, position=3)
    instances["clone_invariance"].append(
        {"base": "rps", "variant": "rps_clone", "player": 1, "source": 0, "clone_pos": 3, "maps": maps}
    )

    games["general_sum"] = general_sum_reference_game()
    weights = {0: 0.3, 1: 0.7}
    games["general_sum_mixture"], maps = mixture_action(games["general_sum"], 0, weights, 2)
    instances["mixture_invariance"].append(
        {
            "base": "general_sum",
            "variant": "general_sum_mixture",
            "player": 0,
            "weights": weights,
            "mix_pos": 2,
            "maps": maps,
        }
    )

    offsets = [{(0,): 10.0, (1,): -4.0}, {(0,): 7.0, (1,): -3.0}]
    games["general_sum_offset"] = add_offsets(games["general_sum"], offsets)
    instances["offset_invariance"].append(
        {"base": "general_sum", "variant": "general_sum_offset", "maps": identity_maps(games["general_sum"])}
    )

    games["dominance"] = dominance_test_game()
    instances["dominance_preserving"].append({"game": "dominance"})

    order = list(games)
    return games, instances, order


def evaluate_public(scores_path: Path, title: str, command: Optional[Sequence[str]] = None) -> dict:
    games, instances, order = public_suite()
    if scores_path.exists() or scores_path.is_symlink():
        scores_path.unlink()
    results, error, log_tail = run_rater(games, order, command=command)
    if error and log_tail:
        print("rating program output (tail):")
        print(log_tail)
    scores, diagnostics = score_suite(games, instances, results, error)
    print_report(scores, diagnostics, title)
    write_scores(scores_path, scores)
    return scores
