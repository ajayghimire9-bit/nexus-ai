import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]


def audit_module():
    spec=importlib.util.spec_from_file_location('focus_audit',ROOT/'scripts/audit_seed_focus.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_static_audit_retains_shared_dependencies_and_never_licenses_deletion():
    r=audit_module().audit()
    for name in ('nexus.evolution1.fixtures','nexus.evolution1.catalogue','nexus.meta.controller','nexus.world.planning','nexus.nn.factory'):
        assert name in r['reachable_modules']
    assert r['safe_to_delete_automatically']==[] and not r['scientific_execution']


def test_archive_preserves_exact_prior_context():
    import hashlib
    expected={'AGENTS.md':'2b4e2f18f9c54f192eef28f5c28d2a77f2a20adcb344ff2de99152cb49294661','MASTER_CONTEXT.md':'8cd13a66d8055550675f86d99e88be55ed57de0ddcce2ba2222a48dda4637366','NEXUS_CANONICAL_CURRENT_STATE.md':'1f1a93486d1050e579a44f5088269cba02db03c0c0d13a0d0116a7d3cda9fe1e','NEXUS_CODE_REUSE_MAP.md':'b0aaca92070a01209c5b10aca8944640ec6f9e787ddf010be03370dd8c74ac08','NEXUS_FULL_RESEARCH_REGISTRY.md':'5f209950a4f008628f4a9e6f44c00ee4f28c9675c74ff7b7eb8223fb0792a343'}
    for name,sha in expected.items():assert hashlib.sha256((ROOT/'docs/history/seed-focus-2026-10-20'/name).read_bytes()).hexdigest()==sha


def test_standing_authority_is_preserved_verbatim_and_limits_unchanged():
    marker='## Standing Coding and Local Research Authority'
    prior=(ROOT/'docs/history/seed-focus-2026-10-20/AGENTS.md').read_text().split(marker)[1].strip()
    current=(ROOT/'AGENTS.md').read_text().split(marker)[1].strip()
    assert current==prior


def test_seed_cli_status_runs_without_third_party_or_research_imports():
    code="import sys;sys.path.insert(0,sys.argv[1]);from nexus.seed.cli import main;main(['--repository',sys.argv[2],'status']);assert not any(n in sys.modules for n in ['torch','numpy','gymnasium','nexus.cli','nexus.meta.loop'])"
    r=subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],text=True,capture_output=True,check=True)
    assert json.loads(r.stdout)['learning_to_learn_established'] is False


def test_seed_runtime_does_not_eagerly_import_historical_training():
    code="import sys;from nexus.seed import grounded_agent;assert not any(n in sys.modules for n in ['gymnasium','nexus.meta.loop','nexus.evolution.loop','nexus.train_run','nexus.world.dynamics'])"
    subprocess.run([sys.executable,'-c',code],text=True,capture_output=True,check=True)


def test_lazy_public_exports_remain_identical():
    from nexus.meta import LinUCBController
    from nexus.meta.controller import LinUCBController as same
    from nexus.world import RandomShootingMPC,WorldModel
    from nexus.world.planning import RandomShootingMPC as planner
    from nexus.world.dynamics import WorldModel as model
    assert LinUCBController is same and RandomShootingMPC is planner and WorldModel is model


def test_cli_rejects_unbounded_or_missing_repository(tmp_path):
    from nexus.seed.cli import main
    with pytest.raises(SystemExit):main(['--repository',str(tmp_path),'serve'])
    with pytest.raises(SystemExit):main(['--repository',str(ROOT),'serve','--seconds','901'])
