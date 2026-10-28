"""Generic field-mapping repair for lifecycle schema changes (NOT LOCKED; sc track).

Input: the deployed payload (machine, contract, mapping versions), the runtime INCIDENTS (raw records whose required field was
absent / non-numeric), the incident archive with its oracle labels (already charged by the operator), and the oracle's
membership-query API (charged). Nothing else: no field name, project, domain, fault label or reference code is used.
  1. candidates   every numeric top-level field and one-level nested path present on ALL incident records (presence + type)
  2. consistency  the deployed machine read through the candidate mapping reproduces the labelled archive exactly
  3. separation   if several candidates are consistent: distinguishing membership queries (structural lifecycle words built
                  from the incident records' own shape, each candidate path carrying a different generic value); candidates
                  the oracle contradicts are dropped; still several after the probe budget -> AMBIGUOUS (abstain)
  4. relearn      if no candidate is consistent: the lifecycle is relearned on the archive read through each plausible
                  candidate (the same learner as every other relearn), at most `max_relearn` candidates
  5. acceptance   the program read through the mapping must pass the bounded acceptance check (ba_accept, unchanged) on
                  NEW-schema events, mixed old->new histories (prefix in the old schema, rest in the new) and - if the
                  machine changed - the old schema; the operator then replays the tick and reconciles it independently
Returns (new payload | None, log)."""
from __future__ import annotations

import contextlib
import random

from nexus import ba_accept as BA
from nexus import sc_contract as SC
from nexus import u5_statesplit as SP


def numeric_paths(e):
    out = []
    for k, v in e.items():
        if SC._isnum(v):
            out.append(k)
        elif isinstance(v, dict):
            out += [f"{k}.{k2}" for k2, v2 in v.items() if SC._isnum(v2)]
    return out


def candidates(incidents):
    sets = [set(numeric_paths(i["raw"])) for i in incidents]
    common = set.intersection(*sets) if sets else set()
    return sorted(common)


def _payload_with(payload, f, path, machine=None, source=None, name=None):
    p = dict(payload)
    if machine is not None:
        p.update(machine=machine, source=source, name=name)
    p["mappings"] = list(payload.get("mappings", [])) + [dict(field=f, path=path, version=len(payload.get("mappings", [])) + 1,
                                                              when=f"'{f}' absent and '{path}' numeric")]
    return p


def run(payload, events):
    r = SC.ContractRunner(payload)
    return [r.ingest(e) for e in events]


def consistent(payload, arch, rows):
    got = run(payload, arch)
    return all(SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))) for g, w in zip(got, rows))


class _Probe:
    """Learner-like object for ba_accept.bounded_cex on NEW-schema (and mixed) events: events are built from the incident
    records' own shape; the machine is evaluated THROUGH the contract runner + mapping (the deployed composite)."""

    def __init__(self, payload, templates_new, templates_old, oracle, key, path, seed):
        self.payload, self.tn, self.to, self.oracle, self.key, self.path = payload, templates_new, templates_old, oracle, key, path
        m = payload["machine"]
        top = path if "." not in path else None
        self.machine = dict(m, regs=[dict(rg, field=top or rg["field"]) for rg in m["regs"]])   # boundary draws hit the path
        self.alpha = list(m["alpha"])
        self.rnd = random.Random(seed)
        self.n_mq, self.n = 0, 0
        self.mixed_at = None

    def _fresh(self, e):
        e = dict(e)
        for p in numeric_paths(e):
            if "." in p:
                a, b = p.split(".")
                e[a] = dict(e[a], **{b: round(self.rnd.uniform(1, 400), 2)})
            else:
                e[p] = round(self.rnd.uniform(1, 400), 2) if not isinstance(e[p], int) else self.rnd.randint(0, 9)
        return e

    def make_events(self, word, fresh_values=True):
        self.n += 1
        k = f"probe_sc_{self.n:06d}"
        out = []
        for j, a in enumerate(word):
            old = self.mixed_at is not None and j < self.mixed_at
            pool = (self.to if old else self.tn).get(a) or self.tn.get(a) or self.to.get(a)
            e = self._fresh(dict(self.rnd.choice(pool), **{self.key: k}))
            out.append(e)
        return out

    def _query(self, evs):
        return self.oracle(evs)


@contextlib.contextmanager
def _composite_check(probe):
    """ba_accept.bounded_cex compares SP.run_machine(L.machine, evs) with the oracle; here the deployed composite (contract
    runner + mapping) is compared instead - the acceptance procedure itself is the unchanged ba_accept code."""
    orig = BA._mismatch

    def _mm(L, evs):
        rows = L._query(evs)
        L.n_mq += 1
        got = run(probe.payload, evs)
        return rows, not all(SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))) for g, w in zip(got, rows))

    BA._mismatch = _mm
    try:
        yield
    finally:
        BA._mismatch = orig


