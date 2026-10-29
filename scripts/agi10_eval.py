"""Phase 10 Stage 4 frozen evaluation (NOT LOCKED; ONE-USE agi10de/eval, 48 targets, claimed once under an fcntl lock).
  python scripts/agi10_eval.py freeze                 sha256 of every checkpoint used -> artifacts/agi10_freeze.json
  python scripts/agi10_eval.py run CHUNK N            targets[CHUNK::N] x all arms -> artifacts/agi10_eval/rows_cCHUNK.jsonl
  python scripts/agi10_eval.py score                  -> artifacts/agi10_eval/result.json
PRE-REGISTERED ARMS (624 rows; the procedure is F0 and the learner M is fixed for the factorial rows):
  A1@N0                 fresh: no library, fixed guide, no trust (baseline)
  factorial @N3 (main, or C3 when main adopted M*): trust REMOVED in all six cells (pure search-side attribution)
    A2 L0 + G_count     A3 L0 + G_learned     B1 L0+L* + G_fixed     B2 L0+L* + G_count     B3 L0+L* + G_learned
  learning curve        B3 @N1, @N2 (and @N3 above)
  self-evolving         C1 @N1 / N2 / N3: full main memory (trust, w, L*, G_learned) + the strongest P* hypotheses in the
                        method queue + the evolved procedure pi*
                        C2 @N3: the P*-discarded lineage, same composition;  C3 @N3: the M0-locked lineage (== C1 when main
                        adopted no M*; then reported as identical by construction, not rerun)
Memories are frozen and deep-copied per row; arm order rotated per target; rows appended + flushed; a restarted chunk
resumes after the written rows and never reruns one."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, memory10 as MEM, procedure10 as PR10  # noqa: E402
TR = ROOT / "artifacts/agi10_train"
D = ROOT / "artifacts/agi10_eval"


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def ck(name, N):
    return json.loads((TR / f"{name}.N{N}.json").read_text())


def m_adopted():
    p = TR / "main.m.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return bool(rows and rows[-1].get("adopted"))


def ckpt_files():
    fs = [TR / f"main.N{n}.json" for n in MF.CHECKPOINTS] + [TR / "C2.N120.json"]
    if m_adopted():
        fs.append(TR / "C3.N120.json")
    return fs


def freeze():
    files = {str(f.relative_to(ROOT)): sha(f) for f in ckpt_files()}
    code = {f: sha(ROOT / f) for f in ("src/nexus/de_phase10/guide10.py", "src/nexus/de_phase10/lineage10.py", "src/nexus/de_phase10/procedure10.py",
                                       "src/nexus/de_phase10/memory10.py", "src/nexus/de_phase10/manifest10.py", "scripts/agi10_eval.py")}
    man = MF.eval_manifest()
    (ROOT / "artifacts/agi10_freeze.json").write_text(json.dumps(dict(files=files, code=code, manifest=man, manifest_sha=hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest(),
                                                                       m_adopted=m_adopted()), indent=1))
    print("frozen", len(files), "checkpoints; M* adopted:", m_adopted())


def compose(mem, library=True, guide="fixed", trust=True, count=True, hyps=0):
    m = copy.deepcopy(mem)
    if not library:
        m["de"]["skills"] = {}
    if not count:
        m["de"]["w"] = {}
    if not trust:
        m["trust"] = dict(records=[], weights={}, support={})
    if guide == "fixed":
        m["guide"] = dict(kind="fixed")
    elif guide == "count":
        m["guide"] = None
    elif guide == "learned":
        m["guide"] = mem.get("guide") or dict(kind="fixed")
        m["de"]["w"] = {}
    if hyps and m.get("pstar"):
        m = PR10.with_hypotheses(m, MEM.strong(m["P"], n=hyps))
    m["pairs"] = []
    return m


def arms():
    A = {"A1@N0": dict(mem=compose(LN.empty_memory(), library=False, guide="fixed", trust=False), prog=PR10.F0)}
    fact = ck("C3" if m_adopted() else "main", 120)["memory"]
    A["A2@N3"] = dict(mem=compose(fact, library=False, guide="count", trust=False), prog=PR10.F0)
    A["A3@N3"] = dict(mem=compose(fact, library=False, guide="learned", trust=False), prog=PR10.F0)
    A["B1@N3"] = dict(mem=compose(fact, library=True, guide="fixed", trust=False), prog=PR10.F0)
    A["B2@N3"] = dict(mem=compose(fact, library=True, guide="count", trust=False), prog=PR10.F0)
    A["B3@N3"] = dict(mem=compose(fact, library=True, guide="learned", trust=False), prog=PR10.F0)
    for n in MF.CHECKPOINTS[:2]:
        A[f"B3@N{n}"] = dict(mem=compose(ck("C3" if m_adopted() else "main", n)["memory"] if not m_adopted() or n != 25 else ck("main", n)["memory"],
                                         library=True, guide="learned", trust=False), prog=PR10.F0)
    for n in MF.CHECKPOINTS:
        c = ck("main", n)
        A[f"C1@N{n}"] = dict(mem=compose(c["memory"], library=True, guide="learned", trust=True, hyps=3), prog=c["procedure"])
    c2 = ck("C2", 120)
    A["C2@N3"] = dict(mem=compose(c2["memory"], library=True, guide="learned", trust=True, hyps=3), prog=c2["procedure"])
    if m_adopted():
        c3 = ck("C3", 120)
        A["C3@N3"] = dict(mem=compose(c3["memory"], library=True, guide="learned", trust=True, hyps=3), prog=c3["procedure"])
    return A


def claim_once(key):
    lock = ROOT / "var/agi10_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(chunk, n):
    chunk, n = int(chunk), int(n)
    fz = json.loads((ROOT / "artifacts/agi10_freeze.json").read_text())
    for f, h in fz["files"].items():
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    claim_once(("agi10de", "eval"))
    D.mkdir(parents=True, exist_ok=True)
    A = arms()
    names = sorted(A)
    W.SparkCode.warm()
    live = PR10.Live(LN.W_SRC, LN.WALL)
    out = D / f"rows_c{chunk}.jsonl"
    done = {(x["arm"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in MF.eval_manifest()[chunk::n]:
            try:
                p = LN.build(t, t["seed"], ROOT / "var/agi10_ws/eval", require=True if t.get("require_fault") else False if t["group"] != "heldout_mutation" else None)
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


def score():
    rows = [json.loads(l) for f in sorted(D.glob("rows_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
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
    res["factorial"] = {k: diff(a, b) for k, a, b in (("L* (B1-A1)", "B1@N3", "A1@N0"), ("G_count (A2-A1)", "A2@N3", "A1@N0"), ("G_learned (A3-A1)", "A3@N3", "A1@N0"),
                                                       ("L* | G_count (B2-A2)", "B2@N3", "A2@N3"), ("L* | G_learned (B3-A3)", "B3@N3", "A3@N3"),
                                                       ("G_learned vs G_count | L* (B3-B2)", "B3@N3", "B2@N3"), ("full wake-sleep (B3-A1)", "B3@N3", "A1@N0"))}
    res["self_evolution"] = {k: diff(a, b) for k, a, b in (("C1 - B3 (trust + P* + pi*)", "C1@N120", "B3@N3"), ("C1 - C2 (P*)", "C1@N120", "C2@N3"),
                                                            ("C1 - C3 (M*)", "C1@N120", "C3@N3"), ("C1 - A1", "C1@N120", "A1@N0"))}
    curve = {}
    for fam in ("B3", "C1"):
        pts = [("N0", "A1@N0")] + [(f"N{n}", f"{fam}@N{n}" if fam == "C1" else (f"B3@N{n}" if n != 120 else "B3@N3")) for n in MF.CHECKPOINTS]
        curve[fam] = [dict(N=n, arm=a, verified=res["arms"].get(a, {}).get("verified"), seen=res["arms"].get(a, {}).get("seen"),
                           heldout=res["arms"].get(a, {}).get("heldout_tier3")) for n, a in pts]
        forget = []
        for (n1, a1), (n2, a2) in zip(pts[1:], pts[2:]):
            if a1 in by and a2 in by:
                forget.append(dict(between=[n1, n2], lost=sorted(V(a1) - V(a2)), gained=sorted(V(a2) - V(a1))))
        curve[fam + "_forgetting"] = forget
    res["learning_curve"] = curve
    starved = {s for s, r in by.get("A1@N0", {}).items() if r["reason"] == "no repair candidate"}
    res["rescued_candidate_starved"] = {a: sorted(s for s in starved if by[a].get(s, {}).get("verified") or by[a].get(s, {}).get("reachable")) for a in by}
    res["wrong_total"] = sum(v["wrong"] for v in res["arms"].values())
    (D / "result.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("n_rows", "n_targets", "factorial", "self_evolution", "wrong_total")}, default=str)[:3500])
    print({a: (v["verified"], v["wrong"], v["seen"], v["heldout_tier3"], v["multi_conflict"]) for a, v in res["arms"].items()})


if __name__ == "__main__":
    c = sys.argv[1]
    {"freeze": freeze, "score": score}.get(c, lambda: run(*sys.argv[2:]))() if c != "run" else run(*sys.argv[2:])
