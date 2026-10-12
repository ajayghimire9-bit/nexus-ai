"""V0.8.5 candidate quality vs verifier quality. Same pairs for every gate. Not AGI."""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import source_policy_task, v085_confirmation_targets, v085_development_target
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import adapt_method
from nexus.world.agent import InteractionLedger, collect_planned_belief
from nexus.world.belief import IdentityBelief
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.protocol import (
    V085_CONFIRM_REF_SEED,
    V085_DEV_REF_SEED,
    V085_GATE_SEED,
    V085_SOURCE_COLLECT_SEED,
    V085_TARGET_COLLECT_SEED,
    V085_VAL_COLLECT_SEED,
)
from nexus.world.train import train_world_model
from nexus.world.verify import (
    CONTROL_VAL_HORIZON,
    GateInput,
    MIN_IMPROVE,
    V085_H128,
    V085_MAE_STEPS,
    V085_REF_EPISODES,
    V085_REF_HORIZON,
    V085_REF_MARGIN,
    classify_reference,
    harm_status,
    matched_control_compare,
    run_gate,
    weights_hash,
)

VERIFIER_SPECS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("never", {"horizon": 0, "n_episodes": 0, "cap": 0}),
    ("always", {"horizon": 0, "n_episodes": 0, "cap": 0}),
    ("mae", {"horizon": 0, "n_episodes": 0, "cap": V085_MAE_STEPS}),
    ("control_h32", {"horizon": CONTROL_VAL_HORIZON, "n_episodes": 1, "cap": 2 * CONTROL_VAL_HORIZON}),
    ("control_h128", {"horizon": V085_H128, "n_episodes": 1, "cap": 2 * V085_H128}),
)

RECIPES: tuple[tuple[str, int, int], ...] = (("c128", 128, 64), ("c256", 256, 64))


@dataclass
class CandidatePair:
    pair_id: str
    model_seed: int
    spec: TaskSpec
    recipe: str
    incumbent: WorldModel
    candidate: WorldModel
    train_n: int
    val_n: int
    independent_validation: bool
    checkpoint_rule: str
    inc_hash: str
    cand_hash: str
    collect_n: int
    val_collect_n: int
    collect_interactions: int
    train_seeds: list[int]
    val_seeds: list[int]


def _git_meta() -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=".", stderr=subprocess.DEVNULL, text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return "unknown"

    return {
        "revision": _run(["git", "rev-parse", "HEAD"]),
        "dirty": bool(_run(["git", "status", "--porcelain"])),
        "branch": _run(["git", "branch", "--show-current"]),
    }


def generate_pair(
    spec: TaskSpec,
    source: WorldModel,
    source_replay: Any,
    *,
    model_seed: int,
    recipe: str,
    collect_n: int,
    val_n: int,
    epochs: int,
    pair_i: int,
) -> CandidatePair:
    tr_seeds = tuple(range(50 + 40 * model_seed + 7 * pair_i, 58 + 40 * model_seed + 7 * pair_i))
    va_seeds = tuple(range(900 + 40 * model_seed + 7 * pair_i, 908 + 40 * model_seed + 7 * pair_i))
    train_ds = collect_planned_belief(
        spec, source, IdentityBelief(), collect_n, env_seeds=tr_seeds, base_seed=V085_TARGET_COLLECT_SEED + 19 * model_seed + 3 * pair_i
    )
    val_ds = collect_planned_belief(
        spec, source, IdentityBelief(), val_n, env_seeds=va_seeds, base_seed=V085_VAL_COLLECT_SEED + 19 * model_seed + 3 * pair_i
    )
    if len(train_ds) and len(val_ds):
        assert_disjoint_seeds(train_ds, val_ds)
    cand, log = adapt_method(
        "finetune",
        source,
        source_replay,
        train_ds,
        epochs=epochs,
        seed=11 + 13 * model_seed + pair_i,
        episode_disjoint=True,
        allow_overlap_val=False,
        independent_val=val_ds if len(val_ds) else None,
    )
    return CandidatePair(
        pair_id=f"s{model_seed}_{spec.task_id}_{recipe}",
        model_seed=int(model_seed),
        spec=spec,
        recipe=recipe,
        incumbent=source,
        candidate=cand,
        train_n=int(log.get("train_n", len(train_ds))),
        val_n=int(log.get("val_n", len(val_ds))),
        independent_validation=bool(log.get("independent_validation")),
        checkpoint_rule=str(log.get("checkpoint_rule", "")),
        inc_hash=weights_hash(source),
        cand_hash=weights_hash(cand),
        collect_n=int(collect_n),
        val_collect_n=int(val_n),
        collect_interactions=int(train_ds.env_interactions + val_ds.env_interactions),
        train_seeds=[int(x) for x in np.unique(train_ds.seed).tolist()] if len(train_ds) else [],
        val_seeds=[int(x) for x in np.unique(val_ds.seed).tolist()] if len(val_ds) else [],
    )


