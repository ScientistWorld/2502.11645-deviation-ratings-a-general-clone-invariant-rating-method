#!/usr/bin/env python3
"""Hidden test for the deviation-rating benchmark.

Self-contained (standard library only) and run as ``python3 -I`` so nothing a
submission can edit (PYTHONPATH, sitecustomize, eval/protocol.py, data/,
scoring/reference.json, checkpoints/) is imported or trusted.

Everything scored is generated here at test time from a seed that exists only
in this file: about 210 normal-form games for the five property experiments
(including games above 1000 joint actions and meta-games of Sheriff
populations) and the population-improvement experiment (paper Section 5.3).
The method under test is the program ``scripts/rate.sh``. It is called once per
population iteration; each call carries that iteration's population meta-games
together with a share of the property games, shuffled and anonymised, and the
two games of every invariance pair always go to different calls. Each call runs
in a fresh temporary directory and every process it started is killed before
its output is read. Inside the job container the test also kills every other
process of the submission before it starts, and fails any call that creates or
changes files outside its temporary directory (calls must be stateless, so one
call cannot see another's games). Every scored number is recomputed from the
payoffs and the submitted equilibria. Baselines, transformations (clones, mixtures and their
weights, offsets, permutations), dominance relations, the strictest achievable
deviation gain, the population game and its candidate policies, tolerances and
the test size are fixed here.

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
CALL_TIMEOUT_SECONDS = 600
TOTAL_TIMEOUT_SECONDS = 2400
MAX_OUTPUT_BYTES = 64 * 1024 * 1024

POPULATION_EXPERIMENT = "population_improvement"
PROPERTY_METRICS: Dict[str, Tuple[str, ...]] = {
    "biased_shapley_augmented": ("dev_gap", "all_player_dev_gap", "player_symmetry_gap", "CCE_gap", "strictness_gap"),
    "clone_invariance": ("max_diff", "all_players_max_diff", "clone_source_gap", "strictness_gap"),
    "mixture_invariance": ("original_max_diff", "mixture_error", "max_CCE_gap", "strictness_gap"),
    "offset_invariance": ("max_diff", "max_CCE_gap", "strictness_gap"),
    "dominance_preserving": ("dominance_violations", "min_margin", "CCE_gap", "strictness_gap"),
}
EXPERIMENT_METRICS: Dict[str, Tuple[str, ...]] = dict(
    PROPERTY_METRICS, **{POPULATION_EXPERIMENT: ("mean_gap_ratio", "final_gap_ratio")}
)
HIGHER_IS_BETTER = frozenset({"min_margin"})
INTEGER_METRICS = frozenset({"dominance_violations"})
BASELINES: Dict[str, Tuple[str, ...]] = {
    "biased_shapley_augmented": ("uniform_payoff",),
    "clone_invariance": ("uniform_payoff",),
    "mixture_invariance": ("uniform_payoff",),
    "offset_invariance": ("uniform_payoff",),
    "dominance_preserving": ("uniform_payoff", "zero_rating", "negative_uniform_payoff"),
    POPULATION_EXPERIMENT: ("uniform_payoff", "random_selection"),
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


def deviation_rows(game: Game) -> List[List[float]]:
    """One row per (player, action): its deviation gain is ``row . sigma``."""
    rows = []
    for p in range(game.n):
        table, stride, own = game.tables[p], game.strides[p], game._own[p]
        for action in range(game.dims[p]):
            rows.append([table[j + (action - own[j]) * stride] - table[j] for j in range(game.size)])
    return rows


def strictest_epsilon(game: Game) -> Optional[Tuple[float, float]]:
    """Certified bounds on the smallest achievable largest CCE deviation gain.

    epsilon* = min over joint distributions s of max over (p, a') of the deviation
    gain, i.e. the value of the zero-sum matrix game whose rows are the deviation
    constraints. Solved as the column player's LP  max 1.x  s.t.  M x <= 1, x >= 0,
    with M = rows / scale + shift >= 1 (slack basis is feasible; no phase 1). The
    row player's strategy, read from the final reduced costs, certifies the value:
    returns (lower, upper) with upper - lower <= 1e-9 * scale, or None.
    """
    scale = game.scale()
    norm = [[v / scale for v in row] for row in deviation_rows(game)]
    k, m = len(norm), game.size
    shift = 1.0 - min(min(row) for row in norm)
    tab = []
    for i, row in enumerate(norm):
        line = [v + shift for v in row] + [0.0] * k + [1.0]
        line[m + i] = 1.0
        tab.append(line)
    basis = [m + i for i in range(k)]
    obj = [-1.0] * m + [0.0] * (k + 1)
    degenerate = 0
    for _ in range(200 * (k + m)):
        bland = degenerate > 30
        col = -1
        if bland:
            for j in range(m + k):
                if obj[j] < -1.0e-12:
                    col = j
                    break
        else:
            best = -1.0e-12
            for j in range(m + k):
                if obj[j] < best:
                    best, col = obj[j], j
        if col < 0:
            break
        r, ratio_min = -1, math.inf
        for i, line in enumerate(tab):
            a = line[col]
            if a > 1.0e-11:
                ratio = line[-1] / a
                if ratio < ratio_min or (
                    ratio == ratio_min and (basis[i] < basis[r] if bland else a > tab[r][col])
                ):
                    ratio_min, r = ratio, i
        if r < 0:
            return None
        degenerate = degenerate + 1 if ratio_min <= 1.0e-13 else 0
        inv = 1.0 / tab[r][col]
        prow = [v * inv for v in tab[r]]
        prow[col] = 1.0
        tab[r] = prow
        for i, line in enumerate(tab):
            if i != r:
                f = line[col]
                if f != 0.0:
                    new = [a - f * b for a, b in zip(line, prow)]
                    new[col] = 0.0
                    tab[i] = new
        f = obj[col]
        obj = [a - f * b for a, b in zip(obj, prow)]
        obj[col] = 0.0
        basis[r] = col
        for line in tab:
            if line[-1] < 0.0:
                line[-1] = 0.0
    else:
        return None
    x = [0.0] * m
    for i, b in enumerate(basis):
        if b < m:
            x[b] = tab[i][-1]
    total = math.fsum(x)
    y = [max(obj[m + i], 0.0) for i in range(k)]
    ytotal = math.fsum(y)
    if not (total > 0.0 and ytotal > 0.0):
        return None
    sigma = [v / total for v in x]
    y = [v / ytotal for v in y]
    upper = max(math.fsum(a * s for a, s in zip(row, sigma)) for row in norm)
    lower = min(math.fsum(y[i] * norm[i][j] for i in range(k)) for j in range(m))
    if upper - lower > 1.0e-9:
        return None
    return lower * scale, upper * scale


# ── Process control and rater execution ─────────────────────────────────────


def _enable_subreaper() -> bool:
    """Become the reaper of every orphaned descendant (Linux PR_SET_CHILD_SUBREAPER)."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(36, 1, 0, 0, 0) == 0
    except Exception:
        return False


def _proc_stat(pid: int) -> Optional[List[str]]:
    try:
        with open(f"/proc/{pid}/stat", "r") as handle:
            return handle.read().rsplit(")", 1)[-1].split()
    except OSError:
        return None


def _child_pids() -> List[int]:
    me = os.getpid()
    children = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return children
    for entry in entries:
        if entry.isdigit():
            fields = _proc_stat(int(entry))
            if fields and len(fields) > 1 and fields[1].isdigit() and int(fields[1]) == me:
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


def _in_private_pid_namespace() -> bool:
    """True inside a nested PID namespace (the job container), where /proc only shows the job."""
    try:
        with open("/proc/self/status", "r") as handle:
            for line in handle:
                if line.startswith("NSpid:"):
                    return len(line.split()) > 2
    except OSError:
        pass
    return False


def _pipe_ends(pid: int, want_read: bool) -> set:
    """Pipe inodes ``pid`` holds open for reading (``want_read``) or writing."""
    inodes = set()
    try:
        fds = os.listdir(f"/proc/{pid}/fd")
    except OSError:
        return inodes
    for fd in fds:
        try:
            target = os.readlink(f"/proc/{pid}/fd/{fd}")
            if not target.startswith("pipe:["):
                continue
            with open(f"/proc/{pid}/fdinfo/{fd}", "r") as handle:
                flags = next((int(line.split()[1], 8) for line in handle if line.startswith("flags:")), None)
        except (OSError, ValueError, StopIteration):
            continue
        if flags is None:
            continue
        reading = (flags & os.O_ACCMODE) == os.O_RDONLY
        if reading == want_read:
            inodes.add(target)
    return inodes


def terminate_foreign_processes() -> List[int]:
    """At the transition to testing, kill every other process of the submission.

    Only inside the job's private PID namespace, where every visible process
    belongs to the job: everything of this user that is neither this evaluator,
    one of its ancestors, nor a reader of an ancestor's output pipe (a log
    collector such as ``tee``) is killed. This removes watchers or writers a
    submission started before the test (they could otherwise rewrite the score
    file after this process exits). Outside such a namespace nothing is touched.
    """
    if not _in_private_pid_namespace():
        return []
    uid = os.getuid()
    protected = set()
    pid = os.getpid()
    while pid > 0 and pid not in protected:
        protected.add(pid)
        fields = _proc_stat(pid)
        pid = int(fields[1]) if fields and fields[1].isdigit() else 0
    outputs = set()
    for ancestor in protected:
        outputs |= _pipe_ends(ancestor, want_read=False)
    killed: List[int] = []
    for _ in range(20):
        found = False
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            target = int(entry)
            if target in protected:
                continue
            try:
                if os.stat(f"/proc/{entry}").st_uid != uid:
                    continue
            except OSError:
                continue
            if outputs and _pipe_ends(target, want_read=True) & outputs:
                protected.add(target)
                continue
            try:
                os.kill(target, signal.SIGKILL)
                killed.append(target)
                found = True
            except OSError:
                pass
        if not found:
            break
        time.sleep(0.05)
    return sorted(set(killed))


# Inside the job container (private PID namespace) the evaluator also enforces
# that a rating call is stateless: it may not create, change or delete files
# outside its own temporary directory. Only system-managed locations are not
# watched (version control, job logs, agent transcripts, the shared mount).
FORCE_ISOLATION = False
_UNWATCHED = frozenset({".git", "jobs", "logs", "shared", "trajectory", ".claude", ".claude.json",
                        ".claude-tmp", ".codex", ".empty_.claude-tmp", ".empty_trajectory"})
_WATCHED_ROOTS = (str(ROOT), "/tmp", "/var/tmp", "/dev/shm")


def isolation_active() -> bool:
    return FORCE_ISOLATION or _in_private_pid_namespace()


def _file_state(skip: str) -> Dict[str, tuple]:
    state: Dict[str, tuple] = {}
    for top in _WATCHED_ROOTS:
        if not os.path.isdir(top):
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            if dirpath == str(ROOT):
                dirnames[:] = [d for d in dirnames if d not in _UNWATCHED]
                filenames = [f for f in filenames if f not in _UNWATCHED]
            dirnames[:] = [d for d in dirnames if os.path.join(dirpath, d) != skip]
            for name in dirnames + filenames:
                path = os.path.join(dirpath, name)
                try:
                    info = os.lstat(path)
                except OSError:
                    continue
                state[path] = (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode)
    return state


def _paths_open_for_writing() -> set:
    """Files any still-running process (this evaluator, its ancestors, log collectors) writes to."""
    paths = set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fds = os.listdir(f"/proc/{entry}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(f"/proc/{entry}/fd/{fd}")
                if not target.startswith("/"):
                    continue
                with open(f"/proc/{entry}/fdinfo/{fd}", "r") as handle:
                    flags = next((int(line.split()[1], 8) for line in handle if line.startswith("flags:")), 0)
            except (OSError, ValueError):
                continue
            if flags & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR):
                paths.add(target)
    return paths


def _changed_files(before: Dict[str, tuple], after: Dict[str, tuple]) -> List[str]:
    changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    if changed:
        busy = _paths_open_for_writing()
        changed = [p for p in changed if p not in busy]
    return sorted(changed)


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
    timeout: float = CALL_TIMEOUT_SECONDS,
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
        if timeout <= 0:
            return None, "rating program exceeded the total time budget", log_tail
        _enable_subreaper()
        isolated = isolation_active()
        before = _file_state(str(workdir)) if isolated else {}
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(ROOT),
            "LANG": "C.UTF-8",
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TMPDIR": str(workdir),
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
        if isolated:
            changed = _changed_files(before, _file_state(str(workdir)))
            if changed:
                return None, (
                    f"rating program changed {len(changed)} file(s) outside its temporary directory "
                    f"(calls must be stateless), e.g. {changed[0]}"
                ), log_tail
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
    """Check one game's output. Returns {'ok', 'reason', 'ratings', 'cce_gap', 'max_gain', ...}."""
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


# view(game id) -> (ratings, total CCE regret, largest deviation gain of the distribution)
View = Callable[[str], Tuple[List[List[float]], float, float]]


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
        ratings, gap, _ = view(inst["game"])
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
        rb, _, _ = view(inst["base"])
        rv, _, _ = view(inst["variant"])
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
        rb, gb, _ = view(inst["base"])
        rv, gv, _ = view(inst["variant"])
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
        rb, gb, _ = view(inst["base"])
        rv, gv, _ = view(inst["variant"])
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
        ratings, gap, _ = view(inst["game"])
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


def strictness_gap(gids: Sequence[str], games: Dict[str, Game], view: View, strictest: Dict[str, Optional[tuple]]) -> float:
    """Largest excess of the distribution's largest deviation gain over the smallest achievable one.

    The strictest equilibrium minimises the largest deviation gain; 0 means the
    submitted equilibrium is as strict as any CCE of the game at that level.
    """
    worst = 0.0
    for gid in gids:
        bounds = strictest.get(gid)
        if bounds is None:
            continue
        _, _, max_gain = view(gid)
        worst = max(worst, _err(max(0.0, max_gain - bounds[1]), games[gid].scale()))
    return worst


def instance_game_ids(experiment: str, instances: List[dict]) -> List[str]:
    keys = ("game",) if experiment in ("biased_shapley_augmented", "dominance_preserving") else ("base", "variant")
    ids: List[str] = []
    for inst in instances:
        for key in keys:
            if inst[key] not in ids:
                ids.append(inst[key])
    return ids


def baseline_view(name: str, games: Dict[str, Game]) -> View:
    cache: Dict[str, Tuple[List[List[float]], float, float]] = {}

    def view(gid: str):
        if gid not in cache:
            game = games[gid]
            uniform = uniform_ratings(game)
            gains = deviation_gains(game, uniform_distribution(game))
            if name == "uniform_payoff":
                ratings = uniform
            elif name == "zero_rating":
                ratings = [[0.0] * d for d in game.dims]
            elif name == "negative_uniform_payoff":
                ratings = [[-v for v in row] for row in uniform]
            else:
                raise KeyError(name)
            cache[gid] = (ratings, cce_gap(gains), max(max(row) for row in gains))
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
    results: Dict[str, object],
    call_errors: Dict[str, str],
    strictest: Dict[str, Optional[tuple]],
) -> Tuple[dict, dict]:
    """Return (scores, diagnostics) for the property experiments.

    ``results[gid]`` is the submitted entry for each game; ``call_errors[gid]``
    is set when the call carrying that game failed as a whole.
    """
    checks = {}
    for gid, game in games.items():
        if gid in call_errors:
            checks[gid] = {"ok": False, "reason": call_errors[gid]}
        else:
            checks[gid] = validate_result(game, results.get(gid))
    valid_view: View = lambda gid: (checks[gid]["ratings"], checks[gid]["cce_gap"], checks[gid]["max_gain"])
    scores = {"experiments": {}}
    diagnostics = {"experiments": {}}
    for experiment, insts in instances.items():
        gids = instance_game_ids(experiment, insts)
        failures = [(gid, checks[gid]["reason"]) for gid in gids if not checks[gid]["ok"]]
        exp_results = {}
        if failures:
            exp_results[PROPOSED_ID] = failed_metrics(experiment)
        else:
            metrics = METRIC_FUNCTIONS[experiment](insts, games, valid_view)
            metrics["strictness_gap"] = strictness_gap(gids, games, valid_view, strictest)
            exp_results[PROPOSED_ID] = _finish(metrics)
        for baseline in BASELINES[experiment]:
            view = baseline_view(baseline, games)
            metrics = METRIC_FUNCTIONS[experiment](insts, games, view)
            metrics["strictness_gap"] = strictness_gap(gids, games, view, strictest)
            exp_results[baseline] = _finish(metrics)
        scores["experiments"][experiment] = {"results": exp_results}
        valid_infos = [checks[g] for g in gids if "mismatch" in checks[g]]
        diagnostics["experiments"][experiment] = {
            "games": len(gids),
            "instances": len(insts),
            "largest_game": max(games[g].size for g in gids),
            "failed_games": len(failures),
            "failure_reasons": sorted({reason for _, reason in failures})[:10],
            "max_rating_mismatch": max((c["mismatch"] for c in valid_infos), default=None),
            "max_deviation_gain": max((c["max_gain"] for c in valid_infos), default=None),
            "uncertified_strictness": sum(1 for g in gids if strictest.get(g) is None),
        }
    return scores, diagnostics


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


