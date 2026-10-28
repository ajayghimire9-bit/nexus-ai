"""Part 3 runner (NOT LOCKED).  python scripts/oc_p3.py weights | eval SELECTOR DOMAIN START N
weights: meta-train the continuation-class weights on 100 lifecycle ep_train episodes (seeds 300-399; disjoint from the
         Part 2 exploration slice); no machine or program is kept.
eval:    SELECTOR in meta | generic | info_gain | random_class; DOMAIN lifecycle (ep_held) | protocol (ep_xfer); resumable."""
import json, sys, time
sys.path.insert(0, "src")
from pathlib import Path
from nexus import oc_seeds, oc_ocean as OC, oc_experiments as X  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/oc_dev"
if sys.argv[1] == "weights":
    t0 = time.process_time()
    w = X.learn_weights(OC.suite("ep_train", n=100, start=300))
    (ART / "p3_weights.json").write_text(json.dumps(dict(weights=w, cpu_s=round(time.process_time() - t0, 2)), indent=1))
    print(w)
else:
    sel, dom, start, n = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    split = "ep_held" if dom == "lifecycle" else "ep_xfer"
    eps = OC.suite(split, n=n, start=start) if dom == "lifecycle" else [OC.Episode(s, "protocol") for s in list(__import__("nexus.seed_registry", fromlist=["R"]).REGISTRY[("oc", "ep_xfer")])[start:start + n]]
    W = json.loads((ART / "p3_weights.json").read_text())["weights"]
    out = ART / f"p3_{sel}_{dom}_{start}.jsonl"
    done = {json.loads(l)["seed"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for ep in eps:
            if ep.seed in done:
                continue
            if time.perf_counter() - T0 > 800:
                break
            r = X.episode(ep, sel, W, seed=ep.seed)
            fh.write(json.dumps(dict(seed=ep.seed, **{k: v for k, v in r.items() if k != "updates"})) + "\n")
            fh.flush()
