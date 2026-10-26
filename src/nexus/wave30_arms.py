"""Wave 30 (first increment): prover-side Evidence Objects for the read-only Checker Kernel, and the A0 / A1 / A1b
representation arms on `dev` and `admission_val`.

* Prover: the Wave 29 Occam-margin certifier (`certify_shell`) over the arm's tool set, with up to PROBE_BUDGET
  rich verification probes (`choose_verify`) while it is ambiguous. Its output is an Evidence Object
  (serialised mechanism specs, scope, verified-by-kernel pruning lemmas, trace).
* Checker: `checker_kernel.check` assigns exhaustive_UNIQUE / proposal_relative_UNIQUE / AMBIGUOUS(k) / ABSTAIN.
  Only kernel labels count. A task is solved iff the kernel issues a UNIQUE label whose answer equals the truth.
  A UNIQUE label with a wrong answer is a false certificate. The label is relative to the declared scope; a
  teacher outside the scope can make a scope-relative UNIQUE wrong.
* Arms:
  * A0 = base F / S / Sort + the 10-schema comp menu (Wave 26 grammar).
  * A1 = A0 + a fixed richer DSL: projection, arithmetic maps, accumulators (prefix sum, running max,
    difference), objects (run heads, group counts), bounded loops (repeat 2-3 x diff / rotate). No coder.
  * A1b = A1 tools, proposed by a no-pretraining wake-sleep prior over operator families, learned only from
    NEXUS's own kernel-certified solutions earlier in the same stream (Dirichlet(1) start). It searches the
    top-mass families first (proposal scope, labelled proposal_relative). If that scope has no fitting
    program, it escalates to the full A1 scope (exhaustive), and the cost of both is charged.
* Cost = prover work + kernel chains checked + C_ORACLE per probe (one meter, Tycho).
The prover's A1 mechanisms are implemented here independently of the kernel interpreter. A disagreement
between them shows up as a kernel ABSTAIN (candidate_fails).
"""
from __future__ import annotations

import math
import random
from collections import Counter

from nexus import checker_kernel as K
from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, NONE_FOUND, UNIQUE, meter
from nexus.wave25_factored import Mech, Pred, get, ints_world, run, _num
from nexus.wave26_phase1 import records_world_f
from nexus.wave26_phase4 import C_ORACLE, PROBE_BUDGET, Comp, Library, all_schemas, instantiate
from nexus.wave24_v4_core import Searcher
from nexus.wave29_core import choose_verify, violated

DEPTH = 2
PROVER_BUDGET = 6_000_000      # harness-local Searcher budget (the frozen Wave 26 CERT_BUDGET is not touched)
REC_FIELDS = 3                 # 3-field records worlds keep the depth-2 scope within prover / kernel caps


class _R:
    pass


def certify_exact(public, query, tools, m):
    """Unpruned Searcher to the minimal size, then the k_min + 1 shell (Occam margin); UNIQUE iff all agree."""
    s = Searcher(tuple(public), query, tools, popper=True, m=meter(PROVER_BUDGET), partial_depth=0, max_depth=DEPTH)
    r = s.run_to(DEPTH)
    hyps = list(r.hypotheses) if r.status in (UNIQUE, AMBIGUOUS) else []
    unknown = r.status not in (UNIQUE, AMBIGUOUS, NONE_FOUND)
    if hyps and r.size < DEPTH:
        try:
            found = s.level()
            hyps += [(tuple(t.name for t in p), q, p) for p, q in found.values()]
        except WorkExhausted:
            unknown = True
    m.charge("prover_work_units", s.m.total)
    out = _R()
    seen, merged = set(), []
    for h in hyps:
        if vkey(h[1]) not in seen:
            seen.add(vkey(h[1]))
            merged.append(h)
    out.hypotheses = merged
    out.size = r.size
    out.status = NONE_FOUND if not merged and not unknown else (
        "EXHAUSTED" if unknown and not merged else (UNIQUE if len(seen) == 1 and not unknown else AMBIGUOUS))
    return out


# --------------------------------------------------------------------------- serialisation (prover -> kernel)
def pred_spec(p):
    return {"path": p.path, "cmp": p.op, "val": p.val}


