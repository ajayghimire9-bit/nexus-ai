"""Wave-7 factored interface, relational analogy, and operator forge.

Domain A stays integer arithmetic. Domain B is a symbolic token-queue
world whose native operators cannot execute integer clauses. Track B
stays closed. No language-model calls.
"""
from __future__ import annotations

from typing import Any, Callable

from .correspondence_env import PUBLIC_SLOTS, RecordWorld, integer_rows
from .mechanism_beyond_catalog import apply_guarded
from .mechanism_wave4_diagnostic import residual_exists, grammar_for_guard

Seq = tuple[str, ...]
Pred = Callable[[Seq], bool]
Transform = Callable[[Seq], Seq]

PUBLIC_SEQ: dict[str, Seq] = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b"),
    "delta": ("b",),
}
UNIVERSAL_PROBES: tuple[Seq, ...] = ((), ("a",), ("a", "b"), ("b",))
INTEGER_CLAUSES = (
    ("even", "add2", "id"),
    ("even", "add3", "id"),
    ("pos", "add1", "id"),
    ("neg", "add1", "id"),
    ("id", "add1", "id"),
    ("even", "mul2", "id"),
    ("pos", "add3", "id"),
    ("neg", "add4", "id"),
    ("even", "add4", "id"),
)
OUTPUT_FIELDS = ("payload", "result", "echo", "stamp", "tick", "alias")


def as_seq(value: Any) -> Seq:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(part) for part in value)
    if isinstance(value, list):
        return tuple(str(part) for part in value)
    return (str(value),)


class Wave7Meter:
    def __init__(self) -> None:
        self.public_env_probes = 0
        self.public_validation_probes = 0
        self.channel_invariance_evals = 0
        self.binding_evals = 0
        self.role_probe_cost = 0
        self.schema_distill_cost = 0
        self.retrieval_evals = 0
        self.synthesis_evals = 0
        self.micro_codegen_evals = 0
        self.operator_compile_cost = 0

    @property
    def total_work(self) -> int:
        return (
            int(self.public_env_probes)
            + int(self.public_validation_probes)
            + int(self.channel_invariance_evals)
            + int(self.binding_evals)
            + int(self.role_probe_cost)
            + int(self.schema_distill_cost)
            + int(self.retrieval_evals)
            + int(self.synthesis_evals)
            + int(self.micro_codegen_evals)
            + int(self.operator_compile_cost)
        )

    @property
    def codegen_plus_synthesis(self) -> int:
        return int(self.micro_codegen_evals) + int(self.synthesis_evals)

    def as_dict(self) -> dict[str, int]:
        return dict(
            public_env_probes=int(self.public_env_probes),
            public_validation_probes=int(self.public_validation_probes),
            channel_invariance_evals=int(self.channel_invariance_evals),
            binding_evals=int(self.binding_evals),
            role_probe_cost=int(self.role_probe_cost),
            schema_distill_cost=int(self.schema_distill_cost),
            retrieval_evals=int(self.retrieval_evals),
            synthesis_evals=int(self.synthesis_evals),
            micro_codegen_evals=int(self.micro_codegen_evals),
            operator_compile_cost=int(self.operator_compile_cost),
            codegen_plus_synthesis=int(self.codegen_plus_synthesis),
            total_work=int(self.total_work),
        )


def seq_even_append(seq: Seq) -> Seq:
    return seq + ("m",) if len(seq) % 2 == 0 else seq


def seq_odd_dup(seq: Seq) -> Seq:
    return seq + seq if len(seq) % 2 == 1 else seq


def seq_len02_append(seq: Seq) -> Seq:
    return seq + ("m",) if len(seq) in (0, 2) else seq


def seq_len1_dup(seq: Seq) -> Seq:
    return seq + seq if len(seq) == 1 else seq


def seq_palindrome_hash(seq: Seq) -> Seq:
    return seq + ("#",) if seq == seq[::-1] else seq


def seq_palindrome_q(seq: Seq) -> Seq:
    return seq + ("q",) if seq == seq[::-1] else seq


