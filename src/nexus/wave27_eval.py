"""Wave 27 evaluation loops: the Wave 26 Phase 4 / 5 / 6 task generators and scoring, unchanged, driven by the
Wave 27 solver (`solve27`) and `EpistemicLibrary`. Only the solver and the library class differ from Wave 26."""
from __future__ import annotations

import copy
import random
from collections import Counter

from nexus.wave24_domains import Tool, vkey
from nexus.wave25_factored import run
from nexus.wave26_phase4 import PRIMITIVES, _row, long_world, make_fault_task, worlds
from nexus.wave26_phase5 import DriftingOpaque, EmpiricalContractStore, make_stream, tasks_for
from nexus.wave26_phase6 import HIDDEN, noise, ordering, slope, source_tasks
from nexus.wave26_phase5 import world_of
from nexus.wave27_core import EpistemicLibrary, solve27


# --------------------------------------------------------------------------- Phase 4 (router + deletion streams)
def _row27(t, r, wname, kind, i):
    row = _row(t, r, wname, kind, i)
    row.update(audit=r.get("audit"), index=r.get("index"))
    return row


def run_phase4(seed, *, n_per_kind=3, n_del=4):
    out = dict(seed=seed, mixed=[], deletion=[])
    for wname, w in worlds(seed):
        rng = random.Random(f"w26-p4-mixed:{seed}:{wname}")
        for kind in ("dB", "dC", "dM"):
            for i in range(n_per_kind):
                t = make_fault_task(w, rng, kind)
                if t is None:
                    out["mixed"].append(dict(world=wname, kind=kind, generated=False))
                    continue
                r = solve27(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), EpistemicLibrary(),
                            world_like=w, seed=seed, label=f"{wname}:{kind}:{i}")
                out["mixed"].append(_row27(t, r, wname, kind, i))
    for prim in PRIMITIVES:
        for wname, w in worlds(seed):
            lw = long_world(w)
            rng = random.Random(f"w26-p4-del:{seed}:{prim}:{wname}")
            lib = EpistemicLibrary(deleted=[prim])
            for i in range(n_del):
                t = make_fault_task(lw, rng, f"del:{prim}", deleted=[prim])
                if t is None:
                    out["deletion"].append(dict(world=wname, kind=f"del:{prim}", generated=False, encounter=i))
                    continue
                r = solve27(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib,
                            world_like=lw, seed=seed, label=f"{wname}:{prim}:{i}")
                row = _row27(t, r, wname, f"del:{prim}", i)
                row["encounter"] = i
                out["deletion"].append(row)
            out.setdefault("libraries", {})[f"{prim}/{wname}"] = lib.summary()
            out.setdefault("events", {})[f"{prim}/{wname}"] = lib.events
    return out


# --------------------------------------------------------------------------- Phase 5 (drifting continual stream)
class EpistemicStore(EmpiricalContractStore):
    """Phase 5 drift detector; schema demotions are read from the library's event log."""


def visit_cost27(b, w, tasks, lib, store, seed, label):
    rows = []
    path = w["fields"][1] if b["domain"] == "records" else "."
    for i, t in enumerate(tasks):
        op = DriftingOpaque(path, 2, b["drift"], store)
        extra = [Tool(op.name(), op, op.name(), kind="primitive", parts=("Opaque",))]
        r = solve27(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib, world_like=w,
                    seed=seed, label=f"{label}:{i}", extra_tools=extra)
        a = r["answers"][0]
        rows.append(dict(route=r["route"], solved=a is not None and vkey(a) == vkey(t["answer"]),
                         false_certificate=a is not None and vkey(a) != vkey(t["answer"]), work=r["work"],
                         work_by=r["work_by"], audit=r["audit"]))
    return rows


