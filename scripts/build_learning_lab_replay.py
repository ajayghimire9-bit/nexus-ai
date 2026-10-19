"""Build an offline read-only viewer from verified current artifacts."""
import json
from nexus.evolution2.full_policy_source import ROOT
from nexus.evolution2.learning_lab import load_replay,render

if __name__=='__main__':
    path=ROOT/'artifacts/nexus_learning_lab.html'
    evidence=ROOT/'artifacts/e3_8_interface_examples.json'
    events=json.loads(evidence.read_text())['events'] if evidence.exists() else ()
    page=render(load_replay(ROOT),engineering_events=events)
    with path.open('x') as out:out.write(page)
    print(path)
