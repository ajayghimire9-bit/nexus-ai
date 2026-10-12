"""V0.8.6 safer candidate generation. Frozen V0.8.5 MAE gate. Not AGI."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v086_confirmation_targets,
    v086_development_target,
    v086_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import finetune_world_model, interpolate_world_models
from nexus.world.agent import InteractionLedger, _mae, collect_planned_belief, plan_with_belief
from nexus.world.belief import IdentityBelief
from nexus.world.data import assert_disjoint_seeds, collect_transitions, concat_datasets
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.imagine import multi_step_errors
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import (
    V086_CONFIRM_REF_SEED,
    V086_DEV_REF_SEED,
    V086_GATE_SEED,
    V086_ONPOLICY_SEED,
    V086_SEQUENCE_EVAL_SEED,
    V086_SOURCE_COLLECT_SEED,
    V086_TARGET_COLLECT_SEED,
    V086_VAL_COLLECT_SEED,
)
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import CandidatePair, _git_meta, _summarize_labels, _verifier_quality, reference_eval, verify_pair
from nexus.world.verify import (
    GateInput,
    V085_MAE_RATIO,
    V085_MAE_STEPS,
    V085_REF_EPISODES,
    V085_REF_HORIZON,
    V085_REF_MARGIN,
    mpc_action_disagreement,
    run_gate,
    weights_hash,
)

MethodName = Literal["finetune", "low_lr", "early_stop", "replay", "interpolate"]
METHODS: tuple[MethodName, ...] = ("finetune", "low_lr", "early_stop", "replay", "interpolate")
RECIPES: tuple[tuple[str, int, int], ...] = (("c128", 128, 64), ("c256", 256, 64))
V086_FT_LR = 5e-4
V086_LOW_LR = 1e-4
V086_ALPHA = 0.5
V086_PATIENCE = 2
ONPOLICY_N = 32
MAE_VERIFIER = ("mae", {"horizon": 0, "n_episodes": 0, "cap": V085_MAE_STEPS})
ALWAYS_VERIFIER = ("always", {"horizon": 0, "n_episodes": 0, "cap": 0})
NEVER_VERIFIER = ("never", {"horizon": 0, "n_episodes": 0, "cap": 0})
GATES = (NEVER_VERIFIER, ALWAYS_VERIFIER, MAE_VERIFIER)


def collect_matched(
    spec: TaskSpec,
    source: Any,
    *,
    model_seed: int,
    pair_i: int,
    collect_n: int,
    val_n: int,
) -> tuple[Any, Any]:
    tr_seeds = tuple(range(50 + 40 * model_seed + 7 * pair_i, 58 + 40 * model_seed + 7 * pair_i))
    va_seeds = tuple(range(900 + 40 * model_seed + 7 * pair_i, 908 + 40 * model_seed + 7 * pair_i))
    train_ds = collect_planned_belief(
        spec, source, IdentityBelief(), collect_n, env_seeds=tr_seeds, base_seed=V086_TARGET_COLLECT_SEED + 19 * model_seed + 3 * pair_i
    )
    val_ds = collect_planned_belief(
        spec, source, IdentityBelief(), val_n, env_seeds=va_seeds, base_seed=V086_VAL_COLLECT_SEED + 19 * model_seed + 3 * pair_i
    )
    if len(train_ds) and len(val_ds):
        assert_disjoint_seeds(train_ds, val_ds)
    return train_ds, val_ds


def apply_method(
    method: MethodName,
    source: Any,
    source_replay: Any,
    train_ds: Any,
    val_ds: Any,
    *,
    epochs: int,
    seed: int,
) -> tuple[Any, dict[str, Any]]:
    lr = V086_LOW_LR if method == "low_lr" else V086_FT_LR
    patience = V086_PATIENCE if method == "early_stop" else None
    tr = train_ds
    if method == "replay" and len(source_replay) and len(train_ds):
        rng = np.random.default_rng(seed)
        n_src = min(len(source_replay), len(train_ds))
        idx = rng.choice(len(source_replay), size=n_src, replace=False)
        tr = concat_datasets(source_replay.slice(idx), train_ds, task_id="replay_mix")
    cand, log = finetune_world_model(
        source, tr, val_ds, epochs=epochs, seed=seed, lr=lr, select_by_val=len(val_ds) > 0, patience=patience
    )
    log["method"] = method
    log["train_n"] = len(tr)
    log["val_n"] = len(val_ds)
    if method == "interpolate":
        cand = interpolate_world_models(source, cand, alpha=V086_ALPHA)
        log["alpha"] = V086_ALPHA
        log["checkpoint_rule"] = f"interpolate_{V086_ALPHA}_after_{log.get('checkpoint_rule')}"
    return cand, log


def diagnostics(spec: TaskSpec, incumbent: Any, candidate: Any, val_ds: Any, *, seed: int) -> dict[str, Any]:
    pred = {}
    if len(val_ds):
        pred["val_one_step_mae_inc"] = one_step_errors(incumbent, val_ds)["mae"]
        pred["val_one_step_mae_cand"] = one_step_errors(candidate, val_ds)["mae"]
        ms_i = multi_step_errors(incumbent, val_ds, (1, 3, 8))
        ms_c = multi_step_errors(candidate, val_ds, (1, 3, 8))
        pred["val_multi_step_inc"] = {str(k): ms_i[k] for k in ms_i}
        pred["val_multi_step_cand"] = {str(k): ms_c[k] for k in ms_c}
    led = InteractionLedger(target_cap=0)
    onpol = collect_planned_belief(
        spec, candidate, IdentityBelief(), ONPOLICY_N, env_seeds=(int(seed), int(seed) + 1), base_seed=V086_ONPOLICY_SEED + int(seed)
    )
    led.charge(int(onpol.env_interactions), "eval_only")
    on_mae_c = float(_mae(candidate, onpol)) if len(onpol) else None
    on_mae_i = float(_mae(incumbent, onpol)) if len(onpol) else None
    disag = mpc_action_disagreement(incumbent, candidate, val_ds.obs if len(val_ds) else onpol.obs, seed=seed)
    return {
        "prediction": pred,
        "on_policy_mae_incumbent": on_mae_i,
        "on_policy_mae_candidate": on_mae_c,
        "on_policy_minus_incumbent": None if on_mae_c is None or on_mae_i is None else float(on_mae_c - on_mae_i),
        "action_disagreement": disag,
        "onpolicy_eval_only_steps": int(onpol.env_interactions),
        "covers_shift_hypothesis": bool(on_mae_c is not None and on_mae_i is not None and on_mae_c > on_mae_i),
    }


def make_pair(
    spec: TaskSpec,
    source: Any,
    train_ds: Any,
    val_ds: Any,
    cand: Any,
    log: dict[str, Any],
    *,
    model_seed: int,
    recipe: str,
    method: str,
) -> CandidatePair:
    return CandidatePair(
        pair_id=f"s{model_seed}_{spec.task_id}_{recipe}_{method}",
        model_seed=int(model_seed),
        spec=spec,
        recipe=f"{recipe}:{method}",
        incumbent=source,
        candidate=cand,
        train_n=int(log.get("train_n", len(train_ds))),
        val_n=int(log.get("val_n", len(val_ds))),
        independent_validation=bool(log.get("independent_validation")),
        checkpoint_rule=str(log.get("checkpoint_rule", "")),
        inc_hash=weights_hash(source),
        cand_hash=weights_hash(cand),
        collect_n=len(train_ds),
        val_collect_n=len(val_ds),
        collect_interactions=int(train_ds.env_interactions + val_ds.env_interactions),
        train_seeds=[int(x) for x in np.unique(train_ds.seed).tolist()] if len(train_ds) else [],
        val_seeds=[int(x) for x in np.unique(val_ds.seed).tolist()] if len(val_ds) else [],
    )


def run_safe_online(
    spec: TaskSpec,
    source: Any,
    source_replay: Any,
    method: MethodName,
    *,
    target_cap: int,
    epochs: int,
    seed: int,
    gate: str,
) -> dict[str, Any]:
    """One-cycle online: collect → generate with ``method`` → frozen MAE/always/never → maybe commit."""
    deployed = source.clone()
    ledger = InteractionLedger(target_cap=int(target_cap))
    costs = {"collect_train": 0, "collect_val": 0, "verifier": 0, "eval_only": 0}
    if target_cap <= 0:
        return {"model": deployed, "ledger": ledger.snapshot(), "n_accept": 0, "costs": costs, "gate": gate, "method": method}
    mae_need = V085_MAE_STEPS if gate == "mae" else 0
    val_n = 32 if target_cap >= mae_need + 48 else 0
    train_n = max(16, int(target_cap) - val_n - mae_need)
    train_ds = collect_planned_belief(
        spec, deployed, IdentityBelief(), train_n, env_seeds=tuple(range(int(seed), int(seed) + 8)), base_seed=seed
    )
    ledger.charge(int(train_ds.env_interactions), "adapt_collect")
    costs["collect_train"] = int(train_ds.env_interactions)
    val_ds = collect_planned_belief(
        spec, deployed, IdentityBelief(), val_n, env_seeds=tuple(range(int(seed) + 80, int(seed) + 88)), base_seed=seed + 1
    )
    if len(val_ds):
        ledger.charge(int(val_ds.env_interactions), "adapt_collect")
        costs["collect_val"] = int(val_ds.env_interactions)
    cand, log = apply_method(method, deployed, source_replay, train_ds, val_ds, epochs=epochs, seed=seed + 3)
    n_accept = 0
    reason = "none"
    if gate == "always":
        deployed = cand
        n_accept = 1
        reason = "always"
    elif gate == "mae":
        g = run_gate("mae", GateInput(spec=spec, incumbent=deployed, candidate=cand, ledger=ledger, seed=seed + 9))
        costs["verifier"] = int(g.get("val_incumbent_steps", 0))
        reason = str(g.get("reason"))
        if g["decision"] == "accept":
            deployed = cand
            n_accept = 1
    else:
        reason = "never"
    return {
        "model": deployed,
        "ledger": ledger.snapshot(),
        "n_accept": n_accept,
        "reason": reason,
        "costs": costs,
        "gate": gate,
        "method": method,
        "train_log": {k: log[k] for k in log if k != "history"},
        "committed_hash": weights_hash(deployed),
    }


def _select_method(dev_by_method: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """Min harm fraction, then max benefit, then max MAE-gated choice. Dev only."""
    best: tuple[float, float, float, str] | None = None
    for name, q in dev_by_method.items():
        n = max(int(q["n_pairs"]), 1)
        harm = float(q["label_counts"]["harm"]) / n
        ben = float(q["label_counts"]["benefit"]) / n
        choice = float(q["mae_choice_mean"])
        key = (-harm, ben, choice, name)
        if best is None or key[:3] > best[:3] or (key[:3] == best[:3] and name < best[3]):
            best = (-harm, ben, choice, name)
    assert best is not None
    return best[3], "min_harm_then_max_benefit_then_mae_choice"


def _method_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = _summarize_labels([r["ref"] for r in rows])
    n = len(rows)
    mae_choice = []
    mae_acc_harm = 0
    mae_acc = 0
    for r in rows:
        acc = r["gates"]["mae"]["decision"] == "accept"
        if acc:
            mae_acc += 1
            mae_choice.append(float(r["ref"]["diff"]))
            if r["ref"]["label"] == "harm":
                mae_acc_harm += 1
        else:
            mae_choice.append(0.0)
    return {
        "n_pairs": n,
        "label_counts": labels,
        "harm_frac": float(labels["harm"]) / n if n else 0.0,
        "benefit_frac": float(labels["benefit"]) / n if n else 0.0,
        "mae_choice_mean": float(np.mean(mae_choice)) if mae_choice else 0.0,
        "mae_n_accept": mae_acc,
        "mae_accepted_harm": mae_acc_harm,
        "mae_harm_among_accept": (float(mae_acc_harm) / mae_acc) if mae_acc else "not_applicable",
    }


def run_v086_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    artifact_path: str | Path | None = "artifacts/v086_candidates.json",
    checkpoint_dir: str | Path = "checkpoints/v086",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    recipes = RECIPES
    methods: tuple[MethodName, ...] = METHODS
    ref_h, ref_ep = V085_REF_HORIZON, V085_REF_EPISODES
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        n_model_seeds = min(n_model_seeds, 1)
        recipes = (("c24", 24, 16),)
        methods = ("finetune", "low_lr", "interpolate")
        ref_h, ref_ep = 24, 1
    source_spec = source_policy_task()
    dev = v086_development_target()
    confirms = v086_confirmation_targets()
    seq = v086_sequence_tasks()
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()
    protocol = {
        "code_version": "v0.8.6",
        "parent_commit": "cf6780e",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "methods": list(methods),
        "ft_lr": V086_FT_LR,
        "low_lr": V086_LOW_LR,
        "interpolate_alpha": V086_ALPHA,
        "early_stop_patience": V086_PATIENCE,
        "mae_ratio": V085_MAE_RATIO,
        "mae_steps": V085_MAE_STEPS,
        "ref_horizon": ref_h,
        "ref_episodes": ref_ep,
        "ref_margin": V085_REF_MARGIN,
        "recipes": [r[0] for r in recipes],
        "n_model_seeds": n_model_seeds,
        "adapt_epochs": adapt_epochs,
        "confirm_ref_seed": V086_CONFIRM_REF_SEED,
        "dev_ref_seed": V086_DEV_REF_SEED,
        "gate_seed": V086_GATE_SEED,
        "selection_split": "dev_v086",
        "retuned_mae": False,
        "retuned_on_v085_confirm": False,
        "reference_feeds_gate": False,
        "planned_runtime_note": "n=10, 2 recipes, 5 methods, 1 dev + 3 confirm + A-B-C-A; ~8–15 min CPU",
        "is_agi": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    dev_rows: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    held: list[dict[str, Any]] = []

    def _make_bank(spec: TaskSpec, source: Any, replay: Any, pretrain: int, mseed: int, ref_seed: int) -> list[dict[str, Any]]:
        out_rows: list[dict[str, Any]] = []
        for pi, (rname, cn, vn) in enumerate(recipes):
            train_ds, val_ds = collect_matched(spec, source, model_seed=mseed, pair_i=pi, collect_n=cn, val_n=vn)
            for mi, method in enumerate(methods):
                cand, log = apply_method(method, source, replay, train_ds, val_ds, epochs=adapt_epochs, seed=11 + 13 * mseed + 7 * mi + pi)
                pair = make_pair(spec, source, train_ds, val_ds, cand, log, model_seed=mseed, recipe=rname, method=method)
                ref = reference_eval(pair, seed=ref_seed + 17 * pi + mi, horizon=ref_h, n_episodes=ref_ep)
                diag = diagnostics(spec, source, cand, val_ds, seed=mseed * 100 + pi * 10 + mi)
                gates = {vname: verify_pair(pair, vname, vspec, gate_seed=V086_GATE_SEED + 31 * mseed + 5 * pi + mi) for vname, vspec in GATES}
                out_rows.append(
                    {
                        "pair_id": pair.pair_id,
                        "method": method,
                        "recipe": rname,
                        "matched_collect": True,
                        "independent_validation": pair.independent_validation,
                        "checkpoint_rule": pair.checkpoint_rule,
                        "epochs_run": log.get("epochs_run"),
                        "lr": log.get("lr"),
                        "collect_train": int(train_ds.env_interactions),
                        "collect_val": int(val_ds.env_interactions),
                        "inc_hash": pair.inc_hash,
                        "cand_hash": pair.cand_hash,
                        "ref": ref,
                        "diagnostics": diag,
                        "gates": gates,
                        "costs": {
                            "pretrain": pretrain,
                            "collect_train": int(train_ds.env_interactions),
                            "collect_val": int(val_ds.env_interactions),
                            "verifier": int(gates["mae"]["val_incumbent_steps"]),
                            "onpolicy_eval_only": int(diag["onpolicy_eval_only_steps"]),
                            "reference_eval_only": int(ref["eval_only_steps"]),
                        },
                    }
                )
        return out_rows

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V086_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V086_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        d_rows = _make_bank(dev, source, train, pretrain, mseed, V086_DEV_REF_SEED)
        for r in d_rows:
            dev_rows[r["method"]].append(r)
        held.append({"mseed": mseed, "train": train, "val": val, "source": source, "slog": slog, "pretrain": pretrain, "d_rows": d_rows})
        print(f"v086 dev seed={mseed}", flush=True)

    dev_stats = {m: _method_stats(dev_rows[m]) for m in methods}
    selected, sel_reason = _select_method(dev_stats)
    protocol["selected_method"] = selected
    protocol["selection_reason"] = sel_reason
    protocol["sequence_generator"] = selected
    sel_method: MethodName = selected  # type: ignore[assignment]

    seq_budget = 24 if quick else 128
    for item in held:
        mseed = int(item["mseed"])
        train, val, source = item["train"], item["val"], item["source"]
        pretrain = int(item["pretrain"])
        c_tasks = [{"task_id": spec.task_id, "params": dict(spec.params), "pairs": _make_bank(spec, source, train, pretrain, mseed, V086_CONFIRM_REF_SEED)} for spec in confirms]
        memory = PredictiveMemory(max_entries=6, replay_cap=n_train + seq_budget)
        memory.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        names = ("A", "B", "C", "A_return")
        specs_l = (seq[0], seq[1], seq[2], seq[0])
        shared_always = source.clone()
        shared_mae = source.clone()
        seq_log = []
        for ti, (sp, name) in enumerate(zip(specs_l, names)):
            never_l = run_safe_online(sp, source, train, sel_method, target_cap=seq_budget, epochs=adapt_epochs, seed=V086_SEQUENCE_EVAL_SEED + ti, gate="never")
            alw = run_safe_online(sp, shared_always, train, sel_method, target_cap=seq_budget, epochs=adapt_epochs, seed=V086_SEQUENCE_EVAL_SEED + 20 + ti, gate="always")
            gat = run_safe_online(sp, shared_mae, train, sel_method, target_cap=seq_budget, epochs=adapt_epochs, seed=V086_SEQUENCE_EVAL_SEED + 40 + ti, gate="mae")
            shared_always = alw["model"]
            shared_mae = gat["model"]
            retrieved, meta = memory.retrieve(val.slice(np.arange(min(16, len(val)))))
            memory.store(shared_mae, val.slice(np.arange(min(16, len(val)))), stats={"stage": name}, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            n_ep = 1 if quick else 2
            seq_log.append(
                {
                    "stage": name,
                    "never": plan_with_belief(eval_sp, never_l["model"], IdentityBelief(), seed=V086_SEQUENCE_EVAL_SEED, episodes=n_ep),
                    "naive_shared": plan_with_belief(eval_sp, shared_always, IdentityBelief(), seed=V086_SEQUENCE_EVAL_SEED, episodes=n_ep),
                    "gated_shared": plan_with_belief(eval_sp, shared_mae, IdentityBelief(), seed=V086_SEQUENCE_EVAL_SEED, episodes=n_ep),
                    "snapshot": plan_with_belief(eval_sp, source, IdentityBelief(), seed=V086_SEQUENCE_EVAL_SEED, episodes=n_ep),
                    "retrieved": plan_with_belief(eval_sp, retrieved or source, IdentityBelief(), seed=V086_SEQUENCE_EVAL_SEED, episodes=n_ep),
                    "retrieval": meta,
                    "always_accept": alw["n_accept"],
                    "mae_accept": gat["n_accept"],
                    "always_hash": alw["committed_hash"],
                    "mae_hash": gat["committed_hash"],
                    "source_hash": weights_hash(source),
                    "never_ledger": never_l["ledger"],
                    "always_ledger": alw["ledger"],
                    "mae_ledger": gat["ledger"],
                }
            )
        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": item["slog"]["best_val"],
                "dev": item["d_rows"],
                "confirmation": c_tasks,
                "continual": seq_log,
            }
        )
        print(f"v086 confirm seed={mseed} selected={selected}", flush=True)

    conf_by_m: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    noisy_by_m: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    for s in per_seed:
        for task in s["confirmation"]:
            for r in task["pairs"]:
                conf_by_m[r["method"]].append(r)
                if "noisy" in task["task_id"]:
                    noisy_by_m[r["method"]].append(r)

    def _seed_choice(method: str, gate: str, noisy: bool) -> list[float]:
        xs = []
        for s in per_seed:
            diffs = []
            for task in s["confirmation"]:
                if noisy and "noisy" not in task["task_id"]:
                    continue
                if not noisy and "noisy" in task["task_id"]:
                    continue
                for r in task["pairs"]:
                    if r["method"] != method:
                        continue
                    acc = r["gates"][gate]["decision"] == "accept"
                    diffs.append(float(r["ref"]["diff"]) if acc else 0.0)
            if diffs:
                xs.append(float(np.mean(diffs)))
        return xs

    def _seed_raw(method: str, noisy: bool) -> list[float]:
        xs = []
        for s in per_seed:
            diffs = []
            for task in s["confirmation"]:
                if noisy and "noisy" not in task["task_id"]:
                    continue
                for r in task["pairs"]:
                    if r["method"] != method:
                        continue
                    diffs.append(float(r["ref"]["diff"]))
            if diffs:
                xs.append(float(np.mean(diffs)))
        return xs

    confirm_stats = {m: _method_stats(conf_by_m[m]) for m in methods}
    noisy_stats = {m: _method_stats(noisy_by_m[m]) for m in methods}

    payload = {
        "protocol": protocol,
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "dev_method_stats": dev_stats,
        "confirm_method_stats": confirm_stats,
        "noisy_method_stats": noisy_stats,
        "primary": {
            "selected_method": selected,
            "noisy_harm_frac": noisy_stats[selected]["harm_frac"],
            "noisy_benefit_frac": noisy_stats[selected]["benefit_frac"],
            "mae_choice_vs_never": seed_level_ci(_seed_choice(selected, "mae", True)),
            "always_choice_vs_never": seed_level_ci(_seed_choice(selected, "always", True)),
            "raw_delta": seed_level_ci(_seed_raw(selected, True)),
            "mae_harm_among_accept": noisy_stats[selected]["mae_harm_among_accept"],
        },
        "paired_mae_choice_all_methods": {m: seed_level_ci(_seed_choice(m, "mae", True)) for m in methods},
        "continual_return_to_A": {
            "never": seed_level_ci([float(p["continual"][-1]["never"]["mean_return"]) for p in per_seed]),
            "naive_shared": seed_level_ci([float(p["continual"][-1]["naive_shared"]["mean_return"]) for p in per_seed]),
            "gated_shared": seed_level_ci([float(p["continual"][-1]["gated_shared"]["mean_return"]) for p in per_seed]),
            "snapshot": seed_level_ci([float(p["continual"][-1]["snapshot"]["mean_return"]) for p in per_seed]),
            "retrieved": seed_level_ci([float(p["continual"][-1]["retrieved"]["mean_return"]) for p in per_seed]),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.6 safer generation on CartPole. Not AGI. MAE threshold frozen from V0.8.5.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
