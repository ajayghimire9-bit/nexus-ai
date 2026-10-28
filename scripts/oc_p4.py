"""Part 4 runner (NOT LOCKED).  python scripts/oc_p4.py ledger | evolve ARM | eval ARM START N
ledger: parse docs/*.md -> P(gain | category); retrospective check with the ledger frozen BEFORE priority A (t7 report,
        ocean report and capability register excluded).
evolve: ARM in ledger | trace | random: 10 proposals, fitness on 20 ep_val episodes each (equal budget per arm).
eval:   ARM in ledger | trace | random | current: the arm's final surface on held-out ep_held episodes (resumable)."""
import json, sys, time
sys.path.insert(0, "src")
from pathlib import Path
from nexus import oc_seeds, oc_ocean as OC, oc_evolve as EV  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/oc_dev"
cmd = sys.argv[1]
if cmd == "ledger":
    pre = EV.ledger_records(ROOT / "docs", exclude=("NEXUS_7_TRIAL", "NEXUS_OCEAN", "NEXUS_CAPABILITY"))
    full = EV.ledger_records(ROOT / "docs")
    P_pre, n_pre = EV.ledger_predictor(pre)
    P_full, n_full = EV.ledger_predictor(full)
    retro = dict(verification=P_pre["verification"], transport_alignment=P_pre["transport_alignment"], library=P_pre["library"],
                 meta_evolution=P_pre["meta_evolution"], neural=P_pre["neural"])
    ok = all(P_pre["verification"] > P_pre[c] for c in ("transport_alignment", "library", "meta_evolution", "neural"))
    (ART / "p4_ledger.json").write_text(json.dumps(dict(n_docs_pre=len(pre), n_docs_full=len(full), P_pre=P_pre, n_pre=n_pre, P_full=P_full,
                                                         n_full=n_full, retrospective=retro, retrospective_ranks_verification_first=ok), indent=1))
    print("docs", len(pre), len(full), "P_pre", P_pre, "retro ok", ok)
elif cmd == "evolve":
    arm = sys.argv[2]
    P = json.loads((ART / "p4_ledger.json").read_text())["P_full"]
    eps = OC.suite("ep_val", n=20)
    best, hist, cpu = EV.evolve(arm, eps, 10, seed={"ledger": 1, "trace": 2, "random": 3}[arm], P=P)
    (ART / f"p4_evolve_{arm}.json").write_text(json.dumps(dict(surface=best, history=hist, cpu_s=round(cpu, 2)), indent=1))
    print(arm, best, hist[-1], round(cpu, 1))
else:
    arm, start, n = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    S = EV.SURFACE0 if arm == "current" else json.loads((ART / f"p4_evolve_{arm}.json").read_text())["surface"]
    eps = OC.suite("ep_held", n=n, start=start)
    out = ART / f"p4_eval_{arm}_{start}.jsonl"
    done = {json.loads(l)["seed"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for ep in eps:
            if ep.seed in done:
                continue
            if time.perf_counter() - T0 > 800:
                break
            r = EV.run_surface(ep, S, seed=ep.seed)
            fh.write(json.dumps(dict(seed=ep.seed, score=EV.curve_score(r), **{k: v for k, v in r.items() if k not in ("updates", "curve")})) + "\n")
            fh.flush()
