"""Phase 3 data-engineering learner on the shared experience interfaces (NOT LOCKED).

Operating cycle per project: INVESTIGATE (read contract.json / pipeline.json / state files / the visible batch header; run
the legacy pipeline on the project's real runtime; collect evidence) -> ATTEMPT (best-first search over generic pipeline
edit operators, ordered by the learned policy) -> LEARN FROM FAILURE (every evaluated candidate's runtime error class,
failing public checks and per-column diff kinds are recorded; edits that did not change the evidence are refutations; edits
that passed more checks are provisional partial successes, independently observed on the visible batch) -> REPAIR (the
search continues from the best partial state) -> VERIFY (submit only when EVERY public check passes on the real runtime;
the independent evaluator then runs hidden batches) -> REUSE (learned skills and the policy apply to the next project).

Memory (state["DE"]):
  w        pi_de: weights evidence-feature -> operator type (positive from verified solves; negative from refutations - the
           refutation part is incomplete-experience learning and is OFF in the Solved-Only cohort)
  skills   L_de: admitted skills = verified operator-type sequences with an evidence precondition (feature set), contract
           (checks they satisfied), provenance and validation projects; retrieval by precondition overlap
  P        provisional records: partial successes (operator sequences that raised the passed-check count without solving)
           and refutations; a provisional sequence is promoted to a skill only after admission on separate projects
Operators are generic (column / value parameters enumerated from the schema, state files and constants mined from the golden
rows); there is no rule that maps a contract kind or an error class to an operator - that mapping is what pi_de learns."""
from __future__ import annotations

import copy
import itertools
import json
import random
import time
from pathlib import Path

from nexus.campaign3 import de_world as W

OPS = ("try_parse", "quarantine_invalid", "default_fill", "real_div", "zero_guard", "round2", "dedup_latest", "dedup_first",
       "filter_file")
# the strong conventional baseline's fixed, engineer-sensible operator order (no learning)
BASELINE_ORDER = ("try_parse", "quarantine_invalid", "dedup_latest", "filter_file", "zero_guard", "real_div", "round2",
                  "dedup_first", "default_fill")


def empty_de():
    return dict(w={}, skills={}, P=[], next_id=0)


# ------------------------------------------------------------------ investigation / evidence
def _walk(e):
    if isinstance(e, list):
        yield e
        for x in e[1:]:
            yield from _walk(x)


def _cols_in(spec):
    out = []
    for _, x in spec["outputs"]:
        for n in _walk(x):
            if n and n[0] == "col" and n[1] not in out:
                out.append(n[1])
    return out


class Investigation:
    def __init__(self, ws, runtime):
        self.ws, self.rt = Path(ws), runtime
        self.contract = json.loads((self.ws / "contract.json").read_text())
        self.legacy = json.loads((self.ws / "pipeline.json").read_text())
        self.header = W._rows_csv(self.ws / "data" / "visible.csv")[0]
        self.raw_vals = {v for r in W._rows_csv(self.ws / "data" / "visible.csv")[1] for v in r}
        self.files = {}
        for p in self.ws.glob("*.json"):
            if p.name not in ("contract.json", "pipeline.json"):
                d = json.loads(p.read_text())
                for k, v in (d.items() if isinstance(d, dict) else []):
                    if isinstance(v, (int, float)):
                        self.files[(p.name, k)] = v
        ex = [c for c in self.contract["public_checks"] if c["kind"] == "example_rows"]
        self.consts_num, self.consts_str = [0], []
        for c in ex:
            for row in c["rows"]:
                for v in row:
                    if isinstance(v, str) and v not in self.raw_vals and v not in self.consts_str:
                        self.consts_str.append(v)
        self.runs = 0

    def run(self, spec):
        self.runs += 1
        try:
            res = self.rt.run(self.ws, spec)
            err = None
        except W.RunError as e:
            return dict(ok=False, error=e.cls, err_loc=_err_loc(e.msg), passed=[], failed=["no_error"],
                        features={f"err:{_err_class(e.cls)}", "fail:no_error"}, score=0, n_checks=len(self.contract["public_checks"]))
        passed, failed = [], []
        for chk in self.contract["public_checks"]:
            (passed if W.run_check(chk, res, None) else failed).append(chk["kind"])
        feats = {f"fail:{k}" for k in failed} | _diff_features(res, self.contract)
        return dict(ok=not failed, error=err, passed=passed, failed=failed, features=feats,
                    score=len(passed) + graded(res, self.contract), n_checks=len(self.contract["public_checks"]))


