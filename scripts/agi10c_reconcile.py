"""Phase 10C log reconciliation of Phase 10 ('10A') / 10B method-admission and run-count claims (NOT LOCKED; reads committed
artifacts only, executes nothing).  python scripts/agi10c_reconcile.py OUT.json
  1 Phase 10 main lineage: candidates / promoted methods / promoted methods with partial-program (P*) support
    (artifacts/agi10_train/main.abstraction.jsonl; clone files main.mround.* are M* rollouts, counted separately)
  2 Phase 10B rep0 / rep1: promoted methods (rep*.abstraction.jsonl; clone files excluded) vs the final checkpoint libraries
  3 '197 -> 85': artifacts/agi10_dev/gate6.json screen rows [family, library verified, base verified, library work, base work]
  4 Phase 10B rep1 wrong training submission (P6.X2 seed 88021): what entered memory"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()] if Path(p).exists() else []


def lineage(prefix, final):
    ab = rows(ROOT / f"{prefix}.abstraction.jsonl")
    adm = [r for r in ab if r.get("admitted")]
    lib = json.loads(Path(final).read_text())["memory"]["de"]["skills"]
    return dict(candidates=len(ab), promoted=len(adm), promoted_with_partial_support=sum(bool(r.get("from_partial")) for r in adm),
                promoted_partial_only=sum(all("#partial" in s for s in r["support"]) for r in adm), promoted_multi_edit=sum(len(r["edits"]) > 1 for r in adm),
                promoted_valley=sum(bool(r.get("valley_crossing")) for r in adm), final_library=len(lib),
                final_library_from_partial=sum(bool(v.get("from_partial")) for v in lib.values()))


def main(out):
    res = {}
    res["phase10_main"] = lineage("artifacts/agi10_train/main", ROOT / "artifacts/agi10_train/main.N120.json")
    for tag in ("M0", "M_edit", "M_rand"):
        ab = rows(ROOT / f"artifacts/agi10_train/main.mround.{tag}.abstraction.jsonl")
        res[f"phase10_mround_{tag}"] = dict(candidates=len(ab), promoted=sum(bool(r.get("admitted")) for r in ab))
    for r in ("rep0", "rep1"):
        res[f"phase10b_{r}"] = lineage(f"artifacts/agi10b_train/{r}", ROOT / f"artifacts/agi10b_train/{r}.final.json")
    g = json.loads((ROOT / "artifacts/agi10_dev/gate6.json").read_text())
    scr = [dict(family=f, lib_verified=a, base_verified=b, lib_work=x, base_work=y) for f, a, b, x, y in g["screen"]]
    p6 = [s for s in scr if s["family"] == "P6"]
    res["gate6_phase10"] = dict(library_size=g["library_size"], screen_projects=len(scr), P6_projects=len(p6),
                                P6_rows=p6, P6_mean_lib_work=round(sum(s["lib_work"] for s in p6) / max(1, len(p6)), 1),
                                P6_mean_base_work=round(sum(s["base_work"] for s in p6) / max(1, len(p6)), 1),
                                non_P6_lib_minus_base={s["family"] + str(i): s["lib_work"] - s["base_work"] for i, s in enumerate(scr) if s["family"] != "P6"},
                                completion_changes=sum(s["lib_verified"] != s["base_verified"] for s in scr))
    pid = "P6.X2.P7_duckdb-P6_sqlite.88021"
    w = [r for r in rows(ROOT / "artifacts/agi10b_train/rep1.wake.jsonl") if r["project"] == pid]
    mem = json.loads((ROOT / "artifacts/agi10b_train/rep1.final.json").read_text())["memory"]
    res["phase10b_rep1_wrong_x2"] = dict(wake_row=w, skill_sources=sum(pid in s["project"] for s in mem["skill_src"]), ranker_pairs=sum(d["project"] == pid for d in mem["pairs"]),
                                         trust_records=sum(pid in json.dumps(t) for t in mem["trust"]["records"]), pstar_hypotheses=sum(pid in json.dumps(h) for h in mem["P"]["hypotheses"]),
                                         pstar_witness_log=sum(x.get("project") == pid for x in mem["P"]["witnesses"]),
                                         library_support=sum(pid in json.dumps(v.get("support")) for v in mem["de"]["skills"].values()))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, default=str)[:3500])


if __name__ == "__main__":
    main(*sys.argv[1:])
