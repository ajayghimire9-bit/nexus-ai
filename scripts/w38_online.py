"""Wave 38 experiments 4 (empty-library meta-learning), 5 (repeatable self-evolution, >= 5 lineages per method), 6 (continual
adaptation / forgetting) for program streams, plus online planning and repair learners (NOT LOCKED).
All streams start from an EMPTY library; all costs are on the OS meter; every attempt is recorded."""
import argparse, json, math, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FAST = ("strings", "graphs")


def program_stream(seed, domains, which="all", rep=3, mechs=None):
    from nexus import w38_domains as D
    r = random.Random(f"w38-stream:{seed}")
    tasks = []
    for (d, m), (_v, _p, src) in D.MECH.items():
        if d not in domains or (which == "source" and not src) or (which == "withheld" and src) or (mechs and m not in mechs):
            continue
        for _ in range(rep):
            t = D.make_task(d, m, r)
            if t:
                tasks.append(t)
    r.shuffle(tasks)
    return tasks


def stream_cost(ev, tasks, genome, tag):
    rows, learn, declared = ev.stream(tasks, genome, tag)
    return dict(work=sum(r["work"] for r in rows) + learn, learn=learn, n=len(rows), correct=sum(r["correct"] for r in rows),
                wrong=sum(r["wrong"] for r in rows), abstain=sum(r["label"] == "ABSTAIN" for r in rows),
                flags=sum(sum(r["flags"].values()) for r in rows), declared=declared,
                curve=[r["work"] for r in rows])


def mutate(g, rng):
    from nexus import w38_online as O
    g = dict(g)
    for k in rng.sample(sorted(O.GENES), rng.choice((1, 2))):
        g[k] = rng.choice([v for v in O.GENES[k] if v != g[k]])
    return O.validate(g)


def rand_genome(rng):
    from nexus import w38_online as O
    return {k: rng.choice(v) for k, v in O.GENES.items()}