def spec_of(fn):
    if isinstance(fn, A1Op):
        return fn.spec
    if isinstance(fn, Mech):
        if fn.role == "F":
            return {"op": "F", "pred": pred_spec(fn.slots[0])}
        o = fn.slots[1] if fn.role == "S" else fn.slots[0]
        # wave25 Order.key ignores `desc` for position order: serialise the prover's actual semantics
        desc = bool(o.desc) if o.path != "#" else False
        if fn.role == "S":
            return {"op": "S", "k": fn.slots[0], "path": o.path, "desc": desc}
        if fn.role == "Sort":
            return {"op": "Sort", "path": o.path, "desc": desc}
    if isinstance(fn, Comp):
        cp = pred_spec(fn.cparam) if isinstance(fn.cparam, Pred) else fn.cparam
        return {"op": "comp", "path": fn.order.path, "desc": bool(fn.order.desc), "cond": fn.cond, "cparam": cp,
                "transform": fn.transform, "tparam": fn.tparam}
    raise TypeError(f"unserialisable mechanism {fn!r}")


def post_spec(post):
    kind, p = post
    if kind == "len_le":
        return ["len_le", p]
    if kind == "all":
        return ["all", pred_spec(p)]
    if kind == "distinct":
        return ["distinct", p]
    return ["sorted", p[0], bool(p[1])]


# --------------------------------------------------------------------------- A1 fixed DSL (prover implementation)
class A1Op:
    role = "A1"
    slots = ()

    def __init__(self, spec, fn, family):
        self.spec, self.fn, self.family = spec, fn, family

    def __call__(self, xs):
        if not isinstance(xs, list):
            raise TypeError("list op on non-list")
        return self.fn(xs)

    def name(self):
        return K.key(self.spec)


def _nums(xs):
    if not all(_num(v) for v in xs):
        raise TypeError("numeric op on non-numbers")
    return xs


def _prefix(xs):
    out, acc = [], 0
    for x in _nums(xs):
        acc += x
        out.append(acc)
    return out


def _runmax(xs):
    out = []
    for x in _nums(xs):
        out.append(x if not out else max(out[-1], x))
    return out


def _diff(xs):
    _nums(xs)
    return [b - a for a, b in zip(xs, xs[1:])]


def _rot(k):
    def f(xs):
        if not xs:
            return []
        j = k % len(xs)
        return xs[j:] + xs[:j]
    return f


def _run_heads(xs):
    out = []
    for x in xs:
        if not out or vkey(out[-1]) != vkey(x):
            out.append(x)
    return out


def _group_count(path):
    def f(xs):
        order, cnt = [], {}
        for x in xs:
            k = vkey(get(x, path))
            if k not in cnt:
                order.append(k)
                cnt[k] = 0
            cnt[k] += 1
        return [cnt[k] for k in order]
    return f


def _repeat(n, f):
    def g(xs):
        for _ in range(n):
            xs = f(xs)
            if not isinstance(xs, list):
                raise TypeError("repeat body left the list type")
        return xs
    return g


def a1_ops(inputs):
    items = [it for x in inputs if isinstance(x, list) for it in x]
    paths = sorted({p for it in items if isinstance(it, dict) for p in it})
    num_paths = [p for p in paths if all(isinstance(it, dict) and _num(it.get(p)) for it in items)]
    ops = []
    for p in num_paths:
        ops.append(A1Op({"op": "proj", "path": p}, lambda xs, p=p: [get(x, p) for x in xs], "proj"))
        ops.append(A1Op({"op": "group_count", "path": p}, _group_count(p), "group_count"))
    if not paths:
        ops.append(A1Op({"op": "group_count", "path": "."}, _group_count("."), "group_count"))
    for c in (-2, -1, 1, 2, 3):
        ops.append(A1Op({"op": "map_add", "c": c}, lambda xs, c=c: [x + c for x in _nums(xs)], "map_add"))
    for c in (-1, 2, 3):
        ops.append(A1Op({"op": "map_mul", "c": c}, lambda xs, c=c: [x * c for x in _nums(xs)], "map_mul"))
    for c in (2, 3, 5):
        ops.append(A1Op({"op": "map_mod", "c": c}, lambda xs, c=c: [x % c for x in _nums(xs)], "map_mod"))
    ops.append(A1Op({"op": "prefix_sum"}, _prefix, "prefix_sum"))
    ops.append(A1Op({"op": "running_max"}, _runmax, "running_max"))
    ops.append(A1Op({"op": "diff"}, _diff, "diff"))
    ops.append(A1Op({"op": "run_heads"}, _run_heads, "run_heads"))
    for k in (1, 2):
        ops.append(A1Op({"op": "rotate", "k": k}, _rot(k), "rotate"))
    for n in (2, 3):
        ops.append(A1Op({"op": "repeat", "n": n, "body": {"op": "diff"}}, _repeat(n, _diff), "repeat"))
    return ops


def family(fn):
    if isinstance(fn, A1Op):
        return fn.family
    if isinstance(fn, Comp):
        return "comp:" + fn.cond + "/" + fn.transform
    return fn.role