def run_phase5(seed):
    bases, order = make_stream(seed)
    lib, store = EpistemicLibrary(), EpistemicStore()
    snapshots, first, rows, first_pos = {}, {}, [], {}
    for pos, (wid, visit) in enumerate(order):
        b = bases[wid]
        store.visit = pos
        w, tasks = tasks_for(b, visit, seed)
        vr = visit_cost27(b, w, tasks, lib, store, seed, f"{seed}:{wid}:{visit}")
        cost = sum(r["work"] for r in vr)
        actual = pos - first_pos[wid] if visit == 2 else 0
        bucket = 5 if actual <= 7 else 10 if actual <= 14 else 20
        row = dict(seed=seed, pos=pos, wid=wid, visit=visit, lag=bucket if visit == 2 else b["lag"],
                   scheduled_lag=b["lag"], actual_lag=actual, domain=b["domain"],
                   hidden="/".join(b["hidden"]) if b["hidden"] else None, drift=b["drift"], tasks=len(tasks),
                   solved=sum(r["solved"] for r in vr), false_certificates=sum(r["false_certificate"] for r in vr),
                   work=cost, routes=dict(Counter(r["route"] for r in vr)), library_size=len(lib.schemas),
                   core_size=len(lib.core()), audits=dict(Counter(r["audit"] for r in vr if r["audit"])))
        if visit == 1:
            first_pos[wid] = pos
            snapshots[wid] = copy.deepcopy(lib)
            first[wid] = cost
        else:
            snap = copy.deepcopy(snapshots[wid])
            sr = visit_cost27(b, w, tasks, snap, EpistemicStore(), seed, f"{seed}:{wid}:snap")
            row.update(snapshot_work=sum(r["work"] for r in sr), first_visit_work=first[wid])
        rows.append(row)
    return dict(seed=seed, rows=rows, contracts=dict(store.status), retired_at=store.retired_at,
                drift_tool_names=sorted(store.drift_used), checks=dict(store.checks),
                library=sorted("/".join(s) for s in lib.schemas), library_state=lib.summary(), events=lib.events,
                drift_worlds=[b["wid"] for b in bases if b["drift"]])


# --------------------------------------------------------------------------- Phase 6 (learning to learn)
def train27(arm, seed, *, work_target=None):
    lib, work, calls = EpistemicLibrary(), 0, 0
    if arm == "fresh":
        return lib, dict(work=0, calls=0, library={})
    rng = random.Random(f"w26-p6-placebo:{seed}")
    passes = 0
    while True:
        for b in ordering(seed):
            w, tasks = source_tasks(b, seed)
            for i, t in enumerate(tasks):
                if arm == "placebo":
                    t = noise(t, rng)
                r = solve27(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib, world_like=w,
                            seed=seed, label=f"src:{arm}:{passes}:{b['wid']}:{i}")
                work += r["work"]
                calls += 1
                if arm == "placebo" and work_target is not None and work >= work_target:
                    return lib, dict(work=work, calls=calls, passes=passes + 1, library=lib.summary())
        passes += 1
        if arm == "experienced" or work_target is None or passes >= 4:
            return lib, dict(work=work, calls=calls, passes=passes, library=lib.summary())


def eval_stream(seed, n_worlds=16):
    """Held-out synthetic target worlds (fresh field-name seeds, disjoint from the source worlds 900000+)."""
    rng = random.Random(f"w27-p6-target:{seed}")
    stream = []
    for j in range(n_worlds):
        b = dict(wid=100 + j, domain=rng.choice(("ints", "records")), fseed=700_000 + seed * 100 + j,
                 hidden=rng.choice(HIDDEN), corr=1, drift=False, lag=5)
        w = world_of(b)
        for _ in range(4):
            t = make_fault_task(w, rng, "dM", hidden_choice=b["hidden"])
            if t is not None:
                stream.append(dict(public=t["public"], queries=[t["query"]],
                                   oracle=lambda x, c=t["teacher"]: run(c, x),
                                   truths=lambda t=t: [t["answer"]], world_like=w, group=f"w{j}"))
                break
    return stream


def evaluate27(lib, stream, seed, arm):
    rows = []
    for i, t in enumerate(stream):
        try:
            r = solve27(list(t["public"]), list(t["queries"]), t["oracle"], lib, world_like=t["world_like"],
                        seed=seed, label=f"eval:{arm}:{i}")
            truths = t["truths"]()
            sol = [a is not None and vkey(a) == vkey(y) for a, y in zip(r["answers"], truths)]
            fc = [a is not None and vkey(a) != vkey(y) for a, y in zip(r["answers"], truths)]
            rows.append(dict(i=i, group=t["group"], route=r["route"], solved=all(sol), false_certificates=sum(fc),
                             work=r["work"], work_by=r["work_by"], audit=r["audit"]))
        except Exception as exc:                       # type only (RULE 1 for sealed tasks)
            rows.append(dict(i=i, group=t["group"], route="error", error=type(exc).__name__, solved=False,
                             false_certificates=0, work=0))
    return rows


