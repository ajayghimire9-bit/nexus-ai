"""MI-2 discovery (NOT LOCKED; development data only: mi2/disc, mi2/sel, mi2/bdev). Resumable; one call <= WORK_S of work.
  python scripts/mi2_discover.py cache POOLSET                POOLSET a (Milestone A: disc + sel) | b (Milestone B: bdev)
  python scripts/mi2_discover.py search ARM LINEAGE [POOLSET]  ARM in evolve | random_struct | params | b0 | b1
  python scripts/mi2_discover.py select ARM LINEAGE [POOLSET]
Frozen rules (MI-2 pre-registration):
  * Pools: episodes on which the shared fast path does NOT accept, family-balanced. A: disc 60 (MUL / ADDC / SUBH x 20),
    sel 30 (x 10). B: bdev disc 45 + sel 30 over SCL / AVG / MAX (families no Milestone-A procedure was discovered or selected on).
  * Every candidate is scored by mi2_learner.full_space with a per-episode CPU cap CAP_S on the WHOLE discovery pool.
  * Fitness (lexicographic, frozen): (exact episodes, mean fraction of register searches solved [partial credit, learner-side,
    recorded separately], -evaluation CPU s). Exactness = the evaluator's held-out stream check.
  * CPU-matched discovery: each lineage runs until its summed candidate-evaluation CPU reaches B_LIN s (failed and degenerate
    candidates included; the last candidate may overrun and the overrun is recorded). Candidate counts are reported, not matched.
  * evolve: seed (transcribed existing procedure) + 2 random programs, then tournament (top POP) mutation (1-3 edits) /
    crossover (p 0.3). random_struct: random programs or the seed with 1-6 random edits, no selection. params: the A4 grid
    (mi2_learner.PARAMS_GRID) in a lineage-seeded random order, without replacement (finite: may stop early, recorded).
    b0 = evolve (the original improver) on the B pools; b1 = evolve whose mutation call site is mi2_lpl.mutate_lib with the
    library of accepted machine-generated procedures (artifacts/mi2_accepted.json, written only by mi2_score.py after a passing
    Milestone-A confirmation) and P_LIB; otherwise identical.
  * Selection inside a lineage: the top 3 by discovery fitness re-scored on the selection pool; winner = best (sel exact, sel
    partial, disc fitness, -id). An arm's representative = the lineage winner with the best selection score (ties: lower lineage).
No human or Claude writes or edits a candidate once a search starts; privileged witness domains are refused."""
import copy, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi2_seeds, mi_ocean as M, mi_learner as ML, mi2_learner as M2, mi_lpl as LP, mi2_lpl as L2, seed_registry as R  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/mi2_dev"
CAP_S, B_LIN, POP, P_LIB, WORK_S = 3.0, 1200.0, 8, 0.3, 820
POOLS = {"a": dict(disc=("disc", ("MUL", "ADDC", "SUBH"), 20), sel=("sel", ("MUL", "ADDC", "SUBH"), 10)),
         "b": dict(disc=("bdev", ("SCL", "AVG", "MAX"), 15), sel=("bdev", ("SCL", "AVG", "MAX"), 10))}


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def cache(ps):
    """Fast path on seeds of the split in order; family of seed index k = FAMS[k % 3]; keep failing episodes until each pool
    is full. For poolset b, disc and sel draw from the same split in order (disc filled first; no episode in both)."""
    res = load(ROOT / "artifacts/mi2_test/result.json", {})
    if ps == "b" and not res.get("passed"):
        raise SystemExit("Milestone B pools touch SCL / AVG / MAX: refused unless Milestone A's confirmation was scored and passed")
    pol = ba_eps.policy("learned", "bounded")
    T0 = time.perf_counter()
    st = load(D / f"fastpath_{ps}.json", dict(rows=[], next={}))
    for name in ("disc", "sel"):
        split, fams, per = POOLS[ps][name]
        seeds = list(R.REGISTRY[("mi2", split)])
        used = {(r["seed"], r["family"]) for r in st["rows"]}
        while time.perf_counter() - T0 < WORK_S:
            have = {f: sum(1 for r in st["rows"] if r["pool"] == name and not r["accepted"] and r["family"] == f) for f in fams}
            if all(v >= per for v in have.values()):
                break
            k = st["next"].get(split, 0)
            st["next"][split] = k + 1
            fam = fams[k % len(fams)]
            if have[fam] >= per or (seeds[k], fam) in used:
                continue
            ep = M.Episode(seeds[k], fam)
            r, s = ML.fast_path(ep, pol, ep.seed)
            sc = ML.score(ep, r)
            st["rows"].append(dict(pool=name, split=split, k=k, seed=ep.seed, family=fam, accepted=r is not None, exact=sc["exact"],
                                   silent=sc["silent"], **s))
            save(D / f"fastpath_{ps}.json", st)
            print(ps, name, k, fam, r is not None, sc["exact"], s["cpu_s"], flush=True)


