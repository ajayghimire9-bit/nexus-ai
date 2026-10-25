"""Wave 26 Phase 4 driver.

  --dev            synthetic router + deletion streams on dev seeds 721-725
  --confirm        the same on the one-use confirmation seeds 4001-4005 (checkpointed)
  --sealed         Sealed Vault Group A (seeds 3001-3010) through the token-gated loader; prints aggregates only
  --replay-of A    fresh-process replay of a saved confirmation (or sealed) artifact
Phase 4 PASS (declared in docs/NEXUS_WAVE26_PHASE4.md before confirmation): router accuracy >= 0.8 per class
(dB, dC, dM) on the mixed stream; for every deleted primitive, >= 80% of deletion tasks routed dM and solved and
later encounters cheaper than the first on >= 4 of 5 seeds; on Group A >= 50% of base-tier failures repaired
and second encounters of a mechanism group cheaper than first encounters (pooled); >= 1 admitted invented schema
with positive net benefit on later Group A tasks; 0 false certificates; G_tycho; identical replay digests.
"""
import argparse, json, os, sys, time, traceback
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def ledger(run, wall, status, **kw):
    with LEDGER.open("a") as f:
        f.write(json.dumps(dict(run=run, wall_s=wall, status=status, **kw)) + "\n")


def digest_synth(outs):
    from nexus.standing_gates import json_digest
    return json_digest([(o["seed"], r.get("kind"), r.get("world"), r.get("task", r.get("encounter")), r.get("route"),
                         r.get("status"), r.get("work")) for o in outs for r in o["mixed"] + o["deletion"]])


def run_synth(seeds, checkpoint=None):
    from nexus.wave26_phase4 import run_dev_or_confirm
    outs, done = [], set()
    ck = Path(checkpoint) if checkpoint else None
    if ck and ck.exists():
        for l in ck.read_text().splitlines():
            o = json.loads(l); outs.append(o); done.add(o["seed"])
    for s in seeds:
        if s in done:
            continue
        o = run_dev_or_confirm(s)
        outs.append(o)
        if ck:
            with ck.open("a") as f:
                f.write(json.dumps(o, default=repr) + "\n")
        print(f"seed {s} done", flush=True)
    return sorted(outs, key=lambda o: o["seed"])


def score_synth(outs):
    mixed = [r for o in outs for r in o["mixed"] if r.get("generated")]
    acc = {}
    for k in ("dB", "dC", "dM"):
        rs = [r for r in mixed if r["kind"] == k]
        acc[k] = dict(n=len(rs), routed=sum(r["route"] == r["expected"] for r in rs),
                      solved=sum(r["solved"] for r in rs),
                      confusion={x: sum(r["route"] == x for r in rs) for x in ("dB", "dC", "dM", "base", "library")})
    prim = {}
    for p in ("Sort", "F", "S"):
        rs = [r for o in outs for r in o["deletion"] if r["kind"] == f"del:{p}" and r.get("generated")]
        seeds_cheaper = 0
        for o in outs:
            for w in ("ints", "records"):
                st = sorted([r for r in o["deletion"] if r["kind"] == f"del:{p}" and r["world"] == w and r.get("generated")],
                            key=lambda r: r["encounter"])
                if len(st) >= 2 and sum(r["work"] for r in st[1:]) / len(st[1:]) < st[0]["work"]:
                    seeds_cheaper += 1
        prim[p] = dict(n=len(rs), routed_dM=sum(r["route"] == "dM" for r in rs if r["encounter"] == 0),
                       first_encounters=sum(r["encounter"] == 0 for r in rs),
                       solved=sum(r["solved"] for r in rs), library_reuse=sum(r["route"] == "library" for r in rs),
                       streams_later_cheaper=seeds_cheaper, streams=2 * len(outs),
                       first_mean_work=_mean([r["work"] for r in rs if r["encounter"] == 0]),
                       later_mean_work=_mean([r["work"] for r in rs if r["encounter"] > 0]))
    false = sum(r.get("false_certificate", False) for o in outs for r in o["mixed"] + o["deletion"])
    g_router = all(v["n"] > 0 and v["routed"] / v["n"] >= 0.8 for v in acc.values())
    g_prim = all(v["first_encounters"] > 0 and v["routed_dM"] / v["first_encounters"] >= 0.8 and
                 v["solved"] / max(1, v["n"]) >= 0.8 and v["streams_later_cheaper"] >= 0.8 * v["streams"]
                 for v in prim.values())
    return dict(router=acc, primitives=prim, false_certificates=false, gate_router=g_router, gate_primitives=g_prim)


