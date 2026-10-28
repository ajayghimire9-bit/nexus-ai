"""mi discovery (NOT LOCKED; development data only). Resumable; one call <= 760 s of work.
  python scripts/mi_discover.py cache                 fast-path cache for the discovery and selection pools
  python scripts/mi_discover.py ARM                    ARM in evolve | random_struct | params; N_EVAL candidate evaluations
  python scripts/mi_discover.py select ARM             top-3 (discovery fitness) re-evaluated on the selection pool -> winner
Fitness of a candidate procedure (run 2; disclosed revision after run 1 collapsed onto empty procedures because every candidate
scored 0 and the CPU penalty was the only signal) = number of episodes (discovery pool) whose held-out stream is reproduced exactly
by the machine the full-space stage learns with that procedure + 0.5 x the mean fraction of register searches the procedure's
space explained (learner-side, no evaluator information) - 0.0001 x CPU s (cap CAP_S per episode). Run 1 is kept in
artifacts/mi_dev/run1/. Only episodes the shared fast path
did not accept enter the pools (the fast path is identical for every candidate). No human selects or writes a candidate: the
seed is the transcribed existing procedure; every other candidate is produced by the generic operators of mi_lpl; the winner is
chosen by the rule above. State: artifacts/mi_dev/disc_<ARM>.json (every candidate: program, lineage, per-episode results)."""
import copy, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi_seeds, mi_ocean as M, mi_learner as ML, mi_lpl as LP, seed_registry as R  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/mi_dev"
N_EVAL, CAP_S, POP = 24, 8.0, 8
POOL_N = dict(disc=12, sel=12)
UNF = ("MUL", "ADDC", "SUBH")
WORK_S = 760


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def episode(split, i):
    seeds = list(R.REGISTRY[("mi", split)])
    fam = M.DEV_FAMILIES[i % len(M.DEV_FAMILIES)]
    return M.Episode(seeds[i], fam)


def cache():
    """Run the shared fast path on dev episodes until each pool holds POOL_N failing episodes (balanced over UNF + K)."""
    pol = ba_eps.policy("learned", "bounded")
    T0 = time.perf_counter()
    for split in ("disc", "sel"):
        p = D / f"fastpath_{split}.json"
        st = load(p, dict(rows=[], next=0))
        while sum(not r["accepted"] for r in st["rows"]) < POOL_N[split] and time.perf_counter() - T0 < WORK_S:
            i = st["next"]
            ep = episode(split, i)
            st["next"] = i + 1
            fail_fam = sum(1 for r in st["rows"] if not r["accepted"] and r["family"] == ep.family)
            if ep.family == "K" or fail_fam >= POOL_N[split] // len(UNF):  # pools: unfamiliar dev families, balanced
                continue
            r, s = ML.fast_path(ep, pol, ep.seed)
            sc = ML.score(ep, r)
            st["rows"].append(dict(i=i, seed=ep.seed, family=ep.family, accepted=r is not None, exact=sc["exact"], **s))
            save(p, st)
            print(split, i, ep.family, r is not None, sc["exact"], s["cpu_s"], flush=True)


def pool(split):
    st = load(D / f"fastpath_{split}.json", dict(rows=[]))
    return [r for r in st["rows"] if not r["accepted"]][:POOL_N[split]]


def evaluate(domain_fn, rows, split, cap_s, max_s=60.0):
    res, fit, cpu = [], 0, 0.0
    for r in rows:
        ep = episode(split, r["i"])
        out, s = ML.full_space(ep, domain_fn, ep.seed, max_s=max_s, cap_s=cap_s)
        sc = ML.score(ep, out)
        res.append(dict(i=r["i"], family=r["family"], exact=sc["exact"], silent=sc["silent"], outcome=s["outcome"], cpu_s=s["cpu_s"],
                        queries=s["queries"], domain_sizes=s.get("domain_sizes"), explained=round(s.get("explained", 0.0), 3)))
        fit += sc["exact"] + 0.5 * s.get("explained", 0.0) / len(rows)
        cpu += s["cpu_s"]
    return fit - 0.0001 * cpu, res


def domain_of(cand):
    if cand["kind"] == "params":
        return ML.params_domain(cand["size_bound"]), cand["max_s"]
    return ML.lpl_domain(cand["prog"]), 60.0


