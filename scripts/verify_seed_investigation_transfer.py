"""Replay recorded answers and independently aggregate. No collection or fitting."""
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.investigation_transfer import adapt,validate_output,METHODS,BUDGETS,LabelOracle


def verify():
    r=json.loads((ROOT/'artifacts/seed_investigation_transfer.json').read_text())
    validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=5000,updates=0,imagined_transitions=0))
    arithmetic={};replayed=0
    for method in METHODS:
        questions=[];accuracy={str(b):[] for b in BUDGETS}
        for row in r['rows']:
            d=row['methods'][method];replay=adapt(method,r['library'],LabelOracle(row['support_bank_answers'],8).reveal,row['task']+700)
            recorded=copy.deepcopy(d)
            for k in ('metrics','predictions'):recorded.pop(k)
            assert replay==recorded,'recorded choice replay';replayed+=1
            questions.append(len(d['steps']) if len(d['steps'][-1]['posterior_after'])==1 else 9)
            for b in BUDGETS:
                preds=d['predictions'][str(b)];labels=[x['answer'] for x in row['final']]
                accuracy[str(b)].append(sum(int(p>=.5)==int(y) for p,y in zip(preds,labels))/len(labels))
        arithmetic[method]=dict(questions=sum(questions)/len(questions),accuracy={b:sum(v)/len(v) for b,v in accuracy.items()})
        assert arithmetic[method]['questions']==r['analysis']['means'][method]['questions']
        assert arithmetic[method]['accuracy']==r['analysis']['means'][method]['accuracy']
    for method in METHODS[1:]:
        delta=[row['methods'][method]['questions_to_identify']-row['methods']['learned']['questions_to_identify'] for row in r['rows']]
        mean=sum(delta)/32;se=math.sqrt(sum((v-mean)**2 for v in delta)/(31*32));v=r['analysis']['question_savings'][method]
        assert abs(v['low']-(mean-2.039513*se))<1e-12 and abs(v['high']-(mean+2.039513*se))<1e-12
    assert r['registration']['dirty'] is False
    assert r['registration']['revision']==r['execution_sha']
    for path,sha in r['registration']['source_hashes'].items():
        body=subprocess.check_output(['git','show',r['execution_sha']+':'+path],cwd=ROOT)
        assert hashlib.sha256(body).hexdigest()==sha,path
    base='6f4b17ff2297aec9c7f54966d9d7a9ff9712e24f';count=0
    for line in subprocess.check_output(['git','ls-tree','-r',base,'artifacts'],cwd=ROOT,text=True).splitlines():
        meta,path=line.split('\t');body=(ROOT/path).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==meta.split()[2],path
        count+=1
    return dict(valid=True,recorded_policy_replays=replayed,independent_arithmetic=arithmetic,historical_artifacts_unchanged=count,
                source_hashes_verified=True,collection=0,model_inference=0,training=0)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
