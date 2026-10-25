#!/usr/bin/env python3
"""Strict saved-evidence verifier. Valid execution and scientific success differ.

Never repairs a payload, fills a grid, changes a threshold or runs an LLM.
Negative scientific gates return a nonzero CLI exit even if arithmetic is valid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from nexus.evolution1.catalogue import digest
from nexus.seed.experimental import read
from nexus.wave24_quotient_core import (
    WorkMeter, freeze, primitive_cost, validate_program, eval_expr, verify_certificate,
    skill_from_wire, expression_from_wire, Grammar, Operator, solve,
)
from nexus.wave24_self_evolving_loop import METHODS, procedural_worlds

BRANCH = "codex/wave24-azr-ruler-cegis"
BASE = "073d9297e6b9b350368f31ee7d18418ef9071634"


def verify_direct_witness(grammar, public_io, query, result, meter):
    """Execute saved g1/g2 only. Never re-enumerate the hop grammar."""
    from scripts.run_wave24_azr_ruler_cegis import result_from_wire
    if isinstance(result, dict):
        result = result_from_wire(result)
    if not result.status.startswith("UNIQUE_QUERY"):
        return True
    if not result.witnesses:
        raise ValueError("unique certificate missing g1")
    for expr in result.witnesses[:2]:
        validate_program(expr, grammar)
        for x, y in public_io:
            if freeze(eval_expr(expr, x, grammar.ops, meter)) != freeze(y):
                raise ValueError("saved witness disagrees with public IO")
        if result.query_values and freeze(eval_expr(expr, query, grammar.ops, meter)) != freeze(result.query_values[0]):
            if expr is result.witnesses[0]:
                raise ValueError("g1 disagrees with the certified query value")
    return True


def verify_direct_cell_certificate(grammar, cell, meter):
    from scripts.run_wave24_azr_ruler_cegis import task_from_wire
    task = task_from_wire(cell["task"]["public"])
    return verify_direct_witness(grammar, task.public_io, task.query, cell["result"], meter)


def run_direct_canary(meter):
    grammar = Grammar("INT", (Operator("op_0", ("INT",), "INT", lambda x: x + 1),))
    result = solve(grammar, ((0, 1), (1, 2)), 2, "INT", 2, quotient=True, meter=meter)
    if result.query_values != (3,):
        raise ValueError("direct canary failed")
    return True


def without_physical_timings(value):
    """Only nondeterministic child measurements are exempt from exact replay."""
    if isinstance(value, dict):
        return {k:without_physical_timings(v) for k,v in value.items() if k not in ("wall_s", "peak_rss_mib")}
    if isinstance(value, (tuple,list)):
        return [without_physical_timings(v) for v in value]
    return value


def verify_lifelong_streams(audit, worlds, config, seed, meter, *, replay=False, allocation=None):
    from nexus.wave24_lifelong_streams import derive_capability_metrics, run_lifelong_streams
    def require(condition, message):
        if not condition: raise ValueError(message)
    require(audit.get("schema")=="wave24_lifelong_audit_v1" and audit.get("execution_status")=="COMPLETE", "incomplete lifelong stream execution")
    require(audit.get("false_certificate_count")==0, "false lifelong certificate")
    rows=audit["stream1"]
    require(len(rows)==4 and [r["world"] for r in rows]==[w.name for w in worlds[:-1]], "source stream world grid differs")
    methods=("adaptive","fixed_no_learning","ordinary_exact_cache")
    for row in rows:
        cells=row["cells"]; keys=[(c["index"],c["method"]) for c in cells]
        require(len(keys)==9 and set(keys)=={(i,m) for i in range(3) for m in methods}, "source stream cell grid differs")
        require(len(row["updates"])==3 and row["cache_hits"]==1,"feedback/cache budget differs")
        for i in range(3):
            matched=[c for c in cells if c["index"]==i]
            require(len({digest(c["task"]) for c in matched})==1,"controls saw different tasks")
        for c in cells:
            require(c["report"]["certificate_valid"] is True,"unverified stream certificate")
            require(c["report"]["total_work"]>=0 and c["report"]["verification_work"]>=0,"negative stream cost")
        for update in row["updates"]:
            if update["accepted"]:
                r=update["receipt"]
                require(r["source_only"] and r["certificate_valid"] and r["retention_passed"] and
                    r["net_work_saved"]==r["without_work"]-r["with_work"]-r["proposal_work"]>0,"invalid source promotion")
    target=audit["stream2"]
    require(len(target["cells"])==3 and {c["method"] for c in target["cells"]}==
        {"transferred_doctor","transferred_unguided","source_free_same_hops"},"target stream grid differs")
    require(target["frozen_before"]==target["frozen_after"],"target solve changed learned state")
    require(target["target_feedback_updates"]==target["target_training_rows"]==target["target_selfplay_tasks"]==0,
            "target outcomes entered learning")
    require(audit["unseen_world_selfplay_tasks"]==audit["unseen_world_training_rows"]==0,"target training aggregate differs")
    require(audit["source_feedback_events"]==15 and audit["source_update_domains"]==
        [w.name for w in worlds[:-1] for _ in range(3)]+["OPEN_PYTHON_SOURCE"]*3,"source update provenance/budget differs")
    require(len(audit["stream3"]["open_cells"])==3 and len(audit["stream3"]["poison_audit"])==3,"open/fault stream grid differs")
    for cell in (*target["cells"],*audit["stream3"]["open_cells"]):
        require(cell["report"]["certificate_valid"] is True,"unverified target/open certificate")
    for item in audit["stream3"]["invented_tools"]:
        require(item["composite_only"] is True and item["source_sha256"]==digest(item["python_source"]),"helper export differs")
        require(item["charged_primitive_cost"]>=2,"composite helper undercharged")
    # Independent cost arithmetic, in addition to recomputing the status gates.
    adaptive=[c for r in rows for c in r["cells"] if c["method"]=="adaptive"]
    expected=sum(c["report"]["total_work"] for c in adaptive)+sum(u["learning_work"] for r in rows for u in r["updates"])
    require(audit["adaptive_training_inclusive_work"]==expected,"training-inclusive cost differs")
    for method,key in (("fixed_no_learning","fixed_no_learning_work"),("ordinary_exact_cache","ordinary_cache_work")):
        require(audit[key]==sum(c["report"]["total_work"] for r in rows for c in r["cells"] if c["method"]==method),"baseline cost differs")
    derived=derive_capability_metrics(audit)
    require(all(audit.get(k)==v for k,v in derived.items()),"unsupported or misaggregated capability claim")
    require(audit["arbitrary_depth_demonstrated"] is False,"finite three-hop engine cannot certify arbitrary depth")
    bench=audit.get("guidance_benchmark")
    if bench is not None and config.get("lifelong_streams") is True:
        require(type(bench.get("learned_guidance_same_library_work")) is int
            and type(bench.get("fixed_same_library_work")) is int,"identical-library benchmark missing")
        require(bench["learned_guidance_same_library_work"]<bench["fixed_same_library_work"],
                "learned same-library work must strictly beat fixed search")
        require(audit.get("adaptive_stream_correct_count",0)>audit.get("fixed_stream_correct_count",0),
                "adaptive correctness must strictly beat fixed search")
        require(audit.get("adaptive_stream_correct_count",0)>=10,"adaptive stream must remain at least 10/12")
        require(audit.get("fixed_stream_correct_count",0)>=9,"fixed stream dropped below the 9/12 baseline")
    if replay:
        if bench is None:
            # Historical v5 certificates stay valid; engine revisions do not rewrite them.
            return {k:audit[k] for k in ("arbitrary_depth_demonstrated","lifelong_learning_demonstrated",
                "cross_domain_transfer_demonstrated","meta_learning_symptom_doctor_demonstrated",
                "closed_loop_self_improvement_demonstrated","self_evolving_tool_invention_demonstrated",
                "open_python_sandbox_demonstrated")}
        if audit.get("direct_certificate_verification") is True:
            worlds_by_name={w.name:w for w in worlds}
            for row in rows:
                world=worlds_by_name[row["world"]]
                for cell in row["cells"]:
                    if cell["unique_correct"]:
                        verify_direct_cell_certificate(world.grammar, cell, meter)
            target_name=(target.get("cells") or [{}])[0].get("task",{}).get("world") or target.get("world") or "BIT_CELLULAR_AUTOMATA"
            target_grammar=worlds_by_name.get(target_name, worlds[-1]).grammar
            for cell in target["cells"]:
                if cell.get("unique_correct") and cell.get("task") and cell["task"].get("public"):
                    verify_direct_cell_certificate(target_grammar, cell, meter)
            from nexus.wave24_auto_laws import OpenPythonToolboxAdapter
            from nexus.wave24_lifelong_streams import operator_neg
            raw=OpenPythonToolboxAdapter().ingest((lambda x:x+1, operator_neg, lambda x:2*x),
                                                 tuple(range(-4,8)), meter=meter)
            for cell in audit["stream3"]["open_cells"]:
                if cell.get("unique_correct") and cell.get("task") and cell["task"].get("public"):
                    verify_direct_cell_certificate(raw.grammar, cell, meter)
        else:
            from nexus.wave24_resource_host import Allocation, Wave24ResourceHost
            host=Wave24ResourceHost(Allocation(**allocation),meter)
            reproduced=run_lifelong_streams(worlds,config,seed,meter,host)
            require(digest(without_physical_timings(audit))==digest(without_physical_timings(reproduced)),
                    "independent source/frozen-target stream replay differs")
    return {k:audit[k] for k in ("arbitrary_depth_demonstrated","lifelong_learning_demonstrated",
        "cross_domain_transfer_demonstrated","meta_learning_symptom_doctor_demonstrated",
        "closed_loop_self_improvement_demonstrated","self_evolving_tool_invention_demonstrated",
        "open_python_sandbox_demonstrated")}


def verify_open_world_arena(arena):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(arena.get("schema")=="wave24_open_world_arena_v1", "invalid open-world schema")
    require(arena.get("task_count")==24 and arena.get("toolbox_size",0)>=40, "incomplete open-world grid")
    require(arena.get("false_certificate_count")==0, "open-world false certificate")
    require(arena.get("lyapunov",{}).get("dynamic_lyapunov_max_hops_reached",0)>=4,
            "Lyapunov horizon did not exceed the old 3-hop constant")
    summary=arena.get("method_summary") or {}
    evolving=summary.get("nexus_self_evolving_open_world") or {}
    for name in ("unpruned_open_stdlib_search","standalone_or_tool_llm_baseline","nexus_static_quotient_open_world"):
        other=summary.get(name) or {}
        require(evolving.get("solved",0)>other.get("solved",0),
                "self-evolving open-world solved count does not dominate "+name)
        # v8 measured evolving work/solved 331 vs static 149. Solved-count
        # dominance is the v9 gate; work/solved remains a recorded comparison.
    meta=arena.get("metabolic_stability") or {}
    require(abs(meta.get("atp_total_sum",0)-100.0)<1e-6, "ATP conservation failed")
    require(0.25<=meta.get("normalized_atp_entropy",0)<=0.98, "ATP entropy left the homeostatic band")
    require(meta.get("metabolic_freeze_events")==0 and meta.get("metabolic_drift_events")==0, "metabolic freeze/drift")
    require(meta.get("injected_distractors_quarantined") is True, "shift-4 distractors were not quarantined")
    require(meta.get("band_respected") is True, "per-task metabolic telemetry left the band")
    return dict(open_world_arena_valid=True, metabolic_stability_demonstrated=True)


def require_complete_grid(task_ids, cells, repetitions=2):
    expected = {(t, m, r) for t in task_ids for m in METHODS for r in range(repetitions)}
    keys = [(c["task_id"], c["method"], c["repetition"]) for c in cells]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("incomplete or duplicate registered method/task/repetition grid")
    return True


def require_symkan_identities(reports, payload):
    attempted = nonempty = abstained = faithful = 0
    for report in reports:
        a, n, f = report["attempted"], bool(report["induced_expression"]), report["faithful_export"]
        if type(a) is not bool or type(f) is not bool or n and not a or f != n:
            raise ValueError("invalid SymKAN report/export")
        attempted += a
        nonempty += n
        abstained += a and not n
        faithful += f
    counts = dict(symkan_attempted_count=attempted, symkan_nonempty_induced_count=nonempty,
                  symkan_abstained_count=abstained, symkan_faithful_export_count=faithful)
    if any(type(payload[k]) is not int or payload[k] != v for k, v in counts.items()):
        raise ValueError("SymKAN counts differ from actual reports")
    if attempted != nonempty+abstained or faithful != nonempty:
        raise ValueError("SymKAN accounting identity failed")
    return True


def git(repository, *args):
    return subprocess.check_output(["git", *args], cwd=repository, timeout=15)


def verify_role_source(payload, worlds, config, meter, *, replay):
    """Rebuild source discovery/role transfer without any evaluation outcomes."""
    from scripts.run_wave24_azr_ruler_cegis import prepare_role_source
    from nexus.wave24_self_evolving_loop import DerivationOutcomeCritic
    source, errors = payload["source_preparation"], []
    def check(value, message):
        if not value:
            errors.append(message)
    check(source.get("recipe") == "role_ratchet_v3", "unregistered ratchet source recipe")
    check(source.get("scorer_source_digest") == source.get("source_feedback_sha256") == digest(source["source_rows"]),
          "critic source feedback binding differs")
    check(isinstance(source.get("scorer_parameters"), (list, tuple)) and len(source["scorer_parameters"]) == 2,
          "both critic heads are required")
    check(source.get("scorer_fingerprint") == digest(("derivation_outcome_critic_v3", digest(dict(
          source=source.get("scorer_source_digest"), ridge=config["ridge"], parameters=source.get("scorer_parameters"))))),
          "critic parameter fingerprint differs")
    receipts = source["receipts"]
    check(len(receipts) == 4 and {r["world"] for r in receipts} == set(list(worlds)[:-1]), "source receipt grid differs")
    for row in receipts:
        check(row["promoted_skills_count"] == len(payload["libraries"][row["world"]]), "source skill aggregate differs")
        check(row["frontier_tasks"] == row["mining"]["frontier_tasks_generated"] and row["training_rows_generated"] == row["mining"]["training_rows_generated"], "source mining count differs")
    promoted = sum(r["promoted_skills_count"] for r in receipts)
    check(source["intra_domain_promoted_skills_count"] == promoted, "intra-domain promotion aggregate differs")
    check(source["cross_domain_role_functors_count"] == len(source["role_functors"]), "functor count differs")
    check(source["unseen_world_selfplay_tasks"] == source["unseen_world_training_rows"] == 0, "unseen world received task training")
    check(source["unseen_world_zero_shot_transferred_skills_count"] == len(payload["libraries"][list(worlds)[-1]]) == len(source["transfer_lineage"]), "zero-shot transfer count differs")
    for name in ("intra_domain_promoted_skills_count", "cross_domain_role_functors_count", "unseen_world_selfplay_tasks", "unseen_world_training_rows", "unseen_world_zero_shot_transferred_skills_count"):
        check(payload.get(name) == source[name], "top-level role aggregate differs: "+name)
    check(all(row["target_training_tasks"] == 0 for row in source["transfer_lineage"]), "target-trained transfer record")
    check(all(len(r["features"]) == 10 and r["label_semantics"] == "source_derivation_behavioral_v3"
              and type(r["J_fit"]) is int and r["J_fit"] in (0, 1)
              and type(r["J_disagree"]) is int and r["J_disagree"] in (0, 1) for r in source["source_rows"]), "invalid behavioral training labels/features")
    for item in source["hygiene"]:
        check(item["accepted"] and item["utility"]["rule"] == config["hygiene_rule"]
              and item["utility"]["net_utility"] > 0 and item["final_utility"]["net_utility"] > 0,
              "nonpositive source metabolic utility or wrong policy")
        for utility in (item["utility"], item["final_utility"]):
            check(utility["net_utility"] == utility["saved_positions"]-utility["description_rent"], "metabolic rent arithmetic differs")
            check(utility["physical_execution_savings_claimed"] is False and utility["population_confidence_interval"] is None,
                  "descriptor compression mislabeled as CPU evidence")
    if replay and payload.get("direct_certificate_verification") is not True:
        _, libraries, reproduced = prepare_role_source(tuple(worlds.values()), config, payload["seed"], meter, None)
        # Numeric parameters use a separately verified float32 residual below;
        # every nonnumeric source/selection/role lineage field is deterministic.
        for field in ("receipts", "source_rows", "source_feedback_sha256", "hygiene", "roles", "role_functors", "transfer_lineage"):
            check(digest(source[field]) == digest(reproduced[field]), "source-only role replay differs: "+field)
        from nexus.wave24_quotient_core import skill_wire
        for name, library in libraries.items():
            check(digest([skill_wire(s) for s in library.snapshot()]) == digest(payload["libraries"][name]), "source/transfer AST replay differs")
        rows = source["source_rows"]
        critic = DerivationOutcomeCritic(config["ridge"], feature_count=10).fit(rows, meter=meter)
        import numpy as np
        x = np.asarray([r["features"] for r in rows], float)
        for index, ((scale_ref, beta_ref), (scale, beta)) in enumerate(zip(critic.models, source["scorer_parameters"])):
            scale, beta = np.asarray(scale), np.asarray(beta)
            check(scale.shape == beta.shape == (10,) and np.isfinite(beta).all() and np.all(scale > 0), "behavioral critic parameter shape/type differs")
            check(np.allclose(scale, scale_ref, atol=1e-4, rtol=1e-4), "behavioral critic normalization differs")
            z = x/scale
            check(np.max(np.abs(z@beta-(x/scale_ref)@beta_ref)) <= 1e-4, "behavioral critic prediction replay differs")
            lhs = 2*z.T@z+config["ridge"]*np.eye(10)
            rhs = 2*z.T@np.asarray([r[("J_fit", "J_disagree")[index]] for r in rows])
            denominator = np.linalg.norm(lhs, np.inf)*np.linalg.norm(beta, np.inf)+np.linalg.norm(rhs, np.inf)
            check(np.linalg.norm(lhs@beta-rhs, np.inf)/max(denominator, 1e-30) <= 32*np.finfo(np.float32).eps,
                  "behavioral critic ridge normal-equation residual differs")
    gates = dict(source_frontier_and_rows_each_permitted_world=all(r["frontier_tasks"] > 0 and r["training_rows_generated"] > 0 for r in receipts),
        intra_domain_promotions_each_source_world=all(r["promoted_skills_count"] > 0 for r in receipts),
        cross_domain_role_functors=source["cross_domain_role_functors_count"] > 0,
        zero_shot_transfer_without_target_training=source["unseen_world_zero_shot_transferred_skills_count"] > 0 and source["unseen_world_selfplay_tasks"] == source["unseen_world_training_rows"] == 0,
        disagreement_positive_source_feedback=any(r["J_disagree"] == 1 for r in source["source_rows"]))
    if config.get("workspace_hops"):
        gates["source_workspace_exploration_and_compilation"] = all(
            r["mining"].get("workspace", {}).get("explored_source") is True
            and r["mining"]["workspace"]["hops"] and r["mining"].get("workspace_compiled_candidates")
            for r in receipts)
    return gates, errors


def verify_git(repository, freeze_commit, hashes, *, require_pushed=False):
    from scripts.run_wave24_azr_ruler_cegis import PHASE1_FILES
    if type(freeze_commit) is not str or not re.fullmatch("[0-9a-f]{40}", freeze_commit):
        raise ValueError("exact Commit-1 freeze SHA required")
    if set(hashes) != set(PHASE1_FILES):
        raise ValueError("incomplete Phase-1 source manifest")
    branch = git(repository, "branch", "--show-current").decode().strip()
    if branch != BRANCH:
        raise ValueError("wrong Wave24 research branch")
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, freeze_commit], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", freeze_commit, "HEAD"], cwd=repository, check=True, capture_output=True)
    for path, claimed in hashes.items():
        frozen = git(repository, "show", freeze_commit+":"+path)
        current = (Path(repository)/path).read_bytes()
        if frozen != current or hashlib.sha256(frozen).hexdigest() != claimed:
            raise ValueError("Phase-1 bytes/hash changed: "+path)
    if git(repository, "diff", freeze_commit, "--", *PHASE1_FILES):
        raise ValueError("nonempty Phase-1 diff")
    reflog = git(repository, "reflog", "show", "--format=%gs", branch).decode().lower()
    if not reflog.strip():
        raise ValueError("missing local branch audit trail")
    if any(s in reflog for s in ("commit (amend)", "rebase", "reset:")):
        raise ValueError("history rewrite present in available branch reflog")
    if require_pushed:
        head = git(repository, "rev-parse", "HEAD").decode().strip()
        if head != freeze_commit:
            raise ValueError("new final execution must start at Commit 1 itself")
        for remote in ("origin", "github"):
            advertised = git(repository, "ls-remote", "--heads", remote, "refs/heads/"+branch).decode().split()
            if not advertised or advertised[0] != freeze_commit:
                raise ValueError("freeze not pushed to "+remote)
    return dict(phase1_zero_diff=True, zero_amend_on_branch=True,
                history_audit_scope="available local branch reflog + anchored ancestry; not a universal proof of absent erased history")


def verify_payload(payload, *, check_git=False, replay=True, wall_limit=30):
    from scripts.run_wave24_azr_ruler_cegis import (
        WORLDS, PHASE1_FILES, validate_config, task_from_wire, result_from_wire, build_bank, derive_seed,
    )
    from nexus.wave24_quotient_core import expression_from_wire
    errors, gates, git_report = [], {}, {}
    def must(condition, message):
        if not condition:
            errors.append(message)
    try:
        must(type(payload) is dict and payload.get("schema") == "wave24_azr_v1", "invalid schema")
        if errors:
            raise ValueError("required schema missing")
        config = validate_config(payload["config"])
        must(payload["config_sha256"] == digest(config), "configuration hash differs")
        if "payload_sha256" in payload:
            copy = dict(payload)
            claimed = copy.pop("payload_sha256")
            must(claimed == digest(copy), "payload hash differs")
        manifest_version = payload.get("source_manifest_version", 1)
        lifelong_additions={"src/nexus/wave24_lifelong_streams.py", "tests/test_wave24_lifelong.py",
            "tests/test_wave24_lifelong_streams.py", "configs/wave24_azr_dev_lifelong_allocation.json"}
        role_additions = {"tests/test_wave24_roles_ratchet.py", "configs/wave24_azr_dev_role_allocation.json"}
        workspace_additions = {"docs/evidence/wave24_azr_dev_role_v3.json", "tests/test_wave24_workspace.py",
                               "configs/wave24_azr_dev_workspace_allocation.json"}
        if manifest_version == 1 and payload["mode"] == "dev_preflight":
            # The consumed dev result predates portable receipt hardening.
            # It remains verifiable as its original snapshot, not a run of
            # the later accounting code or a scientific freeze candidate.
            old_files = set(PHASE1_FILES)-{"configs/wave24_azr_dev_allocation.json", "docs/evidence/wave24_azr_dev_24001.json",
                "tests/test_wave24_parametric_frontier.py", "configs/wave24_azr_dev_frontier_allocation.json",
                "docs/evidence/wave24_azr_dev_frontier_v2.json"}
            old_files -= role_additions
            old_files -= workspace_additions
            old_files.discard("docs/evidence/wave24_azr_dev_workspace_v4.json")
            old_files -= lifelong_additions
            old_files.discard("docs/evidence/wave24_azr_dev_lifelong_v5.json")
            old_files.discard("configs/wave24_azr_dev_guidance_allocation.json")
            old_files -= {"src/nexus/wave24_open_world_arena.py", "tests/test_wave24_open_world_arena.py",
                          "src/nexus/wave24_helper_spawn.py"}
            old_files -= {"src/nexus/wave24_unlimited_playground.py",
                          "tests/test_wave24_unlimited_playground.py",
                          "scripts/run_nexus_unlimited_playground.py"}
            must(set(payload["source_hashes"]) == old_files, "incomplete original dev source manifest")
        else:
            expected_files = set(PHASE1_FILES)
            if manifest_version < 10:
                expected_files.discard("configs/wave24_azr_dev_guidance_allocation.json")
                expected_files -= {"src/nexus/wave24_open_world_arena.py", "tests/test_wave24_open_world_arena.py",
                                  "src/nexus/wave24_helper_spawn.py"}
            if manifest_version < 9:
                expected_files.discard("docs/evidence/wave24_azr_dev_lifelong_v5.json")
            if manifest_version < 8:
                expected_files -= lifelong_additions
            if manifest_version < 7:
                expected_files.discard("docs/evidence/wave24_azr_dev_workspace_v4.json")
            if manifest_version < 6:
                expected_files -= workspace_additions
            if manifest_version < 5:
                expected_files -= role_additions
            if manifest_version == 2:
                expected_files -= {"tests/test_wave24_parametric_frontier.py", "configs/wave24_azr_dev_frontier_allocation.json"}
            if manifest_version in (2, 3):
                expected_files.discard("docs/evidence/wave24_azr_dev_frontier_v2.json")
            if manifest_version < 11:
                expected_files -= {"src/nexus/wave24_unlimited_playground.py",
                                   "tests/test_wave24_unlimited_playground.py",
                                   "scripts/run_nexus_unlimited_playground.py"}
            must(manifest_version in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11) and set(payload["source_hashes"]) == expected_files, "incomplete current source hash grid")
        must(all(re.fullmatch("[0-9a-f]{64}", v) for v in payload["source_hashes"].values()), "invalid source hash")
        must(payload["mode"] in ("dev_preflight", "post_freeze_assessment"), "invalid result mode")
        must(type(payload["seed"]) is int and payload["seed"] >= 0, "missing assessment/dev seed")
        if payload["mode"] == "dev_preflight":
            must(payload["seed"] == 24001, "development seed must remain 24001")
        must(payload["execution_status"] == "COMPLETE", "execution incomplete or invalid")
        cells, tasks = payload["cells"], payload["tasks"]
        must(payload["independent_task_count"] == len(tasks), "task count differs")
        must(payload["total_evaluation_cells"] == len(cells), "evaluation-cell count differs")
        by_task = {t["task_id"]: t for t in tasks}
        must(len(by_task) == len(tasks), "duplicate task IDs")
        expected_task_count = (10 if config.get("dev_tiers") == "both" else 5) if payload["mode"] == "dev_preflight" else 5*2*config["tasks_per_world_tier"]
        must(len(tasks) == expected_task_count, "incomplete registered task strata")
        actual_strata = {(w, t): 0 for w in WORLDS for t in ("Tier-1", "Tier-2")}
        for task in tasks:
            must((task["world"], task["tier"]) in actual_strata, "unknown world/tier")
            actual_strata[(task["world"], task["tier"])] += 1
            must(task["task_id"] == digest((task["world"], task["public"])), "task ID not bound to public data")
        for i, world in enumerate(WORLDS):
            if payload["mode"] == "dev_preflight" and config.get("dev_tiers") == "both":
                must(all(actual_strata[(world, tier)] == 1 for tier in ("Tier-1", "Tier-2")), "incomplete both-tier dev allocation: "+world)
            elif payload["mode"] == "dev_preflight":
                wanted = "Tier-1" if i % 2 == 0 else "Tier-2"
                must(actual_strata[(world, wanted)] == 1 and actual_strata[(world, "Tier-2" if wanted == "Tier-1" else "Tier-1")] == 0,
                     "dev world allocation differs: "+world)
            else:
                must(all(actual_strata[(world, tier)] == config["tasks_per_world_tier"] for tier in ("Tier-1", "Tier-2")),
                     "incomplete per-world tier allocation: "+world)
        expected = {(t["task_id"], m, r) for t in tasks for m in METHODS for r in range(config["repetitions"])}
        keyed = {(c["task_id"], c["method"], c["repetition"]): c for c in cells}
        require_complete_grid(by_task, cells, config["repetitions"])
        must(len(keyed) == len(cells) and set(keyed) == expected, "incomplete or duplicated cell grid")
        must(len(cells) == expected_task_count*5*2, "registered full-cell count not met")
        must(payload["false_certificate_count"] == 0, "false certificate count nonzero")
        measured_false = sum(c["certificate_valid"] is False for c in cells)
        must(measured_false == payload["false_certificate_count"], "false certificate aggregate differs")
        worlds = {w.name: w for w in procedural_worlds()}
        verifier_meter = WorkMeter(limit=50_000_000, wall_limit=wall_limit)
        direct = payload.get("direct_certificate_verification") is True
        if replay and not direct:
            regenerated, generation_grid, rejected = build_bank(tuple(worlds.values()), config, payload["seed"],
                verifier_meter, dev=payload["mode"] == "dev_preflight")
            must(digest(regenerated) == digest(tasks), "saved tasks differ from locked procedural seed")
            must(generation_grid == payload["generation_grid"] and rejected == payload["generator_rejections"], "generator accounting differs")
        if direct:
            run_direct_canary(verifier_meter)
        for row in tasks:
            task, world = task_from_wire(row["public"]), worlds[row["world"]]
            must(row["world"] in WORLDS, "unknown task family")
            if replay:
                ast = expression_from_wire(row["teacher"])
                validate_program(ast, world.grammar)
                cost = primitive_cost(ast, world.grammar.ops)
                must(cost == row["teacher_primitive_cost"], "teacher expansion cost differs")
                must((cost <= config["b0"]) if row["tier"] == "Tier-1" else config["b0"] < cost <= 2*config["b0"],
                     "teacher outside tier horizon")
                must(all(freeze(eval_expr(ast, x, world.grammar.ops, verifier_meter)) == freeze(y) for x, y in task.public_io),
                     "teacher/public I/O mismatch")
                must(freeze(eval_expr(ast, task.query, world.grammar.ops, verifier_meter)) == tuple_tree(row["teacher_query"]),
                     "teacher query mismatch")
        fixed_methods = METHODS[:4] if manifest_version >= 3 else METHODS[:3]
        unique_work = {m: 0 for m in fixed_methods}
        unique_counts = {m: 0 for m in fixed_methods}
        matches, comparisons, deep_ok, deep_total = 0, 0, 0, 0
        for cell in cells:
            row = by_task[cell["task_id"]]
            must(cell["world"] == row["world"] and cell["tier"] == row["tier"], "cell/task mismatch")
            work = cell["work_units"]
            must(type(work) is int and work >= 0, "invalid cell work")
            must(type(cell["wall_clock_ms"]) in (int, float) and math.isfinite(cell["wall_clock_ms"]) and cell["wall_clock_ms"] >= 0,
                 "invalid cell wall time")
            for key in ("work_to_g1", "work_to_g2", "work_to_uniqueness"):
                v = cell[key]
                must(v is None or type(v) is int and 0 <= v <= work, "invalid/censored work endpoint: "+key)
            must(cell["first_acquisition_work"] == (work if cell["repetition"] == 0 else None), "first-use work differs")
            must(cell["repeated_use_work"] == (work if cell["repetition"] == 1 else None), "repeat work differs")
            result = result_from_wire(cell["result"])
            unknown = result.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED"
            must(unknown or cell["certificate_checked"] is True and cell["certificate_valid"] is True, "unverified completed certificate")
            if replay and not unknown:
                world, task = worlds[row["world"]], task_from_wire(row["public"])
                if direct:
                    verify_direct_witness(world.grammar, task.public_io, task.query, result, verifier_meter)
                else:
                    evolved = cell["method"] == METHODS[4]
                    skills = tuple(skill_from_wire(x) for x in payload["libraries"][world.name]) if evolved else ()
                    if evolved and config.get("workspace_hops"):
                        from nexus.wave24_self_evolving_loop import verify_workspace_certificate
                        verify_workspace_certificate(world.grammar, task, result, cell["workspace"], skills=skills, meter=verifier_meter)
                        must(cell["workspace"]["max_hops"] == config["workspace_hops"] and cell["workspace"]["slots"] == config["workspace_slots"],
                             "workspace allocation differs")
                    else:
                        verify_certificate(world.grammar, task.public_io, task.query, task.output_sort,
                                           config["mdl_bound"] if evolved else config["b0"], result,
                                           meter=verifier_meter, macros=skills, mdl=evolved and config.get("source_recipe") != "role_ratchet_v3",
                                           evolved=evolved and config.get("source_recipe") == "role_ratchet_v3",
                                           primitive_cap=config.get("primitive_expansion_cap") if evolved else None)
            baseline = keyed[(cell["task_id"], METHODS[0], cell["repetition"])]
            if cell["tier"] == "Tier-1" and cell["method"] in fixed_methods[1:] and not unknown:
                comparisons += 1
                agrees = result.status == baseline["result"]["status"]
                if result.status.startswith("UNIQUE_QUERY"):
                    agrees = agrees and result.query_values == result_from_wire(baseline["result"]).query_values
                matches += agrees
                must(agrees, "completed Tier-1 status/output disagreement")
            if cell["tier"] == "Tier-1" and cell["method"] in fixed_methods and result.status.startswith("UNIQUE_QUERY"):
                must(cell["work_to_uniqueness"] is not None, "missing uniqueness-work endpoint")
                unique_work[cell["method"]] += cell["work_to_uniqueness"] or 0
                unique_counts[cell["method"]] += 1
            if cell["tier"] == "Tier-2" and cell["method"] == METHODS[4]:
                deep_total += 1
                static = [keyed[(cell["task_id"], m, cell["repetition"])]["result"]["status"] for m in METHODS[:4]]
                good = all(v == "NO_PROGRAM_IN_BOUNDED_GRAMMAR" for v in static)
                good = good and result.status in ("AMBIGUOUS_WITNESS_FOUND", "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE") and bool(result.witnesses)
                if config.get("source_recipe") == "role_ratchet_v3":
                    covered = any(freeze(v) == tuple_tree(row["teacher_query"]) for v in result.query_values)
                    must(cell["teacher_query_covered"] == covered, "teacher query coverage arithmetic differs")
                    must(cell["certificate_b_metric"] == config["certificate_b_metric"], "Certificate B metric mislabeled")
                    good = good and covered
                deep_ok += good
        gates["completed_tier1_exact_agreement"] = comparisons > 0 and matches == comparisons
        base_n = unique_counts[METHODS[0]]
        gates["stage2_reduces_work_to_uniqueness"] = base_n > 0 and unique_counts[METHODS[1]] == base_n and unique_work[METHODS[1]] < unique_work[METHODS[0]]
        gates["stage3_reduces_work_to_uniqueness"] = base_n > 0 and unique_counts[METHODS[2]] == base_n and unique_work[METHODS[2]] < unique_work[METHODS[0]]
        if manifest_version >= 3:
            gates["stage4_reduces_work_to_uniqueness"] = base_n > 0 and unique_counts[METHODS[3]] == base_n and unique_work[METHODS[3]] < unique_work[METHODS[0]]
        gates["certificate_b_deep_horizon"] = deep_total > 0 and deep_ok == deep_total
        for method in METHODS:
            rows = [c for c in cells if c["method"] == method]
            summary = payload["method_summary"][method]
            must(summary["cells"] == len(rows), "method cell count differs")
            rate = sum(c["result"]["status"] == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" for c in rows)/len(rows) if rows else None
            must(summary["unresolved_rate"] == rate, "unresolved rate differs")
            for metric in ("first_acquisition_work", "repeated_use_work"):
                must(summary[metric] == sum(c[metric] or 0 for c in rows), "method work aggregate differs")
            if rows:
                ledger = payload["break_even"][method]
                setup = payload["setup_work_units"] if method in METHODS[2:] else 0
                training = payload["training_work_units"] if method in METHODS[3:] else 0
                p, b, first = setup+training, 0, None
                for n, c in enumerate(rows, 1):
                    p += c["work_units"]
                    b += keyed[(c["task_id"], METHODS[0], c["repetition"])]["work_units"]
                    if first is None and p < b:
                        first = n
                must(ledger == dict(N=len(rows), proposed_total=p, baseline_total=b,
                                    strict_break_even=p < b, first_observed_break_even=first), "Horizon-N ledger arithmetic differs")
        cached_setup = payload.get("cached_setup_work_units", 0)
        must(type(cached_setup) is int and cached_setup >= 0, "invalid carried setup work")
        if cached_setup:
            previous = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")["payload"]
            must(cached_setup == previous["setup_work_units"], "cached setup debit differs from consumed run")
            must(payload["calibration"].get("cached") is True and payload["calibration"].get("source_sha256") == previous["payload_sha256"],
                 "cached calibration lacks consumed-run provenance")
            must(payload["calibration"]["rows"] == previous["calibration"]["rows"], "cached calibration timings changed")
            must(payload["resource_stats"].get("mps_scoring_calls", 0) == 0 and payload["resource_stats"].get("mps_weight_updates", 0) == 0,
                 "CPU revision unexpectedly executed MPS")
        must(payload["setup_work_units"] == payload["resource_counts"].get("setup_work_units", 0)+cached_setup, "setup accounting differs")
        must(payload["training_work_units"] == payload["resource_counts"].get("training_work_units", 0), "training accounting differs")
        require_symkan_identities(payload["symkan_reports"], payload)
        source = payload["source_preparation"]
        must(len(source["source_rows"]) == source["fitted_rows"] <= config["max_source_rows"], "source row cap/count differs")
        must(source["source_feedback_sha256"] == digest(source["source_rows"]), "source feedback hash differs")
        must(all(r["purpose"] == "training" for r in source["source_rows"]), "hidden feedback entered source fitting")
        must(source["heldout_training_tasks"] == 0 and source["heldout_test_time_selfplay"] is False, "heldout world trained")
        if config.get("source_recipe") == "role_ratchet_v3":
            role_gates, role_errors = verify_role_source(payload, worlds, config, verifier_meter, replay=replay)
            gates.update(role_gates)
            errors.extend(role_errors)
        else:
            must(not payload["libraries"][WORLDS[-1]], "heldout-world skills leaked from source")
        if 3 <= manifest_version < 5:
            must(source.get("recipe") == "quotient_frontier_parametric_v2", "unregistered source algorithm")
            receipts = source["receipts"]
            must({r["world"] for r in receipts} == set(WORLDS[:-1]) and len(receipts) == 4, "source world grid differs")
            for entry in receipts:
                mining = entry["mining"]
                must(mining["quotient_complete"] is True, "incomplete frontier cannot certify minimum costs")
                must(entry["frontier_tasks"] == mining["frontier_tasks_generated"] and
                     entry["training_rows_generated"] == mining["training_rows_generated"], "frontier accounting differs")
                must(entry["promoted_skills_count"] == len(payload["libraries"][entry["world"]]), "promoted skill count differs")
            gates["source_frontier_and_rows_each_permitted_world"] = all(r["frontier_tasks"] > 0 and r["training_rows_generated"] > 0 for r in receipts)
            gates["promoted_skills_each_permitted_world"] = all(r["promoted_skills_count"] > 0 for r in receipts)
            # Explicitly retain the requested all-domain screen: an untrained
            # fifth world cannot be silently relabelled as having learned skills.
            gates["promoted_skills_every_domain"] = all(payload["libraries"][w] for w in WORLDS)
            must(all(r.get("label_semantics") == "source_derivation_membership_v2" and
                     type(r.get("J_fit")) is int and r["J_fit"] in (0, 1) and
                     type(r.get("J_disagree")) is int and r["J_disagree"] in (0, 1)
                     for r in source["source_rows"]), "source critic labels are not observed derivation memberships")
            must(source["scorer_source_digest"] == source["source_feedback_sha256"], "critic was not fitted to recorded source rows")
            if replay:
                # Independently reconstruct the source bank before trusting a
                # purpose tag or a hash of arbitrary labels. No evaluation
                # task, query outcome or promoted target result is passed in.
                from nexus.wave24_self_evolving_loop import ZeroDataFrontierSelfPlay, DerivationOutcomeCritic
                generated_rows = []
                for world in list(worlds.values())[:-1]:
                    player = ZeroDataFrontierSelfPlay(derive_seed(payload["seed"], "source", world.name),
                        config["b0"], public_count=config["public_count"])
                    player.wake(world, attempts=config["source_attempts_per_world"], meter=verifier_meter)
                    saved = next(r for r in receipts if r["world"] == world.name)
                    must(saved["frontier_tasks"] == len(player.accepted) and
                         saved["training_rows_generated"] == len(player.training_rows), "source frontier/row regeneration differs")
                    must(tuple_tree(saved["mining"]["source_probe_inputs"]) == tuple_tree(player.diagnostics["source_probe_inputs"]), "source probe seed differs")
                    generated_rows.extend(player.training_rows[:config["max_source_rows"]//4])
                generated_rows = generated_rows[:config["max_source_rows"]]
                must(digest(generated_rows) == source["source_feedback_sha256"], "source labels do not reproduce from the permitted quotient DAG")
                if generated_rows:
                    critic = DerivationOutcomeCritic(config["ridge"]).fit(generated_rows, meter=verifier_meter)
                    reference = [(s.tolist(), b.tolist()) for s, b in critic.models]
                    supplied = source["scorer_parameters"]
                    must(len(supplied) == 2 and all(len(s) == len(b) == 6 for s, b in supplied), "critic parameter shape differs")
                    import numpy as np
                    x = np.asarray([r["features"] for r in generated_rows], dtype=float)
                    y = np.asarray([[r[k] for k in ("J_fit", "J_disagree")] for r in generated_rows], dtype=float)
                    for head, ((scale_ref, beta_ref), (scale, beta)) in enumerate(zip(reference, supplied)):
                        scale, beta = np.asarray(scale), np.asarray(beta)
                        must(np.isfinite(scale).all() and np.isfinite(beta).all() and (scale > 0).all(), "nonfinite/invalid critic parameters")
                        must(np.allclose(scale, scale_ref, atol=1e-4, rtol=1e-4), "critic training-only normalization differs")
                        z = x/scale
                        prediction_error = np.max(np.abs(z@beta - (x/np.asarray(scale_ref))@np.asarray(beta_ref)))
                        must(prediction_error <= 1e-4, "critic predictions disagree with independent CPU ridge fit")
                        # Coefficients are ill-conditioned when structural
                        # features are collinear. Audit the actual ridge
                        # equations as well as predictions, using a specified
                        # float32 backward-error bound, not an arbitrary loose
                        # coefficient-distance tolerance.
                        lhs = 2*z.T@z + config["ridge"]*np.eye(x.shape[1])
                        rhs = 2*z.T@y[:, head]
                        denominator = np.linalg.norm(lhs, ord=np.inf)*np.linalg.norm(beta, ord=np.inf)+np.linalg.norm(rhs, ord=np.inf)
                        backward_error = np.linalg.norm(lhs@beta-rhs, ord=np.inf)/max(denominator, 1e-30)
                        must(backward_error <= 32*np.finfo(np.float32).eps, "critic normal-equation residual exceeds float32 tolerance")
        for entry in source["hygiene"] if config.get("source_recipe") != "role_ratchet_v3" else ():
            if entry["accepted"]:
                pairs = entry["pairs"]
                must(len(pairs) >= 2 and len({p["task_id"] for p in pairs}) == len(pairs), "invalid shadow units")
                gains = [p["without_skill_work"]-p["with_skill_work"] for p in pairs]
                must(all(abs(v) <= config["shadow_gain_bound"] for v in gains), "shadow gain exceeds bound")
                lcb = sum(gains)/len(gains)-2*config["shadow_gain_bound"]*math.sqrt(math.log(1/config["shadow_alpha"])/(2*len(pairs)))
                must(lcb > 0 and math.isclose(lcb, entry["lcb"], abs_tol=1e-8), "invalid promotion LCB")
        must(payload["resource_stats"].get("runtime_calls", 0) == 0, "unexpected LLM runtime execution")
        if config.get("lifelong_streams"):
            gates.update(verify_lifelong_streams(payload["lifelong_7_capability_audit"],tuple(worlds.values()),
                config,payload["seed"],verifier_meter,replay=replay,allocation=payload["allocation"]))
        if payload.get("open_world_arena"):
            gates.update(verify_open_world_arena(payload["open_world_arena"]))
        if check_git or payload["mode"] == "post_freeze_assessment":
            git_report = verify_git(ROOT, payload["freeze_commit"], payload["source_hashes"])
    except Exception as exc:
        errors.append(type(exc).__name__+": "+str(exc))
    valid = not errors
    return dict(integrity_valid=valid, scientific_gates=gates,
                scientific_gates_passed=bool(gates) and all(gates.values()),
                ready_for_freeze=valid and bool(gates) and all(gates.values()),
                errors=errors, failed_scientific_gates=[k for k, v in gates.items() if not v],
                replayed=replay, **git_report)


def tuple_tree(v):
    return tuple(tuple_tree(x) for x in v) if isinstance(v, (list, tuple)) else v


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("payload")
    p.add_argument("--post-freeze", action="store_true")
    args = p.parse_args(argv)
    data = read(args.payload)
    payload = data.get("payload", data)
    report = verify_payload(payload, check_git=args.post_freeze, replay=True)
    print(json.dumps(report, indent=2))
    return 0 if report["ready_for_freeze"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