def reference_eval(
    pair: CandidatePair,
    *,
    seed: int,
    horizon: int = V085_REF_HORIZON,
    n_episodes: int = V085_REF_EPISODES,
) -> dict[str, Any]:
    led = InteractionLedger(target_cap=0)
    cmp = matched_control_compare(
        pair.spec,
        pair.incumbent,
        pair.candidate,
        ledger=led,
        seed=int(seed),
        horizon=int(horizon),
        n_episodes=int(n_episodes),
        bucket="eval_only",
    )
    inc = [float(x) for x in cmp["incumbent_scores"]]
    cand = [float(x) for x in cmp["candidate_scores"]]
    label = classify_reference(inc, cand)
    diff = float(np.mean(cand) - np.mean(inc)) if inc and cand else float("nan")
    h = int(horizon)
    return {
        "incumbent_scores": inc,
        "candidate_scores": cand,
        "diff": diff,
        "label": label,
        "eval_only_steps": int(cmp["incumbent_steps"] + cmp["candidate_steps"]),
        "horizon": h,
        "n_episodes": int(n_episodes),
        "ceiling_both": bool(inc and cand and all(s >= h - 1e-6 for s in inc + cand)),
    }


def verify_pair(pair: CandidatePair, vname: str, vspec: dict[str, Any], *, gate_seed: int) -> dict[str, Any]:
    cap = int(vspec["cap"])
    led = InteractionLedger(target_cap=max(cap, 0))
    gname = vname if vname in ("never", "always", "mae") else "control"
    inp = GateInput(
        spec=pair.spec,
        incumbent=pair.incumbent,
        candidate=pair.candidate,
        ledger=led,
        seed=int(gate_seed),
        horizon=int(vspec["horizon"] or CONTROL_VAL_HORIZON),
        n_episodes=max(int(vspec["n_episodes"]), 1),
        min_improve=MIN_IMPROVE,
    )
    out = run_gate(gname, inp)
    out["ledger"] = led.snapshot()
    out["verifier"] = vname
    out["pair_id"] = pair.pair_id
    out["pair_ids_hash"] = pair.pair_id
    out["inc_hash"] = pair.inc_hash
    out["cand_hash"] = pair.cand_hash
    return out


def _summarize_labels(rows: list[dict[str, Any]]) -> dict[str, int]:
    c = {"benefit": 0, "harm": 0, "inconclusive": 0, "unresolved": 0}
    for r in rows:
        lab = str(r.get("label", "unresolved"))
        c[lab] = c.get(lab, 0) + 1
    return c


