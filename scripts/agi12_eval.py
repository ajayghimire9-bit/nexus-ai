"""Phase 12 matched evaluation (NOT LOCKED).
  python scripts/agi12_eval.py freeze
  python scripts/agi12_eval.py run SUITE CHUNK N        SUITE = dev | suite1 (ONE-USE) | suite2 (diagnostic) -> artifacts/agi12_eval/<suite>_cCHUNK.jsonl
  python scripts/agi12_eval.py score SUITE
Per (task, stream r): the SHARED candidate collection (synth12.collect: the frozen Phase 11 Stage A library L_r, fixed search, candidate
retention) runs ONCE inside a budget of COLLECT_SHARE of every cap; each arm then FORKS that budget (counters and clock carried over, the
FULL caps) and runs disamb12.resolve. Arms: first_match (diagnostic), fixed / random / nexus at B_q = 1 and 2. Every row is charged the
shared work in full plus its own. Caps per task (every arm): relational pops 1,000, micro-evaluations 150,000, full checks 5,000 (candidate
checks, probe evaluations and reference queries all count), constructed ASTs 400,000, wall 6 s. Submissions are verified NATIVELY on DuckDB
against the hidden batches. Rows are written and flushed immediately; a restarted chunk skips written rows (never rerun)."""
import fcntl, hashlib, json, resource, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase11 import abstr11 as A, core11 as C, tasks11 as T11, verify11 as V  # noqa: E402
from nexus.de_phase12 import disamb12 as D, manifest12 as M, synth12 as S, tasks12 as T  # noqa: E402
OUT = ROOT / "artifacts/agi12_eval"
FZ = ROOT / "artifacts/agi12_freeze.json"
CAPS = dict(rel_cap=1000, sc_cap=150000, fc_cap=5000, ast_cap=400000, wall=6.0)
ARMS = [("first_match", 1), ("fixed", 1), ("fixed", 2), ("random", 1), ("random", 2), ("nexus", 1), ("nexus", 2)]
REPS = ("rep0", "rep1")
LIBS = {r: ROOT / f"artifacts/agi11_stageA/{r}.final.json" for r in REPS}
CODE = ["src/nexus/de_phase12/" + f for f in ("synth12.py", "disamb12.py", "tasks12.py", "manifest12.py")] + ["scripts/agi12_eval.py"] + \
       ["src/nexus/de_phase11/" + f for f in ("core11.py", "sql11.py", "abstr11.py", "tasks11.py", "verify11.py")]


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def jdump(x):
    return json.dumps(x, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o))


def freeze():
    FZ.write_text(json.dumps(dict(libraries={str(f.relative_to(ROOT)): sha(f) for f in LIBS.values()}, code={f: sha(ROOT / f) for f in CODE},
                                  suite1=M.suite1(), suite2=M.suite2(), caps=CAPS, arms=ARMS, collect_share=D.COLLECT_SHARE,
                                  constructor=dict(ROWS_MAX=D.ROWS_MAX, MUT_MAX=D.MUT_MAX, PROBES=D.PROBES, FINAL_PROBES=D.FINAL_PROBES),
                                  retention=dict(M_MAX=S.M_MAX, RETAIN_POPS=S.RETAIN_POPS)), indent=1))
    print("frozen")


def build(t):
    if t["suite"] == "suite1":
        return T.build(t["mech"], t["inst"], t["seed"])
    learner, admin, hidden = T11.build(t["kind"], t["seed"], t["pool"])
    ref = hidden["ref"]
    adm = dict(static=[admin["evidence"], admin["valid"]], oracle=lambda env, ref=ref: C.evaluate(ref, env))
    return dict(learner, contracts={}), adm, hidden


def tasks(suite):
    return {"dev": M.dev, "suite1": M.suite1, "suite2": M.suite2}[suite]()


