"""mi Part A: profile the strongest existing lifecycle learner on dev-family episodes (NOT LOCKED; development data).
  python scripts/mi_profile.py START N        seeds mi/profile[START:START+N]; family = DEV_FAMILIES[i % 4]
Baseline = x7_regsearch.learn_class_bounded(growth = learned ba policy, fix = True, fallback = True) + bounded acceptance.
Per episode: exact on held-out, accepted, CPU split (control learning / register search / acceptance+coverage / other), register
search outcomes (ok / unsat / timeout), queries. Appends artifacts/mi_dev/profile.jsonl."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi_seeds, mi_ocean as M, x7_regsearch as XR, oc_learner as OL, t7_repair as TR, ba_accept as BA, seed_registry as R  # noqa: F401
from nexus import u5_statesplit as SP
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
PROF = {}


def wrap(cls, name, key):
    f = getattr(cls, name)

    def g(self, *a, **k):
        t = time.process_time()
        try:
            r = f(self, *a, **k)
        except TimeoutError:
            PROF.setdefault(key + "_outcome", []).append("timeout")
            PROF[key] = PROF.get(key, 0) + time.process_time() - t
            raise
        PROF[key] = PROF.get(key, 0) + time.process_time() - t
        if name == "learn_registers":
            PROF.setdefault(key + "_outcome", []).append("ok" if r is not None else (getattr(self, "fail", None) or {}).get("kind", "none"))
        return r
    setattr(cls, name, g)


for c in (XR.Learner3X, XR.Learner2X):
    wrap(c, "learn_registers", "regs_" + c.__name__)
    wrap(c, "learn_control", "control_" + c.__name__)
_bc, _cc = BA.bounded_cex, TR.coverage_cex


def bc(*a, **k):
    t = time.process_time(); r = _bc(*a, **k); PROF["accept"] = PROF.get("accept", 0) + time.process_time() - t; return r


def cc(*a, **k):
    t = time.process_time(); r = _cc(*a, **k); PROF["coverage"] = PROF.get("coverage", 0) + time.process_time() - t; return r


BA.bounded_cex, TR.coverage_cex = bc, cc
XR.BA.bounded_cex, XR.TR.coverage_cex = bc, cc


def main(start, n):
    pol = ba_eps.policy("learned", "bounded")
    out = ROOT / "artifacts/mi_dev/profile.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    seeds = list(R.REGISTRY[("mi", "profile")])
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for i in range(start, start + n):
            if time.perf_counter() - T0 > 760:
                break
            fam = M.DEV_FAMILIES[i % len(M.DEV_FAMILIES)]
            ep = M.Episode(seeds[i], fam)
            PROF.clear()
            c0 = time.process_time()
            r = XR.learn_class_bounded(ep.train, ep.y_train, ep.query, seed=seeds[i], growth=pol, fix=True, fallback=True)
            cpu = time.process_time() - c0
            sc = dict(exact=False)
            if r:
                cls = SP.compile_class(r["source"], r["name"])
                sc = ep.score(lambda evs: SP.run_class(cls, evs))
            row = dict(i=i, seed=seeds[i], family=fam, accepted=r is not None, exact=bool(r and sc["exact"]), silent=bool(r and not sc["exact"]),
                       learner=(r or {}).get("learner"), cpu_s=round(cpu, 3), queries=ep.n_queries, modes=ep.machine["modes"], regs=ep.machine["regs"],
                       prof={k: (round(v, 3) if isinstance(v, float) else v) for k, v in PROF.items()})
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(i, fam, row["accepted"], row["exact"], row["learner"], row["cpu_s"], flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
