"""Phase 13 bounded experiment runner (NOT LOCKED; engineering machinery, not NEXUS learning). Full protocol:
docs/NEXUS_PHASE13_PROTOCOL_AND_HANDOFF.md.

CONTROLS (identical version space, shadows, query budget B_q, resume rule, abstention rule, strict synth12 Budget per row)
  fixed      AST-blind static menu (proposals13.generic_proposals), first proposal in menu order
  random     the same static menu, seeded uniform draw (per stream / task / B_q)
  untrained  program-aware proposals (proposals13.program_aware_proposals), uniform weights
  trained    program-aware proposals, the frozen source-trained Selector (weights + shortcut-tag leader prior) and the frozen
             DeltaStateGuide production costs for candidate collection
  Every arm spends up to B_q reference queries per row (a lone candidate is still challenged against its shadows). When every member
  is falsified, synthesis resumes with the answered queries as observations (at most MAX_RESUME times). Submission: the leader, unless
  (a) live members still disagree on a scored proposal of the program-aware + static menus, (b) that final scoring was INCOMPLETE
  ('incomplete_scoring'), or (c) the ROW BUDGET is out / exhausted (any cap or the wall, INCLUDING with a single live member)
  -> ABSTAIN (reason 'budget').
  REGRET ABLATION (diagnostic, result['ablations']): trained_no_regret = same source episodes / scored lists / utilities / listwise
  train_step, WITHOUT audit_choice and audit_submission; same frozen guide costs and collection as trained.
  DIAGNOSTIC BASELINE (result['baselines']): single_shot submits the first candidate of the shared collection (no LLM baseline exists).

WORK CAPS  one synth12.Budget per row (full checks <= fc_cap <= 5000; CappedCounter raises at the exact increment). Collection runs in a
           fork limited to 70 % of the remaining headroom of every counter and of the wall, charged IN FULL to every arm's row. Hidden-batch
           grading of evaluation tasks is evaluation, not learner work. Privileged SOURCE supervision is metered separately (SourceMeter,
           SOURCE_CAPS; charged before execution; refusal skips the step; any overrun -> exit 1).

STREAMS / ISOLATION  rep0 / rep1 train independent states on disjoint source seeds; evaluation tasks are identical across streams. Seeds:
           source 1310000 + 10000*stream + 100*family + i; eval 132000 + 100*family + i; pipeline 133000 + 100*spec + i (overlap refused
           before the run). Trained / no-regret selectors and guide are FROZEN before evaluation; sha256 fingerprints before / after.

PIPELINE SUITE  multi-stage SQL pipelines with one broken stage; pipeline_lifter13.repair_pipeline under each arm's choice rule with ONE
           row budget and ONE query allowance; 'verified' requires core11 AND native SQLite agreement on hidden batches. Fixed / Random use
           the AST-blind static menu (lift_stage(menu=...)), Untrained / Trained the program-aware menu, as in the ambiguous suite. Every
           spec declares edit_reachable (engineer's design knowledge): P1-P3 and P6 are reachable by one shadow edit, P4 (left join +
           default) and P5 (COUNT(*) -> SUM) are NOT and need the atomic synthesizer. P6 (invoices / vendors, three stages) uses a schema
           and generator that no source family uses (held_out_schema; summarised separately). Each row records the method of every
           repaired stage (repair_methods / verified_method edit | synth | mixed).
           ENGINES: repairs are gated by core11 + SQLite. When the `duckdb` package is importable, the compiled SQL of every repaired
           pipeline is ALSO executed natively on DuckDB over the hidden batches (evaluation grading only; one dialect mapping
           CAST AS REAL -> DOUBLE) and reported as hidden_duckdb; 'verified' does not depend on it, so the controls stay matched whether
           or not DuckDB is installed. Polars / PySpark are not executed.

VERDICT (ambiguous suite, primary B_q = max(budgets))  positive: Trained - X >= +2 for every X in {fixed, random, untrained} in every
           stream AND Trained wrong <= every comparator's; negative: Trained - X <= -2 for some X in every stream; else mixed.

PROGRESSION METRICS (charter section 10; None when undefined, never imputed): learning_to_learn_gain, transfer_efficiency,
  self_evolution_delta (trained minus trained_no_regret), unseen_domain_reuse_rate, enterprise_reliability_advantage.

ATTRIBUTION  learned by NEXUS: selector weights, shortcut-tag prior, guide counts / cost table, update ledger (learned_by_nexus). No
           library functions are admitted (lib = {}). Everything else is engineering machinery.

INVOCATION  python -m nexus.de_phase13.runner13 --grant-seconds S [--execute]   or   python src/nexus/de_phase13/runner13.py ... ;
           --execute runs the full bounded experiment (the only mode; accepted for the coordinator). Exit: 0 ok, 1 over-cap row,
           source-supervision overrun or isolation failure, 2 no completed rows."""
from __future__ import annotations

import os
import sys

if __package__ in (None, ""):                                            # executed as a script: make `nexus` importable
    _SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)

import argparse                                                          # noqa: E402
import hashlib                                                           # noqa: E402
import inspect                                                           # noqa: E402
import json                                                              # noqa: E402
import math                                                              # noqa: E402
import platform                                                          # noqa: E402
import random                                                            # noqa: E402
import re                                                                # noqa: E402
import time                                                              # noqa: E402
import traceback                                                         # noqa: E402
from collections import Counter                                          # noqa: E402

from nexus.de_phase11 import core11 as C                                 # noqa: E402
from nexus.de_phase12 import synth12 as S                                # noqa: E402
from nexus.de_phase13 import WORK_CAPS                                   # noqa: E402
from nexus.de_phase13 import pipeline_lifter13 as PL                     # noqa: E402
from nexus.de_phase13 import proposals13 as P                            # noqa: E402
from nexus.de_phase13 import selector13 as L                             # noqa: E402

try:                                                                     # optional third native engine (evaluation grading only)
    import duckdb as _duckdb                                             # noqa: E402
except Exception:                                                        # noqa: BLE001 - absent or broken install: reported, never faked
    _duckdb = None
DUCKDB_VERSION = getattr(_duckdb, "__version__", None) if _duckdb is not None else None

ARMS = L.ARMS
ABLATION_ARM = "trained_no_regret"
LEARNED_ARMS = ("trained", ABLATION_ARM)
STATIC_MENU_ARMS = ("fixed", "random")
STREAMS = ("rep0", "rep1")
SOURCE_BASE, SOURCE_STREAM_STRIDE, EVAL_BASE, PIPE_BASE = 1310000, 10000, 132000, 133000
MAX_INDEX = 100                                                          # family / spec / instance indices must lie in 0..99
HIDDEN, MAX_RESUME, FC_LIMIT, SAFETY, COLLECT_SHARE = 3, 2, 5000, 0.95, 0.7
# pre-registered privileged source-supervision caps (separate from row budgets; charged before execution)
SOURCE_CAPS = dict(ref_answers_per_episode=512, ref_answers_per_stream=6000, grade_execs_per_episode=16 * HIDDEN,
                   grade_execs_per_stream=400 * HIDDEN)
DEFAULT_GRANT_S = 1500.0
DEFAULT_OUT = os.path.join("artifacts", "agi13_eval")
DEFAULT = dict(streams=STREAMS, budgets=(1, 2), eval_instances=2, source_instances=3, pipeline_instances=2, collect_wall=2.5,
               investigate_wall=4.0, lift_wall=4.0, fc_cap=FC_LIMIT, pipelines=True, source_share=0.30, ambiguous_share=0.80,
               regret_ablation=True)
QUICK = dict(budgets=(1,), eval_instances=1, source_instances=1, pipeline_instances=1, collect_wall=1.0, investigate_wall=2.0,
             lift_wall=2.0)


