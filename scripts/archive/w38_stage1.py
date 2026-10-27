"""Wave 38 Stage 1 pilot across all 6 domains + external samples (NOT LOCKED; development data).
Program domains (strings, tables, grids, graphs) and PROSE: Fresh search over the declared scope, Checker v4, active probing
(<= 3 oracle queries; never the query input). Planning: internal logistics-lite + external blocksworld, VALIDATED_PLAN.
Repairs: TEST_VERIFIED_PATCH via sandboxed search + separate sandboxed held-out oracle. MPS vs CPU benchmark for a small MLP.
Every attempt is recorded (no dropped failures)."""
import json, os, random, resource, sys, time, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def program_task(t, depth, budget, rng, instr):
    from nexus import w38_scope as S, w38_lang as L, w38_search as Q, checker_kernel_v4 as V4
    i0, w0 = instr(), time.perf_counter()
    sc = S.scope(t["public"], t["query"], depth)
    pub, probes, v, cand = [list(p) for p in t["public"]], 0, {"label": "NO_CANDIDATE"}, None
    teacher = t.get("teacher")
    while True:
        cand = Q.search(pub, t["query"], sc["tools"], depth, Q.uniform(len(sc["tools"])), budget=budget)
        if cand is None:
            v = {"label": "ABSTAIN", "reason": "no_candidate_within_budget"}
            break
        ans = L.run(cand, t["query"])
        v = V4.check({"checker_version": 4, "public": pub, "query": t["query"], "claimed_answer": ans, "candidate": cand,
                      "scope": sc})
        if v["label"] != "AMBIGUOUS" or probes >= 3 or teacher is None:
            break
        x = Q.design_probe(pub, t["query"], sc["tools"], v, rng)
        if x is None:
            break
        y = L.run(teacher, x)
        probes += 1
        if y == L.ERROR:
            break
        pub = pub + [[x, y]]
    correct = None
    if v["label"] == "exhaustive_UNIQUE":
        ans = L.run(cand, t["query"])
        correct = L.key(ans) == L.key(t["answer"])
        if "heldout" in t:
            correct = all(L.key(L.run(cand, x)) == L.key(y) for x, y in t["heldout"])
    return dict(label=v["label"], reason=v.get("reason"), k=v.get("k"), probes=probes, correct=correct, tools=len(sc["tools"]),
                instr_G=(instr() - i0) / 1e9, wall_s=time.perf_counter() - w0, nodes=v.get("nodes"))


