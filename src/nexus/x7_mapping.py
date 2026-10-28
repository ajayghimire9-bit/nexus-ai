"""Expression-adapter repair for lifecycle schema changes (NOT LOCKED; x7 Parts 4-5). Extends sc_mapping (unchanged).

Inputs: the deployed payload, runtime INCIDENTS (a needed field absent / non-numeric) or shape NOTICES (new numeric paths on
a kind), the incident archive with its oracle labels (charged by the operator) and the oracle's membership-query API (each call
charged). Never used: field names known to the developer, project / domain / fault labels, generator metadata, reference code.

  0. evidence     missing shape  -> target = the expected field, evidence records = the incident records
                  trigger shape  -> targets = the fields the machine needs on the notice kinds, triggers = new paths present
                                    on every notice record, evidence records = the notice records
                  no incident / notice but an output alarm -> evidence records = archive records whose numeric-path signature
                                    was never seen on their kind at build (trigger shape); none -> relearn (caller)
  1. benign       (trigger shape) the deployed composite is consistent with the labelled archive AND passes the composite
                  acceptance suite on new-shape events -> SHAPE_VERIFIED_BENIGN (paths recorded; no adapter); a counterexample
                  found here becomes evidence
  2. tiers        tier 0 = field / path selection (FieldOnly arms stop here), tier 1 = one operator or a parse, tier 2 = two
                  operators (x7_expr); bodies are wrapped as  if present(f) then f else BODY  (missing shape) or
                  if present(t) then BODY else f  (trigger shape)
  3. consistency  composite (machine + adapter) reproduces every labelled archive row and every acceptance counterexample
  4. separation   > 1 consistent: distinguishing membership queries built from the evidence records' own shape with fresh
                  values; a query is spent only on a word where the live candidates predict different rows; still > 1 after
                  the budget -> AMBIGUOUS (unresolved, never a unique claim)
  5. acceptance   the unique survivor must pass composite_accept (exhaustive words to the declared horizon, structural
                  delayed-effect tests with boundary draws on the adapter's inputs, mixed old -> new histories; if the
                  machine was relearned, the old shape too); a failure adds the counterexample and the search expands
  6. relearn      no tier yields: the lifecycle is relearned on the archive read through the cheapest candidates (<= 2)
Returns (new payload | None, log)."""
from __future__ import annotations

import itertools
import random
import time

from nexus import ba_accept as BA
from nexus import u5_statesplit as SP
from nexus import x7_contract as XC
from nexus import x7_expr as X

CAPS = dict(consistency_checks=30000, repair_cpu_s=300.0, probe_queries=24, probe_attempts=300, max_relearn=2,
            cap_exhaustive=400, cap_structural=700, n_mixed=120)


def _rows_ok(got, want):
    return all(SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))) for g, w in zip(got, want))


def _with(payload, f, expr, tier, kinds, machine=None, extra=None):
    p = dict(payload)
    if machine is not None:
        p.update(machine=machine[0], source=machine[1], name=machine[2])
    v = len(payload.get("mappings", [])) + 1
    when = (f"'{f}' absent and every input of the expression is present" if expr[0] == "if" and expr[1] == f
            else f"'{expr[1]}' present" if expr[0] == "if" else "always")
    p["mappings"] = list(payload.get("mappings", [])) + [dict(field=f, expr=expr, path=X.src(expr), version=v, when=when, tier=tier,
                                                              kinds=sorted(kinds), paths=sorted(X.paths(expr)), **(extra or {}))]
    return p


