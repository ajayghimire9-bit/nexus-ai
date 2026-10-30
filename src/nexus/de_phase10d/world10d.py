"""Phase 10D out-of-sandbox project generator (NOT LOCKED): multi-table, wide-schema, 3-node DAG data-engineering projects.

WORKSPACE (3-5 relational tables, 60-120 columns in total incl. audit / metadata / status / numeric distractor columns)
  cdc_customers  Debezium change envelopes: payload = {"op": c|u|d, "before": {...}|null, "after": {...}|null, "ts_ms": n}
                 (a delete carries only `before`), plus event id / offset / distractors
  orders         order id, customer reference (some zero-padded text: '007'), epoch ts, currency, total (some dirty), ...
  order_items    item id, order reference, qty, ingest sequence (REPLAYED duplicates with later corrections), ...
  payments       (4+ tables) payment rows per order
  fx_rates       (5 tables) currency rate validity intervals (as-of join)
TRUTH DAG  stg_ (unpack CDC with after/before coalesce, latest per key by ts_ms, drop tombstones AFTER dedup; quarantine dirty
           totals; latest item per replay) -> int_orders (child tables PRE-AGGREGATED to order grain, LEFT joins with typed keys,
           as-of fx rate) -> fct (per-customer aggregates, MERGE INTO the prior target: delete / update / insert)
FAULT MECHANISMS (legacy = truth with faults; node):
  stg  qualify_order (oldest version kept), tombstone (deletes kept), tomb_early (tombstone filter BEFORE dedup), cdc_key (key
       from `after` only, so deletes lose their key), dirty (dirty totals not quarantined), replay (no latest-per-item dedup)
  int  fanout (child joined unaggregated), inner (INNER join drops orphan orders), keycast (text keys compared: '007' <> '7'),
       asof_dir (forward instead of backward as-of)
  fct  merge_delete (no WHEN MATCHED ... DELETE), merge_update (no UPDATE branch), overwrite (full overwrite instead of MERGE)
Every injected fault is checked to be INDIVIDUALLY effective (it alone fails a visible check and changes a hidden batch).
CONTRACTS (schema.yml, per node): stg_customers unique + not_null key, accepted_values op in (c, u, r); stg_orders not_null
total; stg_order_items unique item id; int_orders unique order id + grain (row count = stg_orders); fct_out unique key.
Public end-to-end checks: example rows of the visible fct_out + row count. Hidden: two further batches (different data / state)."""
from __future__ import annotations

import copy
import json
import random
import shutil
from pathlib import Path

import yaml

from nexus.de_phase10d import ir10d as IR

POOLS = dict(
    base=dict(cust="customer_id", seg="segment", ctry="country", email="email", ev="event_id", off="kafka_offset", payload="payload",
              oid="order_id", fk="customer_ref", ts="order_ts", ccy="currency", total="order_total", status="status",
              iid="item_id", ofk="order_ref", qty="qty", seq="ingest_seq", price="unit_price",
              pid="payment_id", pofk="pay_order_ref", amt="paid_cents", method="method", vfrom="valid_from", rate="rate_bp"),
    heldout=dict(cust="account_id", seg="tier_code", ctry="market", email="contact", ev="msg_uid", off="log_position", payload="envelope",
                 oid="ord_no", fk="acct_ref", ts="placed_epoch", ccy="ccy", total="gross_cents", status="state_cd",
                 iid="line_id", ofk="ord_ref", qty="units", seq="load_seq", price="list_price",
                 pid="txn_id", pofk="txn_ord_ref", amt="settled_cents", method="tender", vfrom="effective_from", rate="fx_bp"))
DISTRACT = ["_loaded_at", "_batch_id", "_source_file", "_row_hash", "created_by", "updated_by", "created_at", "updated_at", "is_test", "region_code",
            "channel", "campaign_id", "discount_pct", "tax_amount", "weight_g", "notes", "priority", "risk_score", "warehouse_id", "promo_code",
            "version_no", "legacy_id", "utm_source", "device", "locale", "margin_bp", "fee_cents", "shipping_cents", "coupon_id", "sales_rep",
            "store_id", "pos_terminal", "audit_flag", "etl_run_id", "partner_id", "cost_center", "gl_account", "approval_cd", "rma_flag", "batch_seq"]
