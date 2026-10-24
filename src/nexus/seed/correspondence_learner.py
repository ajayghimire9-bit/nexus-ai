"""Active correspondence learner. Frozen Wave-5 grammar/clauses only."""
from __future__ import annotations

from typing import Any

from .correspondence_env import (
    BASE_FIELDS, CANDIDATE_SLOT_MAPS, FRESH_SLOT, PUBLIC_SLOTS, RecordWorld,
    candidate_bindings, integer_rows,
)
from .event_record_env import parse_record
from .mechanism_beyond_catalog import apply_leaf, filter_specs
from .mechanism_wave4_diagnostic import residual_exists, grammar_for_guard
from .mechanism_wave5_prior_transfer import populate_clauses
from .mechanism_skills import SubMechanismLibrary

STORED_GUARDS = ("pos", "neg", "even")
PROBE_KINDS = ("repeat", "shuffle", "fresh")
IDENTITY_SLOTS = dict(alpha=0, beta=1, gamma=2, delta=-1)


class Wave6Meter:
    def __init__(self) -> None:
        self.public_env_probes = 0
        self.public_validation_probes = 0
        self.binding_evals = 0
        self.disagreement_policy_evals = 0
        self.retrieval_evals = 0
        self.synthesis_evals = 0

    def as_dict(self) -> dict[str, int]:
        return dict(
            public_env_probes=int(self.public_env_probes),
            public_validation_probes=int(self.public_validation_probes),
            binding_evals=int(self.binding_evals),
            disagreement_policy_evals=int(self.disagreement_policy_evals),
            retrieval_evals=int(self.retrieval_evals),
            synthesis_evals=int(self.synthesis_evals),
            public_probes_plus_bindings=int(self.public_env_probes) + int(self.public_validation_probes) + int(self.binding_evals),
            total_acquisition_work=int(self.total_acquisition_work),
        )

    @property
    def total_acquisition_work(self) -> int:
        return (
            int(self.public_env_probes)
            + int(self.public_validation_probes)
            + int(self.binding_evals)
            + int(self.disagreement_policy_evals)
            + int(self.retrieval_evals)
            + int(self.synthesis_evals)
        )


def fields_for(records: list[dict[str, Any]]) -> tuple[str, ...]:
    found = set(BASE_FIELDS)
    for rec in records:
        found.update(parse_record(rec))
    return tuple(sorted(found))