class _Evidence:
    """Labelled archive (+ counterexamples). Consistency of a candidate payload, replayed from a snapshot taken just before the
    first record any adapter could affect (earlier records read the raw field under every adapter shape used here)."""

    def __init__(self, payload, arch, rows, first):
        self.arch, self.rows, self.first = arch, rows, first
        r = XC.ContractRunnerX(payload)
        for e in arch[:first]:
            r.ingest(e)
        self.snap = r.get_state()
        self.extra = []
        self.checks = 0

    def ok(self, p, same_machine=True):
        self.checks += 1
        r = XC.ContractRunnerX(p)
        if same_machine:
            r.set_state(self.snap)
            got = [r.ingest(e) for e in self.arch[self.first:]]
            if not _rows_ok(got, self.rows[self.first:]):
                return False
        else:
            got = [r.ingest(e) for e in self.arch]
            if not _rows_ok(got, self.rows):
                return False
        for evs, rows in self.extra:
            r = XC.ContractRunnerX(p)
            if not _rows_ok([r.ingest(e) for e in evs], rows):
                return False
        return True


class _Gen:
    """Builds probe / acceptance events from the evidence records' own shape (new) and the archive's old-shape records."""

    def __init__(self, machine, new_by_kind, old_by_kind, seed):
        self.m, self.tn, self.to = machine, new_by_kind, old_by_kind
        self.rnd = random.Random(seed)
        self.n = 0

    def fresh(self, e):
        e = dict(e)
        for p in X.numeric_paths(e):
            v = X.get_path(e, p)
            X.set_path(e, p, self.rnd.randint(0, 9) if isinstance(v, int) else round(self.rnd.uniform(1, 400), 2))
        return e

    def events(self, word, old_until=0, boundary=None, pos=None, fields=()):
        self.n += 1
        k = f"probe_x7_{self.n:06d}"
        out = []
        for j, a in enumerate(word):
            pool = (self.to if j < old_until else self.tn).get(a) or self.tn.get(a) or self.to.get(a)
            e = self.fresh(dict(self.rnd.choice(pool), **{self.m["key"]: k}))
            out.append(e)
        if boundary:
            v0 = {f: X.get_path(out[0], f) for f in fields}
            for j, e in enumerate(out):
                for f in fields:
                    if not X.isnum(X.get_path(e, f)):
                        continue
                    if boundary == "all_equal":
                        X.set_path(e, f, 0 if j == pos else v0[f])
                    elif j == pos:
                        cur = X.get_path(e, f)
                        X.set_path(e, f, {"zero": 0, "unit": 1, "sign": -abs(cur) or -1.0}[boundary])
        return out


def composite_accept(p, gen, oracle, fields, relearned=False, caps=CAPS, seed=0):
    """Bounded acceptance of the deployed composite (machine + adapters). Returns (cex | None, scope)."""
    m = p["machine"]
    alpha = list(m["alpha"])
    h = 1
    while len(alpha) ** (h + 1) <= caps["cap_exhaustive"]:
        h += 1
    used = dict(exhaustive_new=0, exhaustive_old=0, depth0=0, depth1=0, boundary=0, mixed=0)
    scope = dict(label="TESTED_WITHIN_STATED_LIMITS", alphabet=alpha, alphabet_size=len(alpha), hyp_modes=m["n"],
                 hyp_regs=len(m["regs"]), adapter_inputs=list(fields),
                 exhaustive=dict(horizon=h, words_per_shape=len(alpha) ** h, value_draws="1 generic per word"),
                 assumptions=["per-key machines over kinds observed at build", "register updates in the learner's class",
                              "adapter inputs drawn from the evidence records' shape (ints 0-9, floats 1-400) + boundary draws"])

    def run(evs):
        rows = oracle(evs)
        r = XC.ContractRunnerX(p)
        return rows, not _rows_ok([r.ingest(e) for e in evs], rows)

    def done(cex):
        scope.update(runs=dict(used), queries=sum(used.values()), stopped="counterexample" if cex else "passed")
        return cex, scope
    words = list(itertools.product(alpha, repeat=h))
    random.Random(seed).shuffle(words)
    for shape in (["new", "old"] if relearned else ["new"]):
        for w in words:
            evs = gen.events(w, old_until=len(w) if shape == "old" else 0)
            rows, bad = run(evs)
            used[f"exhaustive_{shape}"] += 1
            if bad:
                return done((evs, rows))
    tests, info = BA.structural_tests(m, alpha)
    scope["structural"] = dict(tests=len(tests), cap=caps["cap_structural"], **info)
    n = 0
    for idx, (d, pre, a, mid, fl) in enumerate(tests):
        for bd in ([None, BA.BOUNDARY[idx % 4]] if d == 0 else [None]):
            if n >= caps["cap_structural"]:
                scope["structural"]["cap_reached"] = True
                break
            w = pre + (a,) + mid + fl
            evs = gen.events(w, boundary=bd, pos=len(pre), fields=fields)
            rows, bad = run(evs)
            n += 1
            used["boundary" if bd else "depth0" if d == 0 else "depth1"] += 1
            if bad:
                return done((evs, rows))
    scope["structural"].setdefault("cap_reached", False)
    for d, pre, a, mid, fl in tests[:caps["n_mixed"]]:
        w = pre + (a,) + mid + fl
        evs = gen.events(w, old_until=len(pre))
        rows, bad = run(evs)
        used["mixed"] += 1
        if bad:
            return done((evs, rows))
    scope["mixed_old_new_tests"] = used["mixed"]
    return done(None)


