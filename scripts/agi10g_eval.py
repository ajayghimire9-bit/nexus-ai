"""Phase 10G one-use evaluation: 4 investigation arms x 2 streams x B_ev in {1, 2} on a FRESH 48-target draw (NOT LOCKED).
  python scripts/agi10g_eval.py freeze [--dev]
  python scripts/agi10g_eval.py run CHUNK N [--dev]     ONE-USE agi10gde/eval -> artifacts/agi10g_eval/rows_cCHUNK.jsonl
  python scripts/agi10g_eval.py score [--dev]
SHARED SOLVER (every arm): atomic-dedup substrate + the stream's learned guidance G_L0 (guides["L0"] of rep{r}.final.json), library L0,
dag10g acceptance, search10e (work 600, wall 4 s). Per (target, stream) the search and the tie set are computed ONCE and shared by the
arms (identical deterministic computation; each row is charged the shared work in full). On a tie each arm orders the 5 channels:
  E0 none (abstain)   E1 uniform random (rng10c (stream, seed, 77))   E2 fixed operator-type rule   E3 learned pi_ev (guides["pi_ev"])
and spends at most B_ev requests (primary B_ev = 1; sensitivity B_ev = 2; ev10g.resolve). A resolved survivor other than c* must pass
the declared-engine re-run (1 charged execution). Every submission is verified on the DECLARED engine against 2 hidden batches.
Rows appended + flushed; a restarted chunk skips written rows (never rerun)."""
import fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase10f import atomic10f as AT  # noqa: E402
from nexus.de_phase10g import ev10g as EV, lineage10g as LG, manifest10g as MG  # noqa: E402
DEV = "--dev" in sys.argv
TR = ROOT / ("artifacts/agi10g_dev/train" if DEV else "artifacts/agi10g_train")
OUT = ROOT / ("artifacts/agi10g_dev/eval" if DEV else "artifacts/agi10g_eval")
FZ = ROOT / ("artifacts/agi10g_dev/freeze.json" if DEV else "artifacts/agi10g_freeze.json")
CODE = ["src/nexus/de_phase10g/" + f for f in ("dag10g.py", "ev10g.py", "lineage10g.py", "manifest10g.py", "world10g.py")] + \
       ["src/nexus/de_phase10f/" + f for f in ("abstract10f.py", "atomic10f.py", "dag10f.py", "lineage10f.py", "world10f.py")] + \
       ["src/nexus/de_phase10e/" + f for f in ("dag10e.py", "search10e.py", "lineage10e.py")] + \
       ["src/nexus/de_phase10d/" + f for f in ("ir10d.py", "engines10d.py", "legacy10d.py", "world10d.py", "dag10d.py")] + ["scripts/agi10g_eval.py", "scripts/agi10g_train.py"]
REPS, ARMS, BUDGETS = ("rep0", "rep1"), ("E0", "E1", "E2", "E3"), (1, 2)
CH_OF = {"seq": 1, "time": 2, "grain": 3}


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def manifest():
    return MG.dev_manifest() if DEV else MG.eval_manifest()


def freeze():
    files = {str((TR / f"{r}.final.json").relative_to(ROOT)): sha(TR / f"{r}.final.json") for r in REPS if (TR / f"{r}.final.json").exists()}
    FZ.write_text(json.dumps(dict(files=files, code={f: sha(ROOT / f) for f in CODE}, manifest=manifest()), indent=1))
    print("frozen", files)


