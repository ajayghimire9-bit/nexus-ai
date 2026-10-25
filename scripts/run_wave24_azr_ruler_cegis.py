#!/usr/bin/env python3
"""Single-attempt AZR runner. Default refuses execution; --dev-preflight is temporary.

No final cryptographic seed is drawn until a pushed freeze passes provenance,
an explicit final allocation is validated and a durable attempt is reserved.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, fields
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time

# Set by the supervising parent before this module imports numpy/torch.
if os.environ.get("NEXUS_W24_SUPERVISED") == "1":
    import resource
    _cap = int(os.environ["NEXUS_W24_CPU_CAP"])
    resource.setrlimit(resource.RLIMIT_CPU, (_cap, _cap))
try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass
try:
    import multiprocessing
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from nexus.evolution1.catalogue import digest
from nexus.seed.experimental import read, write_new
from nexus.wave24_quotient_core import (
    WorkMeter, WorkExhausted, SearchResult, expression_wire, expression_from_wire,
    freeze, unfreeze, primitive_cost, solve, verify_certificate, symkan_accounting,
    skill_wire, skill_from_wire,
)
from nexus.wave24_auto_laws import AutoOperatorFingerprinter
from nexus.wave24_resource_host import Allocation, Wave24ResourceHost
from nexus.wave24_self_evolving_loop import (
    METHODS, World, PublicTask, SeededProceduralTaskGenerator, ZeroDataFrontierSelfPlay,
    DualHeadExecutionScorer, JournalSkillView, FrozenSourceState, MeterView,
    source_execution_trace, source_shadow_pairs, procedural_worlds, run_method,
    horizon_break_even,
    DerivationOutcomeCritic, mine_parametric_skills,
    select_ratcheted_source_skills, AlgebraicRoleFunctor, zero_shot_role_transfer,
    UniversalForceFunctor, force_table, zero_shot_force_transfer,
    source_metabolic_utility,
    verify_workspace_certificate, ScratchpadWorkspaceEngine,
)

CONFIG_PATH = "configs/wave24_azr_ruler_cegis.json"
PHASE1_FILES = (
    "src/nexus/wave24_quotient_core.py", "src/nexus/wave24_auto_laws.py",
    "src/nexus/wave24_self_evolving_loop.py", "src/nexus/wave24_resource_host.py",
    "src/nexus/wave24_pytest_guard.py",
    "scripts/run_wave24_azr_ruler_cegis.py", "scripts/verify_wave24_azr_ruler_cegis.py",
    "tests/test_wave24_quotient_soundness.py", "tests/test_wave24_resource_host_and_runner.py",
    CONFIG_PATH, "docs/NEXUS_WAVE24_AZR_RULER_CEGIS_PROTOCOL.md",
    "src/nexus/nn/ridge.py", "src/nexus/evolution1/fixtures.py",
    "src/nexus/evolution1/catalogue.py", "src/nexus/seed/experimental.py",
    "src/nexus/seed/process_memory.py", "src/nexus/seed/metal_model_runtime.py",
    "src/nexus/seed/local_model_runtime.py",
    "src/nexus/seed/public_failure.py",
    "configs/wave24_azr_dev_allocation.json",
    "docs/evidence/wave24_azr_dev_24001.json",
    "tests/test_wave24_parametric_frontier.py",
    "configs/wave24_azr_dev_frontier_allocation.json",
    "docs/evidence/wave24_azr_dev_frontier_v2.json",
    "tests/test_wave24_roles_ratchet.py",
    "configs/wave24_azr_dev_role_allocation.json",
    "docs/evidence/wave24_azr_dev_role_v3.json",
    "tests/test_wave24_workspace.py",
    "configs/wave24_azr_dev_workspace_allocation.json",
    "docs/evidence/wave24_azr_dev_workspace_v4.json",
    "src/nexus/wave24_lifelong_streams.py", "tests/test_wave24_lifelong.py",
    "tests/test_wave24_lifelong_streams.py", "configs/wave24_azr_dev_lifelong_allocation.json",
    "docs/evidence/wave24_azr_dev_lifelong_v5.json",
    "configs/wave24_azr_dev_guidance_allocation.json",
    "src/nexus/wave24_open_world_arena.py", "tests/test_wave24_open_world_arena.py",
    "src/nexus/wave24_helper_spawn.py",
    "src/nexus/wave24_unlimited_playground.py", "tests/test_wave24_unlimited_playground.py",
    "scripts/run_nexus_unlimited_playground.py",
)
WORLDS = ("INT_SEQ", "STR_PARSE", "DICT_RECORD", "STATE_TRANSITION", "BIT_CELLULAR_AUTOMATA")


def source_hashes(repository=ROOT):
    return {p: hashlib.sha256((Path(repository)/p).read_bytes()).hexdigest() for p in PHASE1_FILES}


def validate_config(config):
    historical = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")["payload"]["config"]
    new_keys = {"source_recipe", "source_public_count", "certificate_b_metric", "primitive_expansion_cap", "dev_tiers",
                "twin_mutations", "role_probe_cap", "hygiene_rule", "feature_count", "heldout_transfer"}
    lifelong = config.get("schema") == "wave24_azr_config_v4"
    workspace = config.get("schema") in ("wave24_azr_config_v3", "wave24_azr_config_v4")
    ratchet = config.get("schema") in ("wave24_azr_config_v2", "wave24_azr_config_v3", "wave24_azr_config_v4")
    workspace_keys = {"workspace_hops", "workspace_slots", "source_workspace_extra_tasks"}
    if set(config) != set(historical) | (new_keys if ratchet else set()) | (workspace_keys if workspace else set()) | ({"lifelong_streams"} if lifelong else set()) or config["schema"] not in ("wave24_azr_config_v1", "wave24_azr_config_v2", "wave24_azr_config_v3", "wave24_azr_config_v4"):
        raise ValueError("exact versioned configuration fields required")
    if lifelong and config["lifelong_streams"] is not True:
        raise ValueError("version4 requires the complete locked stream grid")
    if workspace and not (config["workspace_hops"] == 3 and config["workspace_slots"] == 3 and config["source_workspace_extra_tasks"] == 2):
        raise ValueError("locked three-hop three-slot source workspace recipe differs")
    if ratchet and not (config["source_recipe"] == "role_ratchet_v3" and config["source_public_count"] == 2
        and config["certificate_b_metric"] == ("adaptive_workspace_reached_hop_primitive_cap" if workspace else "evolved_steps_primitive_cap_mdl_tie")
        and config["primitive_expansion_cap"] == (3 if lifelong else 2)*config["b0"] and config["dev_tiers"] == "both"
        and config["twin_mutations"] == 16 and config["role_probe_cap"] == 512
        and config["hygiene_rule"] == "finite_source_descriptor_rent_v3" and config["feature_count"] == 10
        and config["heldout_transfer"] == "source_role_functors_only" and config["max_skills_per_world"] <= 3):
        raise ValueError("ratchet metric, source boundaries and fixed resource recipe differ")
    integer_fields = ("b0", "mdl_bound", "tasks_per_world_tier", "repetitions", "public_count",
        "generator_attempts_per_stratum", "source_attempts_per_world", "max_source_rows", "max_skills_per_world",
        "shadow_tasks_per_skill", "shadow_gain_bound", "calibration_repeats", "work_unit_cap", "cell_work_unit_cap",
        "cpu_s", "memory_mb")
    if any(type(config[k]) is not int or config[k] < 1 for k in integer_fields):
        raise ValueError("positive integral bounded config values required")
    if config["b0"] > 6 or config["mdl_bound"] > 6 or config["repetitions"] != 2:
        raise ValueError("declared finite horizons and exactly two acquisition passes required")
    if config["source_attempts_per_world"] > 100 or config["generator_attempts_per_stratum"] > 1000 or config["max_source_rows"] > 512:
        raise ValueError("source/generator bounds exceeded")
    if config["calibration_repeats"] > 5 or not 0 < config["shadow_alpha"] < 1 or config["ridge"] <= 0:
        raise ValueError("invalid fixed calibration/ridge/hygiene settings")
    if config["heldout_world"] != WORLDS[-1] or config["heldout_test_time_selfplay"] is not False:
        raise ValueError("fifth world remains source-unseen; no test-time training")
    if config["min_uniqueness_reduction"] != 0.:
        raise ValueError("strict positive work reduction gate cannot be redefined")
    return config


def derive_seed(seed, purpose, world):
    return int(hashlib.sha256(f"{seed}:{purpose}:{world}".encode()).hexdigest(), 16)


def task_wire(task):
    return dict(public_io=[[freeze(x), freeze(y)] for x, y in task.public_io],
                query=freeze(task.query), output_sort=task.output_sort)


def task_from_wire(value):
    if set(value) != {"public_io", "query", "output_sort"} or not value["public_io"]:
        raise ValueError("complete public task encoding required")
    return PublicTask(tuple((unfreeze(x), unfreeze(y)) for x, y in value["public_io"]),
                      unfreeze(value["query"]), value["output_sort"])


def result_wire(result):
    return dict(status=result.status, witnesses=[expression_wire(e) for e in result.witnesses],
                query_values=[freeze(v) for v in result.query_values], complete=result.complete,
                root_equivalence_discharges=result.root_equivalence_discharges)


def result_from_wire(value):
    if set(value) != {"status", "witnesses", "query_values", "complete", "root_equivalence_discharges"}:
        raise ValueError("exact certificate fields required")
    if type(value["complete"]) is not bool or type(value["root_equivalence_discharges"]) is not int:
        raise ValueError("invalid certificate flags")
    return SearchResult(value["status"], tuple(expression_from_wire(e) for e in value["witnesses"]),
                        tuple(unfreeze(v) for v in value["query_values"]), value["complete"], value["root_equivalence_discharges"])


class CellMeter:
    def __init__(self, parent, cap):
        self.parent, self.cap, self.start = parent, cap, parent.total

    @property
    def total(self):
        return self.parent.total

    def charge(self, category="search_work_units", n=1):
        if self.parent.total-self.start+n > self.cap:
            raise WorkExhausted("cell work cap")
        self.parent.charge(category, n)


def build_bank(worlds, config, seed, meter, *, dev=False):
    tasks, counts, rejections = [], {}, {}
    for i, world in enumerate(worlds):
        generator = SeededProceduralTaskGenerator(derive_seed(seed, "evaluation", world.name),
                                                config["b0"], public_count=config["public_count"])
        tiers = (("Tier-1" if i % 2 == 0 else "Tier-2"),) if dev and config.get("dev_tiers") != "both" else ("Tier-1", "Tier-2")
        for tier in tiers:
            count, seen, rejected = 0, set(), 0
            wanted = 1 if dev else config["tasks_per_world_tier"]
            for _ in range(config["generator_attempts_per_stratum"]):
                if count == wanted:
                    break
                generated = generator.sample(world, meter)
                task = generated.public_view
                key = digest((world.name, task_wire(task)))
                if generated.tier != tier or key in seen:
                    rejected += 1
                    continue
                if tier == "Tier-2":
                    ref = solve(world.grammar, task.public_io, task.query, task.output_sort, config["b0"],
                                quotient=False, meter=MeterView(meter, "generator_work_units"))
                    if ref.status != "NO_PROGRAM_IN_BOUNDED_GRAMMAR":
                        rejected += 1
                        continue
                seen.add(key)
                count += 1
                tasks.append(dict(task_id=key, world=world.name, tier=tier, public=task_wire(task),
                                  teacher=expression_wire(generated.teacher),
                                  teacher_primitive_cost=generated.teacher_primitive_cost,
                                  teacher_query=freeze(generated.teacher_query)))
            counts[world.name+":"+tier] = dict(expected=wanted, actual=count)
            rejections[world.name+":"+tier] = rejected
    return tasks, counts, rejections


def prepare_source(worlds, config, seed, meter, host):
    if config.get("source_recipe") == "role_ratchet_v3":
        return prepare_role_source(worlds, config, seed, meter, host)
    scorer = DerivationOutcomeCritic(config["ridge"], resource_host=host)
    libraries = {w.name: JournalSkillView() for w in worlds}
    all_rows, candidates, receipts = [], {}, []
    for world in worlds[:-1]:
        player = ZeroDataFrontierSelfPlay(derive_seed(seed, "source", world.name), config["b0"],
                                         public_count=config["public_count"])
        player.wake(world, attempts=config["source_attempts_per_world"], meter=meter)
        # Balance the capped fitting bank across source worlds. No target data
        # chooses rows, preprocessing or the critic's fixed ridge coefficient.
        quota = config["max_source_rows"]//(len(worlds)-1)
        all_rows.extend(player.training_rows[:quota])
        candidates[world.name] = mine_parametric_skills(player, world, meter=meter)[:config["max_skills_per_world"]]
        receipts.append(dict(world=world.name, attempts=player.attempts, frontier_tasks=len(player.accepted),
            training_rows_generated=len(player.training_rows), candidate_skills=len(candidates[world.name]),
            skill_expansion_interval=[3, config["b0"]-1],
            infeasibility_reason="EMPTY_PARAMETRIC_SKILL_COST_INTERVAL" if config["b0"] < 4 else None,
            mining=player.diagnostics))
    selected = all_rows[:config["max_source_rows"]]
    if selected:
        scorer.fit(selected, meter=meter)
    hygiene = []
    for world in worlds[:-1]:
        generator = SeededProceduralTaskGenerator(derive_seed(seed, "shadow", world.name),
                                                config["b0"], public_count=config["public_count"])
        for candidate in candidates[world.name]:
            skill = candidate["skill"]
            prospective_size = len(libraries[world.name].snapshot())+1
            import math
            actual_call_cost = 1+math.ceil(math.log2(1+prospective_size))
            if prospective_size > 3 or skill.expansion_cost(world.grammar.ops) <= actual_call_cost:
                hygiene.append(dict(world=world.name, ast=skill_wire(skill), accepted=False,
                    error="noncompressive at actual prospective library-size MDL cost", pairs=[]))
                continue
            if candidate["compression_utility"] <= 0:
                hygiene.append(dict(world=world.name, ast=skill_wire(skill), accepted=False,
                    error="nonpositive exact source compression utility", pairs=[],
                    compression={k: v for k, v in candidate.items() if k != "skill"}))
                continue
            if primitive_cost(skill, world.grammar.ops) > 2*config["b0"]:
                continue
            records = []
            for _ in range(config["shadow_tasks_per_skill"]):
                task = generator.sample(world, MeterView(meter, "training_work_units")).public_view
                records.append(dict(world=world.name, purpose="training_shadow", task=task))
            try:
                pairs = source_shadow_pairs(world, records, skill, b0=2*config["b0"], meter=meter)
                decision = libraries[world.name].promote(skill, pairs, gain_bound=config["shadow_gain_bound"],
                                                       alpha=config["shadow_alpha"])
                hygiene.append(dict(world=world.name, ast=skill_wire(skill), **decision,
                                    compression={k: v for k, v in candidate.items() if k != "skill"},
                                    pairs=[asdict(p) for p in pairs]))
            except ValueError as exc:
                # Rejected/duplicate/invalid source evidence is retained, not
                # converted into a successful promotion or rerolled.
                hygiene.append(dict(world=world.name, ast=skill_wire(skill), accepted=False, error=str(exc), pairs=[]))
    for receipt in receipts:
        receipt["promoted_skills_count"] = len(libraries[receipt["world"]].snapshot())
    return scorer, libraries, dict(recipe="quotient_frontier_parametric_v2", receipts=receipts,
        available_rows=sum(r["training_rows_generated"] for r in receipts), fitted_rows=len(selected),
        source_feedback_sha256=digest(selected), hygiene=hygiene, scorer_source_digest=scorer.source_digest,
        source_rows=selected, scorer_fingerprint=scorer.fingerprint(),
        scorer_parameters=None if scorer.models is None else [(s.tolist(), b.tolist()) for s, b in scorer.models],
        heldout_training_tasks=0, heldout_test_time_selfplay=False)


def prepare_role_source(worlds, config, seed, meter, host):
    """Only source self-play and unlabeled operator-role probes are available."""
    critic = DerivationOutcomeCritic(config["ridge"], resource_host=host, feature_count=10)
    libraries = {w.name: JournalSkillView() for w in worlds}
    roles = {w.name: AutoOperatorFingerprinter(probe_cap=config["role_probe_cap"]).fingerprint_roles(
        w.grammar.operators, w.carriers, meter=meter) for w in worlds}
    rows, receipts, hygiene, schemas = [], [], [], {}
    forces = {w.name: force_table(w.grammar, w.carriers, meter=meter) for w in worlds}
    force_schemas = {}
    for world in worlds[:-1]:
        player = ZeroDataFrontierSelfPlay(derive_seed(seed, "source", world.name), config["b0"],
            public_count=config["source_public_count"], behavioral_features=True)
        player.wake(world, attempts=config["source_attempts_per_world"], meter=meter)
        if config.get("workspace_hops") and player.accepted:
            player.augment_workspace_frontier(world, meter=meter, roles=roles[world.name],
                extra_tasks=config["source_workspace_extra_tasks"], max_hops=config["workspace_hops"])
        rows.extend(player.training_rows[:config["max_source_rows"]//4])
        selected, portfolio = select_ratcheted_source_skills(player, world, max_skills=config["max_skills_per_world"], meter=meter)
        for skill in selected:
            decision = libraries[world.name].promote_ratcheted(skill, player, world, meter=meter,
                max_skills=config["max_skills_per_world"])
            hygiene.append(dict(world=world.name, ast=skill_wire(skill), **decision))
            if decision["accepted"]:
                for functor in AlgebraicRoleFunctor.lift(skill, roles[world.name]):
                    schemas.setdefault(functor.key(), functor)
                for functor in UniversalForceFunctor.lift(skill, forces[world.name], source_domain=world.name):
                    force_schemas.setdefault(functor.key(), functor)
        for skill in libraries[world.name].snapshot():
            final_utility = source_metabolic_utility(skill, player, world,
                library_size=len(libraries[world.name].snapshot()), meter=meter)
            libraries[world.name].observe_source_utility(skill, source_net_utility=final_utility["net_utility"])
            next(r for r in hygiene if r["world"] == world.name and r["ast"] == skill_wire(skill))["final_utility"] = final_utility
        receipts.append(dict(world=world.name, attempts=player.attempts, frontier_tasks=len(player.accepted),
            training_rows_generated=len(player.training_rows), candidate_skills=portfolio["candidate_count"],
            promoted_skills_count=len(libraries[world.name].snapshot()), mining=player.diagnostics, portfolio=portfolio))
    selected_rows = rows[:config["max_source_rows"]]
    if selected_rows:
        critic.fit(selected_rows, meter=meter)
    functors = tuple(schemas[k] for k in sorted(schemas))
    target = worlds[-1]
    transferred, lineage = zero_shot_role_transfer(functors, target.grammar, roles[target.name], target.inputs,
        meter=meter, max_skills=config["max_skills_per_world"])
    for skill, record in zip(transferred, lineage):
        libraries[target.name].install_transfer(skill, target.grammar, record)
    # Force functors are bound and reported only; they are NOT installed, so the
    # registered matrix library for the fifth world is unchanged by this report.
    force_functors = tuple(force_schemas[k] for k in sorted(force_schemas))
    force_bound, force_lineage = zero_shot_force_transfer(force_functors, target.grammar, forces[target.name],
        target.inputs, meter=meter, max_skills=3)
    return critic, libraries, dict(recipe="role_ratchet_v3", receipts=receipts,
        available_rows=sum(r["training_rows_generated"] for r in receipts), fitted_rows=len(selected_rows),
        source_rows=selected_rows, source_feedback_sha256=digest(selected_rows), scorer_source_digest=critic.source_digest,
        scorer_fingerprint=critic.fingerprint(), scorer_parameters=None if critic.models is None else [(s.tolist(), b.tolist()) for s, b in critic.models],
        roles={name: {key: asdict(value) for key, value in table.items()} for name, table in roles.items()},
        role_functors=[asdict(f) for f in functors], cross_domain_role_functors_count=len(functors),
        intra_domain_promoted_skills_count=sum(len(libraries[w.name].snapshot()) for w in worlds[:-1]),
        unseen_world_selfplay_tasks=0, unseen_world_training_rows=0,
        unseen_world_zero_shot_transferred_skills_count=len(transferred), transfer_lineage=lineage,
        force_tables=forces, universal_force_functors=[asdict(f) for f in force_functors],
        unseen_world_force_functor_bindings_count=len(force_bound), force_transfer_lineage=force_lineage,
        heldout_training_tasks=0, heldout_test_time_selfplay=False, hygiene=hygiene)


def isolate_learned_guidance_benchmark(grammar, task, skills, roles, doctor, meter):
    """Fixed Search + Library vs Learned Doctor + Noether + identical L_t."""
    fixed_trace, learned_trace = {}, {}
    before = meter.total
    fixed = ScratchpadWorkspaceEngine(roles=roles, skills=skills, meter=meter, doctor=None,
        canonical_only=True, use_noether=False, max_hops=1).run(grammar, task, trace=fixed_trace)
    fixed_work = meter.total-before
    before = meter.total
    learned = ScratchpadWorkspaceEngine(roles=roles, skills=skills, meter=meter, doctor=None,
        canonical_only=False, use_noether=True, spine_first=False, max_hops=1).run(grammar, task, trace=learned_trace)
    learned_work = meter.total-before
    return dict(learned_guidance_same_library_work=learned_work, fixed_same_library_work=fixed_work,
        learned_status=learned.status, fixed_status=fixed.status, same_library=True,
        equal_search_budget=True, library_size=len(tuple(skills)),
        learned_hops=len(learned_trace.get("workspace", {}).get("hops") or ()),
        fixed_hops=len(fixed_trace.get("workspace", {}).get("hops") or ()))


def execute_request(request, allocation, *, output_path=None):
    if request.get("mode") not in ("dev_preflight", "post_freeze_assessment"):
        raise ValueError("explicit source preflight or frozen assessment mode required")
    config = validate_config(request["config"])
    if (allocation.wall_s > config["wall_s"] or allocation.cpu_s > config["cpu_s"]
            or allocation.memory_mb > config["memory_mb"]
            or allocation.carried_used_s != config["carried_used_s"]
            or allocation.session_limit_s != config["session_limit_s"]):
        raise ValueError("allocation does not match or tightens beyond the frozen resource contract")
    meter = WorkMeter(limit=config["work_unit_cap"], wall_limit=allocation.wall_s)
    payload = dict(schema="wave24_azr_v1", mode=request["mode"], source_commit=request["source_commit"],
        freeze_commit=request.get("freeze_commit"), source_hashes=request["source_hashes"], source_manifest_version=11,
        direct_certificate_verification=True,
        config=config, config_sha256=digest(config), seed=None, cells=[], tasks=[],
        execution_status="INCOMPLETE", allocation=asdict(allocation), false_certificate_count=0,
        independent_task_count=0, total_evaluation_cells=0, source_preparation={}, laws={},
        setup_work_units=0, training_work_units=0, method_summary={}, break_even={},
        symkan_reports=[], **symkan_accounting([]))
    started, cpu_start = time.perf_counter(), time.process_time()
    host = None
    try:
        if output_path is not None:
            write_new(Path(output_path).parent/"header.json", payload)
        # Parent has already reserved the single attempt and validated freeze.
        seed = 24001 if request["mode"] == "dev_preflight" else secrets.randbits(256)
        payload["seed"] = seed
        if output_path is not None:
            write_new(Path(output_path).parent/"seed.json", dict(seed=seed, source_commit=request["source_commit"],
                      freeze_commit=request.get("freeze_commit"), mode=request["mode"]))
        host = Wave24ResourceHost(allocation, meter)
        payload["runtime_route"] = host.query_runtime("")
        payload["versions"] = dict(python=sys.version, torch=host.torch.__version__)
        if not allocation.mps_approved:
            previous = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")["payload"]
            payload["calibration"] = host.reuse_calibration(previous["calibration"],
                source_sha256=previous["payload_sha256"])
            payload["calibration"].update(calibrated_feature_width=6,
                current_scorer_feature_width=config.get("feature_count", 6),
                revalidated_for_current_width=config.get("feature_count", 6) == 6,
                routing_reason="CPU-only allocation; cached six-feature calibration is historical evidence")
            # Preserve the original measured setup cost in full-cost break-even
            # even though this launch does not repeat the calibration operations.
            payload["cached_setup_work_units"] = previous["setup_work_units"]
        else:
            payload["calibration"] = host.calibrate_cpu_mps_threshold(repeats=config["calibration_repeats"])
        worlds = procedural_worlds()
        laws = {}
        for world in worlds:
            bundle = AutoOperatorFingerprinter().discover(world.grammar.operators, world.carriers,
                                                         complete_carriers=True, meter=meter)
            laws[world.name] = bundle
            payload["laws"][world.name] = dict(certified=bundle.certified, probe_digest=bundle.probe_digest,
                certified_structural_laws=[asdict(l) for l in bundle.certified_structural_laws],
                empirical_probe_priors=[asdict(l) for l in bundle.empirical_probe_priors])
        scorer, libraries, source = prepare_source(worlds, config, seed, meter, host)
        payload["source_preparation"] = source
        for key in ("intra_domain_promoted_skills_count", "cross_domain_role_functors_count", "unseen_world_selfplay_tasks",
                    "unseen_world_training_rows", "unseen_world_zero_shot_transferred_skills_count",
                    "unseen_world_force_functor_bindings_count"):
            if key in source:
                payload[key] = source[key]
        from nexus.wave24_auto_laws import AlgebraicRoleSignature
        role_tables = {name: {k: AlgebraicRoleSignature(**v) for k, v in table.items()}
                       for name, table in source.get("roles", {}).items()}
        frozen = {name: FrozenSourceState.capture(lib, scorer, worlds[:-1]) for name, lib in libraries.items()}
        payload["libraries"] = {name: [skill_wire(s) for s in lib.snapshot()] for name, lib in libraries.items()}
        tasks, grid, rejected = build_bank(worlds, config, seed, meter, dev=request["mode"] == "dev_preflight")
        payload.update(tasks=tasks, generation_grid=grid, generator_rejections=rejected,
                       independent_task_count=len(tasks))
        by_name = {w.name: w for w in worlds}
        for item in tasks:
            world, task = by_name[item["world"]], task_from_wire(item["public"])
            for repetition in range(config["repetitions"]):
                for method in METHODS:
                    library = libraries[world.name]
                    if method == METHODS[3]:
                        # Certificate A only admits exact primitive expansions <= B0.
                        class FixedView:
                            def snapshot(self):
                                return tuple(s for s in library.snapshot() if primitive_cost(s, world.grammar.ops) <= config["b0"])
                        selected_library = FixedView()
                    else:
                        selected_library = library
                    before, trace = meter.total, {}
                    if allocation.mps_approved and host.mps_device is not None:
                        host.torch.mps.synchronize()
                    begin = time.perf_counter()
                    result = run_method(method, world, task, b0=config["b0"],
                        mdl_bound=config["mdl_bound"], meter=CellMeter(meter, config["cell_work_unit_cap"]),
                        laws=laws[world.name], library=selected_library,
                        scorer=scorer if scorer.models is not None else None, trace=trace,
                        ratchet=config.get("source_recipe") == "role_ratchet_v3", roles=role_tables.get(world.name),
                        twin_mutations=config.get("twin_mutations", 16), workspace_hops=config.get("workspace_hops", 0),
                        workspace_cap_multiplier=3 if config.get("lifelong_streams") else 2)
                    if allocation.mps_approved and host.mps_device is not None:
                        host.torch.mps.synchronize()
                    elapsed, cost = (time.perf_counter()-begin)*1000, meter.total-before
                    cert_valid, error, checked = None, None, False
                    if result.status != "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED":
                        try:
                            if method == METHODS[4] and config.get("workspace_hops"):
                                cert_valid = verify_workspace_certificate(world.grammar, task, result, trace["workspace"],
                                    meter=MeterView(meter, "verification_work_units"), skills=library.snapshot())
                            else:
                                cert_valid = verify_certificate(world.grammar, task.public_io, task.query, task.output_sort,
                                    config["mdl_bound"] if method == METHODS[4] else config["b0"], result,
                                    meter=MeterView(meter, "verification_work_units"),
                                    macros=library.snapshot() if method == METHODS[4] else (),
                                    mdl=method == METHODS[4] and config.get("source_recipe") != "role_ratchet_v3",
                                    evolved=method == METHODS[4] and config.get("source_recipe") == "role_ratchet_v3",
                                    primitive_cap=config.get("primitive_expansion_cap") if method == METHODS[4] else None)
                            checked = True
                        except ValueError as exc:
                            cert_valid, error, checked = False, str(exc), True
                            payload["false_certificate_count"] += 1
                    frozen[world.name].verify(library, scorer)
                    cell = dict(task_id=item["task_id"], world=world.name, tier=item["tier"], method=method,
                        repetition=repetition, result=result_wire(result), work_units=cost,
                        work_to_g1=trace.get("work_to_g1"), work_to_g2=trace.get("work_to_g2"),
                        work_to_uniqueness=trace.get("work_to_uniqueness"), wall_clock_ms=elapsed,
                        first_acquisition_work=cost if repetition == 0 else None,
                        repeated_use_work=cost if repetition else None,
                        certificate_checked=checked, certificate_valid=cert_valid, certificate_error=error)
                    if config.get("source_recipe") == "role_ratchet_v3":
                        cell.update(twin=trace.get("twin"),
                            teacher_query_covered=any(freeze(v) == item["teacher_query"] for v in result.query_values),
                            certificate_b_metric=config["certificate_b_metric"] if method == METHODS[4] else None)
                    if method == METHODS[4] and config.get("workspace_hops"):
                        cell["workspace"] = trace.get("workspace")
                    payload["cells"].append(cell)
                    if output_path is not None:
                        write_new(Path(output_path).parent/"cells"/f'{len(payload["cells"])-1:06}.json', cell)
        payload["execution_status"] = "COMPLETE" if all(v["actual"] == v["expected"] for v in grid.values()) else "INCOMPLETE"
        if config.get("lifelong_streams"):
            from nexus.wave24_lifelong_streams import run_lifelong_streams
            checkpoint_index = 0
            def checkpoint_stream(value):
                nonlocal checkpoint_index
                if output_path is not None:
                    write_new(Path(output_path).parent/"stream-progress"/f"{checkpoint_index:04}.json", value)
                    checkpoint_index += 1
            payload["lifelong_7_capability_audit"] = run_lifelong_streams(worlds, config, seed, meter, host, progress=checkpoint_stream)
            if payload["lifelong_7_capability_audit"]["execution_status"] != "COMPLETE":
                payload["execution_status"] = payload["lifelong_7_capability_audit"]["execution_status"]
            from nexus.wave24_open_world_arena import run_open_world_arena
            payload["open_world_arena"] = run_open_world_arena(meter, host)
            if payload["open_world_arena"].get("false_certificate_count", 0):
                payload["false_certificate_count"] += payload["open_world_arena"]["false_certificate_count"]
                payload["execution_status"] = "INVALID"
    except Exception as exc:
        payload["execution_status"] = "INCOMPLETE" if isinstance(exc, WorkExhausted) else "INVALID"
        payload["execution_error"] = type(exc).__name__+": "+str(exc)
    finally:
        payload["total_evaluation_cells"] = len(payload["cells"])
        payload["setup_work_units"] = meter.counts["setup_work_units"]+payload.get("cached_setup_work_units", 0)
        payload["training_work_units"] = meter.counts["training_work_units"]
        payload["resource_counts"] = dict(meter.counts)
        payload["resource_stats"] = {} if host is None else dict(host.stats)
        payload["wall_clock_ms"] = (time.perf_counter()-started)*1000
        payload["cpu_seconds"] = time.process_time()-cpu_start
        summarize(payload)
    return payload


def summarize(payload):
    for method in METHODS:
        cells = [c for c in payload["cells"] if c["method"] == method]
        payload["method_summary"][method] = dict(cells=len(cells),
            unresolved_rate=sum(c["result"]["status"] == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" for c in cells)/len(cells) if cells else None,
            first_acquisition_work=sum(c["first_acquisition_work"] or 0 for c in cells),
            repeated_use_work=sum(c["repeated_use_work"] or 0 for c in cells))
        if not cells:
            continue
        baseline = {(c["task_id"], c["repetition"]): c for c in payload["cells"] if c["method"] == METHODS[0]}
        matched = [c for c in cells if (c["task_id"], c["repetition"]) in baseline]
        payload["break_even"][method] = horizon_break_even(payload["setup_work_units"] if method in METHODS[2:] else 0,
            payload["training_work_units"] if method in METHODS[3:] else 0,
            [c["work_units"] for c in matched],
            [baseline[(c["task_id"], c["repetition"])]["work_units"] for c in matched])


def load_allocation(path, *, dev):
    data = read(path)
    expected_purpose = "dev_preflight_only" if dev else "post_freeze_assessment_only"
    if data.get("authorized") is not True or data.get("purpose") != expected_purpose or data.get("max_attempts") != 1:
        raise ValueError("distinct exact one-attempt allocation required for this mode")
    names = {f.name for f in fields(Allocation)}
    return Allocation(**{k: data[k] for k in names if k in data})


def worker(input_path, output_path):
    if os.environ.get("NEXUS_W24_SUPERVISED") != "1":
        raise ValueError("worker may only run under the bounded resource host")
    envelope = read(input_path)
    allocation = Allocation(**envelope.pop("allocation"))
    if source_hashes() != envelope["source_hashes"]:
        raise ValueError("source changed after host reservation")
    if envelope["mode"] == "post_freeze_assessment":
        from scripts.verify_wave24_azr_ruler_cegis import verify_git
        verify_git(ROOT, envelope["freeze_commit"], envelope["source_hashes"])
    payload = execute_request(envelope, allocation, output_path=output_path)
    from scripts.verify_wave24_azr_ruler_cegis import verify_payload
    payload["verification"] = verify_payload(payload, check_git=False, replay=False)
    payload["payload_sha256"] = digest(payload)
    write_new(output_path, payload)
    return 0 if payload["verification"]["integrity_valid"] else 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dev-preflight", action="store_true")
    p.add_argument("--post-freeze", action="store_true")
    p.add_argument("--freeze-commit")
    p.add_argument("--allocation-file")
    p.add_argument("--worker-input")
    p.add_argument("--worker-output")
    args = p.parse_args(argv)
    if args.worker_input:
        return worker(args.worker_input, args.worker_output)
    if args.dev_preflight == args.post_freeze:
        p.error("choose --dev-preflight or explicitly authorized --post-freeze")
    # The old one-launch GPU grant remains consumed. A newly authorized CPU
    # revision has its own immutable allocation and durable attempt identifier.
    frontier_allocation = ROOT/"configs/wave24_azr_dev_guidance_allocation.json"
    allocation_path = args.allocation_file or str(frontier_allocation)
    allocation_record = read(allocation_path)
    run_id = allocation_record.get("run_id", "dev-24001") if args.dev_preflight else "final-"+str(args.freeze_commit)[:12]
    if args.dev_preflight and run_id == "dev-24001" and (ROOT/"docs/evidence/wave24_azr_dev_24001.json").exists():
        raise ValueError("dev-24001 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-frontier-v2" and (ROOT/"docs/evidence/wave24_azr_dev_frontier_v2.json").exists():
        raise ValueError("dev-24001-frontier-v2 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-role-ratchet-v3" and (ROOT/"docs/evidence/wave24_azr_dev_role_v3.json").exists():
        raise ValueError("dev-24001-role-ratchet-v3 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-workspace-v4" and (ROOT/"docs/evidence/wave24_azr_dev_workspace_v4.json").exists():
        raise ValueError("dev-24001-workspace-v4 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-lifelong-v5" and (ROOT/"docs/evidence/wave24_azr_dev_lifelong_v5.json").exists():
        raise ValueError("dev-24001-lifelong-v5 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v6" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v6.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v6").exists()):
        raise ValueError("dev-24001-guidance-v6 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v7" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v7.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v7").exists()):
        raise ValueError("dev-24001-guidance-v7 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v8" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v8.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v8").exists()):
        raise ValueError("dev-24001-guidance-v8 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v9" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v9.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v9").exists()):
        raise ValueError("dev-24001-guidance-v9 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v10" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v10.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v10").exists()):
        raise ValueError("dev-24001-guidance-v10 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v11" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v11.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v11").exists()):
        raise ValueError("dev-24001-guidance-v11 grant already consumed; preserved receipt forbids automatic retry")
    if args.dev_preflight and run_id == "dev-24001-guidance-v12" and (
            (ROOT/"docs/evidence/wave24_azr_dev_guidance_v12.json").exists()
            or (ROOT/"runs/experimental/wave24-azr/attempts/dev-24001-guidance-v12").exists()):
        raise ValueError("dev-24001-guidance-v12 grant already consumed; preserved receipt forbids automatic retry")
    if args.post_freeze and (ROOT/"artifacts/wave24_azr_ruler_cegis.json").exists():
        raise ValueError("final assessment already recorded; refusing before any seed or resource reservation")
    import subprocess
    from scripts.verify_wave24_azr_ruler_cegis import verify_git, verify_payload
    config = validate_config(read(ROOT/CONFIG_PATH))
    allocation = load_allocation(allocation_path, dev=args.dev_preflight)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    hashes = source_hashes()
    if args.post_freeze:
        verify_git(ROOT, args.freeze_commit, hashes, require_pushed=True)
    request = dict(mode="dev_preflight" if args.dev_preflight else "post_freeze_assessment", config=config,
                   source_commit=head, freeze_commit=args.freeze_commit, source_hashes=hashes)
    with tempfile.TemporaryDirectory(prefix="nexus-wave24-dev-" if args.dev_preflight else "nexus-wave24-final-") as tmp:
        request["temporary_output_directory"] = tmp
        payload, receipt = Wave24ResourceHost.supervise(ROOT, request, allocation, run_id=run_id)
        temporary = Path(tmp)/"checked-output.json"
        write_new(temporary, payload)
        verification_start = time.perf_counter()
        refresh = getattr(allocation, "session_refresh_s", 0.0)
        session_left = receipt["session_remaining_s"]
        if refresh > 0:
            session_left = max(session_left, refresh-receipt["wall_s"])
        remaining = min(allocation.wall_s-receipt["wall_s"], session_left)
        report = verify_payload(read(temporary), check_git=args.post_freeze, replay=True,
                                wall_limit=max(.001, remaining))
        verification_wall = time.perf_counter()-verification_start
        from nexus.seed.experimental import Sandbox
        sandbox = Sandbox(ROOT, ROOT/"runs/experimental/wave24-azr")
        with sandbox.locked():
            sandbox.debit(run_id+"-verify", verification_wall, "independent temporary-output replay",
                          payload.get("payload_sha256") or "incomplete_worker")
            receipt["verification_wall_s"] = verification_wall
            receipt["session_used_s"] = allocation.carried_used_s+sandbox.used_s()
            receipt["session_remaining_s"] = allocation.session_limit_s-receipt["session_used_s"]
            if refresh > 0:
                receipt["session_remaining_s"] = max(receipt["session_remaining_s"], refresh-receipt["wall_s"]-verification_wall)
        if receipt["wall_s"]+verification_wall > allocation.wall_s:
            report["errors"].append("combined worker + verifier wall cap exceeded")
            report["integrity_valid"] = report["ready_for_freeze"] = False
        write_new(Path(receipt["attempt_directory"])/"complete-receipt.json", receipt)
        # The authoritative journal/receipt survives temporary dev outputs.
        write_new(Path(receipt["attempt_directory"])/"verifier.json", report)
        if args.post_freeze:
            write_new(ROOT/"artifacts/wave24_azr_ruler_cegis.json", dict(payload=payload, receipt=receipt, verification=report))
        print(json.dumps(dict(mode=request["mode"], verification=report, receipt=receipt,
                              independent_task_count=payload.get("independent_task_count"),
                              total_evaluation_cells=payload.get("total_evaluation_cells"),
                              source_preparation={k: v for k, v in payload.get("source_preparation", {}).items()
                                  if k in ("recipe", "available_rows", "fitted_rows", "heldout_training_tasks",
                                      "intra_domain_promoted_skills_count", "cross_domain_role_functors_count",
                                      "unseen_world_selfplay_tasks", "unseen_world_training_rows",
                                      "unseen_world_zero_shot_transferred_skills_count",
                                      "unseen_world_force_functor_bindings_count")},
                              calibration=payload.get("calibration"), method_summary=payload.get("method_summary"),
                              lifelong_summary={k:v for k,v in payload.get("lifelong_7_capability_audit",{}).items()
                                  if k not in ("stream1","stream2","stream3")}), indent=2))
        return 0 if report["ready_for_freeze"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
