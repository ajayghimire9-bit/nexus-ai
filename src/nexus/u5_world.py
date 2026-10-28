"""Unified 5-pillar track (u5) task world (NOT LOCKED). Three domains - logistics, financial clearing, IoT telemetry - each
with (a) scalar / validity FORMULA families (synthesis tasks for Pillars 2-5) and (b) one STATEFUL lifecycle family per
domain that no flat per-key dictionary lookup can express (Pillar 1).

Every task is generated from an author-written reference (the black-box ORACLE); learners see only example inputs and the
oracle's outputs, plus the membership queries they choose to ask (counted). Physical field names are drawn per instance
from synonym lists and distractor fields are added, so a program must read the record, not a fixed schema.

Reference programs for formula families are written as oop_synthesizer nodes (so the size of the target is known); the
stateful references are small hand-written machines with registers. Nothing here is imported by a learner except through
Task.oracle / Task.query (a learner that reads `reference` is a leak; tests assert the learners do not)."""
from __future__ import annotations

import random

from nexus.oop_synthesizer import ev

DOMAINS = ("logistics", "clearing", "iot")


# ------------------------------------------------------------------------------------------------ node builders
def F(role):                                          # float(r.get(<role>)): a numeric field
    return ("u", "float", ("b", "get", ("var", "r"), ("const", "@" + role)))


def G(role):                                          # r.get(<role>): a raw field
    return ("b", "get", ("var", "r"), ("const", "@" + role))


def T(name):                                          # t.get(<name>): a registry constant / table
    return ("b", "get", ("var", "t"), ("const", name))


def B(op, a, b):
    return ("b", op, a, b)


def C(v):
    return ("const", v)


def _bind(n, names):
    if n[0] == "const" and isinstance(n[1], str) and n[1].startswith("@"):
        return ("const", names[n[1][1:]])
    if n[0] in ("var", "const"):
        return n
    return tuple(_bind(c, names) if isinstance(c, tuple) else c for c in n)


# ------------------------------------------------------------------------------------------------ value generators
def _gen(kind, rnd, ctx):
    if kind == "money":
        return round(rnd.uniform(5, 2000), 2)
    if kind == "pct":
        return rnd.choice([0, 5, 10, 12.5, 20, 25])
    if kind == "qty":
        return rnd.randint(1, 500)
    if kind == "price":
        return round(rnd.uniform(1, 300), 2)
    if kind == "rate":
        return round(rnd.uniform(0.01, 0.09), 4)
    if kind == "days":
        return rnd.randint(1, 365)
    if kind == "dim":
        return round(rnd.uniform(5, 120), 1)
    if kind == "lb":
        return round(rnd.uniform(0.5, 90), 2)
    if kind == "ts":
        return rnd.randint(1_700_000_000, 1_700_900_000)
    if kind == "dur":
        return rnd.randint(60, 200_000)
    if kind == "temp_f":
        return round(rnd.uniform(-20, 110), 1)
    if kind == "raw":
        return rnd.randint(100, 4000)
    if kind == "volt":
        return round(rnd.uniform(110, 240), 1)
    if kind == "amp":
        return round(rnd.uniform(0.1, 20), 2)
    if kind == "watt":
        return rnd.randint(10, 5000)
    if kind == "ccy":
        return rnd.choice(sorted(ctx["fx"]))
    if kind == "member":
        pool = ctx["allowed"] if rnd.random() < 0.7 else ctx["others"]
        return rnd.choice(pool)
    if kind == "maybe_num":
        return rnd.choice(["N/A", None, "", "err"]) if rnd.random() < 0.3 else round(rnd.uniform(0, 500), 2)
    if kind == "side":
        return rnd.choice([1, -1])
    raise KeyError(kind)