MECH_NODE = dict(qualify_order="stg", tombstone="stg", tomb_early="stg", cdc_key="stg", dirty="stg", replay="stg",
                 fanout="int", inner="int", keycast="int", asof_dir="int", merge_delete="fct", merge_update="fct", overwrite="fct")
EXCLUSIVE = [{"tombstone", "tomb_early"}, {"overwrite", "merge_delete"}, {"overwrite", "merge_update"}]


def distractor_value(rng, name, i):
    if name.endswith(("_at", "_seq", "_id", "_no", "_pct", "_amount", "_g", "_score", "_bp", "_cents")) or name in ("priority", "version_no", "batch_seq"):
        return str(rng.randint(0, 999))
    if name in ("is_test", "audit_flag", "rma_flag"):
        return rng.choice(["Y", "N"])
    return rng.choice(["a", "b", "c", "x"]) + str(rng.randint(0, 3))


def widths(rng, n_tables, target):
    base = dict(cdc_customers=4, orders=6, order_items=5, payments=4, fx_rates=3)
    tabs = ["cdc_customers", "orders", "order_items", "payments", "fx_rates"][:n_tables]
    extra = max(0, target - sum(base[t] for t in tabs))
    out = {t: 0 for t in tabs}
    for _ in range(extra):
        out[rng.choice(tabs)] += 1
    return tabs, out


