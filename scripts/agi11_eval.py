"""Phase 11 frozen evaluation (NOT LOCKED).
  python scripts/agi11_eval.py freeze [--dev]
  python scripts/agi11_eval.py suite1 CHUNK N [--dev]   ONE-USE agi11/suite1 -> artifacts/agi11_eval/s1_cCHUNK.jsonl
  python scripts/agi11_eval.py suite2 [--dev]           the 16 Phase 10C / 10E DEVELOPMENT tasks -> artifacts/agi11_eval/s2.jsonl
  python scripts/agi11_eval.py score [--dev]
ARMS (identical core grammar, physical types, refinement mechanism, evidence policy (one request), verifier, expanded-size limit and
WORK caps; r = rep0 / rep1; libraries frozen after Stage A, guides fitted in Stage B):
  F0    fixed search, no library               (shared by both streams)
  F1_r  fixed search, library L_r
  L0_r  learned guide G_A0_r, no library
  L1_r  learned guide G_M_r, library L_r
Every arm runs every target in ONE process, consecutively, in an order rotated by target index. WORK caps bind (Suite 1: relational pops
<= REL_E, micro-evaluations <= SC_E; Suite 2: half of each); the wall cap WALL_E is a logged safety. Submissions are verified NATIVELY on
DuckDB against the hidden batches; SQLite native execution of the same submission is recorded as coverage. Rows are written and flushed
immediately; a restarted chunk skips written rows (never rerun)."""
import fcntl, hashlib, json, resource, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase11 import abstr11 as A, core11 as C, ext11 as X, manifest11 as M, sql11 as Q, synth11 as S, tasks11 as T, verify11 as V  # noqa: E402
DEV = "--dev" in sys.argv
OUT = ROOT / ("artifacts/agi11_dev/eval" if DEV else "artifacts/agi11_eval")
SA = ROOT / ("artifacts/agi11_dev/stageA" if DEV else "artifacts/agi11_stageA")
SB = ROOT / ("artifacts/agi11_dev/stageB" if DEV else "artifacts/agi11_stageB")
FZ = ROOT / ("artifacts/agi11_dev/freeze.json" if DEV else "artifacts/agi11_freeze.json")
REL_E, SC_E, FC_E, WALL_E = 1000, 150000, 5000, 4.0      # AMENDMENT before any target opened: full checks are a work cap; caps lowered
REPS = ("rep0", "rep1")
CODE = ["src/nexus/de_phase11/" + f for f in ("core11.py", "sql11.py", "synth11.py", "abstr11.py", "guide11.py", "tasks11.py", "manifest11.py", "verify11.py", "ext11.py")] + \
       ["scripts/agi11_eval.py", "scripts/agi11_stageA.py", "scripts/agi11_stageB.py"]


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def jdump(x):
    return json.dumps(x, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o))


def suite1_targets():
    if DEV:
        b = M.RANGES[("agi11", "dev")].start + 900
        return [dict(kind=w, seed=b + i, pool="heldout") for i, w in enumerate(T.WITHHELD[2:6])]
    return M.suite1()


def freeze():
    files = {}
    for d in (SA, SB):
        for r in REPS:
            f = d / f"{r}.final.json"
            if f.exists():
                files[str(f.relative_to(ROOT))] = sha(f)
    FZ.write_text(json.dumps(dict(files=files, code={f: sha(ROOT / f) for f in CODE}, suite1=suite1_targets(),
                                  caps=dict(REL_E=REL_E, SC_E=SC_E, FC_E=FC_E, WALL_E=WALL_E, SIZE_LIMIT=S.SIZE_LIMIT, SC_SIZE=S.SC_SIZE, SLICE=S.SLICE)), indent=1))
    print("frozen", files)


def arms():
    out = {"F0": dict(lib={}, costs=S.Costs())}
    for r in REPS:
        fa, fb = SA / f"{r}.final.json", SB / f"{r}.final.json"
        if not fa.exists() or not fb.exists():
            continue
        lib = A.load_library(json.loads(fa.read_text())["library"])
        g = json.loads(fb.read_text())
        out[f"F1_{r}"] = dict(lib=lib, costs=S.Costs())
        out[f"L0_{r}"] = dict(lib={}, costs=S.Costs(g["G_A0"]))
        out[f"L1_{r}"] = dict(lib=lib, costs=S.Costs(g["G_M"]))
    return out


