"""Wave-6 correspondence disambiguation. Wave-5 grammar stays frozen."""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .correspondence_env import (
    FRESH_SLOT, PUBLIC_SLOTS, RecordWorld, candidate_bindings, fields_for,
    integer_rows,
)
from .correspondence_learner import (
    CompetingBindingSet, Wave6Meter, admit_after_validation, greedy_score,
    mapping_correct, private_correct, run_public_probe, select_disambiguating_probe,
    select_validation_slot, synthesize_spec,
)
from .event_record_env import parse_record
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_wave4_diagnostic import OPENED_IDS as W4_OPENED
from .mechanism_wave5_prior_transfer import OPENED_IDS as W5_OPENED, populate_clauses
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave6_correspondence_disambiguation"
PRIOR_CLOSED = (
    "f2e8942", "6e0df3a", "0d4596e", "c8bc5ad", "25cd50e", "f66ae34",
    "d2c0105", "10f579d",
)
OPENED_IDS = set(W4_OPENED) | set(W5_OPENED)
GREEDY = "greedy_first_fit_mapper"
RANDOM = "random_disambiguation_mapper"
FIXED = "strong_fixed_mapping_solver"
SCRATCH = "active_disambiguation_mapper_scratch"
CLAUSES = "active_disambiguation_mapper_plus_clauses"
METHODS = (GREEDY, RANDOM, FIXED, SCRATCH, CLAUSES)
IDENTIFIABLE = ("w6_stamp", "w6_echo")


def uses_clauses(method: str) -> bool:
    return method == CLAUSES


def initial_reads(world: RecordWorld, meter: Wave6Meter) -> list[dict[str, Any]]:
    rows = []
    for slot in PUBLIC_SLOTS:
        rec = world.public_read(slot)
        meter.public_env_probes += 1
        rows.append(rec)
    return rows


def run_episode(task: dict[str, Any], method: str, rng: random.Random) -> dict[str, Any]:
    meter = Wave6Meter()
    world = RecordWorld(task["mechanism"], int(task["instance_seed"]), str(task.get("record_mode") or "stamp_trap"))
    public = initial_reads(world, meter)
    trace = [dict(phase="public", kind="read", slot=rec["slot"], before_lock=True) for rec in public]
    private_before_lock = False
    bindings = candidate_bindings(fields_for(public))
    competing = CompetingBindingSet(bindings)
    clauses = uses_clauses(method)
    status = "unique"
    admitted = None
    spec = None

    if method == GREEDY:
        best = None
        best_score = (-1, -1)
        for binding in bindings:
            meter.binding_evals += 1
            rows = integer_rows(public, binding)
            score = greedy_score(rows)
            if score > best_score:
                best_score = score
                best = binding
        admitted = best
        status = "unique"
        world.lock()
        spec = synthesize_spec(integer_rows(public, admitted or {}), clauses, meter)
    else:
        competing.filter(public, meter, clauses)
        available = ["repeat", "shuffle", "fresh"]
        if method == FIXED:
            for slot in PUBLIC_SLOTS:
                rec = world.public_read(slot)
                meter.public_env_probes += 1
                public.append(rec)
                trace.append(dict(phase="public", kind="repeat", slot=slot, before_lock=True))
            for rec in run_public_probe("shuffle", world, meter):
                public.append(rec)
                trace.append(dict(phase="public", kind="shuffle", slot=rec["slot"], before_lock=True))
            competing.filter(public, meter, clauses)
        else:
            while len(competing.bindings) > 1 and available:
                if method == RANDOM:
                    kind = rng.choice(list(available))
                    meter.disagreement_policy_evals += 1
                else:
                    kind = select_disambiguating_probe(
                        competing.bindings, public, world, meter, tuple(available),
                    )
                if kind == "fresh":
                    break
                available.remove(kind)
                for rec in run_public_probe(kind, world, meter):
                    public.append(rec)
                    trace.append(dict(phase="public", kind=kind, slot=rec["slot"], before_lock=True))
                competing.filter(public, meter, clauses)
        if method == FIXED:
            validations = []
            for slot in PUBLIC_SLOTS:
                rec = world.public_read(slot)
                meter.public_validation_probes += 1
                public.append(rec)
                validations.append(rec)
                trace.append(dict(phase="public", kind="fresh", slot=slot, before_lock=True))
            validation = validations[-1]
        else:
            slot = select_validation_slot(competing.bindings, public, world, meter)
            validation = world.public_read(slot)
            meter.public_validation_probes += 1
            public.append(validation)
            trace.append(dict(phase="public", kind="fresh", slot=slot, before_lock=True))
        decided = admit_after_validation(competing.bindings, validation, public, meter, clauses)
        status = str(decided["status"])
        admitted = decided.get("binding")
        world.lock()
        if status == "unique" and admitted is not None:
            spec = synthesize_spec(integer_rows(public, admitted), clauses, meter)

    private_ok = private_correct(task, status, admitted, spec, world)
    if world.private_opened and not world.locked:
        private_before_lock = True
    if world.private_opened:
        for slot in PUBLIC_SLOTS:
            trace.append(dict(phase="private", kind="private_eval", slot=slot, before_lock=False))
    map_ok = mapping_correct(task, status, admitted)
    stamp_lock = bool(admitted and admitted.get("output_field") == "stamp" and status == "unique")
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], split=task["split"], w6_group=task.get("w6_group"),
        mechanism=task["mechanism"], method=method, record_mode=task.get("record_mode"),
        gold_status=task.get("gold_status"), gold_field=task.get("gold_field"),
        status=status, admitted=admitted, spec=spec,
        mapping_correct=bool(map_ok), private_correct=bool(private_ok),
        stamp_lock=stamp_lock, false_unique=bool(
            task.get("gold_status") == "ambiguous" and status == "unique"
        ),
        private_before_lock=private_before_lock, locked=world.locked,
        public_records=public, trace=trace,
        unknown_kind=task.get("unknown_kind"),
        retain_wave=task.get("retain_wave"),
        **work,
    )


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(r.get("mapping_correct"))) for r in subset),
            private_correct=sum(int(bool(r.get("private_correct"))) for r in subset),
            stamp_lock=sum(int(bool(r.get("stamp_lock"))) for r in subset),
            false_unique=sum(int(bool(r.get("false_unique"))) for r in subset),
            ambiguous=sum(int(r.get("status") == "ambiguous") for r in subset),
            abstain=sum(int(r.get("status") == "abstain") for r in subset),
            public_env_probes=sum(int(r.get("public_env_probes") or 0) for r in subset),
            public_validation_probes=sum(int(r.get("public_validation_probes") or 0) for r in subset),
            binding_evals=sum(int(r.get("binding_evals") or 0) for r in subset),
            public_probes_plus_bindings=sum(int(r.get("public_probes_plus_bindings") or 0) for r in subset),
            total_acquisition_work=sum(int(r.get("total_acquisition_work") or 0) for r in subset),
        )
    return out


