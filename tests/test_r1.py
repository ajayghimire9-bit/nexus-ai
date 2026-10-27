"""R1 unit tests (no experiment is executed: hand-written mini logs and synthetic observations only; the X1 / X2 generators
are never called)."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from nexus import r1_seeds  # noqa: F401
from nexus import r1_checks as RC, r1_env as RE, r1_monitor as M, r1_template as RT, s4_checks as C, s4_env as E
from nexus import seed_registry as R

T1 = "2026-04-01T02:00:00Z"


def _spec():
    return RE.make_world(951, "dev")["spec"]


def _reg(spec, off):
    n = spec["physical_names_v1"]
    return dict(msg_id="reg-orders-1", ingest_ts="2026-04-01T00:01:00Z", subject="orders", version=1, fields=n,
                types={"discount": "int"}, offset=off)


def _cdc(spec, key, sv, status, off, mid, **kw):
    n = spec["physical_names_v1"]
    after = {n["order_id"]: key, n["warehouse_id"]: "W1", n["status"]: status, n["amount"]: 100.0, n["currency"]: "USD",
             n["discount"]: 0, n["promised_ts"]: "2026-04-05T00:00:00Z", n["deleted"]: 0}
    return dict(msg_id=mid, ingest_ts=T1, op="c" if sv == 1001 else "u", event_ts=T1, key=key, schema_version=1,
                source_version=sv, after=after, offset=off, **kw)


def _write(d, topic, part, recs):
    p = Path(d) / topic / f"p{part}"
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{recs[0]['offset']:08d}.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs))


def _run(tmp, choice, spec, log, st, tick=1):
    b = tmp / "b"
    b.mkdir(exist_ok=True)
    (b / "pipeline.py").write_text(RT.emit(choice))
    (b / "config.json").write_text(json.dumps(RT.config_from_spec(spec)))
    r = subprocess.run([sys.executable, str(b / "pipeline.py"), "--log", str(log), "--state", str(st), "--config",
                        str(b / "config.json"), "--tick", str(tick)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    con = sqlite3.connect(st / "lake.db")
    silver = {k: s for k, s in con.execute("SELECT order_id, status FROM silver_orders")}
    cons = {o: s for o, s in con.execute("SELECT offset, status FROM _consumed WHERE topic='orders_cdc'")}
    con.close()
    return silver, cons


def test_template_patches_apply_and_compile():
    assert set(RT.DECISIONS) == set(C.IMPLICATE.get("x", [])) | set(RT.DECISIONS)
    assert {"txn_isolation", "gap_handling"} <= set(RT.DECISIONS)
    for ch in (RT.correct_choice(), {d: o[0] for d, o in RT.DECISIONS.items()}):
        compile(RT.emit(ch), "pipeline.py", "exec")


@pytest.mark.parametrize("iso,want", [("read_committed", "SHIPPED"), ("read_uncommitted", "CANCELLED")])
def test_txn_isolation_on_handwritten_log(tmp_path, iso, want):
    spec = _spec()
    log = tmp_path / "log"
    _write(log, "_schemas", 0, [_reg(spec, 0)])
    _write(log, "orders_cdc", 0, [_cdc(spec, 1, 1001, "PLACED", 0, "o1"),
                                  _cdc(spec, 1, 1002, "SHIPPED", 1, "o2", txn_id="A"),
                                  dict(msg_id="txn-A-commit", ingest_ts=T1, control="txn_commit", txn_id="A", offset=2),
                                  _cdc(spec, 1, 1003, "CANCELLED", 3, "x1", txn_id="B"),
                                  dict(msg_id="txn-B-abort", ingest_ts=T1, control="txn_abort", txn_id="B", offset=4)])
    st = tmp_path / "st"
    silver, cons = _run(tmp_path, dict(RT.correct_choice(), txn_isolation=iso), spec, log, st)
    assert silver[1] == want
    if iso == "read_committed":
        assert cons[3] == "aborted" and cons[1] == "applied" and cons[2] == "control"


def test_gap_handling_on_handwritten_log(tmp_path):
    spec = _spec()
    for mode, want_next in (("wait_contiguous", 2), ("skip", 6)):
        log, st = tmp_path / f"log_{mode}", tmp_path / f"st_{mode}"
        _write(log, "_schemas", 0, [_reg(spec, 0)])
        _write(log, "orders_cdc", 0, [_cdc(spec, 1, 1001, "PLACED", 0, "o1"), _cdc(spec, 2, 1001, "PLACED", 1, "o2")])
        _write(log, "orders_cdc", 0, [_cdc(spec, 5, 1001, "PLACED", 4, "o5"), _cdc(spec, 6, 1001, "PLACED", 5, "o6")])
        silver, cons = _run(tmp_path, dict(RT.correct_choice(), gap_handling=mode, commit_protocol="transactional"), spec, log, st)
        assert max(cons) + 1 == want_next
        _write(log, "orders_cdc", 0, [_cdc(spec, 3, 1001, "PLACED", 2, "o3"), _cdc(spec, 4, 1001, "PLACED", 3, "o4")])
        silver, cons = _run(tmp_path, dict(RT.correct_choice(), gap_handling=mode, commit_protocol="transactional"), spec, log, st)
        assert (set(silver) == {1, 2, 3, 4, 5, 6}) == (mode == "wait_contiguous")


def _obs(tmp, events, k):
    o = RE.Obs(tmp)
    for e in events:
        o.event(**e)
    return o.materialize(k)


def test_observations_are_facts_as_of_k(tmp_path):
    ev = [dict(ev="partition_created", topic="t", part=0, tick=1),
          dict(ev="segment", topic="t", part=0, base=0, end=2, rtick=1, tick=1, n=2),
          dict(ev="segment", topic="t", part=0, base=4, end=6, rtick=2, tick=2, n=2),
          dict(ev="partition_created", topic="t", part=1, tick=3),
          dict(ev="segment", topic="t", part=0, base=2, end=4, rtick=1, tick=3, n=2)]
    o2 = _obs(tmp_path, ev, 2)
    assert [p["part"] for p in o2["partitions"]] == [0]
    assert o2["offsets"]["t/0"] == dict(log_end=6, contiguous_end=2)
    o3 = RE.Obs(tmp_path).materialize(3)
    assert o3["offsets"]["t/0"]["contiguous_end"] == 6 and len(o3["partitions"]) == 2


def test_monitor_detects_each_violation(tmp_path):
    ev = [dict(ev="partition_created", topic="orders_cdc", part=0, tick=1),
          dict(ev="partition_created", topic="_schemas", part=0, tick=1),
          dict(ev="schema", subject="orders", version=1, offset=0, tick=1),
          dict(ev="segment", topic="_schemas", part=0, base=0, end=1, rtick=1, tick=1, n=1),
          dict(ev="segment", topic="orders_cdc", part=0, base=0, end=2, rtick=1, tick=1, n=2),
          dict(ev="txn_record", txn_id="B", topic="orders_cdc", part=0, offset=1, tick=1),
          dict(ev="txn_marker", txn_id="B", topic="orders_cdc", part=0, kind="abort", offset=2, tick=1)]
    obs = _obs(tmp_path / "env", ev, 1)
    spec = _spec()
    view = tmp_path / "view"
    _write(view, "_schemas", 0, [_reg(spec, 0)])
    _write(view, "orders_cdc", 0, [_cdc(spec, 1, 1001, "PLACED", 0, "o1"), _cdc(spec, 1, 1002, "X", 1, "x1", txn_id="B")])
    assert M.check_view(view, obs) == []
    (view / "orders_cdc" / "p1").mkdir()
    assert {v["kind"] for v in M.check_view(view, obs)} == {"partition_early"}
    (view / "orders_cdc" / "p1").rmdir()
    recs = [_cdc(spec, 1, 1002, "X", 1, "x1"), _cdc(spec, 1, 1001, "PLACED", 0, "o1")]     # reordered within the segment
    (view / "orders_cdc" / "p0" / "00000000.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs))
    assert "order_violation" in {v["kind"] for v in M.check_view(view, obs)}
    st = tmp_path / "st"
    st.mkdir()
    (st / "offsets.json").write_text(json.dumps({"off": [["orders_cdc", 0, 3]], "known": None}))
    con = sqlite3.connect(st / "lake.db")
    con.execute("CREATE TABLE _consumed (topic TEXT, part INTEGER, offset INTEGER, msg_id TEXT, tick INTEGER, status TEXT)")
    con.executemany("INSERT INTO _consumed VALUES (?,?,?,?,?,?)", [("orders_cdc", 0, 0, "o1", 1, "applied"),
                                                                   ("orders_cdc", 0, 1, "x1", 1, "applied")])
    con.commit(); con.close()
    kinds = {v["kind"] for v in M.check_consumer(st, obs)}
    assert kinds == {"ack_beyond_available", "ack_beyond_durable", "txn_effect_violation"}


def test_grow_obs_follows_observations_not_data(tmp_path):
    ev = [dict(ev="partition_created", topic="backfill_orders", part=0, tick=1),
          dict(ev="partition_created", topic="orders_cdc", part=2, tick=3),
          dict(ev="segment", topic="orders_cdc", part=2, base=0, end=1, rtick=3, tick=3, n=1)]
    root = tmp_path / "env"
    for k in (1, 2, 3):
        _obs(root, ev if k == 1 else [], k)
    full = root / "log"
    _write(full, "orders_cdc", 2, [dict(msg_id="a", ingest_ts=T1, offset=0)])
    v1 = RC.grow_obs(full, tmp_path / "v1", 1)
    assert (v1 / "backfill_orders" / "p0").is_dir() and not (v1 / "orders_cdc" / "p2").exists()
    assert (RC.grow_obs(full, tmp_path / "v3", 3) / "orders_cdc" / "p2" / "00000000.jsonl").exists()


def test_stage4_hooks_default_off():
    assert C.GROW is None and C.REWRITE_OBS is None and C.REPLAY_HOOK is None and C.CRASH_HOOK is None
    import inspect
    assert inspect.signature(E.encode).parameters["hook"].default is None


def test_de3_ranges_registered_one_use():
    assert {("de3", "val"), ("de3", "val_b"), ("de3", "test")} <= R.ONE_USE
    R._check_disjoint()


def test_evidence_mapping():
    res = [dict(check=c, ok=True, cpu_s=0.0, runs=0) for c in RC.NEXUS]
    ev = RC.evidence(res, dict(txns_observed=0, holes_observed=0, violations=[]), RC.NEXUS)
    assert RC.outcome(ev) == "COMPLETED_UNVERIFIED"
    assert {e["property"] for e in ev if e["result"] == "UNKNOWN"} == {"txn_isolation", "gap_safety"}
    ev = RC.evidence(res, dict(txns_observed=2, holes_observed=1, violations=[]), RC.NEXUS)
    assert RC.outcome(ev) == "COMPLETED_VERIFIED"
    res[3]["ok"] = False
    assert RC.outcome(RC.evidence(res, dict(txns_observed=0, holes_observed=0, violations=[]), RC.NEXUS)) == "ABSTAIN_UNSUPPORTED"