# ------------------------------------------------------------------ utilities
def _js(x):
    if isinstance(x, dict):
        return {str(k): _js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_js(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted((_js(v) for v in x), key=repr)
    if x is None or isinstance(x, (bool, int, str)):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else repr(x)
    return repr(x)


def _short(ast, n=400):
    s = repr(ast)
    return s if len(s) <= n else s[:n] + "..."


def _seed(*parts):
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _log(msg):
    print(f"[runner13] {msg}", file=sys.stderr, flush=True)


def _caps(fc_cap):
    return dict(WORK_CAPS, full_checks=fc_cap)


def _over_cap(counters, fc_cap):
    return sorted(k for k, cap in _caps(fc_cap).items() if counters.get(k, 0) > cap)


def _rule(arm):
    """Choice rule of an arm (the regret ablation uses the trained rule with its own selector)."""
    return "trained" if arm in LEARNED_ARMS else arm


class SourceMeter:
    """Strict meter for privileged source supervision: charge() refuses (and records) any unit past a per-episode or per-stream cap."""

    def __init__(self, caps=None):
        self.caps, self.used, self.refused, self.episode, self.max_episode = dict(caps or SOURCE_CAPS), Counter(), Counter(), Counter(), Counter()

    def start_episode(self):
        self.episode = Counter()

    def charge(self, key, n=1):
        ep, st = self.caps.get(f"{key}_per_episode"), self.caps.get(f"{key}_per_stream")
        if (ep is not None and self.episode[key] + n > ep) or (st is not None and self.used[key] + n > st):
            self.refused[key] += 1
            return False
        self.episode[key] += n
        self.used[key] += n
        self.max_episode[key] = max(self.max_episode[key], self.episode[key])
        return True

    def over_cap(self):
        out = []
        for k in set(self.used) | set(self.max_episode):
            if self.used[k] > self.caps.get(f"{k}_per_stream", float("inf")) or self.max_episode[k] > self.caps.get(f"{k}_per_episode", float("inf")):
                out.append(k)
        return sorted(out)

    def report(self):
        return dict(caps=dict(self.caps), used=dict(self.used), refused=dict(self.refused), max_per_episode=dict(self.max_episode),
                    over_cap=self.over_cap())


# ------------------------------------------------------------------ relation construction (core11 constructor discovered defensively)
_REL_FACTORY = None
_ALIASES = dict(cols=("cols", "columns", "names"), types=("types", "dtypes", "coltypes"), rows=("rows", "data", "tuples"),
                schema=("schema",))


def _factories():
    for name in ("Rel", "Relation", "Table"):
        cls = getattr(C, name, None)
        if not callable(cls):
            continue
        yield lambda c, t, r, cls=cls: cls(c, t, r)
        yield lambda c, t, r, cls=cls: cls(c, t, tuple(r))
        yield lambda c, t, r, cls=cls: cls(cols=c, types=t, rows=r)
        yield lambda c, t, r, cls=cls: cls(tuple(zip(c, t)), r)
    for name in ("make_rel", "rel_of", "relation", "mk_rel"):
        fn = getattr(C, name, None)
        if callable(fn):
            yield lambda c, t, r, fn=fn: fn(c, t, r)
    for name, obj in sorted(vars(C).items()):
        if not isinstance(obj, type):
            continue
        try:
            params = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            continue
        if not any(p in _ALIASES["rows"] for p in params):
            continue

        def make(c, t, r, obj=obj, params=params):
            kw = {}
            for p in params:
                for role, al in _ALIASES.items():
                    if p in al:
                        kw[p] = dict(cols=c, types=t, rows=r, schema=tuple(zip(c, t)))[role]
            return obj(**kw)
        yield make


def _valid(R, cols, types, rows):
    try:
        return (tuple(R.cols) == cols and tuple(R.types) == types and [tuple(r) for r in R.rows] == rows
                and callable(getattr(R, "schema", None)) and callable(getattr(R, "bag", None)))
    except Exception:                                                  # noqa: BLE001 - unknown object shape: not a relation
        return False


def make_rel(cols, types, rows):
    """A core11 relation with the given columns, types and rows (constructor discovered once, validated by a C.run round trip)."""
    global _REL_FACTORY
    cols, types, rows = tuple(cols), tuple(types), [tuple(r) for r in rows]
    if _REL_FACTORY is not None:
        return _REL_FACTORY(cols, types, rows)
    for f in _factories():
        try:
            R = f(cols, types, rows)
        except Exception:                                              # noqa: BLE001 - try the next constructor signature
            continue
        if not _valid(R, cols, types, rows):
            continue
        try:
            back = C.run(("rel", "nx_probe"), {"nx_probe": R})
        except Exception:                                              # noqa: BLE001
            continue
        if tuple(back.cols) == cols and rows:
            _REL_FACTORY = f
            return R
        if not rows:
            return R
    raise RuntimeError("core11 exposes no recognised relation constructor (tried Rel / Relation / Table / helper functions)")


# ------------------------------------------------------------------ task families (generator side only; never shown to the learner)
def _g_null(rng, mode):
    n = rng.randint(4, 6)
    rows = [(i, rng.randint(1, 40)) for i in rng.sample(range(1, 90), n)]
    if mode == "edge":
        for j in rng.sample(range(n), max(1, n // 3)):
            rows[j] = (rows[j][0], None)
    return {"t": make_rel(("id", "x"), (C.INT, C.INT), rows)}


def _g_count(rng, mode):
    rows = [(g, rng.randint(1, 30)) for g in rng.sample(["a", "b", "c", "d"], 3) for _ in range(rng.randint(2, 3))]
    if mode == "edge":
        for j in rng.sample(range(len(rows)), 2):
            rows[j] = (rows[j][0], None)
    rng.shuffle(rows)
    return {"e": make_rel(("g", "v"), (C.STR, C.INT), rows)}


def _g_sum(rng, mode):
    rows = []
    for i, k in enumerate(rng.sample(["k1", "k2", "k3", "k4", "k5"], 4)):
        rows.append((k, rng.randint(1, 50)))
        if i < 2:
            rows.append((k, 0 if mode == "vis" else rng.randint(1, 50)))
    rng.shuffle(rows)
    return {"p": make_rel(("k", "amt"), (C.STR, C.INT), rows)}


def _g_lookup(rng, mode):
    cids = rng.sample(range(1, 40), 4)
    custs = [(c, rng.choice(["gold", "silver", "bronze"])) for c in cids]
    n = rng.randint(4, 6)
    orders = [(o, rng.choice(cids), rng.randint(1, 90)) for o in rng.sample(range(100, 400), n)]
    if mode == "edge":
        for j in rng.sample(range(n), max(1, n // 3)):
            orders[j] = (orders[j][0], rng.randint(41, 80), orders[j][2])
    return {"orders": make_rel(("oid", "cust", "amt"), (C.INT, C.INT, C.INT), orders),
            "custs": make_rel(("cid", "tier"), (C.INT, C.STR), custs)}


def _g_latest(rng, mode):
    rows = []
    for n, u in enumerate(rng.sample(range(1, 60), 3)):
        ts, vs = sorted(rng.sample(range(1, 100), 2)), sorted(rng.sample(range(1, 500), 2))
        if mode == "edge" and (n == 0 or rng.random() < 0.5):
            vs.reverse()
        rows += [(u, ts[0], vs[0]), (u, ts[1], vs[1])]
    rng.shuffle(rows)
    return {"u": make_rel(("uid", "ts", "v"), (C.INT, C.INT, C.INT), rows)}


def _g_invoices(rng, mode):
    """Held-out pipeline schema (no source family uses it): invoices(inv, vend, total) and vendors(vid, region). In edge mode some
    invoices reference vendors that do not exist (unmatched keys -> NULL region after a left join)."""
    vids = rng.sample(range(500, 560), 3)
    vendors = [(v, rng.choice(["north", "south", "east", "west"])) for v in vids]
    n = rng.randint(5, 7)
    invs = [(i, rng.choice(vids), rng.randint(0, 900)) for i in rng.sample(range(7000, 7900), n)]
    if mode == "edge":
        for j in rng.sample(range(n), max(1, n // 3)):
            invs[j] = (invs[j][0], rng.randint(600, 650), invs[j][2])
    return {"invoices": make_rel(("inv", "vend", "total"), (C.INT, C.INT, C.INT), invs),
            "vendors": make_rel(("vid", "region"), (C.INT, C.STR), vendors)}


def _families():
    col = lambda c: ("col", c)                                           # noqa: E731
    fams = [
        dict(name="null_default", source=True, gen=_g_null,
             ref=("map", ("rel", "t"), (("id", col("id")), ("y", ("branch", ("isnull", col("x")), ("const", 0, C.INT), col("x")))))),
        dict(name="count_col", source=True, gen=_g_count,
             ref=("map", ("fold", ("rel", "e"), ("g",), (("n", "count", col("v")),)), (("g", col("g")), ("n", col("n"))))),
        dict(name="dup_sum", source=True, gen=_g_sum,
             ref=("map", ("fold", ("rel", "p"), ("k",), (("total", "sum", col("amt")),)), (("k", col("k")), ("total", col("total"))))),
        dict(name="left_lookup", source=False, gen=_g_lookup, requires="left",
             ref=("map", ("join", "left", ("rel", "orders"), ("rel", "custs"), ("cust",), ("cid",)), (("oid", col("oid")), ("tier", col("tier"))))),
        dict(name="rank_latest", source=False, gen=_g_latest,
             ref=("map", ("rank", ("rel", "u"), ("uid",), ((col("ts"), True),), 1), (("uid", col("uid")), ("v", col("v"))))),
    ]
    kinds = tuple(getattr(C, "JOIN_KINDS", ()))
    return [f for f in fams if f.get("requires") is None or f["requires"] in kinds]


def _check_index(**kw):
    for k, v in kw.items():
        if not 0 <= int(v) < MAX_INDEX:
            raise ValueError(f"{k}={v} outside 0..{MAX_INDEX - 1}: seed namespaces would no longer be disjoint")


def source_seed(si, fi, i):
    """Source seeds: 1310000 + 10000*stream + 100*family + i (seven digits; disjoint from eval 132xxx and pipeline 133xxx)."""
    _check_index(family=fi, instance=i)
    if not 0 <= int(si) < 90:
        raise ValueError(f"stream index {si} out of range")
    return SOURCE_BASE + SOURCE_STREAM_STRIDE * si + 100 * fi + i


def eval_seed(fi, i):
    _check_index(family=fi, instance=i)
    return EVAL_BASE + 100 * fi + i


def pipeline_seed(pi, i):
    _check_index(spec=pi, instance=i)
    return PIPE_BASE + 100 * pi + i


def build_task(fam, seed, split):
    """-> rec: the learner's view (rec['task']) and the runner-private reference AST + hidden batches (oracle / grading only)."""
    rng = random.Random(seed)
    ref = fam["ref"]
    inputs = {b: fam["gen"](rng, "vis") for b in S.VIS}
    expected = {b: C.run(ref, inputs[b]) for b in S.VIS}
    if not all(expected[b].rows for b in S.VIS):
        raise ValueError("empty visible output")
    hidden = []
    for j in range(HIDDEN):
        env = fam["gen"](rng, "edge")
        hidden.append((f"h{j}", env, C.run(ref, env)))
    E = expected[S.VIS[0]]
    task = dict(inputs=inputs, expected=expected, out_schema=tuple(zip(E.cols, E.types)))
    return dict(id=f"T{seed}", seed=seed, family=fam["name"], held_out=not fam["source"], split=split, task=task, ref=ref, hidden=hidden)


def _outn(rec):
    return [n for n, _ in rec["task"]["out_schema"]]


def _matches(ast, env, E, outn):
    try:
        got = C.run(ast, env)
        if set(got.cols) != set(outn) or len(got.cols) != len(outn):
            return False
        return bool(C.same_bag(C.project_like(got, outn), E))
    except P._EXEC_ERRORS:
        return False


def grade(ast, rec):
    """Evaluation only (not learner work): the program reproduces every hidden batch of the task."""
    outn = _outn(rec)
    return all(_matches(ast, env, E, outn) for _, env, E in rec["hidden"])


def _source_grade(ast, rec, meter):
    """Metered source grading (privileged supervision): None when the meter refuses the hidden-batch executions."""
    if not meter.charge("grade_execs", len(rec["hidden"])):
        return None
    return grade(ast, rec)


def _oracle(ref):
    def oracle(env):
        try:
            return C.run(ref, env)
        except P._EXEC_ERRORS:
            return None
    return oracle


# ------------------------------------------------------------------ candidate collection (strictly metered)
def _share(now, cap, frac=COLLECT_SHARE):
    return min(cap, now + max(1, int(frac * max(0, cap - now))))


def collect_into(task, costs, budget, wall_s, extra_obs=None):
    """synth12 candidate collection inside a fork of `budget` limited to COLLECT_SHARE of the remaining headroom of EVERY counter and
    <= wall_s; the fork's counters are merged back so the row is charged in full. -> (candidates, exhausted)."""
    if budget.out():
        return [], "budget"
    t = dict(task)
    if extra_obs:
        t["extra_obs"] = list(extra_obs)
    c = budget.c
    el = time.time() - budget.t0
    sb = budget.fork(fc_cap=_share(c["full_checks"], budget.fc_cap), rel_cap=_share(c["rel_evals"], budget.rel_cap),
                     sc_cap=_share(c["micro_evals"], budget.sc_cap), ast_cap=_share(c["constructed_asts"], budget.ast_cap),
                     wall=el + min(wall_s, COLLECT_SHARE * max(0.0, budget.wall - el)))
    try:
        res = S.collect(t, {}, costs, sb)
    except P._EXEC_ERRORS + (S.WorkExhausted,) as e:
        res, sb.exhausted = None, sb.exhausted or type(e).__name__
    for k, v in sb.c.items():
        if v > budget.c.get(k, 0):
            Counter.__setitem__(budget.c, k, v)
    return (res["candidates"] if res else []), sb.exhausted


def fresh_collection(task, costs, cfg):
    b = S.Budget(wall=cfg["collect_wall"] + cfg["investigate_wall"], fc_cap=cfg["fc_cap"])
    cands, exh = collect_into(task, costs, b, cfg["collect_wall"])
    return dict(cands=cands, counters=dict(b.c), wall=time.time() - b.t0, exhausted=exh)


# ------------------------------------------------------------------ investigation (identical rule in every arm)
def _static_menu(vs):
    """The AST-blind static menu (Fixed / Random controls in both suites)."""
    return P.generic_proposals(P.base_envs(vs.task))


def _menu(arm, vs):
    if arm in STATIC_MENU_ARMS:
        return _static_menu(vs)
    return P.program_aware_proposals(vs)


def _row_exhausted(budget, vs=None):
    """True when the row budget can no longer support evidence: a cap or the wall is reached, or a charge was refused."""
    return bool(budget.exhausted) or budget.out() or bool(vs is not None and vs.exhausted)


def _learn_step(learn, vs, rec, scored, ch, leader, ctx):
    """Source training only: privileged reference answers for EVERY scored proposal (metered; refused -> step skipped) ->
    counterfactual utilities -> regret audit of the choice actually made + listwise step. The ablation selector gets only the
    listwise step on the SAME scored list and utilities."""
    if not learn["meter"].charge("ref_answers", len(scored)):
        learn["skipped_steps"] += 1
        return
    fps = [vs.run(rec["ref"], s["env"]) for s in scored]
    learn["ref_answers"] += len(fps)
    utils = L.counterfactual_utilities(scored, fps, leader_id=leader["id"] if leader else None)
    sel = learn["selector"]
    a = sel.audit_choice(scored, ch, utils, context=ctx)
    sel.train_step(scored, utils, context=ctx)
    if learn.get("ablation") is not None:
        learn["ablation"].train_step(scored, utils, context=ctx)
    learn["regret"] += a.get("regret", 0.0)


def investigate(rec, cands, arm, budget, bq, *, rng=None, selector=None, costs=None, cfg=None, learn=None):
    task = rec["task"]
    oracle = _oracle(rec["ref"])
    prior = selector.leader_prior if (arm in LEARNED_ARMS and selector is not None) else None
    collect_wall = (cfg or DEFAULT)["collect_wall"]
    vs = P.VersionSpace(task, cands, budget=budget, shadows=True)
    init = dict(candidates=len(cands), alive=len(vs.alive()), alive_candidates=len(vs.alive("candidate")),
                alive_shadows=len(vs.alive("shadow")))
    queries, resumed, earlier = [], 0, []
    while True:
        if not vs.alive():
            answered = vs.extra_obs()
            if not answered or resumed >= MAX_RESUME or _row_exhausted(budget, vs):
                break
            new, _ = collect_into(task, costs or S.Costs(), budget, collect_wall, extra_obs=answered)
            resumed += 1
            earlier.append(vs.summary())
            vs = P.VersionSpace(dict(task, extra_obs=answered), new, budget=budget, shadows=True)
            continue
        if len(queries) >= bq or _row_exhausted(budget, vs):
            break
        leader = vs.leader(prior)
        scored = P.score_proposals(vs, _menu(arm, vs), leader=leader)
        if not scored:
            break
        ch = L.pick(_rule(arm), scored, selector=selector, rng=rng)
        if ch is None:
            break
        if learn is not None:
            _learn_step(learn, vs, rec, scored, ch, leader, dict(task=rec["id"], q=len(queries)))
        E = oracle(ch["env"])
        qn = f"q{len(queries)}"
        q = dict(name=qn, kind=ch["kind"], base=ch["base"], rel=ch["rel"], detail=_js(ch["detail"]), scored=len(scored),
                 splits=len(ch["partition"]) > 1, answered=E is not None, falsified=0, survivors=None)
        queries.append(q)
        if E is None:
            continue
        rep = vs.observe(qn, ch["env"], E)
        q.update(falsified=len(rep["falsified"]), survivors=len(rep["survivors"]), falsified_tags=rep["falsified_tags"],
                 falsified_edges=rep["falsified_edges"])
    out = dict(vs=vs, init=init, queries=queries, resumed=resumed, earlier=earlier, leader=None, unresolved=False,
               agreement_unproven=False, status="abstained", reason=None, final_check=None)
    alive = vs.alive()
    if not alive:
        out["reason"] = "budget" if _row_exhausted(budget, vs) else ("all_falsified" if vs.members else "no_candidate")
        return out
    leader = vs.leader(prior)
    out["leader"] = leader
    if _row_exhausted(budget, vs):                                     # expired row budget -> abstain, even with one live member
        out.update(unresolved=True, reason="budget")
        return out
    if len(alive) > 1:
        chk = P.disagreement_check(vs, P.program_aware_proposals(vs) + P.generic_proposals(P.base_envs(vs.task)), leader=leader)
        out["final_check"] = {k: chk[k] for k in ("complete", "reason", "splitting", "scored", "requested", "live")}
        if _row_exhausted(budget, vs):
            out.update(unresolved=True, reason="budget")
            return out
        if not chk["complete"]:                                        # an unscored proposal could still separate the members
            out.update(unresolved=True, reason="incomplete_scoring")
            return out
        if chk["splitting"]:
            out.update(unresolved=True, reason="unresolved_alternatives")
            return out
    out.update(status="submitted", agreement_unproven=len(alive) > 1)
    return out


# ------------------------------------------------------------------ source training (per stream)
def source_train(stream, si, fams, cfg, deadline):
    sel = L.Selector(name=f"trained-{stream}")
    abl = L.Selector(name=f"trained-no-regret-{stream}")
    guide = L.DeltaStateGuide(name=f"guide-{stream}")
    meter = SourceMeter(SOURCE_CAPS)
    srcs = [(fi, f) for fi, f in enumerate(fams) if f["source"]]
    learn = dict(selector=sel, ablation=abl, meter=meter, ref_answers=0, regret=0.0, skipped_steps=0)
    episodes, skipped, seeds = [], 0, []
    for i in range(cfg["source_instances"]):
        for fi, fam in srcs:
            seed = source_seed(si, fi, i)
            seeds.append(seed)
            if time.time() > deadline:
                skipped += 1
                continue
            meter.start_episode()
            ep = dict(task=f"T{seed}", family=fam["name"])
            try:
                rec = build_task(fam, seed, "source")
                costs = guide.costs()
                budget = S.Budget(wall=cfg["collect_wall"] + cfg["investigate_wall"], fc_cap=cfg["fc_cap"])
                cands, _ = collect_into(rec["task"], costs, budget, cfg["collect_wall"])
                out = investigate(rec, cands, "trained", budget, max(cfg["budgets"]), selector=sel, costs=costs, cfg=cfg, learn=learn)
                vs = out["vs"]
                would = out["leader"] or vs.leader(sel.leader_prior)
                ep.update(candidates=len(cands), queries=len(out["queries"]), status=out["status"], reason=out["reason"])
                if would is not None:
                    ok = _source_grade(would["ast"], rec, meter)
                    if ok is None:
                        ep.update(grading="refused")
                    else:
                        others = [m for m in vs.alive() if m["id"] != would["id"]]
                        alts, ungraded = [], 0
                        for n, m in enumerate(others):
                            g = _source_grade(m["ast"], rec, meter)
                            if g is None:
                                ungraded = len(others) - n
                                break
                            if g:
                                alts.append(m)
                        sel.audit_submission(would["tags"], not ok, sorted({t for m in alts for t in m["tags"]}), context=rec["id"])
                        guide.observe(would["ast"], ok, would.get("provenance"))
                        for m in alts:
                            guide.observe(m["ast"], True, m.get("provenance"))
                        ep.update(would_be_correct=ok, leader_tags=would["tags"], correct_alternatives=len(alts),
                                  alternatives_ungraded=ungraded)
            except Exception as e:                                     # noqa: BLE001 - recorded, never hidden
                ep.update(status="error", error=f"{type(e).__name__}: {e}"[:300])
            ep["supervision"] = dict(meter.episode)
            episodes.append(ep)
    return dict(selector=sel, selector_no_regret=abl, guide=guide, meter=meter, episodes=episodes, skipped=skipped, seeds=seeds,
                ref_answers=learn["ref_answers"], regret_total=learn["regret"], skipped_learning_steps=learn["skipped_steps"])


def _learned_report(tr):
    sel, guide, abl = tr["selector"], tr["guide"], tr["selector_no_regret"]
    top = sorted(sel.weights.items(), key=lambda kv: (-abs(kv[1] - 1.0), kv[0]))[:12]
    atop = sorted(abl.weights.items(), key=lambda kv: (-abs(kv[1] - 1.0), kv[0]))[:12]
    eps = tr["episodes"]
    return dict(selector_fingerprint=sel.fingerprint(), guide_fingerprint=guide.fingerprint(),
                top_weights=[(k, round(v, 4)) for k, v in top], tag_prior={k: round(v, 4) for k, v in sorted(sel.tag_prior.items())},
                demoted_shortcuts=sel.demoted_shortcuts(), selector_stats=dict(sel.stats), ledger_entries=len(sel.ledger),
                no_regret_selector=dict(fingerprint=abl.fingerprint(), top_weights=[(k, round(v, 4)) for k, v in atop],
                                        stats=dict(abl.stats)),
                guide_table=guide.table(), guide_observations=guide.n, source_episodes=len(eps), source_skipped=tr["skipped"],
                source_would_be_correct=sum(bool(e.get("would_be_correct")) for e in eps),
                source_errors=sum(e.get("status") == "error" for e in eps), privileged_reference_answers=tr["ref_answers"],
                skipped_learning_steps=tr["skipped_learning_steps"], source_supervision=tr["meter"].report(),
                regret_total=round(tr["regret_total"], 6), admitted_library_functions=[], episodes=eps)


# ------------------------------------------------------------------ evaluation rows
def eval_row(rec, stream, bq, arm, cfg, frozen, shared, tcache):
    t0 = time.time()
    row = dict(suite="ambiguous", task=rec["id"], family=rec["family"], held_out=rec["held_out"], stream=stream, B_q=bq, arm=arm)
    try:
        learned = arm in LEARNED_ARMS
        if learned:
            costs, key, cache = frozen["costs"], (rec["id"], stream), tcache
        else:
            costs, key, cache = S.Costs(), rec["id"], shared
        if key not in cache:
            cache[key] = fresh_collection(rec["task"], costs, cfg)
        coll = cache[key]
        budget = S.Budget(wall=cfg["collect_wall"] + cfg["investigate_wall"], fc_cap=cfg["fc_cap"], t0=time.time() - coll["wall"],
                          start=coll["counters"])
        rng = random.Random(_seed(stream, rec["id"], bq, "random"))
        sel = (frozen["selector"] if arm == "trained" else frozen["selector_no_regret"]) if learned else None
        out = investigate(rec, coll["cands"], arm, budget, bq, rng=rng, selector=sel, costs=costs, cfg=cfg)
        ld = out["leader"]
        if out["status"] == "submitted":
            status = "verified" if grade(ld["ast"], rec) else "wrong"
        else:
            status = "abstained"
        counters = dict(budget.c)
        qs = out["queries"]
        row.update(status=status, reason=out["reason"], init=out["init"], resumed=out["resumed"], n_queries=len(qs),
                   splitting_queries=sum(q["splits"] for q in qs), falsifying_queries=sum(q["falsified"] > 0 for q in qs), queries=qs,
                   unresolved=out["unresolved"], agreement_unproven=out["agreement_unproven"], final_check=out["final_check"],
                   final=out["vs"].summary(),
                   leader=None if ld is None else dict(origin=ld["origin"], edge=ld["edge"], tags=ld["tags"], ast=_short(ld["ast"]),
                                                       provenance=ld.get("provenance")),
                   leader_prior=None if (sel is None or ld is None) else round(sel.leader_prior(ld), 6),
                   collection=dict(shared=not learned, candidates=len(coll["cands"]), exhausted=coll["exhausted"],
                                   wall=round(coll["wall"], 3)),
                   counters=counters, over_cap=_over_cap(counters, cfg["fc_cap"]) + (["queries"] if len(qs) > bq else []),
                   exhausted=budget.exhausted)
    except Exception as e:                                             # noqa: BLE001 - recorded as an error row
        row.update(status="error", error=f"{type(e).__name__}: {e}"[:300], trace=traceback.format_exc()[-800:], over_cap=[])
    row["wall"] = round(time.time() - t0, 3)
    return row


def single_shot_row(rec, stream, cfg, shared):
    """Diagnostic single-shot heuristic baseline: submit the FIRST candidate of the shared (uniform-cost) collection; no query, no
    shadows, no abstention beyond 'no candidate'. Charged with the shared collection's counters only. Not a control arm."""
    row = dict(suite="ambiguous", task=rec["id"], family=rec["family"], held_out=rec["held_out"], stream=stream, B_q=0,
               arm="single_shot", n_queries=0)
    try:
        if rec["id"] not in shared:
            shared[rec["id"]] = fresh_collection(rec["task"], S.Costs(), cfg)
        coll = shared[rec["id"]]
        cands = coll["cands"]
        if not cands:
            status = "abstained"
        else:
            status = "verified" if grade(cands[0]["expanded"], rec) else "wrong"
        counters = dict(coll["counters"])
        row.update(status=status, reason=None if cands else "no_candidate", counters=counters,
                   over_cap=_over_cap(counters, cfg["fc_cap"]), provenance=cands[0].get("provenance") if cands else None)
    except Exception as e:                                             # noqa: BLE001 - recorded as an error row
        row.update(status="error", error=f"{type(e).__name__}: {e}"[:300], over_cap=[])
    return row


# ------------------------------------------------------------------ pipeline suite (out of sandbox)
def _pipeline_specs():
    """edit_reachable = the engineer's DESIGN claim that one proposals13 shadow edit repairs the broken stage (True for P1-P3, P6). P4
    and P5 need more than one edit / a different measure, so a repair must come from the atomic synthesizer; the measured method of
    every repair is recorded per row regardless of this declaration. held_out_schema = the spec's schema / generator is used by no
    source family (P6)."""
    clean = "SELECT oid, cust, amt FROM orders WHERE amt >= 0"
    kept = "SELECT id, x FROM t WHERE id >= 0"
    inner = "SELECT oid, tier FROM clean c JOIN custs k ON c.cust = k.cid"
    valid = "SELECT inv, vend, total FROM invoices WHERE total >= 0"
    joined = "SELECT inv, vend, region FROM valid v LEFT JOIN vendors d ON v.vend = d.vid"
    specs = [
        dict(name="P1_left_lookup", gen=_g_lookup, requires="left", edit_reachable=True,
             broken=[("clean", clean), ("enriched", inner)],
             reference=[("clean", clean), ("enriched", "SELECT oid, tier FROM clean c LEFT JOIN custs k ON c.cust = k.cid")]),
        dict(name="P2_count_col", gen=_g_count, edit_reachable=True,
             broken=[("by_g", "SELECT g, COUNT(*) AS n FROM e GROUP BY g")],
             reference=[("by_g", "SELECT g, COUNT(v) AS n FROM e GROUP BY g")]),
        dict(name="P3_null_default", gen=_g_null, edit_reachable=True,
             broken=[("kept", kept), ("out", "SELECT id, x AS y FROM kept")],
             reference=[("kept", kept), ("out", "SELECT id, COALESCE(x, 0) AS y FROM kept")]),
        dict(name="P4_lookup_default", gen=_g_lookup, requires="left", edit_reachable=False,
             broken=[("clean", clean), ("enriched", inner)],
             reference=[("clean", clean),
                        ("enriched", "SELECT oid, COALESCE(tier, 'none') AS tier FROM clean c LEFT JOIN custs k ON c.cust = k.cid")]),
        dict(name="P5_sum_measure", gen=_g_sum, edit_reachable=False,
             broken=[("tot", "SELECT k, COUNT(*) AS total FROM p GROUP BY k")],
             reference=[("tot", "SELECT k, SUM(amt) AS total FROM p GROUP BY k")]),
        dict(name="P6_vendor_rollup", gen=_g_invoices, requires="left", edit_reachable=True, held_out_schema=True,
             broken=[("valid", valid), ("joined", joined), ("per_vendor", "SELECT vend, COUNT(*) AS n FROM joined GROUP BY vend")],
             reference=[("valid", valid), ("joined", joined),
                        ("per_vendor", "SELECT vend, COUNT(region) AS n FROM joined GROUP BY vend")]),
    ]
    kinds = tuple(getattr(C, "JOIN_KINDS", ()))
    return [s for s in specs if s.get("requires") is None or s["requires"] in kinds]


def build_pipeline_case(spec, seed):
    rng = random.Random(seed)
    obs_in = [spec["gen"](rng, "edge") for _ in range(3)]
    hid_in = [spec["gen"](rng, "edge") for _ in range(2)]
    ref = PL.Pipeline.from_sql(spec["reference"], obs_in[0])
    broken = PL.Pipeline.from_sql(spec["broken"], obs_in[0])
    batches = []
    for j, inp in enumerate(obs_in):
        outs, errs = ref.run(inp)
        if errs:
            raise ValueError(f"reference pipeline failed: {errs}")
        batches.append(dict(name=f"b{j}", inputs=inp, observed={k: v for k, v in outs.items() if v is not None}))
    loc = PL.localize(broken, batches)
    return dict(id=f"{spec['name']}-{seed}", spec=spec["name"], seed=seed, ref=ref, broken=broken, batches=batches,
                hidden=[dict(name=f"h{j}", inputs=inp) for j, inp in enumerate(hid_in)], bug_visible=loc["broken"] is not None,
                edit_reachable=spec.get("edit_reachable"), held_out_schema=bool(spec.get("held_out_schema")))


def _grade_pipeline(pipe, case):
    """core11 grading (evaluation only): every reference stage reproduced on every hidden batch."""
    for b in case["hidden"]:
        outs, _ = pipe.run(b["inputs"])
        ref_outs, _ = case["ref"].run(b["inputs"])
        for name in case["ref"].names():
            if not PL._same(outs.get(name), ref_outs.get(name)):
                return False
    return True


def _native_hidden(pipe, case):
    """Native grading (evaluation only): the repaired pipeline compiled to SQL on SQLite over the hidden batches agrees on every stage."""
    bs = []
    for b in case["hidden"]:
        ref_outs, _ = case["ref"].run(b["inputs"])
        bs.append(dict(name=b["name"], inputs=b["inputs"], observed={k: v for k, v in ref_outs.items() if v is not None}))
    nat = PL.native_pipeline_check(pipe, bs, None, None)
    return dict(all_agree=bool(nat["all_agree"]), tally=nat["tally"], engine=nat["engine"])


_DUCK_TYPE = {C.INT: "BIGINT", C.NUM: "DOUBLE", C.STR: "VARCHAR", C.BOOL: "BOOLEAN"}
_REAL_CAST = re.compile(r"\bAS REAL\)")                                  # SQLite REAL is 64-bit; DuckDB REAL is 32-bit -> DOUBLE


def _duck_val(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    try:
        return float(v)                                                # Decimal / HUGEINT-like results
    except (TypeError, ValueError):
        return str(v)


def _duckdb_hidden(pipe, case):
    """Third-engine grading (evaluation only): the repaired pipeline's compiled SQL executed natively on DuckDB over the hidden batches,
    every reference stage compared with its core11 reference output. status 'unavailable' when duckdb is not importable."""
    if _duckdb is None:
        return dict(engine="duckdb", status="unavailable", tally={}, version=None)
    tally = Counter()
    for b in case["hidden"]:
        ref_outs, _ = case["ref"].run(b["inputs"])
        comp = PL.compile_pipeline_sql(pipe, b["inputs"])
        try:
            con = _duckdb.connect(":memory:")
        except Exception:                                              # noqa: BLE001
            tally["connect_error"] += 1
            continue
        try:
            for name, R in b["inputs"].items():
                defs = ", ".join(f"{PL._q(c)} {_DUCK_TYPE.get(t, 'VARCHAR')}" for c, t in zip(R.cols, R.types))
                con.execute(f"CREATE TABLE {PL._q(name)} ({defs})")
                if R.rows:
                    marks = ", ".join("?" for _ in R.cols)
                    con.executemany(f"INSERT INTO {PL._q(name)} VALUES ({marks})", [tuple(_duck_val(v) for v in r) for r in R.rows])
            for c in comp:
                E = ref_outs.get(c["name"])
                if c["statement"] is None:
                    st = "unsupported"
                else:
                    try:
                        con.execute(_REAL_CAST.sub("AS DOUBLE)", c["statement"]))
                        if E is None:
                            continue
                        cur = con.execute(f"SELECT * FROM {PL._q(c['name'])}")
                        names = [d[0] for d in cur.description]
                        rows = [tuple(_duck_val(v) for v in r) for r in cur.fetchall()]
                        st = "agree" if PL._bag_equal(names, rows, E) else "disagree"
                    except Exception:                                  # noqa: BLE001 - any DuckDB error is a non-agreement
                        st = "error"
                tally[st] += 1
        except Exception:                                              # noqa: BLE001
            tally["load_error"] += 1
        finally:
            con.close()
    status = "agree" if tally and set(tally) == {"agree"} else ("disagree" if tally.get("disagree") else "error")
    return dict(engine="duckdb", status=status, tally=dict(tally), version=DUCKDB_VERSION)


def pipeline_row(case, stream, bq, arm, cfg, frozen):
    t0 = time.time()
    static = arm in STATIC_MENU_ARMS
    row = dict(suite="pipelines", task=case["id"], family=case["spec"], held_out=bool(case.get("held_out_schema")),
               held_out_schema=bool(case.get("held_out_schema")), stream=stream, B_q=bq, arm=arm, bug_visible=case["bug_visible"],
               edit_reachable=case.get("edit_reachable"), menu="static" if static else "program_aware")
    try:
        rng = random.Random(_seed(stream, case["id"], bq, "random"))
        sel = frozen["selector"] if arm == "trained" else None
        res = PL.repair_pipeline(case["broken"], case["batches"], native=True, costs=frozen["costs"] if arm == "trained" else None,
                                 oracle=PL.pipeline_oracle(case["ref"]), chooser=lambda split: L.pick(arm, split, selector=sel, rng=rng),
                                 prior=sel.leader_prior if sel is not None else None, menu=_static_menu if static else None,
                                 query_budget=bq, wall=cfg["lift_wall"], fc_cap=cfg["fc_cap"])
        core_ok, hidden_native, hidden_duck, reason = None, None, None, None
        if res["status"] == "repaired":
            core_ok = _grade_pipeline(res["pipeline"], case)
            hidden_native = _native_hidden(res["pipeline"], case)
            hidden_duck = _duckdb_hidden(res["pipeline"], case)
            status = "verified" if core_ok and hidden_native["all_agree"] else "wrong"
            if status == "wrong":
                reason = "native_hidden_disagree" if core_ok else "hidden_core_mismatch"
        else:
            status, reason = "abstained", res["status"]
        lifts = [s["lift"] for s in res["steps"]]
        work = dict(res.get("work") or {})                             # ONE shared row budget: localisation + lifts + verification
        n_q = int(res.get("queries_used") or 0)
        over = sorted(set(res.get("over_cap") or []) | set(_over_cap(work, cfg["fc_cap"])) | ({"queries"} if n_q > bq else set()))
        native = res.get("native") or {}
        methods = res.get("repair_methods") or []
        ms = sorted({m.get("method") for m in methods if m.get("method")})
        verified_method = (ms[0] if len(ms) == 1 else "mixed") if status == "verified" and ms else None
        row.update(status=status, reason=reason, repair_status=res["status"], repair_reason=res.get("reason"),
                   lifts=[dict(stage=lf.get("stage"), status=lf["status"], reason=lf["reason"], method=lf.get("method"),
                               queries_used=lf.get("queries_used"), attempts=lf.get("attempts"), accepted_edge=lf.get("accepted_edge"),
                               sql=lf.get("sql"), native_agree=lf.get("native_agree")) for lf in lifts],
                   repair_methods=_js(methods), edit_only=res.get("edit_only", 0), synthesized=res.get("synthesized", 0),
                   verified_method=verified_method, n_queries=n_q,
                   splitting_queries=sum(q.get("splitting", 0) > 0 for lf in lifts for q in lf.get("queries", [])),
                   falsifying_queries=sum(q.get("falsified", 0) > 0 for lf in lifts for q in lf.get("queries", [])),
                   native_tally=native.get("tally"), native_all_agree=native.get("all_agree"), end_to_end=res["end_to_end"],
                   hidden_core_ok=core_ok, hidden_native=hidden_native, hidden_duckdb=hidden_duck,
                   multi_engine_agree=bool(status == "verified" and hidden_duck and hidden_duck["status"] == "agree"),
                   counters=work, over_cap=over, exhausted=res.get("exhausted"))
    except Exception as e:                                             # noqa: BLE001 - recorded as an error row
        row.update(status="error", error=f"{type(e).__name__}: {e}"[:300], trace=traceback.format_exc()[-800:], over_cap=[])
    row["wall"] = round(time.time() - t0, 3)
    return row


# ------------------------------------------------------------------ summaries
def summarize(rows):
    out = {}
    for r in rows:
        k = f"{r['stream']}|B{r['B_q']}|{r['arm']}"
        s = out.setdefault(k, Counter())
        s["rows"] += 1
        s[r["status"]] += 1
        s["submitted"] += r["status"] in ("verified", "wrong")
        s["queries"] += r.get("n_queries", 0)
        s["splitting_queries"] += r.get("splitting_queries", 0)
        s["falsifying_queries"] += r.get("falsifying_queries", 0)
        s["probe_evals"] += (r.get("counters") or {}).get("probe_evals", 0)
        s["max_full_checks"] = max(s["max_full_checks"], (r.get("counters") or {}).get("full_checks", 0))
        s["over_cap_rows"] += bool(r.get("over_cap"))
        if r.get("verified_method"):
            s[f"verified_by_{r['verified_method']}"] += 1
        hd = r.get("hidden_duckdb")
        if hd and r["status"] == "verified":
            s[f"verified_duckdb_{hd['status']}"] += 1
        if r.get("reason") == "incomplete_scoring":
            s["incomplete_scoring"] += 1
        if r.get("reason") == "budget":
            s["budget_abstentions"] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def by_family(rows):
    out = {}
    for r in rows:
        k = f"{r['family']}|B{r['B_q']}|{r['arm']}"
        s = out.setdefault(k, Counter())
        s[r["status"]] += 1
        if r.get("verified_method"):
            s[f"verified_by_{r['verified_method']}"] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def contrasts(summary, streams, bq):
    def v(stream, arm, f="verified"):
        return summary.get(f"{stream}|B{bq}|{arm}", {}).get(f, 0)
    out = {f"trained-{c}": [v(s, "trained") - v(s, c) for s in streams] for c in ("fixed", "random", "untrained")}
    out["untrained-fixed"] = [v(s, "untrained") - v(s, "fixed") for s in streams]
    out["wrong"] = {a: [v(s, a, "wrong") for s in streams] for a in ARMS}
    return out


def verdict(con, streams):
    comps = ("fixed", "random", "untrained")
    safe = all(con["wrong"]["trained"][i] <= min(con["wrong"][c][i] for c in comps) for i in range(len(streams)))
    if all(d >= 2 for c in comps for d in con[f"trained-{c}"]) and safe:
        return "positive"
    if any(all(d <= -2 for d in con[f"trained-{c}"]) for c in comps):
        return "negative"
    return "mixed"


# ------------------------------------------------------------------ charter section 10 progression metrics
def _sel(rows, stream, arm, bq=None, held_out=None):
    return [r for r in rows if r["stream"] == stream and r["arm"] == arm and (bq is None or r["B_q"] == bq)
            and (held_out is None or bool(r.get("held_out")) == held_out) and r["status"] != "error"]


def _cnt(rs, status):
    return sum(r["status"] == status for r in rs)


def _rel(rs):
    """(verified - wrong) / rows, None for no rows."""
    return None if not rs else round((_cnt(rs, "verified") - _cnt(rs, "wrong")) / len(rs), 6)


def _cost_per_solved(rs):
    v = _cnt(rs, "verified")
    if not v:
        return None, None
    work = sum((r.get("counters") or {}).get("full_checks", 0) + (r.get("counters") or {}).get("probe_evals", 0) for r in rs)
    return round(work / v, 3), round(sum(r.get("n_queries", 0) for r in rs) / v, 3)


def _flag(x):
    return "undefined" if x is None else ("positive" if x > 0 else "non_positive")


def regret_ablation_contrasts(rows, ablation, streams, budgets):
    """trained vs trained_no_regret (identical source experience, guide costs, collection, B_q and caps) per stream and B_q."""
    out = {}
    for b in budgets:
        d = {}
        for s in streams:
            tr, ab = _sel(rows, s, "trained", b), _sel(ablation, s, ABLATION_ARM, b)
            d[s] = dict(trained_verified=_cnt(tr, "verified"), trained_wrong=_cnt(tr, "wrong"), no_regret_verified=_cnt(ab, "verified"),
                        no_regret_wrong=_cnt(ab, "wrong"), rows=len(ab),
                        verified_diff=None if not ab or not tr else _cnt(tr, "verified") - _cnt(ab, "verified"))
        out[f"B{b}"] = d
    return out


def progression_metrics(rows, baselines, prow, streams, bq, learned, ablation=None):
    """The five mandatory metrics per stream, from measured rows only (None when undefined; never imputed)."""
    out = {}
    for s in streams:
        tr, un = _sel(rows, s, "trained", bq), _sel(rows, s, "untrained", bq)
        (tw, tq), (uw, uq) = _cost_per_solved(tr), _cost_per_solved(un)
        l2l = None if tw is None or uw is None or uw == 0 else round((uw - tw) / uw, 6)
        l2l_q = None if tq is None or uq is None or uq == 0 else round((uq - tq) / uq, 6)
        th, uh = _sel(rows, s, "trained", bq, True), _sel(rows, s, "untrained", bq, True)
        lift = (_cnt(th, "verified") - _cnt(uh, "verified")) if th and uh else None
        n_ho = len({r["task"] for r in th})
        rt, ru = _rel(tr), _rel(un)
        ab = _sel(ablation or [], s, ABLATION_ARM, bq)
        ra = _rel(ab)
        sed = None if rt is None or ra is None else round(rt - ra, 6)
        combined = None if rt is None or ru is None else round(rt - ru, 6)
        ver_ho = [r for r in th if r["status"] == "verified"]
        reuse = None if not ver_ho else round(sum(bool(((r.get("leader") or {}).get("provenance") or {}).get("relational")
                                                      or ((r.get("leader") or {}).get("provenance") or {}).get("scalar"))
                                                 for r in ver_ho) / len(ver_ho), 6)
        prior_rate = None if not ver_ho else round(sum(bool(r.get("leader_prior")) for r in ver_ho) / len(ver_ho), 6)
        ss = [r for r in baselines if r["stream"] == s and r["status"] != "error"]
        rs_ = _rel(ss)
        era = None if rt is None or rs_ is None else round(rt - rs_, 6)
        ptr = _sel(prow, s, "trained", bq)
        pctl = [_rel(_sel(prow, s, a, bq)) for a in ("fixed", "random", "untrained")]
        pctl = [x for x in pctl if x is not None]
        p_era = None if _rel(ptr) is None or not pctl else round(_rel(ptr) - max(pctl), 6)
        pho = _sel(prow, s, "trained", bq, True)
        lr = learned.get(s, {})
        st = lr.get("selector_stats", {})
        out[s] = dict(
            learning_to_learn_gain=dict(value=l2l, flag=_flag(l2l), work_per_solved=dict(trained=tw, untrained=uw),
                                        queries_per_solved=dict(trained=tq, untrained=uq), query_reduction=l2l_q,
                                        definition="relative reduction of (full_checks + probe_evals) per verified task, trained vs untrained"),
            transfer_efficiency=dict(value=lift, flag=_flag(lift), per_held_out_task=None if lift is None or not n_ho else round(lift / n_ho, 6),
                                     held_out_tasks=n_ho, held_out_schema_pipeline_reliability=_rel(pho),
                                     definition="trained - untrained verified on held-out families"),
            self_evolution_delta=dict(value=sed, flag=_flag(sed), trained_reliability=rt, no_regret_reliability=ra,
                                      verified_gain=None if not ab or not tr else _cnt(tr, "verified") - _cnt(ab, "verified"),
                                      combined_trained_vs_untrained=combined, static_reliability=ru,
                                      regret_updates=st.get("regret_updates", 0), shortcut_demotions=st.get("shortcut_demotions", 0),
                                      demoted_shortcuts=lr.get("demoted_shortcuts", []),
                                      definition="(verified-wrong)/rows: trained minus trained_no_regret (same source experience, guide, "
                                                 "collection, B_q, caps; no audit_choice / audit_submission) = regret-isolated gain"),
            unseen_domain_reuse_rate=dict(value=reuse, flag=_flag(reuse), verified_held_out=len(ver_ho), prior_participation_rate=prior_rate,
                                          definition="share of trained verified held-out rows whose leader uses admitted library functions "
                                                     "(none admitted in phase 13)"),
            enterprise_reliability_advantage=dict(value=era, flag=_flag(era), trained_reliability=rt, single_shot_reliability=rs_,
                                                  pipeline_vs_best_control=p_era, llm_baseline="not available (no LLM baseline run)",
                                                  definition="(verified-wrong)/rows: trained minus single-shot first-candidate heuristic"))
    names = ("learning_to_learn_gain", "transfer_efficiency", "self_evolution_delta", "unseen_domain_reuse_rate",
             "enterprise_reliability_advantage")
    allpos = {n: all(out[s][n]["flag"] == "positive" for s in streams) if streams else False for n in names}
    return dict(primary_B_q=bq, per_stream=out, positive_in_every_stream=allpos, all_five_positive=all(allpos.values()))


def planned_seeds(cfg, n_fams, n_specs):
    """Every seed the configuration would use, per namespace (for the pre-run isolation check)."""
    src = {source_seed(si, fi, i) for si in range(len(cfg["streams"])) for fi in range(n_fams) for i in range(cfg["source_instances"])}
    ev = {eval_seed(fi, i) for fi in range(n_fams) for i in range(cfg["eval_instances"])}
    pipe = {pipeline_seed(pi, i) for pi in range(n_specs) for i in range(cfg["pipeline_instances"])} if cfg["pipelines"] else set()
    return src, ev, pipe


# ------------------------------------------------------------------ experiment
def run_experiment(grant_seconds=DEFAULT_GRANT_S, out_dir=DEFAULT_OUT, quick=False, invocation=None, **overrides):
    cfg = dict(DEFAULT)
    if quick:
        cfg.update(QUICK)
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    cfg["streams"], cfg["budgets"] = tuple(cfg["streams"]), tuple(sorted(set(int(b) for b in cfg["budgets"])))
    if not 0 < int(cfg["fc_cap"]) <= FC_LIMIT:
        raise ValueError(f"fc_cap must be in 1..{FC_LIMIT}")
    if float(grant_seconds) <= 0:
        raise ValueError("grant_seconds must be positive")
    t_start = time.time()
    grant = float(grant_seconds)
    deadline = t_start + SAFETY * grant
    fams = _families()
    specs = _pipeline_specs()
    streams, budgets = cfg["streams"], cfg["budgets"]
    plan_src, plan_eval, plan_pipe = planned_seeds(cfg, len(fams), len(specs))
    if plan_src & plan_eval or plan_src & plan_pipe or plan_eval & plan_pipe:
        raise ValueError("seed namespaces overlap for this configuration (source / eval / pipeline isolation)")
    _log(f"grant {grant:.0f}s; families {[f['name'] for f in fams]}; streams {streams}; B_q {budgets}; duckdb {DUCKDB_VERSION}")

    eval_seeds = [eval_seed(fi, i) for i in range(cfg["eval_instances"]) for fi in range(len(fams))]
    eval_recs, build_errors = [], []
    for i in range(cfg["eval_instances"]):
        for fi, fam in enumerate(fams):
            try:
                eval_recs.append(build_task(fam, eval_seed(fi, i), "eval"))
            except Exception as e:                                     # noqa: BLE001 - recorded
                build_errors.append(dict(task=f"T{eval_seed(fi, i)}", family=fam["name"], error=f"{type(e).__name__}: {e}"[:300]))

    # ---- source training (isolated from evaluation seeds; privileged supervision metered)
    trained, learned, src_seeds, supervision = {}, {}, set(), {}
    t_src = time.time()
    for si, stream in enumerate(streams):
        sd = t_start + grant * cfg["source_share"] * (si + 1) / len(streams)
        tr = source_train(stream, si, fams, cfg, sd)
        src_seeds |= set(tr["seeds"])
        learned[stream] = _learned_report(tr)
        supervision[stream] = tr["meter"].report()
        sel = tr["selector"].copy(name=f"trained-{stream}-frozen", frozen=True)
        snr = tr["selector_no_regret"].copy(name=f"trained-no-regret-{stream}-frozen", frozen=True)
        guide = tr["guide"].freeze()
        trained[stream] = dict(selector=sel, selector_no_regret=snr, guide=guide, costs=guide.costs(), fp_sel=sel.fingerprint(),
                               fp_sel_nr=snr.fingerprint(), fp_guide=guide.fingerprint())
        _log(f"source {stream}: {learned[stream]['source_episodes']} episodes, demoted {learned[stream]['demoted_shortcuts']}, "
             f"supervision {supervision[stream]['used']} refused {supervision[stream]['refused']}")
    t_src = time.time() - t_src
    overlap = sorted(src_seeds & set(eval_seeds))
    sup_over = {s: d["over_cap"] for s, d in supervision.items() if d["over_cap"]}

    # ---- ambiguous suite (+ regret ablation and diagnostic single-shot baseline, kept apart from the control rows)
    rows, ablation, baselines, shared, tcache, groups_done, max_group, missing = [], [], [], {}, {}, 0, 0.0, []
    amb_deadline = t_start + grant * cfg["ambiguous_share"]
    for rec in eval_recs:
        if groups_done and time.time() + max_group > min(amb_deadline, deadline):
            missing.append(rec["id"])
            continue
        g0 = time.time()
        for stream in streams:
            for bq in budgets:
                for arm in ARMS:
                    rows.append(eval_row(rec, stream, bq, arm, cfg, trained[stream], shared, tcache))
                if cfg["regret_ablation"]:
                    ablation.append(eval_row(rec, stream, bq, ABLATION_ARM, cfg, trained[stream], shared, tcache))
            baselines.append(single_shot_row(rec, stream, cfg, shared))
        groups_done += 1
        max_group = max(max_group, time.time() - g0)
        _log(f"{rec['id']} ({rec['family']}) done in {time.time() - g0:.1f}s")

    # ---- pipeline suite
    prow, pmissing, pbuild, pipe_seeds = [], [], [], set()
    if cfg["pipelines"]:
        pg_max = 0.0
        for pi, spec in enumerate(specs):
            for i in range(cfg["pipeline_instances"]):
                seed = pipeline_seed(pi, i)
                pipe_seeds.add(seed)
                if pg_max and time.time() + pg_max > deadline:
                    pmissing.append(f"{spec['name']}-{seed}")
                    continue
                g0 = time.time()
                try:
                    case = build_pipeline_case(spec, seed)
                except Exception as e:                                 # noqa: BLE001 - recorded
                    pbuild.append(dict(case=f"{spec['name']}-{seed}", error=f"{type(e).__name__}: {e}"[:300]))
                    continue
                for stream in streams:
                    for bq in budgets:
                        for arm in ARMS:
                            prow.append(pipeline_row(case, stream, bq, arm, cfg, trained[stream]))
                pg_max = max(pg_max, time.time() - g0)
                _log(f"{case['id']} done in {time.time() - g0:.1f}s")
    pipe_overlap = sorted(src_seeds & pipe_seeds)

    # ---- isolation audit, summaries, verdict, progression metrics
    iso = {s: dict(selector_unchanged=trained[s]["selector"].fingerprint() == trained[s]["fp_sel"],
                   no_regret_selector_unchanged=trained[s]["selector_no_regret"].fingerprint() == trained[s]["fp_sel_nr"],
                   guide_unchanged=trained[s]["guide"].fingerprint() == trained[s]["fp_guide"],
                   selector_frozen=trained[s]["selector"].frozen, no_regret_selector_frozen=trained[s]["selector_no_regret"].frozen,
                   guide_frozen=trained[s]["guide"].frozen, selector_fingerprint=trained[s]["fp_sel"],
                   no_regret_selector_fingerprint=trained[s]["fp_sel_nr"], guide_fingerprint=trained[s]["fp_guide"]) for s in streams}
    isolation_ok = (not overlap and not pipe_overlap
                    and all(all(v for k, v in d.items() if not k.endswith("fingerprint")) for d in iso.values()))
    primary = max(budgets)
    hard = [r for r in prow if r.get("edit_reachable") is False]
    hos = [r for r in prow if r.get("held_out_schema")]
    summ, psumm, hsumm, osumm = summarize(rows), summarize(prow), summarize(hard), summarize(hos)
    con = {f"B{b}": contrasts(summ, streams, b) for b in budgets}
    pcon = {f"B{b}": contrasts(psumm, streams, b) for b in budgets}
    hcon = {f"B{b}": contrasts(hsumm, streams, b) for b in budgets}
    ocon = {f"B{b}": contrasts(osumm, streams, b) for b in budgets}
    acon = regret_ablation_contrasts(rows, ablation, streams, budgets) if ablation else {}
    progression = progression_metrics(rows, baselines, prow, streams, primary, learned, ablation)
    all_rows = rows + prow
    over_rows = sum(bool(r.get("over_cap")) for r in all_rows + baselines + ablation)
    completed = sum(r["status"] in ("verified", "wrong", "abstained") for r in all_rows)
    expected_rows = len(eval_seeds) * len(streams) * len(budgets) * len(ARMS)
    duck_rows = [r for r in prow if r.get("hidden_duckdb")]
    duck_tally = dict(Counter(r["hidden_duckdb"]["status"] for r in duck_rows))
    duck_ran = _duckdb is not None and any(r["hidden_duckdb"]["status"] != "unavailable" for r in duck_rows)
    executed = list(PL.ENGINES) + (["duckdb"] if duck_ran else [])
    result = dict(
        phase=13, config=_js(cfg), grant_seconds=grant, invocation=_js(invocation or {}),
        environment=dict(python=sys.version.split()[0], platform=platform.platform(), machine=platform.machine(), duckdb=DUCKDB_VERSION),
        engines=dict(executed=executed, repair_gate=list(PL.ENGINES), duckdb_available=_duckdb is not None,
                     duckdb_hidden_grading=duck_tally,
                     multi_engine_transfer=("repairs gated by core11 + SQLite; compiled SQL of repaired pipelines additionally executed "
                                            "natively on DuckDB over hidden batches (evaluation grading only)" if duck_ran else
                                            "core11 + SQLite only (duckdb not importable in this environment)")
                     + "; no Polars / PySpark execution"),
        verdict_rule="positive: trained-X >= +2 verified for every X in {fixed, random, untrained} in every stream and trained wrong <= "
                     "every comparator's; negative: trained-X <= -2 for some X in every stream; else mixed (primary B_q = max)",
        verdict=dict(ambiguous=verdict(con[f"B{primary}"], streams) if rows else "no_rows",
                     pipelines=verdict(pcon[f"B{primary}"], streams) if prow else "no_rows",
                     pipelines_beyond_single_edit=verdict(hcon[f"B{primary}"], streams) if hard else "no_rows",
                     pipelines_held_out_schema=verdict(ocon[f"B{primary}"], streams) if hos else "no_rows", primary_B_q=primary),
        contrasts=dict(ambiguous=con, pipelines=pcon, pipelines_beyond_single_edit=hcon, pipelines_held_out_schema=ocon,
                       regret_ablation=acon),
        summary=dict(ambiguous=summ, pipelines=psumm, pipelines_beyond_single_edit=hsumm, pipelines_held_out_schema=osumm,
                     single_shot=summarize(baselines), regret_ablation=summarize(ablation)),
        by_family=dict(ambiguous=by_family(rows), pipelines=by_family(prow), single_shot=by_family(baselines),
                       regret_ablation=by_family(ablation)),
        pipeline_specs=[dict(name=s["name"], edit_reachable=s.get("edit_reachable"), held_out_schema=bool(s.get("held_out_schema")))
                        for s in specs],
        progression=progression,
        learned_by_nexus=learned,
        machinery="runner13 + proposals13 + selector13 + pipeline_lifter13 + synth12 (engineering team); hand-written generators",
        isolation=dict(ok=isolation_ok, source_seeds=sorted(src_seeds), eval_seeds=sorted(eval_seeds), pipeline_seeds=sorted(pipe_seeds),
                       seed_overlap=overlap, pipeline_seed_overlap=pipe_overlap,
                       seed_namespaces=dict(source=f"{SOURCE_BASE} + {SOURCE_STREAM_STRIDE}*stream + 100*family + i",
                                            eval=f"{EVAL_BASE} + 100*family + i", pipeline=f"{PIPE_BASE} + 100*spec + i"),
                       streams=iso),
        checks=dict(over_cap_rows=over_rows, completed_rows=completed, error_rows=sum(r["status"] == "error" for r in all_rows),
                    baseline_error_rows=sum(r["status"] == "error" for r in baselines),
                    ablation_rows=len(ablation), ablation_error_rows=sum(r["status"] == "error" for r in ablation),
                    budget_abstentions=sum(r.get("reason") == "budget" for r in rows + ablation),
                    source_supervision=supervision, source_supervision_over_cap=sup_over,
                    expected_ambiguous_rows=expected_rows, ambiguous_rows=len(rows), pipeline_rows=len(prow),
                    pipeline_rows_beyond_single_edit=len(hard), pipeline_rows_held_out_schema=len(hos),
                    duckdb_available=_duckdb is not None, duckdb_graded_rows=len(duck_rows), missing_tasks=missing,
                    missing_pipeline_cases=pmissing, task_build_errors=build_errors, pipeline_build_errors=pbuild, isolation_ok=isolation_ok),
        wall=dict(total=round(time.time() - t_start, 2), source=round(t_src, 2)),
        rows=all_rows, baselines=baselines, ablations=ablation)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "results.json"), "w") as fh:
            json.dump(_js({k: v for k, v in result.items() if k not in ("rows", "baselines", "ablations")}), fh, indent=1, sort_keys=True)
        for name, rs in (("rows.jsonl", all_rows), ("baselines.jsonl", baselines), ("ablations.jsonl", ablation)):
            with open(os.path.join(out_dir, name), "w") as fh:
                for r in rs:
                    fh.write(json.dumps(_js(r), sort_keys=True) + "\n")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEXUS Phase 13 bounded experiment runner")
    ap.add_argument("--grant-seconds", type=float, default=DEFAULT_GRANT_S)
    ap.add_argument("--execute", action="store_true", help="run the full bounded experiment (the only mode; accepted for the coordinator)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--eval-instances", type=int)
    ap.add_argument("--source-instances", type=int)
    ap.add_argument("--pipeline-instances", type=int)
    ap.add_argument("--budgets", type=int, nargs="+")
    ap.add_argument("--fc-cap", type=int)
    ap.add_argument("--collect-wall", type=float)
    ap.add_argument("--investigate-wall", type=float)
    ap.add_argument("--no-pipelines", action="store_true")
    ap.add_argument("--no-regret-ablation", action="store_true")
    a, unknown = ap.parse_known_args(argv)
    if unknown:
        _log(f"ignoring unrecognised arguments: {unknown}")
    invocation = dict(argv=list(sys.argv[1:] if argv is None else argv), execute=a.execute, ignored=unknown)
    res = run_experiment(a.grant_seconds, a.out, a.quick, invocation=invocation, eval_instances=a.eval_instances,
                         source_instances=a.source_instances, pipeline_instances=a.pipeline_instances, budgets=a.budgets, fc_cap=a.fc_cap,
                         collect_wall=a.collect_wall, investigate_wall=a.investigate_wall, pipelines=False if a.no_pipelines else None,
                         regret_ablation=False if a.no_regret_ablation else None)
    prog = res["progression"]
    brief = dict(verdict=res["verdict"], checks={k: v for k, v in res["checks"].items() if not isinstance(v, list) or len(v) < 20},
                 summary=res["summary"], contrasts=res["contrasts"], engines=res["engines"], pipeline_specs=res["pipeline_specs"],
                 progression=dict(primary_B_q=prog["primary_B_q"], positive_in_every_stream=prog["positive_in_every_stream"],
                                  all_five_positive=prog["all_five_positive"],
                                  values={s: {n: m["value"] for n, m in d.items()} for s, d in prog["per_stream"].items()}),
                 isolation=dict(ok=res["isolation"]["ok"], seed_overlap=res["isolation"]["seed_overlap"],
                                pipeline_seed_overlap=res["isolation"]["pipeline_seed_overlap"]),
                 learned={s: dict(demoted_shortcuts=d["demoted_shortcuts"], selector_fingerprint=d["selector_fingerprint"][:16],
                                  no_regret_fingerprint=d["no_regret_selector"]["fingerprint"][:16], source_episodes=d["source_episodes"],
                                  skipped_learning_steps=d["skipped_learning_steps"]) for s, d in res["learned_by_nexus"].items()},
                 wall=res["wall"])
    print(json.dumps(_js(brief), indent=1, sort_keys=True))
    if res["checks"]["over_cap_rows"] or not res["checks"]["isolation_ok"] or res["checks"]["source_supervision_over_cap"]:
        return 1
    if res["checks"]["completed_rows"] == 0:
        return 2
    return 0


__all__ = ["run_experiment", "main", "build_task", "investigate", "source_train", "collect_into", "grade", "make_rel", "summarize",
           "contrasts", "verdict", "progression_metrics", "regret_ablation_contrasts", "single_shot_row", "build_pipeline_case",
           "source_seed", "eval_seed", "pipeline_seed", "planned_seeds", "SourceMeter", "SOURCE_CAPS", "ARMS", "ABLATION_ARM", "STREAMS",
           "DUCKDB_VERSION"]


if __name__ == "__main__":
    sys.exit(main())
