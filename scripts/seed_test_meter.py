"""Optional pytest QA counters, separate from the one development capture.

These count actual parent-process Seed counter increments including replay and
restoration work. They are NOT new teacher answers or scientific interactions.
The subprocess restart test uses18 authored labels and1 sandbox action separately.
"""
import json
from pathlib import Path

COUNTS={}
ORIGINAL=None


def pytest_sessionstart(session):
    global ORIGINAL
    from nexus.seed.core import Session
    ORIGINAL=Session.charge
    def charged(self,key,amount=1):
        value=ORIGINAL(self,key,amount)
        COUNTS[key]=COUNTS.get(key,0)+amount
        return value
    Session.charge=charged


def pytest_sessionfinish(session,exitstatus):
    from nexus.seed.core import Session
    Session.charge=ORIGINAL
    root=Path(__file__).resolve().parents[1]
    out=dict(kind='test_fixture_work_not_development_comparison',exitstatus=exitstatus,
             parent_process_counter_increments_including_reconstruction=COUNTS,
             separately_known_restart_child_work=dict(authored_labels=18,sandbox_actions=1),
             new_scientific_environment_interactions=0,model_inference=0)
    folder=root/'runs';folder.mkdir(exist_ok=True)
    (folder/'seed-test-costs.json').write_text(json.dumps(out,indent=2))