def evaluate_gates(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    rows = list(payload.get("assessment") or [])
    if any(row.get("private_before_lock") for row in rows):
        ok = False
        notes.append("private_before_lock")
    for seed in TRAIN_SEEDS:
        ident = [
            row for row in rows
            if int(row.get("source_seed")) == seed and row.get("split") in IDENTIFIABLE
        ]
        amb = [row for row in rows if int(row.get("source_seed")) == seed and row.get("split") == "w6_ambiguous"]
        for method in (FIXED, CLAUSES):
            sub = [row for row in ident if row["method"] == method]
            if sub and (sum(int(r["mapping_correct"]) for r in sub) != len(sub) or sum(int(r["private_correct"]) for r in sub) != len(sub)):
                ok = False
                notes.append("gate2_ident_{0}_{1}".format(method, seed))
            asub = [row for row in amb if row["method"] == method]
            if asub and (sum(int(r["mapping_correct"]) for r in asub) != len(asub) or any(r.get("false_unique") for r in asub)):
                ok = False
                notes.append("gate2_amb_{0}_{1}".format(method, seed))
        greedy = [row for row in ident if row["method"] == GREEDY]
        if greedy and sum(int(r["mapping_correct"]) for r in greedy) != 0:
            notes.append("greedy_unexpected_{0}".format(seed))
        plus = [row for row in rows if int(row.get("source_seed")) == seed and row["method"] == CLAUSES]
        for name in (FIXED, SCRATCH):
            other = [row for row in rows if int(row.get("source_seed")) == seed and row["method"] == name]
            plus_tot = sum(int(r["total_acquisition_work"]) for r in plus)
            other_tot = sum(int(r["total_acquisition_work"]) for r in other)
            plus_pb = sum(int(r["public_probes_plus_bindings"]) for r in plus)
            other_pb = sum(int(r["public_probes_plus_bindings"]) for r in other)
            if plus_tot >= other_tot or plus_pb >= other_pb:
                ok = False
                notes.append("gate3_{0}_{1}".format(name, seed))
        retain = [row for row in rows if int(row.get("source_seed")) == seed and row.get("split") == "w6_retain"]
        for method in (FIXED, CLAUSES):
            sub = [row for row in retain if row["method"] == method]
            if sub and sum(int(r["private_correct"]) for r in sub) != len(sub):
                ok = False
                notes.append("retain_{0}_{1}".format(method, seed))
        oog = [row for row in rows if int(row.get("source_seed")) == seed and row.get("split") == "w6_oog"]
        for method in (FIXED, CLAUSES, SCRATCH, RANDOM):
            sub = [row for row in oog if row["method"] == method]
            if sub and any(r.get("status") == "unique" for r in sub):
                ok = False
                notes.append("oog_unique_{0}_{1}".format(method, seed))
    return dict(
        gate1_private_isolation=not any(row.get("private_before_lock") for row in rows),
        gate2_mapping_and_ambiguity=all("gate2" not in n for n in notes),
        gate3_efficiency=all("gate3" not in n for n in notes),
        passed=ok,
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"), task_id=row["task_id"], split=row["split"],
            w6_group=row.get("w6_group"), method=row["method"], status=row.get("status"),
            mapping_correct=bool(row.get("mapping_correct")),
            private_correct=bool(row.get("private_correct")),
            stamp_lock=bool(row.get("stamp_lock")),
            false_unique=bool(row.get("false_unique")),
            public_env_probes=int(row.get("public_env_probes") or 0),
            public_validation_probes=int(row.get("public_validation_probes") or 0),
            binding_evals=int(row.get("binding_evals") or 0),
            public_probes_plus_bindings=int(row.get("public_probes_plus_bindings") or 0),
            total_acquisition_work=int(row.get("total_acquisition_work") or 0),
            admitted_field=(row.get("admitted") or {}).get("output_field") if isinstance(row.get("admitted"), dict) else None,
        )
        for row in rows
    ]