def pool(ps, name):
    rows = [r for r in load(D / f"fastpath_{ps}.json", dict(rows=[]))["rows"] if r["pool"] == name and not r["accepted"]]
    _, fams, per = POOLS[ps][name]
    out = []
    for f in fams:
        out += [r for r in rows if r["family"] == f][:per]
    return out


def evaluate(domain_fn, rows, max_s=60.0, cap_s=CAP_S):
    if getattr(domain_fn, "privileged", False):
        raise SystemExit("privileged witness domains are development-diagnosis only")
    res, cpu = [], 0.0
    for r in rows:
        ep = M.Episode(r["seed"], r["family"])
        out, s = M2.full_space(ep, domain_fn, ep.seed, max_s=max_s, cap_s=cap_s)
        sc = ML.score(ep, out)
        res.append(dict(seed=r["seed"], family=r["family"], exact=sc["exact"], silent=sc["silent"], outcome=s["outcome"], cpu_s=s["cpu_s"],
                        queries=s["queries"], domain_sizes=s["domain_sizes"], explained=round(s["explained"], 3)))
        cpu += s["cpu_s"]
    ex = sum(r["exact"] for r in res)
    part = sum(r["explained"] for r in res) / len(res)
    return [ex, round(part, 4), -round(cpu, 2)], res


def domain_of(c):
    if c["kind"] == "params":
        return M2.params_domain(c["size_bound"], c["max_lit"]), c["max_s"]
    return ML.lpl_domain(c["prog"]), 60.0


def library():
    """Accepted machine-generated procedures: written ONLY by scripts/mi2_score.py when Milestone A's confirmation passes."""
    acc = load(ROOT / "artifacts/mi2_accepted.json", {})
    return [json.loads((ROOT / p).read_text())["winner"]["prog"] for p in acc.get("accepted", [])]


def propose(arm, lin, st):
    k = len(st["cands"])
    rnd = random.Random(f"mi2-{'b' if arm in ('b0', 'b1') else arm}-L{lin}-{k}")   # b0 / b1 pairs: identical RNG streams
    ev = st["cands"]
    if arm == "params":
        order = list(M2.PARAMS_GRID)
        random.Random(f"mi2-params-L{lin}").shuffle(order)
        if k >= len(order):
            return None
        b, mlit, ms = order[k]
        return dict(kind="params", size_bound=b, max_lit=mlit, max_s=ms, lineage=dict(op="grid draw (no replacement)"))
    if arm == "random_struct":
        if k == 0:
            return dict(kind="lpl", prog=copy.deepcopy(LP.SEED_BASELINE), lineage=dict(op="seed (transcribed existing procedure)"))
        if rnd.random() < 0.5:
            return dict(kind="lpl", prog=LP.random_program(rnd), lineage=dict(op="random_program"))
        p, edits = copy.deepcopy(LP.SEED_BASELINE), []
        for _ in range(rnd.randint(1, 6)):
            p, e = LP.mutate(p, rnd)
            edits.append(e)
        return dict(kind="lpl", prog=p, lineage=dict(op="seed + random edits (no selection)", edits=edits))
    lib = library() if arm == "b1" else []                           # evolve / b0: the original improver (empty library)
    if arm == "b1" and not lib:
        raise SystemExit("b1 needs an accepted machine-generated procedure (artifacts/mi2_accepted.json)")
    if k == 0:
        return dict(kind="lpl", prog=copy.deepcopy(LP.SEED_BASELINE), lineage=dict(op="seed (transcribed existing procedure)"))
    if k < 3:
        return dict(kind="lpl", prog=LP.random_program(rnd), lineage=dict(op="random_program"))
    ranked = sorted(range(len(ev)), key=lambda j: [-v for v in ev[j]["fitness"]])[:POP]

    def tour():
        a, b = rnd.sample(ranked, 2)
        return a if ev[a]["fitness"] >= ev[b]["fitness"] else b
    if rnd.random() < 0.3:
        a, b = tour(), tour()
        p, e = LP.crossover(ev[a]["prog"], ev[b]["prog"], rnd)
        return dict(kind="lpl", prog=p, lineage=dict(op=e, parents=[a, b]))
    a = tour()
    p, edits = copy.deepcopy(ev[a]["prog"]), []
    for _ in range(rnd.randint(1, 3)):
        p, e = L2.mutate_lib(p, rnd, lib, P_LIB)
        edits.append(e)
    return dict(kind="lpl", prog=p, lineage=dict(op="mutate", parents=[a], edits=edits))


