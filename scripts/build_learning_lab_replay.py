"""Build an offline read-only viewer from verified current artifacts."""
import json
import argparse
from nexus.evolution2.full_policy_source import ROOT
from nexus.evolution2.learning_lab import load_replay,render,load_integration

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration',action='store_true',help='Create a separate page including verified E3.10 status; preserve the original replay.')
    args=parser.parse_args()
    path=ROOT/('artifacts/nexus_learning_lab_e3_10.html' if args.integration else 'artifacts/nexus_learning_lab.html')
    evidence=ROOT/'artifacts/e3_8_interface_examples.json'
    events=json.loads(evidence.read_text())['events'] if evidence.exists() else ()
    page=render(load_replay(ROOT),engineering_events=events,integration=load_integration(ROOT) if args.integration else None)
    with path.open('x') as out:out.write(page)
    print(path)
