"""Persistent playground compounding; isolated temp brains only."""
from pathlib import Path

from nexus.wave24_quotient_core import WorkMeter
from nexus.wave24_unlimited_playground import PersistentNexusBrain, UnlimitedPythonGround, run_playground


def test_persistent_brain_compounds_skills_across_epochs(tmp_path):
    meter = WorkMeter(limit=400_000, wall_limit=1.)
    first = run_playground(tmp_path / "brain", epochs=2, meter=meter)
    assert first["epochs"] == 2
    assert abs(first["atp_total_sum"] - 100.0) < 1e-6
    assert 0.25 <= first["normalized_atp_entropy"] <= 0.98
    revived = PersistentNexusBrain(tmp_path / "brain", meter=WorkMeter(limit=100_000, wall_limit=1.))
    assert revived.toolbox_path.exists()
    second = run_playground(tmp_path / "brain", epochs=1, meter=WorkMeter(limit=200_000, wall_limit=1.))
    assert second["epochs"] == 1
    assert abs(second["atp_total_sum"] - 100.0) < 1e-6
    assert len(PersistentNexusBrain(tmp_path / "brain").toolbox_names) >= len(first["toolbox"])


def test_unlimited_ground_fingerprints_stdlib_and_toolbox(tmp_path):
    brain = PersistentNexusBrain(tmp_path, meter=WorkMeter(limit=50_000, wall_limit=1.))
    crawled = UnlimitedPythonGround().crawl(brain, meter=brain.meter, max_ops=16)
    assert crawled["operator_count"] >= 8
    assert crawled["fingerprint_ms"] < 5
    assert crawled["roles"]