def evolve(ev, method, lineage, fit_streams, base_cost, budget, search):
    """Multi-fidelity: every candidate is scored on the first fitness stream; the best 2 so far are re-scored on all."""
    from nexus import w38_online as O
    rng = random.Random(f"w38-evo:{method}:{lineage}")
    def score(g, full):
        ss = fit_streams if full else fit_streams[:1]
        rs = []
        for k, ts in enumerate(ss):
            c = stream_cost(ev, ts, g, f"evo:{k}")          # Stage 3 fix: probe seeds depend on the stream only
            search["instr"] += c["work"]
            rs.append(c["work"] / base_cost[k] if c["wrong"] == 0 else 9.9)
        return sum(rs) / len(rs)
    arch = [dict(g=dict(O.BASELINE_80F9CC2), s=score(O.BASELINE_80F9CC2, False), kids=0)]
    while len(arch) < budget:
        if method == "random":
            g = rand_genome(rng)
        elif method == "incumbent":
            best = min(arch, key=lambda e: e["s"]); best["kids"] += 1; g = mutate(best["g"], rng)
        else:
            ranked = sorted(arch, key=lambda e: e["s"])
            w = [1 / (1 + math.exp(10 * (i / max(1, len(ranked) - 1) - 0.5))) / (1 + e["kids"]) for i, e in enumerate(ranked)]
            par = rng.choices(ranked, weights=w)[0]; par["kids"] += 1; g = mutate(par["g"], rng)
        arch.append(dict(g=g, s=score(g, False), kids=0))
    top = sorted(arch, key=lambda e: e["s"])[:2]
    for e in top:
        e["full"] = score(e["g"], True)
    best = min(top, key=lambda e: e["full"])
    return dict(best=best["g"], full=best["full"], evals=len(arch), curve=[e["s"] for e in arch])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--exp", required=True); ap.add_argument("--split", default="dev")
    ap.add_argument("--out", required=True); ap.add_argument("--lineages", type=int, default=5); ap.add_argument("--budget", type=int, default=6)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import w38_eval as WE, w38_online as O
    if a.split == "dev":
        R.claim("wave38", "dev", list(R.REGISTRY[("wave38", "dev")]), run_id="w38-online-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == f"w38-{a.split}" for r in spent):
            R.claim("wave38", a.split, list(R.REGISTRY[("wave38", a.split)]), run_id=f"w38-{a.split}")
    ev = WE.Eval(); t0 = time.perf_counter()
    p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    if a.exp in ("meta_confirm", "continual_confirm", "evo_confirm"):
        seeds = list(R.REGISTRY[("wave38", a.split)])
        for sd in seeds:
            key = str(sd)
            if key in res:
                continue
            if a.exp == "meta_confirm":
                best = json.loads((ROOT / "artifacts/w38_online_dev_meta.json").read_text())["selection"]["best"]
                ts = program_stream(f"metac:{sd}", ("tables",), "all", 1)
                res[key] = {n: stream_cost(ev, ts, g, f"metac:{sd}") for n, g in
                            (("Fresh", None), ("Baseline-80f9cc2", O.BASELINE_80F9CC2), ("Meta-learned", best))}
            elif a.exp == "continual_confirm":
                phases = [("strings", "a"), ("graphs", "b"), ("strings", "c"), ("tables", "d")]
                ts, phase_of = [], []
                for i, (dom, sub) in enumerate(phases):
                    seg = program_stream(f"contc:{sd}:{sub}", (dom,), "source", 2)
                    ts += seg; phase_of += [i] * len(seg)
                res[key] = {"phase_of": phase_of}
                for n, g in (("Fresh", None), ("Learner-no-gate", O.BASELINE_80F9CC2),
                             ("Learner-regime-memory", dict(O.BASELINE_80F9CC2, gate="regime"))):
                    c = stream_cost(ev, ts, g, f"contc:{sd}")
                    c["phase_work"] = [sum(w for w, ph in zip(c["curve"], phase_of) if ph == i) for i in range(len(phases))]
                    res[key][n] = c
            elif a.exp == "evo_confirm":
                evo = json.loads((ROOT / "artifacts/w38_evolve_final.json").read_text())
                ts = program_stream(f"evoc:{sd}", FAST, "all", 1)
                arms = {"Fresh": None, "Start-80f9cc2": O.BASELINE_80F9CC2}
                arms.update({k: v["best"] for k, v in evo.items() if ":" in k})
                res[key] = {n: stream_cost(ev, ts, g, f"evoc:{sd}") for n, g in arms.items()}
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
            print(a.exp, sd, {n: (round(v["work"] / 1e9, 1), v["correct"], v["n"], v["wrong"]) for n, v in res[key].items()
                              if isinstance(v, dict) and "work" in v}, flush=True)
            if time.perf_counter() - t0 > 700:
                break
    if a.exp == "evolve":
        fit = [program_stream(f"evofit{k}", FAST, "source", 2) for k in range(2)]
        base = [stream_cost(ev, ts, O.BASELINE_80F9CC2, f"evo:{k}")["work"] for k, ts in enumerate(fit)]
        res.setdefault("base_cost", base)
        for method in ("dgm_branching", "incumbent", "random"):
            for lin in range(a.lineages):
                key = f"{method}:{lin}"
                if key in res:
                    continue
                search = {"instr": 0}
                out = evolve(ev, method, lin, fit, base, a.budget, search)
                out["search_instr"] = search["instr"]
                res[key] = out
                p.write_text(json.dumps(res, sort_keys=True, default=repr))
                print(key, "full %.4f" % out["full"], out["best"], "search %.1fG" % (search["instr"] / 1e9), flush=True)
                if time.perf_counter() - t0 > 720:
                    break
            if time.perf_counter() - t0 > 720:
                break
    if a.exp == "meta":
        # experiment 4: the procedure genome is SELECTED on fast source-domain streams only (meta-learning; its cost is the meta
        # cost), then applied from an EMPTY library to unfamiliar domains, against Fresh and the 80f9cc2 baseline.
        if "selection" not in res:
            rng = random.Random("w38-meta-select")
            cands = [dict(O.BASELINE_80F9CC2)] + [rand_genome(rng) for _ in range(5)]
            sel_streams = [program_stream(f"metasel{k}", FAST, "source", 2) for k in range(1)]
            meta_cost, scores = 0, []
            base = stream_cost(ev, sel_streams[0], None, "meta-fresh")["work"]
            for g in cands:
                c = stream_cost(ev, sel_streams[0], g, "meta-sel")
                meta_cost += c["work"]; scores.append(c["work"] / base if c["wrong"] == 0 else 9.9)
            best = cands[min(range(len(cands)), key=lambda i: scores[i])]
            res["selection"] = dict(cands=cands, scores=scores, best=best, meta_cost=meta_cost + base)
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
        best = res["selection"]["best"]
        for dom in ("tables", "grids"):
            if dom in res:
                continue
            ts = program_stream(f"meta-target:{dom}:{a.split}", (dom,), "all", 2)
            res[dom] = {name: stream_cost(ev, ts, g, f"meta:{dom}:{name}") for name, g in
                        (("Fresh", None), ("Baseline-80f9cc2", O.BASELINE_80F9CC2), ("Meta-learned", best))}
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
            print(dom, {k: (round(v["work"] / 1e9, 1), v["correct"], v["n"], v["wrong"]) for k, v in res[dom].items()}, flush=True)
    if a.exp == "continual":
        # experiment 6: long multi-phase program stream with RETURNING mechanisms: strings -> graphs -> strings (return) -> tables
        if "program" not in res or "Learner-regime-memory" not in res["program"]:
            phases = [("strings", "a"), ("graphs", "b"), ("strings", "c"), ("tables", "d")]
            ts, phase_of = [], []
            for i, (dom, sub) in enumerate(phases):
                seg = program_stream(f"cont:{a.split}:{sub}", (dom,), "source", 2)
                ts += seg; phase_of += [i] * len(seg)
            res["program"] = {"phase_of": phase_of}
            for name, g in (("Fresh", None), ("Learner-no-gate", O.BASELINE_80F9CC2),
                            ("Learner-surprise-gate", dict(O.BASELINE_80F9CC2, gate="surprise")),
                            ("Learner-regime-memory", dict(O.BASELINE_80F9CC2, gate="regime"))):
                c = stream_cost(ev, ts, g, f"cont:{name}")
                c["phase_work"] = [sum(w for w, ph in zip(c["curve"], phase_of) if ph == i) for i in range(len(phases))]
                res["program"][name] = c
                print("continual", name, round(c["work"] / 1e9, 1), [round(x / 1e9, 1) for x in c["phase_work"]], "declared", c["declared"],
                      "wrong", c["wrong"], flush=True)
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
    if a.exp in ("plan_repair", "plan_repair_confirm"):
        from nexus import w38_planning as PL, w38_repair as RP
        if "planning" not in res:
            dom = PL.parse_domain(open(ROOT / "artifacts/external/planning_domains/blocks_domain.pddl").read())
            names = [f"probBLOCKS-{n}-{k}" for n in (8, 9, 10, 11) for k in (0, 1, 2)]
            probs = []
            for nm in names:
                objs, init, goal = PL.parse_problem(open(ROOT / f"artifacts/external/planning_domains/{nm}.pddl").read())
                probs.append(("ext:" + nm, init, goal, PL.ground(dom, objs)))
            for i in range(8):
                init, goal, acts = PL.logistics(random.Random(f"{a.split}:plog{i}"), n_loc=5, n_pkg=4, capacity=2)
                probs.append((f"int:logistics{i}", init, goal, acts))
            out = {}
            for arm in ("Fresh", "Online-learned"):
                solved, rows = [], []
                for nm, init, goal, acts in probs:
                    w = PL.learn_weights(solved) if (arm == "Online-learned" and solved) else None
                    i0 = WE.instructions(__import__("os").getpid())
                    pl, exp = PL.plan(init, goal, acts, weights=w, budget=60000)
                    ok = pl is not None and PL.validate(init, goal, acts, pl)
                    rows.append(dict(task=nm, label="VALIDATED_PLAN" if ok else "NO_PLAN", length=len(pl) if pl else None, expansions=exp,
                                     instr=WE.instructions(__import__("os").getpid()) - i0))
                    if ok:
                        solved.append((init, goal, pl))
                out[arm] = rows
                print("planning", arm, sum(r["label"] == "VALIDATED_PLAN" for r in rows), len(rows), "expansions", sum(r["expansions"] for r in rows),
                      "instr %.1fG" % (sum(r["instr"] for r in rows) / 1e9), flush=True)
            res["planning"] = out
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
        if "repair" not in res:
            fams = list(RP.FAMILIES) * 4
            tasks = [RP.make_task(f, random.Random(f"{a.split}:rep{i}")) for i, f in enumerate(fams)]
            out = {}
            for arm in ("Fresh", "Online-learned"):
                fixes, rows = [], []
                for t in tasks:
                    if t is None:
                        rows.append(dict(label="NO_TASK")); continue
                    prior = RP.learn_prior(fixes) if (arm == "Online-learned" and fixes) else {}
                    ch = ev.child("0", "scripts/w38_repair_child.py"); c0 = WE.instructions(ch.p.pid)
                    ch.send({"cmd": "search", "buggy": t["buggy"], "public": t["public"], "prior": prior, "max_evals": 4000}); s = ch.recv()
                    ins = WE.instructions(ch.p.pid) - c0; ch.close()
                    lab = "NO_PATCH"
                    if s["found"]:
                        oc = ev.child("0", "scripts/w38_repair_child.py"); oc.send({"cmd": "oracle", "patch": s["found"]["patch"], "tests": t["heldout"]})
                        h = oc.recv(); oc.close()
                        lab = "TEST_VERIFIED_PATCH" if h["passed"] == h["n"] else "PUBLIC_FIT_ONLY"
                        if lab == "TEST_VERIFIED_PATCH":
                            fixes.append(s["found"]["kinds"])
                    rows.append(dict(family=t["family"], label=lab, evals=s["evals"], instr=ins))
                out[arm] = rows
                print("repair", arm, {k: sum(r["label"] == k for r in rows) for k in ("TEST_VERIFIED_PATCH", "PUBLIC_FIT_ONLY", "NO_PATCH")},
                      "evals", sum(r.get("evals", 0) for r in rows), "instr %.1fG" % (sum(r.get("instr", 0) for r in rows) / 1e9), flush=True)
            res["repair"] = out
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
    p.write_text(json.dumps(res, sort_keys=True, default=repr))
    WE.ledger_append(dict(run=f"w38-online-{a.exp}-{a.split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
