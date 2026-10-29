"""Phase 8 frozen evaluation (NOT LOCKED; ONE-USE agi8de/target claimed once under an fcntl lock).
  python scripts/agi8_eval.py freeze_source            sha256 of the four Stage 2 checkpoints -> artifacts/agi8_freeze_source.json
  python scripts/agi8_eval.py run CHUNK N [--dev]      targets[CHUNK::N], all nine endpoints per target -> artifacts/agi8_eval/targets_cCHUNK.jsonl
  python scripts/agi8_eval.py score [--dev]            -> artifacts/agi8_eval/result.json
Endpoints (same acceptance barrier, evidence access, one-clarification limit, per-task work budget W_EVAL / wall cap and
engines for all):
  A0         fresh memory + F0 + fixed archive rule
  A1_r{0,1}  FixedLearner_r memory + F0 + fixed archive rule
  A2_r{0,1}  Full_r memory + its LEARNED executable procedure + fixed archive rule
  A3_r{0,1}  the same Full_r memory + F0 + fixed archive rule
  A4_r{0,1}  as A3 with the invented task methods removed (their method-queue slice returns to base search; trust and
             evidence retained)
Memories are frozen: deep-copied per row, never updated, no target answer reaches another target. The arm order is
rotated per target (counterbalancing). A row is written as soon as it is complete; a restarted chunk skips written rows
and never reruns a completed outcome. Identical search inputs (same project, same search-relevant memory digest, same
configuration) reuse the executed search within a chunk (disclosed, `shared`)."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase7 import world7 as W7  # noqa: E402
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR7, seeds8 as S  # noqa: E402
R = S.R
W_EVAL, WALL_CAP = 3000, 6.0
REPS = (0, 1)
SRC = [f"artifacts/agi8_src/{c}_r{r}.json" for c in ("Full", "FixedLearner") for r in REPS]


def sha(f):
    return hashlib.sha256((ROOT / f).read_bytes()).hexdigest()


def freeze_source():
    (ROOT / "artifacts/agi8_freeze_source.json").write_text(json.dumps(dict(files={f: sha(f) for f in SRC}), indent=1))
    print("frozen", {f: sha(f)[:12] for f in SRC})


def paths(dev):
    return ROOT / ("artifacts/agi8_dev/eval" if dev else "artifacts/agi8_eval")


def _strip(mem, skills=True):
    m = copy.deepcopy(mem)
    m.pop("policy_w", None)                               # archive rule frozen in Phase 8
    if not skills:
        m["de"]["skills"] = {}
    return m


def arms(dev):
    A = {"A0": dict(mem=L8.empty_memory(), prog=PR7.F0, lib={})}
    d = ROOT / ("artifacts/agi8_dev/src" if dev else "artifacts/agi8_src")
    for r in REPS:
        fp, xp = d / f"Full_r{r}.json", d / f"FixedLearner_r{r}.json"
        if xp.exists():
            x = json.loads(xp.read_text())
            A[f"A1_r{r}"] = dict(mem=_strip(x["memory"]), prog=PR7.F0, lib={})
        if fp.exists():
            f = json.loads(fp.read_text())
            A[f"A2_r{r}"] = dict(mem=_strip(f["memory"]), prog=f["procedure"], lib=f["library"])
            A[f"A3_r{r}"] = dict(mem=_strip(f["memory"]), prog=PR7.F0, lib={})
            A[f"A4_r{r}"] = dict(mem=_strip(f["memory"], skills=False), prog=PR7.F0, lib={})
    for a in A.values():
        a["mem"].setdefault("M", copy.deepcopy(L8.M0))
    return A


def manifest(dev):
    if not dev:
        return S.target_manifest()
    T = []
    base = S.RANGES[("agi8de", "dev")].start + 1500
    for i, t in enumerate(S.target_manifest()[::12]):        # development rehearsal: dev seeds, Tier 1-2 only
        if t["tier"] < 3:
            T.append(dict(t, seed=base + i))
    return T


def claim_once(key):
    lock = ROOT / "var/agi8_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi8-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi8-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(chunk, n, *flags):
    dev = "--dev" in flags
    chunk, n = int(chunk), int(n)
    D = paths(dev)
    if not dev:
        for f, h in json.loads((ROOT / "artifacts/agi8_freeze_source.json").read_text())["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
        claim_once(("agi8de", "target"))
    D.mkdir(parents=True, exist_ok=True)
    A = arms(dev)
    names = sorted(A)
    W.SparkCode.warm()
    live = PR7.Live(W_EVAL, wall_cap=WALL_CAP)
    out = D / f"targets_c{chunk}.jsonl"
    done = {(x["arm"], x["pid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for i, t in enumerate(manifest(dev)[chunk::n]):
            spec = {k: v for k, v in t.items() if k not in ("seed", "tier", "family", "answerable") and v is not None}
            try:
                p = W7.make_project7(spec, t["seed"], ROOT / "var/agi8_ws" / ("dev_eval" if dev else "eval"))
            except RuntimeError as e:
                fh.write(json.dumps(dict(pid=f"build_failed:{t['seed']}", arm="-", error=str(e)[:100])) + "\n")
                continue
            k0 = (t["seed"] * 7) % len(names)
            for name in names[k0:] + names[:k0]:                   # rotated arm order
                if (name, p["pid"]) in done:
                    continue
                a = A[name]
                t0 = time.time()
                st = PR7.investigate(p, live, copy.deepcopy(a["mem"]), a["prog"], a["lib"])
                o = PR7.outcome(p, st)
                cand = st.cand or {}
                srch = next((x["obs"] for x in st.trace if x["action"] == "search"), {})
                row = dict(pid=p["pid"], seed=t["seed"], family=t["family"], answerable=t["answerable"], arm=name, tier=p["tier"], paradigm=p["paradigm"], hybrid=p.get("hybrid"), n_stages=len(p["stages"]),
                           engines=[s_["engine"] for s_ in p["stages"]], langs=[s_["legacy_lang"] for s_ in p["stages"]], dps=p["dps"],
                           legacy_flip=p.get("legacy_flip"), undecided=bool(p["undecided"]), decision=o["decision"], verified=o["verified"], wrong=o["wrong"],
                           justified_abstention=o["decision"] == "abstain" and bool(p["undecided"]), reason=st.decision.get("reason"),
                           questions=st.cost["questions"], answers=[x["obs"]["answer"] for x in st.trace if x["action"] == "ask"],
                           cost=st.cost, cost_s=round(PR7.cost_s(st.cost), 4), barrier=st.barrier,
                           coverage_by_procedure=st.coverage_checked and not st.barrier["computed"], obligations=st.obligation_status,
                           method_queue=cand.get("method_queue"), reads=st.cost["reads"],
                           search=dict(mode=srch.get("mode"), skills=srch.get("skills"), outcome=srch.get("outcome"), shared=srch.get("shared")),
                           skill_bound=len(cand.get("skill_trace") or []), via_skill=bool(cand.get("via_skill")), solution_kinds=cand.get("solution_kinds"),
                           resolutions=[dict(stage=d["stage"], pos=str(d["pos"])[:40], via=d["via"], conflict=d["conflict"],
                                                                        undecided=d["undecided"]) for d in st.dps],
                           hidden=o.get("hidden"), trace=[dict(action=x["action"], decision=x["decision"]) for x in st.trace], row_wall=round(time.time() - t0, 3))
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
            print(p["pid"], len(A), "arms", flush=True)


# ------------------------------------------------------------------ scoring
def _rows(dev):
    return [json.loads(l) for p in sorted(paths(dev).glob("targets_c*.jsonl")) for l in p.read_text().splitlines() if l.strip()]


def signflip(d, key, n=20000):
    obs = abs(sum(d))
    rng = random.Random(f"agi8|{key}")
    return (sum(abs(sum(x if rng.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(n)) + 1) / (n + 1)


def score(*flags):
    dev = "--dev" in flags
    D = paths(dev)
    allrows = _rows(dev)
    rows = [r for r in allrows if r.get("arm") != "-"]
    by = {}
    for r in rows:
        by.setdefault(r["arm"], {})[r["pid"]] = r
    pids = sorted({r["pid"] for r in rows})
    tier = {r["pid"]: r["tier"] for r in rows}
    res = dict(n_rows=len(rows), n_targets=len(pids), build_failures=[r for r in allrows if r.get("arm") == "-"], arms={})
    for a, rs in sorted(by.items()):
        v = list(rs.values())
        res["arms"][a] = dict(n=len(v), verified=sum(x["verified"] for x in v), wrong=sum(x["wrong"] for x in v),
                              wrong_projects=sorted(x["pid"] for x in v if x["wrong"]),
                              justified_abstentions=sum(x["justified_abstention"] for x in v), undecided=sum(x["undecided"] for x in v),
                              questions=sum(x["questions"] for x in v), barrier_abstentions=sum("barrier" in (x["reason"] or "") for x in v),
                              no_candidate=sum(x["reason"] == "no repair candidate" for x in v),
                              by_tier={t: f"{sum(x['verified'] for x in v if x['tier'] == t)}/{sum(x['tier'] == t for x in v)}" for t in (1, 2, 3)},
                              skill_bound_rows=sum(x["skill_bound"] > 0 for x in v), via_skill_verified=sum(x["via_skill"] and x["verified"] for x in v),
                              coverage_by_procedure=sum(x["coverage_by_procedure"] for x in v),
                              obligation_status=dict(__import__("collections").Counter(o["status"] for x in v for o in x["obligations"])),
                              absent_obligation_rows=sum(any(o["kind"] == "absent" for o in x["obligations"]) for x in v),
                              method_queue_accepted=sum(bool((x["method_queue"] or {}).get("accepted")) for x in v),
                              work=sum(x["cost"]["work"] for x in v), cost_s=round(sum(x["cost_s"] for x in v), 2))

    def val(arm, pid):
        if arm in ("A1", "A2", "A3", "A4"):
            vals = [by[f"{arm}_r{r}"][pid]["verified"] for r in REPS if pid in by.get(f"{arm}_r{r}", {})]
            return sum(vals) / len(vals) if len(vals) == len(REPS) else None     # complete repetitions only
        return by.get(arm, {}).get(pid, {}).get("verified")
    contr = {}
    for name, a, b, filt in (("A2 - A0 (all)", "A2", "A0", lambda t: True), ("A2 - A1 (all)", "A2", "A1", lambda t: True),
                             ("A2 - A0 (Tier 3)", "A2", "A0", lambda t: t == 3), ("A2 - A1 (Tier 3)", "A2", "A1", lambda t: t == 3),
                             ("A3 - A1 (memory from Full's training process)", "A3", "A1", lambda t: True),
                             ("A2 - A3 (target-time effect of the learned procedure)", "A2", "A3", lambda t: True),
                             ("A3 - A4 (skill library)", "A3", "A4", lambda t: True),
                             ("A1 - A0 (experience, fixed learner)", "A1", "A0", lambda t: True)):
        d, miss = [], 0
        for pid in pids:
            if not filt(tier[pid]):
                continue
            x, y = val(a, pid), val(b, pid)
            if x is None or y is None:
                miss += 1
                continue
            d.append(float(x) - float(y))
        contr[name] = dict(n=len(d), missing=miss, mean_pp=round(100 * sum(d) / len(d), 1) if d else None,
                           p_signflip=round(signflip(d, name), 4) if d and any(d) else 1.0)
        for r in REPS:
            dr = [float(by[f"{a}_r{r}" if a != "A0" else a][p]["verified"]) - float(by[f"{b}_r{r}" if b != "A0" else b][p]["verified"])
                  for p in pids if filt(tier[p]) and p in by.get(f"{a}_r{r}" if a != "A0" else a, {}) and p in by.get(f"{b}_r{r}" if b != "A0" else b, {})]
            contr[name][f"r{r}_mean_pp"] = round(100 * sum(dr) / len(dr), 1) if dr else None
    prim = ["A2 - A0 (all)", "A2 - A1 (all)"]
    ps = sorted((contr[k]["p_signflip"], k) for k in prim)
    for i, (p, k) in enumerate(ps):
        contr[k]["p_holm"] = round(min(1.0, max((len(ps) - j) * ps[j][0] for j in range(i + 1))), 4)
    res["contrasts"] = contr
    for k in prim:
        contr[k]["consistent_direction_both_reps"] = all((contr[k][f"r{r}_mean_pp"] or 0) > 0 for r in REPS)
    fam = {}
    for pid in pids:
        f_ = by["A0"][pid]["family"]
        for a, b in (("A2", "A0"), ("A2", "A1")):
            x, y = val(a, pid), val(b, pid)
            if x is not None and y is not None:
                fam.setdefault(f_, {}).setdefault(f"{a}-{b}", []).append(float(x) - float(y))
    res["family_sensitivity_pp"] = {f_: {k: round(100 * sum(v) / len(v), 1) for k, v in d.items()} for f_, d in sorted(fam.items())}
    res["per_target"] = {pid: {a: val(a, pid) for a in ("A0", "A1", "A2", "A3", "A4")} for pid in pids}
    cost = {}
    for r in REPS:
        F, Z = by.get(f"A2_r{r}", {}), by.get(f"A1_r{r}", {})
        both = [p for p in F if p in Z and F[p]["verified"] and Z[p]["verified"]]
        cost[f"r{r}"] = dict(shared_solves=len(both), cost_s=[round(sum(F[p]["cost_s"] for p in both), 3), round(sum(Z[p]["cost_s"] for p in both), 3)],
                             same_correct_set=sorted(p for p in F if F[p]["verified"]) == sorted(p for p in Z if Z[p]["verified"]))
    res["cost_A2_vs_A1_on_shared_solves"] = cost
    res["wrong_total_all_arms"] = sum(v["wrong"] for v in res["arms"].values())
    res["wrong_distinct_projects"] = sorted({p for v in res["arms"].values() for p in v["wrong_projects"]})
    (D / "result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("n_rows", "n_targets", "contrasts", "cost_A2_vs_A1_on_shared_solves", "wrong_total_all_arms",
                                          "wrong_distinct_projects")}, indent=0)[:4000])
    print({a: (v["verified"], v["wrong"], v["by_tier"]) for a, v in res["arms"].items()})


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "run":
        run(*sys.argv[2:])
    elif c == "score":
        score(*sys.argv[2:])
    else:
        {"freeze_source": freeze_source}[c]()
