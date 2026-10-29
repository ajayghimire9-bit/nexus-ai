"""Phase 5 requirement-grounded DE projects (NOT LOCKED). Extends the Phase 4 world (de_phase4.world: real .sql / .py
pipelines on real engines, multi-fault mechanisms, independent hidden-batch evaluator) with REQUIREMENT DECISION POINTS
whose correct business answer varies independently across projects, and with requirement documents.

Decision points (boundary semantics of a state-driven filter; the visible golden rows do not determine them unless the
mode is `visible`):
  watermark   F6: events exactly at watermark - allowed_lateness are KEPT (inclusive, >=) or EXCLUDED (exclusive, >)
  checkpoint  F4: the checkpoint offset is the LAST COMMITTED record (exclude it, >) or the NEXT TO READ (include it, >=)
The business choice is drawn per project (p = 0.5), so remembering one answer is worth nothing; remembering HOW to determine
it is the learnable part.

Per decision point a requirement MODE:
  explicit           one claim stating the boundary, in one of contract.json / docs/runbook.json / docs/ticket.json
  missing            no claim; the visible batch has no boundary row (a clarification can resolve it)
  conflict_approved  two opposite claims; the correct one has status 'approved', the other 'draft'; versions and dates are
                     drawn independently of correctness (so 'newest wins' is right only by chance)
  undecided          two opposite claims, both 'draft': the business has not decided; the stakeholder answers
                     'undetermined' and the correct outcome is a justified ABSTENTION (a submission counts as wrong)
  visible            no claim; the visible batch contains a boundary row (the golden rows decide)
Claims are STRUCTURED (subject = the state-reference expression the boundary is about, effect at the boundary, source,
status, version, date) with a plain-language text field. Phase 5 reads only the structured fields: a shared structured-
contract diagnostic, NOT a natural-language capability (no language model is used; see the report).

The stakeholder simulator is defined from the intended contract only: for <= 3 probe rows it returns the business-truth
output (clean rows + rejected ids) or 'undetermined' when the probe exercises an undecided requirement. It never returns a
program, a repair id or a hidden-test outcome."""
from __future__ import annotations

import copy
import json
import random
import shutil
from pathlib import Path

from nexus.de_phase4 import world as W, ir

DP_FAMS = {"watermark": "F6", "checkpoint": "F4"}
REF = {"watermark": ["sub", ["file", "watermark.json", "watermark"], ["file", "watermark.json", "allowed_lateness"]],
       "checkpoint": ["file", "checkpoint.json", "last_committed_offset"]}
MODES = ("explicit", "missing", "conflict_approved", "undecided", "visible")
SOURCES = ("contract.json", "docs/runbook.json", "docs/ticket.json")
DEBUG = {}
REJECTS = []                       # line offsets of rejected build attempts (diagnostics)
HELDOUT_POOLS = dict(ts=["evt_time", "observed_at"], offset=["kafka_offset", "seq_no"], event=["record_uid"], key=["tenant_id"],
                     val=["amount_cents"], region=["territory"], units=["pieces"], price=["unit_price_raw"])


def _col_of(dp, nm):
    return nm["ts"] if dp == "watermark" else nm["offset"]


def _threshold(dp, state):
    return ir.ev(REF[dp], {}, state)


def set_boundary(spec, dp, inclusive):
    """Rewrite the decision point's filter comparison in a truth spec: inclusive -> 'ge', exclusive -> 'gt'."""
    s = copy.deepcopy(spec)

    def rw(e):
        if isinstance(e, list):
            if e and e[0] in ("gt", "ge") and e[2] == REF[dp]:
                return ["ge" if inclusive else "gt", e[1], e[2]]
            return [e[0]] + [rw(x) for x in e[1:]]
        return e
    s["filter"] = rw(s.get("filter"))
    return s


def _conjuncts(f):
    if not f:
        return []
    return _conjuncts(f[1]) + _conjuncts(f[2]) if f[0] == "and" else [f]


