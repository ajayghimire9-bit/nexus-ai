"""Run/check the deterministic non-scientific toy example; no scientific runner."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from nexus.evolution1.catalogue import canonical
from nexus.evolution1.toy_loop import (AdaptiveProposer, FixedProposer, RandomProposer,
    VARIANTS, run_cycle, run_training, synthetic_case)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'artifacts/evolution1_toy_loop.json'
BASE = 'e4daa4ea8c89e43c5d296910c0f14e6e3608c4fa'
CODE = ('src/nexus/evolution1/catalogue.py','src/nexus/evolution1/fixtures.py',
        'src/nexus/evolution1/resources.py','src/nexus/evolution1/promotion.py',
        'src/nexus/evolution1/toy_loop.py','scripts/run_evolution1_toy_loop.py')


def build_demo():
    index = {v.fingerprint:i for i,v in enumerate(VARIANTS)}
    cases = {}
    for name in ('aligned_signal','heuristic_counterexample','development_reversal'):
        train,dev = synthetic_case(name)
        runs = {}
        for cls in (AdaptiveProposer,FixedProposer,RandomProposer):
            result = run_cycle(cls(7),train,dev)
            attempts = result['training']['attempts']
            result['summary'] = {
                'variant_indices':[index[a['variant_id']] for a in attempts],
                'training_sum':sum(0 if a['failed'] else a['score'] for a in attempts),
                'best_training_score':max(0 if a['failed'] else a['score'] for a in attempts),
                'development_gain':result['gate']['gain'],
                'decision':result['decision']}
            runs[cls.name] = result
        cases[name] = {'training_rows':[asdict(r) for r in train],
                       'development_rows':[asdict(r) for r in dev],'runs':runs}
    withheld = run_training(AdaptiveProposer(7),synthetic_case('aligned_signal')[0],withhold_feedback=True)
    fed = cases['aligned_signal']['runs']['adaptive']['training']
    return {
        'mode':'deterministic_non_scientific_fixture',
        'toy_seed':7,'proposals_per_run':4,'catalogue_size':12,
        'scientific_claim':False,'scientific_real_steps':0,'scientific_imagined_transitions':0,
        'neural_training_updates':0,'scientific_execution_seconds':0,
        'demo_training_scalar_lookups':40,'demo_development_scalar_lookups':18,
        'cases':cases,
        'feedback_intervention':{
            'fed_indices':[index[a['variant_id']] for a in fed['attempts']],
            'withheld_indices':[index[a.variant_id] for a in withheld.attempts],
            'fed_final_state':fed['policy_after'],
            'withheld_initial_state':withheld.policy_before,
            'withheld_final_state':withheld.policy_after,
            'withheld_raw':asdict(withheld)}}


def code_hashes():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CODE}


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--demo',action='store_true',help='print deterministic synthetic results as JSON')
    mode.add_argument('--check',action='store_true',help='replay toy fixtures and compare the saved artifact')
    args = parser.parse_args()
    if args.check:
        saved = json.loads(OUTPUT.read_text())
        if saved['provenance']['relevant_source_status']:
            raise SystemExit('toy artifact was generated with uncommitted relevant source')
        if saved['provenance']['source_hashes'] != code_hashes():
            raise SystemExit('toy source hashes changed')
        revision = saved['provenance']['implementation_revision']
        if type(revision) is not str or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
            raise SystemExit('invalid toy implementation revision')
        if git('rev-parse','--verify',revision) != revision:
            raise SystemExit('toy implementation revision is unavailable')
        committed = {p:hashlib.sha256(subprocess.check_output(
            ['git','show',f'{revision}:{p}'],cwd=ROOT)).hexdigest() for p in CODE}
        if committed != saved['provenance']['source_hashes']:
            raise SystemExit('toy source hashes do not match the recorded commit')
        if canonical(saved['demo']) != canonical(build_demo()):
            raise SystemExit('toy artifact does not reproduce')
        print('TOY_REPRODUCED: feedback intervention, baselines and gate results match; zero scientific execution')
    else:
        relevant_status = git('status','--porcelain','--',*CODE)
        if relevant_status:
            raise SystemExit('commit the toy implementation before generating the saved example')
        provenance = {'base_revision':BASE,'implementation_revision':git('rev-parse','HEAD'),
                      'source_hashes':code_hashes(),'python_version':sys.version.split()[0],
                      'relevant_source_status':relevant_status,
                      'working_tree_status':git('status','--porcelain')}
        print(json.dumps({'provenance':provenance,'demo':build_demo()},indent=2,allow_nan=False))


if __name__ == '__main__': main()