def _separate(cands, gen, oracle, caps, seed):
    """Distinguishing queries: spend a query only on a word where the live candidates disagree."""
    live = list(cands)
    m = live[0][1]["machine"]
    tests, _ = BA.structural_tests(m, list(m["alpha"]))
    words = [p + (a,) + mid + f for _, p, a, mid, f in tests] or [tuple(m["alpha"])]
    rnd = random.Random(seed)
    used = attempts = 0
    while len(live) > 1 and used < caps["probe_queries"] and attempts < caps["probe_attempts"]:
        attempts += 1
        w = words[attempts % len(words)] if attempts <= len(words) else tuple(rnd.choice(m["alpha"]) for _ in range(rnd.randint(2, 6)))
        evs = gen.events(w)
        preds = []
        for c in live:
            r = XC.ContractRunnerX(c[1])
            preds.append(repr([list(map(tuple, x)) for x in (r.ingest(e) for e in evs)]))
        if len(set(preds)) == 1:
            continue
        rows = oracle(evs)
        used += 1
        keep = []
        for c in live:
            r = XC.ContractRunnerX(c[1])
            if _rows_ok([r.ingest(e) for e in evs], rows):
                keep.append(c)
        live = keep
    return live, dict(queries=used, attempts=attempts)


def _classify(payload, arch):
    """Archive records whose numeric-path signature on their kind was never seen at build (new shape) vs old shape."""
    c = payload["contract"]
    ctrl = payload["machine"]["ctrl"]
    seen = {a: set(ps) for a, ps in c.get("seen_paths", {}).items()}
    for a, ps in payload.get("benign_paths", {}).items():
        seen.setdefault(a, set()).update(ps)
    new, old = {}, {}
    for i, e in enumerate(arch):
        a = e.get(ctrl)
        if a not in seen:                                      # a kind never seen at build is not shape evidence (relearn)
            continue
        need = c["required"].get(a, [])
        is_new = any(p not in seen.get(a, set()) for p in X.numeric_paths(e)) or any(not X.isnum(e.get(f)) for f in need)
        (new if is_new else old).setdefault(a, []).append((i, e))
    return new, old


def _known_shapes(p, tn):
    """The accepted composite was tested on new-shape events of every kind in tn: their numeric paths stop being notices."""
    bp = {a: set(v) for a, v in p.get("benign_paths", {}).items()}
    for a, es in tn.items():
        for e in es:
            bp.setdefault(a, set()).update(X.numeric_paths(e))
    p["benign_paths"] = {a: sorted(v) for a, v in bp.items()}