SYN = {
    "amt": ["amount", "amt", "gross", "value", "total", "sum_amt"],
    "disc": ["discount", "disc_pct", "rebate", "markdown"],
    "ccy": ["currency", "ccy", "cur", "curr_code"],
    "qty": ["qty", "quantity", "units", "lots", "n_items"],
    "price": ["price", "px", "unit_price", "rate_px"],
    "px_in": ["entry_px", "open_price", "px_open", "buy_px"],
    "px_out": ["exit_px", "close_price", "px_close", "sell_px"],
    "principal": ["principal", "face", "notional_amt", "par"],
    "rate": ["rate", "coupon", "int_rate", "yield"],
    "days": ["days", "n_days", "tenor_days", "accrual_days"],
    "len": ["length", "len_cm", "l"], "wid": ["width", "wid_cm", "w"], "hgt": ["height", "hgt_cm", "h"],
    "lb": ["weight_lb", "lbs", "wt_lb", "gross_lb"],
    "t0": ["promised_ts", "eta_ts", "due_ts", "sla_ts"], "t1": ["delivered_ts", "pod_ts", "arrival_ts", "done_ts"],
    "shipped": ["shipped_qty", "qty_shipped", "sent"], "ordered": ["ordered_qty", "qty_ordered", "requested"],
    "temp_f": ["temp_f", "fahrenheit", "t_f", "temperature"], "raw": ["raw", "adc", "counts", "raw_val"],
    "volt": ["volts", "v", "voltage", "u_rms"], "amp": ["amps", "i", "current", "i_rms"],
    "watt": ["watts", "power_w", "p_w", "load"], "dur": ["secs", "duration_s", "elapsed", "dt"],
    "cur": ["reading", "value_now", "cur", "latest"], "prev": ["previous", "value_prev", "prev", "last"],
    "member": ["warehouse", "site", "desk", "device_type", "venue"], "opt": ["weight", "reading_opt", "measure", "level"],
    "side": ["side", "direction", "sign"], "lim": ["reading", "level", "value"],
}
DISTRACT = ["seq", "batch_id", "src", "note_len", "shard", "retry", "ver", "region_id"]


# ------------------------------------------------------------------------------------------------ formula families
# role -> value kind; target node; registry table; output type ("num" | "bool"); family id prefix gives the domain
FAMILIES = {
    # logistics
    "L.net": dict(roles={"amt": "money", "disc": "pct", "ccy": "ccy"}, out="num",
                  node=B("*", B("*", F("amt"), B("-", C(1), B("/", F("disc"), C(100)))),
                         B("get", T("fx"), G("ccy")))),
    "L.kg": dict(roles={"lb": "lb"}, out="num", node=B("*", F("lb"), T("kg_per_lb"))),
    "L.vol": dict(roles={"len": "dim", "wid": "dim", "hgt": "dim"}, out="num",
                  node=B("/", B("*", B("*", F("len"), F("wid")), F("hgt")), T("cm3_per_l"))),
    "L.delay": dict(roles={"t0": "ts", "t1": "ts"}, out="num", node=B("/", B("-", F("t1"), F("t0")), T("secs_per_hour"))),
    "L.fill": dict(roles={"shipped": "qty", "ordered": "qty"}, out="num", node=B("/", F("shipped"), F("ordered"))),
    "L.member": dict(roles={"member": "member"}, out="bool", node=B("in", G("member"), T("allowed"))),
    "L.late": dict(roles={"t0": "ts", "t1": "ts"}, out="bool", node=B("<", B("+", F("t0"), T("grace_s")), F("t1"))),
    # financial clearing
    "C.notional": dict(roles={"qty": "qty", "price": "price"}, out="num", node=B("*", F("qty"), F("price"))),
    "C.fee": dict(roles={"qty": "qty", "price": "price"}, out="num",
                  node=B("/", B("*", B("*", F("qty"), F("price")), T("fee_bps")), T("bps"))),
    "C.pnl": dict(roles={"px_in": "price", "px_out": "price", "qty": "qty"}, out="num",
                  node=B("*", B("-", F("px_out"), F("px_in")), F("qty"))),
    "C.accrued": dict(roles={"principal": "money", "rate": "rate", "days": "days"}, out="num",
                      node=B("/", B("*", B("*", F("principal"), F("rate")), F("days")), T("day_count"))),
    "C.usd": dict(roles={"amt": "money", "ccy": "ccy"}, out="num", node=B("*", F("amt"), B("get", T("fx"), G("ccy")))),
    "C.member": dict(roles={"member": "member"}, out="bool", node=B("in", G("member"), T("allowed"))),
    "C.limit": dict(roles={"qty": "qty", "price": "price"}, out="bool", node=B("<", T("max_notional"), B("*", F("qty"), F("price")))),
    # IoT telemetry
    "I.celsius": dict(roles={"temp_f": "temp_f"}, out="num", node=B("*", B("-", F("temp_f"), T("f_zero")), T("c_per_f"))),
    "I.calib": dict(roles={"raw": "raw"}, out="num", node=B("*", B("-", F("raw"), T("offset")), T("gain"))),
    "I.power": dict(roles={"volt": "volt", "amp": "amp"}, out="num", node=B("*", F("volt"), F("amp"))),
    "I.kwh": dict(roles={"watt": "watt", "dur": "dur"}, out="num", node=B("/", B("*", F("watt"), F("dur")), T("j_per_kwh"))),
    "I.delta": dict(roles={"cur": "raw", "prev": "raw"}, out="num", node=B("-", F("cur"), F("prev"))),
    "I.valid": dict(roles={"opt": "maybe_num"}, out="bool", node=("u", "isnum", G("opt"))),
    "I.over": dict(roles={"lim": "raw"}, out="bool", node=B("<", T("max_level"), F("lim"))),
}


