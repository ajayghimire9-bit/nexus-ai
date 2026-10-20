"""Independent saved arithmetic and hash audit; no fitting or collection."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import investigation_hybrid as h


def verify():
    r=json.loads((ROOT/'artifacts/seed_investigation_hybrid.json').read_text())
    h.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=5000,updates=0,imagined_transitions=0))
    independent={}
    for method in h.METHODS:
        ds=[row['methods'][method] for row in r['rows']]
        q=sum(len(d['steps']) for d in ds)/32
        assert q==r['analysis']['means'][method]['questions']
        search=sum(d['costs']['search_predictions'] for d in ds)
        target=sum(d['costs']['hypothesis_predictions']+d['costs']['tree_nodes'] for d in ds)
        source=r['inherited_source']['source_split_comparisons'] if method in ('tree_fixed','tree_greedy') else 0
        assert target+source==r['analysis']['means'][method]['total_decision_work']
        assert search==r['analysis']['means'][method]['search_predictions']
        for b in (1,2,4,8):
            correct=sum(sum((p>=.5)==f['answer'] for p,f in zip(row['methods'][method]['predictions'][str(b)],row['final'])) for row in r['rows'])
            assert correct/1024==r['analysis']['means'][method]['accuracy'][str(b)]
        independent[method]=dict(questions=q,search_checks=search,total_work_including_source=target+source)
    for method,c in r['analysis']['question_savings'].items():
        xs=[row['methods'][method]['questions_to_identify']-row['methods']['tree_greedy']['questions_to_identify'] for row in r['rows']]
        mean=sum(xs)/32;half=2.039513*math.sqrt(sum((x-mean)**2 for x in xs)/(31*32))
        assert abs(c['low']-(mean-half))<1e-12 and abs(c['high']-(mean+half))<1e-12
    assert r['registration']['dirty'] is False
    for path,sha in r['registration']['source_hashes'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',r['execution_sha']+':'+path],cwd=ROOT)).hexdigest()==sha
    count=0
    for line in subprocess.check_output(['git','ls-tree','-r','c41b07fd04f2c85158b48dba8a407cf2a90ece85','artifacts'],cwd=ROOT,text=True).splitlines():
        meta,path=line.split('\t');body=(ROOT/path).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==meta.split()[2],path
        count+=1
    return dict(valid=True,independent_arithmetic=independent,recorded_policy_replays=160,historical_artifacts_unchanged=count,
        frozen_tree=r['library_hash'],source_cost_charged=True,collection=0,training=0,neural_inference=0)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