def graded(res, contract):
    """Type-aware graded credit in [0, 0.95]: 0.6 x fraction of golden rows reproduced exactly (whole typed rows: a missing or
    constant column earns nothing) + 0.25 x row-count closeness + 0.1 x numeric closeness of key-matched numeric cells
    (missing / non-numeric values earn 0); used only to order search and admission, never to accept."""
    ex = next((c for c in contract["public_checks"] if c["kind"] == "example_rows"), None)
    out = res["output"]
    if not ex or not ex["rows"]:
        return 0.0
    cols = ex["cols"]
    have = {tuple(W._num(r.get(c)) for c in cols) for r in out}
    frac = sum(tuple(W._num(v) for v in row) in have for row in ex["rows"]) / len(ex["rows"])
    n_exp = len(ex["rows"])
    close = max(0.0, 1 - abs(len(out) - n_exp) / max(n_exp, 1))
    # numeric closeness on rows matched by the first column (aggregates move toward the golden totals)
    got = {r.get(cols[0]): r for r in out}
    num = []
    for row in ex["rows"]:
        g = got.get(row[0])
        for j, c in enumerate(cols[1:], 1):
            w_, h = row[j], (g or {}).get(c)
            if isinstance(w_, (int, float)) and not isinstance(w_, bool):
                num.append(0.0 if not isinstance(h, (int, float)) else max(0.0, 1 - abs(h - w_) / max(abs(w_), abs(h), 1)))
    numc = sum(num) / len(num) if num else 0.0
    return round(0.6 * frac + 0.25 * close + 0.1 * numc, 4)


def _err_loc(msg):
    """The offending value / expression quoted by the runtime (Spark names the malformed value and the expression)."""
    import re
    m = re.search(r"The value '([^']*)'", msg) or re.search(r"\[(\w+)\]", msg)
    return m.group(0) if m else msg[:60]


def _err_class(cls):
    c = str(cls).upper()
    for k in ("CAST_INVALID_INPUT", "DIVIDE_BY_ZERO", "NUMBER_FORMAT", "ARITHMETIC", "ANALYSIS"):
        if k in c:
            return k
    return c[:30]


def _diff_features(res, contract):
    """Generic per-column diff kinds between the run's output and the golden rows (matched on the first column)."""
    ex = next((c for c in contract["public_checks"] if c["kind"] == "example_rows"), None)
    if not ex or not ex["cols"]:
        return set()
    cols = ex["cols"]
    got = {}
    for r in res["output"]:
        got.setdefault(r.get(cols[0]), []).append(r)
    feats = set()
    want_keys = {row[0] for row in ex["rows"]}
    if any(len(v) > 1 for v in got.values()):
        feats.add("diff:dup_keys")
    if set(got) - want_keys:
        feats.add("diff:extra_rows")
    if want_keys - set(got):
        feats.add("diff:missing_rows")
    for row in ex["rows"]:
        g = got.get(row[0])
        if not g:
            continue
        for j, c in enumerate(cols[1:], 1):
            want, have = row[j], g[0].get(c)
            if W._num(want) == W._num(have):
                continue
            if want is None:
                feats.add("diff:expect_null")
            elif have is None:
                feats.add("diff:got_null")
            elif isinstance(want, float) and isinstance(have, (int, float)) and int(want) == int(have):
                feats.add("diff:fraction_lost")
            elif isinstance(want, str):
                feats.add("diff:text_value")
            else:
                feats.add("diff:value")
    return feats