def run_wave6(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tasks = []
    for split in ("w6_stamp", "w6_echo", "w6_ambiguous", "w6_oog", "w6_retain"):
        tasks.extend(unfamiliar_policy_tasks(split))
    if any(row["task_id"] in OPENED_IDS for row in tasks):
        raise ValueError("opened_id_in_challenge")
    assessment = []
    seed_blocks = []
    for seed in TRAIN_SEEDS:
        rows = []
        for method in METHODS:
            for task in tasks:
                rng = random.Random(4000 + seed * 97 + METHODS.index(method) * 13 + int(task["instance_seed"]))
                episode = run_episode(task, method, rng)
                episode["source_seed"] = seed
                rows.append(episode)
        assessment.extend(rows)
        seed_blocks.append(dict(
            seed=seed,
            identifiable=_totals([r for r in rows if r["split"] in IDENTIFIABLE]),
            stamp=_totals([r for r in rows if r["split"] == "w6_stamp"]),
            echo=_totals([r for r in rows if r["split"] == "w6_echo"]),
            ambiguous=_totals([r for r in rows if r["split"] == "w6_ambiguous"]),
            oog=_totals([r for r in rows if r["split"] == "w6_oog"]),
            retain=_totals([r for r in rows if r["split"] == "w6_retain"]),
            suite=_totals(rows),
        ))
    totals = dict(
        stamp=_totals([r for r in assessment if r["split"] == "w6_stamp"]),
        echo=_totals([r for r in assessment if r["split"] == "w6_echo"]),
        identifiable=_totals([r for r in assessment if r["split"] in IDENTIFIABLE]),
        ambiguous=_totals([r for r in assessment if r["split"] == "w6_ambiguous"]),
        oog=_totals([r for r in assessment if r["split"] == "w6_oog"]),
        retain=_totals([r for r in assessment if r["split"] == "w6_retain"]),
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
    (directory / "seed_wave6_correspondence_disambiguation.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8",
    )
    return payload


def reconstruct_episode(row: dict[str, Any]) -> dict[str, Any]:
    for step in row.get("trace") or []:
        if step.get("phase") == "private" and step.get("before_lock"):
            return dict(total_acquisition_work=-1, private_before_lock=True)
    work = (
        int(row.get("public_env_probes") or 0)
        + int(row.get("public_validation_probes") or 0)
        + int(row.get("binding_evals") or 0)
        + int(row.get("disagreement_policy_evals") or 0)
        + int(row.get("retrieval_evals") or 0)
        + int(row.get("synthesis_evals") or 0)
    )
    return dict(
        total_acquisition_work=work,
        private_before_lock=bool(row.get("private_before_lock")),
    )


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
        if rec.get("private_before_lock") or rec.get("total_acquisition_work") != row.get("total_acquisition_work"):
            ok = False
            notes.append("reconstruct:" + row["task_id"] + ":" + row["method"])
            break
    rebuilt = _totals(rows)
    saved = (payload.get("totals") or {}).get("suite") or {}
    for name, cell in rebuilt.items():
        if cell.get("total_acquisition_work") != (saved.get(name) or {}).get("total_acquisition_work"):
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
