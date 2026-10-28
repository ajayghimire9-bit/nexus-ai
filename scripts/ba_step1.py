"""Step 1 forensic false-acceptance diagnosis on DEVELOPMENT failures (NOT LOCKED).
  python scripts/ba_step1.py ocean            oc/ep_train explore episodes that were silent at c84fc76 (random growth policy)
  python scripts/ba_step1.py energy           oc/edev energy builds under hand / meta / random / shuffled growth (silent ones)
  python scripts/ba_step1.py platform SEED [strong]   spent oc projects 13127 (oc/val) / 13143, 13155 (oc/test) regenerated IN MEMORY from
                                              the generator; the sealed vault is never read: the regenerated blob's sha256 is
                                              compared with the committed artifacts/oc_test_vault/MANIFEST.json
Writes artifacts/ba_dev/step1_<mode>[_SEED].json."""
import hashlib, json, random, sys
from pathlib import Path
sys.path.insert(0, "scripts")
from nexus import oc_seeds, ba_seeds, oc_ocean as OC, oc_learner as OL, ba_learn as BL, ba_forensics as BF, ba_energy as BE  # noqa: F401
from nexus import seed_registry as R
ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/ba_dev"
ART.mkdir(exist_ok=True)


def policies():
    recs = [json.loads(l) for l in (ROOT / "artifacts/oc_dev/p2_records.jsonl").read_text().splitlines()]
    sigs = [r["sig"] for r in recs]
    random.Random(13).shuffle(sigs)
    return dict(hand=OL.hand_policy, meta=OL.TablePolicy(recs), random=OL.random_policy,
                shuffled=OL.TablePolicy([dict(r, sig=s) for r, s in zip(recs, sigs)]))


def strip(d):
    return {k: v for k, v in d.items() if k != "learner"}


def ocean():
    seeds = [json.loads(l)["seed"] for f in sorted((ROOT / "artifacts/oc_dev").glob("eps_explore_ep_train_*.jsonl"))
             for l in f.read_text().splitlines() if json.loads(l)["silent"]]
    out = []
    for s in seeds:
        ep = OC.Episode(s)
        r = BL.learn_episode(ep, OL.random_policy, seed=s, keep=True)
        row = dict(seed=s, regime=ep.regime, needs=ep.needs, reproduced_silent=r["silent"], run=strip(r))
        if r["silent"]:
            row["diag"] = BF.diagnose(r["learner"], BF.OceanTarget(ep), r["learner"].alpha, stream=ep.test)
        out.append(row)
        print(s, r["silent"], row.get("diag", {}).get("kind"), row.get("diag", {}).get("why_missed", {}).get("reason"), flush=True)
    return out


def energy():
    from nexus import t7_platform as T7
    pols, out = policies(), []
    for s in [x for x in R.REGISTRY[("oc", "edev")] if x % 4 == 3]:
        P = T7.Project(s, "dev")
        for arm, pol in pols.items():
            ep = BE.ProjEp(P)
            r = BL.learn_episode(ep, pol, contract=True, seed=s, keep=True)
            row = dict(seed=s, arm=arm, fault=P.fault, run=strip(r))
            if r["silent"]:
                row["diag"] = BF.diagnose(r["learner"], BF.EmeterTarget(P), r["learner"].alpha, stream=ep.all)
            out.append(row)
            print(s, arm, r["accepted"], r["exact"], r["silent"], row.get("diag", {}).get("why_missed", {}).get("reason"), flush=True)
    return out


def platform(seed, arm="certified"):
    from u5_run import learners
    from nexus import oc_platform as OP, t7_repair as TR, u5_statesplit as SP
    if seed in R.REGISTRY[("oc", "test")]:
        P = OP.PL.Project(seed, "oc_test")
        man = json.loads((ROOT / "artifacts/oc_test_vault/MANIFEST.json").read_text())
        rel = f"oc_test/{list(R.REGISTRY[('oc', 'test')]).index(seed)}.json"
        sha = hashlib.sha256(P.to_json().encode()).hexdigest()
        ident = dict(manifest_entry=rel, regenerated_sha256=sha, matches_manifest=sha == man["files"][rel])
    else:
        P = OP.Project(seed, "val")
        ident = dict(split="oc/val (spent)")
    caught = []

    class Capture(TR.Learner2):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            caught.append(self)

    TR.Learner2, orig = Capture, TR.Learner2
    try:
        nx, _ = learners()
        A = OP.NexusArmCertified if arm == "certified" else OP.NexusArmStrong          # strong = pre-revision (c84fc76 val arm)
        res = OP.run_project(P, A("NEXUS_Confirmed", nx["NEXUS_U5"][0]))
    finally:
        TR.Learner2 = orig
    T = BF.EmeterTarget(P)
    stream = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
    diags = []
    for i, L in enumerate(caught):
        if not getattr(L, "machine", None):
            continue
        bad = BF._differs(T, L.machine, stream)
        d = dict(learner=i, n_modes=L.machine["n"], n_regs=len(L.machine["regs"]), wrong_on_stream=bool(bad),
                 alpha=list(L.alpha), train_events=len(L.events))
        if bad:
            d["diag"] = BF.diagnose(L, T, L.alpha, stream=stream)
        diags.append(d)
    keep = {k: res.get(k) for k in ("project", "domain", "fault", "lifecycle", "outcome", "data_ok", "bad_A", "bad_B", "silent",
                                    "claims_healthy", "human_repairs", "independently_correct", "repairs", "alarms")}
    print(json.dumps(keep, default=str))
    for d in diags:
        print(d["learner"], d["wrong_on_stream"], d.get("diag", {}).get("kind"), d.get("diag", {}).get("why_missed", {}).get("reason"))
    return dict(identity=ident, result=keep, learners=diags)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "platform":
        s, arm = int(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "certified")
        (ART / f"step1_platform_{s}{'' if arm == 'certified' else '_' + arm}.json").write_text(json.dumps(platform(s, arm), indent=1, default=str))
    else:
        (ART / f"step1_{mode}.json").write_text(json.dumps(globals()[mode](), indent=1, default=str))