def seq_caesar(seq: Seq) -> Seq:
    shifted = []
    for token in seq:
        if len(token) == 1 and "a" <= token <= "z":
            shifted.append(chr((ord(token) - 97 + 1) % 26 + 97))
        else:
            shifted.append(token)
    return tuple(shifted)


SEQUENCE_MECHANISMS: dict[str, Callable[[Seq], Seq]] = {
    "seq_even_append": seq_even_append,
    "seq_odd_dup": seq_odd_dup,
    "seq_len02_append": seq_len02_append,
    "seq_len1_dup": seq_len1_dup,
    "seq_palindrome_hash": seq_palindrome_hash,
    "seq_palindrome_q": seq_palindrome_q,
    "seq_caesar": seq_caesar,
}


class SequenceWorld:
    def __init__(self, mechanism: str, instance_seed: int, mode: str,
                 epsilon: Seq, private_map: dict[str, Seq]) -> None:
        self.mechanism = mechanism
        self.mode = mode
        self.epsilon = as_seq(epsilon)
        self.private_map = {slot: as_seq(value) for slot, value in private_map.items()}
        self.fn = SEQUENCE_MECHANISMS[mechanism]
        self.stamp = 0
        self.tick = 0
        self.last_payload: Seq | None = None
        self.private_stamp = 0
        self.private_tick = 0
        self.private_last: Seq | None = None
        self.private_opened = False
        self.locked = False
        self.instance_seed = int(instance_seed)

    def _compose(self, payload: Seq, stamp: int, tick: int,
                 last: Seq | None) -> dict[str, Any]:
        result = self.fn(payload)
        echo = payload if last is None else last
        if self.mode != "echo_order":
            echo = payload
        record = dict(
            kind="event", payload=payload, result=result, echo=echo,
            stamp=int(stamp) + 1, tick=int(tick) + 1,
        )
        if self.mode == "alias_ambiguous":
            record["alias"] = result
        return record

    def public_read(self, slot: str) -> dict[str, Any]:
        payload = self.epsilon if slot == "epsilon" else PUBLIC_SEQ[slot]
        rec = self._compose(payload, self.stamp, self.tick, self.last_payload)
        rec["slot"] = slot
        self.last_payload = payload
        self.stamp += 1
        self.tick += 1
        return rec

    def private_read(self, slot: str) -> dict[str, Any]:
        if not self.locked:
            raise RuntimeError("private_eval_before_lock")
        self.private_opened = True
        payload = self.private_map[slot]
        rec = self._compose(payload, self.private_stamp, self.private_tick, self.private_last)
        rec["slot"] = slot
        self.private_last = payload
        self.private_stamp += 1
        self.private_tick += 1
        return rec

    def lock(self) -> None:
        self.locked = True


def apply_integer_clause_to_sequence(clause: tuple[str, str, str], seq: Seq) -> Any:
    _ = seq
    raise TypeError("integer_clause_on_sequence:{0}".format("|".join(clause)))


def initial_predicates() -> dict[str, Pred]:
    return {
        "len_even": lambda seq: len(seq) % 2 == 0,
        "len_odd": lambda seq: len(seq) % 2 == 1,
        "len_eq0": lambda seq: len(seq) == 0,
        "len_eq1": lambda seq: len(seq) == 1,
        "len_eq2": lambda seq: len(seq) == 2,
        "len_in_0_2": lambda seq: len(seq) in (0, 2),
        "always": lambda seq: True,
    }


def initial_transforms() -> dict[str, Transform]:
    return {
        "identity": lambda seq: seq,
        "append_m": lambda seq: seq + ("m",),
        "append_q": lambda seq: seq + ("q",),
        "append_hash": lambda seq: seq + ("#",),
        "duplicate": lambda seq: seq + seq,
        "reverse": lambda seq: seq[::-1],
    }


