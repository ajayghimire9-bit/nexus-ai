"""MI-2 one-use evaluation (NOT LOCKED).  python scripts/mi2_eval.py SPLIT ARM START N
SPLIT  val   Milestone A validation: 110 fresh episodes, K 20 + MUL / ADDC / SUBH 30 each
       test  Milestone A confirmation: 210 fresh episodes, K 30 + MUL / ADDC / SUBH 20 each + WITHHELD SCL / AVG / MAX 40 each
       btest Milestone B final evaluation: 140 fresh episodes, K 20 + SCL / AVG / MAX 30 each + MUL / ADDC / SUBH 10 each
ARM    fastpath (the shared established fast path; run first) or an arm pre-registered for the split in artifacts/mi2_freeze.json.
Each arm's full-space stage (mi2_learner.full_space, the arm's register-hypothesis procedure) runs only where the shared fast path
did not accept, with the SAME per-episode CPU cap CAP_S, the same oracle, acceptance check and evaluator for every arm. Task
memory is reset per episode: each episode builds a fresh learner; nothing learned on one evaluation episode reaches another. What
carries over = the arm's frozen procedure (and, for every arm, the fast path's frozen growth policy). Frozen files are verified
against the freeze; the split is claimed by the first call; rows -> artifacts/mi2_<SPLIT>/<ARM>.jsonl (resumable, never rerun)."""
import hashlib, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi2_seeds, mi_ocean as M, mi_learner as ML, mi2_learner as M2, seed_registry as R  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
CAP_S = 15.0
FAMS = {"val": ["K"] * 20 + ["MUL"] * 30 + ["ADDC"] * 30 + ["SUBH"] * 30,
        "test": ["K"] * 30 + ["MUL"] * 20 + ["ADDC"] * 20 + ["SUBH"] * 20 + ["SCL"] * 40 + ["AVG"] * 40 + ["MAX"] * 40,
        "btest": ["K"] * 20 + ["SCL"] * 30 + ["AVG"] * 30 + ["MAX"] * 30 + ["MUL"] * 10 + ["ADDC"] * 10 + ["SUBH"] * 10}
GATES = {"test": "artifacts/mi2_val/gate.json", "btest": "artifacts/mi2_bdev/freeze_gate.json"}


def families(split):
    f = list(FAMS[split])
    random.Random(f"mi2-{split}-order").shuffle(f)
    return f


def arm_domain(spec):
    if spec["kind"] == "baseline":
        return ML.baseline_domain, 60.0
    if spec["kind"] == "a6":
        return M2.a6_domain(), 60.0
    if spec["kind"] == "a5":
        return ML.lpl_domain(M2.A5_PROG), 60.0
    w = json.loads((ROOT / spec["file"]).read_text())["winner"]
    if w["kind"] == "params":
        return M2.params_domain(w["size_bound"], w["max_lit"]), w["max_s"]
    return ML.lpl_domain(w["prog"]), 60.0


def main(split, arm, start, n):
    frp = ROOT / ("artifacts/mi2_freeze.json" if split != "btest" else "artifacts/mi2_bfreeze.json")
    fr = json.loads(frp.read_text())
    for f, h in fr["files"].items():
        if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if arm != "fastpath" and arm not in fr["arms"][split]:
        raise SystemExit(f"arm {arm} not pre-registered for {split}")
    if split in GATES and not json.loads((ROOT / GATES[split]).read_text()).get("passed"):
        raise SystemExit("the preceding gate did not pass: this split stays closed")
    key = ("mi2", split)
    if not any(tuple(r["key"]) == key for r in R._spent() if "override" not in r):
        R.claim("mi2", split, list(R.REGISTRY[key]), run_id=f"mi2-{split}")
    d = ROOT / f"artifacts/mi2_{split}"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{arm}.jsonl"
    done = {json.loads(l)["i"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    fp = {}
    if arm != "fastpath":
        fp = {r["i"]: r for r in (json.loads(l) for l in (d / "fastpath.jsonl").read_text().splitlines() if l.strip())}
        dom, max_s = arm_domain(fr["arms"][split][arm])
    fams = families(split)
    seeds = list(R.REGISTRY[key])
    pol = ba_eps.policy("learned", "bounded")
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for i in range(start, min(start + n, len(fams))):
            if i in done:
                continue
            if time.perf_counter() - T0 > 800:
                break
            ep = M.Episode(seeds[i], fams[i])
            if arm == "fastpath":
                r, s = ML.fast_path(ep, pol, ep.seed)
                sc = ML.score(ep, r)
                row = dict(i=i, seed=ep.seed, family=fams[i], accepted=r is not None, exact=sc["exact"], silent=sc["silent"],
                           cpu_s=s["cpu_s"], queries=s["queries"], updates=ML.updates_src(r))
            else:
                f0 = fp[i]
                if f0["accepted"]:
                    row = dict(i=i, seed=ep.seed, family=fams[i], stage="fast_path", exact=f0["exact"], silent=f0["silent"],
                               cpu_s=f0["cpu_s"], queries=f0["queries"], full_cpu_s=0.0)
                else:
                    r, s = M2.full_space(ep, dom, ep.seed, max_s=max_s, cap_s=CAP_S)
                    sc = ML.score(ep, r)
                    row = dict(i=i, seed=ep.seed, family=fams[i], stage="full_space", exact=sc["exact"], silent=sc["silent"],
                               outcome=s["outcome"], cpu_s=round(f0["cpu_s"] + s["cpu_s"], 3), queries=f0["queries"] + s["queries"],
                               full_cpu_s=s["cpu_s"], full_queries=s["queries"], domain_sizes=s["domain_sizes"],
                               searches=s["searches"], explained=round(s["explained"], 3), updates=ML.updates_src(r))
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(split, arm, i, fams[i], row.get("stage", ""), row["exact"], row.get("outcome", ""), row["cpu_s"], flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
