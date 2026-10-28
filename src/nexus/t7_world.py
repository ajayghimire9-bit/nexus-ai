"""7-trial tournament (t7) additions to the u5 world (NOT LOCKED). Imported only by t7 code; u5_world.py is NOT edited -
the fourth domain is registered into its tables at import time (runtime only).

Fourth domain E = energy billing (never used by u5): formula families with larger targets (sizes 9-21, harder than the
u5 ceiling) and one lifecycle family E.meter (billing cycles: OPEN / READ / ADJUST / CLOSE / DISPUTE with accumulators)."""
from __future__ import annotations

from nexus import u5_stateful as SF
from nexus import u5_world as W
from nexus.u5_world import B, C, F, G, T

E_FAMILIES = {
    "E.cost": dict(roles={"kwh": "watt", "rate_c": "price"}, out="num", node=B("/", B("*", F("kwh"), F("rate_c")), T("cents"))),
    "E.vat": dict(roles={"kwh": "watt", "rate_c": "price"}, out="num",
                  node=B("*", B("/", B("*", F("kwh"), F("rate_c")), T("cents")), B("+", C(1), T("vat")))),
    "E.net": dict(roles={"imp": "watt", "exp": "watt", "rate_c": "price"}, out="num",
                  node=B("/", B("*", B("-", F("imp"), F("exp")), F("rate_c")), T("cents"))),
    "E.pf": dict(roles={"watt": "watt", "volt": "volt", "amp": "amp"}, out="num", node=B("/", F("watt"), B("*", F("volt"), F("amp")))),
    "E.standing": dict(roles={"days": "days", "kwh": "watt", "rate_c": "price"}, out="num",
                       node=B("+", B("*", F("days"), T("standing")), B("/", B("*", F("kwh"), F("rate_c")), T("cents")))),
    "E.cap": dict(roles={"kwh": "watt"}, out="bool", node=B("<", T("cap_kwh"), F("kwh"))),
    "E.member": dict(roles={"member": "member"}, out="bool", node=B("in", G("member"), T("allowed"))),
}
E_SYN = {"kwh": ["kwh", "energy_kwh", "usage", "consumed"], "rate_c": ["rate_cents", "tariff", "unit_rate", "price_c"],
         "imp": ["import_kwh", "imported", "grid_in"], "exp": ["export_kwh", "exported", "grid_out"]}
E_CONST = dict(cents=100, vat=0.2, standing=0.45, cap_kwh=3000)

W.FAMILIES.update(E_FAMILIES)
for k, v in E_SYN.items():
    W.SYN.setdefault(k, v)
_dom = W.domain_of
W.domain_of = lambda fam: "energy" if fam[0] == "E" else _dom(fam)   # noqa: E731
_reg = W._registry


def _registry_e(rnd):
    reg, others = _reg(rnd)
    reg.update(E_CONST)
    return reg, others


W._registry = _registry_e

# lifecycle family E.meter: OPEN starts a billing cycle; READ accumulates kWh; ADJUST replaces the last reading's
# contribution? (no: ADJUST adds a signed correction); CLOSE emits (bill, readings, total); DISPUTE while open freezes the
# cycle (READ ignored) until OPEN again closes it with ('disputed', total)
SF.FAM_KINDS["E.meter"] = ["OPEN", "READ", "ADJUST", "CLOSE", "DISPUTE"]
SF.X3_KINDS["E.meter"] = ["ESTIMATE"]
SF.INIT["E.meter"] = ("idle", 0, 0)
_step = SF.step


def step(fam, st, kind, v, x3):
    if fam != "E.meter":
        return _step(fam, st, kind, v, x3)
    m, a, b = st
    Q = SF.Q
    if kind == "OPEN":
        if m == "disputed":
            return ("open", 0, 0), [("disputed", a, b)]
        return (("open", 0, 0), []) if m == "idle" else (st, [Q])
    if kind == "READ":
        if m == "open":
            return ("open", a + 1, round(b + v, 6)), []
        return (st, []) if m == "disputed" else (st, [Q])
    if kind == "ADJUST":
        return (("open", a, round(b + v, 6)), []) if m == "open" else (st, [Q])
    if kind == "CLOSE":
        return (("idle", 0, 0), [("bill", a, b)]) if m == "open" else (st, [Q])
    if kind == "DISPUTE":
        return (("disputed", a, b), []) if m == "open" else (st, [Q])
    if kind == "ESTIMATE" and x3:
        return (("open", a, round(b + 2 * v, 6)), [("estimated", v, None)]) if m == "open" else (st, [Q])
    return st, [Q]


SF.step = step
SF.STATEFUL = tuple(SF.FAM_KINDS)