def check_freeze():
    fz = json.loads(FZ.read_text())
    for f, h in list(fz["files"].items()) + list(fz["code"].items()):
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")


def claim_once(key):
    lock = ROOT / "var/agi11_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi11-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi11-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run_row(suite, tid, kind, learner, admin, hidden, name, arm, caps, fh, rot):
    t0 = time.time()
    r = S.solve(learner, arm["lib"], arm["costs"], S.Budget(caps[0], caps[1], caps[2], caps[3]), evidence=lambda: admin["evidence"])
    v = V.verify(r["program"], arm["lib"], hidden) if r["program"] is not None else None
    sq = None
    if r["program"] is not None:
        try:
            sq = all(V._match(Q.execute(r["program"], env, "sqlite", arm["lib"]), exp) for env, exp in hidden["hid"])
        except C.Unsupported:
            sq = "unsupported"
    row = dict(suite=suite, task=tid, kind=kind, arm=name, rotation=rot, outcome=r["outcome"], verified=bool(v and v["ok"]), wrong=bool(v and not v["ok"]),
               counters=r["counters"], log=r["log"], search_wall=r["wall"], wall_bound=r["wall_bound"], size=r.get("size"), program=r["program"],
               uses=sorted({f for f in arm["lib"] if f in jdump(r["program"])}) if r["program"] is not None else [], native_executions=(v or {}).get("native_executions", 0),
               conformance_mismatch=(v or {}).get("conformance_mismatch"), sqlite_native_ok=sq, row_wall=round(time.time() - t0, 3))
    fh.write(jdump(row) + "\n")
    fh.flush()
    return row