def claim_once(key):
    lock = ROOT / "var/agi10g_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10g-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10g-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(chunk, n):
    chunk, n = int(chunk), int(n)
    fz = json.loads(FZ.read_text())
    for f, h in list(fz["files"].items()) + list(fz["code"].items()):
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if not DEV:
        claim_once(("agi10gde", "eval"))
    OUT.mkdir(parents=True, exist_ok=True)
    mem = {r: json.loads((TR / f"{r}.final.json").read_text())["memory"] for r in REPS}
    out = OUT / f"rows_c{chunk}.jsonl"
    done = {(x["stream"], x["arm"], x["b_ev"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with AT.atomic(), open(out, "a") as fh:
        for t in manifest()[chunk::n]:
            p = LG.build(t, t["seed"], ROOT / "var/agi10g_ws" / ("deveval" if DEV else "eval"))
            for ri, r in enumerate(REPS):
                if all((r, a, b, t["seed"]) in done for a in ARMS for b in BUDGETS):
                    continue
                t0 = time.time()
                inv = LG.inv_for(p)
                res = LG.SD.search(inv, LG.arm_memory(guide_w=mem[r]["guides"].get("L0")), LG.WORK, LG.WALL)
                w_search = res["work"]
                C, sigs, w_tie = [], [], 0
                if res["outcome"] == "submitted":
                    w0 = sum(inv.runs.values())
                    C, sigs = EV.tie_set(inv, res["path"])
                    w_tie = sum(inv.runs.values()) - w0
                feats = EV.features(sigs, len(C)) if len(C) > 1 else []
                orders = dict(E0=[], E1=EV.order_E1(ri, t["seed"]), E2=EV.order_E2(sigs), E3=EV.order_E3(mem[r]["guides"].get("pi_ev"), feats))
                shared_wall = time.time() - t0
                cache = {}
                for a in ARMS:
                    for b in BUDGETS:
                        if (r, a, b, t["seed"]) in done:
                            continue
                        t1 = time.time()
                        chosen, rr, extra = None, None, 0
                        if res["outcome"] == "submitted":
                            if len(C) == 1:
                                chosen, outcome = C[0], "submitted_no_tie"
                            else:
                                rr = EV.resolve(inv, C, orders[a], b if a != "E0" else 0, cache)
                                chosen, outcome = rr["chosen"], rr["outcome"]
                                if chosen is not None and chosen[1] != res["specs"]:
                                    extra = 1
                                    ek = ("engine", EV.norm(chosen[1]))
                                    if ek not in cache:
                                        cache[ek] = inv.run(chosen[1], prescreen=False)["ok"]
                                    if not cache[ek]:
                                        chosen, outcome = None, "abstain_engine_verify_failed"
                        else:
                            outcome = "none"
                        h = LG.verify_hidden(p, chosen[1]) if chosen is not None else None
                        reqs = (rr or {}).get("requests", [])
                        row = dict(seed=t["seed"], stream=r, arm=a, b_ev=b, group=t["group"], family=t["family"], amb=t["amb"], engine=t["engine"], legacy=t["legacy"],
                                   pid=p["pid"], outcome=outcome, verified=bool(h and h["ok"]), wrong=bool(h and not h["ok"]), tie=len(C), tie_ops=sorted({s["op"] for s in sigs}),
                                   order=orders[a][:b] if len(C) > 1 else [], requests=reqs, hit=[q["eliminated"] > 0 for q in reqs],
                                   relevant_channel=CH_OF.get(t["amb"]), w_search=w_search, w_tie=w_tie, ev_execs=(rr or {}).get("ev_execs", 0) + extra,
                                   total_exec=w_search + w_tie + (rr or {}).get("ev_execs", 0) + extra, path=[list(e) for e in (chosen[0] if chosen else [])],
                                   shared_wall=round(shared_wall, 3), row_wall=round(time.time() - t1, 3))
                        fh.write(json.dumps(row, default=str) + "\n")
                        fh.flush()
            print(p["pid"], flush=True)


def signflip(d, key):
    obs = abs(sum(d))
    if not any(d):
        return 1.0
    r = random.Random(key)
    return round((sum(abs(sum(x if r.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(20000)) + 1) / 20001, 4)


def score():
    rows = [json.loads(l) for f in sorted(OUT.glob("rows_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    man = manifest()
    by = {(x["stream"], x["arm"], x["b_ev"], x["seed"]): x for x in rows}
    missing = [(r, a, b, t["seed"]) for t in man for r in REPS for a in ARMS for b in BUDGETS if (r, a, b, t["seed"]) not in by]
    res = dict(n_rows=len(rows), expected_rows=len(man) * len(REPS) * len(ARMS) * len(BUDGETS), missing=len(missing), cells={}, contrasts={}, by_mechanism={})
    for r in REPS:
        for a in ARMS:
            for b in BUDGETS:
                xs = [by[(r, a, b, t["seed"])] for t in man if (r, a, b, t["seed"]) in by]
                ties = [x for x in xs if x["tie"] > 1]
                reqs = [q for x in xs for q in x["requests"]]
                g = lambda grp: sum(x["verified"] for x in xs if x["group"] == grp)            # noqa: E731
                res["cells"][f"{r} {a} B{b}"] = dict(heldout=g("heldout"), ordinary=g("ordinary"), wrong=sum(x["wrong"] for x in xs),
                                                     abstain=sum(x["outcome"].startswith("abstain") for x in xs), none=sum(x["outcome"] == "none" for x in xs),
                                                     ties=len(ties), ties_resolved=sum(x["outcome"] == "resolved" for x in ties), requests=len(reqs),
                                                     hit_rate=round(100 * sum(q["eliminated"] > 0 for q in reqs) / len(reqs), 1) if reqs else None,
                                                     relevant_first=sum(bool(x["order"]) and x["order"][0] == x["relevant_channel"] for x in ties),
                                                     exec_search=sum(x["w_search"] + x["w_tie"] for x in xs), exec_evidence=sum(x["ev_execs"] for x in xs),
                                                     exec_total=sum(x["total_exec"] for x in xs), n=len(xs))
                for m in ("seq", "time", "grain", None):
                    ms = [x for x in xs if x["amb"] == m]
                    res["by_mechanism"][f"{r} {a} B{b} {m}"] = f"{sum(x['verified'] for x in ms)}/{len(ms)}"
    for b in BUDGETS:
        for grp in ("heldout", "ordinary"):
            ss = [t["seed"] for t in man if t["group"] == grp]
            for r in REPS:
                def diff(a1, a2):
                    d = [float(by.get((r, a1, b, s), {}).get("verified", False)) - float(by.get((r, a2, b, s), {}).get("verified", False)) for s in ss]
                    return dict(diff=int(sum(d)), n=len(d), p_signflip=signflip(d, f"10g|{r}|{a1}|{a2}|{grp}|{b}"))
                res["contrasts"][f"{grp} {r} B{b}"] = {"E3 - E2": diff("E3", "E2"), "E3 - E1": diff("E3", "E1"), "E3 - E0": diff("E3", "E0"),
                                                       "E2 - E0": diff("E2", "E0"), "E1 - E0": diff("E1", "E0")}
    res["learning"] = {}
    for r in REPS:
        ck = json.loads((TR / f"{r}.final.json").read_text())
        w = [json.loads(l) for l in (TR / f"{r}.wake.jsonl").read_text().splitlines()]
        res["learning"][r] = dict(tasks=len(w), verified=sum(x["verified"] for x in w), wrong=sum(x["wrong"] for x in w), wrong_tasks=[(x["seed"], x["family"], x["path"]) for x in w if x["wrong"]],
                                  ties=sum(bool(x["tie"]) for x in w), ties_resolved=sum(bool(x["tie"]) and x["tie"]["resolved"] for x in w),
                                  wake_search_exec=sum(x["work"] for x in w), exploration_ev_exec=ck["memory"].get("ev_execs", 0), cost_s=ck["cost"], pi_ev=ck.get("pi_ev"),
                                  wall_bound=sum(x["wall_bound"] for x in w))
    res["eval_wrong_total"] = sum(v["wrong"] for v in res["cells"].values())
    (OUT / "result.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("n_rows", "expected_rows", "missing", "eval_wrong_total")}))
    for k, v in res["cells"].items():
        print(k, {kk: v[kk] for kk in ("heldout", "ordinary", "wrong", "abstain", "ties", "ties_resolved", "requests", "hit_rate", "exec_total")})


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dev"]
    {"run": lambda: run(*a[1:]), "score": score, "freeze": freeze}[a[0]]()