def _replace_conjunct(spec, ref, new):
    cs = _conjuncts(spec.get("filter"))
    if not any(c[2] == ref for c in cs if len(c) > 2):
        return None
    out = None
    for c in cs:
        c2 = new if len(c) > 2 and c[2] == ref else c
        out = c2 if out is None else ["and", out, c2]
    return dict(spec, filter=out)


def claim_text(dp, effect):
    return {"watermark": f"Events exactly at the watermark minus the allowed lateness are {effect}.",
            "checkpoint": f"The record at the stored checkpoint offset is {effect} on restart."}[dp]


def make_docs(rng, dps):
    """dps: {dp: (mode, inclusive)} -> {source: [claims]} plus one unrelated claim (a distractor)."""
    docs = {s: [] for s in SOURCES}
    n = 0
    for dp, (mode, inclusive) in dps.items():
        right, wrong = ("kept", "excluded") if inclusive else ("excluded", "kept")
        if mode == "explicit":
            placed = [(rng.choice(SOURCES), right, rng.choice(["approved", "draft"]))]
        elif mode == "conflict_approved":
            a, b = rng.sample(SOURCES, 2)
            placed = [(a, right, "approved"), (b, wrong, "draft")]
        elif mode == "undecided":
            a, b = rng.sample(SOURCES, 2)
            placed = [(a, right, "draft"), (b, wrong, "draft")]
        else:
            placed = []
        for src, eff, status in placed:
            n += 1
            docs[src].append(dict(id=f"R{n}", source=src, subject=dict(state_ref=REF[dp]), effect_at_boundary=eff, status=status,
                                  version=rng.randint(1, 9), updated=f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}",
                                  text=claim_text(dp, eff)))
    src = rng.choice(SOURCES)
    docs[src].append(dict(id="N0", source=src, subject=dict(note="operations"), status="approved", version=1, updated="2026-01-01",
                          text="Pipelines run hourly; page the on-call engineer on failure."))
    return docs


def _boundary_rows(rows, col, t, rng, k, safe):
    """k rows at the boundary value t of `col`; identity columns made fresh; `safe` = {column: value} keeps the row inside
    every OTHER decision point's filter, so the row tests only this boundary."""
    base = [r for r in rows if r.get(col, "").strip().isdigit()]
    out = []
    for j in range(k):
        r = dict(rng.choice(base))
        r["id"] = f"b{j}_{r['id']}"
        for c in r:
            if c.endswith("_id") or c in ("event_id", "msg_id", "record_uid"):
                r[c] = f"b{j}_{r[c]}"
        r.update({c: str(v + j) for c, v in safe.items()})
        r[col] = str(t)
        out.append(r)
    return out


