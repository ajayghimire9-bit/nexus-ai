"""Phase 6 frozen evaluation (NOT LOCKED; ONE-USE agi6de/target and agi6de/panel claimed under an fcntl lock).
  python scripts/agi6_eval.py freeze_source | freeze_meta | run targets CHUNK N | run panel CHUNK N | score [--dev]
Arms (cross-project state frozen at entry; within-project adaptation only; r = 0, 1, 2):
  A1_fresh_F0            empty memory, the strong fixed procedure F0 (read all, whole-pipeline search, calibrated trust,
                         one question, submit / abstain)
  A2_learnedmem_F0_r     the Fixed cohort endpoint: learned pi / invented skills / calibrated trust, procedure F0
  A3_full_r              the Full endpoint: memory + automatically composed procedure + library (+ its evolved M)
  A4_solvedonly_r        the Solved-Only cohort endpoint (no learning from refutations / partial stage repairs)
  A5_procedure_only_r    A3 with every invented skill removed (isolates the procedure from the skill library L*)
  A6_scrambled_r         the Scrambled cohort endpoint (permuted feedback; matched executions)
  Meta_r_{Mstar,M0,Mrand}  the Stage 3 improver clones (panel only)
Search budget per project 1.0 s (prescreen on SQLite, survivors verified on the declared DuckDB / Spark engines); one
1-row clarification (cost 2.0 cost-s); de_accept_v3 everywhere; the evaluator executes the SUBMITTED target files of every
stage on their engines over 2 hidden batches; an undecided requirement makes every submission wrong."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
from nexus import seed_registry as R
from nexus.de_phase4 import world as W
from nexus.de_phase6 import lineage6 as L6, procedure6 as PR, seeds6 as S6, world6 as W6
ROOT = Path(__file__).resolve().parents[1]
REPS = (0, 1, 2)
BUDGET = 1.0
CODE = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/de_phase6").glob("*.py")) + ["scripts/agi6_eval.py"]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def paths(dev):
    return (ROOT / "artifacts/agi6_dev/src", ROOT / "artifacts/agi6_dev/eval") if dev else (ROOT / "artifacts/agi6_src", ROOT / "artifacts/agi6_eval")


def endpoint(src, name):
    d = json.loads((src / f"{name}.json").read_text())
    return dict(mem=d["memory"], prog=d["procedure"], lib=d["library"])


def arms(kind, dev):
    src, _ = paths(dev)
    if kind == "panel":
        A = {}
        for r in REPS:
            for m in ("Mstar", "M0", "Mrand"):
                f = ROOT / ("artifacts/agi6_dev/meta" if dev else "artifacts/agi6_meta") / f"r{r}_{m}.json"
                if f.exists():
                    d = json.loads(f.read_text())
                    A[f"Meta_r{r}_{m}"] = dict(mem=d["memory"], prog=d["procedure"], lib=d["library"])
        return A
    A = {"A1_fresh_F0": dict(mem=L6.empty_memory(), prog=PR.F0, lib={})}
    for r in REPS:
        if not (src / f"Full_r{r}.json").exists():
            continue
        full = endpoint(src, f"Full_r{r}")
        A[f"A2_learnedmem_F0_r{r}"] = dict(endpoint(src, f"Fixed_r{r}"), prog=PR.F0, lib={}) if (src / f"Fixed_r{r}.json").exists() else None
        A[f"A3_full_r{r}"] = full
        if r != 0:                                     # attribution arms on r0 only (pre-registered size rule 0.6)
            A[f"A2_learnedmem_F0_r{r}"], A[f"A3_full_r{r}"] = A[f"A2_learnedmem_F0_r{r}"], full
            continue
        if (src / f"SolvedOnly_r{r}.json").exists():
            A[f"A4_solvedonly_r{r}"] = endpoint(src, f"SolvedOnly_r{r}")
        po = copy.deepcopy(full)
        po["mem"]["de"]["skills"] = {}
        L6.redigest(po["mem"])
        A[f"A5_procedure_only_r{r}"] = po
        if (src / f"Scrambled_r{r}.json").exists():
            A[f"A6_scrambled_r{r}"] = endpoint(src, f"Scrambled_r{r}")
    return {k: v for k, v in A.items() if v is not None}


def manifest(kind, dev):
    T = S6.panel_manifest() if kind == "panel" else S6.target_manifest()
    if kind == "panel" and not dev:
        T = T[::3]                                    # 6 of 18 (recorded budget deviation, artifacts/agi6_allocation.json)
    if dev:
        T = copy.deepcopy(T)[::9] if kind != "panel" else copy.deepcopy(T)[::6]
        for i, t in enumerate(T):
            t["seed"] = S6.RANGES[("agi6de", "dev")].start + 1500 + i + (100 if kind == "panel" else 0)
    return T


def freeze_source():
    src, _ = paths(False)
    files = CODE + sorted(str(p.relative_to(ROOT)) for p in src.glob("*.json"))
    (ROOT / "artifacts/agi6_freeze_source.json").write_text(json.dumps(dict(files={f: sha(f) for f in files}, manifest=S6.target_manifest(),
                                                                            panel=S6.panel_manifest()), indent=1))
    print("frozen", len(files))


def freeze_meta():
    files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "artifacts/agi6_meta").glob("*.json"))
    (ROOT / "artifacts/agi6_freeze_meta.json").write_text(json.dumps(dict(files={f: sha(f) for f in files}), indent=1))
    print("frozen", len(files))


def claim_once(key):
    lock = ROOT / "var/agi6_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi6-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi6-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(kind, chunk, n, *flags):
    dev = "--dev" in flags
    chunk, n = int(chunk), int(n)
    _, D = paths(dev)
    if not dev:
        for fz in ("artifacts/agi6_freeze_source.json",) + (("artifacts/agi6_freeze_meta.json",) if kind == "panel" else ()):
            for f, h in json.loads((ROOT / fz).read_text())["files"].items():
                if sha(f) != h:
                    raise SystemExit(f"differs from the freeze: {f}")
        claim_once(("agi6de", "panel" if kind == "panel" else "target"))
    D.mkdir(parents=True, exist_ok=True)
    A = arms(kind, dev)
    W.SparkCode.warm()
    live = PR.Live(lambda p: BUDGET)
    out = D / f"{kind}_c{chunk}.jsonl"
    done = {(x["arm"], x["pid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in manifest(kind, dev)[chunk::n]:
            spec = {k: v for k, v in t.items() if k not in ("seed", "tier") and v is not None}
            try:
                p = W6.make_project6(spec, t["seed"], ROOT / "var/agi6_ws" / ("dev_" if dev else "") / kind)
            except RuntimeError as e:
                fh.write(json.dumps(dict(pid=f"build_failed:{t['seed']}", arm="-", error=str(e)[:100])) + "\n")
                continue
            for name, a in A.items():
                if (name, p["pid"]) in done:
                    continue
                st = PR.investigate(p, live, copy.deepcopy(a["mem"]), a["prog"], a["lib"])
                o = PR.outcome(p, st)
                srch = next((x["obs"] for x in st.trace if x["action"] == "search"), {})
                row = dict(pid=p["pid"], arm=name, tier=p["tier"], paradigm=p["paradigm"], hybrid=p.get("hybrid"), n_stages=len(p["stages"]),
                           engines=[s_["engine"] for s_ in p["stages"]], langs=[s_["legacy_lang"] for s_ in p["stages"]], dps=p["dps"],
                           undecided=bool(p["undecided"]), decision=o["decision"], verified=o["verified"], wrong=o["wrong"],
                           justified_abstention=o["decision"] == "abstain" and bool(p["undecided"]), reason=st.decision.get("reason"),
                           questions=st.cost["questions"], answers=[x["obs"]["answer"] for x in st.trace if x["action"] == "ask"],
                           cost=st.cost, search=dict(mode=srch.get("mode"), skills=srch.get("skills"), outcome=srch.get("outcome"),
                                                     shared=srch.get("shared")),
                           resolutions=[dict(stage=d["stage"], via=d["via"], conflict=d["conflict"], undecided=d["undecided"]) for d in st.dps],
                           hidden=o.get("hidden"), trace=[dict(action=x["action"], decision=x["decision"]) for x in st.trace])
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
            print(kind, p["pid"], len(A), "arms", flush=True)


# ------------------------------------------------------------------ scoring
def _rows(dev):
    _, D = paths(dev)
    return [json.loads(l) for p in sorted(D.glob("*_c*.jsonl")) for l in p.read_text().splitlines() if l.strip()]


def signflip(d, key, n=20000):
    obs = abs(sum(d))
    rng = random.Random(f"agi6|{key}")
    return (sum(abs(sum(x if rng.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(n)) + 1) / (n + 1)


def score(*flags):
    dev = "--dev" in flags
    _, D = paths(dev)
    rows = [r for r in _rows(dev) if r.get("arm") != "-"]
    by = {}
    for r in rows:
        by.setdefault(r["arm"], {})[r["pid"]] = r
    res = dict(n_rows=len(rows), build_failures=[r for r in _rows(dev) if r.get("arm") == "-"], arms={})
    for a, rs in by.items():
        v = list(rs.values())
        res["arms"][a] = dict(n=len(v), verified=sum(x["verified"] for x in v), wrong=sum(x["wrong"] for x in v),
                              justified_abstentions=sum(x["justified_abstention"] for x in v), undecided=sum(x["undecided"] for x in v),
                              questions=sum(x["questions"] for x in v), by_tier={t: f"{sum(x['verified'] for x in v if x['tier'] == t)}/"
                                                                                    f"{sum(x['tier'] == t for x in v)}" for t in (1, 2, 3)},
                              cost=dict(sqlite_runs=sum(x["cost"]["sqlite_runs"] for x in v), duckdb_runs=sum(x["cost"]["duckdb_runs"] for x in v),
                                        spark_runs=sum(x["cost"]["spark_runs"] for x in v), wall_s=round(sum(x["cost"]["wall_s"] for x in v), 2)),
                              search_modes=dict(__import__("collections").Counter(f"{x['search']['mode']}|{x['search']['skills']}" for x in v)))
    pids = sorted(by.get("A1_fresh_F0", {}))

    def avg(prefix, pid):
        vals = [by[f"{prefix}_r{r}"][pid]["verified"] for r in REPS if pid in by.get(f"{prefix}_r{r}", {})]
        return sum(vals) / len(vals) if vals else None
    contr = {}
    for name, a, b, filt in (("Full - Fresh F0 (all)", "A3_full", "A1", lambda r: True), ("Full - Fresh F0 (Tier 3)", "A3_full", "A1", lambda r: r["tier"] == 3),
                             ("Learned procedure - fixed F0 (Tier 2+3)", "A3_full", "A2_learnedmem_F0", lambda r: r["tier"] >= 2),
                             ("Full - Solved-Only (failure memory)", "A3_full", "A4_solvedonly", lambda r: True),
                             ("Full - procedure only (skill library)", "A3_full", "A5_procedure_only", lambda r: True),
                             ("Full - Scrambled (placebo)", "A3_full", "A6_scrambled", lambda r: True),
                             ("Learned memory F0 - Fresh F0 (experience)", "A2_learnedmem_F0", "A1", lambda r: True)):
        d = []
        for pid in pids:
            r0 = by["A1_fresh_F0"][pid]
            if not filt(r0):
                continue
            x = avg(a, pid)
            y = r0["verified"] if b == "A1" else avg(b, pid)
            if x is not None and y is not None:
                d.append(x - y)
        contr[name] = dict(n=len(d), mean_pp=round(100 * sum(d) / len(d), 1) if d else None, p_signflip=round(signflip(d, name), 4) if d and any(d) else 1.0)
    prim = [k for k in contr if k.startswith(("Full - Fresh", "Learned procedure"))]
    ps = sorted((contr[k]["p_signflip"], k) for k in prim)
    for i, (p, k) in enumerate(ps):
        contr[k]["p_holm"] = round(min(1.0, max((len(ps) - j) * ps[j][0] for j in range(i + 1))), 4)
    res["contrasts"] = contr
    cost = {}
    for r in REPS:
        F, Z = by.get(f"A3_full_r{r}", {}), by.get("A1_fresh_F0", {})
        both = [p for p in F if p in Z and F[p]["verified"] and Z[p]["verified"]]
        cf = sum(F[p]["cost"]["wall_s"] + 2 * F[p]["questions"] for p in both)
        cz = sum(Z[p]["cost"]["wall_s"] + 2 * Z[p]["questions"] for p in both)
        rf = sum(F[p]["cost"]["sqlite_runs"] + F[p]["cost"]["duckdb_runs"] + F[p]["cost"]["spark_runs"] + F[p]["questions"] for p in both)
        rz = sum(Z[p]["cost"]["sqlite_runs"] + Z[p]["cost"]["duckdb_runs"] + Z[p]["cost"]["spark_runs"] + Z[p]["questions"] for p in both)
        cost[f"r{r}"] = dict(shared_solves=len(both), cost_s=[round(cf, 2), round(cz, 2)], saving_cost_s=round(1 - cf / cz, 3) if cz else None,
                             runs_plus_questions=[rf, rz], saving_runs=round(1 - rf / rz, 3) if rz else None)
    res["cost_full_vs_fresh_on_shared_solves"] = cost
    res["wrong_total_all_arms"] = sum(v["wrong"] for v in res["arms"].values())
    (D / "result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("contrasts", "cost_full_vs_fresh_on_shared_solves", "wrong_total_all_arms")}, indent=0)[:3000])


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "run":
        run(*sys.argv[2:])
    elif c == "score":
        score(*sys.argv[2:])
    else:
        {"freeze_source": freeze_source, "freeze_meta": freeze_meta}[c]()