def joint_acceptance(payload, templates_new, templates_old, oracle, key, path, seed=0, n_mixed=120):
    pr = _Probe(payload, templates_new, templates_old, oracle, key, path, seed)
    with _composite_check(pr):
        cex, scope = BA.bounded_cex(pr, seed=seed)
        if cex:
            return False, dict(stage="new_schema", scope=scope, queries=pr.n_mq)
        tests, _ = BA.structural_tests(pr.machine, pr.alpha)
        mixed = 0
        for d, p, a, mid, f in tests[:n_mixed]:
            pr.mixed_at = len(p)                                 # prefix in the old schema, the rest in the new
            w = p + (a,) + mid + f
            evs = pr.make_events(w)
            rows, bad = BA._mismatch(pr, evs)
            mixed += 1
            if bad:
                pr.mixed_at = None
                return False, dict(stage="mixed_old_new", scope=scope, mixed_tests=mixed, queries=pr.n_mq)
        pr.mixed_at = None
    scope = dict(scope, mixed_old_new_tests=mixed, mapping_path=path,
                 boundary_draws_on_path="yes" if "." not in path else "no (nested path: generic draws only)")
    return True, dict(stage="accepted", scope=scope, queries=pr.n_mq)


def separate(payload, cands, f, templates_new, templates_old, oracle, key, seed=0, budget=24):
    """Distinguishing membership queries among consistent candidate mappings."""
    live = list(cands)
    pr = _Probe(_payload_with(payload, f, live[0]), templates_new, templates_old, oracle, key, live[0], seed)
    tests, _ = BA.structural_tests(pr.machine, pr.alpha)
    tests = [t for t in tests if t[0] == 0] or tests
    used = 0
    for d, p, a, mid, fl in tests:
        if len(live) <= 1 or used >= budget:
            break
        evs = pr.make_events(p + (a,) + mid + fl)                # every numeric path gets its own generic value
        rows = oracle(evs)
        used += 1
        live = [c for c in live if all(SP._rows_eq(list(map(tuple, g)), list(map(tuple, w)))
                                       for g, w in zip(run(_payload_with(payload, f, c), evs), rows))]
    return live, used


def repair(payload, incidents, arch, rows, oracle, relearn=None, seed=0, max_relearn=2):
    m = payload["machine"]
    key, ctrl = m["key"], m["ctrl"]
    log = dict(incidents=len(incidents), expected=sorted({f for i in incidents for f in i["expected_fields"]}))
    if len(log["expected"]) != 1:
        return None, dict(log, outcome="UNRESOLVED_MULTIPLE_FIELDS")
    f = log["expected"][0]
    cands = candidates(incidents)
    log["candidates"] = cands
    if not cands:
        return None, dict(log, outcome="UNRESOLVED_NO_CANDIDATE")
    tn, to = {}, {}
    inc_ids = {id(i["raw"]) for i in incidents}
    for e in arch:
        (to if f in e else tn).setdefault(e.get(ctrl), []).append(e)
    for i in incidents:
        tn.setdefault(i["kind"], []).append(i["raw"])
    _ = inc_ids
    cons = [c for c in cands if consistent(_payload_with(payload, f, c), arch, rows)]
    log["consistent"] = cons
    new_machine = None
    if len(cons) > 1:
        cons, used = separate(payload, cons, f, tn, to, oracle, key, seed)
        log.update(after_probes=cons, probe_queries=used)
        if len(cons) != 1:
            return None, dict(log, outcome="AMBIGUOUS_MAPPING" if cons else "UNRESOLVED_PROBES_REJECT_ALL")
    if not cons:
        if relearn is None:
            return None, dict(log, outcome="UNRESOLVED_NO_CONSISTENT_MAPPING")
        for c in cands[:max_relearn]:
            mapped = [dict(e, **{f: SC.get_path(e, c)}) if f not in e and SC._isnum(SC.get_path(e, c)) else e for e in arch]
            r = relearn(mapped, rows)
            if r is not None:
                new_machine, cons = r, [c]
                log["relearned_with"] = c
                break
        if not cons:
            return None, dict(log, outcome="UNRESOLVED_RELEARN_FAILED")
    path = cons[0]
    newp = _payload_with(payload, f, path, *(new_machine if new_machine else (None, None, None)))
    ok, acc = joint_acceptance(newp, tn, to, oracle, key, path, seed)
    log["acceptance"] = acc
    if not ok:
        return None, dict(log, outcome="MAPPING_REJECTED_BY_ACCEPTANCE")
    return newp, dict(log, outcome="MAPPING_ACCEPTED", mapping=newp["mappings"][-1])