def run_phase6(seed, stream_factory=None, *, fresh_cache=None):
    """fresh_cache: only for a stream shared by every ordering (the sealed paired ablation, as in Wave 26): Fresh is
    then evaluated once with seed 0 and reused. Primary synthetic confirmation: per-ordering target worlds."""
    stream_factory = stream_factory or (lambda: eval_stream(seed))
    out = dict(seed=seed, arms={})
    target = None
    for arm in ("experienced", "fresh", "placebo"):
        if arm == "fresh" and fresh_cache is not None and "fresh" in fresh_cache:
            out["arms"]["fresh"] = fresh_cache["fresh"]
            continue
        lib, src = train27(arm, seed, work_target=target)
        if arm == "experienced":
            target = src["work"]
        eseed = 0 if (arm == "fresh" and fresh_cache is not None) else seed
        rows = evaluate27(lib, stream_factory(), eseed, arm)
        costs = [r["work"] for r in rows]
        out["arms"][arm] = dict(source=src, rows=rows, eval_cost=sum(costs), slope=slope(costs),
                                solved=sum(r["solved"] for r in rows),
                                false_certificates=sum(r["false_certificates"] for r in rows),
                                errors=sum(r["route"] == "error" for r in rows), library_end=lib.summary())
        if arm == "fresh" and fresh_cache is not None:
            fresh_cache["fresh"] = out["arms"]["fresh"]
    return out


def run_sealed_a(lib, seed, gid):
    """Sealed Group A, one seed, through the token-gated loader (harness only); shared library across seeds.
    Mirrors the Wave 26 Phase 4 sealed runner: public pairs, queries and charged oracle calls reach NEXUS; grading
    calls oracle_fn(query) uncharged; metadata only as an anonymised group key; errors by type only."""
    from nexus.sealed_vault_loader import load_split
    rows = []
    try:
        tasks = load_split("group_a", seed)
    except Exception as exc:
        return [dict(seed=seed, idx=-1, error=type(exc).__name__, group="load", encounter=0, solved=False,
                     false_certificates=0, work=0, route="error")]
    for idx, t in enumerate(tasks):
        meta = t.hidden_ground_truth_metadata if isinstance(t.hidden_ground_truth_metadata, dict) else {}
        group = gid(str(meta.get("mechanism_id", meta.get("mechanism", meta.get("name", idx)))))
        row = dict(seed=seed, idx=idx, group=group)
        try:
            public = [tuple(p) if not isinstance(p, dict) else (p.get("input"), p.get("output"))
                      for p in t.train_examples]
            queries = list(t.query_inputs)
            wl = dict(name="sealed", fields=(), sample=lambda r, n=None: None)
            r = solve27(public, queries, t.oracle_fn, lib, world_like=wl, seed=seed, label=f"A{seed}:{idx}")
            truths = [t.oracle_fn(q) for q in queries]
            sol = [a is not None and vkey(a) == vkey(y) for a, y in zip(r["answers"], truths)]
            fc = [a is not None and vkey(a) != vkey(y) for a, y in zip(r["answers"], truths)]
            row.update(route=r["route"], solved=all(sol), solved_queries=sum(sol), queries=len(queries),
                       false_certificates=sum(fc), work=r["work"], work_by=r["work_by"], audit=r["audit"],
                       admitted=len(r["admitted"]), invented=len(r["invented"]))
        except Exception as exc:                                 # type only: never a traceback (RULE 1)
            row.update(route="error", error=type(exc).__name__, solved=False, false_certificates=0, work=0)
        rows.append(row)
    return rows


def score_phase6(outs):
    per = []
    for o in outs:
        a = o["arms"]
        per.append(dict(seed=o["seed"], cost={k: v["eval_cost"] for k, v in a.items()},
                        slope={k: v["slope"] for k, v in a.items()}, solved={k: v["solved"] for k, v in a.items()},
                        false={k: v["false_certificates"] for k, v in a.items()},
                        errors={k: v["errors"] for k, v in a.items()},
                        source_work={k: v["source"]["work"] for k, v in a.items()},
                        library={k: v["source"]["library"] for k, v in a.items()}))
    cw = sum(p["cost"]["experienced"] < min(p["cost"]["fresh"], p["cost"]["placebo"]) for p in per)
    sw = sum(p["slope"]["experienced"] < min(p["slope"]["fresh"], p["slope"]["placebo"]) for p in per)
    fc = sum(sum(p["false"].values()) for p in per)
    return dict(orderings=per, cost_wins=cw, slope_wins=sw, n=len(per), false_certificates=fc,
                gate_cost=cw == len(per) == 5, gate_slope=sw == len(per) == 5,
                gate=cw == sw == len(per) == 5 and fc == 0)