def search(arm, lin, ps):
    p = D / f"disc_{ps}_{arm}_L{lin}.json"
    st = load(p, dict(arm=arm, lineage=lin, poolset=ps, b_lin=B_LIN, cap_s=CAP_S, cands=[], spent_cpu_s=0.0))
    rows = pool(ps, "disc")
    T0 = time.perf_counter()
    while st["spent_cpu_s"] < B_LIN and time.perf_counter() - T0 < WORK_S - len(rows) * CAP_S:
        c = propose(arm, lin, st)
        if c is None:
            st["exhausted"] = True
            save(p, st)
            break
        dom, max_s = domain_of(c)
        c0 = time.process_time()
        fit, res = evaluate(dom, rows, max_s)
        c.update(id=len(st["cands"]), fitness=fit, exact=fit[0], partial=fit[1], silent=sum(r["silent"] for r in res),
                 per_family={f: sum(r["exact"] for r in res if r["family"] == f) for f in POOLS[ps]["disc"][1]},
                 per_episode=res, eval_cpu_s=round(time.process_time() - c0, 2))
        if c["kind"] == "lpl":
            c["space_size_empty_ctx"] = LP.hypothesis_space(c["prog"], {})[1]["size"]
        st["cands"].append(c)
        st["spent_cpu_s"] = round(st["spent_cpu_s"] + c["eval_cpu_s"], 2)
        save(p, st)
        print(arm, lin, c["id"], c["lineage"]["op"][:40], "fit", fit, c["per_family"], "silent", c["silent"], "spent", st["spent_cpu_s"], flush=True)
    if st["spent_cpu_s"] >= B_LIN:
        st["overrun_cpu_s"] = round(st["spent_cpu_s"] - B_LIN, 2)
        save(p, st)


def select(arm, lin, ps):
    st = load(D / f"disc_{ps}_{arm}_L{lin}.json", None)
    top = sorted(st["cands"], key=lambda c: ([-v for v in c["fitness"]], c["id"]))[:3]
    rows = pool(ps, "sel")
    p = D / f"select_{ps}_{arm}_L{lin}.json"
    out = load(p, dict(arm=arm, lineage=lin, evals=[]))
    done = {e["id"] for e in out["evals"]}
    for c in top:
        if c["id"] in done:
            continue
        dom, max_s = domain_of(c)
        c0 = time.process_time()
        fit, res = evaluate(dom, rows, max_s)
        out["evals"].append(dict(id=c["id"], disc_fitness=c["fitness"], sel_fitness=fit, eval_cpu_s=round(time.process_time() - c0, 2),
                                 per_family={f: sum(r["exact"] for r in res if r["family"] == f) for f in POOLS[ps]["sel"][1]},
                                 per_episode=res))
        save(p, out)
        print(arm, lin, "select", c["id"], fit, flush=True)
    w = sorted(out["evals"], key=lambda e: ([-v for v in e["sel_fitness"][:2]], [-v for v in e["disc_fitness"]], e["id"]))[0]
    out["winner"] = next(c for c in st["cands"] if c["id"] == w["id"])
    out["winner_sel_fitness"] = w["sel_fitness"]
    save(p, out)
    print(arm, lin, "WINNER", w["id"], w["sel_fitness"])


if __name__ == "__main__":
    D.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "cache":
        cache(sys.argv[2])
    else:
        ps = sys.argv[4] if len(sys.argv) > 4 else "a"
        (search if cmd == "search" else select)(sys.argv[2], int(sys.argv[3]), ps)
