"""Mixed-repetition stream baseline (NOT LOCKED). The frozen single regime-detecting policy (a0c2, frozen 81edd6a,
confirmed f11c3a1) vs always-ON and always-OFF, on streams whose repetition regime switches: segment 1 = 2 reps,
segment 2 = 3 reps, segment 3 = 2 reps, each segment drawn with its own sub-seed and shuffled internally. All three
segments use the same domain, so cores also recur across segments. One-use seeds wave32 mixed 7221-7225; run once."""
import json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
SEEDS = (7221, 7222, 7223, 7224, 7225)


def mixed(seed, domain):
    from nexus import wave31_tasks as T
    out = []
    for seg, rep in (("a", 2), ("b", 3), ("c", 2)):
        ts = [t for d in F.DOMAINS[domain] for t in T.target_stream3(f"{seed}{seg}", d, rep)]
        random.Random(f"w32m:{seed}:{domain}:{seg}").shuffle(ts)
        out += ts
    return out


def main():
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    R.claim("wave32", "mixed", list(SEEDS), run_id="wave32-mixed")
    st = json.loads((ROOT / "artifacts/wave32_adaptive_state.json").read_text())
    gate = next(e["genome"] for e in st["archive"] if e["id"] == "a0c2")
    pol = {"always-ON": dict(A.GEN0_V3C), "always-OFF": dict(A.GEN0_V3C, online=False), "frozen-a0c2": gate}
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint(); out = {}
    for domain in F.DOMAINS:
        out[domain] = {}
        for name, g in pol.items():
            per = {}
            for s in SEEDS:
                ch = E.Child("0")
                rows, learn, reb = A.episode_v3b(ev, ch, mixed(s, domain), g, f"w32m:{s}:{domain}")
                ch.close()
                per[s] = dict(F.summ(rows, learn, reb), digest=W.digest(rows))
            out[domain][name] = dict(per_seed=per, work=sum(p["work"] for p in per.values()),
                                     correct=sum(p["correct"] for p in per.values()), n=sum(p["n"] for p in per.values()),
                                     wrong=sum(p["wrong"] for p in per.values()),
                                     detectors=sum(sum(p["detectors"].values()) for p in per.values()))
    ch = E.Child("1")
    rows2, _, _ = A.episode_v3b(ev, ch, mixed(7223, "Target"), gate, "w32m:7223:Target")
    ch.close()
    out["replay_7223_target_gate"] = W.digest(rows2) == out["Target"]["frozen-a0c2"]["per_seed"][7223]["digest"]
    out["D4"] = D.scan([], fp)["D4_integrity"]
    (ROOT / "artifacts/wave32_mixed.json").write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run="wave32-mixed", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    for domain in F.DOMAINS:
        d = out[domain]; best = min(d["always-ON"]["work"], d["always-OFF"]["work"])
        wins = sum(d["frozen-a0c2"]["per_seed"][s]["work"] <= min(d["always-ON"]["per_seed"][s]["work"], d["always-OFF"]["per_seed"][s]["work"]) for s in SEEDS)
        print(domain, {k: (round(v["work"] / 1e9, 2), f'{v["correct"]}/{v["n"]}', v["wrong"], v["detectors"]) for k, v in d.items()},
              "gate/min(ON,OFF) %.4f seeds %d/5  ON/OFF %.4f" % (d["frozen-a0c2"]["work"] / best, wins, d["always-ON"]["work"] / d["always-OFF"]["work"]))
    print("replay", out["replay_7223_target_gate"], "D4", out["D4"])


if __name__ == "__main__":
    main()
