"""MI-2 development diagnosis (NOT LOCKED; mi2/diag only; privileged witness domains allowed HERE ONLY).
  python scripts/mi2_diag.py FAMILY N        N episodes of FAMILY on which the shared fast path does not accept
Per episode, the full-space stage (mi2_learner, CPU cap CAP_S) with: baseline (GRAMMAR5), witness_end (GRAMMAR5 + the episode's
true updates appended), witness_front (true updates first), witness_min (identity + true updates only), mi1 (MI-1's frozen
procedure), direct (MI-1's generic direct control). Separates missing expressiveness (baseline unsat, witness_end solves),
hypothesis ordering (witness_front solves, witness_end times out), assignment-search exhaustion (timeouts that a longer cap
fixes) and insufficient evidence / engine limits (witness_min fails). Rows -> artifacts/mi2_dev/diag.jsonl (resumable)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi2_seeds, mi_ocean as M, mi_learner as ML, mi2_learner as M2, mi_lpl as LP, seed_registry as R  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/mi2_dev/diag.jsonl"
CAP_S, WORK_S = 20.0, 820


def main(fam, n):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines()] if OUT.exists() else []
    done = {(r["seed"], r["family"]) for r in rows}
    mi1 = json.loads((ROOT / "artifacts/mi_dev/select_evolve.json").read_text())["winner"]["prog"]
    pol = ba_eps.policy("learned", "bounded")
    seeds = [s for k, s in enumerate(R.REGISTRY[("mi2", "diag")]) if k % len(M.FAMILIES) == list(M.FAMILIES).index(fam)]
    T0, got = time.perf_counter(), sum(1 for r in rows if r["family"] == fam and not r["fast_accepted"])
    for s in seeds:
        if got >= n or time.perf_counter() - T0 > WORK_S:
            break
        if (s, fam) in done:
            continue
        ep = M.Episode(s, fam)
        r0, fs = ML.fast_path(ep, pol, s)
        row = dict(seed=s, family=fam, fast_accepted=r0 is not None, fast_exact=ML.score(ep, r0)["exact"], fast_cpu_s=fs["cpu_s"],
                   truth=[LP.S.src(g) for g in M2.true_updates(ep)], regs=ep.machine["regs"], modes=ep.machine["modes"], arms={})
        if r0 is None:
            got += 1
            for name, fn in [("baseline", ML.baseline_domain), ("witness_end", M2.witness_fn(ep, "end")),
                             ("witness_front", M2.witness_fn(ep, "front")), ("witness_min", M2.witness_fn(ep, "min")),
                             ("mi1", ML.lpl_domain(mi1)), ("direct", ML.direct_domain())]:
                e = M.Episode(s, fam)
                out, st = M2.full_space(e, fn, s, cap_s=CAP_S)
                sc = ML.score(e, out)
                row["arms"][name] = dict(exact=sc["exact"], silent=sc["silent"], outcome=st["outcome"], cpu_s=st["cpu_s"],
                                         queries=st["queries"], searches=st["searches"], domain_sizes=st["domain_sizes"])
        with OUT.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(fam, s, "fast", row["fast_accepted"], {k: (v["exact"], v["outcome"], v["cpu_s"]) for k, v in row["arms"].items()}, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
