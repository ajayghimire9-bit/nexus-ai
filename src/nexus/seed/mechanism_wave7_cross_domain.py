"""Wave-7 cross-domain analogy and self-evolving operators."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .correspondence_env import RecordWorld
from .cross_domain_analogy import (
    ActiveOperatorBank, FactoredInterfaceMapper, RelationalAnalogyEngine,
    SequenceWorld, Wave7Meter, all_specs, coupled_integer_admit,
    coupled_interface, distill_domain_a_schemas, field_pairs,
    factored_integer_admit, private_integer_ok, private_sequence_ok,
    spec_fits, synthesize_integer, synthesize_sequence, try_concrete_clauses,
)
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave4_diagnostic import OPENED_IDS as W4_OPENED
from .mechanism_wave5_prior_transfer import OPENED_IDS as W5_OPENED
from .mechanism_wave6_correspondence import OPENED_IDS as W6_OPENED
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave7_cross_domain_analogy"
PRIOR_CLOSED = (
    "f2e8942", "6e0df3a", "0d4596e", "c8bc5ad", "25cd50e", "f66ae34",
    "d2c0105", "10f579d", "aa34924", "b590ca2",
)
OPENED_IDS = set(W4_OPENED) | set(W5_OPENED) | set(W6_OPENED) | {
    "w6c_stamp_even", "w6c_stamp_abs", "w6c_echo_odd", "w6c_echo_even",
    "w6c_amb_alias", "w6c_amb_twin", "w6c_oog_sum", "w6c_ret_even",
}
COUPLED_RANDOM = "coupled_random_disambiguation_scratch"
COUPLED_FIXED = "coupled_strong_fixed_scratch"
FACTORED_SCRATCH = "factored_interface_scratch"
CONCRETE = "factored_concrete_clauses_only"
SHUFFLED = "factored_shuffled_analogy_prior"
ANALOGY = "factored_relational_analogy_static_bank"
NEXUS = "factored_self_evolving_relational_nexus"
METHODS = (COUPLED_RANDOM, COUPLED_FIXED, FACTORED_SCRATCH, CONCRETE, SHUFFLED, ANALOGY, NEXUS)
G1 = "w7_analogous"
G2 = "w7_lookalike"
G3 = "w7_invent"
G4_AMB = "w7_ambiguous"
G4_OOG = "w7_oog"
RETAIN = "w7_retain_a"

WAVE7_TASKS = (
    dict(task_id="w7b_ana_even_append", split=G1, domain="B", w7_group="g1",
         mechanism="seq_even_append", instance_seed=1201, gold_status="unique",
         gold_field="result", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q", "r", "s")},
         record_mode="stamp_trap"),
    dict(task_id="w7b_ana_odd_dup", split=G1, domain="B", w7_group="g1",
         mechanism="seq_odd_dup", instance_seed=1202, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": ("q",), "delta": ("p", "q", "r")},
         record_mode="stamp_trap"),
    dict(task_id="w7b_look_len02", split=G2, domain="B", w7_group="g2",
         mechanism="seq_len02_append", instance_seed=1211, gold_status="unique",
         gold_field="result", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q", "r", "s")},
         record_mode="stamp_trap"),
    dict(task_id="w7b_look_len1", split=G2, domain="B", w7_group="g2",
         mechanism="seq_len1_dup", instance_seed=1212, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": ("q",), "delta": ("p", "q", "r")},
         record_mode="stamp_trap"),
    dict(task_id="w7b_inv_palindrome", split=G3, domain="B", w7_group="g3",
         mechanism="seq_palindrome_hash", instance_seed=1221, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": (), "delta": ("a", "b", "a")},
         record_mode="stamp_trap", invents="palindrome_pred"),
    dict(task_id="w7b_reuse_palindrome", split=G3, domain="B", w7_group="g3",
         mechanism="seq_palindrome_q", instance_seed=1222, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": (), "delta": ("a", "b", "a")},
         record_mode="stamp_trap", reuses="palindrome_pred"),
    dict(task_id="w7b_amb_alias", split=G4_AMB, domain="B", w7_group="g4",
         mechanism="seq_even_append", instance_seed=1231, gold_status="ambiguous",
         gold_field="ambiguous", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
         record_mode="alias_ambiguous"),
    dict(task_id="w7b_oog_caesar", split=G4_OOG, domain="B", w7_group="g4",
         mechanism="seq_caesar", instance_seed=1232, gold_status="abstain",
         gold_field=None, epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
         record_mode="stamp_trap", unknown_kind="oog"),
    dict(task_id="w7a_ret_even", split=RETAIN, domain="A", w7_group="retain",
         mechanism="oob_even_add2", instance_seed=1241, gold_status="unique",
         gold_field="result", record_mode="stamp_trap", retain_wave="wave2"),
)


def uses_factored(method: str) -> bool:
    return method not in {COUPLED_RANDOM, COUPLED_FIXED}


def uses_analogy(method: str) -> bool:
    return method in {SHUFFLED, ANALOGY, NEXUS}


def uses_concrete(method: str) -> bool:
    return method == CONCRETE


def uses_evolve(method: str) -> bool:
    return method == NEXUS


def mapping_correct(task: dict[str, Any], status: str, field: str | None) -> bool:
    gold = task.get("gold_status")
    if gold == "ambiguous":
        return status == "ambiguous"
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain"
    return status == "unique" and field == task.get("gold_field")


def false_analogy_lock(task: dict[str, Any], spec: tuple[str, str, str] | None, status: str) -> bool:
    if task.get("split") != G2 or status != "unique" or spec is None:
        return False
    if task["mechanism"] == "seq_len02_append":
        return spec[0] == "len_even"
    if task["mechanism"] == "seq_len1_dup":
        return spec[0] == "len_odd"
    return False


def run_domain_b(task: dict[str, Any], method: str, bank: ActiveOperatorBank,
                 schemas: list[Any]) -> dict[str, Any]:
    meter = Wave7Meter()
    world = SequenceWorld(
        task["mechanism"], int(task["instance_seed"]), str(task.get("record_mode") or "stamp_trap"),
        tuple(task["epsilon"]), dict(task["private"]),
    )
    trace = []
    if uses_factored(method):
        admitted = FactoredInterfaceMapper().admit(world, meter)
        fields_tried = ("result",)
    else:
        admitted = coupled_interface(world, meter, "fixed" if method == COUPLED_FIXED else "random")
        fields_tried = admitted.get("fields") or ("payload", "result", "echo", "stamp", "tick")
    status = str(admitted["status"])
    field = admitted.get("field")
    public = list(admitted["public"])
    spec = None
    invented = None
    concrete_hits = 0
    for rec in public:
        trace.append(dict(phase="public", kind="read", slot=rec.get("slot"), before_lock=True))
    if status == "unique" and field:
        pairs = field_pairs(public, str(field))
        confirm_rec = admitted.get("validation") or public[-1]
        confirm = None
        if confirm_rec and field in confirm_rec:
            confirm = (tuple(confirm_rec["payload"]), tuple(confirm_rec[field]) if not isinstance(confirm_rec[field], int) else None)
            if confirm[1] is None:
                confirm = None
        if uses_concrete(method):
            concrete_hits = try_concrete_clauses(pairs, meter)
        if not uses_factored(method):
            waste_bank = ActiveOperatorBank()
            for waste_field in fields_tried:
                if waste_field == field:
                    continue
                waste_pairs = field_pairs(public, str(waste_field))
                if not waste_pairs:
                    meter.synthesis_evals += len(all_specs(waste_bank))
                    continue
                for spec_row in all_specs(waste_bank):
                    meter.synthesis_evals += 1
                    spec_fits(spec_row, waste_pairs, waste_bank)
        prioritized = None
        if uses_analogy(method):
            engine = RelationalAnalogyEngine(schemas, shuffled=method == SHUFFLED)
            prioritized = engine.prioritized_specs(bank, meter)
        allow_micro = task.get("split") in {G3, G4_OOG}
        syn = synthesize_sequence(
            pairs, confirm, bank, meter, prioritized,
            allow_micro=allow_micro, evolve=uses_evolve(method),
        )
        if syn["status"] != "unique":
            status = str(syn["status"])
            field = None if status != "unique" else field
        spec = syn.get("spec")
        invented = syn.get("invented")
    elif status == "unique":
        status = "abstain"
        field = None
    world.lock()
    private_ok = private_sequence_ok(task, status, spec, world, bank)
    private_before_lock = bool(world.private_opened and not world.locked)
    if world.private_opened:
        for slot in ("alpha", "beta", "gamma", "delta"):
            trace.append(dict(phase="private", kind="private_eval", slot=slot, before_lock=False))
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], split=task["split"], domain="B", w7_group=task.get("w7_group"),
        mechanism=task["mechanism"], method=method, gold_status=task.get("gold_status"),
        status=status, admitted_field=field, spec=spec, invented=invented,
        mapping_correct=mapping_correct(task, status, field),
        private_correct=bool(private_ok),
        false_analogy_lock=false_analogy_lock(task, spec, status),
        false_unique=bool(task.get("gold_status") == "ambiguous" and status == "unique"),
        concrete_hits=int(concrete_hits),
        unverified_operators=int(bank.unverified_admitted),
        evolved=list(bank.evolved),
        private_before_lock=private_before_lock, locked=world.locked,
        trace=trace, **work,
    )


def run_domain_a(task: dict[str, Any], method: str) -> dict[str, Any]:
    meter = Wave7Meter()
    world = RecordWorld(task["mechanism"], int(task["instance_seed"]), str(task.get("record_mode") or "stamp_trap"))
    if uses_factored(method):
        admitted = factored_integer_admit(world, meter)
    else:
        admitted = coupled_integer_admit(world, meter, "fixed" if method == COUPLED_FIXED else "random")
    status = str(admitted["status"])
    field = admitted.get("field")
    spec = None
    if status == "unique" and field == "result":
        spec = synthesize_integer(admitted["public"], meter)
        if spec is None:
            status = "abstain"
            field = None
    world.lock()
    private_ok = private_integer_ok(task, status, spec, world)
    private_before_lock = bool(world.private_opened and not world.locked)
    trace = [dict(phase="public", kind="read", slot="alpha", before_lock=True)]
    if world.private_opened:
        trace.append(dict(phase="private", kind="private_eval", slot="alpha", before_lock=False))
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], split=task["split"], domain="A", w7_group=task.get("w7_group"),
        mechanism=task["mechanism"], method=method, gold_status=task.get("gold_status"),
        status=status, admitted_field=field, spec=spec, invented=None,
        mapping_correct=mapping_correct(task, status, field),
        private_correct=bool(private_ok),
        false_analogy_lock=False, false_unique=False, concrete_hits=0,
        unverified_operators=0, evolved=[],
        private_before_lock=private_before_lock, locked=world.locked,
        trace=trace, **work,
    )


def run_episode(task: dict[str, Any], method: str, bank: ActiveOperatorBank,
                schemas: list[Any]) -> dict[str, Any]:
    if task["domain"] == "A":
        return run_domain_a(task, method)
    return run_domain_b(task, method, bank, schemas)


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(r.get("mapping_correct"))) for r in subset),
            private_correct=sum(int(bool(r.get("private_correct"))) for r in subset),
            false_analogy_lock=sum(int(bool(r.get("false_analogy_lock"))) for r in subset),
            false_unique=sum(int(bool(r.get("false_unique"))) for r in subset),
            ambiguous=sum(int(r.get("status") == "ambiguous") for r in subset),
            abstain=sum(int(r.get("status") == "abstain") for r in subset),
            concrete_hits=sum(int(r.get("concrete_hits") or 0) for r in subset),
            unverified_operators=sum(int(r.get("unverified_operators") or 0) for r in subset),
            public_env_probes=sum(int(r.get("public_env_probes") or 0) for r in subset),
            synthesis_evals=sum(int(r.get("synthesis_evals") or 0) for r in subset),
            micro_codegen_evals=sum(int(r.get("micro_codegen_evals") or 0) for r in subset),
            codegen_plus_synthesis=sum(int(r.get("codegen_plus_synthesis") or 0) for r in subset),
            total_work=sum(int(r.get("total_work") or 0) for r in subset),
        )
    return out


def evaluate_gates(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    rows = list(payload.get("assessment") or [])
    if any(row.get("private_before_lock") for row in rows):
        ok = False
        notes.append("private_before_lock")
    if any(int(row.get("concrete_hits") or 0) for row in rows if row.get("domain") == "B"):
        ok = False
        notes.append("concrete_reuse")
    if any(int(row.get("unverified_operators") or 0) for row in rows):
        ok = False
        notes.append("polluted_bank")
    for seed in TRAIN_SEEDS:
        seed_rows = [row for row in rows if int(row.get("source_seed")) == seed]
        look = [row for row in seed_rows if row.get("split") == G2]
        if any(row.get("false_analogy_lock") for row in look):
            ok = False
            notes.append("false_analogy_{0}".format(seed))
        amb = [row for row in seed_rows if row.get("split") == G4_AMB]
        if amb and any(not row.get("mapping_correct") or row.get("false_unique") for row in amb):
            ok = False
            notes.append("amb_{0}".format(seed))
        oog = [row for row in seed_rows if row.get("split") == G4_OOG]
        if oog and any(row.get("status") != "abstain" for row in oog):
            ok = False
            notes.append("oog_{0}".format(seed))
        retain = [row for row in seed_rows if row.get("split") == RETAIN]
        if retain and any(not row.get("private_correct") for row in retain):
            ok = False
            notes.append("retain_{0}".format(seed))
        factored = [row for row in seed_rows if row["method"] == FACTORED_SCRATCH]
        for name in (COUPLED_RANDOM, COUPLED_FIXED):
            other = [row for row in seed_rows if row["method"] == name]
            if sum(int(r["total_work"]) for r in factored) >= sum(int(r["total_work"]) for r in other):
                ok = False
                notes.append("gate2_{0}_{1}".format(name, seed))
        g12 = [row for row in seed_rows if row.get("split") in {G1, G2}]
        for winner in (ANALOGY, NEXUS):
            win = [row for row in g12 if row["method"] == winner]
            for name in (FACTORED_SCRATCH, CONCRETE, SHUFFLED):
                other = [row for row in g12 if row["method"] == name]
                if sum(int(r["total_work"]) for r in win) >= sum(int(r["total_work"]) for r in other):
                    ok = False
                    notes.append("gate3_{0}_{1}_{2}".format(winner, name, seed))
        g3 = [row for row in seed_rows if row.get("split") == G3]
        port = [row for row in seed_rows if row.get("split") in {G1, G2, G3}]
        nexus = [row for row in g3 if row["method"] == NEXUS]
        static = [row for row in g3 if row["method"] == ANALOGY]
        if sum(int(r["total_work"]) for r in nexus) >= sum(int(r["total_work"]) for r in static):
            ok = False
            notes.append("gate4_g3_total_{0}".format(seed))
        if sum(int(r["codegen_plus_synthesis"]) for r in nexus) >= sum(int(r["codegen_plus_synthesis"]) for r in static):
            ok = False
            notes.append("gate4_g3_code_{0}".format(seed))
        nexus_p = [row for row in port if row["method"] == NEXUS]
        static_p = [row for row in port if row["method"] == ANALOGY]
        if sum(int(r["total_work"]) for r in nexus_p) >= sum(int(r["total_work"]) for r in static_p):
            ok = False
            notes.append("gate4_port_total_{0}".format(seed))
        if sum(int(r["codegen_plus_synthesis"]) for r in nexus_p) >= sum(int(r["codegen_plus_synthesis"]) for r in static_p):
            ok = False
            notes.append("gate4_port_code_{0}".format(seed))
    return dict(
        gate1_isolation_and_safety=all(
            token not in "".join(notes)
            for token in ("private", "concrete", "polluted", "false_analogy", "amb_", "oog_", "retain_")
        ),
        gate2_factored_beats_coupled=all("gate2" not in note for note in notes),
        gate3_analogy_beats_controls=all("gate3" not in note for note in notes),
        gate4_evolution_beats_static=all("gate4" not in note for note in notes),
        passed=ok,
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"), task_id=row["task_id"], split=row["split"],
            domain=row.get("domain"), method=row["method"], status=row.get("status"),
            mapping_correct=bool(row.get("mapping_correct")),
            private_correct=bool(row.get("private_correct")),
            false_analogy_lock=bool(row.get("false_analogy_lock")),
            concrete_hits=int(row.get("concrete_hits") or 0),
            micro_codegen_evals=int(row.get("micro_codegen_evals") or 0),
            synthesis_evals=int(row.get("synthesis_evals") or 0),
            codegen_plus_synthesis=int(row.get("codegen_plus_synthesis") or 0),
            total_work=int(row.get("total_work") or 0),
            admitted_field=row.get("admitted_field"),
        )
        for row in rows
    ]


def run_wave7(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tasks = [dict(row) for row in WAVE7_TASKS]
    if any(row["task_id"] in OPENED_IDS for row in tasks):
        raise ValueError("opened_id_in_challenge")
    assessment = []
    seed_blocks = []
    for seed in TRAIN_SEEDS:
        rows = []
        for method in METHODS:
            bank = ActiveOperatorBank()
            schemas = []
            distill_left = 0
            if uses_analogy(method):
                extra = Wave7Meter()
                schemas = distill_domain_a_schemas(extra)
                distill_left = extra.schema_distill_cost
            for task in tasks:
                episode_bank = bank if uses_evolve(method) else ActiveOperatorBank()
                episode = run_episode(task, method, episode_bank if task["domain"] == "B" else bank, schemas)
                if distill_left:
                    episode["schema_distill_cost"] = int(episode.get("schema_distill_cost") or 0) + distill_left
                    episode["total_work"] = int(episode["total_work"]) + distill_left
                    distill_left = 0
                if uses_evolve(method) and task["domain"] == "B":
                    bank = episode_bank
                episode["source_seed"] = seed
                rows.append(episode)
        assessment.extend(rows)
        seed_blocks.append(dict(
            seed=seed,
            g1=_totals([r for r in rows if r["split"] == G1]),
            g2=_totals([r for r in rows if r["split"] == G2]),
            g12=_totals([r for r in rows if r["split"] in {G1, G2}]),
            g3=_totals([r for r in rows if r["split"] == G3]),
            port=_totals([r for r in rows if r["split"] in {G1, G2, G3}]),
            amb=_totals([r for r in rows if r["split"] == G4_AMB]),
            oog=_totals([r for r in rows if r["split"] == G4_OOG]),
            retain=_totals([r for r in rows if r["split"] == RETAIN]),
            suite=_totals(rows),
        ))
    totals = dict(
        g1=_totals([r for r in assessment if r["split"] == G1]),
        g2=_totals([r for r in assessment if r["split"] == G2]),
        g12=_totals([r for r in assessment if r["split"] in {G1, G2}]),
        g3=_totals([r for r in assessment if r["split"] == G3]),
        port=_totals([r for r in assessment if r["split"] in {G1, G2, G3}]),
        amb=_totals([r for r in assessment if r["split"] == G4_AMB]),
        oog=_totals([r for r in assessment if r["split"] == G4_OOG]),
        retain=_totals([r for r in assessment if r["split"] == RETAIN]),
        suite=_totals(assessment),
    )
    payload = dict(
        kind=KIND, prior_closed=list(PRIOR_CLOSED), confirmation=False,
        learning_to_learn_established=False, track_b_closed=True,
        grammar_prior_retrained=False, methods=list(METHODS),
        seeds=list(TRAIN_SEEDS), assessment=assessment, seed_blocks=seed_blocks,
        per_task=per_task_rows(assessment), totals=totals, gates={},
        usage=dict(
            kind=KIND, elapsed_s=0, model_calls=0, metal_used=False,
            frozen_debit_s=0, research_cpu_ledger_debit_s=0,
            ledger_class="symbolic_standing_grant_cpu_not_frozen_1p5b",
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            wall_time_s=0, rss=sample_process_memory(),
        ),
        language_hash=language_hash(),
    )
    payload["gates"] = evaluate_gates(payload)
    elapsed = time.perf_counter() - started
    payload["usage"]["elapsed_s"] = elapsed
    payload["usage"]["wall_time_s"] = elapsed
    payload["hash"] = digest({key: payload[key] for key in ("kind", "assessment", "totals", "gates")})
    (directory / "seed_wave7_cross_domain_analogy.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8",
    )
    return payload


COST_KEYS = (
    "public_env_probes", "public_validation_probes", "channel_invariance_evals",
    "binding_evals", "role_probe_cost", "schema_distill_cost", "retrieval_evals",
    "synthesis_evals", "micro_codegen_evals", "operator_compile_cost",
)


def reconstruct_episode(row: dict[str, Any]) -> dict[str, Any]:
    for step in row.get("trace") or []:
        if step.get("phase") == "private" and step.get("before_lock"):
            return dict(total_work=-1, private_before_lock=True)
    work = sum(int(row.get(key) or 0) for key in COST_KEYS)
    return dict(total_work=work, private_before_lock=bool(row.get("private_before_lock")))


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    if payload.get("grammar_prior_retrained"):
        ok = False
        notes.append("prior_retrained")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("overclaim")
    rows = list(payload.get("assessment") or [])
    if any(row["task_id"] in OPENED_IDS for row in rows):
        ok = False
        notes.append("rescored_opened")
    for row in rows:
        rec = reconstruct_episode(row)
        if rec.get("private_before_lock") or rec.get("total_work") != row.get("total_work"):
            ok = False
            notes.append("reconstruct:" + row["task_id"] + ":" + row["method"])
            break
    rebuilt = _totals(rows)
    saved = (payload.get("totals") or {}).get("suite") or {}
    for name, cell in rebuilt.items():
        if cell.get("total_work") != (saved.get(name) or {}).get("total_work"):
            ok = False
            notes.append("column:" + name)
    gates = evaluate_gates(payload)
    if gates.get("passed") != (payload.get("gates") or {}).get("passed"):
        ok = False
        notes.append("gates_mismatch")
    if not (payload.get("gates") or {}).get("passed"):
        ok = False
        notes.append("gates_failed")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)
