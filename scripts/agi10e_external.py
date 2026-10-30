"""Phase 10E Stage 4: external DEV-audit re-test after the general loader / multi-table binder (NOT LOCKED; diagnostic only:
trains nothing; the same 16 tasks as scripts/agi10c_external.py, texts AS WRITTEN, no human adapter, no per-task rule).
  python scripts/agi10e_external.py OUT.json
FUNNEL per task (pre-registered in docs/NEXUS_PHASE10E_PROTOCOL.md):
  ingested     de_phase10e.extload10e parses the text in its language and binds every relation it reads to a provided table
  expressible  the bound legacy lifts into the stage IR (extload10e stage 'ok')
  reached      a project is built (visible = first rows; public checks = the reference's example rows + row count on them) and
               search10c under the Phase 10C A1 configuration (fixed guide, L0, 1,500 executions, 4 s) SUBMITS a candidate that
               passes every public check; needs a reference repair (T13 / T02 / T04 / T06 / T07 / T14 have none)
  verified     the submitted candidate equals the reference on ALL rows (DuckDB); a submitted but wrong candidate is a WRONG
               repair (verifier gap)
The Phase 10C results (artifacts/agi10c_external.json) are reported alongside; nothing of Phase 10C is rerun or changed."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import engines6 as E, ir6, pipeline6 as P6  # noqa: E402
from nexus.de_phase10c import lineage10c as LC, search10c as S10  # noqa: E402
from nexus.de_phase10e import extload10e as X  # noqa: E402
import agi10c_external as EXT  # noqa: E402
import agi10c_train as TRN  # noqa: E402


def project(t, L, root):
    rs = L.input_rows
    vis = rs[:t.get("visible_n", 14)]
    cols, out_v = EXT.reference(t, vis) if len(t["tables"]) == 1 else (None, None)
    _, out_all = EXT.reference(t, rs)
    ws, hid = Path(root) / t["id"] / "workspace", Path(root) / t["id"] / "hidden"
    for d in (ws / "data", ws / "pipeline", ws / "models", ws / "docs", hid):
        d.mkdir(parents=True, exist_ok=True)
    W.write_csv(ws / "data" / "visible.csv", L.header, vis)
    (ws / "pipeline" / "stage1.sql").write_text(X.lower_stage(L.stages[0]))
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=cols, rows=out_v), dict(kind="row_count", n=len(out_v))]
    (ws / "contract.json").write_text(json.dumps(dict(output_cols=cols, unique_key=None, public_checks=checks, quarantine_table=None, requirements=[],
                                                      stages=[dict(file="pipeline/stage1.sql", paradigm="EXT", engine="duckdb", legacy_language="sql",
                                                                   target_language="duckdb", model="stage1")]), default=str))
    return dict(pid=f"EXT10E.{t['id']}", ws=str(ws), hidden_dir=str(hid), stages=[dict(engine="duckdb", target_lang="duckdb", in_cols=L.header)], undecided=[]), cols, out_all


def main(out):
    t0 = time.time()
    old = {r["id"]: r for r in json.loads((ROOT / "artifacts/agi10c_external.json").read_text())["tasks"]}
    mem = LC.arm_memory(TRN.fixed_trust()[0])
    res = []
    for t in EXT.TASKS:
        L = X.load(t["legacy"], t["lang"], t["tables"])
        r = dict(id=t["id"], pattern=t["pattern"], lang=t["lang"], tables=len(t["tables"]), phase10c_class=old[t["id"]]["class"],
                 phase10c_native_lift=old[t["id"]]["native_lift"], loader_stage=L.stage, loader_error=L.error, loader_notes=L.notes, n_stages=len(L.stages),
                 ingested=L.stage in ("express", "ok"), expressible=L.ok, has_reference=bool(t["ref"]), reached=False, verified=False, wrong=False)
        if L.ok and t["ref"] and len(L.stages) == 1:
            try:
                p, cols, out_all = project(t, L, ROOT / "var/agi10e_ws/external")
                inv = P6.Inv6(p)
                sr = S10.search(inv, mem, LC.WORK, LC.WALL)
                r["search"] = dict(outcome=sr["outcome"], path=sr["path"], work=sr["work"])
                if sr["outcome"] == "submitted":
                    r["reached"] = True
                    code = ir6.lower(sr["specs"][0], "duckdb")
                    try:
                        got = E.ENGINES["duckdb"]().run(code, L.header, L.input_rows, {})["clean"]
                        ok = W.table_key(got, cols) == W.table_key([dict(zip(cols, x)) for x in out_all], cols)
                    except Exception as e:                       # noqa: BLE001
                        ok, r["hidden_err"] = False, f"runtime {type(e).__name__}"
                    r["verified"], r["wrong"] = ok, not ok
            except Exception as e:                               # noqa: BLE001
                r["project_error"] = f"{type(e).__name__}: {str(e)[:140]}"
        r["first_stop"] = ("verified" if r["verified"] else "wrong repair" if r["wrong"] else "search (no candidate)" if r.get("search") else
                           "no reference repair" if L.ok and not t["ref"] else "project build" if r.get("project_error") else
                           f"not expressible: {L.error}" if L.stage == "express" else f"{L.stage}: {L.error}")
        res.append(r)
        print(t["id"], t["lang"], L.stage, "| expressible", L.ok, "| reached", r["reached"], "| verified", r["verified"], "|", r["first_stop"][:90], flush=True)
    summ = dict(total=len(res), ingested=sum(r["ingested"] for r in res), expressible=sum(r["expressible"] for r in res),
                expressible_with_reference=sum(r["expressible"] and r["has_reference"] for r in res), reached=sum(r["reached"] for r in res),
                verified=sum(r["verified"] for r in res), wrong=sum(r["wrong"] for r in res),
                phase10c=dict(native_lifted=sum(o["native_lift"] for o in old.values()), solved_behind_adapter=sum(str(o.get("level2_class")) == "solved" for o in old.values())),
                wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(dict(summary=summ, tasks=res), indent=1, default=str))
    print(json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
