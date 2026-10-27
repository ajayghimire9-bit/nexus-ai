"""R2 reconciliation tests (NOT LOCKED; de4/dev only). Real final pipeline states (the correct pipeline run through ticks
1-14 by the harness, no repair operator) are corrupted in place and both reconcilers judge them; expected values never come
from the pipeline. Worlds: forced incidents none, and snapshot_interrupted@11 + clock_skew@13 (the R1 reproducer setting).
Mutations (each applied alone to a fresh copy of the final state):
  M1 count_preserving_substitution  a quarantine row's msg_id replaced by an accepted event's msg_id
  M2 changed_payload                an accepted telemetry event's stored event time moved by +1 h
  M3 duplicate_promoted             a duplicate delivery's ledger row marked applied (published accounting adjusted to match)
  M4 missing_event                  an accepted manifest's bronze row deleted
  M5 wrong_quarantine_reason        a malformed-weight quarantine row (and its ledger status) relabelled future_event
  M6 superseded_payload             a superseded (non-latest) order version's stored amount changed (silver unaffected)
Reported bounds: these 6 mutation kinds x the worlds below; nothing else is claimed.
  python scripts/r2_dev_reconcile.py OUT.json [seeds]"""
import json, shutil, sqlite3, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import r2_seeds, seed_registry as R  # noqa: F401
from nexus import r2_env as E2, r2_template as T2, r2_ops as RO2, r2_reconcile as R2R, r1_ops as R1O, s5_ops as O
from nexus.wave31_evaluator import ledger_append


def mutate(db, kind):
    con = sqlite3.connect(db)
    q = lambda s, a=(): con.execute(s, a).fetchall()
    done = False
    if kind == "M1":
        row = q("SELECT rowid, topic FROM quarantine LIMIT 1")
        acc = q("SELECT msg_id FROM _consumed WHERE status='applied' AND topic=(SELECT topic FROM quarantine LIMIT 1) LIMIT 1")
        if row and acc:
            con.execute("UPDATE quarantine SET msg_id=? WHERE rowid=?", (acc[0][0], row[0][0])); done = True
    elif kind == "M2":
        r = q("SELECT msg_id FROM bronze_tel WHERE future=0 LIMIT 1 OFFSET 3")
        if r:
            con.execute("UPDATE bronze_tel SET ets=strftime('%Y-%m-%dT%H:%M:%S', datetime(ets, '+1 hour')) WHERE msg_id=?", (r[0][0],)); done = True
    elif kind == "M3":
        r = q("SELECT rowid, topic FROM _consumed WHERE status='dup' LIMIT 1")
        if r:
            con.execute("UPDATE _consumed SET status='applied' WHERE rowid=?", (r[0][0],))
            con.execute("UPDATE record_accounting SET n=n+1 WHERE topic=? AND status='applied'", (r[0][1],))
            con.execute("UPDATE record_accounting SET n=n-1 WHERE topic=? AND status='duplicate'", (r[0][1],)); done = True
    elif kind == "M4":
        r = q("SELECT msg_id FROM bronze_man LIMIT 1 OFFSET 2")
        if r:
            con.execute("DELETE FROM bronze_man WHERE msg_id=?", (r[0][0],)); done = True
    elif kind == "M5":
        r = q("SELECT rowid, topic, msg_id FROM quarantine WHERE reason='malformed_weight' LIMIT 1")
        if r:
            con.execute("UPDATE quarantine SET reason='future_event' WHERE rowid=?", (r[0][0],))
            con.execute("UPDATE _consumed SET status='future' WHERE topic=? AND msg_id=?", (r[0][1], r[0][2])); done = True
    elif kind == "M6":
        r = q("SELECT b.msg_id FROM bronze_orders b WHERE b.payload != 'null' AND EXISTS (SELECT 1 FROM bronze_orders c WHERE "
              "c.key=b.key AND c.sv > b.sv) LIMIT 1")
        if r:
            pay = json.loads(q("SELECT payload FROM bronze_orders WHERE msg_id=?", (r[0][0],))[0][0])
            pay["amount"] = pay["amount"] + 7.0
            con.execute("UPDATE bronze_orders SET payload=? WHERE msg_id=?", (json.dumps(pay), r[0][0])); done = True
    con.commit(); con.close()
    return done


def main(outp, seeds):
    t0 = time.perf_counter()
    res = {}
    for seed in seeds:
        w = E2.make_world(seed, "dev")
        for tag, forced in (("none", []), ("si11_cs13", [("snapshot_interrupted", 11), ("clock_skew", 13)])):
            encs, incs = E2.ops_world(w, "dev", seed, forced=forced)
            work = Path(tempfile.mkdtemp(prefix="r2rc_"))
            b = work / "b"; b.mkdir()
            ch = T2.correct_choice()
            (b / "pipeline.py").write_text(T2.emit(ch)); (b / "config.json").write_text(json.dumps(T2.config_from_spec(w["spec"])))
            env, service = RO2.run_ops(encs, incs, work / "ops", b, O.RestartOnly("x"), ch)
            st = Path(env.rt["state"])
            if tag != "none":                                    # the harness alone does not repair: apply the guard + replay
                env.set_deploy("future_guard", True); env.rollback(12); env.runs_this_tick = 0
                for _ in range(4):
                    env.run_now()
            if (st / "snapshot_ctl").exists():
                pass
            base = work / "base.db"
            shutil.copy(st / "lake.db", base)
            row = {"clean": dict(r1=R1O.reconcile(env, w["spec"])[0], r2=R2R.reconcile(env, w["spec"])[0])}
            for kind in ("M1", "M2", "M3", "M4", "M5", "M6"):
                shutil.copy(base, st / "lake.db")
                if not mutate(st / "lake.db", kind):
                    row[kind] = "not_applicable"
                    continue
                ok2, ev2 = R2R.reconcile(env, w["spec"])
                row[kind] = dict(r1_flags=not R1O.reconcile(env, w["spec"])[0], r2_flags=not ok2,
                                 r2_fields=sorted(k for k, v in ev2.items() if v))
            shutil.copy(base, st / "lake.db")
            res[f"{w['spec']['project']}|{tag}"] = row
            print(seed, tag, {k: (v if isinstance(v, str) else (v.get("r1_flags", v.get("r1")), v.get("r2_flags", v.get("r2")))) for k, v in row.items()}, flush=True)
            O._rm(work)
    Path(outp).write_text(json.dumps(res, indent=1, sort_keys=True))
    ledger_append(dict(run="r2-dev-reconcile", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [971, 972, 973, 977])
