"""Read-only E2.28 inventory. Imports no NEXUS/model/environment modules.

This checks the inspected historical evidence, not future scientific authority.
No generic readiness framework or replacement evaluator is introduced.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "artifacts/evolution2_28_method_sensitive_readiness.json"
BASE = "6b1be164a58153070f87c87d9a2f4c8b67aa2e93"
FAMILIES = ("pendulum", "acrobot")
METHODS = ("persist", "reset", "random", "evolution")
SOURCE = "src/nexus/evolution2/"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, name):
    matches = [n for n in ast.walk(ast.parse(text))
               if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError("missing_or_ambiguous_function:" + name)
    return matches[0]


def calls(node):
    return {ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}


def validate_integration_provenance(root, payload):
    encoded = json.dumps(payload["manifest"], sort_keys=True).encode()
    if hashlib.sha256(encoded).hexdigest() != payload["manifest_sha256"]:
        raise ValueError("integration_manifest_digest_mismatch")
    # Result-report appendices can change after capture; executed Python cannot.
    for name, expected in payload["source_sha256"].items():
        if name.endswith(".py") and sha(root / name) != expected:
            raise ValueError("integration_execution_source_changed:" + name)


def validate_historical_grid(payload):
    """Expected historical E2.17 IDs are fixed independently of produced rows."""
    rows = payload["bundles"]
    if len(rows) != 3 or any(type(r["bundle"]) is not int for r in rows):
        raise ValueError("historical_bundle_grid")
    if sorted(r["bundle"] for r in rows) != [0, 1, 2]:
        raise ValueError("historical_bundle_grid")
    for row in rows:
        if sorted(r["family"] for r in row["families"]) != sorted(FAMILIES):
            raise ValueError("historical_family_grid")
        for key in ("raw_scores", "unit_scores"):
            if set(row[key]) != set(METHODS):
                raise ValueError("historical_method_grid")
            if any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in row[key].values()):
                raise ValueError("historical_nonfinite_or_nonnumeric")
    expected_arrays = {(f, b, s) for f in FAMILIES for b in range(3) for s in ("train", "val")}
    actual_arrays = [(r["family"], r["bundle"], r["split"]) for r in payload["arrays"]]
    actual_fits = [(r["family"], r["bundle"]) for r in payload["fits"]]
    if len(actual_arrays) != 12 or set(actual_arrays) != expected_arrays:
        raise ValueError("historical_array_grid")
    if len(actual_fits) != 6 or set(actual_fits) != {(f, b) for f in FAMILIES for b in range(3)}:
        raise ValueError("historical_fit_grid")


def collect(root=ROOT):
    started, cpu = time.perf_counter(), time.process_time()
    historical = {str(p.relative_to(root)): sha(p)
                  for p in sorted((root / "artifacts").rglob("*.json"))
                  if str(p.relative_to(root)) != OUTPUT}
    names = [SOURCE + n + ".py" for n in (
        "persist_reset_science", "persist_reset_scoring", "persist_reset_executor",
        "persist_reset_method_sensitive", "pendulum_acrobot_protocol_n3_micro",
        "pendulum_acrobot_protocol_v2", "pendulum_acrobot_protocol_v2_pilot",
        "methods", "tasks", "fit_clock")]
    texts = {p: (root / p).read_text() for p in names}
    science = texts[SOURCE + "persist_reset_science.py"]
    scoring = texts[SOURCE + "persist_reset_scoring.py"]
    checks = {
        "legacy_run_uses_method_independent_loop": "run_bundle" in calls(function(science, "run_authorized")),
        "corrected_helper_bypasses_manifest_factory": "MethodSensitiveHiddenEval" in calls(function(science, "corrected_hidden_scores"))
            and "prospective_hidden_evaluator" not in calls(function(science, "corrected_hidden_scores")),
        "fixture_scores_model_forecast_not_environment_return": "max" in calls(function(science, "fixture_hidden_return"))
            and "rollout" not in calls(function(science, "fixture_hidden_return")),
        "analysis_still_df2": "BONFERRONI_T_CRIT_DF2" in {n.id for n in ast.walk(function(science, "analyze")) if isinstance(n, ast.Name)},
        "prospective_factory_exists": bool(function(scoring, "prospective_hidden_evaluator")),
        "scientific_dispatch_explicitly_refuses": any(isinstance(n, ast.Raise) for n in ast.walk(function(texts[SOURCE + "persist_reset_executor.py"], "execute_scientific"))),
    }
    if not all(checks.values()):
        raise ValueError("reviewed_source_changed_reaudit_required")
    old = json.loads((root / "artifacts/evolution2_persist_reset_science.json").read_text())
    integration = json.loads((root / "artifacts/evolution2_27_feedback_integration.json").read_text())
    validate_integration_provenance(root, integration)
    validate_historical_grid(old)
    arrays = []
    for row in old["arrays"]:
        actual = sha(root / row["path"])
        if actual != row["sha256"]:
            raise ValueError("historical_array_digest_mismatch:" + row["path"])
        arrays.append({"path": row["path"], "sha256": actual})
    # This is present-day byte inventory only: E2.17 did not save fit hashes.
    fits = [{"path": r["path"], "expected_sha256": r.get("sha256"),
             "current_sha256": sha(root / r["path"]) if (root / r["path"]).is_file() else None}
            for r in old["fits"]]
    screens = json.loads((root / "artifacts/evolution2_persist_reset_scoring.json").read_text())["screens"]
    if (screens["n3"]["fresh_total_upper"], screens["n10"]["fresh_total_upper"]) != (24480, 81600):
        raise ValueError("historical_budget_changed")
    if any(sha(root / p) != h for p, h in historical.items()):
        raise ValueError("historical_artifacts_changed")
    return {"review_complete": True, "scientific_execution_ready": False,
            "verdict": "BLOCKED_SCIENTIFIC_RUNNER_AND_PROTOCOL_GAPS", "base_sha": BASE,
            "source_sha256": {p: sha(root / p) for p in names}, "source_checks": checks,
            "historical_artifacts_sha256": historical, "historical_artifacts_preserved": True,
            "historical_arrays_verified": arrays, "historical_fit_inventory": fits,
            "e227_execution_sources_and_manifest_verified": True,
            "budget_priors_only": {n: screens[n] for n in ("n3", "n10")},
            "blockers": ["no_prospective_real_return_runner", "no_fair_shared_reference_plan",
                         "no_n10_exact_grid_and_analysis_contract", "no_prospective_matched_fit_manifest",
                         "no_incremental_interrupted_work_accounting", "no_fresh_protocol_or_allocation"],
            "scope": "Targeted source review, not exhaustive repository/remote provenance certification.",
            "resources": {"wall_s": time.perf_counter() - started, "cpu_s": time.process_time() - cpu,
                          "real_interactions": 0, "imagined_transitions": 0, "model_inference": 0,
                          "training": 0, "allocations_created": 0},
            "scientific_ledger": {"used_s": 327.869, "remaining_s": 3272.131}}


if __name__ == "__main__":
    target = ROOT / OUTPUT
    if target.exists():
        raise FileExistsError("preserve_previous_e228_audit")
    if subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True).strip():
        raise RuntimeError("tracked_tree_must_be_clean")
    payload = collect()
    payload["execution_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with target.open("x") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(payload["verdict"])