def suite1(chunk, n):
    check_freeze()
    if not DEV:
        claim_once(("agi11", "suite1"))
    OUT.mkdir(parents=True, exist_ok=True)
    AR = arms()
    names = sorted(AR)
    out = OUT / f"s1_c{chunk}.jsonl"
    done = {(x["task"], x["arm"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for idx, t in list(enumerate(suite1_targets()))[int(chunk)::int(n)]:
            learner, admin, hidden = T.build(t["kind"], t["seed"], t["pool"])
            rot = idx % len(names)
            for name in names[rot:] + names[:rot]:
                if (learner["id"], name) in done:
                    continue
                run_row("suite1", learner["id"], t["kind"], learner, admin, hidden, name, AR[name], (REL_E, SC_E, WALL_E, FC_E), fh, rot)
            print(learner["id"], flush=True)
    print("peak_rss_mb", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 1))


def suite2():
    check_freeze()
    OUT.mkdir(parents=True, exist_ok=True)
    AR = arms()
    names = sorted(AR)
    EXT = X.tasks()
    out = OUT / "s2.jsonl"
    done = {(x["task"], x.get("arm")) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for idx, t in enumerate(EXT.TASKS):
            if (t["id"], "ingest") not in done:
                fh.write(jdump(dict(suite="suite2", task=t["id"], arm="ingest", label=X.LABELS.get(t["id"]), pattern=t["pattern"], **X.ingest(t))) + "\n")
                fh.flush()
            io = X.io_task(t)
            if io is None:
                if (t["id"], "-") not in done:
                    fh.write(jdump(dict(suite="suite2", task=t["id"], arm="-", outcome="no_reference_io_task", label=X.LABELS.get(t["id"]))) + "\n")
                    fh.flush()
                continue
            learner, admin, hidden = io
            rot = idx % len(names)
            for name in names[rot:] + names[:rot]:
                if (t["id"], name) in done:
                    continue
                run_row("suite2", t["id"], t["id"], learner, admin, hidden, name, AR[name], (REL_E // 2, SC_E // 2, WALL_E / 2, FC_E // 2), fh, rot)
            print(t["id"], flush=True)


def score():
    rows = [json.loads(l) for f in sorted(OUT.glob("s1_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    s2 = [json.loads(l) for l in (OUT / "s2.jsonl").read_text().splitlines()] if (OUT / "s2.jsonl").exists() else []
    tg = [T.build(t["kind"], t["seed"], t["pool"])[0]["id"] for t in suite1_targets()]
    AR = sorted(arms())
    by = {(x["task"], x["arm"]): x for x in rows}
    res = dict(suite1=dict(rows=len(rows), expected=len(tg) * len(AR), missing=[(t, a) for t in tg for a in AR if (t, a) not in by], arms={}, contrasts={}))
    for a in AR:
        xs = [by[(t, a)] for t in tg if (t, a) in by]
        res["suite1"]["arms"][a] = dict(n=len(xs), verified=sum(x["verified"] for x in xs), wrong=sum(x["wrong"] for x in xs), none=sum(x["outcome"] == "none" for x in xs),
                                        submitted=sum(x["outcome"] == "submitted" for x in xs), rel_evals=sum(x["counters"].get("rel_evals", 0) for x in xs),
                                        micro_evals=sum(x["counters"].get("micro_evals", 0) for x in xs), full_checks=sum(x["counters"].get("full_checks", 0) for x in xs),
                                        evidence_requests=sum(x["counters"].get("evidence_requests", 0) for x in xs), native_executions=sum(x["native_executions"] for x in xs),
                                        search_wall=round(sum(x["search_wall"] for x in xs), 2), wall_bound=sum(x["wall_bound"] for x in xs),
                                        sqlite_native_ok=sum(x["sqlite_native_ok"] is True for x in xs), uses={f: sum(f in x["uses"] for x in xs if x["verified"])
                                                                                                              for f in sorted({u for x in xs for u in x["uses"]})},
                                        by_kind={k: f"{sum(x['verified'] for x in xs if x['kind'] == k)}/{sum(1 for x in xs if x['kind'] == k)}" for k in T.WITHHELD})
    for r in REPS:
        def diff(a, b):
            V_ = {t for t in tg if by.get((t, a), {}).get("verified")}
            W_ = {t for t in tg if by.get((t, b), {}).get("verified")}
            common = [t for t in tg if (t, a) in by and (t, b) in by]
            return dict(diff=len(V_) - len(W_), gains=sorted(V_ - W_), losses=sorted(W_ - V_), n=len(common),
                        rel_evals=(sum(by[(t, a)]["counters"].get("rel_evals", 0) for t in common), sum(by[(t, b)]["counters"].get("rel_evals", 0) for t in common)),
                        micro=(sum(by[(t, a)]["counters"].get("micro_evals", 0) for t in common), sum(by[(t, b)]["counters"].get("micro_evals", 0) for t in common)),
                        wall=(round(sum(by[(t, a)]["search_wall"] for t in common), 2), round(sum(by[(t, b)]["search_wall"] for t in common), 2)))
        if f"F1_{r}" in AR:
            res["suite1"]["contrasts"][r] = {"F1 - F0": diff(f"F1_{r}", "F0"), "L1 - L0": diff(f"L1_{r}", f"L0_{r}"), "L0 - F0": diff(f"L0_{r}", "F0"),
                                             "L1 - F0": diff(f"L1_{r}", "F0")}
    res["suite2"] = dict(ingest=[x for x in s2 if x.get("arm") == "ingest"], no_io=[x["task"] for x in s2 if x.get("arm") == "-"],
                         arms={a: dict(verified=sum(x["verified"] for x in s2 if x.get("arm") == a), wrong=sum(x["wrong"] for x in s2 if x.get("arm") == a),
                                       n=sum(1 for x in s2 if x.get("arm") == a),
                                       tasks={x["task"]: ("V" if x["verified"] else "W" if x["wrong"] else "-") for x in s2 if x.get("arm") == a}) for a in AR})
    (OUT / "result.json").write_text(jdump(res))
    print(json.dumps({a: (v["verified"], v["wrong"], v["n"]) for a, v in res["suite1"]["arms"].items()}))
    print(json.dumps({r: {k: (v["diff"], v["gains"], v["losses"]) for k, v in c.items()} for r, c in res["suite1"]["contrasts"].items()}))
    print("missing", len(res["suite1"]["missing"]), "suite2", json.dumps({a: (v["verified"], v["wrong"], v["n"]) for a, v in res["suite2"]["arms"].items()}))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dev"]
    {"freeze": freeze, "suite1": lambda: suite1(*a[1:]), "suite2": suite2, "score": score}[a[0]]()