def claim_once(key):
    lock = ROOT / "var/agi12_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi12-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi12-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(suite, chunk, n):
    if suite != "dev":
        fz = json.loads(FZ.read_text())
        for f, h in list(fz["libraries"].items()) + list(fz["code"].items()):
            if sha(ROOT / f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
    if suite == "suite1":
        claim_once(("agi12", "suite1"))
    OUT.mkdir(parents=True, exist_ok=True)
    libs = {r: A.load_library(json.loads(LIBS[r].read_text())["library"]) for r in REPS}
    out = OUT / f"{suite}_c{chunk}.jsonl"
    done = {(x["task"], x["stream"], x["arm"], x["b_q"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in tasks(suite)[int(chunk)::int(n)]:
            learner, admin, hidden = build(t)
            for r in REPS:
                if all((learner["id"], r, a, b) in done for a, b in ARMS):
                    continue
                t0 = time.time()
                cb = S.Budget(**{k: (v * D.COLLECT_SHARE if k != "wall" else v * D.COLLECT_SHARE) for k, v in CAPS.items()})
                col = S.collect(learner, libs[r], S.Costs(), cb)
                shared = dict(counters=dict(cb.c), n_cands=len(col["candidates"]), wall=round(time.time() - t0, 3), exhausted=col["exhausted"])
                for arm, bq in ARMS:
                    if (learner["id"], r, arm, bq) in done:
                        continue
                    t1 = time.time()
                    ab = S.Budget(t0=time.time() - shared["wall"], start=shared["counters"], **CAPS)    # own clock: shared wall + this arm only
                    res = D.resolve(learner, admin, libs[r], S.Costs(), col, arm, bq, ab, seed=hash_seed(learner["id"], r))
                    sub = res.get("submission")
                    v = V.verify(sub["program"], libs[r], hidden) if sub is not None else None
                    caps_ok = all(ab.c[k] <= cap for k, cap in (("rel_evals", CAPS["rel_cap"]), ("micro_evals", CAPS["sc_cap"]), ("full_checks", CAPS["fc_cap"]),
                                                                  ("constructed_asts", CAPS["ast_cap"])))
                    row = dict(suite=suite, task=learner["id"], kind=hidden.get("kind"), mech=hidden.get("mech"), composed=hidden.get("composed"), stream=r, arm=arm, b_q=bq,
                               outcome=res["outcome"], verified=bool(v and v["ok"]), wrong=bool(v and not v["ok"]), queries=res.get("queries", []),
                               survivors=res.get("survivors"), n_cands=shared["n_cands"], counters=dict(ab.c), shared=shared, caps_ok=caps_ok,
                               provenance=(sub or {}).get("provenance"), program=(sub or {}).get("program"), size=(sub or {}).get("size"),
                               exhausted=res.get("exhausted"), native_executions=(v or {}).get("native_executions", 0), arm_wall=round(time.time() - t1, 3),
                               total_wall=round(shared["wall"] + time.time() - t1, 3))
                    fh.write(jdump(row) + "\n")
                    fh.flush()
            print(learner["id"], flush=True)
    print("peak_rss_mb", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 1))


def hash_seed(tid, r):
    """Numeric seed for the arm's input generator: the task's numeric seed and the stream index (no string hashing)."""
    return int("".join(ch for ch in tid if ch.isdigit())) * 10 + REPS.index(r)


def score(suite):
    rows = [json.loads(l) for f in sorted(OUT.glob(f"{suite}_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    tl = [build(t)[0]["id"] for t in tasks(suite)]
    keys = [(t, r, a, b) for t in tl for r in REPS for a, b in ARMS]
    by = {(x["task"], x["stream"], x["arm"], x["b_q"]): x for x in rows}
    res = dict(suite=suite, rows=len(rows), expected=len(keys), missing=[k for k in keys if k not in by], cells={}, contrasts={})
    for r in REPS:
        for a, b in ARMS:
            xs = [by[(t, r, a, b)] for t in tl if (t, r, a, b) in by]
            qs = [q for x in xs for q in x["queries"]]
            sub = [x for x in xs if x["outcome"] == "submitted"]
            res["cells"][f"{r} {a} B{b}"] = dict(n=len(xs), verified=sum(x["verified"] for x in xs), wrong=sum(x["wrong"] for x in xs), submitted=len(sub),
                                                 abstain=sum(x["outcome"].startswith("abstain") for x in xs), none=sum(x["outcome"] == "none" for x in xs),
                                                 queries=len(qs), split_rate=round(sum(q["split"] for q in qs if "split" in q) / max(1, sum("split" in q for q in qs)), 3),
                                                 caps_ok=sum(x["caps_ok"] for x in xs), max_full_checks=max([x["counters"].get("full_checks", 0) for x in xs] or [0]),
                                                 full_checks=sum(x["counters"].get("full_checks", 0) for x in xs), probe_evals=sum(x["counters"].get("probe_evals", 0) for x in xs),
                                                 micro=sum(x["counters"].get("micro_evals", 0) for x in xs), asts=sum(x["counters"].get("constructed_asts", 0) for x in xs),
                                                 wall=round(sum(x["total_wall"] for x in xs), 2),
                                                 scalar_fn=sum(bool((x["provenance"] or {}).get("scalar")) for x in sub if x["verified"]),
                                                 relational_fn=sum(bool((x["provenance"] or {}).get("relational")) for x in sub if x["verified"]),
                                                 by_mech={m: f"{sum(x['verified'] for x in xs if (x['mech'] or x['kind']) == m)}/{sum(1 for x in xs if (x['mech'] or x['kind']) == m)}"
                                                          for m in sorted({(x['mech'] or x['kind']) for x in xs})})
        for b in (1, 2):
            def diff(a1, a2):
                V1 = {t for t in tl if by.get((t, r, a1, b if a1 != "first_match" else 1), {}).get("verified")}
                V2 = {t for t in tl if by.get((t, r, a2, b if a2 != "first_match" else 1), {}).get("verified")}
                W1 = sum(by.get((t, r, a1, b if a1 != "first_match" else 1), {}).get("wrong", False) for t in tl)
                W2 = sum(by.get((t, r, a2, b if a2 != "first_match" else 1), {}).get("wrong", False) for t in tl)
                return dict(diff=len(V1) - len(V2), gains=sorted(V1 - V2), losses=sorted(V2 - V1), wrong=(W1, W2))
            res["contrasts"][f"{r} B{b}"] = {"nexus - fixed": diff("nexus", "fixed"), "nexus - random": diff("nexus", "random"), "fixed - first_match": diff("fixed", "first_match")}
    res["caps_violations"] = sum(not x["caps_ok"] for x in rows)
    (OUT / f"{suite}_result.json").write_text(jdump(res))
    print(json.dumps({k: (v["verified"], v["wrong"], v["submitted"], v["abstain"], v["split_rate"], v["max_full_checks"]) for k, v in res["cells"].items()}))
    print(json.dumps(res["contrasts"]))
    print("rows", len(rows), "missing", len(res["missing"]), "caps_violations", res["caps_violations"])


if __name__ == "__main__":
    a = sys.argv[1:]
    {"freeze": freeze, "run": lambda: run(*a[1:]), "score": lambda: score(a[1])}[a[0]]()
