"""Wave 26 Phase 1 driver. --grid: dev seeds 701-705 over every (c_oracle, W) cell. --confirm: the one-use
confirmation seeds 1001-1005 on the single cell named in docs/NEXUS_WAVE26_PHASE1.md (locked first).

Crossover marks per cell: (a) full_nexus_vault or revisable_controller fully loaded < exact_eig_enum;
(b) s2_transferred_rule fully loaded < exact_eig_enum. Selection rule (declared before the grid ran): among
cells where (a) holds for full_nexus_vault, prefer cells where (b) also holds; then the largest relative
margin of full_nexus_vault over exact_eig_enum; ties -> lower c_oracle.
Phase 1 PASS (confirmation): full_nexus_vault fully loaded < exact_eig_enum in the locked cell, 0 false
certificates in every arm, identical fresh-process replay digest.
"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def digest_rows(rows):
    from nexus.standing_gates import json_digest
    return json_digest([(r["seed"], r["cell"], r["arm"], r["c_oracle"], r["episode"], r["work"], r["probes"],
                         [(q["status"], q["solved"]) for q in r["queries"]]) for r in rows])


def run_seeds(seeds, cells, costs, n_eps, *, checkpoint=None, deadline=None):
    """Runs (seed, cell) units in order. With `checkpoint` (jsonl), every finished unit is appended at once and
    finished units are skipped on resume, so a wall-cap stop never loses completed work. `deadline`
    (perf_counter) stops cleanly between units."""
    from nexus.wave26_phase1 import one_time_costs, run_cell
    rows, meta, done = [], {}, set()
    ck = Path(checkpoint) if checkpoint else None
    if ck and ck.exists():
        for line in ck.read_text().splitlines():
            u = json.loads(line)
            done.add((u["seed"], u["cell"]))
            rows += u["rows"]
            meta.setdefault(u["seed"], dict(once=u["once"], rules=u["rules"]))
            meta[u["seed"]].setdefault("episodes", {})[u["cell"]] = u["n"]
    for s in seeds:
        rules = once = None
        for cell in cells:
            key = f"{cell[0]}/F{cell[2]}/{cell[3]}"
            if (s, key) in done:
                continue
            if deadline is not None and time.perf_counter() > deadline:
                return rows, meta, False
            if rules is None:
                rules, once = one_time_costs(s)
            r, n = run_cell(s, cell, n_eps=n_eps if cell[1] == 2 else max(2, n_eps // 2), costs=costs, rules=rules)
            rows += r
            meta.setdefault(s, dict(once=once, rules=sorted(f"{a}>{b}" for a, b in rules)))
            meta[s].setdefault("episodes", {})[key] = n
            if ck:
                with ck.open("a") as f:
                    f.write(json.dumps(dict(seed=s, cell=key, n=n, once=once, rules=meta[s]["rules"], rows=r),
                                       default=repr) + "\n")
            print(f"seed {s} cell {key}: {n} episodes", flush=True)
    return rows, meta, True


def table(rows, meta, cells, costs):
    from nexus.wave26_phase1 import ARMS, price
    out = {}
    for cell in cells:
        key = f"{cell[0]}/F{cell[2]}/{cell[3]}"
        cr = [r for r in rows if r["cell"] == key]
        for c in costs:
            agg = {a: dict(episodes=0, solved=0, probes=0, false=0, work=0.0, amortised=0.0, fully_loaded=0.0) for a in ARMS}
            for s, mt in meta.items():
                p = price([r for r in cr if r["seed"] == s], mt["episodes"][key], mt["once"], c)
                for a in ARMS:
                    for k in agg[a]:
                        agg[a][k] += p[a][k]
            ex = agg["exact_eig_enum"]["fully_loaded"]
            mark_a = min(agg["full_nexus_vault"]["fully_loaded"], agg["revisable_controller"]["fully_loaded"]) < ex
            mark_b = agg["s2_transferred_rule"]["fully_loaded"] < ex
            out[f"{key}|c={c}"] = dict(arms=agg, a=mark_a, b=mark_b,
                                       full_margin=(ex - agg["full_nexus_vault"]["fully_loaded"]) / max(1, ex),
                                       full_beats=agg["full_nexus_vault"]["fully_loaded"] < ex, cell=key, c=c)
    return out


def select(tab):
    cand = [v for v in tab.values() if v["full_beats"]]
    if not cand:
        return None
    cand.sort(key=lambda v: (not v["b"], -v["full_margin"], v["c"]))
    return dict(cell=cand[0]["cell"], c=cand[0]["c"], b=cand[0]["b"], margin=cand[0]["full_margin"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--digest-only", action="store_true")
    ap.add_argument("--cell")
    ap.add_argument("--c", type=int)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out")
    ap.add_argument("--checkpoint", help="append-only jsonl of finished (seed, cell) units; resumes from it")
    ap.add_argument("--wall-cap", type=float, default=840.0, help="stop cleanly between units before this many s")
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave26_phase1 import CELLS, ORACLE_COSTS
    if a.grid:
        seeds = R.claim("phase1", "dev", range(701, 706), run_id="phase1-grid", record=False)
        cells, costs = CELLS, ORACLE_COSTS
    else:
        cells = [c for c in CELLS if f"{c[0]}/F{c[2]}/{c[3]}" == a.cell]
        costs = (a.c,)
        seeds = list(range(1001, 1006))
        if not a.digest_only:
            R.claim("phase1", "confirm", seeds, run_id="phase1-confirm")
    if a.digest_only:
        rows, _, _ = run_seeds(seeds, cells, costs, a.n)
        print(digest_rows(rows))
        return
    t0, status = time.perf_counter(), "FAILED"
    try:
        rows, meta, complete = run_seeds(seeds, cells, costs, a.n, checkpoint=a.checkpoint,
                                         deadline=t0 + a.wall_cap - 60 if a.wall_cap else None)
        status = "COMPLETE" if complete else "PARTIAL_WALL_CAP"
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave26-phase1-" + ("grid" if a.grid else "confirm"), seeds=list(seeds),
                                    wall_s=time.perf_counter() - t0, status=status)) + "\n")
    tab = table(rows, meta, cells, costs)
    rep = dict(table=tab, meta=meta, digest=digest_rows(rows))
    if a.grid:
        rep["selection"] = select(tab)
    else:
        from nexus.standing_gates import g_replay, g_soundness, g_tycho
        rep["G_soundness"] = g_soundness([q for r in rows for q in r["queries"]])
        rep["G_tycho"] = g_tycho(rows)
        rep["G_replay"] = g_replay(__file__, ["--cell", a.cell, "--c", str(a.c), "--n", str(a.n)], rep["digest"])
        v = list(tab.values())[0]
        rep["phase1_pass"] = v["full_beats"] and rep["G_soundness"]["passed"] and rep["G_replay"]["passed"]
    Path(a.out).write_text(json.dumps(dict(schema="wave26_phase1", report=rep, rows=rows), default=repr, sort_keys=True))
    for k, v in tab.items():
        ex = v["arms"]["exact_eig_enum"]["fully_loaded"]
        print(f"{k:28s} a={int(v['a'])} b={int(v['b'])} " + " ".join(
            f"{arm[:10]}={v['arms'][arm]['fully_loaded'] / max(1, ex):.3f}" for arm in v["arms"]))
    print(json.dumps({k: rep[k] for k in rep if k not in ("table", "meta")}, default=repr))


if __name__ == "__main__":
    main()