def _verifier_quality(decisions: list[dict[str, Any]], refs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    n = len(decisions)
    n_acc = n_inconcl = n_insuf = 0
    n_acc_ben = n_acc_harm = n_acc_unres = n_rej_ben = 0
    choice_diffs: list[float] = []
    ceil = 0
    val_steps = []
    for d in decisions:
        pid = d["pair_id"]
        ref = refs[pid]
        dec = d["decision"]
        reason = d.get("reason", "")
        if d.get("ceiling_both"):
            ceil += 1
        val_steps.append(int(d.get("val_incumbent_steps", 0)) + int(d.get("val_candidate_steps", 0)))
        if reason in ("insufficient_budget", "insufficient_evidence"):
            n_insuf += 1
        if reason == "tie_or_small_diff":
            n_inconcl += 1
        if dec == "accept":
            n_acc += 1
            if ref["label"] == "benefit":
                n_acc_ben += 1
            elif ref["label"] == "harm":
                n_acc_harm += 1
            else:
                n_acc_unres += 1
            choice_diffs.append(float(ref["diff"]))
        else:
            if ref["label"] == "benefit":
                n_rej_ben += 1
            choice_diffs.append(0.0)
    hs = harm_status(n_accept=n_acc, n_harmful_accept=n_acc_harm, n_unresolved_accept=n_acc_unres)
    return {
        "n_pairs": n,
        "n_accept": n_acc,
        "acceptance_rate": float(n_acc) / n if n else 0.0,
        "inconclusive_rate": float(n_inconcl) / n if n else 0.0,
        "insufficient_rate": float(n_insuf) / n if n else 0.0,
        "ceiling_both_rate": float(ceil) / n if n else 0.0,
        "accepted_supported_benefit": n_acc_ben,
        "accepted_supported_harm": n_acc_harm,
        "rejected_supported_benefit": n_rej_ben,
        "unresolved_reference_on_accept": n_acc_unres,
        "mean_choice_minus_never": float(np.mean(choice_diffs)) if choice_diffs else 0.0,
        "mean_val_steps": float(np.mean(val_steps)) if val_steps else 0.0,
        "harm": hs,
    }


def _select_verifier(dev_quality: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """Development-only. Maximize (accepted benefit − accepted harm); cheaper on ties. No confirm data."""
    labels_have_benefit = any(q["accepted_supported_benefit"] + q["rejected_supported_benefit"] > 0 for q in dev_quality.values())
    # rejected_supported_benefit + accepted is total benefit; use that from never's rejected_supported_benefit
    n_ben = int(dev_quality["never"]["rejected_supported_benefit"])  # never accepts 0, so all benefits are "rejected"
    if n_ben <= 0 and not labels_have_benefit:
        return "never", "no_dev_benefit_candidates"
    best: tuple[int, int, str] | None = None
    for name, q in dev_quality.items():
        score = int(q["accepted_supported_benefit"]) - int(q["accepted_supported_harm"])
        cost = int(round(float(q["mean_val_steps"])))
        key = (score, -cost, name)
        if best is None or (key[0], key[1]) > (best[0], best[1]) or ((key[0], key[1]) == (best[0], best[1]) and name < best[2]):
            best = (score, -cost, name)
    assert best is not None
    return best[2], "max_tp_minus_fp_then_cheaper"


def run_v085_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    artifact_path: str | Path | None = "artifacts/v085_verification.json",
    checkpoint_dir: str | Path = "checkpoints/v085",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    recipes = RECIPES
    ref_h, ref_ep = V085_REF_HORIZON, V085_REF_EPISODES
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        n_model_seeds = min(n_model_seeds, 1)
        recipes = (("c24", 24, 16),)
        ref_h, ref_ep = 24, 1
    source_spec = source_policy_task()
    dev = v085_development_target()
    confirms = v085_confirmation_targets()
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()

    protocol = {
        "code_version": "v0.8.5",
        "parent_commit": "4158b4f",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "ref_horizon": V085_REF_HORIZON,
        "ref_episodes": V085_REF_EPISODES,
        "ref_margin": V085_REF_MARGIN,
        "min_improve_gate": MIN_IMPROVE,
        "verifiers": [n for n, _ in VERIFIER_SPECS],
        "recipes": [r[0] for r in recipes],
        "n_model_seeds": n_model_seeds,
        "adapt_epochs": adapt_epochs,
        "confirm_ref_seed": V085_CONFIRM_REF_SEED,
        "dev_ref_seed": V085_DEV_REF_SEED,
        "gate_seed": V085_GATE_SEED,
        "selection_split": "dev_v085",
        "retuned_on_confirmation": False,
        "reference_feeds_gate": False,
        "planned_runtime_note": "n=10, 2 recipes, 1 dev + 3 confirm tasks; H=500×2 reference eval_only; expect ~10–25 min CPU",
        "is_agi": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    def _process(spec: TaskSpec, source: WorldModel, train: Any, mseed: int, ref_seed: int) -> tuple[list[CandidatePair], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        pairs: list[CandidatePair] = []
        refs: dict[str, dict[str, Any]] = {}
        gates: dict[str, list[dict[str, Any]]] = {n: [] for n, _ in VERIFIER_SPECS}
        for pi, (rname, cn, vn) in enumerate(recipes):
            pair = generate_pair(spec, source, train, model_seed=mseed, recipe=rname, collect_n=cn, val_n=vn, epochs=adapt_epochs, pair_i=pi)
            pairs.append(pair)
            refs[pair.pair_id] = reference_eval(pair, seed=ref_seed + 17 * pi, horizon=ref_h, n_episodes=ref_ep)
            for vname, vspec in VERIFIER_SPECS:
                gates[vname].append(verify_pair(pair, vname, vspec, gate_seed=V085_GATE_SEED + 31 * mseed + 5 * pi))
        return pairs, refs, gates

    per_seed: list[dict[str, Any]] = []
    all_dev_refs: list[dict[str, Any]] = []
    all_dev_gates: dict[str, list[dict[str, Any]]] = {n: [] for n, _ in VERIFIER_SPECS}
    all_conf_refs: list[dict[str, Any]] = []
    all_conf_gates: dict[str, list[dict[str, Any]]] = {n: [] for n, _ in VERIFIER_SPECS}

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V085_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V085_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]

        d_pairs, d_refs, d_gates = _process(dev, source, train, mseed, V085_DEV_REF_SEED)
        for r in d_refs.values():
            all_dev_refs.append(r)
        for n, rows in d_gates.items():
            all_dev_gates[n].extend(rows)

        c_task_rows = []
        for spec in confirms:
            c_pairs, c_refs, c_gates = _process(spec, source, train, mseed, V085_CONFIRM_REF_SEED)
            for r in c_refs.values():
                all_conf_refs.append({**r, "task_id": spec.task_id, "model_seed": mseed})
            for n, rows in c_gates.items():
                all_conf_gates[n].extend(rows)
            c_task_rows.append(
                {
                    "task_id": spec.task_id,
                    "params": dict(spec.params),
                    "pairs": [
                        {
                            "pair_id": p.pair_id,
                            "recipe": p.recipe,
                            "independent_validation": p.independent_validation,
                            "checkpoint_rule": p.checkpoint_rule,
                            "train_n": p.train_n,
                            "val_n": p.val_n,
                            "collect_interactions": p.collect_interactions,
                            "inc_hash": p.inc_hash,
                            "cand_hash": p.cand_hash,
                            "ref": c_refs[p.pair_id],
                            "gates": {vn: next(g for g in c_gates[vn] if g["pair_id"] == p.pair_id) for vn, _ in VERIFIER_SPECS},
                        }
                        for p in c_pairs
                    ],
                }
            )

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "dev_pairs": [
                    {
                        "pair_id": p.pair_id,
                        "recipe": p.recipe,
                        "independent_validation": p.independent_validation,
                        "checkpoint_rule": p.checkpoint_rule,
                        "collect_interactions": p.collect_interactions,
                        "inc_hash": p.inc_hash,
                        "cand_hash": p.cand_hash,
                        "ref": d_refs[p.pair_id],
                    }
                    for p in d_pairs
                ],
                "confirmation": c_task_rows,
            }
        )
        print(f"v085 seed={mseed}", flush=True)

    # Freeze verifier from development only (already computed; confirm not used here).
    dev_q = {n: _verifier_quality(all_dev_gates[n], {p["pair_id"]: p["ref"] for s in per_seed for p in s["dev_pairs"]}) for n, _ in VERIFIER_SPECS}
    selected, sel_reason = _select_verifier(dev_q)
    protocol["selected_verifier"] = selected
    protocol["selection_reason"] = sel_reason

    conf_ref_map = {p["pair_id"]: p["ref"] for s in per_seed for task in s["confirmation"] for p in task["pairs"]}
    conf_q = {n: _verifier_quality(all_conf_gates[n], conf_ref_map) for n, _ in VERIFIER_SPECS}

    noisy_ids = [t.task_id for t in confirms if "noisy" in t.task_id] or [t.task_id for t in confirms]
    per_seed_diff = []
    per_seed_choice = {n: [] for n, _ in VERIFIER_SPECS}
    for s in per_seed:
        diffs = []
        ch: dict[str, list[float]] = {n: [] for n, _ in VERIFIER_SPECS}
        for task in s["confirmation"]:
            if noisy_ids and task["task_id"] not in noisy_ids and any("noisy" in x for x in noisy_ids):
                continue
            if "noisy" not in task["task_id"] and any("noisy" in t.task_id for t in confirms):
                continue
            for p in task["pairs"]:
                diffs.append(float(p["ref"]["diff"]))
                for n, _ in VERIFIER_SPECS:
                    acc = p["gates"][n]["decision"] == "accept"
                    ch[n].append(float(p["ref"]["diff"]) if acc else 0.0)
        if diffs:
            per_seed_diff.append(float(np.mean(diffs)))
        for n, _ in VERIFIER_SPECS:
            if ch[n]:
                per_seed_choice[n].append(float(np.mean(ch[n])))

    h1 = {
        "n_pairs": len(all_conf_refs),
        "label_counts": _summarize_labels(all_conf_refs),
        "paired_diff_per_seed": seed_level_ci(per_seed_diff),
        "fraction_ceiling": float(np.mean([1.0 if r.get("ceiling_both") else 0.0 for r in all_conf_refs])) if all_conf_refs else 0.0,
        "replication_unit": "source_training_seed",
        "clustering_note": "Pairs from one source seed are clustered; CIs use per-seed means.",
    }
    h2 = {
        "selected_verifier": selected,
        "selection_reason": sel_reason,
        "dev": dev_q,
        "confirmation": conf_q,
        "choice_vs_never_per_seed": {n: seed_level_ci(per_seed_choice[n]) for n, _ in VERIFIER_SPECS},
    }

    payload = {
        "protocol": protocol,
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "h1_candidate_quality": h1,
        "h2_verifier_quality": h2,
        "costs": {
            "mean_pretrain": float(np.mean([p["pretrain"] for p in per_seed])) if per_seed else 0.0,
            "mean_collect_per_pair": float(
                np.mean([p["collect_interactions"] for s in per_seed for task in s["confirmation"] for p in task["pairs"]])
            )
            if per_seed
            else 0.0,
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.5 CartPole candidate/verifier diagnostic. Not AGI. Rejection-only is not verifier success.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
