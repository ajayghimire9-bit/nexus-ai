"""R2 unit tests (no experiment; hand-written mini logs; the X3 / X4 generators are never called)."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from nexus import r2_seeds  # noqa: F401
from nexus import r2_env as E2, r2_reconcile as R2R, r2_template as T2, r1_template as RT1, seed_registry as R

T1 = "2026-04-01T02:00:00Z"


def _spec():
    return E2.make_world(971, "dev")["spec"]


def _write(d, topic, part, recs):
    p = Path(d) / topic / f"p{part}"
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{recs[0]['offset']:08d}.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs))


def _cdc(spec, key, sv, off, mid, cur="USD", disc=10, ver=1):
    n = spec["physical_names_v1"]
    after = {n["order_id"]: key, n["warehouse_id"]: "W1", n["status"]: "PLACED", n["amount"]: 100.0, n["currency"]: cur,
             n["discount"]: disc, n["promised_ts"]: "2026-04-05T00:00:00Z", n["deleted"]: 0}
    return dict(msg_id=mid, ingest_ts=T1, op="c", event_ts=T1, key=key, schema_version=ver, source_version=sv, after=after, offset=off)


def _regs(spec, fraction=False):
    n = spec["physical_names_v1"]
    out = [dict(msg_id="reg-orders-1", ingest_ts="2026-04-01T00:01:00Z", subject="orders", version=1, fields=n,
                types={"discount": "int"}, offset=0)]
    if fraction:
        out.append(dict(msg_id="reg-orders-4", ingest_ts="2026-04-01T00:02:00Z", subject="orders", version=4, fields=n,
                        types={"discount": "float", "discount_unit": "fraction"}, offset=1))
    return out


def _run(tmp, choice, spec, log, st):
    b = tmp / "b"
    b.mkdir(exist_ok=True)
    (b / "pipeline.py").write_text(T2.emit(choice))
    (b / "config.json").write_text(json.dumps(T2.config_from_spec(spec)))
    r = subprocess.run([sys.executable, str(b / "pipeline.py"), "--log", str(log), "--state", str(st), "--config",
                        str(b / "config.json"), "--tick", "1"], capture_output=True, text=True)
    return r


def test_r2_template_has_18_decisions_and_compiles():
    assert len(RT1.DECISIONS) == 16 and len(T2.DECISIONS) == 18
    for ch in (T2.correct_choice(), {d: o[0] for d, o in T2.DECISIONS.items()}):
        compile(T2.emit(ch), "pipeline.py", "exec")


@pytest.mark.parametrize("opt", ["quarantine", "error"])
def test_unknown_currency_handler(tmp_path, opt):
    spec = _spec()
    log, st = tmp_path / "log", tmp_path / "st"
    _write(log, "_schemas", 0, _regs(spec))
    _write(log, "orders_cdc", 0, [_cdc(spec, 1, 1001, 0, "o1"), _cdc(spec, 2, 1002, 1, "o2", cur="JPY")])
    r = _run(tmp_path, dict(T2.correct_choice(), fx_unknown=opt), spec, log, st)
    if opt == "error":
        assert r.returncode != 0 and "stage=silver" in r.stderr
        return
    assert r.returncode == 0, r.stderr[-400:]
    con = sqlite3.connect(st / "lake.db")
    assert {k for (k,) in con.execute("SELECT order_id FROM silver_orders")} == {1}
    assert con.execute("SELECT topic, msg_id, reason FROM quarantine").fetchall() == [("orders_cdc", "o2", "unknown_currency")]


@pytest.mark.parametrize("opt,net", [("registry_unit", 85.0), ("percent_only", 99.85)])
def test_discount_unit_handler(tmp_path, opt, net):
    spec = _spec()
    log, st = tmp_path / "log", tmp_path / "st"
    _write(log, "_schemas", 0, _regs(spec, fraction=True))
    _write(log, "orders_cdc", 0, [_cdc(spec, 1, 1001, 0, "o1", disc=0.15, ver=4)])
    r = _run(tmp_path, dict(T2.correct_choice(), discount_unit=opt), spec, log, st)
    assert r.returncode == 0, r.stderr[-400:]
    con = sqlite3.connect(st / "lake.db")
    assert abs(con.execute("SELECT net_usd FROM silver_orders").fetchone()[0] - net) < 0.011


def test_event_classification_first_copy_and_reasons():
    spec = _spec()
    pre = [("orders_cdc", 0, 0, _cdc(spec, 1, 1001, 0, "o1")), ("orders_cdc", 0, 1, _cdc(spec, 1, 1001, 1, "o1")),
           ("orders_cdc", 0, 2, _cdc(spec, 2, 1002, 2, "o2", cur="JPY")), ("orders_cdc", 0, 3, None),
           ("telemetry", 0, 0, dict(msg_id="t1", ingest_ts=T1, event_ts="2026-04-09T00:00:00Z", order_id=1, type="PICKED")),
           ("telemetry", 0, 1, dict(msg_id="t1", ingest_ts=T1, event_ts=T1, order_id=1, type="PICKED"))]
    c = R2R.classify(spec, [(tp, p, o, r) for tp, p, o, r in pre])
    assert c[("orders_cdc", 0, 0)][0] == "accepted" and c[("orders_cdc", 0, 1)][0] == "duplicate"
    assert c[("orders_cdc", 0, 2)][0] == "q:unknown_currency" and c[("orders_cdc", 0, 3)][0] == "q:poison"
    assert c[("telemetry", 0, 0)][0] == "q:future_event" and c[("telemetry", 0, 1)][0] == "duplicate"


def test_de4_ranges_one_use_and_x_assignment():
    assert {("de4", "val"), ("de4", "val_b"), ("de4", "test")} <= R.ONE_USE
    R._check_disjoint()
    assert E2.x_class(7972, "test") == "X3" and E2.x_class(7971, "test") == "X4" and E2.x_class(972, "dev") == "X1"
