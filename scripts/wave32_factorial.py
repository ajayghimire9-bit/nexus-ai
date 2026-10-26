"""Wave 32 repetition x domain factorial (NOT LOCKED). Checker v3 (pinned), the OS retired-instruction meter, representations
and library mechanics fixed. Every stream starts from an EMPTY library; all learning decisions and rebuilds run in the
sandboxed solver and are billed.
  --phase evolve --rep 2|3 : Gen 0 (always-ON) + 5 generations x 5 children of the regime-adaptive genome (GENES_V3B) on
                             SOURCE-domain streams with `rep` repetitions per mechanism (fitness dev 771-773), then
                             selection of the top 3 on dev 774-775 (same rep). Champion = Gen k(rep).
  --phase table            : development table on dev2 781-785: 4 cells (Source/Target x 2/3 reps) x policies
                             always-ON, always-OFF, Gen k(2), Gen k(3).
  --phase confirm          : run ONCE on fresh one-use confirm_rep 7211-7215 after the design is frozen; same cells and
                             policies, plus a replay.
Source domains: records, strings, graphs (mixed stream). Target domain: grids."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
STATE = ROOT / "artifacts/wave32_factorial_state.json"
DOMAINS = {"Source": ("records", "strings", "graphs"), "Target": ("grids",)}
FIT, SEL, DEV2, CONF = (771, 772, 773), (774, 775), (781, 782, 783, 784, 785), (7211, 7212, 7213, 7214, 7215)


def stream(seed, domain, rep):
    from nexus import wave31_tasks as T
    tasks = [t for d in DOMAINS[domain] for t in T.target_stream3(seed, d, rep)]
    random.Random(f"w32f-order:{seed}:{domain}:{rep}").shuffle(tasks)
    return tasks


def run(ev, g, seeds, domain, rep, hashseed="0"):
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    rows, learn, reb = [], 0, 0
    for s in seeds:
        ch = E.Child(hashseed)
        r, li, rb = A.episode_v3b(ev, ch, stream(s, domain, rep), g, f"w32f:{s}:{domain}:{rep}")
        ch.close(); rows += r; learn += li; reb += rb
    return rows, learn, reb


def summ(rows, learn, reb):
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    f = A.fitness(rows, learn)
    f.update(rebuilds=reb, child=sum(r["ext"]["child_instr"] for r in rows) + learn,
             checker=sum(r["ext"]["eval_instr"] for r in rows), n=len(rows), detectors=D.scan(rows))
    return f


def policies(st, A):
    on = dict(A.GEN0_V3B)
    pol = {"always-ON": on, "always-OFF": dict(on, online=False)}
    for rep in (2, 3):
        if f"champion_{rep}" in st:
            pol[f"Genk({rep})"] = st[f"champion_{rep}"]
    return pol


def table(ev, seeds, st, A, hashseed="0"):
    out = {}
    for domain in DOMAINS:
        for rep in (2, 3):
            cell = f"{domain}/{rep}rep"
            out[cell] = {}
            for name, g in policies(st, A).items():
                per = {}
                for s in seeds:
                    rows, learn, reb = run(ev, g, (s,), domain, rep, hashseed)
                    per[s] = dict(summ(rows, learn, reb), digest=W.digest(rows))
                pooled = {k: sum(p[k] for p in per.values()) for k in ("correct", "wrong", "exhaustive", "work", "oracle",
                                                                        "child", "checker", "n", "rebuilds")}
                pooled["detectors"] = {k: sum(p["detectors"][k] for p in per.values()) for k in next(iter(per.values()))["detectors"]}
                out[cell][name] = dict(pooled=pooled, per_seed=per)
                print(cell, name, json.dumps({k: pooled[k] for k in ("n", "correct", "wrong", "work", "rebuilds")}),
                      sum(pooled["detectors"].values()), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", required=True); ap.add_argument("--rep", type=int)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if a.phase == "evolve":
        R.claim("wave32", "dev", list(FIT + SEL), run_id=f"wave32f-evolve-{a.rep}", record=False)
        arch, log, seen = [], [], set()
        for gen in range(6):
            rng = random.Random(f"w32f-evolve:{a.rep}:{gen}")
            gfp = D.fingerprint()
            kids = [(None, dict(A.GEN0_V3B))] if gen == 0 else []
            while gen and len(kids) < 5:
                p = A.pick_parent(arch, rng); g = A.mutate(p["genome"], rng)
                if A.gkey(g) not in seen and A.gkey(g) not in {A.gkey(k) for _, k in kids}:
                    kids.append((p["id"], g))
            rep_i = rng.randrange(len(kids))
            for i, (parent, g) in enumerate(kids):
                rows, learn, reb = run(ev, g, FIT, "Source", a.rep)
                fit = summ(rows, learn, reb)
                replay = None
                if i == rep_i:
                    rows2, _, _ = run(ev, g, FIT[:1], "Source", a.rep, "1")
                    replay = W.digest(rows2) == W.digest(rows[:len(rows2)])
                ok = sum(fit["detectors"].values()) == 0 and fit["wrong"] == 0 and replay is not False
                ent = dict(id=f"r{a.rep}g{gen}c{i}", gen=gen, parent=parent, genome=g, key=A.gkey(g), fit=fit,
                           replay=replay, admitted=ok)
                log.append(ent); seen.add(ent["key"])
                if ok:
                    arch.append(ent)
                print(ent["id"], parent, ok, replay, "work %.2fG correct %d rebuilds %d" % (fit["work"] / 1e9, fit["correct"], fit["rebuilds"]), flush=True)
            if D.scan([], gfp)["D4_integrity"]:
                raise SystemExit("D4 integrity violation")
        top = sorted(arch, key=lambda e: (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["work"]))[:3]
        sel = []
        for e in top:
            rows, learn, reb = run(ev, e["genome"], SEL, "Source", a.rep)
            sel.append(dict(id=e["id"], genome=e["genome"], fit=summ(rows, learn, reb)))
        champ = min([s for s in sel if s["fit"]["wrong"] == 0 and sum(s["fit"]["detectors"].values()) == 0],
                    key=lambda s: (-s["fit"]["correct"], s["fit"]["work"]))
        st[f"archive_{a.rep}"], st[f"selection_{a.rep}"] = log, sel
        st[f"champion_{a.rep}"], st[f"champion_id_{a.rep}"] = champ["genome"], champ["id"]
        print("champion", a.rep, champ["id"], champ["genome"])
    elif a.phase == "table":
        R.claim("wave32", "dev2", list(DEV2), run_id="wave32f-table", record=False)
        st["dev_table"] = table(ev, DEV2, st, A)
    elif a.phase == "confirm":
        R.claim("wave32", "confirm_rep", list(CONF), run_id="wave32f-confirm")
        res = dict(frozen_policies=policies(st, A), table=table(ev, CONF, st, A))
        rows2, _, _ = run(ev, st["champion_3"], (7213,), "Target", 3, "1")
        res["replay_7213_target3_genk3"] = W.digest(rows2) == res["table"]["Target/3rep"]["Genk(3)"]["per_seed"][7213]["digest"]
        res["D4_integrity"] = D.scan([], fp)["D4_integrity"]
        (ROOT / "artifacts/wave32_factorial_confirm.json").write_text(json.dumps(res, sort_keys=True, default=repr))
        print("replay", res["replay_7213_target3_genk3"], "D4", res["D4_integrity"])
    STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"wave32f-{a.phase}-{a.rep}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
