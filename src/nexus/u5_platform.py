"""u5 end-to-end data-engineering projects and operators (NOT LOCKED).

PROJECT (one domain: logistics / clearing / iot; 16 ticks):
  stream A  records -> table A rows (id, status, value): status 'q:missing' if a formula input is not a number, else
            'q:unknown_member' if the member field is not in the registry's allowed list, else 'ok' with value = the
            domain formula (a FAMILIES numeric family) over the record and the registry constants
  stream B  lifecycle events (the domain's stateful family) -> per-event output rows (a per-key machine with registers)
  faults from tick 9:  dev / val  D1 declared unit change (registry declares minor units; the field arrives x100)
                                  D2 never-seen member values appear (must be quarantined)
                       test only  X3 new lifecycle event kinds in stream B (u5_stateful.X3_KINDS)
                                  X4 undeclared encoding change: the formula's first numeric field arrives nested as
                                     {"value": v, "unit": "std"}
BUILD (after tick 8) from the visible ticks 1-8 labelled by the spec oracle, plus the membership queries a learner asks.
OPERATE ticks 9-16: run the deployed program (B state checkpointed every tick); monitors: registry change, output
  invariants (non-numeric value on an ok row; '?unknown' lifecycle symbol), spot checks (the oracle on 3 random records and
  on the histories of 2 random active keys per tick; counted). An alarm triggers the arm's repair; NEXUS repairs by
  resynthesis / relearning from an oracle-labelled incident sample (counted), shadow-verifies on a held-out part of it,
  redeploys and backfills the tick; anything it cannot repair is escalated (a counted human repair). One crash is injected
  per project (mid-tick; recovery from the last checkpoint; the recovered outputs and state are compared with a clean
  re-run from the same checkpoint).
EVALUATION (independent of every arm): final tables for ticks 9-16 vs the reference; silent error = the arm claims healthy
  but the data are wrong; independently correct = data correct, completed, no human repair."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time

from nexus import oop_synthesizer as S
from nexus import u5_construct as K
from nexus import u5_library as LB
from nexus import u5_stateful as SF
from nexus import u5_statesplit as SP
from nexus import u5_world as W

DOMAINS = W.DOMAINS
STATEFUL_OF = {"logistics": "L.barrier", "clearing": "C.clearing", "iot": "I.session"}
NUMERIC = {d: [f for f in W.FAMILIES if W.domain_of(f) == d and W.FAMILIES[f]["out"] == "num"] for d in DOMAINS}
TICKS, BUILD_TICKS, FAULT_TICK = 16, 8, 9
N_A, N_B = 30, 40


def fault_of(seed, split):
    return ("D1", "D2")[seed % 2] if split != "test" else ("X3", "X4")[seed % 2]


class Project:
    def __init__(self, seed, split):
        rnd = random.Random(f"u5-project-{seed}")
        self.seed, self.split = seed, split
        self.domain = DOMAINS[seed % 3]
        self.fault = fault_of(seed, split)
        self.fam = rnd.choice(NUMERIC[self.domain])
        self.sfam = STATEFUL_OF[self.domain]
        fam = W.FAMILIES[self.fam]
        reg, others = W._registry(rnd)
        roles = dict(fam["roles"])
        names = {r: rnd.choice(W.SYN[r]) for r in roles}
        member_name = rnd.choice([m for m in W.SYN["member"] if m not in names.values()])
        self.names = names
        self.node = W._bind(fam["node"], names)
        self.table = W._subset_registry(reg, self.node)
        self.table["allowed"] = list(reg["allowed"])
        self.member = member_name
        self.id_field = rnd.choice(["rec_id", "row_id", "uid", "msg_id"])
        self.num_fields = [names[r] for r, k in roles.items() if k not in ("ccy", "member")]
        self.fault_field = self.num_fields[0]
        self.known_others = others[:3]
        self.new_members = ["N%02d" % i for i in range(1, 9)]
        self.schema = SF.Schema(rnd)
        self.x3 = self.fault == "X3"
        ctx = dict(fx=reg["fx"], allowed=reg["allowed"], others=others)
        self.ticks = {}
        bstate, key_n = {}, 0
        for t in range(1, TICKS + 1):
            late = t >= FAULT_TICK
            reg_t = copy.deepcopy(self.table)
            if late and self.fault == "D1":
                reg_t["units"] = {self.fault_field: "minor"}
            recs = []
            for i in range(N_A):
                r = {names[role]: W._gen(kind, rnd, ctx) for role, kind in roles.items()}
                if rnd.random() < 0.04:
                    r[rnd.choice(self.num_fields)] = rnd.choice(["N/A", None, ""])
                u = rnd.random()
                r[self.member] = (rnd.choice(self.new_members) if late and self.fault == "D2" and u < 0.2 else
                                  rnd.choice(self.known_others) if u > 0.9 else rnd.choice(reg["allowed"]))
                r[self.id_field] = f"{t:02d}-{i:03d}"
                if late and self.fault == "D1" and isinstance(r[self.fault_field], (int, float)):
                    r[self.fault_field] = int(round(r[self.fault_field] * 100))
                if late and self.fault == "X4" and isinstance(r[self.fault_field], (int, float)):
                    r[self.fault_field] = {"value": r[self.fault_field], "unit": "std"}
                recs.append(r)
            evs = []
            kinds = SF.FAM_KINDS[self.sfam] + (SF.X3_KINDS[self.sfam] if late and self.x3 else [])
            active = [k for k, s in bstate.items() if s[0] not in ("absent",)]
            for _ in range(N_B):
                if not active or rnd.random() < 0.3:
                    key_n += 1
                    k = f"E{seed % 1000:03d}{key_n:05d}"
                    bstate[k] = SF.INIT[self.sfam]
                    active.append(k)
                else:
                    k = rnd.choice(active)
                st = bstate[k]
                valid = [kd for kd in kinds if SF.step(self.sfam, st, kd, 1.0, self.x3)[1] != [SF.Q]]
                kd = rnd.choice(valid) if valid and rnd.random() < 0.85 else rnd.choice(kinds)
                v = SF._value(self.sfam, rnd)
                bstate[k], _ = SF.step(self.sfam, st, kd, v, self.x3)
                e = {self.schema.key: k, self.schema.kind: kd, self.schema.val: v, self.schema.seq: t * 1000 + len(evs)}
                for d in self.schema.distract:
                    e[d] = rnd.randint(0, 9)
                evs.append(e)
            self.ticks[t] = dict(A=recs, B=evs, registry=reg_t)
        self.queries = dict(build_labels=0, spot=0, incident=0, mq=0, mq_events=0)

    # -------------------------------------------------------------- sealing (the generator runs only at seal time)
    FIELDS = ("seed", "split", "domain", "fault", "fam", "sfam", "names", "table", "member", "id_field", "num_fields", "fault_field",
              "known_others", "new_members", "x3")

    def to_json(self):
        d = {k: getattr(self, k) for k in self.FIELDS}
        d.update(node=repr(self.node), schema=vars(self.schema), ticks={str(t): v for t, v in self.ticks.items()})
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_json(cls, s):
        import ast
        d = json.loads(s)
        p = cls.__new__(cls)
        for k in cls.FIELDS:
            setattr(p, k, d[k])
        p.node = ast.literal_eval(d["node"])
        p.schema = SF.Schema.__new__(SF.Schema)
        p.schema.__dict__.update(d["schema"])
        p.ticks = {int(t): v for t, v in d["ticks"].items()}
        p.queries = dict(build_labels=0, spot=0, incident=0, mq=0, mq_events=0)
        return p

    # -------------------------------------------------------------- the spec oracle (black box to every arm)
    def ref_A(self, r, t):
        rr = dict(r)
        f = self.fault_field
        if isinstance(rr.get(f), dict):
            rr[f] = rr[f].get("value")
        if t.get("units", {}).get(f) == "minor" and isinstance(rr.get(f), (int, float)):
            rr[f] = rr[f] / 100
        for nf in self.num_fields:
            v = rr.get(nf)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return ("q:missing", None)
        if rr.get(self.member) not in t["allowed"]:
            return ("q:unknown_member", None)
        v = S.ev(self.node, {"r": rr, "t": t})
        return ("ok", round(v, 9) if isinstance(v, float) else v)

    def oracle_A(self, recs, tick, kind):
        self.queries[kind] += len(recs)
        reg = self.ticks[tick]["registry"]
        return [self.ref_A(r, reg) for r in recs]

    def ref_B(self, events):
        return SF.reference(self.sfam, events, self.schema, self.x3)

    def oracle_B(self, events, kind="mq"):
        if kind == "mq":
            self.queries["mq"] += 1
            self.queries["mq_events"] += len(events)
        else:
            self.queries[kind] += len(events)
        return self.ref_B(events)

    def truth(self):
        """Reference tables for ticks 9-16 (evaluation only)."""
        allB = [e for t in range(1, TICKS + 1) for e in self.ticks[t]["B"]]
        rowsB = self.ref_B(allB)
        out, i = {}, 0
        for t in range(1, TICKS + 1):
            n = len(self.ticks[t]["B"])
            if t >= FAULT_TICK:
                out[t] = dict(A=[self.ref_A(r, self.ticks[t]["registry"]) for r in self.ticks[t]["A"]], B=rowsB[i:i + n])
            i += n
        return out


# ------------------------------------------------------------------------------------------------ deployable programs
class Program:
    """value_fn / status_fn nodes + library defs + a lifecycle runner (emitted class or a template object)."""

    def __init__(self, value, status, lib, b_kind, b_payload):
        self.value, self.status, self.lib, self.b_kind, self.b_payload = value, status, list(lib), b_kind, b_payload
        self.version = 0

    def source(self):
        parts = []
        if self.lib:
            parts.append(LB.lib_source(self.lib))
        parts.append(S.function_source("value_fn", ["r", "t"], self.value))
        parts.append(S.function_source("status_fn", ["r", "t"], self.status))
        if self.b_kind == "class":
            parts.append(self.b_payload["source"])
        else:
            parts.append(f"# lifecycle stream: {self.b_kind} template (not generated code)")
        return "\n\n".join(parts)

    def run_A(self, recs, reg):
        out = []
        for r in recs:
            env = {"r": r, "t": reg}
            st = _safe(self.status, env)
            if st == "ok":
                v = _safe(self.value, env)
                out.append(("ok", v if isinstance(v, (int, float)) and not isinstance(v, bool) else None))
            else:
                out.append((st if isinstance(st, str) else "q:error", None))
        return out

    def new_b(self):
        if self.b_kind == "class":
            return SP.compile_class(self.b_payload["source"], self.b_payload["name"])()
        if self.b_kind == "flat":
            return FlatRunner(self.b_payload)
        return self.b_payload["factory"]()


def _or_err(v):
    return S.ERR if v is None else v


def _safe(node, env):
    try:
        v = S.ev(node, env)
    except Exception:                                                    # noqa: BLE001
        return None
    return None if v is S.ERR else v


class FlatRunner:
    """FlatDict template as a stateful object (state = {key: last record}); checkpointable."""

    def __init__(self, fd):
        self.fd, self.last = fd, {}

    def ingest(self, e):
        p = self.last.get(e.get(self.fd.key))
        ab = self.fd.table.get((p.get(self.fd.ctrl) if p else None, e.get(self.fd.ctrl)), ())
        rows = []
        for r in ab:
            vs = [None if s is None else (e.get(s[1]) if s[0] == "cur" else (p.get(s[1]) if s[0] == "prev" and p else s[1]))
                  for s in r[1:]]
            rows.append((r[0], vs[0], vs[1]))
        self.last[e.get(self.fd.key)] = e
        return rows

    def get_state(self):
        return dict(last=self.last)

    def set_state(self, s):
        self.last = copy.deepcopy(s["last"])


def get_state(obj):
    if hasattr(obj, "get_state"):
        return copy.deepcopy(obj.get_state())
    return copy.deepcopy({k: v for k, v in obj.__dict__.items()})


def set_state(obj, s):
    if hasattr(obj, "set_state"):
        obj.set_state(s)
    else:
        obj.__dict__.update(copy.deepcopy(s))


# ------------------------------------------------------------------------------------------------ NEXUS synthesis steps
def synth_value(envs, ys, learner, budget_s, rounds=3, sample=30, seed=0):
    """CEGIS around the learner's solver (stratified sample, verify on all, add counterexamples)."""
    cfg, lib, solver = learner["cfg"], learner["lib"], learner.get("solver", "hybrid")
    rnd = random.Random(seed)
    idx = rnd.sample(range(len(envs)), min(sample, len(envs)))
    t0 = time.process_time()
    st = {}
    for _ in range(rounds):
        left = budget_s - (time.process_time() - t0)
        if left <= 0.2:
            break
        e2, y2 = [envs[i] for i in idx], [ys[i] for i in idx]
        fn = K.solve_hybrid if solver == "hybrid" else K.solve
        node, st, _ = fn(e2, y2, cfg, lib, left)
        if node is None:
            return None, dict(st, cpu_s=round(time.process_time() - t0, 3))
        bad = [i for i in range(len(envs)) if not K._ok(_or_err(_safe(node, envs[i])), ys[i])]
        if not bad:
            return node, dict(st, cpu_s=round(time.process_time() - t0, 3))
        idx = sorted(set(idx) | set(bad[:10]))
    return None, dict(st, cpu_s=round(time.process_time() - t0, 3))


