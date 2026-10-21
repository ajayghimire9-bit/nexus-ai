"""Independent stdlib saved-arithmetic and historical-file audit. No collection."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='9b8360aadabe2e79570e1b1a3d62c89191aeb552'


def verify(root=ROOT):
    raw=(root/'artifacts/seed_compiled_greedy.json').read_bytes();r=json.loads(raw)
    parent=json.loads((root/'artifacts/seed_investigation_replication.json').read_text())
    if not r['declared_complete'] or r['registration']['dirty']:raise ValueError('incomplete_or_dirty')
    read_git=lambda ref,p:subprocess.check_output(['git','show',ref+':'+p],cwd=root)
    sha=lambda data:hashlib.sha256(data).hexdigest()
    for path,expected in r['registration']['source_hashes'].items():
        if sha(read_git(r['execution_sha'],path))!=expected:raise ValueError('execution_source_hash:'+path)
    oldpaths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'artifacts'],cwd=root,text=True).splitlines()
    for p in oldpaths:
        if (root/p).read_bytes()!=read_git(BASE,p):raise ValueError('historical_artifact_changed:'+p)
    # Independently derive the public grammar, avoiding runtime hypotheses/scorer.
    truth=[]
    for law in range(8):
        row=[]
        for j in range(8):
            a,b,c=bool(j&1),bool(j&2),bool(j&4)
            row.append((a,b,c,a and b,a or b,a!=b,int(a)+int(b)+int(c)>=2,not a)[law])
        truth.append(row)
    nodecost=0;score_reads=part_reads=0
    for k,node in r['policy']['nodes'].items():
        left,right=k.split('|');ids=list(map(int,left.split(',')));qs=list(map(int,right.split(',')))
        if node['question'] is None:continue
        scores=[]
        for q in qs:
            yes=sum(truth[i][q] for i in ids);scores.append((yes**2+(len(ids)-yes)**2,q))
        if node['question']!=min(scores)[1]:raise ValueError('compiled_argmin')
        score_reads+=len(ids)*len(qs);part_reads+=len(ids)
    nodecost=score_reads+part_reads
    totals={m:0 for m in r['config']['methods']};means={m:[] for m in totals};diff=[];saved_tasks=0
    for block,old in zip(r['blocks'],parent['replications']):
        for m in totals:
            data=[row['methods'][m] for row in block['rows']]
            means[m].append(sum(len(x['steps']) for x in data)/32)
            runtime=sum(x['costs']['hypothesis_predictions']+x['costs']['tree_nodes'] for x in data)
            construction=nodecost if m=='compiled_greedy' else old['study']['analysis']['source_cost']['source_split_comparisons'] if m=='tree_greedy' else 0
            totals[m]+=runtime+construction
            if block['means'][m]['total_work']!=runtime+construction:raise ValueError('block_cost')
        diff.append(means['compiled_greedy'][-1]-means['tree_greedy'][-1])
        for row,previous in zip(block['rows'],old['study']['rows']):
            saved_tasks+=1
            for method,d in row['methods'].items():
                ids=list(range(8));seen=[]
                for step in d['steps']:
                    if step['posterior_before']!=ids:raise ValueError('prior')
                    q=step['question'];seen.append(q)
                    if q in seen[:-1] or step['answer'] is not previous['support_bank_answers'][q]:raise ValueError('answer_boundary')
                    ids=[i for i in ids if truth[i][q]==step['answer']]
                    if ids!=step['posterior_after']:raise ValueError('posterior')
                for budget in (1,2,4,8):
                    post=d['snapshots'][str(budget)]['posterior']
                    probs=[]
                    for f in previous['final']:
                        j=sum((1<<k)*int(v) for k,v in enumerate(f['bits']))
                        probs.append(sum(truth[i][j] for i in post)/len(post))
                    acc=sum((p>=.5)==f['answer'] for p,f in zip(probs,previous['final']))/32
                    mse=sum((p-int(f['answer']))**2 for p,f in zip(probs,previous['final']))/32
                    if d['predictions'][str(budget)]!=probs or abs(d['metrics'][str(budget)]['accuracy']-acc)>1e-12 or abs(d['metrics'][str(budget)]['brier']-mse)>1e-12:raise ValueError('assessment_arithmetic')
            for field in ('steps','snapshots','questions_to_identify','metrics','predictions'):
                if row['methods']['compiled_greedy'][field]!=row['methods']['greedy'][field]:raise ValueError('exact_equivalence')
    if saved_tasks!=96 or len(r['blocks'])!=3:raise ValueError('complete_grid')
    for m,v in totals.items():
        if v!=r['analysis']['means'][m]['total_work'] or st.mean(means[m])!=r['analysis']['means'][m]['questions']:raise ValueError('aggregate')
    if r['execution_debit_s']!=math.ceil(r['host_receipt']['wall_s'])+1:raise ValueError('debit')
    if r['session_used_s']!=r['config']['carried_used_s']+r['execution_debit_s']:raise ValueError('ledger')
    mean=st.mean(diff);half=4.30265272991*st.stdev(diff)/math.sqrt(3)
    return dict(valid=True,raw_sha256=sha(raw),historical_artifacts_unchanged=len(oldpaths),
        execution_sha=r['execution_sha'],all_96_decisions_and_predictions_exact=True,
        independent_cost_totals=totals,construction_score_reads=score_reads,construction_partition_reads=part_reads,
        compiled_minus_hybrid_questions=dict(mean=mean,low=mean-half,high=mean+half,n=3,df=2,
            unit='reused_source_library_block; fixed grammar, not three newly learned compiled policies'),
        scientific_execution=False,new_collection=0,neural_training=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',type=Path);args=p.parse_args();result=verify()
    if args.write:
        with args.write.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))