def _mean(v):
    return sum(v) / len(v) if v else None


def run_sealed(checkpoint=None, deadline=None):
    """Group A through the harness. NEXUS gets train_examples, query_inputs and charged oracle_fn calls only;
    grading calls oracle_fn(query) (uncharged, never shown to NEXUS); metadata is used only as a group key."""
    from nexus.sealed_vault_loader import load_split
    from nexus.wave24_domains import vkey
    from nexus.wave26_phase4 import Library, solve
    lib = Library()
    rows, done = [], set()
    ck = Path(checkpoint) if checkpoint else None
    if ck and ck.exists():
        for l in ck.read_text().splitlines():
            u = json.loads(l)
            if u.get("lib_state"):
                continue
            rows.append(u); done.add((u["seed"], u["idx"]))
    group_seen = defaultdict(int)
    for r in rows:
        group_seen[r["group"]] += 1
    for seed in range(3001, 3011):
        if deadline and time.perf_counter() > deadline:
            break
        try:
            tasks = load_split("group_a", seed)
        except Exception as exc:
            rows.append(dict(seed=seed, idx=-1, error=type(exc).__name__, group="load", encounter=0, solved=False,
                             false_certificate=False, work=0, route="error"))
            continue
        for idx, t in enumerate(tasks):
            if (seed, idx) in done:
                continue
            meta = t.hidden_ground_truth_metadata if isinstance(t.hidden_ground_truth_metadata, dict) else {}
            gkey = str(meta.get("mechanism_id", meta.get("mechanism", meta.get("name", idx))))
            group = "g%08x" % (hash(("w26", gkey)) & 0xFFFFFFFF) if False else _gid(gkey)
            enc = group_seen[group]
            row = dict(seed=seed, idx=idx, group=group, encounter=enc)
            try:
                public = [tuple(p) if not isinstance(p, dict) else (p.get("input"), p.get("output"))
                          for p in t.train_examples]
                queries = list(t.query_inputs)
                world_like = dict(name="sealed", fields=(), sample=lambda r, n=None: None)
                r = solve(public, queries, t.oracle_fn, lib, world_like=world_like, seed=seed, label=f"A{seed}:{idx}")
                truths = [t.oracle_fn(q) for q in queries]          # grading only
                sol = [a is not None and vkey(a) == vkey(y) for a, y in zip(r["answers"], truths)]
                fc = [a is not None and vkey(a) != vkey(y) for a, y in zip(r["answers"], truths)]
                row.update(route=r["route"], solved=all(sol), solved_queries=sum(sol), queries=len(queries),
                           false_certificate=any(fc), false_certificates=sum(fc), work=r["work"], work_by=r["work_by"],
                           admitted=r["admitted"], used_library=r["used_library"], invented=len(r["invented"]))
            except Exception as exc:                                 # type only: never a traceback (RULE 1)
                row.update(route="error", error=type(exc).__name__, solved=False, false_certificate=False, work=0)
            group_seen[group] += 1
            rows.append(row)
            if ck:
                with ck.open("a") as f:
                    f.write(json.dumps(row, default=repr) + "\n")
        print(f"sealed seed {seed} done ({len([r for r in rows if r['seed'] == seed])} tasks)", flush=True)
    lib_summary = {f"inv{i}": dict(cls=v["cls"], uses=v["uses"], reuse_tasks=v["reuse_tasks"],
                                    discovery_cost=v["discovery_cost"], class_check=v["class_check"])
                   for i, (k, v) in enumerate(sorted(lib.schemas.items()))}
    return rows, lib_summary


_GIDS = {}


def _gid(key):
    if key not in _GIDS:
        _GIDS[key] = f"group{len(_GIDS):02d}"
    return _GIDS[key]