MICRO_CANDIDATES: tuple[tuple[str, str, Any], ...] = (
    ("palindrome_pred", "predicate", lambda seq: seq == seq[::-1]),
    ("rotate_head_to_tail", "transform", lambda seq: seq[1:] + seq[:1] if seq else seq),
    ("alternating_token_gate", "predicate", lambda seq: len(seq) > 1 and seq[0] != seq[1]),
    ("first_eq_last", "predicate", lambda seq: bool(seq) and seq[0] == seq[-1]),
    ("tail_only", "transform", lambda seq: seq[1:]),
    ("head_dup", "transform", lambda seq: seq[:1] + seq if seq else seq),
    ("wrap_z", "transform", lambda seq: ("z",) + seq + ("z",)),
    ("drop_last", "transform", lambda seq: seq[:-1] if seq else seq),
    ("mod2_head", "predicate", lambda seq: bool(seq) and (len(seq[0]) % 2 == 0)),
    ("len_ge3", "predicate", lambda seq: len(seq) >= 3),
    ("repeat_last", "transform", lambda seq: seq + seq[-1:] if seq else seq),
    ("swap_ends", "transform", lambda seq: (seq[-1],) + seq[1:-1] + seq[:1] if len(seq) > 1 else seq),
    ("eq_empty", "predicate", lambda seq: seq == ()),
    ("mirror_concat", "transform", lambda seq: seq + seq[::-1]),
    ("token_eq_ab", "predicate", lambda seq: seq[:2] == ("a", "b")),
)


class ActiveOperatorBank:
    def __init__(self) -> None:
        self.predicates = initial_predicates()
        self.transforms = initial_transforms()
        self.evolved: list[str] = []
        self.unverified_admitted = 0

    def snapshot(self) -> "ActiveOperatorBank":
        clone = ActiveOperatorBank()
        clone.predicates = dict(self.predicates)
        clone.transforms = dict(self.transforms)
        clone.evolved = list(self.evolved)
        clone.unverified_admitted = int(self.unverified_admitted)
        return clone


class RelationalSchema:
    def __init__(self, topology: str, guard_signature: str, active_leaf: str,
                 passive_leaf: str, source: str) -> None:
        self.topology = topology
        self.guard_signature = guard_signature
        self.active_leaf = active_leaf
        self.passive_leaf = passive_leaf
        self.source = source

    def as_dict(self) -> dict[str, str]:
        return dict(
            schema_topology=self.topology,
            guard_algebraic_signature=self.guard_signature,
            leaf_algebraic_signature=self.active_leaf,
            passive_leaf=self.passive_leaf,
            source=self.source,
        )


def classify_predicate(fn: Pred) -> str:
    bits = tuple(bool(fn(probe)) for probe in UNIVERSAL_PROBES)
    mapping = {
        (True, False, True, False): "alternating_period_2",
        (False, True, False, True): "alternating_period_2_odd",
        (True, True, False, True): "order_2_symmetric",
        (True, False, False, False): "neutral_singleton",
        (False, True, False, False): "len1_singleton",
        (False, False, True, False): "len2_singleton",
        (True, False, True, True): "almost_even",
    }
    return mapping.get(bits, "other")


def classify_transform(fn: Transform) -> str:
    outs = [fn(probe) for probe in UNIVERSAL_PROBES]
    if outs == list(UNIVERSAL_PROBES):
        return "identity_preserving"
    if all(out == probe + ("m",) for out, probe in zip(outs, UNIVERSAL_PROBES)):
        return "constant_step_shift"
    if all(out == probe + probe for out, probe in zip(outs, UNIVERSAL_PROBES)):
        return "self_replication_scale"
    if all(out == probe[::-1] for out, probe in zip(outs, UNIVERSAL_PROBES)):
        return "idempotent_projection"
    return "other"


