"""Saved-data verification, not a new collection or source-tree refit."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import investigation_replication as r


def verify():
    record=json.loads((ROOT/'artifacts/seed_investigation_replication.json').read_text())
    r.validate_output(dict(study=record,resources=record['resources']),record['config'],dict(real_steps=5000,updates=0,imagined_transitions=0))
    means={};per_tree={}
    for rep in record['replications']:
        per_tree[str(rep['id'])]={}
        for method in r.h.METHODS:
            values=[row['methods'][method] for row in rep['study']['rows']]
            q=sum(len(v['steps']) for v in values)/32
            assert q==rep['study']['analysis']['means'][method]['questions']
            per_tree[str(rep['id'])][method]=q
            for budget in r.b.BUDGETS:
                correct=sum(sum((p>=.5)==f['answer'] for p,f in zip(row['methods'][method]['predictions'][str(budget)],row['final'])) for row in rep['study']['rows'])
                assert correct/1024==rep['study']['analysis']['means'][method]['accuracy'][str(budget)]
    for method in r.h.METHODS:
        mean=sum(v[method] for v in per_tree.values())/3;means[method]=mean
        assert abs(mean-record['analysis']['means'][method]['questions'])<1e-12
        if method=='tree_greedy':continue
        xs=[v[method]-v['tree_greedy'] for v in per_tree.values()];m=sum(xs)/3
        half=4.30265272991*math.sqrt(sum((x-m)**2 for x in xs)/6)
        c=record['analysis']['question_savings'][method]
        assert abs(c['low']-(m-half))<1e-12 and abs(c['high']-(m+half))<1e-12
    assert record['registration']['dirty'] is False
    for path,sha in record['registration']['source_hashes'].items():
        blob=subprocess.check_output(['git','show',record['execution_sha']+':'+path],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==sha,path
    count=0
    for line in subprocess.check_output(['git','ls-tree','-r','7ee43e296c521c713f41e3c4cd4508a152853089','artifacts'],cwd=ROOT,text=True).splitlines():
        meta,path=line.split('\t');data=(ROOT/path).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==meta.split()[2],path
        count+=1
    policies={};source_counts={}
    for i,rep in enumerate(record['replications']):
        signatures={};counts=[0]*8
        for source in rep['study']['source']:
            answers=[e['answer'] for e in source['episodes']];counts[next(j for j,row in enumerate(r.b.TABLE) if list(row)==answers)]+=1
        for row in rep['study']['rows']:
            law=r.subconfig(record['config'],i)['target_laws'][str(row['task'])]
            sequence=[s['question'] for s in row['methods']['tree_greedy']['steps']]
            if law in signatures:assert signatures[law]==sequence
            signatures[law]=sequence
        policies[str(rep['id'])]=signatures;source_counts[str(rep['id'])]=counts
    return dict(valid=True,independent_trees=3,paired_unit='source_tree',df=2,means=means,per_tree_questions=per_tree,
        policy_replays=480,old_artifacts_unchanged=count,source_class_counts=source_counts,
        observed_hybrid_policy_signatures=policies,distinct_observed_hybrid_policies=len({r.digest(v) for v in policies.values()}),
        collection=0,training=0,neural_inference=0)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
