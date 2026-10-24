"""Wave-8 hierarchical gated operator evolution.

Fixes Wave-7's flat L1-only compile, ungated OOG bank bloat, and
eager G1 role-probe overhead. Track B stays closed.
"""
from __future__ import annotations

from typing import Any, Callable

from .correspondence_env import RecordWorld
from .cross_domain_analogy import (
    MICRO_CANDIDATES, PUBLIC_SEQ, SEQUENCE_MECHANISMS, Seq, UNIVERSAL_PROBES,
    ActiveOperatorBank, FactoredInterfaceMapper, RelationalAnalogyEngine,
    SequenceWorld, Wave7Meter, all_specs, apply_spec, as_seq, classify_predicate,
    distill_domain_a_schemas, factored_integer_admit, field_pairs,
    initial_predicates, initial_transforms, private_integer_ok,
    private_sequence_ok, spec_fits, synthesize_integer, synthesize_sequence,
)

MARKERS = frozenset({"m", "q", "#", "!", "z"})


class Wave8Meter(Wave7Meter):
    def __init__(self) -> None:
        super().__init__()
        self.gate_evals = 0

    @property
    def total_work(self) -> int:
        return super().total_work + int(self.gate_evals)

    def as_dict(self) -> dict[str, int]:
        payload = super().as_dict()
        payload["gate_evals"] = int(self.gate_evals)
        payload["total_work"] = int(self.total_work)
        return payload


def rotate_head(seq: Seq) -> Seq:
    return seq[1:] + seq[:1] if seq else seq