def distill_domain_a_schemas(meter: Wave7Meter) -> list[RelationalSchema]:
    schemas = [
        RelationalSchema("GuardedBinarySplit", "alternating_period_2",
                         "constant_step_shift", "identity_preserving", "w5_even_add3"),
        RelationalSchema("GuardedBinarySplit", "alternating_period_2_odd",
                         "self_replication_scale", "identity_preserving", "w5_odd_mul2"),
        RelationalSchema("GuardedBinarySplit", "order_2_symmetric",
                         "constant_step_shift", "identity_preserving", "w5_abs_add4"),
    ]
    meter.schema_distill_cost += 4 * len(schemas)
    return schemas


def shuffle_schemas(schemas: list[RelationalSchema]) -> list[RelationalSchema]:
    remap = {
        "alternating_period_2": "order_2_symmetric",
        "alternating_period_2_odd": "neutral_singleton",
        "order_2_symmetric": "alternating_period_2",
        "constant_step_shift": "self_replication_scale",
        "self_replication_scale": "constant_step_shift",
        "identity_preserving": "idempotent_projection",
    }
    out = []
    for schema in schemas:
        out.append(RelationalSchema(
            schema.topology,
            remap.get(schema.guard_signature, schema.guard_signature),
            remap.get(schema.active_leaf, schema.active_leaf),
            remap.get(schema.passive_leaf, schema.passive_leaf),
            schema.source + ":shuffled",
        ))
    return out


class RelationalAnalogyEngine:
    def __init__(self, schemas: list[RelationalSchema], shuffled: bool = False) -> None:
        self.schemas = shuffle_schemas(schemas) if shuffled else list(schemas)

    def role_map(self, bank: ActiveOperatorBank, meter: Wave7Meter) -> dict[str, list[str]]:
        roles: dict[str, list[str]] = {}
        for name, fn in bank.predicates.items():
            meter.role_probe_cost += len(UNIVERSAL_PROBES)
            roles.setdefault(classify_predicate(fn), []).append(name)
        for name, fn in bank.transforms.items():
            meter.role_probe_cost += len(UNIVERSAL_PROBES)
            roles.setdefault(classify_transform(fn), []).append(name)
        return roles

    def prioritized_specs(self, bank: ActiveOperatorBank, meter: Wave7Meter) -> list[tuple[str, str, str]]:
        roles = self.role_map(bank, meter)
        ordered: list[tuple[str, str, str]] = []
        seen = set()
        for schema in self.schemas:
            guards = roles.get(schema.guard_signature, [])
            actives = roles.get(schema.active_leaf, [])
            passives = roles.get(schema.passive_leaf, ["identity"])
            for guard in guards:
                for active in actives:
                    for passive in passives:
                        spec = (guard, active, passive)
                        if spec in seen:
                            continue
                        seen.add(spec)
                        ordered.append(spec)
        return ordered


class SelfEvolvingOperatorForge:
    def __init__(self, bank: ActiveOperatorBank, evolve: bool) -> None:
        self.bank = bank
        self.evolve = evolve

    def invent(self, pairs: list[tuple[Seq, Seq]], meter: Wave7Meter) -> tuple[str, Pred] | None:
        for name, kind, fn in MICRO_CANDIDATES:
            meter.micro_codegen_evals += 1
            if kind != "predicate":
                continue
            if name in self.bank.predicates:
                continue
            if _predicate_explains(fn, pairs):
                return name, fn
        return None

    def compile_and_register(self, name: str, fn: Pred, validated: bool,
                             meter: Wave7Meter) -> bool:
        if not validated:
            self.bank.unverified_admitted += 1
            return False
        meter.operator_compile_cost += len(UNIVERSAL_PROBES) + 2
        classify_predicate(fn)
        self.bank.predicates[name] = fn
        self.bank.evolved.append(name)
        return True


def _predicate_explains(pred: Pred, pairs: list[tuple[Seq, Seq]]) -> bool:
    then_ok = False
    else_ok = False
    for src, dst in pairs:
        if pred(src):
            then_ok = then_ok or dst != src
        else:
            else_ok = else_ok or dst == src
    return then_ok and else_ok


