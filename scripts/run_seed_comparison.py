"""Exclusive, precommitted Seed authored-development capture; no simulator."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.comparison import run_case, validate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true');args=p.parse_args()
    path=ROOT/'artifacts/seed_s0_s1_dev.json'
    config_path=ROOT/'configs/seed_s0_s1.json';raw=config_path.read_bytes();c=json.loads(raw)
    if args.check:
        result=json.loads(path.read_text());analysis=validate(c,result['rows'])
        if result['analysis']!=analysis or result['config_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('saved_arithmetic_mismatch')
        print(json.dumps(dict(valid=True,analysis=analysis),indent=2));return
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise ValueError('clean_precommitted_protocol_required')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    # Exclusive sentinel prevents accidental repeated capture after failure.
    claim=ROOT/'runs/seed-comparison.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write(sha)
    sources={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in
             [*sorted((ROOT/'src/nexus/seed').glob('*.py')),Path(__file__),config_path,ROOT/'docs/NEXUS_SEED_PROTOCOL.md',
              ROOT/'scripts/verify_seed_comparison.py',ROOT/'scripts/run_learning_lab.py',
              ROOT/'src/nexus/evolution1/fixtures.py',ROOT/'src/nexus/evolution1/catalogue.py',
              ROOT/'web/learning-lab/seed.html']}
    old={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in (ROOT/'artifacts').glob('*') if x.is_file()}
    result=dict(kind=c['kind'],execution_sha=sha,config_sha256=hashlib.sha256(raw).hexdigest(),source_hashes=sources,
                hardware=dict(platform=platform.platform(),machine=platform.machine(),python=sys.version),
                rows=[],declared_complete=False,energy='unmeasured',new_real_interactions=0,imagined_transitions=0,neural_updates=0)
    start=time.perf_counter()
    used={}
    limits={'teacher_answers':c['teacher_label_cap'],'candidate_evaluations':c['candidate_evaluation_cap'],
            'predicate_tests':c['predicate_test_cap'],'sandbox_actions':c['sandbox_action_cap']}
    def reserve(key, amount):
        if time.perf_counter()-start>c['wall_cap_s']:raise TimeoutError('comparison_wall_cap')
        if used.get(key,0)+amount>limits.get(key,100000):raise ValueError('comparison_resource_cap')
        used[key]=used.get(key,0)+amount
    try:
        for i,task in enumerate(c['semantic_tasks']):
            for method in c['methods']:
                if time.perf_counter()-start>c['wall_cap_s']:raise TimeoutError('comparison_wall_cap')
                result['rows'].append(run_case(c,task,method,i,reserve))
                # Prefix costs enforced between very small deterministic cases.
                for key,cap in [('teacher_answers','teacher_label_cap'),('candidate_evaluations','candidate_evaluation_cap'),('predicate_tests','predicate_test_cap')]:
                    if sum(r['costs'][key] for r in result['rows'])>c[cap]:raise ValueError('comparison_resource_cap')
        result['analysis']=validate(c,result['rows'])
        result['declared_complete']=True
    except Exception as exc:
        result['failure']=repr(exc)
    result['wall_s']=time.perf_counter()-start
    result['reserved_fixture_costs']=used
    timings=sorted(t for r in result['rows'] for t in r['latency_ms'])
    result['latency_ms']=dict(p50=statistics.median(timings),p95=timings[min(len(timings)-1,int(.95*len(timings)))]) if timings else None
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['peak_rss_mib']=rss/(1024**2 if sys.platform=='darwin' else 1024)
    result['historical_files_verified']=len(old)
    if any(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v for k,v in old.items()):
        result['declared_complete']=False;result['failure']='historical_artifact_changed'
    result['previous_artifact_hashes']=old
    with path.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','previous_artifact_hashes','source_hashes')},indent=2))
    if not result['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
