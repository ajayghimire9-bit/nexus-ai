"""Phase 12B factorial evaluation (NOT LOCKED; scripts/agi12_eval.py adapted).
  python scripts/agi12b_eval.py freeze
  python scripts/agi12b_eval.py run SUITE CHUNK N      SUITE = p12 | p11 (Stage 2 diagnostics, opened suites) | fresh (ONE-USE) -> artifacts/agi12b_eval/
  python scripts/agi12b_eval.py score SUITE
Per (task, stream r): TWO shared candidate collections (synth12b.collect with reopen False / True; the frozen Phase 11 Stage A library L_r;
fixed search; candidate retention; 70 % of every cap); each arm continues from the matching collection with its own clock and the FULL caps
(full checks 5,000 incl. probes and queries; strict CappedCounter). ARMS (name, selector, B_q, reopen = Change A, challenge = Change B):
  F2_base fixed 2 F -   N2_base nexus 2 F F   N2_challenge nexus 2 F T   F2_reopen fixed 2 T -   N2_both nexus 2 T T   R2_reopen random 2 T -
  diagnostics at B_q = 1: F1_reopen fixed 1 T -   N1_both nexus 1 T T
Stage 2 diagnostic subsets (pre-registered): p12 = all 24 Phase 12 Suite 1 tasks with the 5 attribution arms (F2_base N2_base N2_challenge
F2_reopen N2_both); p11 = the Phase 11 tasks that were wrong in Phase 11 or 12 (T113003 T113006 T113014 T113018 T113022) with the same arms.
Submissions verified NATIVELY on DuckDB against the hidden batches; rows written + flushed immediately, never rerun."""
import fcntl, hashlib, json, resource, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase11 import abstr11 as A, core11 as C, tasks11 as T11, verify11 as V  # noqa: E402
from nexus.de_phase12 import tasks12 as T12  # noqa: E402
from nexus.de_phase12b import disamb12b as D, manifest12b as M, synth12b as S, tasks12b as T  # noqa: E402
OUT = ROOT / "artifacts/agi12b_eval"
FZ = ROOT / "artifacts/agi12b_freeze.json"
CAPS = dict(rel_cap=1000, sc_cap=150000, fc_cap=5000, ast_cap=400000, wall=6.0)
ARMS = [("F2_base", "fixed", 2, False, False), ("N2_base", "nexus", 2, False, False), ("N2_challenge", "nexus", 2, False, True),
        ("F2_reopen", "fixed", 2, True, False), ("N2_both", "nexus", 2, True, True), ("R2_reopen", "random", 2, True, False),
        ("F1_reopen", "fixed", 1, True, False), ("N1_both", "nexus", 1, True, True)]
DIAG_ARMS = ("F2_base", "N2_base", "N2_challenge", "F2_reopen", "N2_both")
P11_DIAG = ("T113003", "T113006", "T113014", "T113018", "T113022")
REPS = ("rep0", "rep1")
LIBS = {r: ROOT / f"artifacts/agi11_stageA/{r}.final.json" for r in REPS}
CODE = ["src/nexus/de_phase12b/" + f for f in ("synth12b.py", "disamb12b.py", "tasks12b.py", "manifest12b.py")] + ["scripts/agi12b_eval.py"] + \
       ["src/nexus/de_phase11/" + f for f in ("core11.py", "sql11.py", "abstr11.py", "tasks11.py", "verify11.py")]


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def jdump(x):
    return json.dumps(x, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o))


def freeze():
    FZ.write_text(json.dumps(dict(libraries={str(f.relative_to(ROOT)): sha(f) for f in LIBS.values()}, code={f: sha(ROOT / f) for f in CODE},
                                  fresh=M.fresh(), caps=CAPS, arms=ARMS, collect_share=D.COLLECT_SHARE, reopen=dict(REOPEN_BAND=S.REOPEN_BAND, REOPEN_ALTS=S.REOPEN_ALTS),
                                  challenge_probes=D.CHALLENGE_PROBES,
                                  constructor=dict(ROWS_MAX=D.ROWS_MAX, MUT_MAX=D.MUT_MAX, PROBES=D.PROBES, FINAL_PROBES=D.FINAL_PROBES),
                                  retention=dict(M_MAX=S.M_MAX, RETAIN_POPS=S.RETAIN_POPS)), indent=1))
    print("frozen")


