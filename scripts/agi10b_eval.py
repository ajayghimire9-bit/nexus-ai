"""Phase 10B frozen evaluations (NOT LOCKED).
  python scripts/agi10b_eval.py freeze                  checkpoint + code + manifest hashes -> artifacts/agi10b_freeze.json
  python scripts/agi10b_eval.py run CHUNK N             ONE-USE agi10bde/eval (48) x 11 arms -> artifacts/agi10b_eval/rows_cCHUNK.jsonl
  python scripts/agi10b_eval.py confirm CHUNK N         ONE-USE agi9de/confirm (18) x 5 arms (ONLY after the gate passed; refuses otherwise)
  python scripts/agi10b_eval.py score
PRE-REGISTERED ARMS (F0 procedure; final checkpoints of the two repetitions rep0 / rep1; N3 = tasks reached within the cap):
  A1          fresh memory, fixed guide, base primitives (incl. the shared ROUND primitive)
  Full_r      trust + L* (incl. valley-crossing macros) + learned ranker WITH bridge expansion + strongest P* hypotheses
  noLib_r     Full without the library (and without P* hypotheses)
  noBridge_r  Full with the learned ranker WITHOUT bridge expansion (Phase 10 70 / 30 mixing)
  noRanker_r  Full with the fixed guide (no ranker, no bridge)
  noTrust_r   Full without calibrated trust
Confirmation (18 x 5): A1, Full_r, TrustOnly_r (trust, no library, fixed guide) for r = 0, 1 (two-parent paired comparison).
Rows appended + flushed; restarted chunks resume after written rows."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, memory10 as MEM, procedure10 as PR10  # noqa: E402
from nexus.de_phase9 import blocks9 as B9  # noqa: E402
from nexus.de_phase10b import fixes10b, lineage10b as LB, manifest10b as MB, search10b  # noqa: E402,F401
TR = ROOT / "artifacts/agi10b_train"
D = ROOT / "artifacts/agi10b_eval"


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def ck(name):
    return json.loads((TR / f"{name}.final.json").read_text())


def ckpt_files():
    return [TR / "rep0.final.json", TR / "rep1.final.json"]


def freeze():
    files = {str(f.relative_to(ROOT)): sha(f) for f in ckpt_files()}
    code = {f: sha(ROOT / f) for f in ("src/nexus/de_phase10b/search10b.py", "src/nexus/de_phase10b/lineage10b.py", "src/nexus/de_phase10b/fixes10b.py",
                                       "src/nexus/de_phase10/guide10.py", "src/nexus/de_phase10/procedure10.py", "scripts/agi10b_eval.py")}
    man = MB.eval_manifest()
    conf = B9.confirm_manifest()
    gate = json.loads((ROOT / "artifacts/agi10b_dev/gate6.json").read_text()) if (ROOT / "artifacts/agi10b_dev/gate6.json").exists() else None
    (ROOT / "artifacts/agi10b_freeze.json").write_text(json.dumps(dict(files=files, code=code, manifest=man, confirm_manifest=conf, gate6_passed=bool(gate and gate["passed"]),
                                                                        N3={r: ck(r)["n"] for r in ("rep0", "rep1")}), indent=1))
    print("frozen", files, "gate6", bool(gate and gate["passed"]))


def compose(mem, library=True, guide="bridge", trust=True, hyps=3):
    m = copy.deepcopy(mem)
    if not library:
        m["de"]["skills"] = {}
        hyps = 0
    if not trust:
        m["trust"] = dict(records=[], weights={}, support={})
    g = mem.get("guide")
    if guide == "fixed" or not g:
        m["guide"] = dict(kind="fixed")
    elif guide == "bridge":
        m["guide"] = dict(g, bridge=True, ratio=4 / 7)
        m["de"]["w"] = {}
    elif guide == "nobridge":
        m["guide"] = dict(g, bridge=False, ratio=0.7)
        m["de"]["w"] = {}
    if hyps and m.get("pstar"):
        m = PR10.with_hypotheses(m, MEM.strong(m["P"], n=hyps))
    m["pairs"] = []
    return m


def arms(kind="eval"):
    A = {"A1": dict(mem=compose(LN.empty_memory(), library=False, guide="fixed", trust=False), prog=PR10.F0)}
    for r in ("rep0", "rep1"):
        m = ck(r)["memory"]
        if kind == "confirm":
            A[f"Full_{r}"] = dict(mem=compose(m), prog=PR10.F0)
            A[f"TrustOnly_{r}"] = dict(mem=compose(m, library=False, guide="fixed"), prog=PR10.F0)
            continue
        A[f"Full_{r}"] = dict(mem=compose(m), prog=PR10.F0)
        A[f"noLib_{r}"] = dict(mem=compose(m, library=False), prog=PR10.F0)
        A[f"noBridge_{r}"] = dict(mem=compose(m, guide="nobridge"), prog=PR10.F0)
        A[f"noRanker_{r}"] = dict(mem=compose(m, guide="fixed"), prog=PR10.F0)
        A[f"noTrust_{r}"] = dict(mem=compose(m, trust=False), prog=PR10.F0)
    return A


def claim_once(key):
    lock = ROOT / "var/agi10b_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10b-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10b-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(chunk, n, kind="eval"):
    chunk, n = int(chunk), int(n)
    fz = json.loads((ROOT / "artifacts/agi10b_freeze.json").read_text())
    for f, h in fz["files"].items():
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if kind == "confirm":
        g = json.loads((ROOT / "artifacts/agi10b_dev/gate6.json").read_text())
        if not (g["passed"] and fz["gate6_passed"]):
            raise SystemExit("gate 6 has not passed: the one-use confirmation set stays unopened")
    claim_once(("agi9de", "confirm") if kind == "confirm" else ("agi10bde", "eval"))
    D.mkdir(parents=True, exist_ok=True)
    A = arms(kind)
    names = sorted(A)
    W.SparkCode.warm()
    live = PR10.Live(LN.W_SRC, LN.WALL)
    out = D / (f"confirm_c{chunk}.jsonl" if kind == "confirm" else f"rows_c{chunk}.jsonl")
    done = {(x["arm"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        man = [dict(c["spec"], seed=c["seed"], group=c["stratum"], mc=c["stratum"] == "conflict", tier=0) for c in B9.confirm_manifest()] if kind == "confirm" else MB.eval_manifest()
        for t in man[chunk::n]:
            try:
                p = LN.build(t, t["seed"], ROOT / "var/agi10b_ws" / kind, require=True if t.get("require_fault") else None if t["group"] == "heldout_mutation" else None)
            except RuntimeError as e:
                fh.write(json.dumps(dict(seed=t["seed"], arm="-", error=str(e)[:100])) + "\n")
                fh.flush()
                continue
            k0 = (t["seed"] * 7) % len(names)
            for name in names[k0:] + names[:k0]:
                if (name, t["seed"]) in done:
                    continue
                a = A[name]
                t0 = time.time()
                st = PR10.investigate(p, live, copy.deepcopy(a["mem"]), a["prog"], {})
                o = PR10.outcome(p, st)
                cand = st.cand or {}
                pts = [d for d in st.dps if d.get("kind") != "absent"]
                row = dict(seed=t["seed"], pid=p["pid"], arm=name, group=t["group"], mc_built=t["mc"], tier=t["tier"], paradigm=p["paradigm"], faults=p["faults"],
                           undecided=bool(p["undecided"]), decision=o["decision"], verified=o["verified"], wrong=o["wrong"], reason=st.decision.get("reason"),
                           reachable=bool(st.has_candidate), K=sum(1 for d in pts if len({c["effect_at_boundary"] for c in d.get("claims") or []}) > 1 or not d.get("claims")),
                           questions=st.cost["questions"], cost=st.cost, cost_s=round(PR10.cost_s(st.cost), 4), via_skill=bool(cand.get("via_skill")),
                           method_queue=cand.get("method_queue"), trust_used=any((d["via"] or "").startswith("trust") for d in st.dps),
                           legacy_conflicts=sum(bool(d.get("legacy_conflict")) for d in st.dps), obligations=st.obligation_status, row_wall=round(time.time() - t0, 3))
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
            print(p["pid"], len(A), "arms", flush=True)


def score(kind="eval"):
    rows = [json.loads(l) for f in sorted(D.glob(("confirm" if kind == "confirm" else "rows") + "_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r.get("arm") != "-"]
    by = {}
    for r in ok:
        by.setdefault(r["arm"], {})[r["seed"]] = r
    seeds = sorted({r["seed"] for r in ok})
    res = dict(n_rows=len(ok), n_targets=len(seeds), build_failures=[r for r in rows if r.get("arm") == "-"], arms={})
    for a, v in sorted(by.items()):
        vv = list(v.values())
        g = lambda f: f"{sum(x['verified'] for x in vv if f(x))}/{sum(1 for x in vv if f(x))}"  # noqa: E731
        res["arms"][a] = dict(n=len(vv), verified=sum(x["verified"] for x in vv), wrong=sum(x["wrong"] for x in vv), seen=g(lambda x: x["group"] == "seen"),
                              heldout_tier3=g(lambda x: x["group"] == "heldout"), heldout_mutation=g(lambda x: x["group"] == "heldout_mutation"),
                              multi_conflict=g(lambda x: x["K"] >= 2), reachable=g(lambda x: x["reachable"]), no_candidate=sum(x["reason"] == "no repair candidate" for x in vv),
                              questions=sum(x["questions"] for x in vv), via_skill_verified=sum(x["via_skill"] and x["verified"] for x in vv), cost_s=round(sum(x["cost_s"] for x in vv), 2))
    V = lambda a: {s for s, r in by.get(a, {}).items() if r["verified"]}  # noqa: E731
    def diff(a, b):
        if a not in by or b not in by:
            return None
        d = [float(by[a][s]["verified"]) - float(by[b][s]["verified"]) for s in seeds if s in by[a] and s in by[b]]
        rng = random.Random(f"agi10|{a}|{b}")
        obs = abs(sum(d))
        p = (sum(abs(sum(x if rng.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(20000)) + 1) / 20001 if any(d) else 1.0
        return dict(n=len(d), mean_pp=round(100 * sum(d) / len(d), 1), gained=sorted(V(a) - V(b)), lost=sorted(V(b) - V(a)), p_signflip=round(p, 4))
    res["contrasts"] = {}
    for r in ("rep0", "rep1"):
        for name, x, y in (("Full - A1", f"Full_{r}", "A1"), ("L* (Full - noLib)", f"Full_{r}", f"noLib_{r}"), ("bridge (Full - noBridge)", f"Full_{r}", f"noBridge_{r}"),
                           ("ranker+bridge (Full - noRanker)", f"Full_{r}", f"noRanker_{r}"), ("trust (Full - noTrust)", f"Full_{r}", f"noTrust_{r}"),
                           ("Full - TrustOnly", f"Full_{r}", f"TrustOnly_{r}"), ("TrustOnly - A1", f"TrustOnly_{r}", "A1")):
            res["contrasts"][f"{name} [{r}]"] = diff(x, y)
    rep = {}
    for name in ("Full", "noLib", "noBridge", "noRanker", "noTrust", "TrustOnly"):
        v = [res["arms"][f"{name}_{r}"]["verified"] for r in ("rep0", "rep1") if f"{name}_{r}" in res["arms"]]
        if v:
            rep[name] = dict(per_rep=v, mean=sum(v) / len(v), range=[min(v), max(v)])
    res["replication"] = rep
    starved = {s for s, r in by.get("A1", {}).items() if r["reason"] == "no repair candidate"}
    res["rescued_candidate_starved"] = {a: sorted(s for s in starved if by[a].get(s, {}).get("verified") or by[a].get(s, {}).get("reachable")) for a in by}
    res["wrong_total"] = sum(v["wrong"] for v in res["arms"].values())
    (D / ("confirm_result.json" if kind == "confirm" else "result.json")).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("n_rows", "n_targets", "contrasts", "replication", "wrong_total")}, default=str)[:4000])
    print({a: (v["verified"], v["wrong"], v["seen"], v["heldout_tier3"], v["multi_conflict"]) for a, v in res["arms"].items()})


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "run":
        run(*sys.argv[2:])
    elif c == "confirm":
        run(*sys.argv[2:], kind="confirm")
    elif c == "score":
        score(*sys.argv[2:])
    else:
        freeze()
