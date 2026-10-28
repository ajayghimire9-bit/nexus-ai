"""mi one-use evaluation (NOT LOCKED).  python scripts/mi_eval.py SPLIT ARM START N
SPLIT: val (80 episodes, dev families K / MUL / ADDC / SUBH x 20, fresh) | test (300: K 60, MUL / ADDC / SUBH 30 each fresh,
WITHHELD SCL / AVG / MAX 50 each). ARM: fastpath (the shared established fast path; run first) | baseline | invented |
random_struct | params | direct. Each arm's full-space stage runs only where the cached fast path did not accept, with a
per-episode cap of CAP_S (identical for every arm). Frozen artifacts verified against artifacts/mi_freeze.json; the split is
claimed by the first call; rows appended to artifacts/mi_<SPLIT>/<ARM>.jsonl (resumable; a recorded episode never reruns)."""
import hashlib, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi_seeds, mi_ocean as M, mi_learner as ML, seed_registry as R  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
CAP_S = 15.0
VAL_FAMS = [f for f in M.DEV_FAMILIES for _ in range(20)]
TEST_FAMS = ["K"] * 60 + ["MUL"] * 30 + ["ADDC"] * 30 + ["SUBH"] * 30 + ["SCL"] * 50 + ["AVG"] * 50 + ["MAX"] * 50


def families(split):
    f = list(VAL_FAMS if split == "val" else TEST_FAMS)
    random.Random(f"mi-{split}-order").shuffle(f)
    return f


def arm_domain(arm, fr):
    if arm == "baseline":
        return ML.baseline_domain, 60.0
    if arm == "direct":
        return ML.direct_domain(), 60.0
    w = json.loads((ROOT / fr["winners"][arm]).read_text())["winner"]
    if w["kind"] == "params":
        return ML.params_domain(w["size_bound"]), w["max_s"]
    return ML.lpl_domain(w["prog"]), 60.0


def main(split, arm, start, n):
    fr = json.loads((ROOT / "artifacts/mi_freeze.json").read_text())
    for f, h in fr["files"].items():
        if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if arm not in fr["arms"][split]:
        raise SystemExit(f"arm {arm} not pre-registered for {split}")
    if split == "test" and not json.loads((ROOT / "artifacts/mi_val/gate.json").read_text())["passed"]:
        raise SystemExit("validation gate not passed: the confirmation stays closed")
    key = ("mi", split)
    if not any(tuple(r["key"]) == key for r in R._spent() if "override" not in r):
        R.claim("mi", split, list(R.REGISTRY[key]), run_id=f"mi-{split}")
    d = ROOT / f"artifacts/mi_{split}"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{arm}.jsonl"
    done = {json.loads(l)["i"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    fp = {}
    if arm != "fastpath":
        fp = {r["i"]: r for r in (json.loads(l) for l in (d / "fastpath.jsonl").read_text().splitlines() if l.strip())}
        dom, max_s = arm_domain(arm, fr)
    fams = families(split)
    seeds = list(R.REGISTRY[key])
    pol = ba_eps.policy("learned", "bounded")
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for i in range(start, min(start + n, len(fams))):
            if i in done:
                continue
            if time.perf_counter() - T0 > 760:
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
                               cpu_s=f0["cpu_s"], queries=f0["queries"])
                else:
                    r, s = ML.full_space(ep, dom, ep.seed, max_s=max_s, cap_s=CAP_S)
                    sc = ML.score(ep, r)
                    row = dict(i=i, seed=ep.seed, family=fams[i], stage="full_space", exact=sc["exact"], silent=sc["silent"],
                               outcome=s["outcome"], cpu_s=round(f0["cpu_s"] + s["cpu_s"], 3), queries=f0["queries"] + s["queries"],
                               full_cpu_s=s["cpu_s"], full_queries=s["queries"], domain_sizes=s.get("domain_sizes"),
                               updates=ML.updates_src(r))
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(split, arm, i, fams[i], row.get("stage", ""), row["exact"], row.get("outcome", ""), row["cpu_s"], flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
