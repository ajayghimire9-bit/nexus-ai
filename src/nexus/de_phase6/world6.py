"""Phase 6 nine-paradigm multi-stage, multi-language, multi-engine DE arena (NOT LOCKED).

A PROJECT is a pipeline of 1-3 STAGES. Stage k reads the previous stage's clean output (landed as text) and has its own
legacy input language, execution engine and target language (ir6 / engines6). Each stage implements a paradigm's
MECHANISMS; a mechanism has a correct form and a legacy defect form (a fault). Final output = the last stage's clean table;
quarantine = the union of every stage's rejects.

Paradigms (mechanisms):
  Tier 1  P1 batch          chunk window ts >= start AND ts < end (end boundary = a decision point), duplicate-batch
                            protection (dedup by id), per-key sum (conservation)
          P2 replication/CDC latest version per key by sequence, delete tombstones (op <> 'D')
          P3 ELT            malformed amounts: quarantine or default 0 (ANSI-safe parse)
  Tier 2  P4 analytical     join fan-out dedup (by id), normalised dimension codes, per-region totals
          P5 streaming      watermark (decision point), checkpoint (decision point), replay dedup (by event id)
          P6 reverse-ETL    required-field rejection (empty region -> quarantine) or contract default, normalised codes
          P7 MLOps          point-in-time cut-off feature_ts <= label_ts (decision point: <= or <), NaN/Inf-safe ratio
  Tier 3  P8 lift-and-refactor  a legacy Scala Spark or Hive job (P1 / P2 / P5 / P3 mechanisms) migrated to a DuckDB or
                            PySpark target; Hive '/' and ANSI casts change the semantics
          P9 hybrid         A streaming -> batch reconciliation, B CDC -> ELT -> analytical, C analytical -> MLOps -> reverse-ETL,
                            each stage on its own engine / language
Every stage except the last has schema.yml tests (unique / not_null / accepted_values derived from the intended stage
output): stage-level evidence a stage-wise investigation can use. Requirement decision points carry documents with
provenance (contract.json, docs/runbook.json, docs/ticket.json) in the Phase 5 modes explicit / missing /
conflict_approved / undecided / visible; the business answer is drawn per project. Tier 3 paradigms never appear in source
or admission projects (seeds6 / tests)."""
from __future__ import annotations

import copy
import json
import random
import shutil
from pathlib import Path

import yaml

from nexus.de_phase4 import ir, world as W
from nexus.de_phase6 import engines6 as E, ir6

ROLES = ("key", "seq", "op", "ts", "off", "ev", "amt", "qty", "region", "fts", "lts")
POOLS = dict(key=["account_id", "customer_id", "sku"], seq=["version", "seq", "rev"], op=["op", "change_type"], ts=["event_ts", "ts"],
             off=["offset", "log_pos"], ev=["event_id", "msg_id"], amt=["amount", "gross"], qty=["qty", "units"], region=["region", "market"],
             fts=["feature_ts", "obs_ts"], lts=["label_ts", "outcome_ts"])
HELDOUT = dict(key=["tenant_id"], seq=["lsn"], op=["dml_type"], ts=["evt_time"], off=["kafka_offset"], ev=["record_uid"], amt=["amount_cents"],
               qty=["pieces"], region=["territory"], fts=["snapshot_ts"], lts=["target_ts"])
PARADIGMS = {"P1": dict(tier=1, mech=("window", "dup_id"), out="group"), "P2": dict(tier=1, mech=("latest", "tombstone"), out="entity"),
             "P3": dict(tier=1, mech=("parse",), out="row"), "P4": dict(tier=2, mech=("fanout", "normalize"), out="group_region"),
             "P5": dict(tier=2, mech=("watermark", "checkpoint", "replay"), out="group"), "P6": dict(tier=2, mech=("require", "normalize"), out="row_region"),
             "P7": dict(tier=2, mech=("pit", "ratio"), out="row_feature")}
TIER3 = ("P8", "P9")
HYBRIDS = {"A": [("P5", "spark"), ("P1", "duckdb")], "B": [("P2", "sqlite"), ("P3", "duckdb"), ("P4", "spark")],
           "C": [("P4", "duckdb"), ("P7", "spark"), ("P6", "sqlite")]}
