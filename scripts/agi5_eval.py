"""Phase 5 frozen transfer evaluation (NOT LOCKED; ONE-USE agi5de/target claimed under an fcntl lock).
  python scripts/agi5_eval.py freeze | run RUNTIME [--dev] | score [--dev]
Arms (cross-project state frozen at entry; only within-project adaptation; r = 0, 1, 2 independent source lineages):
  A1_fresh_F0         empty repair memory, empty evidence memory, the strong fixed policy F0
  A2_mem_F0_r         lineage r's repair + evidence memory, F0
  A3_mem_learned_r    lineage r's memory, lineage r's automatically learned procedure + library
  A4_placebo_learned_r  the placebo history's memory and its learned procedure + library (lineage r)
  A5_learned_minus_procs_r  A3 with every library call removed (does removing a learned procedure remove its advantage?)
All arms: the same primitives, document access, checker / de_accept_v2, action set, one clarification of 1 probe row
(cost 2.0 cost-s), budgets 2.5 s SQLite / 10 s Spark per search. Searches are shared only between arms whose repair memory
is identical (A2 / A3 / A5 of one lineage) - the same deterministic inputs - and are charged once. The submitted FILE is
executed by the independent evaluator on 2 hidden batches; an undecided requirement makes every submission wrong."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
from nexus import seed_registry as R
from nexus.de_phase4 import world as W
from nexus.de_phase5 import investigate as IV, seeds5 as S5, world5 as W5
ROOT = Path(__file__).resolve().parents[1]
CODE = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/de_phase5").glob("*.py")) + ["scripts/agi5_eval.py"]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def paths(dev):
    return (ROOT / "artifacts/agi5_dev", ROOT / "artifacts/agi5_dev/eval") if dev else (ROOT / "artifacts/agi5_src", ROOT / "artifacts/agi5_eval")


def strip_calls(prog):
    out = []
    for s in prog:
        if s[0] == "call":
            continue
        out.append(["if", s[1], strip_calls(s[2])] + ([strip_calls(s[3])] if len(s) > 3 else []) if s[0] == "if" else s)
    return out


def arms(dev):
    src, _ = paths(dev)
    reps = sorted(int(p.stem[1:]) for p in src.glob("r*.json"))
    A = {"A1_fresh_F0": dict(mem=dict(de=None, _digest="empty"), em=IV.empty_evidence(), prog=IV.F0, lib={})}
    for r in reps:
        d = json.loads((src / f"r{r}.json").read_text())
        A[f"A2_mem_F0_r{r}"] = dict(mem=d["mem"], em=d["evidence"], prog=IV.F0, lib={})
        A[f"A3_mem_learned_r{r}"] = dict(mem=d["mem"], em=d["evidence"], prog=d["policy"], lib=d["library"])
        A[f"A4_placebo_learned_r{r}"] = dict(mem=d["placebo"]["mem"], em=d["placebo"]["evidence"], prog=d["placebo"]["policy"],
                                            lib=d["placebo"]["library"])
        A[f"A5_learned_minus_procs_r{r}"] = dict(mem=d["mem"], em=d["evidence"], prog=strip_calls(d["policy"]), lib={})
    for a in A.values():
        if a["mem"].get("de") is None:
            from nexus.de_phase4 import learner as L
            a["mem"] = dict(de=L.empty_de(), _digest="empty")
    return A


def manifest(dev):
    if not dev:
        return S5.target_manifest()
    T = copy.deepcopy(S5.target_manifest())[::3]                 # dev rehearsal: every 3rd target type on dev seeds
    for i, t in enumerate(T):
        t["seed"] = S5.RANGES[("agi5de", "dev")].start + 900 + i
    return T


def freeze():
    src, _ = paths(False)
    files = CODE + sorted(str(p.relative_to(ROOT)) for p in src.glob("r*.json"))
    (ROOT / "artifacts/agi5_freeze.json").write_text(json.dumps(dict(files={f: sha(f) for f in files}, manifest=S5.target_manifest()), indent=1))
    print("frozen", len(files), "files")


def claim_once():
    lock = ROOT / "var/agi5_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            key = ("agi5de", "target")
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi5-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi5-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def necessity(project, dp):
    """Was a question about this decision point necessary? (from the documents: unnecessary iff they state it unambiguously)"""
    claims = [c for s in W5.SOURCES for c in IV.read_claims(project["ws"], s) if dp.get("ref") is not None and c["subject"]["state_ref"] == dp["ref"]]
    return not (claims and len({c["effect_at_boundary"] for c in claims}) == 1)


def run(runtime, *flags):
    dev = "--dev" in flags
    _, D = paths(dev)
    if not dev:
        for f, h in json.loads((ROOT / "artifacts/agi5_freeze.json").read_text())["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
        claim_once()
    D.mkdir(parents=True, exist_ok=True)
    A = arms(dev)
    live = IV.Live()
    if runtime == "spark":
        t0 = time.time()
        W.SparkCode.warm()
        print("spark warm", round(time.time() - t0, 2), flush=True)
    out = D / f"rows_{runtime}.jsonl"
    done = {(x["arm"], x["pid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in manifest(dev):
            if t["runtime"] != runtime:
                continue
            spec = {k: v for k, v in t.items() if k not in ("seed", "kind", "instance")}
            p = W5.make_project5(spec, t["seed"], ROOT / "var/agi5_ws" / ("dev_eval" if dev else "eval"))
            for name, a in A.items():
                if (name, p["pid"]) in done:
                    continue
                st = IV.investigate(p, live, copy.deepcopy(a["em"]), a["mem"], a["prog"], a["lib"])
                o = IV.outcome(p, st, live.rts[runtime])
                asked = next((x for x in st.trace if x["action"] == "ask"), None)
                dp_asked = next((d for d in st.dps if asked and d["pos"] == asked["obs"]["pos"]), None)
                row = dict(pid=p["pid"], kind=t["kind"], expected=S5.expected_outcome(t), dps=t["dps"], runtime=runtime, arm=name,
                           decision=o["decision"], verified=o["verified"], wrong=o["wrong"],
                           justified_abstention=o["decision"] == "abstain" and S5.expected_outcome(t) == "abstain",
                           reason=st.decision.get("reason"), questions=st.cost["questions"],
                           question_necessary=necessity(p, dp_asked) if dp_asked else None,
                           question_answer=asked["obs"]["answer"] if asked else None,
                           resolutions=[dict(pos=d["pos"], via=d["via"], conflict=d["conflict"], undecided=d["undecided"]) for d in st.dps],
                           cost=st.cost, hidden=o.get("hidden"), trace=st.trace)
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
            print(runtime, p["pid"], len(A), "arms", flush=True)


def _rows(dev):
    _, D = paths(dev)
    return [json.loads(l) for p in sorted(D.glob("rows_*.jsonl")) for l in p.read_text().splitlines() if l.strip()]


def signflip(diffs, key, n=20000):
    """Two-sided paired sign-flip permutation p-value for the mean of per-project differences."""
    obs = abs(sum(diffs))
    rng = random.Random(f"agi5|{key}")
    hits = sum(abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= obs - 1e-12 for _ in range(n))
    return (hits + 1) / (n + 1)


def score(*flags):
    dev = "--dev" in flags
    rows = _rows(dev)
    _, D = paths(dev)
    by = {}
    for r in rows:
        by.setdefault(r["arm"], {})[r["pid"]] = r
    res = dict(n_rows=len(rows), arms={})
    for a, rs in by.items():
        v = list(rs.values())
        cs = lambda k: round(sum(x["cost"][k] for x in v), 3)              # noqa: E731
        res["arms"][a] = dict(n=len(v), verified=sum(x["verified"] for x in v), wrong=sum(x["wrong"] for x in v),
                              justified_abstentions=sum(x["justified_abstention"] for x in v), questions=sum(x["questions"] for x in v),
                              unnecessary_questions=sum(x["question_necessary"] is False for x in v),
                              undetermined_answers=sum(x["question_answer"] == "undetermined" for x in v),
                              sqlite_runs=cs("sqlite_runs"), spark_runs=cs("spark_runs"), wall_s=cs("wall_s"),
                              by_kind={k: f"{sum(x['verified'] for x in v if x['kind'] == k)}/{sum(x['kind'] == k for x in v)}"
                                       for k in sorted({x['kind'] for x in v})})
    pids = sorted(by.get("A1_fresh_F0", {}))
    reps = sorted({int(a.rsplit("_r", 1)[1]) for a in by if "_r" in a and a.rsplit("_r", 1)[1].isdigit()})

    def avg(prefix, pid, k="verified"):
        vals = [by[f"{prefix}_r{r}"][pid][k] for r in reps if pid in by.get(f"{prefix}_r{r}", {})]
        return sum(vals) / len(vals) if vals else None
    contrasts = {}
    for name, a, b in (("experience: A2-A1", "A2_mem_F0", "A1_fresh_F0"), ("procedure: A3-A2", "A3_mem_learned", "A2_mem_F0"),
                       ("history vs placebo: A3-A4", "A3_mem_learned", "A4_placebo_learned"),
                       ("procedure removal: A3-A5", "A3_mem_learned", "A5_learned_minus_procs")):
        d = []
        for pid in pids:
            x = avg(a, pid)
            y = by["A1_fresh_F0"][pid]["verified"] if b == "A1_fresh_F0" else avg(b, pid)
            if x is not None and y is not None:
                d.append(x - y)
        per_rep = {}
        for r in reps:
            ya = f"{b}_r{r}" if b != "A1_fresh_F0" else b
            per_rep[f"r{r}"] = sum(by[f"{a}_r{r}"][p]["verified"] - by[ya][p]["verified"] for p in pids if p in by.get(f"{a}_r{r}", {}))
        contrasts[name] = dict(n_projects=len(d), mean_pp=round(100 * sum(d) / len(d), 1) if d else None, per_lineage_projects=per_rep,
                               p_signflip=round(signflip(d, name), 4) if d and any(d) else 1.0)
    ps = sorted(((v["p_signflip"], k) for k, v in contrasts.items() if not k.startswith("procedure removal")))
    m = len(ps)
    for i, (p, k) in enumerate(ps):                                       # Holm correction over the 3 primary contrasts
        contrasts[k]["p_holm"] = round(min(1.0, max((m - j) * ps[j][0] for j in range(i + 1))), 4)
    res["contrasts"] = contrasts
    (D / "result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=0)[:3500])


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"freeze": lambda: freeze(), "run": lambda: run(*sys.argv[2:]), "score": lambda: score(*sys.argv[2:])}[cmd]()
