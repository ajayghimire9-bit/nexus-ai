"""Phase 10G Stage 1 design check (NOT LOCKED; agi10gde/dev projects + the Phase 10F training project 104529 only; no learned
component, no evaluation target).  python scripts/agi10g_dev.py OUT.json
For one dev project per (mechanism, control): build cost (rejection attempts), the truth passes every acceptance rule (incl.
necessary_dedup), the dream teacher's truth path in the atomic substrate, its TIE SET, and for each channel alone: the resolution
outcome and whether the chosen survivor verifies on the hidden batches. Plus 104529: the accepted paths of the confirmed shape
re-checked under dag10g, and its truth."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10e import dag10e as D  # noqa: E402
from nexus.de_phase10f import atomic10f as AT, manifest10f as MF, world10f as W10F  # noqa: E402
from nexus.de_phase10g import dag10g as DG, ev10g as EV, lineage10g as LG, manifest10g as MG  # noqa: E402

CASES = [("S_replay", "seq"), ("S_qualify_order", "time"), ("S_fanout", "grain"), ("S_replay", None), ("S_qualify_order", None), ("S_fanout", None),
         ("W3", "time"), ("W5", "grain"), ("T_tombstone+qualify_order", "time"), ("W1", "seq")]


def main(out):
    t0 = time.time()
    base = MG.RANGES[("agi10gde", "dev")].start
    rows = []
    with AT.atomic():
        for i, (fam, amb) in enumerate(CASES):
            faults = list(MG.WITHHELD[fam][0]) if fam in MG.WITHHELD else list(MG.TRAIN_FAMILIES[fam])
            spec = dict(family=fam, faults=faults, amb=amb, engine=MG.ENGINES[i % 3], legacy=MG.legacy_for(faults, i), names="heldout" if i % 2 else "base")
            tb = time.time()
            p = LG.build(spec, base + i, ROOT / "var/agi10g_ws/devcheck")
            build_s = round(time.time() - tb, 2)
            inv = LG.inv_for(p)
            truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
            tr_ok = inv.run([truth[n] for n in D.NODES], True)
            path, found = LG.witness(inv, truth)
            C, sigs = EV.tie_set(inv, path) if found else ([], [])
            per = {}
            for e in range(1, EV.K + 1):
                if len(C) > 1:
                    res = EV.resolve(inv, C, [e], 1)
                    per[e] = dict(outcome=res["outcome"], eliminated=res["requests"][0]["eliminated"],
                                  verified=LG.verify_hidden(p, res["chosen"][1])["ok"] if res["chosen"] else None)
            rows.append(dict(project=p["pid"], amb=amb, attempt=p["attempt"], build_s=build_s, truth_ok=tr_ok["ok"], truth_failed=tr_ok["failed"],
                             witness_found=found, path=[list(e) for e in path], tie=len(C), tie_ops=sorted({s["op"] for s in sigs}),
                             features=EV.features(sigs, len(C)) if len(C) > 1 else [], E2=EV.order_E2(sigs) if sigs else None, channels=per))
            print(rows[-1]["project"], "tie", len(C), {e: (v["outcome"][:9], v["verified"]) for e, v in per.items()}, "truth_ok", tr_ok["ok"], "build", build_s, "att", p["attempt"], flush=True)
    d = json.loads((ROOT / "artifacts/agi10g_diag_104529.json").read_text())
    p = W10F.make_project10d(MF.train_spec(1, 29), 104529, ROOT / "var/agi10g_ws/diag")
    i10g = DG.Inv10g(p)
    acc = [(r["path"], r["hidden"]["ok"]) for r in d["wrong_paths"]] + [(pp, True) for pp in d["correct_paths"]]
    still = [(pp, ok) for pp, ok in acc if i10g.run(D.replay(i10g, [(0, "add_partition", pp[0]), (0, "add_filter", pp[1]), (0, "set_dedup", pp[2])]), True)["ok"]]
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    clos = dict(rechecked=len(acc), wrong_in_recheck=sum(not ok for _, ok in acc), accepted_under_10g=len(still), wrong_accepted_under_10g=sum(not ok for _, ok in still),
                truth_ok_under_10g=i10g.run([truth[n] for n in D.NODES], True)["ok"])
    summ = dict(cases=len(rows), truth_false_rejects=sum(not r["truth_ok"] for r in rows),
                designed_ties=sum(r["tie"] > 1 for r in rows if r["amb"]), designed=sum(1 for r in rows if r["amb"]),
                incidental_ties=sum(r["tie"] > 1 for r in rows if not r["amb"]), controls=sum(1 for r in rows if not r["amb"]),
                relevant_channel_resolves_and_verifies=sum(bool(r["channels"]) and r["channels"][{"seq": 1, "time": 2, "grain": 3}[r["amb"]]]["verified"] is True for r in rows if r["amb"]),
                irrelevant_channel_resolutions=sum(v["outcome"] == "resolved" for r in rows if r["amb"] for e, v in r["channels"].items() if e != {"seq": 1, "time": 2, "grain": 3}[r["amb"]]),
                closure_104529=clos, wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(dict(summary=summ, rows=rows), indent=1, default=str))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
