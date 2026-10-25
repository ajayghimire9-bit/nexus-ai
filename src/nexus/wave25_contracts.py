"""Wave 25 S1-Auto: automatic acquisition of abstract operator contracts + cheap Tycho admission.

Replaces the three hand-wired S1 pruning rules (`wave25_factored.make_abstract`) with a learner:

1. Property basis (domain-free, over collection values): length, distinct_count, provenance (item
   multiset), max_atom (largest numeric atom), plus distractors parity (length mod 2) and first_sign
   (sign of the first numeric atom). Each basis property declares how it lifts through four IR structural
   classes (sub-multiset, permutation, item-wise map, to-scalar). This table is knowledge about the
   *properties*, not about any mechanism, domain or task.
2. Mechanism structural classes are *verified*, not trusted: every bound mechanism of a role (all bindings
   in the grammar over a declared universe) is executed on every universe value and must satisfy its
   class (e.g. Counter(out) <= Counter(in) for sub-multiset). Every unit is charged.
3. Candidate contracts (property, role, relation) are enumerated automatically. A contract is admitted only
   if it is DERIVED from a verified class + the property's lifting table (proof) and survives an empirical
   cross-check. Non-derivable candidates are searched for a counterexample (refuted) or rejected as
   unproven. A property is usable for pruning in a world only if every list->list role there carries a
   non-increasing contract for it (otherwise a suffix could increase it).
4. Cheap Tycho: a stratified micro-sample of validation tasks runs the twin (with / without contracts) to
   calibrate a counterfactual pruned-subtree estimator; per-contract savings come from prune attribution
   in pruned-only runs. Admit iff calibrated saving per task x horizon > (verification + micro-sample cost).
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import product

from nexus.wave24_domains import vkey
from nexus.wave24_v4_core import Searcher, meter
from nexus.wave25_factored import (MAPS, MAX_DEPTH, TASK_BUDGET, Mech, _num, binding_grammar, get)

# --------------------------------------------------------------------------- property basis
def _atoms(v):
    for it in v:
        if isinstance(it, dict):
            yield from (x for x in it.values() if _num(x))
        elif _num(it):
            yield it


def p_length(v):
    return len(v)


def p_distinct(v):
    return len({vkey(i) for i in v})


def p_max_atom(v):
    a = list(_atoms(v))
    return max(a) if a else None


def p_parity(v):
    return len(v) % 2


def p_first_sign(v):
    a = list(_atoms(v))
    return (a[0] > 0) - (a[0] < 0) if a else None


def p_provenance(v):
    return Counter(vkey(i) for i in v)


NUMERIC = {"length": p_length, "distinct_count": p_distinct, "max_atom": p_max_atom, "parity": p_parity,
           "first_sign": p_first_sign}
BASIS = tuple(NUMERIC) + ("provenance",)
# how each property lifts through an IR structural class (None = no relation derivable)
LIFT = {
    "length": {"submultiset": "le", "permutation": "eq", "itemwise": "eq"},
    "distinct_count": {"submultiset": "le", "permutation": "eq", "itemwise": "le"},
    "max_atom": {"submultiset": "le", "permutation": "eq"},
    "provenance": {"submultiset": "subset", "permutation": "equal", "itemwise": "image_subset"},
    "parity": {"permutation": "eq", "itemwise": "eq"},
    "first_sign": {"itemwise": None},
}
RELATIONS = {"numeric": ("le", "eq", "ge"), "provenance": ("subset", "equal", "image_subset")}
CLASSES = ("submultiset", "permutation", "itemwise", "to_scalar")
ROLE_CLASS_CANDIDATES = CLASSES      # the learner tests every class for every role


def _class_holds(cls, v, out, mech=None):
    if cls == "to_scalar":
        return not isinstance(out, list)
    if not isinstance(out, list):
        return False
    if cls == "submultiset":
        ci, co = p_provenance(v), p_provenance(out)
        return all(ci[k] >= c for k, c in co.items())
    if cls == "permutation":
        return p_provenance(v) == p_provenance(out)
    g = item_map(mech)
    return g is not None and len(out) == len(v) and all(vkey(g(a)) == vkey(b) for a, b in zip(v, out))


def item_map(mech):
    """The bound item function of a mechanism slot, if its IR declares one (Map[g])."""
    if mech is not None and mech.role == "Map":
        return MAPS[mech.slots[0]]
    return None


def _rel_holds(prop, rel, v, out, mech=None):
    if not isinstance(out, list):
        return False
    if prop == "provenance":
        a, b = p_provenance(v), p_provenance(out)
        if rel == "image_subset":
            g = item_map(mech)
            return g is not None and {vkey(i) for i in out} <= {vkey(g(i)) for i in v}
        return all(a[k] >= c for k, c in b.items()) if rel == "subset" else a == b
    x, y = NUMERIC[prop](v), NUMERIC[prop](out)
    if x is None or y is None:
        return (y is None) if rel == "le" else (x is None and y is None)
    return y <= x if rel == "le" else y == x if rel == "eq" else y >= x


def universes():
    ints = [list(t) for n in range(0, 5) for t in product((-2, 0, 1, 3), repeat=n)]
    recs_items = [{"b": b, "s": s, "t": t} for b in (True, False) for s in (0, 2) for t in ("a", "b")]
    recs = [[dict(r) for r in t] for n in range(0, 4) for t in product(recs_items, repeat=n)]
    return {"INT_LIST": (ints, True), "RECORDS": (recs, False)}


@dataclass
class Contract:
    prop: str
    role: str
    relation: str
    status: str = "candidate"       # proved | refuted | unproven
    checks: int = 0
    counterexample: object = None


@dataclass
class ContractLibrary:
    contracts: list = field(default_factory=list)
    role_classes: dict = field(default_factory=dict)
    role_rejects_scalar: dict = field(default_factory=dict)
    usable: dict = field(default_factory=dict)       # world -> {"numeric": [...], "provenance": bool}
    work: Counter = field(default_factory=Counter)
    admitted: dict = field(default_factory=dict)     # world -> [prop names]
    tycho: dict = field(default_factory=dict)

    def proved(self):
        return [c for c in self.contracts if c.status == "proved"]


def learn_contracts(*, sanity_samples=60, seed=0):
    """Verify role structural classes on the universes, enumerate and decide every candidate contract."""
    lib = ContractLibrary()
    rng = random.Random(seed)
    UNI = universes()
    by_role = defaultdict(list)             # role -> [(mech, world)]
    for world, (U, maps) in UNI.items():
        items = [it for v in U for it in v]
        for t in binding_grammar([items], maps=maps):
            by_role[t.fn.role].append((t.fn, world))
    # 1. structural classes (exhaustive over the universe of each world)
    for role, mechs in sorted(by_role.items()):
        ok = {c: True for c in CLASSES}
        rejects = True
        for mech, world in mechs:
            U, _ = UNI[world]
            for scalar in (0, 1, -2, 2.5, "a", True):
                lib.work["class_verification_work"] += 1
                try:
                    mech(scalar)
                    rejects = False
                except Exception:
                    pass
            for v in U:
                lib.work["class_verification_work"] += 1
                try:
                    out = mech(v)
                except Exception:
                    continue
                for c in CLASSES:
                    if ok[c] and not _class_holds(c, v, out, mech):
                        ok[c] = False
        held = [c for c in CLASSES if ok[c]]
        lib.role_rejects_scalar[role] = rejects
        # most specific verified class (permutation implies submultiset)
        lib.role_classes[role] = "permutation" if "permutation" in held else \
            "submultiset" if "submultiset" in held else "itemwise" if "itemwise" in held else \
            "to_scalar" if "to_scalar" in held else "none"
    # 2. candidate contracts
    for prop in BASIS:
        rels = RELATIONS["provenance" if prop == "provenance" else "numeric"]
        for role in sorted(by_role):
            for rel in rels:
                c = Contract(prop, role, rel)
                cls = lib.role_classes[role]
                derived = LIFT.get(prop, {}).get(cls)
                implied = derived == rel or (derived == "eq" and rel in ("le", "ge")) or \
                    (derived == "equal" and rel == "subset")
                if implied:
                    # empirical sanity cross-check of a proved contract (charged)
                    sample = [(m, v) for m, w in by_role[role] for v in rng.sample(UNI[w][0], 5)]
                    for m, v in rng.sample(sample, min(sanity_samples, len(sample))):
                        lib.work["contract_check_work"] += 1
                        c.checks += 1
                        try:
                            out = m(v)
                        except Exception:
                            continue
                        if not _rel_holds(prop, rel, v, out, m):
                            c.status, c.counterexample = "refuted", (m.name(), v)
                            break
                    else:
                        c.status = "proved"
                else:
                    c.status = "unproven"
                    for m, w in by_role[role]:
                        for v in UNI[w][0]:
                            lib.work["contract_check_work"] += 1
                            c.checks += 1
                            try:
                                out = m(v)
                            except Exception:
                                continue
                            if not _rel_holds(prop, rel, v, out, m):
                                c.status, c.counterexample = "refuted", (m.name(), repr(v)[:80])
                                break
                        if c.status == "refuted":
                            break
                lib.contracts.append(c)
    return lib


def usable_props(lib, roles_present):
    """Properties that every list->list role present carries a non-increasing proved contract for."""
    list_roles = [r for r in roles_present if lib.role_classes.get(r) != "to_scalar"]
    proved = {(c.prop, c.role, c.relation) for c in lib.proved()}
    numeric = [p for p in NUMERIC if all((p, r, "le") in proved or (p, r, "eq") in proved for r in list_roles)]
    prov_plain = all(("provenance", r, "subset") in proved or ("provenance", r, "equal") in proved for r in list_roles)
    prov_image = not prov_plain and all(("provenance", r, "subset") in proved or ("provenance", r, "equal") in proved
                                        or ("provenance", r, "image_subset") in proved for r in list_roles)
    prov = prov_plain or prov_image
    scalar_terminal = all(lib.role_rejects_scalar.get(r) for r in roles_present)
    return dict(numeric=numeric, provenance=prov, provenance_image=prov_image, scalar_terminal=scalar_terminal)


def make_contract_pruner(props, *, attribution=None, maps=None):
    """Sound pruner from usable proved contracts, checks in the given property order. `attribution`
    (Counter) records which property pruned and how many checks each property cost. With
    `provenance_image`, target items must lie in the closure of the state's items under <= r applications of
    the bound item maps of the grammar (`maps`)."""
    numeric = list(props["numeric"])
    prov = props["provenance"]
    image = props.get("provenance_image", False)
    terminal = props.get("scalar_terminal", False)
    maps = list(maps or ())

    last = [None]

    def note(key, n=1):
        if attribution is not None:
            attribution[key] += n
        if not isinstance(key, tuple):
            last[0] = key

    def prune(pub, targets, r, m):
        last[0] = None
        hit = _prune(pub, targets, r, m)
        if hit:
            note(("remaining", r))
            if last[0] is not None:
                note(("by", last[0], r))
        return hit

    def _prune(pub, targets, r, m):
        for v, y in zip(pub, targets):
            if isinstance(y, list):
                if not isinstance(v, list):
                    if not terminal:
                        continue
                    m.charge("abstract_work_units", 1)
                    note(("checks", "kind"))
                    note("kind")
                    return True
                for p in numeric:
                    m.charge("abstract_work_units", 1)
                    note(("checks", p))
                    a, b = NUMERIC[p](v), NUMERIC[p](y)
                    if (a is not None and b is not None and a < b) or (a is None and b is not None):
                        note(p)
                        return True
                if prov and r > 0:
                    m.charge("abstract_work_units", 1)
                    note(("checks", "provenance"))
                    if image:
                        if all(isinstance(i, int) and not isinstance(i, bool) for i in list(v) + list(y)):
                            clo = set(v)
                            frontier = set(v)
                            for _ in range(r):
                                frontier = {g(i) for i in frontier for g in maps} - clo
                                clo |= frontier
                            if any(i not in clo for i in y):
                                note("provenance")
                                return True
                    else:
                        have, need = p_provenance(v), p_provenance(y)
                        if any(have[k] < c for k, c in need.items()):
                            note("provenance")
                            return True
            elif terminal:
                m.charge("abstract_work_units", 1)
                note(("checks", "kind"))
                if not isinstance(v, list) and vkey(v) != vkey(y):
                    note("kind")
                    return True
                if isinstance(v, list) and r == 0:
                    return True
        return False
    return prune


# --------------------------------------------------------------------------- certification with contracts
def certify_with(task, world, props, *, public=None, tools=None, attribution=None, extra=()):
    from nexus.wave25_factored import task_grammar
    public = tuple(public if public is not None else task.public)
    tools = tools if tools is not None else task_grammar(task, world)
    maps = [item_map(t.fn) for t in tools if item_map(t.fn) is not None]
    pr = make_contract_pruner(props, attribution=attribution, maps=maps) if props is not None else None
    s = Searcher(public, task.query, tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0, extra=extra,
                 max_depth=MAX_DEPTH, abstract=pr)
    res = s.run_to(MAX_DEPTH)
    res.searcher = s
    return res


def counterfactual_saving(res, n_ops, attribution):
    """Work the pruned subtrees would have cost, from the pruned run alone. A state pruned at depth
    d = MAX_DEPTH - r would have been expanded at level d + 1 only if the search reached that level
    (level reached = certificate size, or MAX_DEPTH when nothing was found); its surviving children would
    have been expanded at d + 2 under the same condition, at the run's observed survival ratio
    rho = |frontier_2| / |frontier_1|. One expansion = n_ops evaluations x n public values."""
    s = res.searcher
    unit = n_ops * s.n
    sizes = s.level_sizes + [0, 0]
    rho = sizes[1] / max(1, sizes[0])
    reached = res.size or MAX_DEPTH
    total = 0.0
    for r in range(1, MAX_DEPTH + 1):
        c = attribution.get(("remaining", r), 0)
        d = MAX_DEPTH - r
        if c and d + 1 <= reached:
            total += c * unit * (1 + (rho if d + 2 <= reached else 0.0))
    return total


def tycho_admit_contracts(lib, val_tasks, world_of, *, micro=12, horizon=100, seed=0):
    """Cheap admission. Only a stratified micro-sample of validation tasks is run, as a twin (with / without
    the usable proved contracts); every unit of both halves plus the one-time contract-learning cost is
    validation overhead. Admit the contract properties that actually pruned iff
    mean micro saving x horizon > overhead. The counterfactual estimator (pruned run only) is calibrated on
    the same sample and its leave-one-out error reported, for later twin-free monitoring."""
    from nexus.wave25_factored import task_grammar
    rng = random.Random(f"w25-micro:{seed}")
    strata = defaultdict(list)
    for t in val_tasks:
        strata[(t.world, len(t.teacher))].append(t)
    order = sorted(strata)
    sample, i = [], 0
    while len(sample) < min(micro, len(val_tasks)) and i < 10 * micro:
        bucket = strata[order[i % len(order)]]
        if bucket:
            sample.append(bucket.pop(rng.randrange(len(bucket))))
        i += 1
    twin, rows, attr_total = 0, [], Counter()
    for t in sample:
        world = world_of[t.world]
        tools = task_grammar(t, world)
        props = usable_props(lib, {tl.fn.role for tl in tools})
        a = certify_with(t, world, None, tools=tools)
        attr = Counter()
        b = certify_with(t, world, props, attribution=attr, tools=tools)
        same = a.status == b.status and {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}
        twin += a.work + b.work
        rows.append((a.work - b.work, counterfactual_saving(b, len(tools), attr), same))
        attr_total.update(attr)
    savings = [r[0] for r in rows]
    mean_saving = sum(savings) / max(1, len(savings))
    learning_cost = sum(lib.work.values())
    overhead = twin + learning_cost
    net = mean_saving * horizon - overhead
    # leave-one-out calibration error of the twin-free estimator
    loo = []
    for j, (s_, e_, _) in enumerate(rows):
        rest = [r for k, r in enumerate(rows) if k != j]
        alpha = sum(r[0] for r in rest) / max(1e-9, sum(r[1] for r in rest))
        loo.append(abs(alpha * e_ - s_))
    alpha = sum(savings) / max(1e-9, sum(r[1] for r in rows))
    prop_attr = {p: c for p, c in attr_total.items() if not isinstance(p, tuple)}
    checks = {k[1]: c for k, c in attr_total.items() if isinstance(k, tuple) and k[0] == "checks"}
    total_prunes = max(1, sum(prop_attr.values()))
    per_prune = sum(savings) / total_prunes            # mean measured saving per prune on the micro-sample
    value = {p: prop_attr.get(p, 0) * per_prune - checks.get(p, 0) for p in set(prop_attr) | set(checks)}
    keep = sorted((p for p, v in value.items() if v > 0 and prop_attr.get(p, 0) > 0), key=lambda p: -value[p])
    admitted = keep if net > 0 and all(r[2] for r in rows) else []
    lib.tycho = dict(micro_sample=len(sample), twin_work=twin, learning_cost=learning_cost,
                     validation_overhead=overhead, mean_saving_per_task=mean_saving, horizon=horizon,
                     net_benefit=net, break_even_horizon=overhead / mean_saving if mean_saving > 0 else None,
                     identical_verdicts=all(r[2] for r in rows), alpha=alpha,
                     loo_abs_error_over_total_saving=sum(loo) / max(1, sum(savings)),
                     per_property_prunes=prop_attr, per_property_checks=checks,
                     per_property_value={p: round(v, 1) for p, v in value.items()}, admitted=admitted,
                     prunes_by_remaining_depth={str(k[1]): c for k, c in attr_total.items()
                                                if isinstance(k, tuple) and k[0] == "remaining"})
    return lib.tycho


def default_props(lib, roles_present):
    """Certifier default after admission: usable proved contracts restricted to admitted properties."""
    u = usable_props(lib, roles_present)
    adm = list(lib.tycho.get("admitted", ()))          # ordered by estimated pruning value
    return dict(numeric=[p for p in adm if p in u["numeric"]], provenance=u["provenance"] and "provenance" in adm,
                provenance_image=u.get("provenance_image", False), scalar_terminal=u["scalar_terminal"] and "kind" in adm)