def propose(arm, st, k):
    rnd = random.Random(f"mi-{arm}-{k}")
    ev = st["cands"]
    if arm == "params":
        return dict(kind="params", size_bound=rnd.choice([3, 5, 7, 9]), max_s=rnd.choice([2.0, 4.0, 8.0, 60.0]),
                    lineage=dict(op="random parameter draw"))
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
    if k == 0:                                                       # evolve
        return dict(kind="lpl", prog=copy.deepcopy(LP.SEED_BASELINE), lineage=dict(op="seed (transcribed existing procedure)"))
    if k < 3:
        return dict(kind="lpl", prog=LP.random_program(rnd), lineage=dict(op="random_program"))
    ranked = sorted(range(len(ev)), key=lambda j: -ev[j]["fitness"])[:POP]
    def tour():
        a, b = rnd.sample(ranked, 2) if len(ranked) > 1 else (ranked[0], ranked[0])
        return a if ev[a]["fitness"] >= ev[b]["fitness"] else b
    if rnd.random() < 0.3 and len(ranked) > 1:
        a, b = tour(), tour()
        p, e = LP.crossover(ev[a]["prog"], ev[b]["prog"], rnd)
        return dict(kind="lpl", prog=p, lineage=dict(op=e, parents=[a, b]))
    a = tour()
    p, edits = copy.deepcopy(ev[a]["prog"]), []
    for _ in range(rnd.randint(1, 3)):
        p, e = LP.mutate(p, rnd)
        edits.append(e)
    return dict(kind="lpl", prog=p, lineage=dict(op="mutate", parents=[a], edits=edits))


def search(arm):
    p = D / f"disc_{arm}.json"
    st = load(p, dict(arm=arm, cands=[]))
    rows = pool("disc")
    T0 = time.perf_counter()
    while len(st["cands"]) < N_EVAL and time.perf_counter() - T0 < WORK_S - 12 * CAP_S:
        k = len(st["cands"])
        c = propose(arm, st, k)
        dom, max_s = domain_of(c)
        c0 = time.process_time()
        fit, res = evaluate(dom, rows, "disc", CAP_S, max_s)
        c.update(id=k, fitness=round(fit, 4), exact=sum(r["exact"] for r in res), silent=sum(r["silent"] for r in res), per_episode=res,
                 eval_cpu_s=round(time.process_time() - c0, 2))
        if c["kind"] == "lpl":
            c["space_size_empty_ctx"] = LP.hypothesis_space(c["prog"], {})[1]["size"]
        st["cands"].append(c)
        save(p, st)
        print(arm, k, c["lineage"]["op"], "exact", c["exact"], "/", len(rows), "silent", c["silent"], "cpu", c["eval_cpu_s"], flush=True)


def select(arm):
    st = load(D / f"disc_{arm}.json", None)
    top = sorted(st["cands"], key=lambda c: (-c["fitness"], c["id"]))[:3]
    rows = pool("sel")
    out = load(D / f"select_{arm}.json", dict(arm=arm, evals=[]))
    done = {e["id"] for e in out["evals"]}
    T0 = time.perf_counter()
    for c in top:
        if c["id"] in done or time.perf_counter() - T0 > WORK_S - 12 * 20:
            continue
        dom, max_s = domain_of(c)
        fit, res = evaluate(dom, rows, "sel", 20.0, max_s)
        out["evals"].append(dict(id=c["id"], disc_fitness=c["fitness"], sel_fitness=round(fit, 4), per_episode=res))
        save(D / f"select_{arm}.json", out)
        print(arm, "select", c["id"], "sel", round(fit, 3), flush=True)
    if len(out["evals"]) == len(top):
        w = sorted(out["evals"], key=lambda e: (-e["sel_fitness"], -e["disc_fitness"], e["id"]))[0]
        out["winner"] = next(c for c in st["cands"] if c["id"] == w["id"])
        save(D / f"select_{arm}.json", out)
        print(arm, "WINNER", w["id"], w["sel_fitness"])


if __name__ == "__main__":
    D.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "cache":
        cache()
    elif sys.argv[1] == "select":
        select(sys.argv[2])
    else:
        search(sys.argv[1])