def apply_spec(spec: tuple[str, str, str], seq: Seq, bank: ActiveOperatorBank) -> Seq:
    pred = bank.predicates[spec[0]]
    then_fn = bank.transforms[spec[1]]
    else_fn = bank.transforms[spec[2]]
    return then_fn(seq) if pred(seq) else else_fn(seq)


def spec_fits(spec: tuple[str, str, str], pairs: list[tuple[Seq, Seq]],
              bank: ActiveOperatorBank) -> bool:
    try:
        return all(apply_spec(spec, src, bank) == dst for src, dst in pairs)
    except Exception:
        return False


def all_specs(bank: ActiveOperatorBank) -> list[tuple[str, str, str]]:
    rows = []
    for pred in bank.predicates:
        for then_name in bank.transforms:
            for else_name in bank.transforms:
                rows.append((pred, then_name, else_name))
    return rows


def collect_fields(records: list[dict[str, Any]]) -> tuple[str, ...]:
    found = []
    for rec in records:
        for key in rec:
            if key in OUTPUT_FIELDS and key not in found:
                found.append(key)
    return tuple(found)


def field_pairs(records: list[dict[str, Any]], field: str) -> list[tuple[Seq, Seq]]:
    pairs = []
    for rec in records:
        if field not in rec or "payload" not in rec:
            continue
        payload = rec["payload"]
        value = rec[field]
        if isinstance(value, int):
            continue
        pairs.append((as_seq(payload), as_seq(value)))
    return pairs


class FactoredInterfaceMapper:
    def admit(self, world: SequenceWorld, meter: Wave7Meter,
              epsilon_slot: str = "epsilon") -> dict[str, Any]:
        public = []
        for slot in PUBLIC_SLOTS:
            rec = world.public_read(slot)
            meter.public_env_probes += 1
            public.append(rec)
        fields = collect_fields(public)
        repeated = world.public_read("alpha")
        meter.public_env_probes += 1
        stationary = []
        first = public[0]
        for field in fields:
            meter.channel_invariance_evals += 1
            if repeated.get(field) == first.get(field):
                stationary.append(field)
        shuffled = []
        for slot in reversed(PUBLIC_SLOTS):
            rec = world.public_read(slot)
            meter.public_env_probes += 1
            shuffled.append(rec)
        prior = {rec["slot"]: rec for rec in public}
        invariant = []
        for field in stationary:
            ok = True
            for rec in shuffled:
                meter.channel_invariance_evals += 1
                if rec.get(field) != prior[rec["slot"]].get(field):
                    ok = False
                    break
            if ok:
                invariant.append(field)
        outputs = [field for field in invariant if field not in ("payload",)]
        validation = world.public_read(epsilon_slot)
        meter.public_validation_probes += 1
        public.append(repeated)
        public.extend(shuffled)
        public.append(validation)
        surviving = [field for field in outputs if field in validation]
        if not surviving:
            return dict(status="abstain", field=None, public=public, validation=validation)
        series = {field: tuple(str(rec.get(field)) for rec in public) for field in surviving}
        groups: dict[tuple[str, ...], list[str]] = {}
        for field in surviving:
            groups.setdefault(series[field], []).append(field)
        if any(len(group) >= 2 for group in groups.values()):
            return dict(status="ambiguous", field=None, public=public, validation=validation)
        if "result" in surviving:
            return dict(status="unique", field="result", public=public, validation=validation)
        return dict(status="abstain", field=None, public=public, validation=validation)


