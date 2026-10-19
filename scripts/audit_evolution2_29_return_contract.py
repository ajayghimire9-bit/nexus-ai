"""Authored receipt integration only. No scientific worker is connected."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator, feedback_reference_digest
from nexus.evolution2.persist_reset_scoring import (
    analyze_return_grid, freeze_shared_reference, prospective_hidden_evaluator,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/evolution2_29_return_contract.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authored_capture():
    t0, cpu0 = time.perf_counter(), time.process_time()
    before = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / "artifacts").rglob("*.json") if p != OUTPUT}
    rows, scales, operations, manifests = [], {}, [], {}
    query_calls = 0
    methods = ("persist", "reset", "random", "evolution")
    families = ("pendulum", "acrobot")
    with tempfile.TemporaryDirectory() as tmp:
        for b in range(10):
            for f in families:
                reference = tuple(ANCHORS)
                source = TrustedEvaluator(reference, family=f, bundle_id=b,
                    produce_score=lambda v: 0. if v == reference[0] else 10.)
                for m in methods:
                    for v in reference: source.evaluate(m, v)
                ref = feedback_reference_digest(f, b, reference)
                scale = freeze_shared_reference(source, method_names=methods,
                    reference=reference, expected_reference_digest=ref)
                scales[b, f] = scale
                manifest = dict(version="prospective_feedback_manifest_v1", scale=scale.payload(),
                    snapshot_digest=scale.snapshot_digest, reference_digest=ref,
                    query_family=f, query_bundle_id=b, query_slots=[0, 1],
                    allowed_variant_ids=[v.fingerprint for v in reference])
                path = Path(tmp) / f"fixture_{b}_{f}.json"
                path.write_text(json.dumps(manifest, sort_keys=True))
                manifests[f"{b}:{f}"] = {"manifest": manifest, "sha256": sha(path)}
                def produce(v, key):
                    nonlocal query_calls
                    query_calls += 1
                    return float(10 + b if v == reference[1] else 0.)
                evaluator = prospective_hidden_evaluator(path, expected_manifest_sha256=sha(path),
                    expected_reference_digest=ref, produce_score=produce)
                for slot in (0, 1):
                    for m in methods:
                        variant = reference[int(m in ("persist", "random"))]
                        prior = evaluator.physical
                        unit = evaluator.evaluate(m, variant, seed_key=("hidden", b, f, slot))
                        cached = evaluator.physical == prior
                        outcome = next(r for r in evaluator._hidden_outcomes
                            if r["outcome_id"][1] == ("hidden", b, f, slot)
                            and r["fingerprint"] == variant.fingerprint)
                        key = f"fixture_{b}_{f}_{slot}_{reference.index(variant)}"
                        if not cached: operations.append(Operation(key, "environment", Work(real_steps=1)))
                        rows.append(dict(bundle=b, family=f, slot=slot, method=m,
                            variant_id=variant.fingerprint, episode_id=f"fixture_{b}_{f}_{slot}",
                            raw=outcome["raw"], unit=unit, clipped=outcome["clipped"],
                            snapshot_digest=scale.snapshot_digest, cached=cached, steps=1,
                            physical_receipt=key, measurement="environment_return"))
    ledger = ReservationLedger(tuple(operations), Limits(Work(real_steps=80), Work(real_steps=80), 10000, 10000))
    for i, op in enumerate(operations):
        ticket = ledger.reserve(op.key, Clock(i * 2, i * 2))
        ledger.settle(ticket, "success", Clock(i * 2 + 1, i * 2 + 1))
    execution = ledger.close(Clock(200, 200))
    summary = analyze_return_grid(rows, bundle_ids=tuple(range(10)), families=families,
        slots=(0, 1), scales=scales, raw_spans={f: 100. for f in families}, execution_report=execution)
    if query_calls != 80 or any(sha(ROOT / p) != h for p, h in before.items()):
        raise RuntimeError("authored_capture_integrity_failure")
    if time.perf_counter() - t0 >= 10:
        raise RuntimeError("authored_capture_time_cap")
    return {"scientific": False, "declared_complete": True, "scientific_execution_ready": False,
        "fixture_only": True, "rows": rows, "manifests": manifests, "summary": summary,
        "historical_artifacts_sha256": before, "historical_artifacts_preserved": True,
        "resources": {"real_interactions": 0, "imagined_transitions": 0, "model_inference": 0,
            "training": 0, "proposer_updates": 0, "synthetic_query_callbacks": query_calls,
            "synthetic_reference_callbacks": 40, "wall_s": time.perf_counter() - t0,
            "cpu_s": time.process_time() - cpu0, "cap_s": 10},
        "scientific_ledger": {"used_s": 327.869, "remaining_s": 3272.131},
        "limitations": ["All returns, episode IDs, bundle IDs, spans and clocks are authored fixtures.",
            "The 80 reported step reservations are synthetic metadata, not executed environment steps.",
            "A label/hash cannot prove a trusted producer measured real returns or independent models.",
            "No practical success threshold, allocation, scientific registration or runtime integration."]}


if __name__ == "__main__":
    if OUTPUT.exists(): raise FileExistsError("preserve_previous_e229_capture")
    if subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True).strip():
        raise RuntimeError("tracked_tree_must_be_clean")
    p = authored_capture()
    p["execution_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    p["source_sha256"] = {name: sha(ROOT / name) for name in (
        "src/nexus/evolution2/persist_reset_scoring.py", "src/nexus/evolution1/resources.py",
        "src/nexus/evolution2/persist_reset_science.py",
        "scripts/audit_evolution2_29_return_contract.py", "docs/NEXUS_E2_29_RETURN_CONTRACT.md")}
    with OUTPUT.open("x") as stream:
        json.dump(p, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("Authored integration complete; scientific execution remains blocked.")