# Tier-2 SOURCE compositions (cross-paradigm, 2 stages) - different from the held-out Tier-3 hybrids A / B / C
COMPOSITES = {"X1": [("P3", "sqlite"), ("P2", "duckdb")], "X2": [("P7", "duckdb"), ("P6", "sqlite")], "X3": [("P3", "sqlite"), ("P5", "duckdb")]}
TIER = dict({p: v["tier"] for p, v in PARADIGMS.items()}, X1=2, X2=2, X3=2, P8=3, P9=3)
DP_MECH = {"window": "window_end", "watermark": "watermark", "checkpoint": "checkpoint", "pit": "pit"}
MODES = ("explicit", "missing", "conflict_approved", "undecided", "visible")
SOURCES = ("contract.json", "docs/runbook.json", "docs/ticket.json")
LEGACY_LANGS = {"sqlite": ("sql", "postgres", "j2"), "duckdb": ("sql", "postgres", "snowflake", "j2"), "spark": ("py",)}


def dp_ref(dp, nm):
    """(column compared, right-hand side expression, inclusive comparison, exclusive comparison)."""
    return {"window_end": (nm["ts"], ["file", "batch.json", "end"], "le", "lt"),
            "watermark": (nm["ts"], ["sub", ["file", "watermark.json", "watermark"], ["file", "watermark.json", "allowed_lateness"]], "ge", "gt"),
            "checkpoint": (nm["off"], ["file", "checkpoint.json", "last_committed_offset"], "ge", "gt"),
            "pit": (nm["fts"], ["cast_int", ["col", nm["lts"]]], "le", "lt")}[dp]


def _and_all(fs):
    out = None
    for f in fs:
        out = f if out is None else ["and", out, f]
    return out


# ------------------------------------------------------------------ stage specs from mechanisms
def build_stage(mechs, faults, out, nm, params, cols, choice, final):
    """(truth, legacy) for one stage. mechs: its mechanisms; faults: those the legacy gets wrong; choice: {dp: inclusive}."""
    T, Lg = dict(outputs=[]), dict(outputs=[])
    tf, lf, tq, lq = [], [], [], []

    def add(lst_t, lst_l, x, mech):
        lst_t.append(x)
        if mech not in faults:
            lst_l.append(x)
    c = lambda r: ["col", nm[r]]                                        # noqa: E731
    ci = lambda r: ["cast_int", c(r)]                                   # noqa: E731
    for m in mechs:
        if m in DP_MECH:
            col, rhs, inc, exc = dp_ref(DP_MECH[m], nm)
            x = [inc if choice[DP_MECH[m]] else exc, ["cast_int", ["col", col]], rhs]
            if m == "window":
                add(tf, lf, ["ge", ci("ts"), ["file", "batch.json", "start"]], m)
            add(tf, lf, x, m)
        elif m == "tombstone":
            add(tf, lf, ["ne", c("op"), ["lit", "D"]], m)
        elif m == "latest":
            T["dedup"] = dict(key=nm["key"], order=ci("seq"))
            if m not in faults:
                Lg["dedup"] = dict(T["dedup"])
        elif m in ("dup_id", "fanout"):
            T["dedup"] = dict(key="id")
            if m not in faults:
                Lg["dedup"] = dict(key="id")
        elif m == "replay":
            T["dedup"] = dict(key=nm["ev"])
            if m not in faults:
                Lg["dedup"] = dict(key=nm["ev"])
        elif m == "parse" and params["policy"] == "quarantine":
            add(tq, lq, ["valid_int", c("amt")], m)
        elif m == "require":
            add(tq, lq, ["nonempty", c("region")], m)
    for s, f, q in ((T, tf, tq), (Lg, lf, lq)):
        if f:
            s["filter"] = _and_all(f)
        if q:
            s["quarantine"] = ["not", _and_all(q)]

    def amt(leg):
        if "parse" in mechs and not (leg and "parse" in faults):
            return ["try_int", c("amt")] if params["policy"] == "quarantine" else ["coalesce", ["try_int", c("amt")], ["lit", 0]]
        return ci("amt")

    def region(leg):
        x = c("region")
        if "normalize" in mechs and not (leg and "normalize" in faults):
            x = ["norm_text", x]
        return x

    def ratio(leg):
        if leg and "ratio" in faults:
            return ["div", amt(leg), ci("qty")]
        return ["round2", ["div_real", amt(leg), ["nullif_zero", ci("qty")]]]
    for s, leg in ((T, False), (Lg, True)):
        if not final:                                   # intermediate: pass every column through, typed where transformed
            for col in cols:
                role = next((r for r in ROLES if nm[r] == col), None)
                x = amt(leg) if role == "amt" and "parse" in mechs else region(leg) if role == "region" and "normalize" in mechs else ["col", col]
                s["outputs"].append([col, x])
        elif out == "group":
            s["group"] = [nm["key"], c("key")]
            s["outputs"].append(["total", amt(leg)])
        elif out == "group_region":
            s["group"] = [nm["region"], region(leg)]
            s["outputs"].append(["total", amt(leg)])
        elif out == "entity":
            s["outputs"] += [[nm["key"], c("key")], [nm["seq"], ci("seq")], [nm["amt"], amt(leg)]]
        elif out == "row":
            s["outputs"] += [["id", ["col", "id"]], [nm["key"], c("key")], [nm["amt"], amt(leg)]]
        elif out == "row_region":
            s["outputs"] += [["id", ["col", "id"]], [nm["region"], region(leg)], [nm["amt"], amt(leg)]]
        elif out == "row_feature":
            s["outputs"] += [["id", ["col", "id"]], [nm["key"], c("key")], ["feature", ratio(leg)]]
    return T, Lg