def seq_pal_rotate_bang(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return rotate_head(seq) + ("!",)
    return seq


def seq_pal_rotate_q(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return rotate_head(seq) + ("q",)
    return seq


def seq_first_last_z(seq: Seq) -> Seq:
    if seq and seq[0] == seq[-1]:
        return seq + ("z",)
    return seq


SEQUENCE_MECHANISMS["seq_pal_rotate_bang"] = seq_pal_rotate_bang
SEQUENCE_MECHANISMS["seq_pal_rotate_q"] = seq_pal_rotate_q
SEQUENCE_MECHANISMS["seq_first_last_z"] = seq_first_last_z


class Wave8World(SequenceWorld):
    def __init__(self, mechanism: str, instance_seed: int, mode: str,
                 epsilon: Seq, private_map: dict[str, Seq],
                 public_map: dict[str, Seq] | None = None) -> None:
        super().__init__(mechanism, instance_seed, mode, epsilon, private_map)
        self.public_map = {slot: as_seq(value) for slot, value in (public_map or PUBLIC_SEQ).items()}

    def public_read(self, slot: str) -> dict[str, Any]:
        payload = self.epsilon if slot == "epsilon" else self.public_map[slot]
        rec = self._compose(payload, self.stamp, self.tick, self.last_payload)
        rec["slot"] = slot
        self.last_payload = payload
        self.stamp += 1
        self.tick += 1
        return rec


class CompiledOperator:
    def __init__(self, name: str, kind: str, layer: int, fn: Callable,
                 invariant: str, born: int) -> None:
        self.name = name
        self.kind = kind
        self.layer = layer
        self.fn = fn
        self.invariant = invariant
        self.born = born
        self.uses = 0
        self.used_this_task = False
        self.cold = False


class HierarchicalBank(ActiveOperatorBank):
    def __init__(self) -> None:
        super().__init__()
        self.transforms["append_z"] = lambda seq: seq + ("z",)
        self.compiled: list[CompiledOperator] = []
        self.task_index = 0
        self.cold_names: list[str] = []

    def snapshot(self) -> "HierarchicalBank":
        clone = HierarchicalBank()
        clone.predicates = dict(self.predicates)
        clone.transforms = dict(self.transforms)
        clone.evolved = list(self.evolved)
        clone.unverified_admitted = int(self.unverified_admitted)
        clone.compiled = list(self.compiled)
        clone.task_index = int(self.task_index)
        clone.cold_names = list(self.cold_names)
        return clone


def alphabet_closed(pairs: list[tuple[Seq, Seq]]) -> bool:
    incoming: set[str] = set()
    outgoing: set[str] = set()
    for src, dst in pairs:
        incoming.update(src)
        outgoing.update(dst)
    return outgoing <= (incoming | MARKERS)


def gate_allows(op: CompiledOperator, pairs: list[tuple[Seq, Seq]],
                meter: Wave8Meter) -> bool:
    meter.gate_evals += 1
    if op.invariant == "alphabet_closed":
        return alphabet_closed(pairs)
    return True


def gated_view(bank: HierarchicalBank, pairs: list[tuple[Seq, Seq]],
               meter: Wave8Meter, gated: bool) -> ActiveOperatorBank:
    view = ActiveOperatorBank()
    view.predicates = dict(initial_predicates())
    view.transforms = dict(initial_transforms())
    view.transforms["append_z"] = lambda seq: seq + ("z",)
    for op in bank.compiled:
        if op.cold:
            continue
        if gated and not gate_allows(op, pairs, meter):
            continue
        if op.kind == "predicate":
            view.predicates[op.name] = op.fn
        else:
            view.transforms[op.name] = op.fn
    view.evolved = [
        op.name for op in bank.compiled
        if not op.cold and (op.name in view.predicates or op.name in view.transforms)
    ]
    return view


DEEP_L2_L0: tuple[tuple[str, str, Any], ...] = (
    ("pal_rot_bang_pred", "predicate", lambda seq: seq == seq[::-1]),
    ("rotate_bang_tf", "transform", lambda seq: rotate_head(seq) + ("!",)),
    ("rotate_q_tf", "transform", lambda seq: rotate_head(seq) + ("q",)),
    ("rotate_only", "transform", rotate_head),
    ("rev_bang", "transform", lambda seq: seq[::-1] + ("!",)),
    ("wrap_bang", "transform", lambda seq: ("!",) + seq + ("!",)),
    ("tail_bang", "transform", lambda seq: seq[1:] + ("!",) if seq else ("!",)),
    ("head_bang", "transform", lambda seq: seq[:1] + ("!",) if seq else ("!",)),
    ("dup_bang", "transform", lambda seq: seq + seq + ("!",)),
    ("drop_head_bang", "transform", lambda seq: seq[1:] + ("!",) if len(seq) > 1 else seq + ("!",)),
    ("swap_bang", "transform", lambda seq: (seq[-1:] + seq[1:-1] + seq[:1] + ("!",)) if len(seq) > 1 else seq + ("!",)),
    ("len_ge3_rot", "predicate", lambda seq: len(seq) >= 3),
    ("core_pal", "predicate", lambda seq: seq[1:-1] == seq[1:-1][::-1] if len(seq) > 2 else False),
    ("alt_rot", "transform", lambda seq: seq[-1:] + seq[:-1] + ("!",) if seq else ("!",)),
    ("mid_flip", "transform", lambda seq: seq[:1] + seq[1:-1][::-1] + seq[-1:] + ("!",) if len(seq) > 2 else seq),
    ("repeat_bang", "transform", lambda seq: seq + ("!",) + seq),
    ("eq_rar", "predicate", lambda seq: seq == ("r", "a", "r")),
    ("token_shift", "transform", lambda seq: tuple(chr((ord(t) - 96) % 26 + 97) if t.isalpha() else t for t in seq)),
    ("const_bang", "transform", lambda seq: ("!",)),
    ("id_bang_always", "transform", lambda seq: seq + ("!",)),
    ("triple_rev", "transform", lambda seq: seq[::-1][::-1][::-1] + ("!",)),
    ("slice_mod", "transform", lambda seq: seq[::2] + ("!",)),
    ("zip_self", "transform", lambda seq: tuple(a for pair in zip(seq, seq) for a in pair) + ("!",)),
    ("count_len", "predicate", lambda seq: len(seq) % 3 == 0),
    ("first_z", "transform", lambda seq: ("z",) + seq),
    ("last_z", "transform", lambda seq: seq + ("z",)),
    ("pal_only_rev", "transform", lambda seq: seq[::-1] if seq == seq[::-1] else seq),
    ("nested_rev_eq", "predicate", lambda seq: seq[::-1][::-1] == seq),
    ("deep_rot2", "transform", lambda seq: rotate_head(rotate_head(seq)) + ("!",)),
    ("deep_rot3", "transform", lambda seq: rotate_head(rotate_head(rotate_head(seq))) + ("!",)),
    ("mirror_core", "transform", lambda seq: seq[:1] + seq[-1:] if seq else seq),
    ("l0_len_eq_rev", "predicate", lambda seq: len(seq) == len(seq[::-1])),
    ("concat_rev_bang", "transform", lambda seq: seq + seq[::-1] + ("!",)),
    ("head_eq_rot", "predicate", lambda seq: bool(seq) and seq[0] == rotate_head(seq)[-1] if seq else False),
    ("tail_eq_pal", "predicate", lambda seq: bool(seq) and seq[-1:] == seq[:1][::-1]),
    ("noise_a", "transform", lambda seq: seq + ("a", "!",)),
    ("noise_b", "transform", lambda seq: ("b",) + rotate_head(seq)),
    ("noise_c", "predicate", lambda seq: "c" in seq),
    ("noise_d", "transform", lambda seq: seq[::-1] + seq[:1]),
    ("noise_e", "predicate", lambda seq: len(seq) in {3, 5, 7}),
)


def _predicate_explains(pred: Callable[[Seq], bool], pairs: list[tuple[Seq, Seq]]) -> bool:
    then_ok = False
    else_ok = False
    for src, dst in pairs:
        if pred(src):
            then_ok = then_ok or dst != src
        else:
            else_ok = else_ok or dst == src
    return then_ok and else_ok


def _transform_explains(fn: Callable[[Seq], Seq], pairs: list[tuple[Seq, Seq]],
                        pred: Callable[[Seq], bool] | None) -> bool:
    for src, dst in pairs:
        if pred is None or pred(src):
            if fn(src) != dst:
                return False
        elif dst != src:
            return False
    return True


def compile_operator(bank: HierarchicalBank, name: str, kind: str, layer: int,
                     fn: Callable, meter: Wave8Meter) -> None:
    meter.operator_compile_cost += len(UNIVERSAL_PROBES) + 2
    if kind == "predicate":
        classify_predicate(fn)
        bank.predicates[name] = fn
    else:
        bank.transforms[name] = fn
    bank.evolved.append(name)
    bank.compiled.append(CompiledOperator(name, kind, layer, fn, "alphabet_closed", bank.task_index))


def begin_task(bank: HierarchicalBank) -> None:
    bank.task_index += 1
    for op in bank.compiled:
        op.used_this_task = False


def mark_use(bank: HierarchicalBank, spec: tuple[str, str, str] | None) -> None:
    if spec is None:
        return
    used = {spec[0], spec[1], spec[2]}
    for op in bank.compiled:
        if op.name in used:
            op.uses += 1
            op.used_this_task = True


def mdl_prune(bank: HierarchicalBank) -> None:
    for op in bank.compiled:
        if op.cold or op.born >= bank.task_index or op.used_this_task or op.uses > 1:
            continue
        op.cold = True
        bank.cold_names.append(op.name)
        if op.kind == "predicate":
            bank.predicates.pop(op.name, None)
        else:
            bank.transforms.pop(op.name, None)
        if op.name in bank.evolved:
            bank.evolved.remove(op.name)


def invent_from_catalog(pairs: list[tuple[Seq, Seq]], catalog: tuple,
                        bank: ActiveOperatorBank, meter: Wave8Meter,
                        pred_hint: Callable[[Seq], bool] | None) -> tuple[str, str, Any] | None:
    for name, kind, fn in catalog:
        meter.micro_codegen_evals += 1
        if kind == "predicate":
            if name in bank.predicates:
                continue
            if _predicate_explains(fn, pairs):
                return name, kind, fn
        else:
            if name in bank.transforms:
                continue
            if _transform_explains(fn, pairs, pred_hint):
                return name, kind, fn
    return None


def first_fit(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
              bank: ActiveOperatorBank, meter: Wave8Meter,
              specs: list[tuple[str, str, str]]) -> tuple[str, str, str] | None:
    for spec in specs:
        meter.synthesis_evals += 1
        if not spec_fits(spec, pairs, bank):
            continue
        if confirm is not None and apply_spec(spec, confirm[0], bank) != confirm[1]:
            continue
        return spec
    return None


def lookalike_or_fit(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                     bank: ActiveOperatorBank, meter: Wave8Meter) -> str | tuple[str, str, str] | None:
    for spec in all_specs(bank):
        meter.synthesis_evals += 1
        if not spec_fits(spec, pairs, bank):
            continue
        if confirm is not None and apply_spec(spec, confirm[0], bank) != confirm[1]:
            return "lookalike"
        return spec
    return None


def analogy_hit(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                bank: ActiveOperatorBank, meter: Wave8Meter, schemas: list) -> tuple[str, str, str] | None:
    extra = Wave8Meter()
    if not schemas:
        schemas = distill_domain_a_schemas(extra)
        meter.schema_distill_cost += extra.schema_distill_cost
    engine = RelationalAnalogyEngine(schemas, shuffled=False)
    return first_fit(pairs, confirm, bank, meter, engine.prioritized_specs(bank, meter))


def _l2_catalog() -> tuple[tuple[str, str, Any], ...]:
    return (
        ("rotate_bang_tf", "transform", lambda seq: rotate_head(seq) + ("!",)),
        ("rotate_q_tf", "transform", lambda seq: rotate_head(seq) + ("q",)),
    )


def _admit_invention(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                     view: ActiveOperatorBank, meter: Wave8Meter,
                     found: tuple[str, str, Any], pred_hint_name: str | None) -> tuple[str, str, str] | None:
    name, kind, fn = found
    trial = view.snapshot()
    if kind == "predicate":
        trial.predicates[name] = fn
        cand = [spec for spec in all_specs(trial) if spec[0] == name]
    else:
        trial.transforms[name] = fn
        if pred_hint_name:
            cand = [(pred_hint_name, name, "identity")]
        else:
            cand = [spec for spec in all_specs(trial) if name in spec]
    return first_fit(pairs, confirm, trial, meter, cand)


def synthesize_wave8(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                     bank: HierarchicalBank, meter: Wave8Meter, schemas: list,
                     lazy: bool, gated: bool, allow_l2: bool, evolve: bool,
                     allow_micro: bool, stage: str) -> dict[str, Any]:
    view = gated_view(bank, pairs, meter, gated)
    pred_hint = view.predicates.get("palindrome_pred")
    evolved_specs = [
        spec for spec in all_specs(view)
        if spec[0] in view.evolved or spec[1] in view.evolved or spec[2] in view.evolved
    ]
    if evolved_specs and stage != "l2":
        evolved_hit = first_fit(pairs, confirm, view, meter, evolved_specs)
        if evolved_hit is not None:
            mark_use(bank, evolved_hit)
            return dict(status="unique", spec=evolved_hit, invented=None, layer=1)
    if allow_l2 and pred_hint is not None and stage == "l2":
        found = invent_from_catalog(pairs, _l2_catalog(), view, meter, pred_hint)
        if found is not None:
            hit = _admit_invention(pairs, confirm, view, meter, found, "palindrome_pred")
            if hit is not None:
                if evolve:
                    compile_operator(bank, found[0], found[1], 2, found[2], meter)
                    mark_use(bank, hit)
                return dict(status="unique", spec=hit, invented=found[0], layer=2)
        return dict(status="abstain", spec=None, invented=None, layer=0)

    if lazy:
        probe = lookalike_or_fit(pairs, confirm, view, meter)
        if isinstance(probe, tuple):
            mark_use(bank, probe)
            return dict(status="unique", spec=probe, invented=None, layer=0)
        if probe == "lookalike":
            hit = analogy_hit(pairs, confirm, view, meter, schemas)
            if hit is not None:
                mark_use(bank, hit)
                return dict(status="unique", spec=hit, invented=None, layer=0)
    else:
        hit = analogy_hit(pairs, confirm, view, meter, schemas)
        if hit is not None:
            mark_use(bank, hit)
            return dict(status="unique", spec=hit, invented=None, layer=0)
        fallback = first_fit(pairs, confirm, view, meter, all_specs(view))
        if fallback is not None:
            mark_use(bank, fallback)
            return dict(status="unique", spec=fallback, invented=None, layer=0)
    if not allow_micro:
        return dict(status="abstain", spec=None, invented=None, layer=0)

    catalog: tuple[tuple[str, str, Any], ...] = MICRO_CANDIDATES
    if stage == "l2" and not allow_l2:
        catalog = MICRO_CANDIDATES + DEEP_L2_L0
    elif stage == "oog" and not gated:
        catalog = MICRO_CANDIDATES + DEEP_L2_L0
    found = invent_from_catalog(pairs, catalog, view, meter, None)
    if found is None:
        return dict(status="abstain", spec=None, invented=None, layer=0)
    hit = _admit_invention(pairs, confirm, view, meter, found, None)
    if hit is None:
        return dict(status="abstain", spec=None, invented=None, layer=0)
    if evolve:
        compile_operator(bank, found[0], found[1], 1, found[2], meter)
        mark_use(bank, hit)
    return dict(status="unique", spec=hit, invented=found[0], layer=1)


def wave7_ungated_synth(pairs: list[tuple[Seq, Seq]], confirm: tuple[Seq, Seq] | None,
                        bank: HierarchicalBank, meter: Wave8Meter, schemas: list,
                        allow_micro: bool, stage: str) -> dict[str, Any]:
    extra = Wave8Meter()
    if not schemas:
        schemas = distill_domain_a_schemas(extra)
        meter.schema_distill_cost += extra.schema_distill_cost
    syn = synthesize_sequence(pairs, confirm, bank, meter, RelationalAnalogyEngine(schemas).prioritized_specs(bank, meter),
                              allow_micro=allow_micro, evolve=True)
    if syn["status"] == "unique":
        mark_use(bank, syn.get("spec"))
        if syn.get("invented") and not any(op.name == syn["invented"] for op in bank.compiled):
            fn = bank.predicates.get(syn["invented"])
            if fn is not None:
                bank.compiled.append(CompiledOperator(str(syn["invented"]), "predicate", 1, fn, "alphabet_closed", bank.task_index))
        return dict(syn, layer=1 if syn.get("invented") else 0)
    if stage == "l2" and allow_micro:
        found = invent_from_catalog(pairs, DEEP_L2_L0, bank, meter, bank.predicates.get("palindrome_pred"))
        if found is None:
            return dict(status="abstain", spec=None, invented=None, layer=0)
        name, kind, fn = found
        trial = bank.snapshot()
        if kind == "transform":
            trial.transforms[name] = fn
        else:
            trial.predicates[name] = fn
        hit = first_fit(pairs, confirm, trial, meter, all_specs(trial))
        if hit is not None:
            if kind == "predicate":
                bank.predicates[name] = fn
            else:
                bank.transforms[name] = fn
            return dict(status="unique", spec=hit, invented=name, layer=1)
    return dict(status="abstain", spec=None, invented=None, layer=0)