def domain_of(fam):
    return {"L": "logistics", "C": "clearing", "I": "iot"}[fam[0]]


def _registry(rnd):
    fx = {"USD": 1.0, "EUR": round(rnd.uniform(1.0, 1.2), 4), "GBP": round(rnd.uniform(1.2, 1.35), 4),
          "JPY": round(rnd.uniform(0.006, 0.008), 6)}
    sites = ["S%02d" % i for i in range(1, 13)]
    rnd.shuffle(sites)
    return dict(fx=fx, allowed=sites[:6], kg_per_lb=0.45359237, cm3_per_l=1000, secs_per_hour=3600, grace_s=rnd.choice([3600, 7200, 14400]),
                fee_bps=rnd.choice([1.5, 2.5, 4.0]), bps=10000, day_count=rnd.choice([360, 365]), max_notional=rnd.choice([20000, 50000]),
                f_zero=32, c_per_f=5 / 9, offset=rnd.choice([50, 120, 200]), gain=rnd.choice([0.05, 0.1, 0.25]), j_per_kwh=3600000,
                max_level=rnd.choice([2500, 3000, 3500])), sites[6:]


def _subset_registry(reg, node):
    """Only the registry entries the family uses, plus a few distractor constants (keeps tasks honest but focused)."""
    used = set()

    def walk(n):
        if n[0] == "b" and n[1] == "get" and n[2] == ("var", "t") and n[3][0] == "const":
            used.add(n[3][1])
        for c in n[1:]:
            if isinstance(c, tuple):
                walk(c)
    walk(node)
    extra = [k for k in reg if k not in used and not isinstance(reg[k], (dict, list))]
    return {k: reg[k] for k in sorted(used) + extra[:2]}


class Task:
    """One synthesis task: examples (env dicts) + oracle outputs; held-out envs for generalisation; query() for
    membership queries (counted)."""

    def __init__(self, tid, family, seed, n_train=30, n_test=120):
        rnd = random.Random(f"u5-task-{family}-{seed}")
        self.tid, self.family, self.seed, self.domain = tid, family, seed, domain_of(family)
        fam = FAMILIES[family]
        reg, others = _registry(rnd)
        names = {role: rnd.choice(SYN[role]) for role in fam["roles"]}
        if len(set(names.values())) < len(names):                       # synonym clash -> suffix
            names = {r: f"{n}_{i}" for i, (r, n) in enumerate(names.items())}
        self.names = names
        self.reference = _bind(fam["node"], names)
        self.table = _subset_registry(reg, self.reference)
        self.out = fam["out"]
        ctx = dict(fx=reg["fx"], allowed=reg["allowed"], others=others)
        dis = rnd.sample(DISTRACT, 2)

        def rec():
            r = {names[role]: _gen(kind, rnd, ctx) for role, kind in fam["roles"].items()}
            for d in dis:
                r[d] = rnd.randint(0, 99)
            return {"r": r, "t": self.table}
        self.train = [rec() for _ in range(n_train)]
        self.test = [rec() for _ in range(n_test)]
        self.queries = 0
        self.y_train = [self.oracle(e) for e in self.train]
        self.queries = 0                                                # labelling the given examples is free

    def oracle(self, env):
        self.queries += 1
        v = ev(self.reference, env)
        return round(v, 9) if isinstance(v, float) else v


def tol(y):
    return 1e-6 * max(1.0, abs(y)) if isinstance(y, (int, float)) and not isinstance(y, bool) else 0.0


def correct_on(task, prog, envs=None):
    """Fraction of held-out envs where prog matches the oracle (within tolerance; exceptions are wrong)."""
    envs = task.test if envs is None else envs
    ok = 0
    for e in envs:
        y = ev(task.reference, e)
        try:
            v = ev(prog, e)
        except Exception:                                               # noqa: BLE001
            continue
        if isinstance(y, bool) or isinstance(v, bool):
            ok += v is y or v == y and type(v) is type(y)
        elif isinstance(y, (int, float)) and isinstance(v, (int, float)):
            ok += abs(v - y) <= tol(y)
    return ok / len(envs)


def suite(families, seeds, n_train=30):
    return [Task(f"{f}#{s}", f, s, n_train=n_train) for f in families for s in seeds]


def ref_size(task):
    from nexus.oop_synthesizer import size
    return size(task.reference)