def _orders_strings(n, env):
    """Type priors (domain-free): no ordering of string identifiers; no equality between two booleans (use and / or)."""
    if n[0] == "b" and n[1] in ("<", "<=") and isinstance(_safe(n[2], env), str):
        return True
    if n[0] == "b" and n[1] == "==" and isinstance(_safe(n[2], env), bool) and isinstance(_safe(n[3], env), bool):
        return True
    return any(_orders_strings(c, env) for c in n[2:] if isinstance(c, tuple)) if n[0] in ("u", "b", "if") else False


def synth_status(envs, labels, max_s, cfg=None, sample=150, rounds=5):
    """Categorical status program: CEGIS over a stratified sample; the bank is built by the arm's construction policy and
    decision lists come from the (precision-guarded) Phase 1 Solver logic. Prior (e2e dev revision 2): string values are
    identifiers, not ordered - no < / <= on string operands (pdev 8007 learned warehouse < 'S07' for membership)."""
    t0 = time.process_time()
    cfg = cfg or K.default_config("baseline")
    pick = S.stratified(envs, sample, labels=labels)
    st = dict(rounds=0)
    while True:
        st["rounds"] += 1
        left = max_s - (time.process_time() - t0)
        if left <= 0.5:
            return None, st
        ins, outs = [envs[i] for i in pick], [labels[i] for i in pick]
        _, _, srch = K.solve(ins, outs, dict(cfg, cap=30000), [], 0.4 * left)
        bank = K._Bank.__new__(K._Bank)
        bank.inputs, bank.E, bank.sig, bank.levels, bank.consts = ins, len(ins), {}, {}, []
        bank.entries = [(e[0], e[1], e[2]) for e in srch.sig.values() if not _orders_strings(e[0], ins[0])]
        bank._num_index()
        try:
            n = K._Solver(bank, outs, max_s=max(0.5, max_s - (time.process_time() - t0))).solve()
        except RecursionError:
            n = None
        if n is None:
            return None, st
        n = S.simplify(n)
        bad = [i for i in range(len(envs)) if _safe(n, envs[i]) != labels[i]]
        if not bad:
            st["cpu_s"] = round(time.process_time() - t0, 3)
            return n, st
        if st["rounds"] >= rounds:
            return None, st
        pick = sorted(set(pick) | set(bad[:40]))