# ------------------------------------------------------------------ generic edit operators
def _replace(e, pred, fn):
    if isinstance(e, list):
        if pred(e):
            return fn(e)
        return [e[0]] + [_replace(x, pred, fn) for x in e[1:]]
    return e


def candidates(op, spec, inv):
    """All parameterisations of operator `op` on spec -> list of (spec', param description)."""
    out = []
    cols = [c for c in inv.header if c != "id"]
    used = _cols_in(spec)
    if op == "try_parse":
        for c in used:
            s = copy.deepcopy(spec)
            s["outputs"] = [[n, _replace(x, lambda e: e[0] == "cast_int" and e[1] == ["col", c], lambda e: ["try_int", e[1]])]
                            for n, x in s["outputs"]]
            if s != spec:
                out.append((s, c))
    elif op == "quarantine_invalid":
        for c in used:
            q = ["valid_int", ["col", c]]
            s = copy.deepcopy(spec)
            old = s.get("quarantine")
            s["quarantine"] = ["not", q] if not old else ["not", ["and", ["not", old], q]]
            out.append((s, c))
    elif op == "default_fill":
        for c in used:
            for v in inv.consts_num:
                s = copy.deepcopy(spec)
                s["outputs"] = [[n, _replace(x, lambda e: e[0] in ("cast_int", "try_int") and e[1] == ["col", c],
                                             lambda e: ["coalesce", ["try_int", e[1]], ["lit", v]])] for n, x in s["outputs"]]
                if s != spec:
                    out.append((s, f"{c}={v}"))
            for v in inv.consts_str:
                s = copy.deepcopy(spec)
                s["outputs"] = [[n, _replace(x, lambda e: e == ["col", c], lambda e: ["coalesce", ["nullif_empty", e], ["lit", v]])]
                                for n, x in s["outputs"]]
                if s != spec:
                    out.append((s, f"{c}='{v}'"))
    elif op == "real_div":
        s = copy.deepcopy(spec)
        s["outputs"] = [[n, _replace(x, lambda e: e[0] == "div", lambda e: ["div_real"] + e[1:])] for n, x in s["outputs"]]
        if s != spec:
            out.append((s, ""))
    elif op == "zero_guard":
        s = copy.deepcopy(spec)
        s["outputs"] = [[n, _replace(x, lambda e: e[0] in ("div", "div_real") and e[2][0] != "nullif_zero",
                                     lambda e: [e[0], e[1], ["nullif_zero", e[2]]])] for n, x in s["outputs"]]
        if s != spec:
            out.append((s, ""))
    elif op == "round2":
        for i, (n, x) in enumerate(spec["outputs"]):
            if x[0] not in ("col", "round2") and any(m[0] in ("div", "div_real") for m in _walk(x)):
                s = copy.deepcopy(spec)
                s["outputs"][i] = [n, ["round2", x]]
                out.append((s, n))
    elif op == "dedup_latest" and not spec.get("dedup"):
        for k, o in itertools.permutations(cols, 2):
            s = copy.deepcopy(spec)
            s["dedup"] = dict(key=k, order=["cast_int", ["col", o]])
            out.append((s, f"{k} by {o}"))
    elif op == "dedup_first" and not spec.get("dedup"):
        for k in cols:
            s = copy.deepcopy(spec)
            s["dedup"] = dict(key=k)
            out.append((s, k))
    elif op == "filter_file":
        vals = [["file", f, k] for (f, k) in inv.files]
        vals += [["sub", ["file", f1, k1], ["file", f2, k2]] for (f1, k1), (f2, k2) in itertools.permutations(inv.files, 2)]
        for c in cols:
            for v in vals:
                for cmp in ("gt", "ge"):
                    s = copy.deepcopy(spec)
                    f = [cmp, ["cast_int", ["col", c]], v]
                    s["filter"] = f if not s.get("filter") else ["and", s["filter"], f]
                    out.append((s, f"{c} {cmp} {json.dumps(v)}"))
    return out