# ------------------------------------------------------------------ data
def gen_rows(rng, n, nm, has, ordered=True):
    keys = [f"k{j}" for j in range(max(4, n // 5))]
    regs = ["EU", "US", "APAC"]
    seqs = {}
    rows = []
    for i in range(n):
        k = rng.choice(keys)
        seqs[k] = seqs.get(k, 0) + rng.randint(1, 3)
        reg = rng.choice(regs)
        if "normalize" in has and rng.random() < 0.4:
            reg = rng.choice([reg.lower(), f" {reg}", f"{reg} ", reg.capitalize()])
        if "require" in has and rng.random() < 0.2:
            reg = ""
        lts = 100 + rng.randint(0, 3 * n)
        amt = str(rng.randint(1, 50))
        if "parse" in has and rng.random() < 0.2:
            amt = rng.choice(["n/a", "", "12x", "?", "1,5"])
        ts = 100 + 3 * i + rng.randint(-8, 2) if ordered else 100 + rng.randint(0, 3 * n)
        rows.append({"id": f"r{i}", nm["key"]: k, nm["seq"]: str(seqs[k]), nm["op"]: rng.choice(["I", "U", "U", "D"]) if "tombstone" in has else "U",
                     nm["ts"]: str(ts), nm["off"]: str(i + 1), nm["ev"]: f"e{i}", nm["amt"]: amt, nm["qty"]: str(rng.randint(0, 9)),
                     nm["region"]: reg, nm["fts"]: str(lts + rng.randint(-12, 4)), nm["lts"]: str(lts)})
    if has & {"replay", "dup_id", "fanout"}:
        dup = rows[n // 3: n // 3 + max(3, n // 6)]
        rows += [dict(r) for r in dup]
    return rows


# ------------------------------------------------------------------ documents (Phase 5 modes, generic subjects)
def make_docs(rng, dps, nm):
    docs = {s: [] for s in SOURCES}
    n = 0
    for dp, (mode, inclusive) in dps.items():
        right, wrong = ("kept", "excluded") if inclusive else ("excluded", "kept")
        placed = {"explicit": [(rng.choice(SOURCES), right, rng.choice(["approved", "draft"]))],
                  "conflict_approved": list(zip(rng.sample(SOURCES, 2), (right, wrong), ("approved", "draft"))),
                  "undecided": list(zip(rng.sample(SOURCES, 2), (right, wrong), ("draft", "draft")))}.get(mode, [])
        col, rhs, _, _ = dp_ref(dp, nm)
        for src, eff, status in placed:
            n += 1
            docs[src].append(dict(id=f"R{n}", source=src, subject=dict(column_role=dp, state_ref=rhs), effect_at_boundary=eff, status=status,
                                  version=rng.randint(1, 9), updated=f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}",
                                  text=f"Rows exactly at the {dp.replace('_', ' ')} boundary are {eff}."))
    return docs


# ------------------------------------------------------------------ pipelines
def run_pipeline(stages, specs, rows, state, engines=None, fast=False):
    """Execute stage specs in order (lowered to each stage's execution language). fast: False (declared engines) |
    "spark" (SQLite for Spark stages: generator self-checks) | "all" / True (SQLite for every stage: search screening). -> (final result, [per-stage results]); raises W.RunError."""
    res_all, cur, rejects = [], rows, []
    for k, (st, sp) in enumerate(zip(stages, specs)):
        eng = (engines or {}).get(k) or st["engine"]
        if (fast == "spark" and eng == "spark") or (fast in (True, "all") and eng != "sqlite"):
            eng = "sqlite"
        rt = E.ENGINES[eng]() if eng != "spark" else W.SparkCode()
        header = list(cur[0].keys()) if cur else st["in_cols"]
        res = rt.run(ir6.lower(sp, E.EXEC_LANG[eng]), header, cur, state)
        res_all.append(res)
        if res["rejects"] is not None:
            rejects += res["rejects"]
        cur = [{c: ("" if v is None else (str(int(v)) if isinstance(v, float) and v == int(v) else str(v))) for c, v in r.items()}
               for r in res["clean"]]
        cur = [dict(r, id=r.get("id", f"g{i}")) for i, r in enumerate(cur)] if k < len(stages) - 1 else cur
    final = dict(clean=res_all[-1]["clean"], rejects=rejects if any(r["rejects"] is not None for r in res_all) else None)
    return final, res_all


def key_of(res, cols):
    return (W.table_key(res["clean"], cols), sorted(str(r.get("id")) for r in res["rejects"]) if res["rejects"] is not None else None)


def stage_tests(spec_truth, res, k):
    """schema.yml tests for an intermediate stage, derived from its intended output."""
    rows = res["clean"]
    tests = []
    if rows:
        for c in rows[0]:
            vals = [r[c] for r in rows]
            if all(v is not None and str(v).strip() != "" for v in vals):
                tests.append(dict(column=c, test="not_null"))
            if c == "id" or (len(set(map(str, vals))) == len(vals) and c != "id" and isinstance(vals[0], str) and len(vals) > 3):
                tests.append(dict(column=c, test="unique"))
            if isinstance(vals[0], str) and 1 < len(set(vals)) <= 4:
                tests.append(dict(column=c, test="accepted_values", values=sorted(set(map(str, vals)))))
    return tests


def check_stage_tests(tests, res):
    rows = res["clean"]
    fails = []
    for t in tests:
        vals = [r.get(t["column"]) for r in rows]
        if t["test"] == "not_null" and any(v is None or str(v).strip() == "" for v in vals):
            fails.append(f"not_null:{t['column']}")
        elif t["test"] == "unique" and len(vals) != len(set(map(str, vals))):
            fails.append(f"unique:{t['column']}")
        elif t["test"] == "accepted_values" and any(str(v) not in t["values"] for v in vals if v is not None):
            fails.append(f"accepted_values:{t['column']}")
    return fails


# ------------------------------------------------------------------ project builder
def plan_stages(paradigm, rng, hybrid=None):
    if paradigm == "P9":
        return [dict(paradigm=p, engine=e) for p, e in HYBRIDS[hybrid or rng.choice(sorted(HYBRIDS))]]
    if paradigm in COMPOSITES:
        return [dict(paradigm=p, engine=e) for p, e in COMPOSITES[paradigm]]
    if paradigm == "P8":
        base = rng.choice(["P1", "P2", "P5", "P3"])
        return [dict(paradigm=base, engine=rng.choice(["duckdb", "spark"]), lift=rng.choice(["scala", "hive"]), lift_of=base)]
    return [dict(paradigm=paradigm, engine=rng.choice(["sqlite", "duckdb", "duckdb", "spark"]))]


def make_project6(spec, seed, root):
    for attempt in range(80):
        p = _make6(spec, seed, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build a phase-6 project {spec} seed {seed}")


REJECTS = []


def _make6(spec, seed, root, attempt):
    rng = random.Random(f"p6de|{json.dumps(spec, sort_keys=True)}|{seed}|{attempt}")
    par = spec["paradigm"]
    stages = plan_stages(par, rng, spec.get("hybrid"))
    if spec.get("engine") and par not in TIER3 and par not in COMPOSITES:
        stages[0]["engine"] = spec["engine"]
    pools = dict(POOLS)
    if spec.get("names") == "heldout" or par in TIER3:
        pools.update(HELDOUT) if spec.get("names") == "heldout" else None
    nm = {r: rng.choice(v) for r, v in pools.items()}
    params = dict(policy=rng.choice(["quarantine", "default"]))
    for st in stages:
        mechs = list(PARADIGMS[st["paradigm"]]["mech"])
        if st["paradigm"] == "P8":
            mechs = list(PARADIGMS[st["lift_of"]]["mech"])
        if st.get("lift") and "parse" not in mechs:
            mechs.append("parse")                       # lifted jobs must become ANSI-safe
        st["mechs"] = mechs
        st["faults"] = [m for m in mechs if rng.random() < spec.get("fault_p", 0.7)] or [rng.choice(mechs)]
    dedups = {"latest", "replay", "dup_id", "fanout"}
    for k, st in enumerate(stages):                     # a later id-dedup is redundant after an earlier stage deduplicates
        if k and any(set(s0["mechs"]) & dedups for s0 in stages[:k]):
            st["mechs"] = [m for m in st["mechs"] if m not in ("dup_id", "fanout")] or st["mechs"]
            st["faults"] = [m for m in st["faults"] if m in st["mechs"]] or [rng.choice(st["mechs"])]
    for k, st in enumerate(stages):                     # a mechanism repeated in a later stage lives only in the last one
        later = {m for s2 in stages[k + 1:] for m in s2["mechs"]}
        st["mechs"] = [m for m in st["mechs"] if m not in later] or st["mechs"]
        st["faults"] = [m for m in st["faults"] if m in st["mechs"]] or [rng.choice(st["mechs"])]
    has = {m for st in stages for m in st["mechs"]}
    dps = {DP_MECH[m]: spec.get("modes", {}).get(DP_MECH[m], rng.choice(MODES)) for m in sorted(has) if m in DP_MECH}
    if spec.get("dp_mode"):
        dps = {d: spec["dp_mode"] for d in dps}
    choice = {d: rng.random() < 0.5 for d in dps}
    undecided = [d for d, m in dps.items() if m == "undecided"]
    cols = ["id"] + [nm[r] for r in ROLES]
    truths, legacies = [], []
    for k, st in enumerate(stages):
        st["in_cols"] = cols
        t, l = build_stage(st["mechs"], st["faults"], PARADIGMS[st["paradigm"] if st["paradigm"] != "P8" else st["lift_of"]]["out"],
                           nm, params, cols, choice, k == len(stages) - 1)
        truths.append(t)
        legacies.append(l)
    n = rng.randint(40, 50)
    ordered = not ({"watermark", "checkpoint"} <= has or ({"window", "watermark"} <= has))
    batches = {b: gen_rows(rng, n + dn, nm, has, ordered) for b, dn in (("visible.csv", 0), ("hidden1.csv", 20), ("hidden2.csv", 30))}
    states = {}
    for b, rows in batches.items():
        st_ = {}
        tsv = sorted(int(r[nm["ts"]]) for r in rows)
        if "window" in has:
            lo = tsv[len(tsv) // 10] if "watermark" in has else tsv[len(tsv) // 5]
            st_["batch.json"] = {"start": lo, "end": tsv[4 * len(tsv) // 5]}
        if "watermark" in has:                         # inside the batch window when both exist (hybrid A)
            wm = tsv[len(tsv) // 2] + rng.randint(0, 3)
            st_["watermark.json"] = {"watermark": wm, "allowed_lateness": rng.choice([5, 10])}
        if "checkpoint" in has:
            st_["checkpoint.json"] = {"last_committed_offset": rng.randint(3, max(4, len(rows) // 4))}
        states[b] = st_
    if "window" in has:                                 # the conventional window START is always evidenced (a row at start)
        for b, rows in batches.items():
            t0_ = states[b]["batch.json"]["start"]
            if not any(r[nm["ts"]] == str(t0_) for r in rows):
                q = dict(rows[len(rows) // 2], id=f"s0_{rows[len(rows) // 2]['id']}", **{nm["ev"]: "s0_ev", nm["off"]: str(len(rows) + 50)})
                q[nm["ts"]] = str(t0_)
                batches[b] = rows + [q]
    # boundary control (Phase 5): visible boundary rows only in 'visible' mode; hidden batches always test the boundary
    for d, mode in dps.items():
        col, rhs, _, _ = dp_ref(d, nm)
        for b, rows in batches.items():
            t = ir.ev(rhs, rows[0], states[b]) if d != "pit" else None
            if d == "pit":
                if b == "visible.csv" and mode != "visible":
                    batches[b] = [r for r in rows if r[nm["fts"]] != r[nm["lts"]]]
                else:
                    add = [dict(r, id=f"b{j}_{r['id']}", **{nm["ev"]: f"b{j}_{r[nm['ev']]}", nm["fts"]: r[nm["lts"]]}) for j, r in enumerate(rng.sample(rows, 2))]
                    batches[b] = rows + add[:1 if b == "visible.csv" else 2]
                continue
            if b == "visible.csv" and mode != "visible":
                batches[b] = [r for r in rows if r[col] != str(t)]
            else:
                safe = {}
                for o in dps:
                    if o in ("watermark", "checkpoint", "window_end") and o != d:
                        oc, orhs, _, _ = dp_ref(o, nm)
                        ov = ir.ev(orhs, {}, states[b])
                        safe[oc] = ov + (1 if o == "window_end" and False else 2) if o != "window_end" else ov - 2
                base = [r for r in rows if r[col].isdigit()]
                add = []
                for j, r in enumerate(rng.sample(base, 2)):
                    q = dict(r, id=f"b{j}_{r['id']}", **{nm["ev"]: f"b{j}_{r[nm['ev']]}", nm["off"]: str(len(rows) + 10 + j)})
                    q.update({c_: str(v) for c_, v in safe.items()})
                    q[col] = str(t)
                    add.append(q)
                batches[b] = rows + add[:1 if b == "visible.csv" else 2]
    header = list(batches["visible.csv"][0].keys())
    # legacy files: written in the stage's legacy language, then RE-LIFTED (the legacy semantics are what the file means)
    for k, st in enumerate(stages):
        st["legacy_lang"] = st.get("lift") or rng.choice(LEGACY_LANGS[st["engine"]])
        st["target_lang"] = E.EXEC_LANG[st["engine"]]
        try:
            text = ir6.lower(legacies[k], st["legacy_lang"])
            legacies[k] = ir6.lift(text, st["legacy_lang"])
        except Exception as e:                          # noqa: BLE001
            REJECTS.append(f"legacy lift {st['legacy_lang']}: {repr(e)[:60]}")
            return None
        st["legacy_text"] = text
    try:
        refs = {}
        for b, rows in batches.items():
            cur = rows
            rej = []
            for k, t in enumerate(truths):
                r = ir.interpret(t, cur, states[b])
                if r["rejects"] is not None:
                    rej += r["rejects"]
                if k < len(truths) - 1:
                    cur = [{c: ("" if v is None else str(v)) for c, v in x.items()} for x in r["clean"]]
            refs[b] = dict(clean=r["clean"], rejects=rej if any(t.get("quarantine") for t in truths) else None)
    except (ir.RefError, KeyError, TypeError) as e:
        REJECTS.append(f"reference error {type(e).__name__} {str(e)[:50]}")
        return None
    cols_out = ir.out_cols(truths[-1])
    vis = refs["visible.csv"]
    if len(vis["clean"]) < 2:
        REJECTS.append("tiny output")
        return None
    want = key_of(vis, cols_out)

    def vres(specs, b="visible.csv"):
        try:
            return key_of(run_pipeline(stages, specs, batches[b], states[b], fast="spark")[0], cols_out)
        except W.RunError:
            return "error"
    if vres(truths) != want:
        REJECTS.append("truth differs on the engines")
        return None
    for k, st in enumerate(stages):                     # per-fault identifiability
        for f in st["faults"]:
            t2, _ = build_stage(st["mechs"], [x for x in st["faults"] if x != f], PARADIGMS[st["paradigm"] if st["paradigm"] != "P8" else st["lift_of"]]["out"],
                                nm, params, cols, choice, k == len(stages) - 1)
            _, one = build_stage(st["mechs"], [f], PARADIGMS[st["paradigm"] if st["paradigm"] != "P8" else st["lift_of"]]["out"],
                                 nm, params, cols, choice, k == len(stages) - 1)
            specs = list(truths)
            specs[k] = one
            if vres(specs) == want:
                REJECTS.append(f"invisible fault {f}")
                return None
    # only the intended requirements are unknown: no coincidental state-threshold or value-exclusion filter fits the visible
    # batch while changing a hidden result (Phase 5 rule, extended to every stage and to lt / le / <>)
    dp_pairs = {(dp_ref(d, nm)[0], json.dumps(dp_ref(d, nm)[1])) for d in dps}
    srefs = [["file", f, k_] for f, d_ in states["visible.csv"].items() for k_ in d_] + \
            [["sub", ["file", f, a], ["file", f, b]] for f, d_ in states["visible.csv"].items() for a in d_ for b in d_ if a != b]
    vrows = batches["visible.csv"]
    icols = [c for c in header if c != "id" and sum(str(r.get(c, "")).strip().isdigit() for r in vrows) >= 0.5 * len(vrows)]
    tcols = [c for c in header if c not in icols and c != "id" and 1 < len({r.get(c) for r in vrows}) <= 4]
    dcols = sorted({c for c, _ in dp_pairs})
    for k in range(len(stages)):
        extra = [[cmp, ["cast_int", ["col", c]], v] for c in dcols for v in srefs for cmp in ("gt", "ge", "lt", "le")
                 if (c, json.dumps(v)) not in dp_pairs]
        if k == len(stages) - 1:
            extra += [["ne", ["col", c], ["lit", v]] for c in tcols for v in sorted({r.get(c) for r in vrows})]
        for f_ in extra:
            alt = list(truths)
            alt[k] = dict(truths[k], filter=["and", truths[k]["filter"], f_] if truths[k].get("filter") else f_)
            if vres(alt) == want and any(vres(alt, b) != vres(truths, b) for b in ("hidden1.csv", "hidden2.csv")):
                REJECTS.append(f"coincidental filter {f_[0]}")
                return None
    for d, mode in dps.items():                         # the boundary is (un)determined by the visible batch as declared
        k = next(i for i, st in enumerate(stages) if any(DP_MECH.get(m) == d for m in st["mechs"]))
        col, rhs, inc, exc = dp_ref(d, nm)
        flip = list(truths)
        flip[k] = _flip(truths[k], rhs)
        if (vres(flip) == want) == (mode == "visible"):
            REJECTS.append(f"boundary visibility {d}")
            return None
        if any(vres(flip, b) == vres(truths, b) for b in ("hidden1.csv", "hidden2.csv")):
            REJECTS.append(f"hidden does not test {d}")
            return None
    pid = f"P6.{par}{('.' + stages[0].get('lift', '')) if par == 'P8' else ''}{('.' + spec.get('hybrid', '')) if par == 'P9' else ''}." + \
          "-".join(f"{st['paradigm']}:{st['engine']}" for st in stages).replace(":", "_") + f".{seed}"
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    if ws.parent.exists():
        shutil.rmtree(ws.parent)
    for d_ in (ws / "data", ws / "docs", ws / "pipeline", ws / "models", hid):
        d_.mkdir(parents=True, exist_ok=True)
    W.write_csv(ws / "data" / "visible.csv", header, batches["visible.csv"])
    for fname, dd in states["visible.csv"].items():
        (ws / fname).write_text(json.dumps(dd))
    # stage files + schema.yml (intermediate stage tests from the intended stage outputs on the visible batch)
    cur = batches["visible.csv"]
    schema = dict(version=2, models=[])
    for k, st in enumerate(stages):
        ext = {"sql": "sql", "postgres": "sql", "snowflake": "sql", "hive": "hql", "j2": "sql.j2", "py": "py", "scala": "scala"}[st["legacy_lang"]]
        fname = f"stage{k + 1}_{st['paradigm'].lower()}.{ext}"
        (ws / ("models" if st["legacy_lang"] == "j2" else "pipeline") / fname).write_text(st["legacy_text"])
        st["file"] = f"{'models' if st['legacy_lang'] == 'j2' else 'pipeline'}/{fname}"
        r = ir.interpret(truths[k], cur, states["visible.csv"])
        if k < len(stages) - 1:
            st["tests"] = stage_tests(truths[k], r, k)
            schema["models"].append(dict(name=f"stage{k + 1}", columns=[dict(name=t["column"], tests=[t["test"] if t["test"] != "accepted_values"
                                                                                                       else {"accepted_values": {"values": t["values"]}}])
                                                                        for t in st["tests"]]))
            cur = [{c: ("" if v is None else str(v)) for c, v in x.items()} for x in r["clean"]]
        else:
            st["tests"] = []
    (ws / "models" / "schema.yml").write_text(yaml.safe_dump(schema, sort_keys=False))
    hidden_state = {}
    for b in ("hidden1.csv", "hidden2.csv"):
        W.write_csv(hid / b, header, batches[b])
        r = refs[b]
        (hid / (b + ".expected.json")).write_text(json.dumps(dict(output=[[row[c] for c in cols_out] for row in r["clean"]], output_cols=cols_out,
                                                                 quarantine_ids=sorted(x["id"] for x in r["rejects"]) if r["rejects"] is not None else None)))
        hidden_state[b] = states[b]
    unique = {"group": cols_out[0], "group_region": cols_out[0], "entity": nm["key"]}.get(
        PARADIGMS[stages[-1]["paradigm"] if stages[-1]["paradigm"] != "P8" else stages[-1]["lift_of"]]["out"], "id")
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=cols_out, rows=[[row[c] for c in cols_out] for row in vis["clean"]]),
              dict(kind="row_count", n=len(vis["clean"])), dict(kind="unique", col=unique)]
    if vis["rejects"] is not None:
        checks.append(dict(kind="quarantine_ids", id="id", ids=sorted(x["id"] for x in vis["rejects"])))
    docs = make_docs(rng, {d: (m, choice[d]) for d, m in dps.items()}, nm)
    contract = dict(output_cols=cols_out, output_types=W._types(vis["clean"], cols_out), unique_key=unique, public_checks=checks,
                    quarantine_table="rejects" if vis["rejects"] is not None else None, requirements=docs["contract.json"],
                    stages=[dict(file=st["file"], paradigm=st["paradigm"] if st["paradigm"] != "P8" else "P8", engine=st["engine"],
                                 legacy_language=st["legacy_lang"], target_language=st["target_lang"], model=f"stage{k + 1}")
                            for k, st in enumerate(stages)])
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    for src in ("docs/runbook.json", "docs/ticket.json"):
        (ws / src).write_text(json.dumps(dict(claims=docs[src]), indent=1))
    variants = {d: [(_flip(truths[k], dp_ref(d, nm)[1]) if any(DP_MECH.get(m) == d for m in stages[k]["mechs"]) else truths[k]) for k in range(len(stages))]
                for d in undecided}
    (hid / "stakeholder.json").write_text(json.dumps(dict(truths=truths, variants=variants)))
    return dict(pid=pid, paradigm=par, tier=TIER[par], hybrid=spec.get("hybrid"), seed=seed,
                ws=str(ws), hidden_dir=str(hid), hidden_state=hidden_state, names=nm, dps=dps, inclusive=choice, undecided=undecided,
                stages=[{k: v for k, v in st.items() if k not in ("legacy_text",)} for st in stages], faults=[f for st in stages for f in st["faults"]],
                spec=spec)


def _flip(spec, rhs):
    s = copy.deepcopy(spec)
    sw = {"ge": "gt", "gt": "ge", "le": "lt", "lt": "le"}

    def rw(e):
        if isinstance(e, list):
            if e and e[0] in sw and len(e) == 3 and e[2] == rhs:
                return [sw[e[0]], e[1], e[2]]
            return [e[0]] + [rw(x) for x in e[1:]]
        return e
    s["filter"] = rw(s.get("filter"))
    return s


# ------------------------------------------------------------------ stakeholder + evaluator
def stakeholder_answer(project, probe_rows):
    if not probe_rows or len(probe_rows) > 1:
        return dict(answer="refused", reason="a question carries exactly 1 probe row")
    st = json.loads((Path(project["hidden_dir"]) / "stakeholder.json").read_text())
    state = W.state_of(project["ws"])
    cols = json.loads((Path(project["ws"]) / "contract.json").read_text())["output_cols"]

    def run(specs):
        cur, rej = probe_rows, []
        for k, t in enumerate(specs):
            r = ir.interpret(t, cur, state)
            rej += r["rejects"] or []
            cur = [{c: ("" if v is None else str(v)) for c, v in x.items()} for x in r["clean"]]
        return [W.table_key(r["clean"], cols), sorted(str(x["id"]) for x in rej)]
    try:
        a = run(st["truths"])
        for v in st["variants"].values():
            if run(v) != a:
                return dict(answer="undetermined", reason="the business has not decided this requirement")
    except (ir.RefError, KeyError, ValueError, TypeError):
        return dict(answer="unanswerable", reason="the probe row is not valid business input")
    return dict(answer="output", output=a)


def evaluate6(project, files):
    """files: [target-language text per stage]. Executes them on each stage's engine over both hidden batches."""
    hid = Path(project["hidden_dir"])
    fails = []
    for b in ("hidden1.csv", "hidden2.csv"):
        header, rows = W.read_csv(hid / b)
        state = dict(W.state_of(project["ws"]), **project["hidden_state"][b])
        cur, rej, any_q = rows, [], False
        try:
            for k, (st, code) in enumerate(zip(project["stages"], files)):
                rt = E.ENGINES[st["engine"]]() if st["engine"] != "spark" else W.SparkCode()
                h = list(cur[0].keys()) if cur else st["in_cols"]
                res = rt.run(code, h, cur, state)
                if res["rejects"] is not None:
                    any_q = True
                    rej += res["rejects"]
                cur = [{c: ("" if v is None else (str(int(v)) if isinstance(v, float) and v == int(v) else str(v))) for c, v in r.items()}
                       for r in res["clean"]]
        except W.RunError as e:
            fails.append(f"{b}: runtime {e.cls}")
            continue
        ref = json.loads((hid / (b + ".expected.json")).read_text())
        oc = ref["output_cols"]
        if W.table_key(res["clean"], oc) != W.table_key([dict(zip(oc, r)) for r in ref["output"]], oc):
            fails.append(f"{b}: output differs")
        if ref.get("quarantine_ids") is not None and sorted(str(r.get("id")) for r in rej) != sorted(ref["quarantine_ids"]):
            fails.append(f"{b}: quarantine differs")
    if project["undecided"]:
        return dict(ok=False, fails=fails + ["requirement undecided: a submission cannot be correct"], unjustified=True)
    return dict(ok=not fails, fails=fails)
