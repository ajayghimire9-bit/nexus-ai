"""Wave-8 hierarchical gated evolution runner."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .correspondence_env import RecordWorld
from .cross_domain_analogy import (
    PUBLIC_SEQ, FactoredInterfaceMapper, field_pairs, factored_integer_admit,
    private_integer_ok, private_sequence_ok, synthesize_integer,
    synthesize_sequence,
)
from .hierarchical_gated_evolution import (
    HierarchicalBank, RelationalAnalogyEngine, Wave8Meter, Wave8World, begin_task,
    distill_domain_a_schemas, mdl_prune, synthesize_wave8, wave7_ungated_synth,
)
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave7_cross_domain import OPENED_IDS as W7_OPENED
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave8_hierarchical_gated_evolution"
PRIOR_CLOSED = (
    "f2e8942", "6e0df3a", "0d4596e", "c8bc5ad", "25cd50e", "f66ae34",
    "d2c0105", "10f579d", "aa34924", "b590ca2", "c3a4b40", "907db66",
)
OPENED_IDS = set(W7_OPENED) | {
    "w7b_ana_even_append", "w7b_ana_odd_dup", "w7b_look_len02", "w7b_look_len1",
    "w7b_inv_palindrome", "w7b_reuse_palindrome", "w7b_amb_alias", "w7b_oog_caesar",
    "w7a_ret_even",
}
SCRATCH = "factored_interface_scratch"
STATIC = "factored_relational_analogy_static_bank"
WAVE7 = "wave7_ungated_flat_evolving"
HIER_UNGATED = "ablation_hierarchical_ungated"
FLAT_GATED = "ablation_gated_flat_L1_only"
NEXUS = "nexus_hierarchical_gated_evolving"
METHODS = (SCRATCH, STATIC, WAVE7, HIER_UNGATED, FLAT_GATED, NEXUS)
G1 = "w8_analogous"
G2 = "w8_lookalike"
G3L1 = "w8_l1"
G3L2 = "w8_l2"
G4_AMB = "w8_ambiguous"
G4_OOG = "w8_oog"
RETAIN = "w8_retain_a"
L2_PUBLIC = dict(PUBLIC_SEQ, gamma=("r", "a", "r"))
FIRST_LAST_PUBLIC = dict(PUBLIC_SEQ, gamma=("m", "m"))

WAVE8_TASKS = (
    dict(task_id="w8b_ana_even_append", split=G1, domain="B", stage="g1",
         mechanism="seq_even_append", instance_seed=1301, gold_status="unique",
         gold_field="result", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q", "r", "s")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_ana_odd_dup", split=G1, domain="B", stage="g1",
         mechanism="seq_odd_dup", instance_seed=1302, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": ("q",), "delta": ("p", "q", "r")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_look_len02", split=G2, domain="B", stage="g2",
         mechanism="seq_len02_append", instance_seed=1311, gold_status="unique",
         gold_field="result", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q", "r", "s")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_look_len1", split=G2, domain="B", stage="g2",
         mechanism="seq_len1_dup", instance_seed=1312, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": ("q",), "delta": ("p", "q", "r")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_inv_palindrome", split=G3L1, domain="B", stage="l1",
         mechanism="seq_palindrome_hash", instance_seed=1321, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": (), "delta": ("a", "b", "a")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_reuse_palindrome", split=G3L1, domain="B", stage="l1",
         mechanism="seq_palindrome_q", instance_seed=1322, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": (), "delta": ("a", "b", "a")},
         record_mode="stamp_trap"),
    dict(task_id="w8b_once_first_last", split=G3L1, domain="B", stage="l1",
         mechanism="seq_first_last_z", instance_seed=1323, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": ("z",), "delta": ("a", "a")},
         record_mode="stamp_trap", spurious=True, public_map=FIRST_LAST_PUBLIC),
    dict(task_id="w8b_inv_pal_rotate", split=G3L2, domain="B", stage="l2",
         mechanism="seq_pal_rotate_bang", instance_seed=1331, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": ("r", "a", "r"), "delta": ()},
         record_mode="stamp_trap", public_map=L2_PUBLIC),
    dict(task_id="w8b_reuse_pal_rotate", split=G3L2, domain="B", stage="l2",
         mechanism="seq_pal_rotate_q", instance_seed=1332, gold_status="unique",
         gold_field="result", epsilon=("x", "y", "z"),
         private={"alpha": ("x", "x"), "beta": ("x", "y"), "gamma": ("r", "a", "r"), "delta": ()},
         record_mode="stamp_trap", public_map=L2_PUBLIC),
    dict(task_id="w8b_amb_alias", split=G4_AMB, domain="B", stage="amb",
         mechanism="seq_even_append", instance_seed=1341, gold_status="ambiguous",
         gold_field="ambiguous", epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
         record_mode="alias_ambiguous"),
    dict(task_id="w8b_oog_caesar", split=G4_OOG, domain="B", stage="oog",
         mechanism="seq_caesar", instance_seed=1342, gold_status="abstain",
         gold_field=None, epsilon=("w", "x", "y", "z"),
         private={"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
         record_mode="stamp_trap", unknown_kind="oog"),
    dict(task_id="w8a_ret_even", split=RETAIN, domain="A", stage="retain",
         mechanism="oob_even_add2", instance_seed=1351, gold_status="unique",
         gold_field="result", record_mode="stamp_trap", retain_wave="wave2"),
)


def method_flags(method: str) -> dict[str, bool]:
    return dict(
        lazy=method in {FLAT_GATED, NEXUS, SCRATCH},
        gated=method in {FLAT_GATED, NEXUS},
        allow_l2=method in {HIER_UNGATED, NEXUS},
        evolve=method in {WAVE7, HIER_UNGATED, FLAT_GATED, NEXUS},
        analogy=method in {STATIC, WAVE7, HIER_UNGATED, FLAT_GATED, NEXUS},
        prune=method == NEXUS,
        wave7=method == WAVE7,
        scratch=method == SCRATCH,
        static=method == STATIC,
    )


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


def run_domain_b(task: dict[str, Any], method: str, bank: HierarchicalBank,
                 schemas: list) -> dict[str, Any]:
    flags = method_flags(method)
    meter = Wave8Meter()
    begin_task(bank)
    world = Wave8World(
        task["mechanism"], int(task["instance_seed"]), str(task.get("record_mode") or "stamp_trap"),
        tuple(task["epsilon"]), dict(task["private"]), task.get("public_map"),
    )
    admitted = FactoredInterfaceMapper().admit(world, meter)
    status = str(admitted["status"])
    field = admitted.get("field")
    public = list(admitted["public"])
    spec = None
    invented = None
    trace = [dict(phase="public", kind="read", slot=rec.get("slot"), before_lock=True) for rec in public]
    if status == "unique" and field:
        confirm_rec = admitted.get("validation") or public[-1]
        prior = [row for row in public if row is not confirm_rec]
        pairs = field_pairs(prior, str(field))
        confirm = None
        if confirm_rec and field in confirm_rec and not isinstance(confirm_rec[field], int):
            confirm = (tuple(confirm_rec["payload"]), tuple(confirm_rec[field]))
        stage = str(task.get("stage") or "g1")
        allow_micro = stage in {"l1", "l2", "oog"}
        if flags["wave7"]:
            syn = wave7_ungated_synth(pairs, confirm, bank, meter, schemas, allow_micro, stage)
        elif flags["scratch"]:
            syn = synthesize_sequence(pairs, confirm, bank, meter, None, allow_micro, False)
            syn = dict(syn, layer=0)
        elif flags["static"]:
            extra = Wave8Meter()
            local_schemas = schemas or distill_domain_a_schemas(extra)
            meter.schema_distill_cost += extra.schema_distill_cost
            prioritized = RelationalAnalogyEngine(local_schemas).prioritized_specs(bank, meter)
            syn = synthesize_sequence(pairs, confirm, bank, meter, prioritized, allow_micro, False)
            syn = dict(syn, layer=0)
        else:
            syn = synthesize_wave8(
                pairs, confirm, bank, meter, schemas,
                lazy=flags["lazy"], gated=flags["gated"], allow_l2=flags["allow_l2"],
                evolve=flags["evolve"], allow_micro=allow_micro, stage=stage,
            )
        if syn.get("status") != "unique":
            status = str(syn.get("status") or "abstain")
            field = None if status != "unique" else field
        spec = syn.get("spec")
        invented = syn.get("invented")
    elif status == "unique":
        status = "abstain"
        field = None
    if flags["prune"]:
        mdl_prune(bank)
    world.lock()
    private_ok = private_sequence_ok(task, status, spec, world, bank)
    private_before_lock = bool(world.private_opened and not world.locked)
    if world.private_opened:
        for slot in ("alpha", "beta", "gamma", "delta"):
            trace.append(dict(phase="private", kind="private_eval", slot=slot, before_lock=False))
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], split=task["split"], domain="B", stage=task.get("stage"),
        mechanism=task["mechanism"], method=method, gold_status=task.get("gold_status"),
        status=status, admitted_field=field, spec=spec, invented=invented,
        mapping_correct=mapping_correct(task, status, field),
        private_correct=bool(private_ok),
        false_analogy_lock=false_analogy_lock(task, spec, status),
        false_unique=bool(task.get("gold_status") == "ambiguous" and status == "unique"),
        private_before_lock=private_before_lock, locked=world.locked,
        evolved=list(bank.evolved), cold=list(bank.cold_names),
        trace=trace, **work,
    )


def run_domain_a(task: dict[str, Any], method: str) -> dict[str, Any]:
    meter = Wave8Meter()
    world = RecordWorld(task["mechanism"], int(task["instance_seed"]), str(task.get("record_mode") or "stamp_trap"))
    admitted = factored_integer_admit(world, meter)
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
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], split=task["split"], domain="A", stage=task.get("stage"),
        mechanism=task["mechanism"], method=method, gold_status=task.get("gold_status"),
        status=status, admitted_field=field, spec=spec, invented=None,
        mapping_correct=mapping_correct(task, status, field),
        private_correct=bool(private_ok),
        false_analogy_lock=False, false_unique=False,
        private_before_lock=bool(world.private_opened and not world.locked),
        locked=world.locked, evolved=[], cold=[],
        trace=[dict(phase="public", kind="read", slot="alpha", before_lock=True)],
        **work,
    )


def run_episode(task: dict[str, Any], method: str, bank: HierarchicalBank,
                schemas: list) -> dict[str, Any]:
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
            synthesis_evals=sum(int(r.get("synthesis_evals") or 0) for r in subset),
            micro_codegen_evals=sum(int(r.get("micro_codegen_evals") or 0) for r in subset),
            role_probe_cost=sum(int(r.get("role_probe_cost") or 0) for r in subset),
            gate_evals=sum(int(r.get("gate_evals") or 0) for r in subset),
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
    for seed in TRAIN_SEEDS:
        seed_rows = [row for row in rows if int(row.get("source_seed")) == seed]
        if any(row.get("false_analogy_lock") for row in seed_rows if row.get("split") == G2):
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
        nexus_rows = [row for row in seed_rows if row["method"] == NEXUS]
        if any(not row.get("mapping_correct") or not row.get("private_correct") for row in nexus_rows):
            ok = False
            notes.append("nexus_accuracy_{0}".format(seed))
        g1 = [row for row in seed_rows if row.get("split") == G1]
        nexus_g1 = sum(int(r["total_work"]) for r in g1 if r["method"] == NEXUS)
        wave7_g1 = sum(int(r["total_work"]) for r in g1 if r["method"] == WAVE7)
        scratch_g1 = sum(int(r["total_work"]) for r in g1 if r["method"] == SCRATCH)
        if nexus_g1 >= wave7_g1 or nexus_g1 > scratch_g1:
            ok = False
            notes.append("gate2_g1_{0}".format(seed))
        g12 = [row for row in seed_rows if row.get("split") in {G1, G2}]
        if sum(int(r["total_work"]) for r in g12 if r["method"] == NEXUS) >= sum(int(r["total_work"]) for r in g12 if r["method"] == SCRATCH):
            ok = False
            notes.append("gate2_g12_{0}".format(seed))
        oog_n = [row for row in seed_rows if row.get("split") == G4_OOG]
        nexus_oog = sum(int(r["total_work"]) for r in oog_n if r["method"] == NEXUS)
        wave7_oog = sum(int(r["total_work"]) for r in oog_n if r["method"] == WAVE7)
        hier_oog = sum(int(r["total_work"]) for r in oog_n if r["method"] == HIER_UNGATED)
        scratch_oog = sum(int(r["total_work"]) for r in oog_n if r["method"] == SCRATCH)
        if nexus_oog >= wave7_oog or nexus_oog >= hier_oog or nexus_oog > scratch_oog + 40:
            ok = False
            notes.append("gate3_oog_{0}".format(seed))
        g3 = [row for row in seed_rows if row.get("split") in {G3L1, G3L2}]
        suite = seed_rows
        for name in (FLAT_GATED, WAVE7, STATIC, SCRATCH):
            nexus_g3 = [row for row in g3 if row["method"] == NEXUS]
            other_g3 = [row for row in g3 if row["method"] == name]
            if sum(int(r["total_work"]) for r in nexus_g3) >= sum(int(r["total_work"]) for r in other_g3):
                ok = False
                notes.append("gate4_g3_tot_{0}_{1}".format(name, seed))
            if sum(int(r["codegen_plus_synthesis"]) for r in nexus_g3) >= sum(int(r["codegen_plus_synthesis"]) for r in other_g3):
                ok = False
                notes.append("gate4_g3_code_{0}_{1}".format(name, seed))
            nexus_s = [row for row in suite if row["method"] == NEXUS]
            other_s = [row for row in suite if row["method"] == name]
            if sum(int(r["total_work"]) for r in nexus_s) >= sum(int(r["total_work"]) for r in other_s):
                ok = False
                notes.append("gate4_suite_tot_{0}_{1}".format(name, seed))
            if sum(int(r["codegen_plus_synthesis"]) for r in nexus_s) >= sum(int(r["codegen_plus_synthesis"]) for r in other_s):
                ok = False
                notes.append("gate4_suite_code_{0}_{1}".format(name, seed))
    return dict(
        gate1_isolation_and_safety=all(token not in "".join(notes) for token in ("private", "false_analogy", "amb_", "oog_", "retain_")),
        gate2_lazy_g1=all("gate2" not in note for note in notes),
        gate3_oog_gate=all("gate3" not in note for note in notes),
        gate4_hierarchy=all("gate4" not in note for note in notes),
        passed=ok,
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"), task_id=row["task_id"], split=row["split"],
            method=row["method"], status=row.get("status"),
            mapping_correct=bool(row.get("mapping_correct")),
            private_correct=bool(row.get("private_correct")),
            false_analogy_lock=bool(row.get("false_analogy_lock")),
            synthesis_evals=int(row.get("synthesis_evals") or 0),
            micro_codegen_evals=int(row.get("micro_codegen_evals") or 0),
            codegen_plus_synthesis=int(row.get("codegen_plus_synthesis") or 0),
            total_work=int(row.get("total_work") or 0),
            admitted_field=row.get("admitted_field"),
        )
        for row in rows
    ]


def run_wave8(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tasks = [dict(row) for row in WAVE8_TASKS]
    if any(row["task_id"] in OPENED_IDS for row in tasks):
        raise ValueError("opened_id_in_challenge")
    assessment = []
    seed_blocks = []
    for seed in TRAIN_SEEDS:
        rows = []
        for method in METHODS:
            bank = HierarchicalBank()
            extra = Wave8Meter()
            schemas = distill_domain_a_schemas(extra) if method_flags(method)["analogy"] else []
            distill_left = extra.schema_distill_cost if method in {STATIC, WAVE7, HIER_UNGATED} else 0
            for task in tasks:
                episode_bank = bank if method_flags(method)["evolve"] else HierarchicalBank()
                episode = run_episode(task, method, episode_bank if task["domain"] == "B" else bank, schemas)
                if distill_left:
                    episode["schema_distill_cost"] = int(episode.get("schema_distill_cost") or 0) + distill_left
                    episode["total_work"] = int(episode["total_work"]) + distill_left
                    distill_left = 0
                if method_flags(method)["evolve"] and task["domain"] == "B":
                    bank = episode_bank
                episode["source_seed"] = seed
                rows.append(episode)
        assessment.extend(rows)
        seed_blocks.append(dict(
            seed=seed,
            g1=_totals([r for r in rows if r["split"] == G1]),
            g2=_totals([r for r in rows if r["split"] == G2]),
            g12=_totals([r for r in rows if r["split"] in {G1, G2}]),
            g3=_totals([r for r in rows if r["split"] in {G3L1, G3L2}]),
            g3l1=_totals([r for r in rows if r["split"] == G3L1]),
            g3l2=_totals([r for r in rows if r["split"] == G3L2]),
            amb=_totals([r for r in rows if r["split"] == G4_AMB]),
            oog=_totals([r for r in rows if r["split"] == G4_OOG]),
            retain=_totals([r for r in rows if r["split"] == RETAIN]),
            suite=_totals(rows),
        ))
    totals = dict(
        g1=_totals([r for r in assessment if r["split"] == G1]),
        g2=_totals([r for r in assessment if r["split"] == G2]),
        g12=_totals([r for r in assessment if r["split"] in {G1, G2}]),
        g3=_totals([r for r in assessment if r["split"] in {G3L1, G3L2}]),
        g3l1=_totals([r for r in assessment if r["split"] == G3L1]),
        g3l2=_totals([r for r in assessment if r["split"] == G3L2]),
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
    (directory / "seed_wave8_hierarchical_gated_evolution.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8",
    )
    return payload


COST_KEYS = (
    "public_env_probes", "public_validation_probes", "channel_invariance_evals",
    "binding_evals", "role_probe_cost", "schema_distill_cost", "gate_evals",
    "retrieval_evals", "synthesis_evals", "micro_codegen_evals", "operator_compile_cost",
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