# ------------------------------------------------------------------ the search procedure (pi_de) with memory
def op_score(de, feats, op, order=None):
    if order is not None:
        return -order.index(op)
    return sum(de["w"].get(f, {}).get(op, 0.0) for f in feats)


def solve(project, de, runtime, budget_s=2.0, max_depth=3, order=None, use_skills=True, log=None):
    """Investigate -> attempt -> repair -> verify on the real runtime. Returns the episode record (trace included)."""
    t0 = time.time()
    inv = Investigation(project["ws"], runtime)
    trace = []
    seen = set()
    legacy = inv.legacy
    ev0 = inv.run(legacy)
    diff = None
    if getattr(runtime, "name", "") != "sqlite":
        # differential investigation: also execute the legacy pipeline on the cheap SQLite engine; its evidence (silent
        # wrong rows where Spark raises) is added to the starting signature used for skill retrieval and pi_de
        dev = Investigation(project["ws"], W.SQLiteRuntime()).run(legacy)
        diff = sorted(dev["features"])
        ev0["features"] = ev0["features"] | dev["features"]
    trace.append(dict(step="investigate", edits=[], error=ev0.get("error"), passed=ev0["passed"], failed=ev0["failed"],
                      features=sorted(ev0["features"]), differential_sqlite=diff))
    seen.add(json.dumps(legacy, sort_keys=True))
    if ev0["ok"]:
        return dict(solved_visible=True, spec=legacy, edits=[], runs=inv.runs, wall=time.time() - t0, trace=trace, start=ev0)
    frontier = [(ev0["score"], 0, [], legacy, ev0)]
    refutations, partials = [], []
    skill_seqs = []
    if use_skills:
        for sid, sk in de["skills"].items():
            ov = len(set(sk["pre"]) & ev0["features"]) / max(1, len(set(sk["pre"]) | ev0["features"]))
            if ov >= sk.get("match", 0.5):
                skill_seqs.append((ov, sid, sk["ops"]))
        skill_seqs.sort(reverse=True)
    best = None
    tick = itertools.count()

    def expand(state, ops_seq=None):
        score, _, edits, spec, ev = state
        ops = ops_seq or sorted(OPS, key=lambda o: (-op_score(de, ev["features"], o, order), OPS.index(o)))
        for op in ops:
            for s2, prm in candidates(op, spec, inv):
                if time.time() - t0 > budget_s:
                    return "timeout"
                key = json.dumps(s2, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                ev2 = inv.run(s2)
                rec = dict(step="attempt", edits=edits + [f"{op}({prm})"], op=op, error=ev2.get("error"), passed=ev2["passed"],
                           failed=ev2["failed"], features=sorted(ev2["features"]), from_features=sorted(ev["features"]))
                trace.append(rec)
                if ev2["ok"]:
                    return (ev2["score"], next(tick), edits + [(op, prm, sorted(ev["features"]))], s2, ev2)
                if ev2["score"] > score:
                    partials.append(dict(op=op, prm=prm, pre=sorted(ev["features"]), gain=ev2["score"] - score))
                    frontier.append((ev2["score"], next(tick), edits + [(op, prm, sorted(ev["features"]))], s2, ev2))
                elif ev2["score"] == score and ((ev2["features"] != ev["features"] and ev2.get("error") is None) or
                                                (ev2.get("error") and ev.get("error") and ev2.get("err_loc") != ev.get("err_loc"))):
                    # plateau move: no more checks pass, but the observed evidence changed (kept at lower priority)
                    frontier.append((ev2["score"] - 0.01, next(tick), edits + [(op, prm, sorted(ev["features"]))], s2, ev2))
                elif ev2["features"] == ev["features"]:
                    refutations.append(dict(op=op, pre=sorted(ev["features"])))
            if ops_seq:
                break
        return None

    # 1. retrieved skills first (reuse), each as a guided operator sequence from the legacy state
    for ov, sid, ops in skill_seqs:
        state = frontier[0]
        for op in ops:
            r = expand(state, [op])
            if r == "timeout":
                break
            if r is not None:
                best = r
                break
            nxt = [f for f in frontier if len(f[2]) == len(state[2]) + 1 and f[2][:len(state[2])] == state[2]]
            if not nxt:
                break
            state = max(nxt, key=lambda f: f[0])
        if best:
            trace.append(dict(step="reuse", skill=sid))
            break
    # 2. best-first repair search ordered by pi_de
    while best is None and time.time() - t0 <= budget_s:
        cand = [f for f in frontier if len(f[2]) < max_depth and not f[4].get("_expanded")]
        if not cand:
            break
        state = max(cand, key=lambda f: (f[0], -len(f[2]), -f[1]))
        state[4]["_expanded"] = True
        r = expand(state)
        if r == "timeout":
            break
        if r is not None:
            best = r
    out = dict(solved_visible=best is not None, spec=best[3] if best else None,
               edits=[(o, p) for o, p, _ in best[2]] if best else None, edit_pre=[pre for _, _, pre in best[2]] if best else None,
               runs=inv.runs, wall=round(time.time() - t0, 3), trace=trace, start=ev0, refutations=refutations, partials=partials,
               start_features=sorted(ev0["features"]), n_checks=len(inv.contract["public_checks"]))
    return out


def learn(de, rec, project, cfg, solved_verified):
    """Online pi_de update + P records (the 'learn from failure' step). cfg: lr, neg_lr, use_failures (False = Solved-Only)."""
    if solved_verified:
        for (op, prm), pre in zip(rec["edits"], rec["edit_pre"]):
            for f in pre:
                de["w"].setdefault(f, {})[op] = de["w"].get(f, {}).get(op, 0.0) + cfg["lr"]
    if cfg["use_failures"]:
        for r in rec.get("refutations", [])[:40]:
            for f in r["pre"]:
                de["w"].setdefault(f, {})[r["op"]] = de["w"].get(f, {}).get(r["op"], 0.0) - cfg["neg_lr"]
        if not solved_verified:
            for p in rec.get("partials", [])[:10]:
                de["P"].append(dict(project=project["pid"], kind="partial", op=p["op"], prm=p["prm"], pre=p["pre"],
                                    gain=p["gain"], evidence="public checks on the visible batch (real runtime)"))
        de["P"] = de["P"][-cfg.get("max_P", 60):]


def skill_from(rec, project):
    """A candidate skill (provisional until admitted): the verified operator-type sequence + its evidence precondition."""
    return dict(ops=[o for o, _ in rec["edits"]], pre=rec["start_features"], params_example=[p for _, p in rec["edits"]],
                contract=dict(public_checks_satisfied=rec["n_checks"], runtime=project["runtime"]), provenance=project["pid"],
                origin="pure_synthesis", match=0.5, validated_on=[])


def provisional_skills(de):
    """Provisional sequences from P: operators that repeatedly raised the passed-check count under similar evidence."""
    groups = {}
    for p in de["P"]:
        if p["kind"] == "partial":
            groups.setdefault((p["op"], tuple(p["pre"])), []).append(p)
    out = []
    for (op, pre), ps in groups.items():
        if len({p["project"] for p in ps}) >= 2:
            out.append(dict(ops=[op], pre=list(pre), params_example=[ps[0]["prm"]], contract=dict(satisfied="partial"),
                            provenance=[p["project"] for p in ps], origin="pure_synthesis", match=0.5, validated_on=[],
                            tier="provisional"))
    return out


def random_skill(rng):
    return dict(ops=[rng.choice(OPS) for _ in range(rng.randint(1, 3))],
                pre=sorted(rng.sample(["fail:example_rows", "fail:row_count", "fail:unique", "fail:quarantine_ids", "fail:no_error",
                                       "diff:value", "diff:extra_rows", "diff:dup_keys", "err:CAST_INVALID_INPUT"], 2)),
                params_example=[], contract={}, provenance="random", origin="random", match=0.5, validated_on=[], tier="random")