def repair(payload, incidents, notices, arch, rows, oracle, relearn=None, mode="expression", seed=0, caps=CAPS):
    t0 = time.process_time()
    m = payload["machine"]
    key, ctrl = m["key"], m["ctrl"]
    c = payload["contract"]
    max_tier = 2 if mode == "expression" else 0
    log = dict(mode=mode, incidents=len(incidents), notices=len(notices))
    new_by, old_by = _classify(payload, arch)
    if incidents:
        shape = "missing"
        exp = sorted({f for i in incidents for f in i["expected_fields"]})
        log["expected"] = exp
        if any(f in c.get("structural", []) for f in exp):
            return None, dict(log, outcome="UNRESOLVED_STRUCTURAL_FIELD")
        if len(exp) != 1:
            return None, dict(log, outcome="UNRESOLVED_MULTIPLE_FIELDS")
        targets = exp
        R = [i["raw"] for i in incidents]
        triggers = [None]
    else:
        shape = "trigger"
        R = [n["raw"] for n in notices] or [e for a in new_by for _, e in new_by[a]]
        if not R:
            return None, dict(log, outcome="NO_SHAPE_EVIDENCE")
        kinds = sorted({e.get(ctrl) for e in R})
        targets = sorted({f for a in kinds for f in c["required"].get(a, []) + c["nullable"].get(a, [])})
        seen = c.get("seen_paths", {})
        newp = [set(p for p in X.numeric_paths(e) if p not in set(seen.get(e.get(ctrl), [])) | set(payload.get("benign_paths", {}).get(e.get(ctrl), []))) for e in R]
        triggers = sorted(set.intersection(*newp)) if newp else []
        log.update(notice_kinds=kinds, targets=targets, triggers=triggers)
    log["shape"] = shape
    tn = {a: [e for _, e in v] for a, v in new_by.items()}
    for e in R:
        tn.setdefault(e.get(ctrl), []).append(e)
    to = {a: [e for _, e in v] for a, v in old_by.items()}
    gen = _Gen(m, tn, to, seed)
    first = min([i for v in new_by.values() for i, _ in v] or [len(arch)])
    E = _Evidence(payload, arch, rows, first)
    affected_kinds = sorted({e.get(ctrl) for e in R})
    if shape == "trigger":
        if E.ok(payload):
            cex, scope = composite_accept(payload, gen, oracle, sorted(set(p for e in R for p in X.numeric_paths(e))), seed=seed, caps=caps)
            log["benign_check"] = scope
            if cex is None:
                p = dict(payload)
                bp = {a: list(v) for a, v in payload.get("benign_paths", {}).items()}
                for e in R:
                    bp.setdefault(e.get(ctrl), [])
                    bp[e.get(ctrl)] = sorted(set(bp[e.get(ctrl)]) | set(X.numeric_paths(e)))
                p["benign_paths"] = bp
                return p, dict(log, outcome="SHAPE_VERIFIED_BENIGN", cpu_s=round(time.process_time() - t0, 3))
            E.extra.append(cex)
        if not targets or not triggers:
            return None, dict(log, outcome="UNRESOLVED_NO_TARGET_OR_TRIGGER")
    num, strs = X.leaves(R, exclude=(key, ctrl))
    log["leaves"] = dict(numeric=num, parse=strs)
    bodies = X.enumerate_bodies(num, strs, R, max_tier=max_tier, seed=seed)
    log["bodies_per_tier"] = {t: sum(1 for x in bodies if x[0] == t) for t in range(max_tier + 1)}
    tried = []
    for tier in range(max_tier + 1):
        cands = []
        for f in targets:
            for t in triggers:
                for tt, b in bodies:
                    if tt != tier:
                        continue
                    if shape == "missing" and f in X.paths(b):
                        continue
                    expr = X.wrap_missing(f, b) if shape == "missing" else X.wrap_trigger(t, b, f)
                    cands.append((f, expr))
        cons = []
        for f, expr in cands:
            if E.checks >= caps["consistency_checks"] or time.process_time() - t0 > caps["repair_cpu_s"]:
                log.update(tiers=tried, outcome="UNRESOLVED_SEARCH_BUDGET", consistency_checks=E.checks)
                return None, log
            p = _with(payload, f, expr, tier, affected_kinds)
            if E.ok(p):
                cons.append((f, p, expr))
        rec = dict(tier=tier, candidates=len(cands), consistent=[X.src(x[2]) for x in cons][:12], n_consistent=len(cons))
        tried.append(rec)
        while cons:
            if len(cons) > 1:
                live, pr = _separate([(f, p) for f, p, _ in cons], gen, oracle, caps, seed + tier)
                rec.setdefault("probes", []).append(dict(pr, before=len(cons), after=len(live)))
                live_ids = {id(p) for _, p in live}
                cons = [x for x in cons if id(x[1]) in live_ids]
                if len(cons) > 1:
                    rec["ambiguous"] = [X.src(x[2]) for x in cons][:12]
                    log.update(tiers=tried, outcome="AMBIGUOUS_MAPPING", consistency_checks=E.checks,
                               cpu_s=round(time.process_time() - t0, 3))
                    return None, log
                if not cons:
                    break
            f, p, expr = cons[0]
            fields = sorted(X.paths(expr) - {f} if shape == "missing" else X.paths(expr))
            cex, scope = composite_accept(p, gen, oracle, fields, seed=seed + 31 * tier, caps=caps)
            rec.setdefault("acceptance", []).append(dict(expr=X.src(expr), scope=scope))
            if cex is None:
                _known_shapes(p, tn)
                mv = p["mappings"][-1]
                mv["provenance"] = dict(shape=shape, tier=tier, evidence_records=len(R), archive_events=len(arch),
                                        candidates_in_tier=len(cands), consistent_in_tier=rec["n_consistent"],
                                        probes=rec.get("probes", []), acceptance=scope)
                log.update(tiers=tried, outcome="ADAPTER_ACCEPTED", mapping=dict((k, v) for k, v in mv.items() if k != "expr"),
                           consistency_checks=E.checks, cpu_s=round(time.process_time() - t0, 3))
                return p, log
            E.extra.append(cex)
            cons = [x for x in cons[1:] if E.ok(x[1])]
    if relearn is not None:
        ordered = [b for _, b in bodies][:caps["max_relearn"]]
        for b in ordered:
            for f in targets:
                for t in triggers:
                    expr = X.wrap_missing(f, b) if shape == "missing" else X.wrap_trigger(t, b, f)
                    mapped = []
                    for e in arch:
                        v = X.ev(expr, e)
                        mapped.append(dict(e, **{f: v}) if v is not X.MISSING else e)
                    r = relearn(mapped, rows)
                    if r is None:
                        continue
                    p = _with(payload, f, expr, "relearn", affected_kinds, machine=r)
                    p["contract"] = XC.infer(r[0], arch, payload["contract"])
                    p["contract"]["seen_paths"] = payload["contract"].get("seen_paths", {})     # new shapes stay notices
                    if not E.ok(p, same_machine=False):
                        continue
                    g2 = _Gen(r[0], tn, to, seed + 7)
                    fields = sorted(X.paths(expr) - {f})
                    cex, scope = composite_accept(p, g2, oracle, fields, relearned=True, seed=seed + 99, caps=caps)
                    tried.append(dict(tier="relearn", expr=X.src(expr), acceptance=scope))
                    if cex is None:
                        _known_shapes(p, tn)
                        log.update(tiers=tried, outcome="ADAPTER_ACCEPTED_AFTER_RELEARN", relearned_with=X.src(expr),
                                   mapping=dict((k, v) for k, v in p["mappings"][-1].items() if k != "expr"),
                                   consistency_checks=E.checks, cpu_s=round(time.process_time() - t0, 3))
                        return p, log
    log.update(tiers=tried, outcome="UNRESOLVED_NO_ACCEPTED_ADAPTER", consistency_checks=E.checks,
               cpu_s=round(time.process_time() - t0, 3))
    return None, log
