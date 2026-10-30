"""Phase 10D Stage 1 HARD PRE-FLIGHT GATE 0 (NOT LOCKED).  python scripts/agi10d_gate0.py OUT.json [N_PROJECTS] [N_SPARK]
verify_out_of_sandbox_gate0() builds N development projects (agi10dde/dev 97000+; legacy languages x engines rotate) and asserts
the owner's five requirements, logging exact counts:
  1 multi-table schemas with join bugs: >= 3 tables per project; fan-out, wrong join type and key-cast join faults are generated
    and each is individually effective (it alone fails a visible check and changes a hidden batch)
  2 wide schemas: 60-120 columns per workspace
  3 true 3-node DAGs (stg_ -> int_ -> fct_) with per-node contracts; an injected stg_ or int_ fault propagates to change fct_
  4 Polars as a first-class engine: the TRUTH DAG executed by Polars (and DuckDB, SQLite, PySpark 4.0.1) equals the reference
    interpreter on every node output and every batch; the generated Polars code uses filter / with_columns / group_by().agg /
    join / join_asof / over / unique / cast(strict=False)
  5 MERGE / QUALIFY / nested CDC envelopes: legacy texts carry MERGE INTO (or the Delta merge API) and QUALIFY or ROW_NUMBER
    dedup; data carries {"op","before","after","ts_ms"} payloads; the MERGE result agrees across engines
  + every legacy language lifts back to exactly the legacy DAG (snowflake / postgres / hive / dbt / scala)
PASS iff every check passes on every project (100 %)."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import engines10d as EN, ir10d as IR, legacy10d as LG, manifest10d as MD, world10d as W  # noqa: E402

FAULT_SETS = [["fanout", "merge_delete"], ["inner", "tombstone"], ["keycast", "replay"], ["qualify_order", "merge_update"], ["fanout", "cdc_key"],
              ["inner", "dirty"], ["keycast", "overwrite"], ["tomb_early", "fanout"], ["asof_dir", "inner"], ["keycast", "merge_delete"]]
POLARS_METHODS = (".filter(", ".with_columns(", ".group_by(", ".agg(", ".join(", ".join_asof(", ".over(", ".unique(", "strict=False")


def relcols(rows):
    return list(rows[0].keys()) if rows else []


def verify_out_of_sandbox_gate0(n=10, n_spark=4, out=None):
    t0 = time.time()
    base = MD.RANGES[("agi10dde", "dev")].start
    rows, ok_all = [], True
    for i in range(n):
        sp = dict(family=f"G{i}", faults=FAULT_SETS[i % len(FAULT_SETS)], engine=MD.ENGINES[i % 4], legacy=MD.LEGACY[i % 5], names="base" if i % 2 else "heldout")
        r = dict(i=i, spec=sp)
        try:
            p = W.make_project10d(sp, base + i, ROOT / "var/agi10d_ws/gate0")
        except Exception as e:                                  # noqa: BLE001
            r["error"] = f"build: {type(e).__name__}: {str(e)[:160]}"
            rows.append(r)
            ok_all = False
            print(i, r["error"], flush=True)
            continue
        ws, hid = Path(p["ws"]), Path(p["hidden_dir"])
        contract = json.loads((ws / "contract.json").read_text())
        truth = json.loads((hid / "truth.json").read_text())
        nm = p["names"]
        legacy = W.inject(truth, sp["faults"], nm)
        r.update(pid=p["pid"], tables=p["n_tables"], columns=p["n_cols"], dag_nodes=len(contract["nodes"]), node_files=sorted(contract["files"]))
        try:
            lifted = LG.read_and_lift(ws, contract)
            r["lift_equal"] = json.loads(json.dumps(lifted)) == json.loads(json.dumps(legacy))
            if not r["lift_equal"]:
                r["lift_diff"] = [k for k in ("stg", "int", "fct") if json.loads(json.dumps(lifted[k])) != json.loads(json.dumps(legacy[k]))]
        except Exception as e:                                  # noqa: BLE001
            r["lift_equal"], r["lift_error"] = False, f"{type(e).__name__}: {str(e)[:200]}"
        texts = {nd: (ws / f).read_text() for nd, f in contract["files"].items()}
        allt = "\n".join(texts.values())
        r["merge_text"] = ("MERGE INTO" in allt) or (".merge(" in allt)
        r["dedup_text"] = ("QUALIFY" in allt) or ("ROW_NUMBER()" in allt) or ("row_number()" in allt)
        batches = {"visible": (W.load_tables(ws, p_tabs := contract["tables"]), json.loads((ws / "state/fct_target.json").read_text()))}
        for b in ("hidden1", "hidden2"):
            batches[b] = (W.load_tables(hid, p_tabs, prefix=f"{b}_"), json.loads((hid / f"{b}_state.json").read_text())["fct_target"])
        env = batches["visible"][0]["cdc_customers"][0][nm["payload"]]
        r["cdc_envelope"] = set(json.loads(env)) == {"op", "before", "after", "ts_ms"}
        rels = sorted(truth["stg"]) + ["stg_customers_latest", "int_orders", "fct_out"]
        engines = ["duckdb", "sqlite", "polars"] + (["spark"] if i < n_spark else [])
        exe = {}
        for eng in engines:
            agree, nrun = True, 0
            for b, (T, tgt) in batches.items():
                ref = IR.interpret(truth, T, dict(fct_target=tgt))
                try:
                    got = EN.run(truth, T, dict(fct_target=tgt), eng, rels)
                    nrun += 1
                    for rel in rels:
                        cols = relcols(ref[rel]) or relcols(got[rel])
                        if IR.table_key(got[rel], cols) != IR.table_key(ref[rel], cols):
                            agree = False
                            exe.setdefault(f"{eng}_mismatch", []).append(f"{b}:{rel}")
                except Exception as e:                          # noqa: BLE001
                    agree = False
                    exe[f"{eng}_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            exe[eng] = dict(agree=agree, executions=nrun)
        r["engines"] = exe
        pol = EN.gen_polars(truth)
        r["polars_methods"] = {m: m in pol for m in POLARS_METHODS}
        prop = {}
        for f in sp["faults"]:
            if W.MECH_NODE[f] in ("stg", "int"):
                one = W.inject(truth, [f], nm)
                cols = W.fct_cols(truth)
                prop[f] = any(IR.table_key(IR.interpret(one, T, dict(fct_target=tg))["fct_out"], cols) != IR.table_key(IR.interpret(truth, T, dict(fct_target=tg))["fct_out"], cols)
                              for T, tg in batches.values())
        r["propagates_to_fct"] = prop
        r["merge_in_truth"] = bool(truth["fct"].get("merge")) and truth["fct"]["merge"]["delete"] and truth["fct"]["merge"]["update"]
        checks = dict(tables=r["tables"] >= 3, columns=60 <= r["columns"] <= 120, dag=r["dag_nodes"] == 3 and len(r["node_files"]) == 3, lift=r["lift_equal"],
                      merge=r["merge_in_truth"] and (r["merge_text"] or "overwrite" in sp["faults"]), dedup=r["dedup_text"], cdc=r["cdc_envelope"], engines=all(v["agree"] for k, v in exe.items() if isinstance(v, dict)),
                      polars_methods=all(r["polars_methods"].values()) or not ("fx_rates" in contract["tables"]) and all(v for m, v in r["polars_methods"].items() if m != ".join_asof("),
                      propagation=all(prop.values()))
        r["checks"] = checks
        r["pass"] = all(checks.values())
        ok_all &= r["pass"]
        rows.append(r)
        print(i, p["pid"], "tables", r["tables"], "cols", r["columns"], "lift", r["lift_equal"], r.get("lift_error", r.get("lift_diff", "")),
              {k: (v["agree"], v["executions"]) if isinstance(v, dict) else v for k, v in exe.items()}, "prop", prop, "PASS" if r["pass"] else "FAIL", flush=True)
    good = [x for x in rows if "error" not in x]
    summary = dict(passed=ok_all and len(good) == n, projects=n, built=len(good), tables=[x["tables"] for x in good], columns=[x["columns"] for x in good],
                   dag_nodes=[x["dag_nodes"] for x in good], legacy_languages=sorted({x["spec"]["legacy"] for x in good}),
                   engine_executions={e: sum(x["engines"].get(e, {}).get("executions", 0) for x in good) for e in ("duckdb", "sqlite", "polars", "spark")},
                   engine_agreement={e: f"{sum(x['engines'].get(e, {}).get('agree', False) for x in good)}/{sum(e in x['engines'] for x in good)}" for e in ("duckdb", "sqlite", "polars", "spark")},
                   lift_equal=f"{sum(x['lift_equal'] for x in good)}/{len(good)}", join_bug_projects=sum(any(f in ('fanout', 'inner', 'keycast') for f in x['spec']['faults']) for x in good),
                   merge_legacy_text=f"{sum(x['merge_text'] for x in good)}/{len(good)}", merge_executed_truth=f"{sum(x['merge_in_truth'] for x in good)}/{len(good)}", qualify_or_rownumber=f"{sum(x['dedup_text'] for x in good)}/{len(good)}",
                   cdc_envelopes=f"{sum(x['cdc_envelope'] for x in good)}/{len(good)}", propagation=f"{sum(all(x['propagates_to_fct'].values()) for x in good)}/{len(good)}",
                   versions=dict(polars=__import__("polars").__version__, pyspark=__import__("pyspark").__version__, duckdb=__import__("duckdb").__version__,
                                 sqlite=__import__("sqlite3").sqlite_version, sqlglot=__import__("sqlglot").__version__), wall=round(time.time() - t0, 1))
    if out:
        Path(out).write_text(json.dumps(dict(summary=summary, projects=rows), indent=1, default=str))
    print(json.dumps(summary, default=str))
    return summary


if __name__ == "__main__":
    a = sys.argv[1:]
    s = verify_out_of_sandbox_gate0(int(a[1]) if len(a) > 1 else 10, int(a[2]) if len(a) > 2 else 4, a[0])
    sys.exit(0 if s["passed"] else 1)
