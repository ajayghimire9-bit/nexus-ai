"""Saved-result arithmetic only; no planner/model/environment calls."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess

from nexus.evolution1.fixtures import Event, verify_journal
from nexus.evolution2.unified_source_bench import ROOT, CONFIG, RESULT, METHODS, validate


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def mean(xs): return sum(xs) / len(xs)


def audit(p, config):
    validate(p, config)
    if not p["declared_complete"]: raise ValueError("incomplete_capture")
    for name, h in p["historical_artifacts_sha256"].items():
        if sha(ROOT / name) != h: raise ValueError("historical_digest_mismatch:" + name)
    for h in p["histories"]:
        if not verify_journal(tuple(Event(**e) for e in h["journal"])):
            raise ValueError("lineage_journal_mismatch")
    for r in p["rows"]:
        if not math.isclose(sum(t["regret"] for t in r["trace"][2:]), r["cumulative_regret"], abs_tol=1e-15):
            raise ValueError("wrong_regret_sum")
        for t in r["trace"]:
            if any(not math.isfinite(t[k]) for k in ("raw_proxy", "observed", "prediction", "regret")):
                raise ValueError("nonfinite_raw_trace")
    summaries = {m: {"cumulative_regret": mean([r["cumulative_regret"] for r in p["rows"] if r["method"] == m]),
                     "first_free_regret": mean([r["first_free_regret"] for r in p["rows"] if r["method"] == m])}
                 for m in METHODS}
    cells = []
    for f,b in itertools.product(config["families"], config["bundles"]):
        subset = [r for r in p["rows"] if (r["family"],r["held_bundle"]) == (f,b)]
        means = {m: mean([r["cumulative_regret"] for r in subset if r["method"] == m]) for m in METHODS}
        cells.append({"family": f, "held_bundle": b, "regret": means,
                      "unified_minus_persistent": means["unified"] - means["persistent"]})
    s = p["summary"]
    common = p["prediction_common_support"]
    capability_a = (p["prediction_summary"]["fixed"]["mae"] < .95*p["prediction_summary"]["fixed"]["zero_mae"]
                    and common["predicted"] < .95*min(common["paired_mean"], common["observation_kernel"]))
    capability_c = (s["feedback_generation"]["cumulative_regret"] < .95*s["random_generation"]["cumulative_regret"]
                    and s["unified"]["cumulative_regret"] < .95*min(s["shuffled"]["cumulative_regret"],s["withheld"]["cumulative_regret"]))
    strongest = min((m for m in METHODS if m != "unified"), key=lambda m:s[m]["cumulative_regret"])
    d_pooled = s["unified"]["cumulative_regret"] < .95*s[strongest]["cumulative_regret"]
    d_families = {f: mean([c["regret"]["unified"] for c in cells if c["family"]==f]) <
                    .95*min(mean([c["regret"][m] for c in cells if c["family"]==f]) for m in METHODS if m!="unified")
                  for f in config["families"]}
    wins = sum(c["regret"]["unified"] < c["regret"][strongest] for c in cells)
    # Source fixture limitation: all methods already found the same best score.
    best_values_equal = all(len({r["best_observed"] for r in p["rows"] if
        (r["family"],r["held_bundle"],r["offset"],r["seed"]) == (f,b,o,seed)})==1
        for f,b,o,seed in itertools.product(config["families"],config["bundles"],config["offsets"],config["proposal_seeds"]))
    anchor_optimal = sum(max(t["observed"] for t in r["trace"][:2]) == r["best_observed"] for r in p["rows"])
    return {"audit_complete": True, "scientific": False, "source_result_sha256": sha(RESULT),
        "capabilities": {"A_quality_generalization": capability_a,
            "B_source_behavioral_novelty": p["behavior_witness"]["novel_action_vectors_beyond_fixed"]>0,
            "C_useful_feedback_generation": capability_c,
            "D_unified_strongest_baseline": d_pooled and all(d_families.values()),
            "E_held_bundle_advantage": d_pooled and all(d_families.values()) and wins>=3},
        "strongest_baseline": strongest, "summary": summaries, "folds": cells,
        "family_screen_D": d_families, "held_fold_wins": wins,
        "all_best_values_tied": best_values_equal, "anchor_already_best_traces": anchor_optimal,
        "total_traces": len(p["rows"]), "historical_artifacts_verified": len(p["historical_artifacts_sha256"]),
        "lineage_journals_verified": len(p["histories"]),
        "parameter_reporting_correction": {"raw_field": "predictor_parameters",
            "issue": "Raw capture reports0 after final observe invalidates cached fit; this is not coefficient capacity.",
            "fitted_coefficients_per_nonwithheld_model": 192, "withheld_model_coefficients": 0,
            "derivation": "12 public task features x16 operator descriptors; no new fit performed."},
        "resources": {"real_interactions": 0, "model_inference": 0, "fits": 0},
        "limitations": ["Inspected reverse source folds and shared proposer seeds are not independent scientific replications.",
            "FakeStepModel/common-neutral-continuation action values are proxies, not environment/control returns.",
            "Initial incomplete attempt remains preserved; recovery is not independent confirmation."]}


if __name__ == "__main__":
    dest = ROOT / "artifacts/unified_e225_e30_audit.json"
    if dest.exists(): raise FileExistsError("preserve_previous_audit")
    p = audit(json.loads(RESULT.read_text()), json.loads(CONFIG.read_text()))
    p["audit_sha"] = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    dest.write_text(json.dumps(p,indent=2,allow_nan=False)+"\n")
    print(json.dumps(p["capabilities"]))