FAMILIES = tuple(["F", "S", "Sort"] + ["comp:" + s[1] + "/" + s[2] for s in all_schemas()] +
                 ["proj", "group_count", "map_add", "map_mul", "map_mod", "prefix_sum", "running_max", "diff",
                  "run_heads", "rotate", "repeat"])


def a0_tools(inputs):
    lib = Library()
    tools = lib.tools(inputs, with_schemas=False)
    for s in all_schemas():
        tools += [Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,))
                  for c in instantiate(s, inputs, present=lib.base_roles)]
    return tools


def a1_tools(inputs):
    return a0_tools(inputs) + [Tool(o.name(), o, o.name(), kind="primitive", parts=("A1",)) for o in a1_ops(inputs)]


# --------------------------------------------------------------------------- task generator (dev / admission_val)
def make_task(rng, w, a1_only):
    """Teacher = chain of 1-2 A1-DSL tools (a1_only: containing at least one A1 op; else A0 tools only)."""
    for _ in range(300):
        xs = [w["sample"](rng) for _ in range(5)]
        a0 = [t.fn for t in a0_tools(xs)]
        a1 = [o for o in a1_ops(xs)]
        if a1_only:
            h = rng.choice(a1)
            chain = (h,) if rng.random() < 0.4 else ((rng.choice(a0), h) if rng.random() < 0.5 else (h, rng.choice(a1)))
            if isinstance(chain[0], A1Op) and chain[0].family not in ("proj", "rotate", "run_heads") and \
                    len(chain) == 2 and not isinstance(chain[1], A1Op):
                continue
        else:
            chain = (rng.choice(a0),) if rng.random() < 0.4 else (rng.choice(a0), rng.choice(a0))
        try:
            ys = [run(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:4]}) < 3 or any(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        return dict(public=tuple(zip(xs[:4], ys[:4])), query=xs[4], answer=ys[4], teacher=chain,
                    family="A1" if a1_only else "A0", teacher_spec=[spec_of(f) for f in chain])
    return None


def stream(split_seed, n=16):
    rng = random.Random(f"w30-stream:{split_seed}")
    out = []
    for j in range(n):
        dom = rng.choice(("ints", "records"))
        w = ints_world(900_000 + split_seed * 50 + j) if dom == "ints" else \
            records_world_f(900_000 + split_seed * 50 + j, REC_FIELDS)
        t = make_task(rng, w, a1_only=(j % 2 == 1))
        if t is not None:
            t["domain"] = dom
            out.append(t)
    return out


# --------------------------------------------------------------------------- prover + evidence
def prove(public, query, tools, kind, m, oracle, rng):
    """Occam-margin certificate over `tools` with up to PROBE_BUDGET rich probes while ambiguous; returns the
    Evidence Object (or None if nothing fits) and the probes used."""
    public = list(public)
    probes = 0
    stats = {}
    while True:
        r = certify_exact(public, query, tools, m)
        if r.status == NONE_FOUND or r.status not in (UNIQUE, AMBIGUOUS):
            return None, probes, public
        if r.status == UNIQUE or probes >= PROBE_BUDGET or oracle is None:
            break
        chains = [tuple(t.fn for t in h[2]) for h in r.hypotheses]
        v = choose_verify(chains, [], [x for x, _ in public] + [query], rng, m)
        if v is None:
            break
        m.charge("oracle_work_units", C_ORACLE)
        probes += 1
        try:
            public.append((v, oracle(v)))
        except Exception:
            break
    h = r.hypotheses[0]
    cand = [spec_of(t.fn) for t in h[2]]
    specs = [spec_of(t.fn) for t in tools]
    idx = {K.key(s): i for i, s in enumerate(specs)}
    lemmas = []
    ys = [y for _, y in public]
    for i, t in enumerate(tools):
        for post in violated(t.fn, public, m):
            ps = post_spec(post)
            j = next((j for j, y in enumerate(ys) if K.violates(ps, y)), None)
            if j is not None:
                lemmas.append({"tool": i, "post": ps, "public_index": j})
    ev = {"version": 1, "public": [[x, y] for x, y in public], "query": query, "claimed_answer": h[1],
          "candidate": cand, "scope": {"kind": kind, "tools": specs, "max_depth": DEPTH}, "lemmas": lemmas,
          "trace": {"prover_status": r.status, "shell_size": r.size, "probes": probes,
                    "lemmas": len(lemmas)}}
    return ev, probes, public


def _flat(chain_tools):
    out = []
    for t in chain_tools:
        if t.kind == "macro" and t.children:
            out += _flat(t.children)
        else:
            out.append(t)
    return out


class WakeSleepPrior:
    """No-pretraining prior over operator families: Dirichlet(1) counts, updated (sleep) only from the families of
    NEXUS's own kernel-certified candidates."""

    def __init__(self, families):
        self.c = Counter({f: 1.0 for f in families})

    def proposal(self, mass=0.8, min_families=4):
        tot = sum(self.c.values())
        keep, acc = [], 0.0
        for f, v in sorted(self.c.items(), key=lambda kv: (-kv[1], kv[0])):
            keep.append(f)
            acc += v / tot
            if acc >= mass and len(keep) >= min_families:
                break
        return set(keep)

    def sleep(self, fams):
        for f in fams:
            self.c[f] += 1.0


def solve_arm(arm, task, prior, seed, label):
    m = meter(10**12)
    rng = random.Random(f"w30:{arm}:{seed}:{label}")
    inputs = [x for x, _ in task["public"]] + [task["query"]]
    tools = a0_tools(inputs) if arm == "A0" else a1_tools(inputs)
    oracle = lambda x, c=task["teacher"]: run(c, x)
    kind = "exhaustive"
    scope_used = "full"
    try:
        if arm == "A1b":
            fams = prior.proposal()
            sub = [t for t in tools if family(t.fn) in fams]
            ev, probes, pub = prove(task["public"], task["query"], sub, "proposal", m, oracle, rng)
            scope_used = "proposal"
            if ev is None:
                ev, probes2, pub = prove(task["public"], task["query"], tools, "exhaustive", m, oracle, rng)
                probes += probes2
                scope_used = "escalated"
        else:
            ev, probes, pub = prove(task["public"], task["query"], tools, kind, m, oracle, rng)
    except WorkExhausted:
        ev, probes = None, 0
    if ev is None:
        verdict = dict(label="ABSTAIN", reason="no_fitting_program", chains_checked=0)
    else:
        verdict = K.check(ev)
    m.charge("kernel_work_units", verdict.get("chains_checked", 0))
    uniq = verdict["label"] in ("exhaustive_UNIQUE", "proposal_relative_UNIQUE")
    truth_ok = uniq and K.key(ev["claimed_answer"]) == K.key(task["answer"])
    if arm == "A1b" and uniq:
        prior.sleep({family(f) for f in _cand_fns(ev, inputs)})
    return dict(arm=arm, label=verdict["label"], k=verdict.get("k"), reason=verdict.get("reason"),
                solved=truth_ok, false_certificate=uniq and not truth_ok, work=m.total, work_by=dict(m.counts),
                probes=probes, scope=scope_used, family=task["family"], domain=task["domain"],
                prover_status=(ev or {}).get("trace", {}).get("prover_status"),
                tools=len(tools))


def _cand_fns(ev, inputs):
    by = {K.key(spec_of(t.fn)): t.fn for t in a1_tools(inputs)}
    return [by[K.key(s)] for s in ev["candidate"] if K.key(s) in by]


def run_split(split_seed, arms=("A0", "A1", "A1b")):
    st = stream(split_seed)
    out = {}
    for arm in arms:
        prior = WakeSleepPrior(FAMILIES)
        out[arm] = [solve_arm(arm, t, prior, split_seed, f"{arm}:{i}") for i, t in enumerate(st)]
    return dict(seed=split_seed, tasks=len(st), arms=out)


def summarise(outs):
    rep = {}
    for arm in ("A0", "A1", "A1b"):
        rows = [r for o in outs for r in o["arms"].get(arm, [])]
        if not rows:
            continue
        by = {}
        for fam in ("A0", "A1"):
            rs = [r for r in rows if r["family"] == fam]
            by[fam] = dict(n=len(rs), solved=sum(r["solved"] for r in rs), false=sum(r["false_certificate"] for r in rs),
                           work=sum(r["work"] for r in rs))
        rep[arm] = dict(n=len(rows), solved=sum(r["solved"] for r in rows),
                        false_certificates=sum(r["false_certificate"] for r in rows),
                        labels=dict(Counter(r["label"] for r in rows)), work=sum(r["work"] for r in rows),
                        work_per_solved=(sum(r["work"] for r in rows) / max(1, sum(r["solved"] for r in rows))),
                        abstain_reasons=dict(Counter(r["reason"] for r in rows if r["label"] == "ABSTAIN")),
                        scope=dict(Counter(r["scope"] for r in rows)), by_family=by,
                        prover_kernel_disagree=sum(r["prover_status"] == UNIQUE and r["label"] not in
                                                   ("exhaustive_UNIQUE", "proposal_relative_UNIQUE") for r in rows))
    return rep
