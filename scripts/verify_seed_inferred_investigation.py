"""Independent stdlib arithmetic/provenance verification; no learner or collector."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='b480a507f005c41340c518ce483a3e27383cc78e'


def verify(root=ROOT):
    raw=(root/'artifacts/seed_inferred_investigation.json').read_bytes();r=json.loads(raw);c=r['config']
    if r['declared_complete'] is not True or r['registration']['dirty']:raise ValueError('incomplete_or_dirty')
    sha=lambda data:hashlib.sha256(data).hexdigest()
    gitread=lambda ref,p:subprocess.check_output(['git','show',ref+':'+p],cwd=root)
    for name,expected in r['registration']['source_hashes'].items():
        if sha(gitread(r['execution_sha'],name))!=expected:raise ValueError('source_hash')
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'artifacts'],cwd=root,text=True).splitlines()
    for name in paths:
        if (root/name).read_bytes()!=gitread(BASE,name):raise ValueError('historical_artifact_changed')
    if [x['id'] for x in r['blocks']]!=c['families']:raise ValueError('family_grid')
    families={m:[] for m in c['methods']};totals={m:0 for m in families};decisions=0
    def source_cost(tree,rows,depth=0):
        if tree['op']!='probe':return 0
        q=tree['index'];return 2*len(rows)*(8-depth)+sum(source_cost(child,[a for a in rows if a[q]==bool(j)],depth+1) for j,child in enumerate(tree['branches']))
    for index,block in enumerate(r['blocks']):
        table=[None]*8
        for example in block['source']:
            i=example['hypothesis']
            if example['role']!='source':raise ValueError('non_source_label')
            if table[i] is not None and table[i]!=example['answers']:raise ValueError('source_inconsistent')
            table[i]=example['answers']
        if table!=block['fitted']['model']['table'] or table!=block['evaluator_table']:raise ValueError('source_reconstruction')
        compile_reads=0
        for key,node in block['fitted']['policy']['nodes'].items():
            ids,available=key.split('|');ids=list(map(int,ids.split(',')));available=list(map(int,available.split(',')))
            if node['question'] is None:continue
            scores=[]
            for q in available:
                yes=sum(table[i][q] for i in ids);scores.append((yes**2+(len(ids)-yes)**2,q))
            if node['question']!=min(scores)[1]:raise ValueError('compiler_argmin')
            compile_reads+=len(ids)*(len(available)+1)
        tree_reads=source_cost(block['fitted']['library']['tree'],[s['answers'] for s in block['source']])
        expected_ids=c['tasks']['target'][32*index:32*(index+1)]
        if [row['task'] for row in block['rows']]!=expected_ids:raise ValueError('task_grid')
        for row in block['rows']:
            if set(row['methods'])!=set(c['methods']):raise ValueError('method_grid')
            for method,data in row['methods'].items():
                decisions+=1;ids=list(range(8));seen=[]
                for step in data['steps']:
                    q=step['question']
                    if q in seen or step['posterior_before']!=ids or step['answer'] is not row['support_answers'][q]:raise ValueError('answer_or_belief')
                    seen.append(q);ids=[i for i in ids if table[i][q]==step['answer']]
                    if ids!=step['posterior_after']:raise ValueError('posterior')
                if data['questions_to_identify']!=(len(seen) if len(ids)==1 else 9):raise ValueError('question_count')
                if set(data['metrics'])!={'1','2','4','8'}:raise ValueError('budget_grid')
                for budget in (1,2,4,8):
                    expected_post=list(range(8)) if not data['steps'] else data['steps'][min(budget,len(seen))-1]['posterior_after']
                    post=data['snapshots'][str(budget)]['posterior']
                    if post!=expected_post:raise ValueError('snapshot')
                    pred=[sum(table[i][f['query']] for i in post)/len(post) for f in row['final']]
                    acc=sum((p>=.5)==f['answer'] for p,f in zip(pred,row['final']))/32
                    brier=sum((p-int(f['answer']))**2 for p,f in zip(pred,row['final']))/32
                    if pred!=data['predictions'][str(budget)] or abs(acc-data['metrics'][str(budget)]['accuracy'])>1e-12 or abs(brier-data['metrics'][str(budget)]['brier'])>1e-12:raise ValueError('metric_arithmetic')
            for k in ('steps','snapshots','questions_to_identify','predictions','metrics'):
                if row['methods']['compiled_greedy'][k]!=row['methods']['greedy'][k]:raise ValueError('compiled_equivalence')
        for m in families:
            ds=[row['methods'][m] for row in block['rows']]
            mean=sum(len(d['steps']) for d in ds)/32;families[m].append(mean)
            runtime=sum(d['costs']['hypothesis_predictions']+d['costs']['tree_nodes'] for d in ds)
            total=480+runtime+(compile_reads if m=='compiled_greedy' else tree_reads if m=='tree_greedy' else 0)
            if abs(mean-block['means'][m]['questions'])>1e-12 or total!=block['means'][m]['total_work']:raise ValueError('family_cost')
            totals[m]+=total
    intervals={}
    for m in families:
        if st.mean(families[m])!=r['analysis']['means'][m]['questions'] or totals[m]!=r['analysis']['means'][m]['total_work']:raise ValueError('aggregate')
        if m=='tree_greedy':continue
        d=[a-b for a,b in zip(families[m],families['tree_greedy'])];mean=st.mean(d);half=2.364624251*st.stdev(d)/math.sqrt(8)
        intervals[m]=dict(mean=mean,low=mean-half,high=mean+half)
        for key,value in intervals[m].items():
            if abs(value-r['analysis']['question_savings'][m][key])>1e-12:raise ValueError('paired_family_interval')
    if decisions!=1280 or r['resources']['real_steps']!=12544 or r['execution_debit_s']!=math.ceil(r['host_receipt']['wall_s'])+1:raise ValueError('resource_grid')
    return dict(valid=True,raw_sha256=sha(raw),execution_sha=r['execution_sha'],historical_artifacts_unchanged=len(paths),
        policies_checked=decisions,all_compiled_online_choices_exact=True,mean_questions={m:st.mean(x) for m,x in families.items()},
        independent_work_totals=totals,paired_family_intervals=intervals,new_collection=0,model_fits=0,
        scope='verification only; scientific collection costs are in the original result')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',type=Path);args=p.parse_args();result=verify()
    if args.write:
        with args.write.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))