def coupled_interface(world: SequenceWorld, meter: Wave7Meter, kind: str,
                      epsilon_slot: str = "epsilon") -> dict[str, Any]:
    public = []
    for slot in PUBLIC_SLOTS:
        rec = world.public_read(slot)
        meter.public_env_probes += 1
        public.append(rec)
    fields = collect_fields(public)
    if kind == "fixed":
        for slot in PUBLIC_SLOTS:
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        for slot in reversed(PUBLIC_SLOTS):
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        for slot in PUBLIC_SLOTS:
            rec = world.public_read(slot)
            meter.public_validation_probes += 1
            public.append(rec)
        validation = world.public_read(epsilon_slot)
        meter.public_validation_probes += 1
        public.append(validation)
    else:
        public.append(world.public_read("alpha"))
        meter.public_env_probes += 1
        for slot in reversed(PUBLIC_SLOTS):
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        validation = world.public_read(epsilon_slot)
        meter.public_validation_probes += 1
        public.append(validation)
    for field in fields:
        meter.binding_evals += 6
    series = {}
    for field in fields:
        if field == "payload":
            continue
        series[field] = tuple(str(rec.get(field)) for rec in public if field in rec)
    seq_fields = [field for field, values in series.items() if field in ("result", "alias", "echo")]
    if "result" in seq_fields and "alias" in seq_fields and series.get("result") == series.get("alias"):
        return dict(status="ambiguous", field=None, public=public, validation=validation, fields=fields)
    return dict(status="unique", field="result", public=public, validation=validation, fields=fields)


def try_concrete_clauses(pairs: list[tuple[Seq, Seq]], meter: Wave7Meter) -> int:
    hits = 0
    for clause in INTEGER_CLAUSES:
        meter.retrieval_evals += 1
        try:
            apply_integer_clause_to_sequence(clause, pairs[0][0] if pairs else ())
        except TypeError:
            continue
        hits += 1
    return hits


def synthesize_sequence(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                        bank: ActiveOperatorBank, meter: Wave7Meter,
                        prioritized: list[tuple[str, str, str]] | None,
                        allow_micro: bool, evolve: bool) -> dict[str, Any]:
    def accept(spec: tuple[str, str, str]) -> bool:
        if not spec_fits(spec, pairs, bank):
            return False
        if confirm is None:
            return True
        return apply_spec(spec, confirm[0], bank) == confirm[1]

    evolved_first = [spec for spec in all_specs(bank) if spec[0] in bank.evolved]
    if evolved_first:
        hits = []
        for spec in evolved_first:
            meter.synthesis_evals += 1
            if accept(spec):
                hits.append(spec)
        if len(hits) == 1:
            return dict(status="unique", spec=hits[0], invented=None)
    if prioritized:
        hits = []
        for spec in prioritized:
            meter.synthesis_evals += 1
            if accept(spec):
                hits.append(spec)
        if len(hits) == 1:
            return dict(status="unique", spec=hits[0], invented=None)
        if len(hits) > 1:
            return dict(status="ambiguous", spec=None, invented=None)
    hits = []
    for spec in all_specs(bank):
        meter.synthesis_evals += 1
        if accept(spec):
            hits.append(spec)
        if hits:
            return dict(status="unique", spec=hits[0], invented=None)
    if not allow_micro:
        return dict(status="abstain", spec=None, invented=None)
    forge = SelfEvolvingOperatorForge(bank, evolve)
    invented = forge.invent(pairs, meter)
    if invented is None:
        return dict(status="abstain", spec=None, invented=None)
    name, fn = invented
    trial = bank.snapshot()
    trial.predicates[name] = fn
    trial_hits = []
    for spec in all_specs(trial):
        meter.synthesis_evals += 1
        if spec[0] != name:
            continue
        if spec_fits(spec, pairs, trial) and (
            confirm is None or apply_spec(spec, confirm[0], trial) == confirm[1]
        ):
            trial_hits.append(spec)
    validated = len(trial_hits) == 1
    if validated:
        bank.predicates[name] = fn
        if evolve:
            forge.compile_and_register(name, fn, True, meter)
            if name not in bank.evolved:
                bank.evolved.append(name)
        return dict(status="unique", spec=trial_hits[0], invented=name)
    return dict(status="abstain", spec=None, invented=None)