def make_project5(spec, seed, root):
    """spec: dict(dps={dp: mode}, extra_faults=[...], runtime, names='base'|'heldout', shape=None, k_extra=0).
    Returns the project dict (Phase 4 fields + dps, undecided, docs) or raises RuntimeError."""
    for attempt in range(80):
        p = _make5(spec, seed, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build a phase-5 project for {spec} seed {seed}")


def _make5(spec, seed, root, attempt):
    rng = random.Random(f"p5de|{json.dumps(spec, sort_keys=True)}|{seed}|{attempt}")
    dps = spec["dps"]
    need = [DP_FAMS[d] for d in dps]
    shape = spec.get("shape") or rng.choice([s for s in ("row", "agg", "entity") if all(f in W.SHAPES[s] for f in need)])
    if not all(f in W.SHAPES[shape] for f in need):
        REJECTS.append("if not all(f in W.SHAPES[shape] for f in need):")
        return None
    others = [f for f in W.SHAPES[shape] if f in W.SOURCE_FAMS and f not in need and not (f == "F3" and "F4" in need)]
    extra = list(spec.get("extra_faults", [])) or rng.sample(others, min(len(others), spec.get("k_extra", 0)))
    if any(f not in W.SHAPES[shape] for f in extra) or ("F3" in extra and "F4" in need):
        REJECTS.append("if any(f not in W.SHAPES[shape] for f in extra) or ('F3' in ")
        return None
    faults = need + [f for f in extra if f not in need]
    oks = []
    has = set(faults)
    pools = dict(W.POOLS)
    if spec.get("names") == "heldout":
        pools.update(HELDOUT_POOLS)
    nm = {c: rng.choice(v) for c, v in pools.items()}
    params = dict(policy=rng.choice(["quarantine", "default"]), label=rng.choice(["UNKNOWN", "OTHER"]), lateness=rng.choice([5, 10]))
    params["parse_col"] = {"row": rng.choice([nm["units"], nm["price"]]), "entity": nm["price"], "agg": nm["val"]}[shape]
    truth, legacy = W.build(shape, faults, oks, nm, params)
    choice = {d: rng.random() < 0.5 for d in dps}                  # inclusive?
    for d in dps:
        truth = set_boundary(truth, d, choice[d])
    undecided = [d for d, m in dps.items() if m == "undecided"]
    pid = f"P5.{'+'.join(f'{d}:{m}' for d, m in sorted(dps.items()))}.{'-'.join(faults)}.{spec['runtime']}.{seed}"
    pid = pid.replace(":", "_")
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    if ws.parent.exists():
        shutil.rmtree(ws.parent)
    (ws / "data").mkdir(parents=True)
    (ws / "docs").mkdir()
    hid.mkdir(parents=True)
    n = rng.randint(40, 50)                            # enough visible evidence that coincidental thresholds are rare
    batches = {b: W.gen_rows(shape, has, rng, n + dn, nm, params, bp) for b, dn, bp in
               (("visible.csv", 0, 0.25), ("hidden1.csv", 20, 0.3), ("hidden2.csv", 30, 0.3))}
    if "F4" in has and "F6" in has:                     # out-of-order arrivals: event time independent of the log offset
        for b, rows in batches.items():                  # (replayed copies keep their event's time)
            tmap = {}
            for r in rows:
                r[nm["ts"]] = tmap.setdefault(r[nm["event"]], str(100 + rng.randint(0, 3 * len(rows))))
    states = {}
    for b, rows in batches.items():
        st = {}
        if "F4" in has:
            st["checkpoint.json"] = {"last_committed_offset": rng.randint(3, max(4, len(rows) // 3))}
        if "F6" in has:
            st["watermark.json"] = {"watermark": 100 + 3 * len(rows) // 2 + rng.randint(-2, 2), "allowed_lateness": params["lateness"]}
        states[b] = st
    # boundary control: remove boundary rows from the visible batch unless the mode is 'visible' (then make sure one
    # exists); hidden batches always contain boundary rows, so a wrong boundary choice fails the evaluator
    for d, mode in dps.items():
        col = _col_of(d, nm)
        for b, rows in batches.items():
            t = _threshold(d, states[b])
            safe = {_col_of(o, nm): _threshold(o, states[b]) + 50 for o in dps if o != d}
            if b == "visible.csv" and mode != "visible":
                batches[b] = [r for r in rows if r.get(col) != str(t)]
            elif b != "visible.csv" or not any(r.get(col) == str(t) for r in rows):
                batches[b] = rows + _boundary_rows(rows, col, t, rng, 1 if b == "visible.csv" else 2, safe)
    header = list(batches["visible.csv"][0].keys())
    variants = {}
    try:
        refs = {b: ir.interpret(truth, rows, states[b]) for b, rows in batches.items()}
        for d in undecided:
            variants[d] = set_boundary(truth, d, not choice[d])
    except ir.RefError:
        REJECTS.append("except ir.RefError:")
        return None
    cols = ir.out_cols(truth)
    vis = refs["visible.csv"]
    if len(vis["clean"]) < 2:
        REJECTS.append("if len(vis['clean']) < 2:")
        return None
    sq = W.SQLiteCode()

    def vres(sp, batch="visible.csv"):
        try:
            res = sq.run(ir.lower_sql(sp), header, batches[batch], states[batch])
        except W.RunError:
            return "error"
        return (W.table_key(res["clean"], cols), sorted(str(r["id"]) for r in res["rejects"]) if res["rejects"] is not None else None)
    want = (W.table_key(vis["clean"], cols), sorted(r["id"] for r in vis["rejects"]) if vis["rejects"] is not None else None)
    DEBUG['last'] = (truth, header, batches['visible.csv'], states['visible.csv'], cols)
    if vres(truth) != want:
        REJECTS.append("if vres(truth) != want:")
        return None
    for f in faults:                                             # per-fault identifiability (Phase 4 rule)
        _, one = W.build(shape, [f], [x for x in has if x != f], nm, params)
        for d in dps:
            one = set_boundary(one, d, choice[d])
        if vres(one) == want:
            REJECTS.append(f"invisible fault {f}")
            return None
    # only the intended requirement is unknown: no coincidental state-threshold filter (any integer column, any state
    # reference, > or >=) fits the visible batch while changing a hidden result - neither replacing a decision point's filter
    # nor added to the truth
    state_refs = [["file", f, k] for f, d_ in states["visible.csv"].items() for k in d_] + list(REF[d] for d in dps)
    int_cols = [c for c in header if c != "id" and sum(str(r.get(c, "")).strip().isdigit() for r in batches["visible.csv"]) >= 0.5 * len(batches["visible.csv"])]
    for c in int_cols:
        for v in state_refs:
            for cmp in ("gt", "ge"):
                f = [cmp, ["cast_int", ["col", c]], v]
                if any(c == _col_of(d, nm) and v == REF[d] for d in dps):     # the intended boundary ambiguity itself
                    continue
                alt = dict(truth, filter=["and", truth["filter"], f] if truth.get("filter") else f)
                if vres(alt) == want and any(vres(alt, b) != vres(truth, b) for b in ("hidden1.csv", "hidden2.csv")):
                    REJECTS.append(f"coincidental extra filter {c} {cmp} {json.dumps(v)}")
                    return None
                for d in dps:
                    rep_ = _replace_conjunct(truth, REF[d], f)
                    if rep_ is not None and vres(rep_) == want and any(vres(rep_, b) != vres(truth, b) for b in ("hidden1.csv", "hidden2.csv")) \
                            and not (c == _col_of(d, nm) and v == REF[d]):
                        REJECTS.append("coincidental replacement filter")
                        return None
    for d, mode in dps.items():                                  # the boundary is (un)determined by the visible batch as declared
        flip = set_boundary(truth, d, not choice[d])
        if (vres(flip) == want) == (mode == "visible"):
            REJECTS.append("if (vres(flip) == want) == (mode == 'visible'):")
            return None
        for b in ("hidden1.csv", "hidden2.csv"):                 # and the hidden batches always distinguish it
            if vres(flip, b) == vres(truth, b):
                REJECTS.append("if vres(flip, b) == vres(truth, b):")
                return None
    W.write_csv(ws / "data" / "visible.csv", header, batches["visible.csv"])
    for fname, dd in states["visible.csv"].items():
        (ws / fname).write_text(json.dumps(dd))
    hidden_state = {}
    for b in ("hidden1.csv", "hidden2.csv"):
        W.write_csv(hid / b, header, batches[b])
        r = refs[b]
        (hid / (b + ".expected.json")).write_text(json.dumps(dict(
            output=[[row[c] for c in cols] for row in r["clean"]], output_cols=cols,
            quarantine_ids=sorted(x["id"] for x in r["rejects"]) if r["rejects"] is not None else None)))
        hidden_state[b] = states[b]
    unique = {"row": "id", "entity": nm["key"], "agg": cols[0]}[shape]
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=cols, rows=[[row[c] for c in cols] for row in vis["clean"]]),
              dict(kind="row_count", n=len(vis["clean"])), dict(kind="unique", col=unique)]
    if vis["rejects"] is not None:
        checks.append(dict(kind="quarantine_ids", id="id", ids=sorted(x["id"] for x in vis["rejects"])))
    lang = W.LANG[spec["runtime"]]
    docs = make_docs(rng, {d: (m, choice[d]) for d, m in dps.items()})
    contract = dict(output_table="clean", quarantine_table="rejects" if vis["rejects"] is not None else None, output_cols=cols,
                    output_types=W._types(vis["clean"], cols), unique_key=unique, runtime=spec["runtime"], pipeline_file=f"pipeline.{lang}",
                    engine_semantics="Apache Spark 4.0.1, spark.sql.ansi.enabled=true" if spec["runtime"] == "spark" else "SQLite 3",
                    public_checks=checks, notes=W.notes(shape, has, nm, params), requirements=docs["contract.json"])
    style_rng = random.Random(f"style|{pid}")
    if lang == "sql":
        style = dict(kw=style_rng.choice(["upper", "lower"]), comments=style_rng.random() < 0.7, header=["legacy pipeline"],
                     views=style_rng.choice([("stage1", "stage2"), ("s1_dedup", "s2_select")]))
    else:
        style = dict(names=style_rng.choice([("stage1", "stage2", "kept"), ("df1", "df2", "df3")]), comments=True, header=["legacy pipeline"],
                     where=style_rng.choice(["filter", "where"]))
    (ws / f"pipeline.{lang}").write_text(ir.lower(legacy, lang, style))
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    for src in ("docs/runbook.json", "docs/ticket.json"):
        (ws / src).write_text(json.dumps(dict(claims=docs[src]), indent=1))
    (ws / "README.md").write_text(f"Goal: repair pipeline.{lang} so it satisfies contract.json; requirements may also be in docs/.\n")
    stake = dict(truth=truth, variants=variants, header=header)
    (hid / "stakeholder.json").write_text(json.dumps(stake))
    return dict(pid=pid, family="+".join(faults), faults=faults, oks=oks, shape=shape, seed=seed, runtime=spec["runtime"], lang=lang,
                ws=str(ws), hidden_dir=str(hid), hidden_state=hidden_state, params=params, names=nm, dps=dict(dps),
                inclusive={d: choice[d] for d in dps}, undecided=undecided, spec=spec)


# ------------------------------------------------------------------ stakeholder simulator (from the intended contract only)
MAX_PROBE_ROWS = 1


def stakeholder_answer(project, probe_rows):
    """One bounded clarification: the expected output for <= MAX_PROBE_ROWS probe rows under the INTENDED contract, or
    'undetermined' if the probe exercises a requirement the business has not decided."""
    if not probe_rows or len(probe_rows) > MAX_PROBE_ROWS:
        return dict(answer="refused", reason=f"a question carries 1..{MAX_PROBE_ROWS} probe rows")
    st = json.loads((Path(project["hidden_dir"]) / "stakeholder.json").read_text())
    state = W.state_of(project["ws"])
    try:
        res = ir.interpret(st["truth"], probe_rows, state)
        for d, v in st["variants"].items():
            alt = ir.interpret(v, probe_rows, state)
            if _key(alt, project) != _key(res, project):
                return dict(answer="undetermined", reason="the business has not decided this requirement")
    except (ir.RefError, KeyError, ValueError):
        return dict(answer="unanswerable", reason="the probe rows are not valid business input")
    return dict(answer="output", output=_key(res, project))


def _key(res, project):
    cols = json.loads((Path(project["ws"]) / "contract.json").read_text())["output_cols"]
    return [W.table_key(res["clean"], cols), sorted(str(r["id"]) for r in res["rejects"]) if res["rejects"] is not None else None]


def evaluate5(project, code, runtime=None):
    """Hidden-batch evaluation; for a project with an undecided requirement the only correct outcome is abstention."""
    ev = W.evaluate(project, code, runtime)
    if project["undecided"]:
        return dict(ev, ok=False, fails=ev["fails"] + ["requirement undecided: a submission cannot be correct"], unjustified=True)
    return ev
