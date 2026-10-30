"""Phase 10C Stage 1A forensic audit of the 13 Phase 10B held-out Tier-3 targets unsolved by EVERY arm (NOT LOCKED).
  python scripts/agi10c_audit.py OUT.json
The Phase 10B agi10bde/eval targets are OPENED (claimed once in Phase 10B): they are development data here; no outcome is
rerun or rescored. Per target (and for the 7 solved held-out targets as a contrast):
  rows        decision / reason / work / wall per arm (from artifacts/agi10b_eval/rows_c*.jsonl, read only)
  witness     greedy truth-agreement witness (scripts/agi7_diag.witness): found?, depth in primitive edits, number of flat
              (neutral / worse) steps on it, stages touched
  ranker      share of root candidates whose rep0 / rep1 learned-ranker score is exactly 0 (every token unseen in training)
  macros      the rep0 / rep1 libraries bound at the root (skills6.SkillProposer): bound paths, paths passing ALL visible checks
              (the monolithic acceptance the method queue requires), paths making MODULAR progress (fewer failing stage tests /
              checks, no previously passing check lost)
PRIMARY CLASS (first match, declared before running): undecided_abstention (an arm reached a candidate and abstained on an
undecided requirement) | out_of_language (witness not found) | depth_exhaustion (witness depth >= 4) |
monolithic_macro (a bound library path makes modular progress but none passes all checks) | ranker_zeroing (>= 90 % of root
candidates score 0 under both rankers) | other. Every flag is reported, not only the primary class."""
import collections, glob, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import engines6 as E, pipeline6 as P6, skills6 as SK  # noqa: E402
from nexus.de_phase10 import guide10 as G, lineage10 as LN  # noqa: E402
from nexus.de_phase10b import fixes10b, manifest10b as MB, search10b  # noqa: E402,F401
import agi7_diag as WIT  # noqa: E402


def progress(ev0, ev):
    lost = set(ev0["passed"]) - set(ev["passed"])
    f0 = len(ev0["failed"]) + sum(map(len, ev0["stage_fail"]))
    f1 = len(ev["failed"]) + sum(map(len, ev["stage_fail"]))
    return not lost and not ev.get("error") and f1 < f0


def main(out):
    t0 = time.time()
    rows = [json.loads(l) for f in sorted(glob.glob(str(ROOT / "artifacts/agi10b_eval/rows_c*.jsonl"))) for l in open(f) if l.strip()]
    by = collections.defaultdict(dict)
    for r in rows:
        if r.get("arm") != "-":
            by[r["seed"]][r["arm"]] = r
    held = sorted(s for s, a in by.items() if a["A1"]["group"] == "heldout")
    fail = [s for s in held if not any(x["verified"] for x in by[s].values())]
    man = {t["seed"]: t for t in MB.eval_manifest()}
    cks = {r: json.loads((ROOT / f"artifacts/agi10b_train/{r}.final.json").read_text())["memory"] for r in ("rep0", "rep1")}
    W.SparkCode.warm()
    res = []
    for s in held:
        a = by[s]
        t = man[s]
        row = dict(seed=s, pid=a["A1"]["pid"], solved_by_any=s not in fail, faults=a["A1"]["faults"], undecided=a["A1"]["undecided"],
                   arms={k: dict(decision=v["decision"], reason=v["reason"], reachable=v["reachable"], work=v["cost"].get("work"), wall=v["cost"].get("wall_s"),
                                 mq=v.get("method_queue")) for k, v in sorted(a.items())})
        try:
            p = LN.build(t, s, ROOT / "var/agi10c_ws/audit", require=None)
            inv = P6.Inv6(p)
        except Exception as e:                                  # noqa: BLE001
            row["error"] = str(e)[:100]
            res.append(row)
            continue
        truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
        wit = WIT.witness(P6.Inv6(p), p, truths)
        row["witness"] = dict(found=wit["found"], depth=wit["depth"], flat=sum(x["kind"] in ("neutral", "worse") for x in wit["steps"]),
                              kinds=[x["kind"] for x in wit["steps"]], stages=sorted({x["stage"] for x in wit["steps"]}), ops=[x["op"] for x in wit["steps"]],
                              n_stages=len(p["stages"]))
        ev0 = inv.run(inv.legacy, True)
        cands = [(op, k, prm, inv.dom(k, inv.legacy)) for op in E.OPS for k in range(len(inv.stages))
                 for _, prm in E.candidates(op, inv.legacy[k], inv.dom(k, inv.legacy))]
        row["root_candidates"] = len(cands)
        row["ranker_zero_share"] = {}
        row["macros"] = {}
        for r, mem in cks.items():
            gw = (mem.get("guide") or {}).get("w") or {}
            z = sum(G.score(gw, G.tokens(op, k, prm, ev0["features"], d)) == 0 for op, k, prm, d in cands)
            row["ranker_zero_share"][r] = round(z / max(1, len(cands)), 3)
            sk = mem["de"]["skills"]
            paths = SK.SkillProposer().proposals(sk, inv, dict(specs=list(inv.legacy)), ev0) if sk else []
            allok = mod = 0
            stages = collections.Counter()
            for path in paths:
                ev = inv.run(P6.replay(inv, path), True)
                allok += bool(ev["ok"])
                if progress(ev0, ev):
                    mod += 1
                    stages.update({k for k, _, _ in path})
            row["macros"][r] = dict(library=len(sk), bound_paths=len(paths), pass_all_checks=allok, modular_progress=mod, progress_stages=dict(stages))
        flags = dict(undecided_abstention=any(v["reachable"] and v["decision"] != "submit" and a["A1"]["undecided"] for v in a.values()),
                     out_of_language=not wit["found"], depth_exhaustion=wit["found"] and wit["depth"] >= 4,
                     monolithic_macro=any(m["modular_progress"] > 0 and m["pass_all_checks"] == 0 for m in row["macros"].values()),
                     ranker_zeroing=all(z >= 0.9 for z in row["ranker_zero_share"].values()),
                     work_exhausted=all((v["cost"].get("work") or 0) >= 690 for v in a.values()),
                     wall_capped=any((v["cost"].get("wall_s") or 0) >= 5.5 for v in a.values()))
        row["flags"] = flags
        row["primary"] = next((k for k in ("undecided_abstention", "out_of_language", "depth_exhaustion", "monolithic_macro", "ranker_zeroing") if flags[k]), "other")
        res.append(row)
        print(s, row["pid"], "solved" if row["solved_by_any"] else "UNSOLVED", row["primary"], row["witness"]["depth"], row["witness"]["flat"],
              row["ranker_zero_share"], {r: (m["bound_paths"], m["pass_all_checks"], m["modular_progress"]) for r, m in row["macros"].items()}, flush=True)
    un = [r for r in res if not r["solved_by_any"]]
    summary = dict(n_unsolved=len(un), primary=collections.Counter(r["primary"] for r in un),
                   flags={f: sum(r.get("flags", {}).get(f, False) for r in un) for f in (un[0].get("flags") or {})},
                   witness_depth_unsolved=sorted(r["witness"]["depth"] for r in un if "witness" in r),
                   witness_depth_solved=sorted(r["witness"]["depth"] for r in res if r["solved_by_any"] and "witness" in r),
                   wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(dict(summary=summary, targets=res), indent=1, default=str))
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