def dominance_test_game() -> Game:
    g0 = [[2.0, 2.0], [1.0, 1.0]]
    g1 = [[2.0, 1.0], [2.0, 1.0]]
    return Game.from_function((2, 2), lambda p, j: (g0 if p == 0 else g1)[j[0]][j[1]])


# ── Population game (paper Section 5.3): Sheriff ────────────────────────────


POP_SIZE = 8
POP_DROP = 2
POP_RUNS = 8
POP_ITERATIONS = 64
POP_CHECKPOINT_EVERY = 8
MECCE_EPS_REL = 1.0e-4
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
    The small eps keeps the problem strictly feasible.
    """
    rows = deviation_rows(game)
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


class CandidatePool:
    """Stream of random candidate policies for one run, shared by every method."""

    def __init__(self, sheriff: Sheriff, seed: int, count: int):
        self.reach: List[List[array]] = [[], []]
        for player in (0, 1):
            rng = random.Random(_mix(seed, player))
            for _ in range(count):
                self.reach[player].append(sheriff.realization(player, sheriff.random_policy(rng, player)))
        payoffs = sheriff.term_payoffs
        self.weighted = [
            [array("d", map(operator.mul, r, payoffs[p])) for p in (0, 1)] for r in self.reach[0]
        ]


class Population:
    """POP_SIZE policies per player drawn from a candidate pool; the meta-game is their payoff table."""

    def __init__(self, pool: CandidatePool):
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


def drop_slots(ratings: Sequence[float], keys: Sequence[float], scale: float) -> List[int]:
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


class PopulationLoop:
    """The paper's improvement loop on POP_RUNS independent runs, advanced one iteration per call.

    Every iteration: rate each run's meta-game, discard each player's POP_DROP
    lowest-rated policies and replace them with the next candidates of the run's
    pool. Progress is the full-game CCE gap of the population (under the
    meta-game's maximum-entropy CCE) every POP_CHECKPOINT_EVERY iterations.
    The candidate streams, tie-breaking keys and the measured gap are fixed
    here, so every method faces exactly the same draws.
    """

    def __init__(self, sheriff: Sheriff, pools: List[CandidatePool], seed: int):
        self.sheriff = sheriff
        self.seed = seed
        self.populations = [Population(pool) for pool in pools]
        self.curves = [[pop.full_game_gap(sheriff)] for pop in self.populations]
        self.iteration = 0

    def meta_games(self) -> List[Game]:
        return [pop.game() for pop in self.populations]

    def advance(self, ratings: List[List[List[float]]]) -> None:
        self.iteration += 1
        for run, pop in enumerate(self.populations):
            scale = pop.game().scale()
            key_rng = random.Random(_mix(self.seed, run, self.iteration, 2))
            for player in (0, 1):
                keys = [key_rng.random() for _ in range(POP_SIZE)]
                pop.replace(player, drop_slots(ratings[run][player], keys, scale))
        if self.iteration % POP_CHECKPOINT_EVERY == 0 or self.iteration == POP_ITERATIONS:
            for run, pop in enumerate(self.populations):
                self.curves[run].append(pop.full_game_gap(self.sheriff))

    def metrics(self) -> Dict[str, float]:
        initial = math.fsum(curve[0] for curve in self.curves) / len(self.curves)
        final = math.fsum(curve[-1] for curve in self.curves) / len(self.curves)
        later = [v for curve in self.curves for v in curve[1:]]
        return {"mean_gap_ratio": math.fsum(later) / len(later) / initial, "final_gap_ratio": final / initial}

    def mean_curve(self) -> List[float]:
        return [round(math.fsum(c[i] for c in self.curves) / len(self.curves), 4) for i in range(len(self.curves[0]))]


def make_pools(seed: int, runs: int = POP_RUNS) -> Tuple[Sheriff, List[CandidatePool]]:
    sheriff = Sheriff(**SHERIFF_PARAMETERS)
    count = POP_SIZE + POP_DROP * POP_ITERATIONS
    return sheriff, [CandidatePool(sheriff, _mix(seed, run), count) for run in range(runs)]


def baseline_population(sheriff: Sheriff, pools: List[CandidatePool], seed: int, name: str) -> PopulationLoop:
    loop = PopulationLoop(sheriff, pools, seed)
    for _ in range(POP_ITERATIONS):
        if name == "uniform_payoff":
            ratings = [uniform_ratings(game) for game in loop.meta_games()]
        elif name == "random_selection":
            ratings = [[[0.0] * POP_SIZE, [0.0] * POP_SIZE] for _ in loop.meta_games()]
        else:
            raise KeyError(name)
        loop.advance(ratings)
    return loop


# ── Hidden test suite: generated here at test time; the seed lives only here ──


HIDDEN_SEED = 7_311_942_665
RPS_MATRIX = [[0.0, -1.0, 1.0], [1.0, 0.0, -1.0], [-1.0, 1.0, 0.0]]
# gs2/gs3: random general-sum 2/3-player games; zs2: zero-sum; cc2: common interest;
# by3: a random 2-player game plus a bystander (see _with_bystander); sh2: the
# meta-game of a random Sheriff population (as rated in the population experiment);
# L2/L3: games above 1000 joint actions.
CLONE_KINDS = ("gs2", "by3", "zs2", "gs3", "gs2", "cc2", "by3", "gs3", "zs2", "gs2", "by3", "gs3", "gs2",
               "cc2", "by3", "gs3", "zs2", "gs2", "by3", "gs3", "gs2", "by3", "gs2", "gs2", "gs3", "gs2",
               "sh2", "sh2", "sh2", "L3", "L2")
MIXTURE_KINDS = ("gs2", "gs3", "by3", "zs2", "gs2", "cc2", "by3", "gs3", "gs2", "by3", "gs2", "zs2", "gs3",
                 "by3", "gs2", "gs2", "cc2", "gs3", "by3", "gs2", "zs2", "gs2", "gs3", "by3", "gs2", "gs2",
                 "sh2", "sh2", "sh2", "L2")
OFFSET_KINDS = ("gs2", "zs2", "by3", "gs3", "gs2", "cc2", "by3", "gs3", "gs2", "zs2", "by3", "gs2", "gs3",
                "gs2", "by3", "gs3", "cc2", "gs2", "by3", "zs2", "gs3", "gs2", "by3", "gs2", "gs2", "gs3",
                "sh2", "sh2", "L3")
DOMINANCE_KINDS = ("gs2", "gs3", "by3", "gs2", "gs2", "gs3", "by3", "gs2", "gs3", "gs2", "by3", "gs2",
                   "gs3", "gs2", "sh2", "L3")
LARGE_DIMS = {"L2": ((32, 33), (33, 32), (33, 33)), "L3": ((11, 11, 9), (10, 11, 10), (11, 10, 10))}


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


class _SheriffSource:
    """Meta-games of independent random Sheriff populations (same game as the population experiment)."""

    def __init__(self, seed: int):
        self.sheriff = Sheriff(**SHERIFF_PARAMETERS)
        self.rng = random.Random(seed)

    def game(self) -> Game:
        policies = [[self.sheriff.realization(p, self.sheriff.random_policy(self.rng, p)) for _ in range(POP_SIZE)]
                    for p in (0, 1)]
        payoffs = self.sheriff.term_payoffs
        tables = [[0.0] * (POP_SIZE * POP_SIZE) for _ in (0, 1)]
        for i, smuggler in enumerate(policies[0]):
            for j, sheriff in enumerate(policies[1]):
                for p in (0, 1):
                    tables[p][i * POP_SIZE + j] = math.fsum(a * b * u for a, b, u in zip(smuggler, sheriff, payoffs[p]))
        return Game((POP_SIZE, POP_SIZE), tables)


def _random_game(rng, kind: str, sheriff: Optional[_SheriffSource] = None) -> Game:
    if kind == "by3":
        return _with_bystander(rng, _random_game(rng, "gs2"))[0]
    if kind == "sh2":
        return sheriff.game()
    if kind in LARGE_DIMS:
        dims = rng.choice(LARGE_DIMS[kind])
    elif kind == "gs3":
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
        self.sheriff = _SheriffSource(_mix(seed, 0x5E))
        self.games: Dict[str, Game] = {}
        self.instances: Dict[str, List[dict]] = {name: [] for name in PROPERTY_METRICS}

    def new_id(self) -> str:
        while True:
            gid = f"{self.id_rng.getrandbits(48):012x}"
            if gid not in self.games:
                return gid

    def add(self, game: Game) -> str:
        gid = self.new_id()
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
    # A large population (above 1000 joint actions): 30 random mixtures besides R, P, S.
    add(BIASED_SHAPLEY, pure3 + [mixture3() for _ in range(30)], ["R", "P", "S"] + [f"m{i}" for i in range(30)])
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
        base = _random_game(rng, kind, suite.sheriff)
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
        base = _random_game(rng, kind, suite.sheriff)
        player = rng.choice([p for p in range(base.n) if base.dims[p] >= 2])
        k = rng.randint(2, min(base.dims[player], 4))
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
        base = _random_game(rng, kind, suite.sheriff)
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
        game = _random_game(rng, kind, suite.sheriff)
        for _ in range(1 if kind in LARGE_DIMS else rng.choice((1, 2))):
            game = _plant_dominated_action(rng, game)
        game, _ = permute_actions(game, _random_perms(rng, game.dims))
        suite.instances["dominance_preserving"].append({"game": suite.add(game)})
    public, _ = permute_actions(dominance_test_game(), _random_perms(rng, (2, 2)))
    suite.instances["dominance_preserving"].append({"game": suite.add(public)})


def build_hidden_suite(seed: int = HIDDEN_SEED) -> _Suite:
    suite = _Suite(seed)
    _shapley_family(suite)
    _clone_family(suite)
    _mixture_family(suite)
    _offset_family(suite)
    _dominance_family(suite)
    return suite


# ── Scheduling: one call per population iteration ───────────────────────────


def schedule_property_games(suite: _Suite, calls: int, rng: random.Random) -> List[List[str]]:
    """Spread the property games over ``calls`` calls; games of one instance never share a call."""
    slots: List[List[str]] = [[] for _ in range(calls)]
    for experiment, insts in suite.instances.items():
        for inst in insts:
            gids = [inst[k] for k in ("game", "base", "variant") if k in inst]
            for gid, slot in zip(gids, rng.sample(range(calls), len(gids))):
                slots[slot].append(gid)
    return slots


def _split_pairs(suite: _Suite, gids: Iterable[str]) -> List[List[str]]:
    """Two calls for the given property games, with the games of an instance in different calls."""
    pending = set(gids)
    first, second = [], []
    for insts in suite.instances.values():
        for inst in insts:
            members = [inst[k] for k in ("game", "base", "variant") if k in inst and inst[k] in pending]
            for index, gid in enumerate(members):
                (first if index == 0 else second).append(gid)
                pending.discard(gid)
    return [group for group in (first, second) if group]


def evaluate_hidden(seed: int = HIDDEN_SEED, command: Optional[Sequence[str]] = None) -> Tuple[dict, dict]:
    started = time.monotonic()
    suite = build_hidden_suite(seed)
    strictest = {gid: strictest_epsilon(game) for gid, game in suite.games.items()}
    sheriff, pools = make_pools(_mix(seed, 0x50))
    loop: Optional[PopulationLoop] = PopulationLoop(sheriff, pools, _mix(seed, 0x50))
    plan_rng = random.Random(_mix(seed, 0x51))
    slots = schedule_property_games(suite, POP_ITERATIONS, plan_rng)
    results: Dict[str, object] = {}
    call_errors: Dict[str, str] = {}
    population_failure = ""
    calls = 0

    def call(games: Dict[str, Game]) -> Tuple[Optional[dict], str]:
        nonlocal calls
        calls += 1
        order = list(games)
        plan_rng.shuffle(order)
        remaining = TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
        out, error, log_tail = run_rater(games, order, command=command, timeout=min(CALL_TIMEOUT_SECONDS, remaining))
        if error and log_tail:
            print("rating program output (tail):")
            print(log_tail)
        return out, error

    for index in range(POP_ITERATIONS):
        if loop is None:
            break
        games = {gid: suite.games[gid] for gid in slots[index]}
        loop_ids = []
        for game in loop.meta_games():
            perms = _random_perms(plan_rng, game.dims)
            presented, to_presented = permute_actions(game, perms)
            gid = suite.new_id()
            while gid in games:
                gid = suite.new_id()
            games[gid] = presented
            loop_ids.append((gid, presented, to_presented))
        out, error = call(games)
        for gid in slots[index]:
            if out is None:
                call_errors[gid] = error
            else:
                results[gid] = out.get(gid)
        if out is None:
            population_failure = error
            loop = None
            slots = slots[index + 1:]
            break
        ratings = []
        for gid, presented, to_presented in loop_ids:
            check = validate_result(presented, out.get(gid))
            if not check["ok"]:
                population_failure = f"population meta-game: {check['reason']}"
                break
            gains = check["ratings"]
            ratings.append([[gains[p][to_presented[p][a]] for a in range(POP_SIZE)] for p in (0, 1)])
        if population_failure:
            loop = None
            slots = slots[index + 1:]
            break
        loop.advance(ratings)
    else:
        slots = []
    rest = [gid for slot in slots for gid in slot]
    for group in _split_pairs(suite, rest):
        out, error = call({gid: suite.games[gid] for gid in group})
        for gid in group:
            if out is None:
                call_errors[gid] = error
            else:
                results[gid] = out.get(gid)

    scores, diagnostics = score_suite(suite.games, suite.instances, results, call_errors, strictest)
    population: Dict[str, Dict[str, float]] = {}
    curves: Dict[str, List[float]] = {}
    if loop is not None and loop.iteration == POP_ITERATIONS:
        population[PROPOSED_ID] = _finish(loop.metrics())
        curves[PROPOSED_ID] = loop.mean_curve()
    else:
        population[PROPOSED_ID] = failed_metrics(POPULATION_EXPERIMENT)
        population_failure = population_failure or "population loop did not complete"
    for name in BASELINES[POPULATION_EXPERIMENT]:
        baseline = baseline_population(sheriff, pools, _mix(seed, 0x50), name)
        population[name] = _finish(baseline.metrics())
        curves[name] = baseline.mean_curve()
    scores["experiments"][POPULATION_EXPERIMENT] = {"results": population}
    diagnostics["population"] = {"failure": population_failure, "curves": curves}
    diagnostics["calls"] = calls
    diagnostics["seconds"] = round(time.monotonic() - started, 1)
    return scores, diagnostics


def print_report(scores: dict, diagnostics: dict, title: str) -> None:
    print(f"== {title}: {diagnostics['calls']} rating-program calls, {diagnostics['seconds']} s ==")
    for experiment, entry in scores["experiments"].items():
        if experiment == POPULATION_EXPERIMENT:
            diag = diagnostics["population"]
            status = "FAILED" if diag["failure"] else "ok"
            print(f"[{experiment}] Sheriff, {POP_RUNS} runs x {POP_ITERATIONS} iterations, proposed method: {status}")
            if diag["failure"]:
                print(f"    gate failure: {diag['failure']}")
        else:
            diag = diagnostics["experiments"][experiment]
            status = "FAILED" if diag["failed_games"] else "ok"
            print(f"[{experiment}] {diag['instances']} instances, {diag['games']} games "
                  f"(largest {diag['largest_game']} joint actions), proposed method: {status}")
            for reason in diag["failure_reasons"]:
                print(f"    gate failure: {reason}")
        for method, metrics in entry["results"].items():
            print(f"    {method:<26} {json.dumps(metrics)}")
    for method, curve in diagnostics["population"]["curves"].items():
        print(f"    mean full-game CCE gap every {POP_CHECKPOINT_EVERY} iterations, {method}: {curve}")


def write_scores(path: Path, scores: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        path.unlink()
    path.write_text(json.dumps(scores, indent=2))


def main() -> dict:
    killed = terminate_foreign_processes()
    if killed:
        print(f"stopped {len(killed)} leftover process(es) of the submission before testing")
    scores_path = ROOT / "scoring" / "scores_test.json"
    if scores_path.exists() or scores_path.is_symlink():
        scores_path.unlink()
    scores, diagnostics = evaluate_hidden()
    print_report(scores, diagnostics, "hidden test")
    write_scores(scores_path, scores)
    print(f"Test evaluation complete. Results written to {scores_path}")
    return scores


if __name__ == "__main__":
    main()