def score_sealed(rows, lib_summary):
    ok = [r for r in rows if r.get("route") not in ("error",)]
    failures = [r for r in ok if r["route"] != "base"]
    repaired = [r for r in failures if r["solved"]]
    first = [r["work"] for r in ok if r["encounter"] == 0]
    second = [r["work"] for r in ok if r["encounter"] == 1]
    dm = [r for r in ok if r["route"] == "dM"]
    mean_syn = _mean([r["work"] for r in dm]) or 0
    benefit = {k: v["reuse_tasks"] * mean_syn - v["discovery_cost"] - v["class_check"] for k, v in lib_summary.items()}
    return dict(tasks=len(rows), errors=sum(r.get("route") == "error" for r in rows),
                error_types=dict(__import__("collections").Counter(r.get("error") for r in rows if r.get("error"))),
                solved=sum(r["solved"] for r in ok), base_failures=len(failures), repaired=len(repaired),
                repair_rate=len(repaired) / len(failures) if failures else None,
                routes=dict(__import__("collections").Counter(r["route"] for r in rows)),
                first_mean_work=_mean(first), second_mean_work=_mean(second),
                false_certificates=sum(r.get("false_certificates", 0) for r in ok),
                admitted=len(lib_summary), positive_net_schemas=sum(b > 0 for b in benefit.values()),
                net_benefit=benefit, groups=len({r["group"] for r in ok}))


def main():
    ap = argparse.ArgumentParser()
    for f in ("--dev", "--confirm", "--sealed", "--digest-only"):
        ap.add_argument(f, action="store_true")
    ap.add_argument("--replay-of")
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    ap.add_argument("--wall-cap", type=float, default=840.0)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.standing_gates import g_tycho, json_digest
    if a.digest_only:
        if a.sealed:
            rows, lib = run_sealed()
            print(json_digest([(r["seed"], r["idx"], r.get("route"), r.get("solved"), r.get("work")) for r in rows]))
        else:
            print(digest_synth(run_synth(list(range(4001, 4006)))))
        return
    if a.replay_of:
        from nexus.standing_gates import g_replay
        art = json.loads(Path(a.replay_of).read_text())
        t0 = time.perf_counter()
        try:
            art["report"]["G_replay"] = g_replay(__file__, ["--sealed"] if art.get("sealed") else ["--confirm"],
                                                 art["report"]["digest"])
        finally:
            ledger("wave26-phase4-replay" + ("-sealed" if art.get("sealed") else ""), time.perf_counter() - t0, "COMPLETE")
        Path(a.replay_of).write_text(json.dumps(art, default=repr, sort_keys=True))
        print(json.dumps(art["report"]["G_replay"]))
        return
    t0 = time.perf_counter()
    if a.sealed:
        if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN") or not a.checkpoint:
            raise SystemExit("sealed run requires the harness token and --checkpoint")
        R.claim("phase3", "vault_group_a", range(3001, 3011), run_id="phase4-sealed-group-a")
        status = "FAILED"
        try:
            rows, lib = run_sealed(a.checkpoint, deadline=t0 + a.wall_cap - 60)
            status = "COMPLETE" if len({r["seed"] for r in rows}) == 10 else "PARTIAL_WALL_CAP"
        finally:
            ledger("wave26-phase4-sealed-group-a", time.perf_counter() - t0, status)
        rep = score_sealed(rows, lib)
        rep["digest"] = json_digest([(r["seed"], r["idx"], r.get("route"), r.get("solved"), r.get("work")) for r in rows])
        rep["G_tycho"] = g_tycho([r for r in rows if "work_by" in r])
        rep["status"] = status
        Path(a.out).write_text(json.dumps(dict(schema="wave26_phase4_sealed", sealed=True, report=rep, rows=rows),
                                          default=repr, sort_keys=True))
        print(json.dumps({k: v for k, v in rep.items() if k != "net_benefit"}, default=repr))
        return
    seeds = list(range(721, 726)) if a.dev else list(range(4001, 4006))
    if a.dev:
        R.claim("phase4", "dev", seeds, run_id="phase4-dev", record=False)
    else:
        if not a.checkpoint:
            raise SystemExit("confirmation requires --checkpoint")
        R.claim("phase4", "confirm", seeds, run_id="phase4-confirm")
    status = "FAILED"
    try:
        outs = run_synth(seeds, a.checkpoint)
        status = "COMPLETE"
    finally:
        ledger("wave26-phase4-" + ("dev" if a.dev else "confirm"), time.perf_counter() - t0, status, seeds=seeds)
    rep = score_synth(outs)
    rep["digest"] = digest_synth(outs)
    rep["G_tycho"] = g_tycho([r for o in outs for r in o["mixed"] + o["deletion"] if "work_by" in r])
    Path(a.out).write_text(json.dumps(dict(schema="wave26_phase4", report=rep, seeds_raw=outs), default=repr, sort_keys=True))
    print(json.dumps(rep, default=repr, indent=1))


if __name__ == "__main__":
    main()
