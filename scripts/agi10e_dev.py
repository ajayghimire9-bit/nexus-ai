"""Phase 10E Stage 1 development checks on the amended substrate (NOT LOCKED; agi10ede/dev seeds only, never a target).
  python scripts/agi10e_dev.py OUT.json [N_PER]
For development projects of every family (training families + held-out replay compositions, dev seeds 100000+):
  truth_ok        the generator's truth passes every visible check, contract and BOTH Phase 10E acceptance rules (a rule that
                  rejects the truth would be a false rejection)
  legacy_rules    acceptance-rule violations of the faulty legacy (expected on tomb_early: tombstone filter before dedup)
On replay projects additionally:
  key_roles / order_roles      Phase 10E roles of the truth's dedup key and order column
  key_twins / order_twins      add_partition (resp. set_dedup order) candidates whose role-form edit equals the truth's
  interim_rule                 add_partition(truth key) alone violates deterministic_dedup (the 2-step path is enforced)
  two_step_visible / _hidden   add_partition(key) -> set_dedup(order) passes visibly / verifies on the hidden batches
  A1                           fixed-guide L0 search10e (600 executions, 4 s): outcome, work, verified"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import world10d as W  # noqa: E402
from nexus.de_phase10e import dag10e as D, lineage10e as LE, manifest10e as ME  # noqa: E402


def main(out, n_per="1"):
    n_per = int(n_per)
    fams = sorted(ME.TRAIN_FAMILIES) + sorted(ME.HELD)
    rows, seed = [], ME.RANGES[("agi10ede", "dev")].start
    for f in fams:
        faults = list(ME.TRAIN_FAMILIES.get(f) or ME.HELD[f])
        for j in range(n_per if ("replay" in faults) else 1):
            spec = dict(family=f, faults=faults, engine=("duckdb", "sqlite", "polars")[seed % 3], legacy=ME.legacy_for(faults, seed), names="base")
            try:
                p = W.make_project10d(spec, seed, ROOT / "var/agi10e_ws/dev")
            except RuntimeError:
                rows.append(dict(family=f, seed=seed, build=False))
                seed += 1
                continue
            inv = D.Inv10e(p)
            truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
            tr = [truth[n] for n in D.NODES]
            r = dict(family=f, seed=seed, n_cols=p["n_cols"], truth_ok=inv.run(tr, True)["ok"], truth_rules=inv.rules(tr), legacy_rules=inv.rules(inv.legacy))
            if "replay" in faults:
                rel = "stg_order_items"
                want = truth["stg"][rel]["dedup"]
                kc, oc = want["key"][1][1], want["order"][1][1]
                start = [dict(s) for s in inv.legacy]
                if "dirty" in faults:
                    start[0] = dict(start[0], stg_orders=dict(start[0]["stg_orders"], pre=truth["stg"]["stg_orders"]["pre"]))
                dom = inv.dom(0, start)
                r.update(key_roles=dom.roles(rel, kc), order_roles=dom.roles(rel, oc))
                ap = [(s, prm) for s, prm in D.candidates("add_partition", start[0], dom) if prm.startswith(rel + "|")]
                t_ap = f"{rel}|{kc}"
                a_abs = D.abstract_edit("add_partition", t_ap, dom)
                r["key_twins"] = sum(D.abstract_edit("add_partition", prm, dom) == a_abs for _, prm in ap) - 1
                mid = D.replay(inv, [(0, "add_partition", t_ap)], start)
                r["interim_rule"] = inv.rules(mid)
                dom2 = inv.dom(0, mid)
                sd = [(s, prm) for s, prm in D.candidates("set_dedup", mid[0], dom2) if prm.startswith(rel + "|")]
                t_sd = next(prm for s, prm in sd if s[rel]["dedup"] == want)
                s_abs = D.abstract_edit("set_dedup", t_sd, dom2)
                r["order_twins"] = sum(D.abstract_edit("set_dedup", prm, dom2) == s_abs for _, prm in sd) - 1
                r["set_dedup_pos"] = [prm for _, prm in sd].index(t_sd)
                fin = D.replay(inv, [(0, "set_dedup", t_sd)], mid)
                r["two_step_visible"] = inv.run(fin, True)["ok"]
                r["two_step_hidden"] = D.verify_hidden(p, fin)["ok"]
                inv2, res, ver, wrong = LE.investigate(p, LE.memory())
                r["A1"] = dict(outcome=res["outcome"], work=res["work"], verified=ver, wrong=wrong, path=[e[1] for e in (res.get("path") or [])])
            rows.append(r)
            print(json.dumps(r, default=list), flush=True)
            seed += 1
    rep = [r for r in rows if "A1" in r]
    summ = dict(projects=len(rows), truth_ok=sum(r.get("truth_ok", False) for r in rows), truth_rule_violations=sum(bool(r.get("truth_rules")) for r in rows),
                replay_projects=len(rep), ckey_on_truth_key=sum("ckey" in r["key_roles"] for r in rep), arrival_on_truth_order=sum("arrival" in r["order_roles"] for r in rep),
                interim_rejected=sum(bool(r["interim_rule"]) for r in rep), two_step_visible=sum(r["two_step_visible"] for r in rep),
                two_step_hidden=sum(r["two_step_hidden"] for r in rep),
                A1_verified={f: sum(r["A1"]["verified"] for r in rep if r["family"] == f) for f in sorted({r["family"] for r in rep})},
                A1_wrong=sum(r["A1"]["wrong"] for r in rep))
    Path(out).write_text(json.dumps(dict(summary=summ, rows=rows), indent=1, default=list))
    print("SUMMARY", json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
