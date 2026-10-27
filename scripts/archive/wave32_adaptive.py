"""Wave 32 single regime-detecting policy (NOT LOCKED). Checker v3 (pinned), the OS meter, representations and library
mechanics fixed; every stream starts from an EMPTY library; all learning decisions run in the sandboxed solver.
  --phase evolve  : one genome (GENES_V3C) evolved under a MIXED-REGIME fitness: Source streams at 2 AND 3 reps (dev
                    771-773). Score = mean over (seed, rep) of work / always-OFF work on that stream. Archive seeded
                    with Gen 0 (always-ON) + the earlier Gen k(2), Gen k(3), re-scored. 8 generations x 6 children,
                    resumable. Then the top 3 are re-selected on dev 774-775 (both reps).
  --phase table   : development check on dev2 781-785, 4 cells x {always-ON, always-OFF, Gen k(2), Gen k(3), Gen k(adapt)}.
  --phase confirm : once, on fresh one-use confirm_adapt 7216-7220, after the design is frozen.
Lexicographic fitness: wrong = 0 and no detector flag, then max correct, then min mean normalised work."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
STATE = ROOT / "artifacts/wave32_adaptive_state.json"
FIT, SEL, DEV2, CONF = (771, 772, 773), (774, 775), (781, 782, 783, 784, 785), (7216, 7217, 7218, 7219, 7220)


def upgrade(g, A):
    """Lift an earlier V3B genome into V3C (rebuild_hit_min = 0 reproduces its behaviour exactly)."""
    return A.validate(dict(g, rebuild_hit_min=0.0))


def score(ev, g, seeds, off, hashseed="0"):
    from nexus import wave32_detectors as D
    rows_all, ratios, correct, wrong, n = [], [], 0, 0, 0
    for s in seeds:
        for rep in (2, 3):
            rows, learn, reb = F.run(ev, g, (s,), "Source", rep, hashseed)
            f = F.summ(rows, learn, reb)
            ratios.append(f["work"] / off[f"{s}:{rep}"])
            correct += f["correct"]; wrong += f["wrong"]; n += f["n"]; rows_all += rows
    m = sum(ratios) / len(ratios)
    # `work` = the mean normalised ratio, so the archive's tournament (wave32_archive.better) ranks by it
    return dict(mean_ratio=m, work=m, max_ratio=max(ratios), correct=correct, wrong=wrong, n=n,
                detectors=D.scan(rows_all)), rows_all


def off_baseline(ev, seeds, A):
    off = {}
    for s in seeds:
        for rep in (2, 3):
            rows, learn, reb = F.run(ev, dict(A.GEN0_V3C, online=False), (s,), "Source", rep)
            off[f"{s}:{rep}"] = F.summ(rows, learn, reb)["work"]
    return off


def key(e):
    return (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["mean_ratio"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", required=True); ap.add_argument("--gens", type=int, default=8)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    prev = json.loads((ROOT / "artifacts/wave32_factorial_state.json").read_text())
    if a.phase == "evolve":
        R.claim("wave32", "dev", list(FIT + SEL), run_id="wave32a-evolve", record=False)
        if "off_fit" not in st:
            st.update(off_fit=off_baseline(ev, FIT, A), archive=[], log=[], gen=-1)
        seen = {e["key"] for e in st["log"]}
        while st["gen"] + 1 <= a.gens and time.perf_counter() - t0 < 600:
            gen = st["gen"] + 1
            rng = random.Random(f"w32a-evolve:{gen}")
            gfp = D.fingerprint()
            if gen == 0:
                kids = [(None, dict(A.GEN0_V3C)), ("prev:Genk(2)", upgrade(prev["champion_2"], A)),
                        ("prev:Genk(3)", upgrade(prev["champion_3"], A))]
            else:
                kids = []
                while len(kids) < 6:
                    p = A.pick_parent(st["archive"], rng); g = A.mutate(p["genome"], rng)
                    if A.gkey(g) not in seen and A.gkey(g) not in {A.gkey(k) for _, k in kids}:
                        kids.append((p["id"], g))
            rep_i = rng.randrange(len(kids))
            for i, (parent, g) in enumerate(kids):
                fit, rows = score(ev, g, FIT, st["off_fit"])
                replay = None
                if i == rep_i:
                    rows2, _, _ = F.run(ev, g, FIT[:1], "Source", 2, "1")
                    replay = W.digest(rows2) == W.digest(rows[:len(rows2)])
                ok = sum(fit["detectors"].values()) == 0 and fit["wrong"] == 0 and replay is not False
                ent = dict(id=f"a{gen}c{i}", gen=gen, parent=parent, genome=g, key=A.gkey(g), fit=fit, replay=replay, admitted=ok)
                st["log"].append(ent); seen.add(ent["key"])
                if ok:
                    st["archive"].append(ent)
                print(ent["id"], parent, ok, replay, "mean %.4f max %.4f" % (fit["mean_ratio"], fit["max_ratio"]), flush=True)
            if D.scan([], gfp)["D4_integrity"]:
                raise SystemExit("D4 integrity violation")
            st["gen"] = gen
            STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
        if st["gen"] >= a.gens and "champion" not in st:
            off_sel = off_baseline(ev, SEL, A)
            sel = []
            for e in sorted(st["archive"], key=key)[:3]:
                fit, _ = score(ev, e["genome"], SEL, off_sel)
                sel.append(dict(id=e["id"], genome=e["genome"], fit=fit))
                print("select", e["id"], "mean %.4f max %.4f" % (fit["mean_ratio"], fit["max_ratio"]), flush=True)
            champ = min([s for s in sel if s["fit"]["wrong"] == 0 and sum(s["fit"]["detectors"].values()) == 0], key=key)
            st.update(selection=sel, champion=champ["genome"], champion_id=champ["id"])
            print("champion", champ["id"], champ["genome"])
    elif a.phase == "reselect":
        # Protocol amendment (dev only): all-cell re-selection on dev 774-775 (Source + Target, 2 + 3 reps), each stream
        # scored as work / always-OFF work; candidates = top 8 archive members by mean fitness; rule: max ratio <= 1.01,
        # then min mean ratio (fallback: min max ratio).
        R.claim("wave32", "dev", list(SEL), run_id="wave32a-reselect", record=False)
        # amendment 2: normalise each stream by min(always-ON, always-OFF) on that stream (the success criterion's
        # yardstick); amendment 1 normalised by always-OFF only and selected a learning-OFF policy.
        off = {}
        for dom in F.DOMAINS:
            for rep in (2, 3):
                for s in SEL:
                    w = []
                    for g in (dict(A.GEN0_V3C, online=False), dict(A.GEN0_V3C)):
                        rows, learn, reb = F.run(ev, g, (s,), dom, rep)
                        w.append(F.summ(rows, learn, reb)["work"])
                    off[f"{dom}:{rep}:{s}"] = min(w)
        res = []
        for e in sorted(st["archive"], key=key)[:8]:
            ratios, wrong, det = [], 0, 0
            for dom in F.DOMAINS:
                for rep in (2, 3):
                    for s in SEL:
                        rows, learn, reb = F.run(ev, e["genome"], (s,), dom, rep)
                        f = F.summ(rows, learn, reb)
                        ratios.append(f["work"] / off[f"{dom}:{rep}:{s}"]); wrong += f["wrong"]; det += sum(f["detectors"].values())
            res.append(dict(id=e["id"], genome=e["genome"], mean=sum(ratios) / len(ratios), max=max(ratios), wrong=wrong, det=det))
            print("reselect", e["id"], "mean %.4f max %.4f wrong %d det %d" % (res[-1]["mean"], res[-1]["max"], wrong, det), flush=True)
        ok = [r for r in res if r["wrong"] == 0 and r["det"] == 0]
        feas = [r for r in ok if r["max"] <= 1.01]
        champ = min(feas, key=lambda r: r["mean"]) if feas else min(ok, key=lambda r: r["max"])
        if "reselection" in st:
            st["reselection_amendment1"] = dict(rows=st["reselection"], champion_id=st["champion_id"])
        st.update(reselection=res, champion_v1=st.get("champion_v1", st.get("champion")),
                  champion_id_v1=st.get("champion_id_v1", st.get("champion_id")),
                  champion=champ["genome"], champion_id=champ["id"], reselect_feasible=bool(feas))
        print("champion", champ["id"], champ["genome"], "feasible", bool(feas))
    else:
        pol = {"always-ON": dict(A.GEN0_V3C), "always-OFF": dict(A.GEN0_V3C, online=False),
               "Genk(2)": upgrade(prev["champion_2"], A), "Genk(3)": upgrade(prev["champion_3"], A),
               "Genk(adapt)": st["champion"]}
        if a.phase == "confirm":
            # FROZEN (amendment 3): primary single policy = a0c2 (= Gen k(3) lifted), the only evaluated candidate that
            # satisfies the success criterion on dev2; secondary arms: a4c2 (amendment-2 pick) and a6c5 (Source-only
            # pick); Gen k(2) kept as the learning-OFF reference.
            by_id = {e["id"]: e["genome"] for e in st["archive"]}
            pol = {"always-ON": dict(A.GEN0_V3C), "always-OFF": dict(A.GEN0_V3C, online=False),
                   "Genk(2)": upgrade(prev["champion_2"], A), "Genk(adapt)": by_id["a0c2"],
                   "secondary:a4c2": by_id["a4c2"], "secondary:a6c5": by_id["a6c5"]}
        F.policies = lambda _st, _A: pol
        if a.phase == "table":
            R.claim("wave32", "dev2", list(DEV2), run_id="wave32a-table", record=False)
            st["dev_table" if "champion_v1" not in st else "dev_table_v2"] = F.table(ev, DEV2, st, A)
        else:
            R.claim("wave32", "confirm_adapt", list(CONF), run_id="wave32a-confirm")
            res = dict(frozen_policies=pol, table=F.table(ev, CONF, st, A))
            rows2, _, _ = F.run(ev, pol["Genk(adapt)"], (7218,), "Target", 3, "1")   # fixed: replay the FROZEN primary
            res["replay_7218_target3_adapt"] = W.digest(rows2) == res["table"]["Target/3rep"]["Genk(adapt)"]["per_seed"][7218]["digest"]
            res["D4_integrity"] = D.scan([], fp)["D4_integrity"]
            (ROOT / "artifacts/wave32_adaptive_confirm.json").write_text(json.dumps(res, sort_keys=True, default=repr))
            print("replay", res["replay_7218_target3_adapt"], "D4", res["D4_integrity"])
    STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"wave32a-{a.phase}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
