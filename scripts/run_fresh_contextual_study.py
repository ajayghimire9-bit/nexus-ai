"""Inspect the staged collection gate; never implicitly create environments."""
import json
from nexus.evolution2.full_policy_source import ROOT
from nexus.evolution2.staged_study import StagedStudy

if __name__=='__main__':
    config=json.loads((ROOT/'configs/fresh_contextual_selection_design.json').read_text())
    try:StagedStudy(config)
    except ValueError as error:
        print(json.dumps(dict(status='BLOCKED',reason=str(error),collection=False)));raise SystemExit(2)
    raise SystemExit('Reviewed resource-metered environment worker must be bound by a future protocol; no implicit dispatch')