def is_identity_output(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(int(row["x"]) == int(row["observation"]) for row in rows)


def is_identity_map(binding: dict[str, Any]) -> bool:
    return all(int(binding[slot]) == IDENTITY_SLOTS[slot] for slot in IDENTITY_SLOTS if slot in binding)


def is_counter_output(records: list[dict[str, Any]], binding: dict[str, Any]) -> bool:
    bound = []
    stamp_vals = []
    field = str(binding.get("output_field") or "")
    for rec in records:
        parsed = parse_record(rec)
        if field in parsed and "stamp" in parsed:
            bound.append(int(parsed[field]))
            stamp_vals.append(int(parsed["stamp"]))
    return bool(bound) and bound == stamp_vals


def field_series(records: list[dict[str, Any]], field: str) -> tuple[int, ...]:
    values = []
    for rec in records:
        parsed = parse_record(rec)
        if field in parsed:
            values.append(int(parsed[field]))
    return tuple(values)


def observationally_tied(records: list[dict[str, Any]], fields: set[str]) -> bool:
    if len(fields) < 2:
        return False
    series = [field_series(records, str(field)) for field in fields]
    return bool(series) and bool(series[0]) and len(set(series)) == 1


def functional_fit(rows: list[dict[str, Any]], records: list[dict[str, Any]],
                   binding: dict[str, Any], meter: Wave6Meter | None = None) -> bool:
    if len(rows) < 2:
        return False
    if is_identity_output(rows) or is_counter_output(records, binding):
        return False
    grouped: dict[int, set[int]] = {}
    for row in rows:
        grouped.setdefault(int(row["x"]), set()).add(int(row["observation"]))
    if any(len(values) > 1 for values in grouped.values()):
        return False
    _ = meter
    return any(residual_exists(guard, rows, None) for guard in ("id", "pos", "neg", "even", "abs_ge2"))


def greedy_score(rows: list[dict[str, Any]]) -> tuple[int, int]:
    non_id = sum(1 for row in rows if int(row["x"]) != int(row["observation"]))
    residuals = sum(1 for guard in ("pos", "neg", "even", "abs_ge2") if residual_exists(guard, rows, None))
    return (non_id, residuals)


class CompetingBindingSet:
    def __init__(self, bindings: list[dict[str, Any]]) -> None:
        self.bindings = [dict(row) for row in bindings]

    def filter(self, records: list[dict[str, Any]], meter: Wave6Meter,
               clauses: bool) -> list[dict[str, Any]]:
        kept = []
        pool = list(self.bindings)
        if clauses:
            meter.retrieval_evals += 1
            short = []
            for field in {row.get("output_field") for row in pool}:
                probe = dict(alpha=0, beta=1, gamma=2, delta=-1, output_field=field)
                meter.binding_evals += 1
                rows = integer_rows(records, probe)
                if functional_fit(rows, records, probe, None):
                    if any(residual_exists(guard, rows, None) for guard in STORED_GUARDS):
                        short.append(field)
            if short:
                pool = [row for row in pool if row.get("output_field") in short]
            else:
                self.bindings = []
                return []
        for binding in pool:
            meter.binding_evals += 1
            rows = integer_rows(records, binding)
            if not functional_fit(rows, records, binding, meter):
                continue
            kept.append(binding)
        self.bindings = kept
        return list(kept)


def predict_field(binding: dict[str, Any], record: dict[str, Any]) -> int | None:
    parsed = parse_record(record)
    field = str(binding.get("output_field"))
    if field not in parsed:
        return None
    return int(parsed[field])


def probe_disagreement(surviving: list[dict[str, Any]],
                       imagined: list[dict[str, Any]]) -> int:
    preds = []
    for binding in surviving:
        preds.append(tuple(predict_field(binding, rec) for rec in imagined))
    return len(set(preds))


def select_disambiguating_probe(surviving: list[dict[str, Any]],
                                public: list[dict[str, Any]],
                                world: RecordWorld, meter: Wave6Meter,
                                available: tuple[str, ...]) -> str:
    best = available[0]
    best_score = -1
    for kind in available:
        meter.disagreement_policy_evals += 1
        if kind == "repeat":
            imagined = [dict(slot="alpha", payload=0, result=99, echo=99, stamp=world.stamp + 1)]
            # score by whether stamp field would change vs result
            score = 0
            stamps = {b.get("output_field") for b in surviving}
            if "stamp" in stamps and len(stamps) > 1:
                score = 3
            elif "echo" in stamps and world.mode == "echo_order":
                score = 2
            else:
                score = 1
        elif kind == "shuffle":
            score = 2 if world.mode == "echo_order" else 0
        else:
            score = 1 if len({b.get("output_field") for b in surviving}) > 1 else 0
        if score > best_score:
            best_score = score
            best = kind
    _ = public, imagined if False else None
    return best


def select_validation_slot(surviving: list[dict[str, Any]], public: list[dict[str, Any]],
                           world: RecordWorld, meter: Wave6Meter) -> str:
    best = "beta"
    best_n = -1
    for slot, x in (("alpha", 0), ("beta", 1), ("gamma", 2), ("delta", -1)):
        meter.disagreement_policy_evals += 1
        preds = set()
        prev = next((rec for rec in reversed(public) if rec.get("slot") == slot), None)
        for binding in surviving:
            field = str(binding.get("output_field"))
            if field == "stamp":
                preds.add(("stamp", world.stamp + 1))
            elif field == "payload":
                preds.add(("payload", x))
            elif field == "echo" and world.mode == "echo_order":
                preds.add(("echo", world.last_payload))
            elif prev is not None:
                parsed = parse_record(prev)
                if field in parsed:
                    preds.add((field, int(parsed[field])))
        if len(preds) > best_n:
            best_n = len(preds)
            best = slot
    return best


def run_public_probe(kind: str, world: RecordWorld, meter: Wave6Meter) -> list[dict[str, Any]]:
    rows = []
    if kind == "repeat":
        rec = world.public_read("alpha")
        meter.public_env_probes += 1
        rows.append(rec)
    elif kind == "shuffle":
        for slot in reversed(PUBLIC_SLOTS):
            rec = world.public_read(slot)
            meter.public_env_probes += 1
            rows.append(rec)
    elif kind == "fresh":
        rec = world.public_read(FRESH_SLOT)
        meter.public_validation_probes += 1
        rows.append(rec)
    return rows


def admit_after_validation(surviving: list[dict[str, Any]],
                           validation: dict[str, Any],
                           prior_records: list[dict[str, Any]],
                           meter: Wave6Meter, clauses: bool) -> dict[str, Any]:
    checked = []
    for binding in surviving:
        meter.binding_evals += 1
        rows = integer_rows(prior_records + [validation], binding)
        if not functional_fit(rows, prior_records + [validation], binding, meter):
            continue
        checked.append(binding)
    if len(checked) == 0:
        return dict(status="abstain", binding=None, surviving=checked)
    identities = [row for row in checked if is_identity_map(row)]
    identity_fields = {str(row.get("output_field")) for row in identities}
    records = prior_records + [validation]
    if observationally_tied(records, identity_fields):
        return dict(status="ambiguous", binding=None, surviving=checked)
    preferred = next((row for row in identities if row.get("output_field") == "result"), None)
    if preferred is None:
        return dict(status="abstain", binding=None, surviving=checked)
    return dict(status="unique", binding=preferred, surviving=checked)


def synthesize_spec(rows: list[dict[str, Any]], clauses: bool, meter: Wave6Meter) -> str | None:
    if not rows:
        return None
    guards = STORED_GUARDS if clauses else ("id", "pos", "neg", "even", "abs_ge2")
    for guard in guards:
        if clauses:
            meter.retrieval_evals += 1
        specs = filter_specs(grammar_for_guard(guard), rows, None)
        meter.synthesis_evals += max(len(grammar_for_guard(guard)), 1)
        if len(specs) == 1:
            return "|".join(specs[0])
        if specs:
            return "|".join(specs[0])
    return None


def private_correct(task: dict[str, Any], status: str, binding: dict[str, Any] | None,
                    spec: str | None, world: RecordWorld) -> bool:
    gold = task.get("gold_status")
    if gold == "ambiguous":
        return status == "ambiguous"
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain"
    if status != "unique" or binding is None:
        return False
    if binding.get("output_field") != task.get("gold_field"):
        return False
    if tuple(binding.get(slot) for slot in PUBLIC_SLOTS) != (0, 1, 2, -1):
        return False
    world.lock()
    ok = True
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        rows = integer_rows([rec], binding)
        if not rows:
            ok = False
            break
        if spec:
            parts = spec.split("|")
            from .mechanism_beyond_catalog import apply_guarded
            pred = apply_guarded(parts[0], parts[1], parts[2], int(rows[0]["x"]))
            if pred != int(rows[0]["observation"]):
                ok = False
                break
        elif int(rec["result"]) != int(rows[0]["observation"]):
            ok = False
            break
    return ok


def mapping_correct(task: dict[str, Any], status: str, binding: dict[str, Any] | None) -> bool:
    gold = task.get("gold_status")
    if gold == "ambiguous":
        return status == "ambiguous"
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain"
    if status != "unique" or binding is None:
        return False
    if binding.get("output_field") == "stamp":
        return False
    return (
        binding.get("output_field") == task.get("gold_field")
        and tuple(binding.get(slot) for slot in PUBLIC_SLOTS) == (0, 1, 2, -1)
    )