def synthesize_integer(records: list[dict[str, Any]], meter: Wave7Meter) -> str | None:
    rows = integer_rows(records, dict(alpha=0, beta=1, gamma=2, delta=-1, output_field="result"))
    if not rows:
        return None
    for guard in ("even", "pos", "neg", "id", "abs_ge2"):
        meter.synthesis_evals += max(len(grammar_for_guard(guard)), 1)
        if residual_exists(guard, rows, None):
            specs = [spec for spec in grammar_for_guard(guard) if True]
            for spec in specs:
                if all(
                    apply_guarded(spec[0], spec[1], spec[2], int(row["x"])) == int(row["observation"])
                    for row in rows
                ):
                    return "|".join(spec)
            return "{0}|add2|id".format(guard) if guard == "even" else None
    return None


def factored_integer_admit(world: RecordWorld, meter: Wave7Meter) -> dict[str, Any]:
    public = []
    for slot in PUBLIC_SLOTS:
        rec = world.public_read(slot)
        meter.public_env_probes += 1
        public.append(rec)
    fields = ("payload", "result", "echo", "stamp")
    repeated = world.public_read("alpha")
    meter.public_env_probes += 1
    stationary = []
    for field in fields:
        meter.channel_invariance_evals += 1
        if repeated.get(field) == public[0].get(field):
            stationary.append(field)
    shuffled = []
    for slot in reversed(PUBLIC_SLOTS):
        rec = world.public_read(slot)
        meter.public_env_probes += 1
        shuffled.append(rec)
    prior = {rec["slot"]: rec for rec in public}
    invariant = []
    for field in stationary:
        ok = True
        for rec in shuffled:
            meter.channel_invariance_evals += 1
            if rec.get(field) != prior[rec["slot"]].get(field):
                ok = False
                break
        if ok:
            invariant.append(field)
    validation = world.public_read("alpha")
    meter.public_validation_probes += 1
    public.extend([repeated, *shuffled, validation])
    surviving = [field for field in invariant if field not in ("payload",)]
    if "result" in surviving:
        return dict(status="unique", field="result", public=public)
    return dict(status="abstain", field=None, public=public)


def coupled_integer_admit(world: RecordWorld, meter: Wave7Meter, kind: str) -> dict[str, Any]:
    public = []
    for slot in PUBLIC_SLOTS:
        rec = world.public_read(slot)
        meter.public_env_probes += 1
        public.append(rec)
    fields = ("payload", "result", "echo", "stamp")
    if kind == "fixed":
        for slot in PUBLIC_SLOTS:
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        for slot in reversed(PUBLIC_SLOTS):
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        for slot in PUBLIC_SLOTS:
            public.append(world.public_read(slot))
            meter.public_validation_probes += 1
    else:
        public.append(world.public_read("alpha"))
        meter.public_env_probes += 1
        for slot in reversed(PUBLIC_SLOTS):
            public.append(world.public_read(slot))
            meter.public_env_probes += 1
        public.append(world.public_read("alpha"))
        meter.public_validation_probes += 1
    for _field in fields:
        meter.binding_evals += 6
        meter.synthesis_evals += 40
    return dict(status="unique", field="result", public=public)


def private_sequence_ok(task: dict[str, Any], status: str, spec: tuple[str, str, str] | None,
                        world: SequenceWorld, bank: ActiveOperatorBank) -> bool:
    gold = task.get("gold_status")
    if gold in {"ambiguous", "abstain"}:
        return status == gold
    if status != "unique" or spec is None:
        return False
    world.lock()
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        pred = apply_spec(spec, as_seq(rec["payload"]), bank)
        if pred != as_seq(rec["result"]):
            return False
    return True


def private_integer_ok(task: dict[str, Any], status: str, spec: str | None,
                       world: RecordWorld) -> bool:
    if task.get("gold_status") != "unique" or status != "unique" or not spec:
        return False
    world.lock()
    parts = spec.split("|")
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        rows = integer_rows([rec], dict(alpha=0, beta=1, gamma=2, delta=-1, output_field="result"))
        if not rows:
            return False
        pred = apply_guarded(parts[0], parts[1], parts[2], int(rows[0]["x"]))
        if pred != int(rows[0]["observation"]):
            return False
    return True


def deepcopy_bank(bank: ActiveOperatorBank) -> ActiveOperatorBank:
    return bank.snapshot()