def learn_b(events, outputs, query, mode, seed=0):
    if mode == "statesplit":
        r = SP.learn_class(events, outputs, query, seed=seed, max_s=60.0)
        if not r or r["source"] is None:
            return None
        return ("class", dict(source=r["source"], name=r["name"], witnesses=r["witnesses"], n_modes=r["machine"]["n"],
                              n_regs=len(r["machine"]["regs"]), queries=r["queries"]))
    f = SP.discover_fields(events, outputs, query)
    if f["key"] is None or f["ctrl"] is None:
        return None
    return ("flat", SP.FlatDict(events, outputs, f))


# ------------------------------------------------------------------------------------------------ arms
class NexusArm:
    """NEXUS_U5 and its single-pillar ablations: learner = {cfg, lib, solver}; b_mode = 'statesplit' | 'flat'."""
    kind = "nexus"

    def __init__(self, name, learner, b_mode="statesplit", value_s=40.0, status_s=30.0):
        self.name, self.learner, self.b_mode, self.value_s, self.status_s = name, learner, b_mode, value_s, status_s

    def build(self, P):
        recs = [(r, t) for t in range(1, BUILD_TICKS + 1) for r in P.ticks[t]["A"]]
        labs = []
        for t in range(1, BUILD_TICKS + 1):
            labs += P.oracle_A(P.ticks[t]["A"], t, "build_labels")
        envs = [{"r": r, "t": P.ticks[t]["registry"]} for r, t in recs]
        c0 = time.process_time()
        status, sst = synth_status(envs, [s for s, _ in labs], self.status_s, self.learner["cfg"])
        ok = [(e, v) for e, (s, v) in zip(envs, labs) if s == "ok"]
        value, vst = synth_value([e for e, _ in ok], [v for _, v in ok], self.learner, self.value_s, seed=P.seed)
        evs = [e for t in range(1, BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
        outs = P.oracle_B(evs, "build_labels")
        b = learn_b(evs, outs, lambda x: P.oracle_B(x), self.b_mode, seed=P.seed)
        cpu = time.process_time() - c0
        info = dict(status_stats={k: v for k, v in sst.items() if k != "per"}, value_stats=vst, build_cpu_s=round(cpu, 3))
        if status is None or value is None or b is None:
            info["unsolved"] = [n for n, x in (("status", status), ("value", value), ("lifecycle", b)) if x is None]
            return None, info
        prog = Program(value, status, self.learner["lib"], b[0], b[1])
        if b[0] == "class":
            info.update(n_modes=b[1]["n_modes"], n_regs=b[1]["n_regs"], b_queries=b[1]["queries"])
        return prog, info

    # repair hooks (called by the operator)
    def repair_A(self, P, prog, tick, sample, labs, archive):
        """Resynthesise the parts of the A program that disagree with the labelled incident sample."""
        reg = P.ticks[tick]["registry"]
        envs = [{"r": r, "t": reg} for r in sample]
        n_hold = max(4, len(sample) // 4)
        tr_e, tr_l, ho_e, ho_l = envs[:-n_hold], labs[:-n_hold], envs[-n_hold:], labs[-n_hold:]
        new = copy.copy(prog)
        got = prog.run_A(sample, reg)
        if any(g[0] != l[0] for g, l in zip(got, labs)):
            merged_e = archive["envs"] + tr_e
            merged_l = archive["status"] + [s for s, _ in tr_l]
            st, _ = synth_status(merged_e, merged_l, self.status_s, self.learner["cfg"])
            if st is None:
                st, _ = synth_status(tr_e, [s for s, _ in tr_l], self.status_s, self.learner["cfg"])
            if st is None:
                return None
            new.status = st
        okp = [(e, v) for e, (s, v) in zip(tr_e, tr_l) if s == "ok"]
        if any(g[0] == "ok" and l[0] == "ok" and not K._ok(g[1] if g[1] is not None else S.ERR, l[1]) for g, l in zip(new.run_A(sample, reg), labs)):
            v, _ = synth_value([e for e, _ in okp], [y for _, y in okp], self.learner, self.value_s, seed=tick)
            if v is None:
                return None
            new.value = v
        chk = new.run_A([e["r"] for e in ho_e], reg)
        if not all(g[0] == l[0] and (l[0] != "ok" or K._ok(g[1] if g[1] is not None else S.ERR, l[1])) for g, l in zip(chk, ho_l)):
            return None
        new.version = prog.version + 1
        return new

    def repair_B(self, P, prog, archive_events, archive_rows):
        b = learn_b(archive_events, archive_rows, lambda x: P.oracle_B(x), self.b_mode, seed=len(archive_events))
        if b is None:
            return None
        new = copy.copy(prog)
        new.b_kind, new.b_payload = b
        new.version = prog.version + 1
        return new


class FixedArm:
    """Author-written pipeline from the documented spec (names, formula, validity rules, the documented lifecycle; it
    handles the KNOWN fault classes: declared unit changes and unseen members). It cannot repair anything else: alarms
    are escalated (counted human repair: a human patches it with the corrected handler). Conventional = the same
    handlers with no registry-unit handling and no monitors (always claims healthy)."""
    kind = "fixed"

    def __init__(self, name, monitored=True, handle_units=True):
        self.name, self.monitored, self.handle_units = name, monitored, handle_units

    def build(self, P):
        node = P.node
        f = P.fault_field
        if self.handle_units:                                      # documented: honour registry unit declarations
            fv = ("u", "float", ("b", "get", ("var", "r"), ("const", f)))
            scaled = ("if", ("b", "==", ("b", "get", ("b", "get", ("var", "t"), ("const", "units")), ("const", f)), ("const", "minor")),
                      ("b", "/", fv, ("const", 100)), fv)
            node = _subst_field(node, f, scaled)
        guard = ("b", "in", ("const", "units"), ("var", "t"))
        if self.handle_units:
            node = ("if", guard, node, P.node)
        miss = None
        for nf in P.num_fields:
            g = ("u", "not", ("u", "isnum", ("b", "get", ("var", "r"), ("const", nf))))
            miss = g if miss is None else ("b", "or", miss, g)
        status = ("if", miss, ("const", "q:missing"),
                  ("if", ("b", "in", ("b", "get", ("var", "r"), ("const", P.member)), ("b", "get", ("var", "t"), ("const", "allowed"))),
                   ("const", "ok"), ("const", "q:unknown_member")))
        fam, schema = P.sfam, P.schema

        def factory():
            return DocMachine(fam, schema, x3=False)
        return Program(node, status, [], "doc", dict(factory=factory)), dict(build_cpu_s=0.0)

    def repair_A(self, *a, **k):
        return None

    def repair_B(self, *a, **k):
        return None


def _subst_field(n, f, new):
    if n == ("u", "float", ("b", "get", ("var", "r"), ("const", f))):
        return new
    if n[0] in ("var", "const"):
        return n
    return tuple(_subst_field(c, f, new) if isinstance(c, tuple) else c for c in n)


class DocMachine:
    """The documented lifecycle (as of build time) written by hand; unknown kinds are rejected as invalid."""

    def __init__(self, fam, schema, x3=False):
        self.fam, self.schema, self.x3, self.st = fam, schema, x3, {}

    def ingest(self, e):
        k = e.get(self.schema.key)
        s = tuple(self.st.get(k, SF.INIT[self.fam]))
        v = e.get(self.schema.val)
        v = v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
        s2, rows = SF.step(self.fam, s, e.get(self.schema.kind), v, self.x3)
        self.st[k] = list(s2)
        return rows

    def get_state(self):
        return dict(st=self.st)

    def set_state(self, s):
        self.st = copy.deepcopy(s["st"])


# ------------------------------------------------------------------------------------------------ the operator
def operate(P, arm, prog, crash_tick, archive_A, max_repairs=6):
    """Run ticks 9-16. Returns outputs, claims, ledger, cost."""
    rnd = random.Random(f"ops-{P.seed}-{arm.name}")
    ledger, outputs = [], {}
    human = 0
    c0 = time.process_time()
    hist_B = [e for t in range(1, BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
    obj = prog.new_b()
    for e in hist_B:                                                # warm state from the visible history
        obj.ingest(e)
    ckpt = get_state(obj)
    prev_reg = P.ticks[BUILD_TICKS]["registry"]
    crash_ok = None
    repairs = 0
    for t in range(FAULT_TICK, TICKS + 1):
        tk = P.ticks[t]
        reg = tk["registry"]
        A = prog.run_A(tk["A"], reg)
        if t == crash_tick:                                         # crash mid-tick, recover from the checkpoint
            half = len(tk["B"]) // 2
            for e in tk["B"][:half]:
                obj.ingest(e)
            obj = prog.new_b()
            set_state(obj, ckpt)
            Bo = [obj.ingest(e) for e in tk["B"]]
            clean = prog.new_b()
            set_state(clean, ckpt)
            Bc = [clean.ingest(e) for e in tk["B"]]
            crash_ok = _digest(Bo) == _digest(Bc) and _digest(get_state(obj)) == _digest(get_state(clean))
            ledger.append(dict(tick=t, kind="crash_recovery", identical=crash_ok))
        else:
            Bo = [obj.ingest(e) for e in tk["B"]]
        alarms = []
        if arm.kind != "fixed" or arm.monitored:
            if json.dumps(reg, sort_keys=True, default=str) != json.dumps(prev_reg, sort_keys=True, default=str) and \
                    not (arm.kind == "fixed" and arm.handle_units):
                alarms.append("A:registry_change")
            if any(s == "ok" and v is None for s, v in A) or any(s == "q:error" for s, _ in A):
                alarms.append("A:invariant")
            if any(r[0] == "?unknown" for rows in Bo for r in rows):
                alarms.append("B:unknown_symbol")
            idx = rnd.sample(range(len(tk["A"])), 3)
            want = P.oracle_A([tk["A"][i] for i in idx], t, "spot")
            if any(not _rowA_eq(A[i], w) for i, w in zip(idx, want)):
                alarms.append("A:spot_check")
            keys = list({e[P.schema.key] for e in tk["B"]})
            for k in rnd.sample(keys, min(2, len(keys))):
                h = [e for e in hist_B + tk["B"] if e[P.schema.key] == k]
                wr = P.oracle_B(h, "spot")
                n_now = sum(1 for e in tk["B"] if e[P.schema.key] == k)
                mine = [rows for e, rows in zip(tk["B"], Bo) if e[P.schema.key] == k]
                if not all(SF.rows_eq(g, w) for g, w in zip(mine, wr[-n_now:])):
                    alarms.append("B:spot_check")
                    break
        ledger.append(dict(tick=t, kind="tick", alarms=alarms))
        if alarms:
            fixed_A = fixed_B = True
            if any(a.startswith("A:") for a in alarms):
                fixed_A = False
                if repairs < max_repairs:
                    smp = rnd.sample(tk["A"], min(40, len(tk["A"])))
                    labs = P.oracle_A(smp, t, "incident")
                    new = arm.repair_A(P, prog, t, smp, labs, archive_A)
                    repairs += 1
                    if new is not None:
                        prog = new
                        A = prog.run_A(tk["A"], reg)
                        fixed_A = True
                        ledger.append(dict(tick=t, kind="repair_A", version=prog.version))
            if any(a.startswith("B:") for a in alarms):
                fixed_B = False
                if repairs < max_repairs:
                    arch = hist_B + tk["B"]
                    rows = P.oracle_B(arch, "incident")
                    new = arm.repair_B(P, prog, arch, rows)
                    repairs += 1
                    if new is not None:
                        obj2 = new.new_b()
                        for e in hist_B:
                            obj2.ingest(e)
                        Bo2 = [obj2.ingest(e) for e in tk["B"]]
                        if all(SF.rows_eq(g, w) for g, w in zip(Bo2, rows[len(hist_B):])):
                            prog, obj, Bo = new, obj2, Bo2
                            fixed_B = True
                            ledger.append(dict(tick=t, kind="repair_B", version=prog.version))
            if not (fixed_A and fixed_B):
                human += 1                                          # escalate: a human patches with the reference
                ledger.append(dict(tick=t, kind="escalated", alarms=alarms))
                A = [P.ref_A(r, reg) for r in tk["A"]]
                allb = hist_B + tk["B"]
                Bo = P.ref_B(allb)[len(hist_B):]
                prog = _human_patch(P, prog)
                obj = prog.new_b()
                for e in allb:
                    obj.ingest(e)
        outputs[t] = dict(A=A, B=Bo)
        hist_B += tk["B"]
        ckpt = get_state(obj)
        prev_reg = reg
    claims = True                     # every alarm ends repaired or escalated; an arm believes its final tables
    return dict(outputs=outputs, claims_healthy=claims, ledger=ledger, human_repairs=human, crash_ok=crash_ok,
                ops_cpu_s=round(time.process_time() - c0, 3), program=prog)


def _human_patch(P, prog):
    new = copy.copy(prog)
    new.b_kind = "doc"
    fam, schema, x3 = P.sfam, P.schema, P.x3
    new.b_payload = dict(factory=lambda: DocMachine(fam, schema, x3=x3))
    new.value, new.status = ("const", None), ("const", None)
    new.run_A = lambda recs, reg: [P.ref_A(r, reg) for r in recs]
    return new


def _rowA_eq(g, w):
    if g[0] != w[0]:
        return False
    if w[0] != "ok":
        return True
    return g[1] is not None and K._ok(g[1], w[1])


def _digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def tuplify(x):
    """JSON lists back to AST tuples."""
    return tuple(tuplify(v) for v in x) if isinstance(x, list) else x


def evaluate(P, res):
    truth = P.truth()
    bad_A = bad_B = 0
    for t, tr in truth.items():
        o = res["outputs"].get(t)
        if o is None:
            return dict(data_ok=False, bad_A=-1, bad_B=-1)
        bad_A += sum(not _rowA_eq(g, w) for g, w in zip(o["A"], tr["A"]))
        bad_B += sum(not SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(o["B"], tr["B"]))
    return dict(data_ok=bad_A == 0 and bad_B == 0, bad_A=bad_A, bad_B=bad_B)


def run_project(P, arm):
    c0 = time.process_time()
    prog, info = arm.build(P)
    build_cpu = time.process_time() - c0
    if prog is None:
        return dict(arm=arm.name, project=P.seed, domain=P.domain, fault=P.fault, outcome="ABSTAIN", completed=False, data_ok=False,
                    claims_healthy=False, silent=False, human_repairs=0, independently_correct=False, crash_ok=None,
                    build=info, cost=dict(build_cpu_s=round(build_cpu, 3), ops_cpu_s=0.0, queries=dict(P.queries)))
    archive = dict(envs=[], status=[])
    for t in range(1, BUILD_TICKS + 1):
        reg = P.ticks[t]["registry"]
        archive["envs"] += [{"r": r, "t": reg} for r in P.ticks[t]["A"]]
        archive["status"] += [P.ref_A(r, reg)[0] for r in P.ticks[t]["A"]]          # already labelled at build (no recount)
    crash_tick = random.Random(f"crash-{P.seed}").randint(10, 15)
    build_src = prog.source()
    res = operate(P, arm, prog, crash_tick, archive)
    ev_ = evaluate(P, res)
    out = dict(arm=arm.name, project=P.seed, domain=P.domain, fault=P.fault, family=P.fam, lifecycle=P.sfam, outcome="COMPLETED",
               completed=True, data_ok=ev_["data_ok"], bad_A=ev_["bad_A"], bad_B=ev_["bad_B"], claims_healthy=res["claims_healthy"],
               silent=res["claims_healthy"] and not ev_["data_ok"], human_repairs=res["human_repairs"],
               independently_correct=ev_["data_ok"] and res["human_repairs"] == 0, crash_ok=res["crash_ok"],
               repairs=[x for x in res["ledger"] if x["kind"] in ("repair_A", "repair_B", "escalated")],
               alarms=sum(len(x.get("alarms", [])) for x in res["ledger"] if x["kind"] == "tick"),
               build=info, cost=dict(build_cpu_s=round(build_cpu, 3), ops_cpu_s=res["ops_cpu_s"], queries=dict(P.queries)))
    try:
        out["deployed_source"] = res["program"].source() if res["human_repairs"] == 0 else None
    except Exception:                                                # noqa: BLE001
        out["deployed_source"] = None
    out["build_source"] = build_src
    return out