def build(t):
    if t["suite"] == "fresh":
        return T.build(t["mech"], t["inst"], t["seed"])
    if t["suite"] == "p12":
        return T12.build(t["mech"], t["inst"], t["seed"])
    learner, admin, hidden = T11.build(t["kind"], t["seed"], t["pool"])
    ref = hidden["ref"]
    adm = dict(static=[admin["evidence"], admin["valid"]], oracle=lambda env, ref=ref: C.evaluate(ref, env))
    return dict(learner, contracts={}), adm, hidden


def tasks(suite):
    return {"p12": M.p12, "p11": M.p11, "fresh": M.fresh}[suite]()


def claim_once(key):
    lock = ROOT / "var/agi12b_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi12b-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi12b-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(suite, chunk, n):
    if True:
        fz = json.loads(FZ.read_text())
        for f, h in list(fz["libraries"].items()) + list(fz["code"].items()):
            if sha(ROOT / f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
    if suite == "fresh":
        claim_once(("agi12b", "fresh"))
    OUT.mkdir(parents=True, exist_ok=True)
    libs = {r: A.load_library(json.loads(LIBS[r].read_text())["library"]) for r in REPS}
    out = OUT / f"{suite}_c{chunk}.jsonl"
    done = {(x["task"], x["stream"], x["arm"], x["b_q"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    arms = [a for a in ARMS if suite == "fresh" or a[0] in DIAG_ARMS]
    with open(out, "a") as fh:
        for t in tasks(suite)[int(chunk)::int(n)]:
            learner, admin, hidden = build(t)
            if suite == "p11" and learner["id"] not in P11_DIAG:
                continue
            for r in REPS:
                if all((learner["id"], r, a[0], a[2]) in done for a in arms):
                    continue
                shared = {}
                for reopen in (False, True):
                    if not any(a[3] == reopen for a in arms):
                        continue
                    t0 = time.time()
                    cb = S.Budget(**{k: v * D.COLLECT_SHARE for k, v in CAPS.items()})
                    col = S.collect(learner, libs[r], S.Costs(), cb, reopen=reopen)
                    shared[reopen] = dict(col=col, counters=dict(cb.c), n_cands=len(col["candidates"]), wall=round(time.time() - t0, 3), exhausted=col["exhausted"])
                for name, arm, bq, reopen, challenge in arms:
                    if (learner["id"], r, name, bq) in done:
                        continue
                    sh = shared[reopen]
                    t1 = time.time()
                    ab = S.Budget(t0=time.time() - sh["wall"], start=sh["counters"], **CAPS)
                    res = D.resolve(learner, admin, libs[r], S.Costs(), sh["col"], arm, bq, ab, seed=hash_seed(learner["id"], r), challenge=challenge, reopen=reopen)
                    sub = res.get("submission")
                    v = V.verify(sub["program"], libs[r], hidden) if sub is not None else None
                    caps_ok = all(ab.c[k] <= cap for k, cap in (("rel_evals", CAPS["rel_cap"]), ("micro_evals", CAPS["sc_cap"]), ("full_checks", CAPS["fc_cap"]),
                                                                  ("constructed_asts", CAPS["ast_cap"])))
                    row = dict(suite=suite, task=learner["id"], kind=hidden.get("kind"), mech=hidden.get("mech"), composed=hidden.get("composed"), stream=r, arm=name, b_q=bq,
                               selector=arm, reopen=reopen, challenge=challenge, outcome=res["outcome"], verified=bool(v and v["ok"]), wrong=bool(v and not v["ok"]),
                               queries=res.get("queries", []), survivors=res.get("survivors"), n_cands=sh["n_cands"], counters=dict(ab.c), caps_ok=caps_ok,
                               shared_wall=sh["wall"], provenance=(sub or {}).get("provenance"), program=(sub or {}).get("program"), size=(sub or {}).get("size"),
                               exhausted=res.get("exhausted"), native_executions=(v or {}).get("native_executions", 0), arm_wall=round(time.time() - t1, 3),
                               total_wall=round(sh["wall"] + time.time() - t1, 3))
                    fh.write(jdump(row) + "\n")
                    fh.flush()
            print(learner["id"], flush=True)
    print("peak_rss_mb", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 1))


def hash_seed(tid, r):
    """Numeric seed for the arm's input generator: the task's numeric seed and the stream index (no string hashing)."""
    return int("".join(ch for ch in tid if ch.isdigit())) * 10 + REPS.index(r)


def score(suite):
    rows = [json.loads(l) for f in sorted(OUT.glob(f"{suite}_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    arms = [a for a in ARMS if suite == "fresh" or a[0] in DIAG_ARMS]
    tl = sorted({x["task"] for x in rows}) if suite == "p11" else [build(t)[0]["id"] for t in tasks(suite)]
    by = {(x["task"], x["stream"], x["arm"]): x for x in rows}
    keys = [(t, r, a[0]) for t in tl for r in REPS for a in arms]
    res = dict(suite=suite, rows=len(rows), expected=len(keys), missing=[k for k in keys if k not in by], cells={}, contrasts={}, per_task={})
    for r in REPS:
        for a in arms:
            xs = [by[(t, r, a[0])] for t in tl if (t, r, a[0]) in by]
            qs = [q for x in xs for q in x["queries"]]
            res["cells"][f"{r} {a[0]}"] = dict(n=len(xs), verified=sum(x["verified"] for x in xs), wrong=sum(x["wrong"] for x in xs),
                                               submitted=sum(x["outcome"] == "submitted" for x in xs), abstain=sum(x["outcome"].startswith("abstain") for x in xs),
                                               queries=len(qs), q_disagreeing=sum(q.get("distinct_predictions", 1) >= 2 for q in qs),
                                               q_singleton_or_unanimous=sum(q.get("distinct_predictions", 1) < 2 for q in qs if "distinct_predictions" in q),
                                               q_challenge=sum(q.get("qtype") == "challenge" for q in qs), shared_belief_falsified=sum(bool(q.get("all_falsified")) for q in qs),
                                               recovered_after_restart=sum(x["verified"] for x in xs if any(q.get("all_falsified") for q in x["queries"])),
                                               caps_ok=sum(x["caps_ok"] for x in xs), max_full_checks=max([x["counters"].get("full_checks", 0) for x in xs] or [0]),
                                               full_checks=sum(x["counters"].get("full_checks", 0) for x in xs), probe_evals=sum(x["counters"].get("probe_evals", 0) for x in xs),
                                               wall=round(sum(x["total_wall"] for x in xs), 2),
                                               recovery_functions=sorted({f"{k}:{f}" for x in xs if x["verified"] and any(q.get("all_falsified") for q in x["queries"])
                                                                          for k in ("scalar", "relational") for f in (x["provenance"] or {}).get(k, [])}),
                                               by_mech={m: f"{sum(x['verified'] for x in xs if (x['mech'] or x['kind']) == m)}/{sum(1 for x in xs if (x['mech'] or x['kind']) == m)}"
                                                        for m in sorted({(x['mech'] or x['kind']) for x in xs})})

        def diff(a1, a2):
            V1 = {t for t in tl if by.get((t, r, a1), {}).get("verified")}
            V2 = {t for t in tl if by.get((t, r, a2), {}).get("verified")}
            W1 = sum(by.get((t, r, a1), {}).get("wrong", False) for t in tl)
            W2 = sum(by.get((t, r, a2), {}).get("wrong", False) for t in tl)
            return dict(diff=len(V1) - len(V2), gains=sorted(V1 - V2), losses=sorted(V2 - V1), wrong=(W1, W2))
        pairs = [("N2_challenge", "N2_base"), ("N2_challenge", "F2_base"), ("F2_reopen", "F2_base"), ("N2_both", "F2_base")]
        if suite == "fresh":
            pairs += [("N2_both", "F2_reopen"), ("N2_both", "R2_reopen"), ("N1_both", "F1_reopen")]
        res["contrasts"][r] = {f"{a1} - {a2}": diff(a1, a2) for a1, a2 in pairs}
    for t in tl:
        res["per_task"][t] = {f"{r} {a[0]}": ("V" if by.get((t, r, a[0]), {}).get("verified") else "W" if by.get((t, r, a[0]), {}).get("wrong") else "-")
                              for r in REPS for a in arms}
    res["caps_violations"] = sum(not x["caps_ok"] for x in rows)
    (OUT / f"{suite}_result.json").write_text(jdump(res))
    print(json.dumps({k: (v["verified"], v["wrong"], v["submitted"], v["abstain"], v["q_challenge"], v["shared_belief_falsified"], v["max_full_checks"]) for k, v in res["cells"].items()}))
    print(json.dumps({r: {k: (v["diff"], v["wrong"]) for k, v in c.items()} for r, c in res["contrasts"].items()}))
    print("rows", len(rows), "missing", len(res["missing"]), "caps_violations", res["caps_violations"])


if __name__ == "__main__":
    a = sys.argv[1:]
    {"freeze": freeze, "run": lambda: run(*a[1:]), "score": lambda: score(a[1])}[a[0]]()