def gen_batch(rng, nm, tabs, dcols, size=1.0):
    n_c = rng.randint(8, 11)
    ids = rng.sample(range(1, 60), n_c)
    cdc, ts, ev, deleted, alive = [], 1000, 1, set(), {}
    for c in ids:
        row = {nm["cust"]: c, nm["seg"]: rng.choice(["gold", "silver", "bronze"]), nm["ctry"]: rng.choice(["us", "de", "fr"]), nm["email"]: f"u{c}@x.io"}
        evs = [("c", None, dict(row))]
        for _ in range(rng.randint(0, 2)):
            new = dict(evs[-1][2], **{nm["seg"]: rng.choice(["gold", "silver", "bronze"])})
            evs.append(("u", evs[-1][2], new))
        if rng.random() < 0.3:
            evs.append(("d", evs[-1][2], None))
            deleted.add(c)
        else:
            alive[c] = evs[-1][2]
        for op, before, after in evs:
            ts += rng.randint(1, 9)
            cdc.append({nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": op, "before": before, "after": after, "ts_ms": ts}), nm["off"]: str(100 + ev)})
            ev += 1
    if not deleted:
        c = rng.choice(sorted(alive))
        ts += 3
        cdc.append({nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": "d", "before": alive.pop(c), "after": None, "ts_ms": ts}), nm["off"]: str(100 + ev)})
        deleted.add(c)
    rng.shuffle(cdc)
    orders, items, pays = [], [], []
    oid, iid, pid = rng.randint(100, 200), 1, 1
    custs = ids + [rng.randint(70, 90) for _ in range(2)]                  # 2 orphan customer references
    for _ in range(rng.randint(18, 24)):
        oid += rng.randint(1, 3)
        c = rng.choice(custs)
        dirty = rng.random() < 0.12
        orders.append({nm["oid"]: str(oid), nm["fk"]: (f"{c:03d}" if rng.random() < 0.45 else str(c)), nm["ts"]: str(rng.randint(1000, 1400)),
                       nm["ccy"]: rng.choice(["USD", "EUR", "GBP"]), nm["total"]: (rng.choice(["12x", "", "n/a"]) if dirty else str(rng.randint(100, 9999))),
                       nm["status"]: rng.choice(["placed", "shipped", "returned"])})
        for _ in range(rng.choice([0, 1, 2, 2, 3])):
            q = rng.randint(1, 5)
            items.append({nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q), nm["seq"]: str(rng.randint(1, 50)), nm["price"]: str(rng.randint(5, 90))})
            if rng.random() < 0.25:                                    # replayed with a correction and a later ingest sequence
                items.append({nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q + rng.randint(1, 3)), nm["seq"]: str(60 + rng.randint(1, 30)),
                              nm["price"]: str(rng.randint(5, 90))})
            iid += 1
        for _ in range(rng.choice([0, 1, 1, 2])):
            pays.append({nm["pid"]: str(pid), nm["pofk"]: str(oid), nm["amt"]: str(rng.randint(50, 5000)), nm["method"]: rng.choice(["card", "wire", "cash"])})
            pid += 1
    rates = [{nm["ccy"]: c, nm["vfrom"]: str(v), nm["rate"]: str(rng.randint(8000, 13000))} for c in ("USD", "EUR", "GBP") for v in (900, 1100, 1250)]
    T = dict(cdc_customers=cdc, orders=orders, order_items=items, payments=pays, fx_rates=rates)
    out = {}
    for t in tabs:
        rows = T[t] or [dict.fromkeys(next(iter(T[t] or [{}])), None)]
        for r in rows:
            for j, dname in enumerate(dcols[t]):
                r[dname] = distractor_value(rng, dname, j)
        out[t] = rows
    known = [c for c in ids if c not in deleted]
    target = []
    for c in rng.sample(known, max(1, len(known) // 2)) + rng.sample(sorted(deleted), len(deleted)) + [rng.randint(91, 99) for _ in range(2)]:
        target.append(c)
    return out, sorted(set(target))


def _mix(rng, role_cols, extra):
    """role columns interleaved among the distractors (relevant columns sit anywhere in a wide table)"""
    cols = list(role_cols) + list(extra)
    rng.shuffle(cols)
    return cols


def truth_spec(nm, tabs, dcols, rng=None):
    rng = rng or random.Random(0)
    P = nm["payload"]
    cd = [[c, ["col", c]] for c in _mix(rng, [nm["ev"], nm["off"]], dcols["cdc_customers"])]
    stg = {"stg_customers": dict(src="cdc_customers", cols=[[nm["cust"], ["coalesce", ["json", P, "after." + nm["cust"]], ["json", P, "before." + nm["cust"]]]],
                                                          [nm["seg"], ["coalesce", ["json", P, "after." + nm["seg"]], ["json", P, "before." + nm["seg"]]]],
                                                          ["op", ["json", P, "op"]], ["ts_ms", ["json", P, "ts_ms"]]] + cd,
                                 pre=[], dedup=dict(key=["try_int", ["col", nm["cust"]]], order=["try_int", ["col", "ts_ms"]], desc=True),
                                 post=[["ne", ["col", "op"], ["lit", "d"]]], latest_as="stg_customers_latest"),
           "stg_orders": dict(src="orders", cols=[[c, ["try_int", ["col", c]] if c == nm["total"] else ["col", c]] for c in
                                                  _mix(rng, [nm["oid"], nm["fk"], nm["ts"], nm["ccy"], nm["total"], nm["status"]], dcols["orders"])],
                              pre=[["notnull", ["col", nm["total"]]]], dedup=None, post=[]),
           "stg_order_items": dict(src="order_items", cols=[[c, ["try_int", ["col", c]] if c == nm["qty"] else ["col", c]] for c in
                                                            _mix(rng, [nm["iid"], nm["ofk"], nm["qty"], nm["seq"], nm["price"]], dcols["order_items"])],
                                   pre=[], dedup=dict(key=["try_int", ["col", nm["iid"]]], order=["try_int", ["col", nm["seq"]]], desc=True), post=[])}
    if "payments" in tabs:
        stg["stg_payments"] = dict(src="payments", cols=[[c, ["try_int", ["col", c]] if c == nm["amt"] else ["col", c]] for c in
                                                         _mix(rng, [nm["pid"], nm["pofk"], nm["amt"], nm["method"]], dcols["payments"])], pre=[], dedup=None, post=[])
    if "fx_rates" in tabs:
        stg["stg_fx_rates"] = dict(src="fx_rates", cols=[[c, ["try_int", ["col", c]] if c in (nm["vfrom"], nm["rate"]) else ["col", c]] for c in
                                                         _mix(rng, [nm["ccy"], nm["vfrom"], nm["rate"]], dcols["fx_rates"])], pre=[], dedup=None, post=[])
    base_cols = [n for n, _ in stg["stg_orders"]["cols"]]
    joins = [dict(rel="stg_order_items", how="left", lkey=["try_int", ["col", nm["oid"]]], rkey=["try_int", ["col", nm["ofk"]]],
                  agg=dict(by=nm["ofk"], measures=[["item_qty", "sum", ["col", nm["qty"]]]]), take=[["item_qty", "item_qty"]]),
             dict(rel="stg_customers", how="left", lkey=["try_int", ["col", nm["fk"]]], rkey=["try_int", ["col", nm["cust"]]], agg=None, take=[[nm["seg"], nm["seg"]]])]
    out = [[c, ["col", c]] for c in base_cols] + [[nm["seg"], ["col", nm["seg"]]], ["item_qty", ["coalesce", ["col", "item_qty"], ["lit", 0]]]]
    meas = [["n_orders", "count", ["col", nm["oid"]]], ["total", "sum", ["col", nm["total"]]], ["items", "sum", ["col", "item_qty"]],
            ["n_segmented", "count", ["col", nm["seg"]]]]
    if "payments" in tabs:
        joins.append(dict(rel="stg_payments", how="left", lkey=["try_int", ["col", nm["oid"]]], rkey=["try_int", ["col", nm["pofk"]]],
                          agg=dict(by=nm["pofk"], measures=[["paid", "sum", ["col", nm["amt"]]]]), take=[["paid", "paid"]]))
        out.append(["paid", ["coalesce", ["col", "paid"], ["lit", 0]]])
        meas.append(["paid", "sum", ["col", "paid"]])
    if "fx_rates" in tabs:
        joins.append(dict(rel="stg_fx_rates", how="asof", lkey=["try_int", ["col", nm["ts"]]], rkey=["col", nm["vfrom"]], by=[nm["ccy"], nm["ccy"]],
                          strategy="backward", agg=None, take=[["rate", nm["rate"]]]))
        out.append(["rate", ["col", "rate"]])
        meas.append(["max_rate", "max", ["col", "rate"]])
    fct = dict(src="int_orders", group=[["cust_key", ["try_int", ["col", nm["fk"]]]]], measures=meas,
               merge=dict(key="cust_key", update=True, delete=True, deletes=dict(rel="stg_customers_latest", key=["try_int", ["col", nm["cust"]]], minus="stg_customers")))
    return dict(stg=stg, int=dict(base="stg_orders", base_cols=base_cols, joins=joins, out=out), fct=fct)


def inject(spec, faults, nm):
    s = copy.deepcopy(spec)
    c = s["stg"]["stg_customers"]
    for f in faults:
        if f == "qualify_order":
            c["dedup"]["desc"] = False
        elif f == "tombstone":
            c["post"] = []
        elif f == "tomb_early":
            c["pre"], c["post"] = c["pre"] + c["post"], []
        elif f == "cdc_key":
            c["cols"][0][1] = ["json", nm["payload"], "after." + nm["cust"]]
        elif f == "dirty":
            s["stg"]["stg_orders"]["pre"] = []
        elif f == "replay":
            s["stg"]["stg_order_items"]["dedup"] = None
        elif f == "fanout":
            j = s["int"]["joins"][0]
            j["agg"], j["take"] = None, [["item_qty", nm["qty"]]]
        elif f == "inner":
            s["int"]["joins"][1]["how"] = "inner"
        elif f == "keycast":
            s["int"]["joins"][1]["lkey"], s["int"]["joins"][1]["rkey"] = ["col", nm["fk"]], ["col", nm["cust"]]
        elif f == "asof_dir":
            next(j for j in s["int"]["joins"] if j["how"] == "asof")["strategy"] = "forward"
        elif f == "merge_delete":
            s["fct"]["merge"]["delete"] = False
        elif f == "merge_update":
            s["fct"]["merge"]["update"] = False
        elif f == "overwrite":
            s["fct"]["merge"] = None
    return s


# ------------------------------------------------------------------ checks (public + per-node contracts)
def contracts(nm):
    return dict(stg=[("stg_customers", "unique", nm["cust"]), ("stg_customers", "not_null", nm["cust"]), ("stg_customers", "accepted_values", "op"),
                     ("stg_orders", "not_null", nm["total"]), ("stg_order_items", "unique", nm["iid"])],
                int=[("int_orders", "unique", nm["oid"]), ("int_orders", "grain", "stg_orders")],
                fct=[("fct_out", "unique", "cust_key")])


def run_contracts(R, nm):
    fails = dict(stg=[], int=[], fct=[])
    for node, tests in contracts(nm).items():
        for rel, test, col in tests:
            rows = R.get(rel, [])
            if test == "unique":
                v = [IR.canon(r.get(col)) for r in rows]
                ok = len(v) == len(set(v))
            elif test == "not_null":
                ok = all(r.get(col) not in (None, "") for r in rows)
            elif test == "accepted_values":
                ok = all(r.get(col) in ("c", "u", "r") for r in rows)
            else:
                ok = len(rows) == len(R.get(col, []))
            if not ok:
                fails[node].append(f"{test}:{rel}")
    return fails


def fct_cols(spec):
    return [n for n, _ in spec["fct"]["group"]] + [n for n, _, _ in spec["fct"]["measures"]]


def visible_fail(spec_l, spec_t, tables, state, nm):
    """Does the legacy fail a public check or a contract on this batch?"""
    try:
        Rl = IR.interpret(spec_l, tables, state)
    except Exception:                                          # noqa: BLE001
        return True
    Rt = IR.interpret(spec_t, tables, state)
    cols = fct_cols(spec_t)
    return IR.table_key(Rl["fct_out"], cols) != IR.table_key(Rt["fct_out"], cols) or any(run_contracts(Rl, nm).values())


def target_rows(rng, keys, spec):
    cols = fct_cols(spec)
    return [dict({cols[0]: k}, **{c: rng.randint(0, 9000) for c in cols[1:]}) for k in keys]


# ------------------------------------------------------------------ project
def make_project10d(spec, seed, root):
    """spec: dict(family, faults, engine, legacy, names, n_tables, width)."""
    for attempt in range(60):
        p = _make(spec, seed, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build a phase-10D project {spec} seed {seed}")


def _make(spec, seed, root, attempt):
    rng = random.Random(seed * 1000 + attempt)
    nm = dict(POOLS[spec.get("names", "base")])
    n_tables = spec.get("n_tables") or rng.choice([3, 4, 5])
    if "asof_dir" in spec["faults"]:
        n_tables = 5
    if spec.get("legacy") == "scala" and n_tables == 5:
        n_tables = 4                                          # the Scala lifter has no as-of form (disclosed)
    target_w = spec.get("width") or rng.randint(62, 118)
    tabs, extra = widths(rng, n_tables, target_w)
    pool = [d for d in DISTRACT]
    rng.shuffle(pool)
    dcols, i = {}, 0
    for t in tabs:
        dcols[t] = [f"{pool[(i + j) % len(pool)]}" + ("" if (i + j) < len(pool) else f"_{(i + j) // len(pool)}") for j in range(extra[t])]
        i += extra[t]
    truth = truth_spec(nm, tabs, dcols, rng)
    legacy = inject(truth, spec["faults"], nm)
    batches, states = {}, {}
    for b, sz in (("visible", 1.0), ("hidden1", 1.2), ("hidden2", 1.4)):
        T, keys = gen_batch(rng, nm, tabs, dcols, sz)
        batches[b] = T
        states[b] = dict(fct_target=target_rows(rng, keys, truth))
    n_cols = sum(len(batches["visible"][t][0]) for t in tabs)
    if not 60 <= n_cols <= 120:
        return None
    for f in spec["faults"]:                                   # every fault individually effective (visible fail + hidden change)
        one = inject(truth, [f], nm)
        if not visible_fail(one, truth, batches["visible"], states["visible"], nm):
            return None
        if not any(visible_fail(one, truth, batches[b], states[b], nm) for b in ("hidden1", "hidden2")):
            return None
    if not visible_fail(legacy, truth, batches["visible"], states["visible"], nm):
        return None
    pid = f"P10D.{spec['family']}.{spec['engine']}.{spec['legacy']}.{seed}"
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    if ws.parent.exists():
        shutil.rmtree(ws.parent)
    for d in (ws / "data", ws / "models", ws / "state", hid):
        d.mkdir(parents=True, exist_ok=True)
    from nexus.de_phase10d import legacy10d as LG
    for t in tabs:
        write_csv(ws / "data" / f"{t}.csv", batches["visible"][t])
        for b in ("hidden1", "hidden2"):
            write_csv(hid / f"{b}_{t}.csv", batches[b][t])
    (ws / "state" / "fct_target.json").write_text(json.dumps(states["visible"]["fct_target"]))
    for b in ("hidden1", "hidden2"):
        (hid / f"{b}_state.json").write_text(json.dumps(states[b]))
        R = IR.interpret(truth, batches[b], states[b])
        (hid / f"{b}_expected.json").write_text(json.dumps(dict(cols=fct_cols(truth), rows=[[r.get(c) for c in fct_cols(truth)] for r in R["fct_out"]])))
    files = LG.write_legacy(legacy, spec["legacy"], ws)
    Rv = IR.interpret(truth, batches["visible"], states["visible"])
    cols = fct_cols(truth)
    schema = dict(version=2, models=[dict(name=rel, columns=[dict(name=col, tests=[test if test != "accepted_values" else {"accepted_values": {"values": ["c", "u", "r"]}}])])
                                     for node, ts in contracts(nm).items() for rel, test, col in ts if test != "grain"]
                  + [dict(name="int_orders", tests=[{"equal_rowcount": {"compare_model": "ref('stg_orders')"}}])])
    (ws / "models" / "schema.yml").write_text(yaml.safe_dump(schema, sort_keys=False))
    contract = dict(nodes=["stg", "int", "fct"], files=files, legacy_language=spec["legacy"], engine=spec["engine"], tables=tabs,
                    public_checks=[dict(kind="example_rows", cols=cols, rows=[[r.get(c) for c in cols] for r in Rv["fct_out"]]), dict(kind="row_count", n=len(Rv["fct_out"])),
                                   dict(kind="unique", col="cust_key")], names=nm)
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    (hid / "truth.json").write_text(json.dumps(truth))
    return dict(pid=pid, family=spec["family"], faults=list(spec["faults"]), nodes_faulted=sorted({MECH_NODE[f] for f in spec["faults"]}), engine=spec["engine"],
                legacy=spec["legacy"], ws=str(ws), hidden_dir=str(hid), n_tables=len(tabs), n_cols=n_cols, names=nm, seed=seed, spec=spec)


def write_csv(path, rows):
    import csv
    cols = list(rows[0].keys())
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])


def read_csv(path):
    import csv
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        cols = next(rd)
        return [dict(zip(cols, row)) for row in rd]


def load_tables(ws_or_hidden, tabs, prefix=""):
    return {t: read_csv(Path(ws_or_hidden) / (f"{prefix}{t}.csv" if prefix else f"data/{t}.csv")) for t in tabs}