def main():
    from nexus import w38_domains as D, w38_planning as PL, w38_repair as RP, wave31_evaluator as E
    pid = os.getpid(); instr = lambda: E.instructions(pid)
    t0 = time.perf_counter(); rng = random.Random("w38-stage1")
    out = {"program": [], "prose": [], "planning": [], "repair": [], "mps": None}
    for t in D.stream("stage1", n_per=2):
        r = program_task(t, len(t["teacher"]), 300000, rng, instr)
        r.update(domain=t["domain"], mech=t["mechanism"], depth=len(t["teacher"]))
        out["program"].append(r)
        print("prog", t["domain"], t["mechanism"], r["label"], r["correct"], r["probes"], "%.2fs" % r["wall_s"], flush=True)
    for f in sorted(glob.glob(str(ROOT / "artifacts/external/prose/*.json")))[:10]:
        ex = json.load(open(f))["Examples"]
        if len(ex) < 4 or any(len(e["Input"]) != 1 for e in ex):
            out["prose"].append(dict(task=Path(f).stem, label="SKIPPED_FORMAT")); continue
        t = {"public": [[e["Input"][0], e["Output"]] for e in ex[:3]], "query": ex[3]["Input"][0], "answer": ex[3]["Output"],
             "heldout": [[e["Input"][0], e["Output"]] for e in ex[3:]]}
        r = program_task(t, 3, 300000, rng, instr)
        r.update(task=Path(f).stem)
        out["prose"].append(r)
        print("prose", r["task"], r["label"], r["correct"], "%.2fs" % r["wall_s"], flush=True)
    dom = PL.parse_domain(open(ROOT / "artifacts/external/planning_domains/blocks_domain.pddl").read())
    probs = [("ext:" + p, *PL.parse_problem(open(ROOT / f"artifacts/external/planning_domains/{p}.pddl").read()))
             for p in ("probBLOCKS-5-0", "probBLOCKS-6-0", "probBLOCKS-7-1", "probBLOCKS-7-2")]
    for name, objs, init, goal in probs:
        acts = PL.ground(dom, objs); i0, w0 = instr(), time.perf_counter()
        pl, exp = PL.plan(init, goal, acts, budget=50000)
        out["planning"].append(dict(task=name, label="VALIDATED_PLAN" if pl and PL.validate(init, goal, acts, pl) else "NO_PLAN",
                                    length=len(pl) if pl else None, expansions=exp, instr_G=(instr() - i0) / 1e9, wall_s=time.perf_counter() - w0))
    for i in range(6):
        init, goal, acts = PL.logistics(random.Random(f"s1log{i}"), n_pkg=3 + i % 2, shifted=i >= 4)
        i0, w0 = instr(), time.perf_counter()
        pl, exp = PL.plan(init, goal, acts, budget=50000)
        out["planning"].append(dict(task=f"int:logistics{i}", label="VALIDATED_PLAN" if pl and PL.validate(init, goal, acts, pl) else "NO_PLAN",
                                    length=len(pl) if pl else None, expansions=exp, instr_G=(instr() - i0) / 1e9, wall_s=time.perf_counter() - w0))
    for p in out["planning"]:
        print("plan", p["task"], p["label"], p["length"], p["expansions"], flush=True)
    for i, fam in enumerate(list(RP.FAMILIES) * 2):
        t = RP.make_task(fam, random.Random(f"s1rep{i}"))
        if t is None:
            out["repair"].append(dict(family=fam, label="NO_TASK")); continue
        ch = E.Child("0", "scripts/w38_repair_child.py"); c0 = E.instructions(ch.p.pid); w0 = time.perf_counter()
        ch.send({"cmd": "search", "buggy": t["buggy"], "public": t["public"], "prior": {}, "max_evals": 4000}); s = ch.recv()
        ins = E.instructions(ch.p.pid) - c0; ch.close()
        lab, held = "NO_PATCH", None
        if s["found"]:
            oc = E.Child("0", "scripts/w38_repair_child.py"); oc.send({"cmd": "oracle", "patch": s["found"]["patch"], "tests": t["heldout"]})
            held = oc.recv(); oc.close()
            lab = "TEST_VERIFIED_PATCH" if held["passed"] == held["n"] else "PUBLIC_FIT_ONLY"
        out["repair"].append(dict(family=fam, label=lab, evals=s["evals"], heldout=held, instr_G=ins / 1e9, wall_s=time.perf_counter() - w0))
        print("repair", fam, lab, s["evals"], flush=True)
    import torch
    bench = {}
    for dev in ("cpu", "mps"):
        if dev == "mps" and not torch.backends.mps.is_available():
            continue
        net = torch.nn.Sequential(torch.nn.Linear(256, 256), torch.nn.ReLU(), torch.nn.Linear(256, 64)).to(dev)
        opt = torch.optim.Adam(net.parameters(), 1e-3)
        for bs in (16, 128, 1024, 4096):
            x = torch.randn(bs, 256, device=dev); y = torch.randn(bs, 64, device=dev)
            for _ in range(3):
                loss = ((net(x) - y) ** 2).mean(); opt.zero_grad(); loss.backward(); opt.step()
            if dev == "mps":
                torch.mps.synchronize()
            w0 = time.perf_counter()
            for _ in range(20):
                loss = ((net(x) - y) ** 2).mean(); opt.zero_grad(); loss.backward(); opt.step()
            if dev == "mps":
                torch.mps.synchronize()
            bench[f"{dev}:{bs}"] = (time.perf_counter() - w0) / 20
    out["mps"] = bench
    print("mps bench (s per train step)", {k: round(v, 5) for k, v in bench.items()})
    out["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
    out["wall_s"] = time.perf_counter() - t0
    (ROOT / "artifacts/w38_stage1.json").write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run="w38-stage1", wall_s=out["wall_s"], status="COMPLETE"))
    print("peak RSS %.0f MiB, wall %.0f s" % (out["peak_rss_mib"], out["wall_s"]))


if __name__ == "__main__":
    main()
