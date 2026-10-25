"""Source-only host/protocol tests; mocked MPS is not a GPU experiment."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import time

import pytest

from nexus.wave24_quotient_core import WorkMeter, freeze
from nexus.wave24_resource_host import Allocation, Wave24ResourceHost
from nexus.wave24_self_evolving_loop import DualHeadExecutionScorer
from scripts.run_wave24_azr_ruler_cegis import (
    ROOT, CONFIG_PATH, PHASE1_FILES, WORLDS, validate_config, source_hashes,
    load_allocation, task_wire, task_from_wire, result_wire, result_from_wire,
)
from scripts.verify_wave24_azr_ruler_cegis import verify_payload, verify_git
from nexus.seed.experimental import read


def allocation(**kw):
    return Allocation(owner="unit fixture", reason="mocked deterministic source test", **kw)


def fake_torch(events, available=True):
    return SimpleNamespace(device=lambda name: name,
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: available)),
        mps=SimpleNamespace(synchronize=lambda: events.append("sync")))


def test_exact_allocation_cannot_reset_or_expand_carried_allowance():
    assert allocation().session_limit_s-allocation().carried_used_s == pytest.approx(35.432)
    for kwargs in (dict(wall_s=40.), dict(carried_used_s=-1), dict(memory_mb=0), dict(mps_approved="yes")):
        with pytest.raises(ValueError):
            allocation(**kwargs)


def test_every_mps_operation_and_timing_boundary_are_synchronized():
    events = []
    host = Wave24ResourceHost(allocation(mps_approved=True), WorkMeter(), torch_module=fake_torch(events))
    result = host._timed(host.mps_device, lambda: host._op(host.mps_device, lambda: events.append("operation") or 7), scoring=True)
    assert result == 7
    assert events == ["sync", "sync", "operation", "sync", "sync"]
    assert host.stats["mps_scoring_calls"] == 1
    assert host.stats["mps_tensor_operations"] == 1


def test_unapproved_mps_never_executes_an_operation():
    events = []
    host = Wave24ResourceHost(allocation(), WorkMeter(), torch_module=fake_torch(events))
    assert str(host.route(4096)) == "cpu"
    with pytest.raises(ValueError, match="approved"):
        host._op("mps", lambda: events.append("bad"))
    assert not events


def test_calibration_has_fixed_batches_charges_setup_and_does_not_invent_crossover(monkeypatch):
    host = Wave24ResourceHost(allocation(mps_approved=True), WorkMeter(), torch_module=fake_torch([]))
    def mlp(values, device):
        # Deterministic mocked timing is separate from actual hardware evidence.
        return [[0., 0.] for _ in values]
    monkeypatch.setattr(host, "_mlp", mlp)
    def timed(device, fn, **kw):
        host.stats["cpu_wall_ms" if device == "cpu" else "mps_sync_wall_ms"] += 1. if device == "cpu" else 2.
        return fn()
    monkeypatch.setattr(host, "_timed", timed)
    report = host.calibrate_cpu_mps_threshold(repeats=1)
    assert [r["batch_size"] for r in report["rows"]] == [16, 64, 256, 512, 1024]
    assert report["mps_crossover_batch_size"] is None
    assert host.meter.counts["setup_work_units"] > 0
    host.mps_crossover_batch_size = 256
    assert host.route(64) == "cpu" and host.route(256) == "mps" and host.route(16, update=True) == "cpu"
    assert host.route(256, update=True) == "mps"


def test_cached_calibration_never_reuses_gpu_authorization():
    events = []
    host = Wave24ResourceHost(allocation(), WorkMeter(), torch_module=fake_torch(events))
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")
    report = host.reuse_calibration(evidence["payload"]["calibration"], source_sha256=evidence["payload"]["payload_sha256"])
    assert report["cached"] and report["selected_device"] == "cpu"
    assert len(report["cpu_ms_by_batch"]) == len(report["mps_sync_ms_by_batch"]) == 5
    assert host.route(4096, update=True) == "cpu" and not events
    assert host.stats["cpu_scoring_calls"] == host.stats["mps_scoring_calls"] == 0


def test_cpu_ridge_host_matches_existing_ridge_and_is_metered():
    import numpy as np
    from nexus.nn.ridge import fit_ridge
    host = Wave24ResourceHost(allocation(), WorkMeter())
    x = [[1., i, i*i, i%2, 0., 1.] for i in range(1, 7)]
    y = [[float(i), float(7-i)] for i in range(1, 7)]
    scale, beta = host.update_ridge(x, y, ridge=1.)
    models = tuple((scale, beta[:, i]) for i in range(2))
    outputs = host.score_ridge(x, models)
    for head in range(2):
        reference = fit_ridge(x, [row[head] for row in y], ridge=1.)
        expected = (np.asarray(x)/reference[0]) @ reference[1]
        assert np.allclose(np.asarray(outputs)[:, head], expected, atol=1e-4, rtol=1e-4)
    assert host.stats["cpu_weight_updates"] == host.stats["cpu_scoring_calls"] == 1
    assert host.stats["mps_scoring_calls"] == 0


def test_complete_runtime_response_required_and_fallback_has_zero_model_calls():
    host = Wave24ResourceHost(allocation(), WorkMeter(), torch_module=fake_torch([]))
    assert host.query_runtime("unused")["inference_ran"] is False
    assert host.stats["runtime_calls"] == 0
    host.runtime = SimpleNamespace(complete=lambda *a, **k: {"content": "partial", "termination": "streaming"})
    with pytest.raises(ValueError, match="approval"):
        host.query_runtime("blocked")
    host.allocation = replace(host.allocation, llm_approved=True)
    with pytest.raises(ValueError, match="terminated"):
        host.query_runtime("partial")
    def complete(*args, **kwargs):
        return {"content": "done", "termination": "natural_or_stop", "telemetry": {"generated_tokens": 2}}
    host.runtime = SimpleNamespace(complete=complete)
    assert host.query_runtime("mock")["content"] == "done"
    assert host.stats["runtime_work_units"] == 2


def test_config_and_dev_allocation_are_explicit_and_final_cannot_reuse_dev():
    config = read(ROOT/CONFIG_PATH)
    assert validate_config(config) == config
    assert set(source_hashes()) == set(PHASE1_FILES)
    path = ROOT/"configs/wave24_azr_dev_allocation.json"
    assert load_allocation(path, dev=True).mps_approved
    with pytest.raises(ValueError, match="distinct"):
        load_allocation(path, dev=False)
    changed = dict(config, heldout_test_time_selfplay=True)
    with pytest.raises(ValueError, match="fifth"):
        validate_config(changed)


def test_final_git_gate_rejects_missing_sha_before_touching_seed_or_output():
    with pytest.raises(ValueError, match="freeze SHA"):
        verify_git(ROOT, None, source_hashes())


def test_verifier_rejects_incomplete_or_fabricated_preflight():
    result = verify_payload(dict(schema="wave24_azr_v1", execution_status="COMPLETE"), replay=False)
    assert not result["integrity_valid"] and not result["ready_for_freeze"]
    assert result["errors"]


def test_import_does_not_launch_worker_or_draw_final_seed(monkeypatch):
    import scripts.run_wave24_azr_ruler_cegis as runner
    monkeypatch.setattr(runner.secrets, "randbits", lambda *a: pytest.fail("final seed drawn"))
    with pytest.raises(SystemExit):
        runner.main([])
    with pytest.raises(ValueError, match="bounded resource host"):
        runner.worker("not-read.json", "not-written.json")


def test_host_and_runner_source_have_no_history_rewrite_or_historical_output_paths():
    import ast
    host = ast.parse((ROOT/"src/nexus/wave24_resource_host.py").read_text())
    calls = [n for n in ast.walk(host) if isinstance(n, ast.Call)]
    assert calls
    code = (ROOT/"scripts/run_wave24_azr_ruler_cegis.py").read_text()
    assert "artifacts/seed_wave" not in code
    assert "secrets.randbits(256)" in code
    assert "TemporaryDirectory" in code


def test_kernel_cpu_limit_is_installed_before_numpy_torch_imports():
    code = (ROOT/"scripts/run_wave24_azr_ruler_cegis.py").read_text()
    assert code.index("resource.setrlimit") < code.index("from nexus.")


def test_opt_in_source_guard_reports_protected_execution_not_success():
    from nexus.wave24_pytest_guard import exclusion_reason
    assert exclusion_reason("def test_old():\n run_wave16_assessment()")
    assert exclusion_reason('def test_gpu():\n model.to("mps")')
    assert exclusion_reason('def test_pure():\n assert 2+2==4') is None


def test_legacy_feedback_export_round_trips_only_supplied_public_evidence():
    from nexus.seed.public_failure import serialize_revision_feedback
    evidence = dict(instruction="Public tests failed.", actual=False, expected=True, operator_supplied=False)
    assert json.loads(serialize_revision_feedback(evidence)) == evidence
    with pytest.raises(ValueError):
        serialize_revision_feedback(dict(actual=float("nan")))


def test_strict_grid_rejects_missing_duplicate_and_extra_cells():
    from scripts.verify_wave24_azr_ruler_cegis import require_complete_grid
    from nexus.wave24_self_evolving_loop import METHODS
    cells = [dict(task_id="unit-only", method=m, repetition=r) for m in METHODS for r in range(2)]
    assert require_complete_grid(["unit-only"], cells)
    for rows in (cells[:-1], cells+[cells[0]], cells+[dict(task_id="extra", method=METHODS[0], repetition=0)]):
        with pytest.raises(ValueError, match="grid"):
            require_complete_grid(["unit-only"], rows)


def test_strict_symkan_verifier_recomputes_all_four_counts():
    from scripts.verify_wave24_azr_ruler_cegis import require_symkan_identities
    reports = [dict(attempted=True, induced_expression="x", faithful_export=True),
               dict(attempted=True, induced_expression="", faithful_export=False)]
    counts = dict(symkan_attempted_count=2, symkan_nonempty_induced_count=1,
                  symkan_abstained_count=1, symkan_faithful_export_count=1)
    assert require_symkan_identities(reports, counts)
    for key in counts:
        bad = dict(counts)
        bad[key] += 1
        with pytest.raises(ValueError):
            require_symkan_identities(reports, bad)


def test_post_freeze_provenance_checks_bytes_remotes_and_rewrite_audit(tmp_path, monkeypatch):
    import scripts.verify_wave24_azr_ruler_cegis as verifier
    import hashlib
    sha = "a"*40
    hashes, contents = {}, {}
    for path in PHASE1_FILES:
        content = ("source unit fixture "+path).encode()
        dest = tmp_path/path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        contents[path] = content
        hashes[path] = hashlib.sha256(content).hexdigest()
    state = dict(reflog=b"branch: Created from HEAD\n", remote=sha)
    def fake_git(repo, *args):
        if args[0] == "branch": return (verifier.BRANCH+"\n").encode()
        if args[0] == "show": return contents[args[1].split(":", 1)[1]]
        if args[0] == "diff": return b""
        if args[0] == "reflog": return state["reflog"]
        if args[0] == "rev-parse": return (sha+"\n").encode()
        if args[0] == "ls-remote": return (state["remote"]+"\trefs/heads/"+verifier.BRANCH+"\n").encode()
        raise AssertionError(args)
    monkeypatch.setattr(verifier, "git", fake_git)
    monkeypatch.setattr(verifier.subprocess, "run", lambda *a, **k: None)
    report = verifier.verify_git(tmp_path, sha, hashes, require_pushed=True)
    assert report["phase1_zero_diff"] and report["zero_amend_on_branch"]
    state["remote"] = "b"*40
    with pytest.raises(ValueError, match="pushed"):
        verifier.verify_git(tmp_path, sha, hashes, require_pushed=True)
    state["remote"] = sha
    state["reflog"] = b"commit (amend): forbidden\n"
    with pytest.raises(ValueError, match="rewrite"):
        verifier.verify_git(tmp_path, sha, hashes)
    state["reflog"] = b"branch: Created from HEAD\n"
    (tmp_path/PHASE1_FILES[0]).write_text("changed after freeze")
    with pytest.raises(ValueError, match="changed"):
        verifier.verify_git(tmp_path, sha, hashes)


def test_rss_watchdog_preserves_failed_attempt_and_never_retries(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import nexus.wave24_resource_host as module
    events, signals = [], []
    class SandboxFixture:
        def __init__(self, *a):
            self.directory = tmp_path
        def locked(self): return nullcontext()
        def used_s(self): return 0
        def records(self, kind):
            return [dict(run_id=n) for n in ("dev-24001", "dev-24001-frontier-v2", "dev-24001-role-ratchet-v3", "dev-24001-workspace-v4", "dev-24001-lifelong-v5")] if kind == "reserved" else []
        def grant(self, *a, **k): events.append("grant")
        def append(self, kind, payload): events.append((kind, payload))
    class ProcessFixture:
        pid = 777777
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None):
            self.returncode = -9
            return -9
    process = ProcessFixture()
    monkeypatch.setattr(module, "Sandbox", SandboxFixture)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(module, "_rss_kib", lambda pid: 2048*1024)
    monkeypatch.setattr(module.os, "killpg", lambda *args: signals.append(args))
    output, receipt = module.Wave24ResourceHost.supervise(ROOT, dict(config=dict(max_source_rows=1)),
                                                        allocation(), run_id="unit-rss")
    assert signals and receipt["failure"] == "rss_cap" and output["execution_status"] == "INCOMPLETE"
    assert [e[0] for e in events if isinstance(e, tuple)] == ["reserved", "settled"]
    assert (tmp_path/"attempts/unit-rss/receipt.json").exists()
    with pytest.raises(FileExistsError):
        module.Wave24ResourceHost.supervise(ROOT, dict(config=dict(max_source_rows=1)), allocation(), run_id="unit-rss")


def test_consumed_dev_grant_refused_before_host_seed_or_gpu(monkeypatch):
    import scripts.run_wave24_azr_ruler_cegis as runner
    monkeypatch.setattr(runner.secrets, "randbits", lambda *a: pytest.fail("seed drawn"))
    monkeypatch.setattr(runner.Wave24ResourceHost, "supervise", lambda *a, **k: pytest.fail("worker launched"))
    with pytest.raises(ValueError, match="already consumed"):
        runner.main(["--dev-preflight", "--allocation-file", str(ROOT/"configs/wave24_azr_dev_allocation.json")])


def test_frontier_revision_has_a_distinct_cpu_only_grant_and_keeps_the_carried_ledger():
    record = read(ROOT/"configs/wave24_azr_dev_frontier_allocation.json")
    grant = load_allocation(ROOT/"configs/wave24_azr_dev_frontier_allocation.json", dev=True)
    assert record["run_id"] == "dev-24001-frontier-v2"
    assert grant.wall_s == 25 and grant.cpu_s == 25
    assert not grant.mps_approved and not grant.llm_approved
    assert grant.carried_used_s == 3564.568
    assert record["session_remaining_before_this_attempt_s"] == pytest.approx(34.28386512500492)


def test_versioned_receipt_carries_usage_once_on_fresh_clone():
    from nexus.wave24_resource_host import carry_recorded_dev_usage
    events = []
    sandbox = SimpleNamespace(records=lambda kind: events if kind == "session_debit" else [],
                              debit=lambda identifier, seconds, reason, reference: events.append(dict(id=identifier, seconds=seconds)))
    carry_recorded_dev_usage(sandbox, ROOT, allocation())
    carry_recorded_dev_usage(sandbox, ROOT, allocation())
    assert len(events) == 5
    assert events[0]["seconds"] == pytest.approx(1.1481348749948666)
    assert events[1]["seconds"] == pytest.approx(.6674120840034448)
    assert events[2]["seconds"] == pytest.approx(1.5338057079934515)
    assert events[3]["seconds"] == pytest.approx(2.1779485419974662)
    assert events[4]["seconds"] == pytest.approx(4.218562000023667)


def test_preserved_dev_snapshot_hashes_match_the_actually_executed_sources():
    import hashlib
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")
    for path, text in evidence["executed_source_snapshot"].items():
        assert hashlib.sha256(text.encode()).hexdigest() == evidence["payload"]["source_hashes"][path]
    assert evidence["verification"]["integrity_valid"] is True
    assert evidence["verification"]["scientific_gates"]["certificate_b_deep_horizon"] is False


def test_preserved_dev_evidence_replays_without_upgrading_negative_outcome():
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_24001.json")
    report = verify_payload(evidence["payload"], replay=True)
    assert report["integrity_valid"], report["errors"]
    assert report["scientific_gates"]["completed_tier1_exact_agreement"]
    assert not report["scientific_gates"]["certificate_b_deep_horizon"]
    assert not report["ready_for_freeze"]


def test_consumed_frontier_revision_is_portable_and_replays_without_upgrading_failure(monkeypatch):
    import hashlib
    import scripts.run_wave24_azr_ruler_cegis as runner
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_frontier_v2.json")
    for path, text in evidence["executed_source_snapshot"].items():
        assert hashlib.sha256(text.encode()).hexdigest() == evidence["payload"]["source_hashes"][path]
    report = verify_payload(evidence["payload"], replay=True)
    assert report["integrity_valid"], report["errors"]
    assert report["scientific_gates"]["source_frontier_and_rows_each_permitted_world"]
    assert not report["ready_for_freeze"]
    assert not report["scientific_gates"]["certificate_b_deep_horizon"]
    monkeypatch.setattr(runner.Wave24ResourceHost, "supervise", lambda *a, **k: pytest.fail("worker launched"))
    with pytest.raises(ValueError, match="already consumed"):
        runner.main(["--dev-preflight", "--allocation-file", str(ROOT/"configs/wave24_azr_dev_frontier_allocation.json")])


def test_a_hash_and_training_tag_cannot_hide_fabricated_derivation_feedback():
    from nexus.evolution1.catalogue import digest
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_frontier_v2.json")
    payload = deepcopy(evidence["payload"])
    payload.pop("payload_sha256")
    source = payload["source_preparation"]
    source["source_rows"][0]["J_fit"] = 1-source["source_rows"][0]["J_fit"]
    source["scorer_source_digest"] = source["source_feedback_sha256"] = digest(source["source_rows"])
    report = verify_payload(payload, replay=True)
    assert not report["integrity_valid"]
    assert any("source labels do not reproduce" in e for e in report["errors"])


def test_predictively_invisible_coefficient_corruption_still_fails_ridge_equations():
    evidence = read(ROOT/"docs/evidence/wave24_azr_dev_frontier_v2.json")
    payload = deepcopy(evidence["payload"])
    payload.pop("payload_sha256")
    beta = payload["source_preparation"]["scorer_parameters"][0][1]
    # Primitive cost and node count happen to coincide in these unary sources.
    # Equal/opposite perturbations preserve predictions, but not ridge's
    # regularized normal equations. An output-only check would miss this.
    beta[1] += 1.
    beta[2] -= 1.
    report = verify_payload(payload, replay=True)
    assert not report["integrity_valid"]
    assert any("normal-equation residual" in e for e in report["errors"])
