"""Phase 10F Stage 1 design checks (NOT LOCKED; agi10fde/dev projects + the Phase 10E training project 101524 only; no
search, no training, no evaluation target).  python scripts/agi10f_dev.py OUT.json
  GENERATOR (world10f)  on dev projects of every training family and every held-out composition: replayed items whose later
                        version has a LOWER quantity (share of replay corrections), projects where the quantity alias passes
                        visible checks / changes a hidden batch, and how often the quantity column still carries the `arrival` role
  RULES (dag10f)        the truth passes every acceptance rule (incl. justified_dedup) on every dev project: false rejects
  101524 CLOSURE        every json_coalesce_before -> add_partition -> add_filter path that is `ok` under Phase 10E acceptance, re-checked
                        under dag10f: how many remain ok, and are any of them hidden-wrong
  ATOMIC SUBSTRATE      on the replay dev projects: the truth dedup is ONE atomic set_dedup candidate (atomic10f), and its position in the
                        fixed root order"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import ir10d as IR, world10d as W10D  # noqa: E402
from nexus.de_phase10e import dag10e as D, manifest10e as ME  # noqa: E402
from nexus.de_phase10f import atomic10f as AT, dag10f as DF, manifest10f as MF, world10f as W  # noqa: E402
from nexus.de_phase10e import search10e as SD  # noqa: E402


def main(out):
    t0 = time.time()
    base = MF.RANGES[("agi10fde", "dev")].start
    fams = [(f, list(fs)) for f, fs in sorted(MF.TRAIN_FAMILIES.items())] + [(h, list(fs)) for h, fs in sorted(MF.HELD.items())]
    gen, rules, atomic = [], [], []
    for i, (fam, faults) in enumerate(fams):
        spec = dict(family=fam, faults=faults, engine=MF.ENGINES[i % 3], legacy=MF.legacy_for(faults, i), names="base" if i % 2 else "heldout")
        p = W.make_project10d(spec, base + i, ROOT / "var/agi10f_ws/devcheck")
        inv = DF.Inv10f(p)
        truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
        tr = [truth[n] for n in D.NODES]
        ev = inv.run(tr, True)
        rules.append(dict(project=p["pid"], truth_ok=ev["ok"], failed=ev["failed"]))
        nm = p["names"]
        items = [W.read_csv(Path(p["ws"]) / "data" / f"{b}order_items.csv") for b in ("", "b/")]
        corr = dec = 0
        for rows in items:
            g = {}
            for r in rows:
                g.setdefault(r[nm["iid"]], []).append((int(r[nm["seq"]]), int(r[nm["qty"]])))
            for v in g.values():
                if len(v) > 1:
                    corr += 1
                    dec += sorted(v)[-1][1] < sorted(v)[0][1]
        alias = W.quantity_alias(truth, nm)
        dom = inv.dom(0, inv.legacy)
        row = dict(project=p["pid"], family=fam, replay="replay" in faults, corrections_visible=corr, decreasing_visible=dec,
                   alias_visible_fails=any(W.visible_fail(alias, truth, *b[:2], nm) for b in [(inv.batches[0][0], inv.batches[0][1]), (inv.batches[1][0], inv.batches[1][1])]),
                   alias_hidden_ok=D.verify_hidden(p, [alias[n] for n in D.NODES])["ok"],
                   qty_has_arrival_role="arrival" in dom.roles("stg_order_items", nm["qty"]) if "stg_order_items" in inv.legacy[0] else None,
                   seq_has_arrival_role="arrival" in dom.roles("stg_order_items", nm["seq"]) if "stg_order_items" in inv.legacy[0] else None)
        gen.append(row)
        if "replay" in faults:
            want = truth["stg"]["stg_order_items"]["dedup"]
            with AT.atomic():
                node = dict(specs=[dict(s) for s in inv.legacy], ev=inv.run(inv.legacy, True))
                cands = SD.candidates(inv, dict(de=dict(skills={})), node, "whole")
                pos = next((j for j, c in enumerate(cands) if c["k"] == 0 and c["s2"]["stg_order_items"].get("dedup") == want), None)
                n_ap = sum(c["op"] == "add_partition" for c in cands)
            split = SD.candidates(inv, dict(de=dict(skills={})), dict(specs=inv.legacy, ev=node["ev"]), "whole")
            atomic.append(dict(project=p["pid"], atomic_truth_root_position=pos, atomic_root_candidates=len(cands), add_partition_offered_in_atomic=n_ap,
                               split_partition_offered=sum(c["op"] == "add_partition" for c in split)))
    # 101524 closure (Phase 10E generator: the original training project)
    p = W10D.make_project10d(ME.train_spec(1, 24), 101524, ROOT / "var/agi10f_ws/diag")
    i10e, i10f = D.Inv10e(p), DF.Inv10f(p)
    clos = dict(ok_10e=0, ok_10f=0, wrong_ok_10e=0, wrong_ok_10f=0)
    for s1, p1 in D.candidates("json_coalesce_before", i10e.legacy[0], i10e.dom(0, i10e.legacy)):
        sp1 = [s1] + i10e.legacy[1:]
        for s2, p2 in D.candidates("add_partition", s1, i10e.dom(0, sp1)):
            sp2 = [s2] + sp1[1:]
            for s3, p3 in D.candidates("add_filter", s2, i10e.dom(0, sp2)):
                sp3 = [s3] + sp2[1:]
                if i10e.run(sp3, True)["ok"]:
                    h = D.verify_hidden(p, sp3)["ok"]
                    clos["ok_10e"] += 1
                    clos["wrong_ok_10e"] += not h
                    if i10f.run(sp3, True)["ok"]:
                        clos["ok_10f"] += 1
                        clos["wrong_ok_10f"] += not h
    rep = [g for g in gen if g["replay"]]
    summ = dict(projects=len(gen), truth_false_rejects=sum(not r["truth_ok"] for r in rules),
                replay_projects=len(rep), replay_corrections_visible=sum(g["corrections_visible"] for g in gen), decreasing_share_visible=round(sum(g["decreasing_visible"] for g in gen) / max(1, sum(g["corrections_visible"] for g in gen)), 3),
                replay_projects_alias_visible_fails=sum(g["alias_visible_fails"] for g in rep), replay_projects_alias_hidden_wrong=sum(not g["alias_hidden_ok"] for g in rep),
                qty_arrival_role=sum(bool(g["qty_has_arrival_role"]) for g in gen), seq_arrival_role_replay=sum(bool(g["seq_has_arrival_role"]) for g in rep),
                closure_101524=clos, atomic_truth_reachable=sum(a["atomic_truth_root_position"] is not None for a in atomic),
                atomic_truth_position_median=sorted(a["atomic_truth_root_position"] for a in atomic if a["atomic_truth_root_position"] is not None)[len(atomic) // 2] if atomic else None,
                wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(dict(summary=summ, generator=gen, rules=rules, atomic=atomic), indent=1, default=str))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
