"""Source-only authored contracts. Never run worlds or neural models."""
from copy import deepcopy
import importlib.util
import json
import io
import subprocess
from pathlib import Path
import pytest
from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost,METHODS,RULES
from nexus.evolution2.generated_strategies import StrategyGenerator,leaf,compose
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution1.fixtures import verify_journal
from nexus.evolution1.resources import Work,Operation,Limits,ReservationLedger,Clock
from nexus.evolution2.measured_mutation import observe_measured_pair
from nexus.evolution1.catalogue import digest
from nexus.evolution2.learning_lab import load_control_replay

ROOT=Path(__file__).resolve().parents[1]


def load_script(name):
    s=importlib.util.spec_from_file_location(name,ROOT/('scripts/'+name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def pair(parent,child,kind='synthetic_fixture_utility'):
    common=dict(kind=kind,phase='training',pair_id='fixture1',context_hash=digest('x'),reset_seed=7,planner_seed=8,horizon=1,planning_cap=1536,cpu_s=1.)
    return ({**common,'strategy':parent.fingerprint,'return':0.,'event':'p1'},
            {**common,'strategy':child.fingerprint,'return':1.,'event':'c1'})


@pytest.mark.parametrize('rule',RULES)
def test_feedback_updates_vetted_rule_and_rejects_hidden_domain(rule):
    g=StrategyGenerator(7,mutation_credit=True,mutation_rule=rule);p=leaf(VARIANTS[0]);child=compose('switch',VARIANTS[0],VARIANTS[-1],.25)
    before=g.mutation_probabilities();feedback=pair(p,child)
    with pytest.raises(ValueError):g.observe_mutation(p,child,*feedback)
    g.observe_mutation(p,child,*feedback,domain='synthetic_fixture',return_scale=1.)
    assert g.mutation_probabilities()!=before and verify_journal(g.journal.snapshot())
    with pytest.raises(ValueError):g.observe_mutation(p,child,*feedback,domain='synthetic_fixture')
    for phase in ('query','development','final'):
        pp,cc=pair(p,child);pp['phase']=cc['phase']=phase
        with pytest.raises(ValueError):g.observe_mutation(p,child,pp,cc,domain='synthetic_fixture')


def test_default_generator_remains_old_mean_no_extra_rng_draws():
    from nexus.evolution1.toy_loop import CONTEXT
    a=StrategyGenerator(7,mutation_credit=True);b=StrategyGenerator(7,mutation_credit=True,mutation_rule='mean',mutation_exploration=0.)
    assert [a.propose(CONTEXT).fingerprint for _ in range(6)]==[b.propose(CONTEXT).fingerprint for _ in range(6)]


@pytest.mark.parametrize('method',METHODS)
def test_deterministic_complete_task_streams_and_bounded_transfer(method):
    a=LearningCycle(7,method);b=LearningCycle(7,method)
    first=a.run(FixtureHost(7));second=b.run(FixtureHost(7))
    assert first==second and [p['task'] for p in first['probes']]==['A','B','A','C']
    assert first['declared_training_cost_units']==2*len(first['trace']) and first['fixture_calls']<=256
    clone=a.transfer_copy();before=deepcopy(clone.rules.state_dict());last=clone.run(FixtureHost(7),tasks=('D','E','F'))
    assert clone.rules.state_dict()==before and len(last['probes'])==3 and clone.rule_frozen
    assert last['new_real_steps']==last['model_inference']==0


def test_query_probes_do_not_change_policy_rng_or_statistics():
    c=LearningCycle(7);c.begin_task('A');g=c.stream.generator
    before=(deepcopy(g.mutation_stats),g.rng.getstate(),c.rng.getstate(),deepcopy(c.rules.state_dict()))
    c.probe(FixtureHost(7),'A')
    assert before==(g.mutation_stats,g.rng.getstate(),c.rng.getstate(),c.rules.state_dict())


def test_hidden_assessment_cannot_change_training_proposals_or_updates():
    class PoisonHost(FixtureHost):
        def evaluate(self,strategy,task,phase):
            result=super().evaluate(strategy,task,phase)
            return result if phase=='training' else -1000*result
    a=LearningCycle(8).run(FixtureHost(8));b=LearningCycle(8).run(PoisonHost(8))
    view=lambda r:[(x['child'],x['action'],x['gain'],x['after']) for x in r['trace']]
    assert view(a)==view(b)


def test_development_promotion_can_be_rolled_back_to_actual_previous_strategy():
    class Reversal:
        def evaluate(self,strategy,task,phase):
            return (1. if phase=='development' else -1.) if strategy.kind!='leaf' else 0.
    c=LearningCycle(7);original=c.incumbent;child=compose('switch',VARIANTS[2],VARIANTS[8],.25)
    c.journal.append('training_attempt',{'fixture':True})
    result=c.assess(child,Reversal(),'A')
    assert result==dict(promoted=True,rolled_back=True) and c.incumbent==original
    assert [x[0] for x in c.gate.events]==['promoted','rolled_back']


def test_failed_host_evaluation_is_charged_and_stream_pending_is_settled():
    c=LearningCycle(7);c.begin_task('A');host=FixtureHost(7,max_calls=1)
    with pytest.raises(ValueError,match='evaluation_cap'):c.step(host,'A')
    assert host.calls==1 and c.charged.cpu_units==2 and c.stream.remaining==15 and c.stream.pending is None


def report(n):
    ops=tuple(Operation('s'+str(i),'environment',Work(real_steps=1)) for i in range(n));cost=Work(real_steps=n)
    ledger=ReservationLedger(ops,Limits(cost,cost,10**9,10**9))
    for op in ops:ticket=ledger.reserve(op.key,Clock(0,0));ledger.settle(ticket,'success',Clock(0,0))
    return ledger.close(Clock(0,0))


def measured():
    p=leaf(VARIANTS[0]);c=compose('switch',VARIANTS[0],VARIANTS[-1],.25)
    protocol=dict(phase='training',pair_id='measured1',context_hash=digest('ctx'),reset_seed=1,planner_seed=2,horizon=2,planning_cap=1536,checkpoint_sha256=digest('weights'),reward_sha256=digest('reward'))
    paths={name:{**protocol,'rewards':[1.,2.] if name=='child' else [0.,1.],'cpu_s':.1,'strategy':s.fingerprint} for name,s in [('parent',p),('child',c)]}
    receipts={name:report(2) for name in paths};return p,c,paths,receipts,protocol


def test_measured_credit_comes_from_complete_charged_real_reward_paths():
    p,c,paths,receipts,protocol=measured();g=StrategyGenerator(7,mutation_credit=True)
    assert observe_measured_pair(g,p,c,paths,receipts,protocol,return_scale=1.)>0


@pytest.mark.parametrize('fault',['phase','receipt','missing','seed','checkpoint','nan','short','cpu'])
def test_measured_bridge_rejects_missing_or_unmatched_evidence(fault):
    p,c,paths,receipts,protocol=measured()
    if fault=='phase':protocol['phase']='query'
    elif fault=='receipt':receipts['child']=report(1)
    elif fault=='missing':paths.pop('child')
    elif fault=='seed':paths['child']['planner_seed']+=1
    elif fault=='checkpoint':paths['child']['checkpoint_sha256']=digest('other')
    elif fault=='nan':paths['child']['rewards'][0]=float('nan')
    elif fault=='short':paths['child']['rewards'].pop()
    elif fault=='cpu':paths['child']['cpu_s']=0.
    with pytest.raises(ValueError):observe_measured_pair(StrategyGenerator(7,mutation_credit=True),p,c,paths,receipts,protocol,return_scale=1.)


def test_recorded_replay_is_verified_and_allowlisted(tmp_path):
    for study in ('forecast16','horizon64'):
        result=load_control_replay(ROOT,study);assert result['live'] is False and len(result['cases'])==16
    with pytest.raises(ValueError):load_control_replay(ROOT,'../../secrets')


def test_fixture_api_accepts_only_small_typed_options():
    m=load_script('run_learning_lab');r=m.run_fixture_request({'seed':7,'method':'unified'})
    assert r['scientific'] is False and len(r['result']['trace'])<=8
    for bad in ({'seed':True,'method':'unified'},{'seed':7,'method':'shell'},{'seed':100,'method':'unified'},{'seed':7,'method':'unified','path':'x'}):
        with pytest.raises(ValueError):m.run_fixture_request(bad)


@pytest.mark.parametrize('fault',['seed','method','probe','nan','trace','gain','journal','boolean_count'])
def test_benchmark_completeness_is_independent_of_produced_rows(fault):
    m=load_script('run_bounded_learning_cycle');c=m.settings();c['seeds']=[91,92];c['methods']=['unified','reset_memory']
    rows=[]
    for seed in c['seeds']:
        for method in c['methods']:
            cycle=LearningCycle(seed,method,max_choices=4);source=cycle.run(FixtureHost(seed),steps_per_task=1)
            transfer=cycle.transfer_copy().run(FixtureHost(seed),tasks=('D','E','F'),steps_per_task=1)
            rows.append(dict(seed=seed,method=method,training=source,transfer=transfer))
    p={'rows':rows};assert m.validate(p,c)
    if fault=='seed':p['rows']=[r for r in rows if r['seed']!=91]
    elif fault=='method':p['rows']=[r for r in rows if r['method']!='unified']
    elif fault=='probe':p['rows'][0]['transfer']['probes'].pop()
    elif fault=='nan':p['rows'][0]['training']['probes'][0]['after']=float('nan')
    elif fault=='trace':p['rows'][0]['training']['trace'].pop()
    elif fault=='gain':p['rows'][0]['training']['gain']+=1
    elif fault=='journal':p['rows'][0]['training']['journal'][0]['payload_json']='{}'
    elif fault=='boolean_count':p['rows'][0]['training']['fixture_calls']=True
    with pytest.raises(ValueError):m.validate(p,c)


def test_fixed_planner_probe_is_actually_fixed_not_sampled_from_a_learner():
    from nexus.evolution2.generated_strategies import compose
    cycle=LearningCycle(7,'fixed_generation');host=FixtureHost(7)
    fixed=compose('switch',VARIANTS[2],VARIANTS[8],.25)
    expected=host.evaluate(fixed,'D','query')
    assert cycle.probe(host,'D')==pytest.approx(expected)


def http_request(method,path,body=b'',headers=None,enabled=True,remaining=10):
    from types import SimpleNamespace
    m=load_script('run_learning_lab')
    class Socket:
        def __init__(self,data):self.data=data;self.output=bytearray()
        def makefile(self,*unused):return io.BytesIO(self.data)
        def sendall(self,value):self.output.extend(value)
    h={'Host':'127.0.0.1:8765','Content-Length':str(len(body)),**(headers or {})}
    raw=(method+' '+path+' HTTP/1.0\r\n'+''.join(k+': '+v+'\r\n' for k,v in h.items())+'\r\n').encode()+body
    sock=Socket(raw);server=SimpleNamespace(server_port=8765,fixtures_enabled=enabled,requests_remaining=remaining)
    m.LabHandler(sock,('127.0.0.1',123),server)
    return bytes(sock.output),server


@pytest.mark.parametrize('fault,status',[('origin',403),('host',403),('header',403),('disabled',403),('cap',429),('body',400),('route',404)])
def test_http_boundary_fails_closed_without_network(fault,status):
    headers={'X-Nexus-Request':'local-fixture','Content-Type':'application/json'};payload=b'{"seed":7,"method":"unified"}';path='/api/fixture'
    if fault=='origin':headers['Origin']='https://other.example'
    elif fault=='host':headers['Host']='other.example'
    elif fault=='header':headers.pop('X-Nexus-Request')
    elif fault=='body':headers['Content-Length']='5000'
    elif fault=='route':path='/api/shell'
    response,_=http_request('POST',path,payload,headers,enabled=fault!='disabled',remaining=0 if fault=='cap' else 10)
    assert response.startswith(('HTTP/1.0 '+str(status)).encode())


def test_http_replay_and_fixture_response_payloads():
    response,_=http_request('GET','/api/replay?study=horizon64')
    assert response.startswith(b'HTTP/1.0 200') and json.loads(response.split(b'\r\n\r\n',1)[1])['live'] is False
    response,server=http_request('POST','/api/fixture',b'{"seed":7,"method":"unified"}',{'X-Nexus-Request':'local-fixture','Content-Type':'application/json'})
    value=json.loads(response.split(b'\r\n\r\n',1)[1]);assert response.startswith(b'HTTP/1.0 200')
    assert server.requests_remaining==9 and not value['scientific'] and value['live_environment'] is False


def test_lab_client_filters_inspects_decisions_and_runs_fixture_with_mock_dom():
    payload=load_control_replay(ROOT,'horizon64')
    script=r'''
const fs=require('fs'),vm=require('vm');let input='';process.stdin.on('data',s=>input+=s);process.stdin.on('end',async()=>{
const replay=JSON.parse(input),nodes={};
function node(){return {value:'',textContent:'',children:[],disabled:false,appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},setAttribute(){}};}
for(const id of ['study','family','case','tick','seed','method','run','recordStatus','forecast','chart','step','fixtureStatus','fixture'])nodes[id]=node();
Object.assign(nodes.study,{value:'horizon64'});nodes.family.value='pendulum';nodes.case.value='0';nodes.tick.value='0';nodes.seed.value='7';nodes.method.value='unified';
const document={getElementById:id=>nodes[id],createElement:node,createElementNS:node};
const fetch=async url=>({ok:true,json:async()=>url.startsWith('/api/replay')?replay:url==='/api/status'?{fixtures_enabled:true,requests_remaining:9}:{result:{gain:0,trace:[],policy:{},probes:[],declared_training_cost_units:2}}});
const html=fs.readFileSync('web/learning-lab/index.html','utf8'),code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const c=vm.createContext({document,fetch,console});vm.runInContext(code,c);await new Promise(setImmediate);
if(nodes.case.children.length!==8||nodes.chart.children.length!==2||!nodes.step.textContent.includes('original_episode_step'))throw Error('initial replay');
nodes.family.value='acrobot';nodes.family.onchange();if(nodes.case.children.length!==8)throw Error('family filter');
await nodes.run.onclick();if(!nodes.fixtureStatus.textContent.includes('Fixture complete'))throw Error('fixture run');
console.log('client interactions verified with mocked DOM; not browser visual QA');});
'''
    result=subprocess.run(['/opt/homebrew/bin/node','-e',script],input=json.dumps(payload),text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr
