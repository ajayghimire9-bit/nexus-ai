"""Wave 26 Phase 5: long-term memory across a drifting continual stream of worlds.

Reuses the Phase 4 router + synthesizer + slot-level schema library unchanged. A stream is a sequence of
world VISITS. Each base world = (domain ints | records, field-name seed, hidden schema needed by its
tasks or none, distractor-correlation sign, whether its opaque stdlib tool drifts). Drift along the stream:
field schemas/names permute (fresh field-name seeds), the active hidden-mechanism subset swaps, distractor
correlations flip sign, and from mid-stream some worlds' opaque tool changes behaviour (it starts emitting
items not present in its input), which breaks that tool's empirical sub-multiset contract.

Each base world is revisited once after a lag k in {5, 10, 20} visits. Metrics:
  * revisit cost ratio = cost(visit 2) / cost(visit 1) per world (memory helps if < 1);
  * backward interference = (cost of visit 2 with the full current library - cost of the same visit-2 tasks
    with a SNAPSHOT of the library taken right after visit 1) / snapshot cost - interference from everything
    learned in between (the snapshot run is a counterfactual, reported only, not in the stream's totals);
  * stale-contract retirement: every opaque tool carries an EMPIRICAL sub-multiset contract (observed on every
    application; never used to prune - vault firewall); a violation retires it (RETIRED_BY_DRIFT). Rate =
    retired / drift-broken. Because empirical contracts never prune, a stale one cannot cause a false
    certificate; the gate still requires 0 false certificates.
"""
from __future__ import annotations

import copy
import heapq
import operator
import random
from collections import Counter

from nexus.wave24_domains import Tool, vkey
from nexus.wave25_contracts import _class_holds
from nexus.wave25_factored import ints_world, run
from nexus.wave26_phase1 import records_world_f
from nexus.wave26_phase4 import HIDDEN, Library, make_fault_task, solve

LAGS = (5, 10, 20)
N_BASE = 18          # 36 visits per stream (budget-driven; protocol discloses the deviation from 50-100)
TASKS_PER_VISIT = 2


class DriftingOpaque:
    """Opaque stdlib top-k tool shared across worlds; after drift it appends a synthetic record (breaking the
    sub-multiset contract). NEXUS sees only a callable and observes its contract empirically."""

    role = "Opaque"
    slots = ()

    def __init__(self, path, k, drifted, store):
        self.path, self.k, self.drifted, self.store = path, k, drifted, store

    def __call__(self, xs):
        if not isinstance(xs, list) or not xs:
            raise TypeError("opaque tool needs a non-empty list")
        try:
            out = heapq.nlargest(self.k, xs, key=operator.itemgetter(self.path) if self.path != "." else None)
        except Exception as exc:
            raise TypeError("opaque failure") from exc
        if self.drifted:
            out = out + [out[0]] if not isinstance(out[0], dict) else out + [dict(out[0], _drift=1)]
        self.store.observe(self.name(), xs, out, drifted=self.drifted)
        return out

    def name(self):
        return f"opaque_top{self.k}_{self.path}"


class EmpiricalContractStore:
    """EMPIRICAL sub-multiset contracts of opaque tools; a counterexample retires the contract at once."""

    def __init__(self):
        self.status = {}             # tool name -> ACTIVE | RETIRED_BY_DRIFT
        self.checks = Counter()
        self.retired_at = {}
        self.visit = None
        self.drift_used = set()

    def observe(self, name, xs, out, drifted=False):
        self.status.setdefault(name, "ACTIVE")
        if drifted:
            self.drift_used.add(name)        # ground truth for scoring only (the tool is drift-broken)
        self.checks[name] += 1
        if self.status[name] == "ACTIVE" and not _class_holds("submultiset", xs, out, None):
            self.status[name] = "RETIRED_BY_DRIFT"
            self.retired_at[name] = self.visit


def make_stream(seed):
    """N_BASE base worlds; each revisited once at lag LAGS[i % 3] (positions resolved greedily)."""
    rng = random.Random(f"w26-p5-stream:{seed}")
    bases = []
    for i in range(N_BASE):
        bases.append(dict(wid=i, domain=rng.choice(("ints", "records")), fseed=seed * 1000 + i,
                          hidden=rng.choice(HIDDEN + (None,)), corr=rng.choice((1, -1)),
                          drift=i >= N_BASE // 2 and rng.random() < 0.5, lag=LAGS[i % 3]))
    order, pending = [], []
    for b in bases:
        order.append((b["wid"], 1))
        pending.append([len(order) - 1 + b["lag"], b["wid"]])
        due = sorted([p for p in pending if p[0] <= len(order)], key=lambda p: p[0])
        for p in due:
            order.append((p[1], 2))
            pending.remove(p)
    for p in sorted(pending, key=lambda p: p[0]):
        order.append((p[1], 2))
    return bases, order


def world_of(b):
    if b["domain"] == "ints":
        w = ints_world(b["fseed"])
    else:
        w = records_world_f(b["fseed"], 5)
        if b["corr"] < 0:
            base = w["sample"]
            fs, dist = w["fields"][1], w["fields"][3:]

            def flipped(r, n=None, base=base):
                xs = base(r, n)
                for rec in xs:
                    for d in dist:
                        rec[d] = 9 - rec[d]          # distractor correlation flips sign
                return xs
            w = dict(w, sample=flipped)
    return w


def tasks_for(b, visit, seed):
    w = world_of(b)
    rng = random.Random(f"w26-p5-tasks:{seed}:{b['wid']}:{visit}")
    out = []
    for _ in range(TASKS_PER_VISIT * 3):
        if len(out) == TASKS_PER_VISIT:
            break
        if b["hidden"] is None:
            t = make_fault_task(w, rng, rng.choice(("dB", "dC")))
        else:
            t = make_fault_task(w, rng, "dM", hidden_choice=b["hidden"])
        if t is not None:
            out.append(t)
    return w, out


def visit_cost(b, w, tasks, lib, store, seed, label):
    rows = []
    path = w["fields"][1] if b["domain"] == "records" else "."
    for i, t in enumerate(tasks):
        op = DriftingOpaque(path, 2, b["drift"], store)
        extra = [Tool(op.name(), op, op.name(), kind="primitive", parts=("Opaque",))]
        r = solve(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib, world_like=w,
                  seed=seed, label=f"{label}:{i}", extra_tools=extra)
        a = r["answers"][0]
        rows.append(dict(route=r["route"], solved=a is not None and vkey(a) == vkey(t["answer"]),
                         false_certificate=a is not None and vkey(a) != vkey(t["answer"]), work=r["work"],
                         work_by=r["work_by"]))
    return rows


def run_stream(seed):
    bases, order = make_stream(seed)
    lib, store = Library(), EmpiricalContractStore()
    snapshots, first, rows, first_pos = {}, {}, [], {}
    for pos, (wid, visit) in enumerate(order):
        b = bases[wid]
        store.visit = pos
        w, tasks = tasks_for(b, visit, seed)
        vr = visit_cost(b, w, tasks, lib, store, seed, f"{seed}:{wid}:{visit}")
        cost = sum(r["work"] for r in vr)
        actual = pos - first_pos[wid] if visit == 2 else 0
        bucket = 5 if actual <= 7 else 10 if actual <= 14 else 20
        row = dict(seed=seed, pos=pos, wid=wid, visit=visit, lag=bucket if visit == 2 else b["lag"],
                   scheduled_lag=b["lag"], actual_lag=actual, domain=b["domain"],
                   hidden="/".join(b["hidden"]) if b["hidden"] else None, drift=b["drift"], tasks=len(tasks),
                   solved=sum(r["solved"] for r in vr), false_certificates=sum(r["false_certificate"] for r in vr),
                   work=cost, routes=dict(Counter(r["route"] for r in vr)), library_size=len(lib.schemas))
        if visit == 1:
            first_pos[wid] = pos
            snapshots[wid] = copy.deepcopy(lib)
            first[wid] = cost
        else:
            # counterfactual (reported only): the same visit-2 tasks with the library snapshot after visit 1
            snap = copy.deepcopy(snapshots[wid])
            sr = visit_cost(b, w, tasks, snap, EmpiricalContractStore(), seed, f"{seed}:{wid}:snap")
            row.update(snapshot_work=sum(r["work"] for r in sr), first_visit_work=first[wid])
        rows.append(row)
    return dict(seed=seed, rows=rows, contracts=dict(store.status), retired_at=store.retired_at,
                drift_tool_names=sorted(store.drift_used),
                checks=dict(store.checks), library=sorted("/".join(s) for s in lib.schemas),
                drift_worlds=[b["wid"] for b in bases if b["drift"]])
