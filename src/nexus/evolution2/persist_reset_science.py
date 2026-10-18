"""One-run n=3 persist-versus-reset scientific screen. Locked protocol.

Collects fresh unused-role physics, fits six residuals, and compares
persist/reset/random/evolution on three bundles. Does not rewrite frozen
request hashes. Does not promote n=3 to n=10. Does not start Evolution-3.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.evolution1.catalogue import catalogue
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.evaluator_dry_run import decode_action
from nexus.evolution2.methods import make_methods
from nexus.evolution2.pendulum_acrobot_instance_rules import ROLE_ORDER
from nexus.evolution2.pendulum_acrobot_protocol import physics_key
from nexus.evolution2.pendulum_acrobot_protocol_n3_micro import (
    BONFERRONI_T_CRIT_DF2,
    DEVELOPMENT_CONDITIONS,
    EXPLORATORY_T_CRIT_95_DF2,
    N_BUNDLES,
    PRACTICAL_MARGIN,
    REVEALED_VARIANTS_PER_FAMILY,
    student_t_interval,
)
from nexus.evolution2.pendulum_acrobot_protocol_v2 import (
    EPISODE_STEPS,
    SOURCE_TRAIN_STEPS,
    SOURCE_VAL_STEPS,
    bundle_family_order,
    paired_bundle_seeds,
)
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import decide
from nexus.evolution2.screen import SHARED_PROBES, feedback_event
from nexus.evolution2.source_persist_plan import atomic_write_npz
from nexus.evolution2.tasks import PROPOSALS
from nexus.tasks.pendulum_family import PENDULUM_TORQUE_NEG, PENDULUM_TORQUE_POS, PENDULUM_TORQUE_ZERO
from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions
from nexus.world.train import train_world_model

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_science.json"
USAGE = ROOT / "artifacts" / "research_session_e2_persist_reset_science_usage.json"
ARRAY_ROOT = ROOT / "artifacts" / "evolution2_persist_reset_science_arrays"
FIT_ROOT = ROOT / "artifacts" / "evolution2_persist_reset_science_fits"
METHODS = ("persist", "reset", "random", "evolution")
METHOD_KEYS = {
    "persist": "persistent_adaptive",
    "reset": "reset_adaptive",
    "random": "random",
    "evolution": "evolutionary",
}


def locked_split():
    variants = catalogue()
    hidden = (variants[5], variants[11])
    anchors = (variants[2], variants[8])
    revealed = anchors + (variants[0], variants[1], variants[6], variants[7])
    if len(revealed) != REVEALED_VARIANTS_PER_FAMILY:
        raise RuntimeError("revealed_split_mismatch")
    if len(hidden) != DEVELOPMENT_CONDITIONS:
        raise RuntimeError("hidden_split_mismatch")
    if any(item in hidden for item in anchors):
        raise RuntimeError("anchor_hidden")
    return {"revealed": revealed, "hidden": hidden, "anchors": anchors}


def role_spec(role: str, key: tuple[float, float, float]) -> TaskSpec:
    a, b, c = physics_key(key)
    if role.startswith("pendulum"):
        return TaskSpec(
            task_id=f"e2pr_{role}",
            family="pendulum",
            gym_id="Pendulum-v1",
            obs_dim=3,
            n_actions=3,
            params={
                "torque_neg": float(PENDULUM_TORQUE_NEG),
                "torque_zero": float(PENDULUM_TORQUE_ZERO),
                "torque_pos": float(PENDULUM_TORQUE_POS),
                "g": float(a),
                "m": float(b),
                "l": float(c),
            },
            train_split=role,
            notes="precommitted unused persist-versus-reset role",
        )
    return TaskSpec(
        task_id=f"e2pr_{role}",
        family="acrobot",
        gym_id="Acrobot-v1",
        obs_dim=6,
        n_actions=3,
        params={"LINK_MASS_1": float(a), "LINK_MASS_2": float(b), "LINK_LENGTH_1": float(c)},
        train_split=role,
        notes="precommitted unused persist-versus-reset role",
    )


def refuse_occupied_defaults(family: str, key: tuple[float, float, float]) -> None:
    default = (10.0, 1.0, 1.0) if family == "pendulum" else (1.0, 1.0, 1.0)
    if physics_key(key) == default:
        raise RuntimeError("occupied_default_reuse_forbidden")


class BudgetMeter:
    def __init__(self, env_cap: int, time_cap_s: float):
        self.env_cap = int(env_cap)
        self.time_cap_s = float(time_cap_s)
        self.env_steps = 0
        self.imagined = 0
        self.fits = 0
        self.started = time.perf_counter()
        self.cpu0 = time.process_time()
        self.interrupt = None

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def charge(self, steps: int, *, imagined: int = 0) -> None:
        if self.elapsed() >= self.time_cap_s:
            self.interrupt = "time_cap"
            raise RuntimeError("time_cap")
        if self.env_steps + int(steps) > self.env_cap:
            self.interrupt = "env_cap"
            raise RuntimeError("env_cap")
        self.env_steps += int(steps)
        self.imagined += int(imagined)


def _arrays(ds, *, family: str, bundle: int, split: str, key) -> dict:
    return {
        "obs": np.asarray(ds.obs, dtype=np.float32),
        "action": np.asarray(ds.action, dtype=np.int64),
        "next_obs": np.asarray(ds.next_obs, dtype=np.float32),
        "terminated": np.asarray(ds.terminated, dtype=np.bool_),
        "env_seeds": np.asarray(ds.seed, dtype=np.int64),
        "family": np.asarray(family),
        "bundle": np.asarray(bundle),
        "split": np.asarray(split),
        "task_id": np.asarray(ds.task_id),
        "physics": np.asarray(key, dtype=np.float64),
    }


def dataset_from_npz(path: Path, *, family: str, expected_n: int, key) -> TransitionDataset:
    data = np.load(path)
    n = int(data["obs"].shape[0])
    if n != int(expected_n):
        raise RuntimeError("array_length_mismatch")
    physics = physics_key(tuple(float(x) for x in np.asarray(data["physics"]).reshape(-1)))
    if physics != physics_key(key):
        raise RuntimeError("collected_physics_mismatch")
    refuse_occupied_defaults(family, physics)
    return TransitionDataset(
        obs=np.asarray(data["obs"], dtype=np.float32),
        action=np.asarray(data["action"], dtype=np.int64),
        next_obs=np.asarray(data["next_obs"], dtype=np.float32),
        reward=np.zeros(n, dtype=np.float32),
        terminated=np.asarray(data["terminated"], dtype=np.bool_),
        truncated=np.zeros(n, dtype=np.bool_),
        task_id=str(np.asarray(data["task_id"]).reshape(-1)[0]),
        seed=np.asarray(data["env_seeds"], dtype=np.int64),
        episode_id=np.zeros(n, dtype=np.int64),
        policy=np.asarray(["random"] * n),
        physics={"g": physics[0], "m": physics[1], "l": physics[2]}
        if family == "pendulum"
        else {"link1": physics[0], "link2": physics[1], "mass": physics[2]},
        env_interactions=0,
        notes={"source": "evolution2_persist_reset_science"},
    )


def collect_sources(assigned: dict, meter: BudgetMeter) -> list[dict]:
    files = []
    for bundle in range(N_BUNDLES):
        for family in ("pendulum", "acrobot"):
            role = f"{family}_source"
            key = physics_key(assigned[role])
            refuse_occupied_defaults(family, key)
            spec = role_spec(role, key)
            datasets = {}
            for split, n in (("train", SOURCE_TRAIN_STEPS), ("val", SOURCE_VAL_STEPS)):
                family_code = 0 if family == "pendulum" else 1
                split_code = 0 if split == "train" else 1
                start = 90_000 + 10_000 * family_code + 5_000 * split_code + 200 * bundle
                seeds = tuple(start + i for i in range(8))
                base = 70 + 23 * bundle + 100 * family_code + 3 * split_code
                ds = collect_transitions(spec, n_transitions=n, env_seeds=seeds, base_seed=base, policy="random")
                if int(ds.env_interactions) != n:
                    raise RuntimeError("interaction_mismatch")
                meter.charge(int(ds.env_interactions))
                datasets[split] = ds
                dest = ARRAY_ROOT / family / f"bundle{bundle}_{split}.npz"
                digest = atomic_write_npz(dest, _arrays(ds, family=family, bundle=bundle, split=split, key=key))
                files.append(
                    {
                        "family": family,
                        "bundle": bundle,
                        "split": split,
                        "n": n,
                        "path": str(dest.relative_to(ROOT)),
                        "sha256": digest,
                        "physics": list(key),
                    }
                )
            assert_disjoint_seeds(datasets["train"], datasets["val"])
    return files


def fit_models(files: list[dict], assigned: dict, meter: BudgetMeter) -> dict:
    recipe = clock.RECIPE
    models = {}
    rows = []
    grouped: dict[tuple[str, int], dict[str, dict]] = {}
    for row in files:
        grouped.setdefault((row["family"], int(row["bundle"])), {})[row["split"]] = row
    if len(grouped) != 6:
        raise RuntimeError("six_matched_fits_required")
    for (family, bundle), splits in grouped.items():
        key = physics_key(assigned[f"{family}_source"])
        train = dataset_from_npz(ROOT / splits["train"]["path"], family=family, expected_n=SOURCE_TRAIN_STEPS, key=key)
        val = dataset_from_npz(ROOT / splits["val"]["path"], family=family, expected_n=SOURCE_VAL_STEPS, key=key)
        seed = paired_bundle_seeds(bundle)["persist"]["model_seed"]
        model, metrics = train_world_model(
            train,
            val,
            kind=recipe["kind"],
            epochs=int(recipe["epochs"]),
            batch_size=int(recipe["batch_size"]),
            lr=float(recipe["lr"]),
            seed=seed,
            hidden=tuple(recipe["hidden"]),
            arch=recipe["arch"],
        )
        dest = FIT_ROOT / family / f"bundle{bundle}.pt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        model.save(dest)
        meter.fits += 1
        models[(family, bundle)] = model
        rows.append(
            {
                "family": family,
                "bundle": bundle,
                "path": str(dest.relative_to(ROOT)),
                "model_seed": seed,
                "val_loss": metrics.get("val_loss"),
                "status": "executed",
            }
        )
    return {"models": models, "fits": rows}


def rollout(spec: TaskSpec, family: str, variant, model, *, seed: int, meter: BudgetMeter) -> dict:
    binding = reviewed_binding(family)
    env = make_task_env(spec, seed=seed)
    obs, _ = env.reset(seed=seed)
    total = 0.0
    steps = 0
    imagined = 0
    try:
        for tick in range(EPISODE_STEPS):
            decision = decide(family, variant, obs, model, seed=seed + tick)
            decode_action(binding, decision.action)
            imagined += int(decision.imagined)
            nxt, rew, terminated, truncated, _ = env.step(int(decision.action))
            total += float(rew)
            steps += 1
            obs = nxt
            if terminated or truncated:
                break
    finally:
        env.close()
    meter.charge(steps, imagined=imagined)
    return {"return": total, "steps": steps, "imagined": imagined}


def _unit(raw: dict) -> dict:
    values = list(raw.values())
    lo, hi = min(values), max(values)
    if hi == lo:
        return {key: 0.5 for key in raw}
    return {key: (value - lo) / (hi - lo) for key, value in raw.items()}


def run_bundle(bundle_id: int, models: dict, assigned: dict, meter: BudgetMeter) -> dict:
    """Historical E2.17 loop. Hidden scores are method-independent. Do not reuse."""
    split = locked_split()
    methods = {short: make_methods(paired_bundle_seeds(bundle_id)["persist"]["proposal_seed"])[inner] for short, inner in METHOD_KEYS.items()}
    family_rows = []
    hidden_raw = {name: [] for name in METHODS}
    hidden_unit = {name: [] for name in METHODS}
    for family in bundle_family_order(bundle_id):
        source_key = physics_key(assigned[f"{family}_source"])
        spec = role_spec(f"{family}_source", source_key)
        model = models[(family, bundle_id)]
        context = PublicFixtureContext(reviewed_binding(family).n_actions, reviewed_binding(family).obs_dim, EPISODE_STEPS, 1536)
        raw = {}
        for index, variant in enumerate(split["revealed"]):
            seed = 200_000 + 1_000 * bundle_id + (0 if family == "pendulum" else 100) + index
            raw[variant] = float(rollout(spec, family, variant, model, seed=seed, meter=meter)["return"])
        unit = _unit(raw)
        evaluator = TrustedEvaluator(split["revealed"], family=family, bundle_id=bundle_id, produce_score=lambda variant, unit=unit: unit[variant])
        task = type("Task", (), {"task_id": f"{family}:{bundle_id}"})()
        for name, method in methods.items():
            if method.resets:
                method.reset_task()
            available = list(split["revealed"])
            for slot in range(PROPOSALS):
                if slot < SHARED_PROBES and split["anchors"][slot] in available:
                    variant = split["anchors"][slot]
                else:
                    variant = method.choose(tuple(available), context)
                if variant not in available:
                    raise RuntimeError("duplicate_or_invalid_proposal")
                score = evaluator.evaluate(method.name, variant, family=family, bundle_id=bundle_id)
                receipt = TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint))
                method.update(receipt, context)
                available.remove(variant)
        family_rows.append({"family": family, "revealed_returns": [raw[v] for v in split["revealed"]]})
    methods["persist"].freeze()
    for family in ("pendulum", "acrobot"):
        dev_key = physics_key(assigned[f"{family}_development"])
        refuse_occupied_defaults(family, dev_key)
        spec = role_spec(f"{family}_development", dev_key)
        model = models[(family, bundle_id)]
        revealed_returns = next(row["revealed_returns"] for row in family_rows if row["family"] == family)
        revealed_map = {variant: revealed_returns[i] for i, variant in enumerate(split["revealed"])}
        scale = _unit(revealed_map)
        lo = min(revealed_map.values())
        hi = max(revealed_map.values())
        for index, variant in enumerate(split["hidden"]):
            seed = 210_000 + 1_000 * bundle_id + (0 if family == "pendulum" else 100) + index
            ret = float(rollout(spec, family, variant, model, seed=seed, meter=meter)["return"])
            unit = 0.5 if hi == lo else (ret - lo) / (hi - lo)
            for name in METHODS:
                hidden_raw[name].append(ret)
                hidden_unit[name].append(unit)
    scores = {name: float(np.mean(hidden_unit[name])) for name in METHODS}
    raw_scores = {name: float(np.mean(hidden_raw[name])) for name in METHODS}
    return {
        "bundle": bundle_id,
        "family_order": list(bundle_family_order(bundle_id)),
        "unit_scores": scores,
        "raw_scores": raw_scores,
        "families": family_rows,
    }


def classify(mean: float, lo: float, hi: float) -> str:
    if mean >= PRACTICAL_MARGIN and lo > 0:
        return "persist_supported"
    if hi < 0:
        return "persist_worse"
    return "inconclusive"


def analyze(bundles: list[dict]) -> dict:
    persist = [row["unit_scores"]["persist"] for row in bundles]
    reset = [row["unit_scores"]["reset"] for row in bundles]
    random = [row["unit_scores"]["random"] for row in bundles]
    evolution = [row["unit_scores"]["evolution"] for row in bundles]
    contrasts = {
        "persist_minus_reset": [p - r for p, r in zip(persist, reset)],
        "persist_minus_random": [p - r for p, r in zip(persist, random)],
        "persist_minus_evolution": [p - r for p, r in zip(persist, evolution)],
    }
    stats = {}
    for name, xs in contrasts.items():
        mean, lo, hi = student_t_interval(xs, BONFERRONI_T_CRIT_DF2)
        exp_mean, exp_lo, exp_hi = student_t_interval(xs, EXPLORATORY_T_CRIT_95_DF2)
        stats[name] = {
            "per_bundle": xs,
            "mean": mean,
            "bonferroni": {"lo": lo, "hi": hi, "t_crit": BONFERRONI_T_CRIT_DF2},
            "exploratory": {"lo": exp_lo, "hi": exp_hi, "t_crit": EXPLORATORY_T_CRIT_95_DF2},
            "label": classify(mean, lo, hi),
        }
    primary = stats["persist_minus_reset"]
    return {
        "primary": "persist_minus_reset",
        "label": primary["label"],
        "practical_margin": PRACTICAL_MARGIN,
        "df": 2,
        "n10_forbidden": True,
        "contrasts": stats,
        "bundle_unit_scores": {name: [row["unit_scores"][name] for row in bundles] for name in METHODS},
        "bundle_raw_scores": {name: [row["raw_scores"][name] for row in bundles] for name in METHODS},
    }


def run_authorized(approval_text: str) -> dict:
    preflight = grant.integrity_preflight(approval_text)
    grant.require_unused_grant(grant.REQUIRED_ENV_CAP, approval_text)
    consumed = grant.consume_grant()
    meter = BudgetMeter(grant.REQUIRED_ENV_CAP, grant.REQUIRED_TIME_CAP_S)
    assigned = {role: physics_key(grant.APPROVED_ROLES[role]) for role in ROLE_ORDER}
    payload = {
        "scientific": True,
        "n3_not_n10": True,
        "h17": "blocked",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "source_commit_granted": consumed["source_commit"],
        "preflight": preflight,
        "status": "incomplete",
        "collection": True,
        "granted_7680": False,
        "occupied_default_credit": 0,
        "env_cap": grant.REQUIRED_ENV_CAP,
        "time_cap_s": grant.REQUIRED_TIME_CAP_S,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    try:
        files = collect_sources(assigned, meter)
        fitted = fit_models(files, assigned, meter)
        bundles = []
        for bundle_id in range(N_BUNDLES):
            bundles.append(run_bundle(bundle_id, fitted["models"], assigned, meter))
        analysis = analyze(bundles)
        payload.update(
            {
                "status": "complete",
                "env_steps": meter.env_steps,
                "imagined": meter.imagined,
                "fits_executed": meter.fits,
                "wall_s": meter.elapsed(),
                "cpu_s": time.process_time() - meter.cpu0,
                "arrays": files,
                "fits": fitted["fits"],
                "bundles": bundles,
                "analysis": analysis,
                "primary_label": analysis["label"],
                "scientific_ledger_after_hint": [305.842 + meter.elapsed(), max(0.0, 3294.158 - meter.elapsed())],
            }
        )
    except Exception as exc:
        payload.update(
            {
                "status": "incomplete" if meter.interrupt else "failed",
                "interrupt": meter.interrupt,
                "error": str(exc),
                "env_steps": meter.env_steps,
                "imagined": meter.imagined,
                "fits_executed": meter.fits,
                "wall_s": meter.elapsed(),
                "cpu_s": time.process_time() - meter.cpu0,
            }
        )
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    USAGE.write_text(
        json.dumps(
            {
                "scientific": True,
                "env_steps": payload.get("env_steps", meter.env_steps),
                "env_cap": grant.REQUIRED_ENV_CAP,
                "wall_s": payload.get("wall_s"),
                "cpu_s": payload.get("cpu_s"),
                "h16_scientific_ledger_untouched": True,
                "session_ledger_used_before_s": 305.842,
                "consumed": True,
                "automatic_retries": False,
            },
            indent=2,
        )
        + "\n"
    )
    return payload


HIDDEN_SLOTS_PER_FAMILY = DEVELOPMENT_CONDITIONS


def family_context(family: str) -> PublicFixtureContext:
    binding = reviewed_binding(family)
    return PublicFixtureContext(binding.n_actions, binding.obs_dim, EPISODE_STEPS, 1536)


def replay_training(bundle_id: int, family_returns: dict[str, list[float]], *, shared_persist_seed: bool):
    """Replay proposer training from recorded revealed returns. No environment."""
    split = locked_split()
    seed_row = paired_bundle_seeds(bundle_id)
    if shared_persist_seed:
        methods = {short: make_methods(seed_row["persist"]["proposal_seed"])[inner] for short, inner in METHOD_KEYS.items()}
    else:
        methods = {short: make_methods(seed_row[short]["proposal_seed"])[inner] for short, inner in METHOD_KEYS.items()}
    choices = {name: [] for name in METHODS}
    for family in bundle_family_order(bundle_id):
        raw = {variant: float(family_returns[family][index]) for index, variant in enumerate(split["revealed"])}
        unit = _unit(raw)
        evaluator = TrustedEvaluator(
            split["revealed"],
            family=family,
            bundle_id=bundle_id,
            produce_score=lambda variant, unit=unit: unit[variant],
        )
        context = family_context(family)
        task = type("Task", (), {"task_id": f"{family}:{bundle_id}"})()
        for name, method in methods.items():
            if method.resets:
                method.reset_task()
            available = list(split["revealed"])
            picked = []
            for slot in range(PROPOSALS):
                if slot < SHARED_PROBES and split["anchors"][slot] in available:
                    variant = split["anchors"][slot]
                else:
                    variant = method.choose(tuple(available), context)
                score = evaluator.evaluate(method.name, variant, family=family, bundle_id=bundle_id)
                method.update(
                    TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint)),
                    context,
                )
                picked.append(
                    {
                        "slot": slot,
                        "family": family,
                        "rule": variant.rule.value,
                        "generator": variant.generator.value,
                        "horizon": variant.horizon,
                        "fingerprint": variant.fingerprint,
                    }
                )
                available.remove(variant)
            choices[name].append({"family": family, "proposals": picked})
    methods["persist"].freeze()
    return {"methods": methods, "choices": choices, "split": split}


def select_hidden_controllers(methods: dict, family: str) -> dict[str, tuple]:
    split = locked_split()
    context = family_context(family)
    selected = {}
    for name, method in methods.items():
        available = list(split["revealed"])
        picked = []
        for _slot in range(HIDDEN_SLOTS_PER_FAMILY):
            variant = method.choose(tuple(available), context)
            if variant not in available:
                raise RuntimeError("duplicate_or_invalid_hidden_selection")
            picked.append(variant)
            available.remove(variant)
        selected[name] = tuple(picked)
    return selected


class MethodSensitiveHiddenEval:
    """Hidden scores follow the selected planner. Logical charges stay equal."""

    def __init__(self, produce_score):
        self._produce = produce_score
        self._cache: dict[tuple, float] = {}
        self._hidden_fingerprints: set[str] = set()
        self.physical = 0
        self.logical = 0
        self.cached = 0
        self.per_method = {name: {"logical": 0, "physical": 0, "cached": 0} for name in METHODS}

    def evaluate(self, method: str, variant, *, seed_key: tuple) -> float:
        if method not in self.per_method:
            raise RuntimeError("unknown_method")
        key = seed_key + (variant.fingerprint,)
        self.logical += 1
        self.per_method[method]["logical"] += 1
        self._hidden_fingerprints.add(variant.fingerprint)
        if key in self._cache:
            self.cached += 1
            self.per_method[method]["cached"] += 1
            return self._cache[key]
        score = float(self._produce(variant, seed_key))
        self._cache[key] = score
        self.physical += 1
        self.per_method[method]["physical"] += 1
        return score

    def training_must_not_see(self, method, evaluator: TrustedEvaluator) -> None:
        leaked = [variant for variant in evaluator.training_feedback(method) if getattr(variant, "fingerprint", variant) in self._hidden_fingerprints]
        if leaked:
            raise RuntimeError("hidden_development_leaked_into_training")


def matched_hidden_seed(bundle_id: int, family: str, slot: int) -> tuple:
    return ("hidden", int(bundle_id), family, int(slot))


def corrected_hidden_scores(methods: dict, bundle_id: int, produce_score) -> dict:
    evaluator = MethodSensitiveHiddenEval(produce_score)
    rows = {name: [] for name in METHODS}
    selections = {name: [] for name in METHODS}
    for family in ("pendulum", "acrobot"):
        selected = select_hidden_controllers(methods, family)
        for name in METHODS:
            for slot, variant in enumerate(selected[name]):
                score = evaluator.evaluate(name, variant, seed_key=matched_hidden_seed(bundle_id, family, slot))
                rows[name].append(score)
                selections[name].append(
                    {
                        "family": family,
                        "slot": slot,
                        "fingerprint": variant.fingerprint,
                        "rule": variant.rule.value,
                        "generator": variant.generator.value,
                        "horizon": variant.horizon,
                    }
                )
    logical = {name: evaluator.per_method[name]["logical"] for name in METHODS}
    if len(set(logical.values())) != 1:
        raise RuntimeError("unequal_hidden_evaluation_budget")
    return {
        "scores": {name: float(sum(rows[name]) / len(rows[name])) for name in METHODS},
        "selections": selections,
        "charges": {
            "physical": evaluator.physical,
            "logical": evaluator.logical,
            "cached": evaluator.cached,
            "per_method": evaluator.per_method,
        },
    }


def fresh_budget_estimate() -> dict:
    source = N_BUNDLES * 2 * (SOURCE_TRAIN_STEPS + SOURCE_VAL_STEPS)
    revealed = N_BUNDLES * 2 * REVEALED_VARIANTS_PER_FAMILY * EPISODE_STEPS
    logical_hidden = N_BUNDLES * 2 * HIDDEN_SLOTS_PER_FAMILY * len(METHODS)
    physical_hidden_upper = logical_hidden * EPISODE_STEPS
    return {
        "scientific": False,
        "collection": False,
        "cannot_reuse_e217_development_as_confirmation": True,
        "fresh_source": source,
        "revealed": revealed,
        "hidden_logical_evaluations": logical_hidden,
        "hidden_physical_steps_upper": physical_hidden_upper,
        "hidden_physical_steps_if_all_cache": N_BUNDLES * 2 * HIDDEN_SLOTS_PER_FAMILY * EPISODE_STEPS,
        "fresh_total_upper": source + revealed + physical_hidden_upper,
        "fresh_total_if_identical_selections": source + revealed + N_BUNDLES * 2 * HIDDEN_SLOTS_PER_FAMILY * EPISODE_STEPS,
        "fits": 6,
        "time_cap_s": 900,
        "n10_forbidden": True,
        "occupied_default_credit": 0,
        "justification": (
            "A corrected n=3 screen still needs matched new-physics residuals "
            "(7680) and revealed training (7200). Hidden evaluation now charges "
            "one physical episode per unique selected planner and seed, with "
            "equal logical slots per method (3×2×2×4=48). If every method "
            "selects a different planner the hidden physical cap is 9600; if "
            "they collide, cache hits reduce physical steps. Completed E2.17 "
            "development outcomes are observed and cannot confirm this repair."
        ),
    }


def write_protocol_artifact(approval_text: str) -> dict:
    preflight = grant.integrity_preflight(approval_text)
    record = grant.write_grant(approval_text, source_commit_sha=grant.REQUIRED_COMMIT)
    return {
        "scientific": False,
        "collection": False,
        "grant_unused": grant.grant_unused(),
        "grant": {
            "authorized": record["authorized"],
            "consumed": record["consumed"],
            "env_cap": record["env_cap"],
            "source_commit": record["source_commit"],
        },
        "preflight": preflight,
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "h17": "blocked",
        "dispatch_still_refused": True,
    }
