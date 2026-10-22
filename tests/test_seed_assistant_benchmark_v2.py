"""Mock orchestration and authored tool fixtures. No model inference here."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import threading
from types import SimpleNamespace

import pytest

from nexus.seed.local_model_runtime import RuntimeConfig,PersistentLocalRuntime,gguf_file_type
from nexus.seed.assistant_benchmark_v2 import Assistant,SCHEMA,validate_intent,intent_prompt,skeleton

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('assistant_verifier_test',ROOT/'scripts/verify_seed_assistant_benchmark_v2.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


class Process:
    def __init__(self):self.code=None;self.terminations=0
    def poll(self):return self.code
    def terminate(self):self.code=0;self.terminations+=1
    def wait(self,timeout=None):return self.code
    def kill(self):self.code=-9


def runtime():
    r=PersistentLocalRuntime(RuntimeConfig('unused-unit-test-path',request_timeout_s=.05))
    r.process=Process()
    return r


def test_response_cache_has_zero_new_tokens_measured_lookup_and_isolation():
    a,b=runtime(),runtime();calls=[]
    def http(*args,**kwargs):
        calls.append(args);return {'content':'{"op":"rows","min":5,"order":"desc"}',
                                  'tokens_evaluated':9,'tokens_predicted':12,'timings':{'cache_n':0}}
    a._http=http;b._http=http
    one=a.complete('prompt',SCHEMA);two=a.complete('prompt',SCHEMA);three=b.complete('prompt',SCHEMA)
    assert len(calls)==2
    assert one['telemetry']['generated_tokens']==12 and three['telemetry']['inference_ran']
    assert two['telemetry']['generated_tokens']==two['telemetry']['input_tokens']==0
    assert not two['telemetry']['inference_ran'] and two['telemetry']['application_cache_hit']
    assert two['telemetry']['request_wall_s']>=0 and two['telemetry']['runtime_timings'] is None
    a.clear_cache();a.complete('prompt',SCHEMA);assert len(calls)==3
    a.close();b.close()


def test_missing_telemetry_unavailable_not_fabricated_zero():
    r=runtime();r._http=lambda *a,**k:{'content':'{}'}
    t=r.complete('x',SCHEMA)['telemetry']
    assert t['input_tokens'] is t['generated_tokens'] is t['runtime_timings'] is None
    r.close()


def test_timeout_cancellation_stops_owned_server_without_retry():
    r=runtime();proc=r.process
    def blocked(*a,**k):
        r._cancel.wait(1)
        raise TimeoutError('authored blocked transport')
    r._http=blocked
    with pytest.raises(TimeoutError):r.complete('x',SCHEMA)
    assert proc.terminations==1 and r.process is None
    with pytest.raises(RuntimeError,match='started'):r.complete('x',SCHEMA)


def test_explicit_cancellation_and_runtime_failure_close_only_owned_process():
    r=runtime();proc=r.process;r.cancel()
    assert proc.code==0 and proc.terminations==1
    r=runtime();proc=r.process
    def bad(*a,**k):raise RuntimeError('HTTP 503')
    r._http=bad
    with pytest.raises(RuntimeError):r.complete('x',SCHEMA)
    assert proc.terminations==1


def test_persistent_lifecycle_paths_and_cpu_flags(monkeypatch,tmp_path):
    model=tmp_path/'model.gguf'
    key=b'general.file_type'
    model.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,1)+struct.pack('<Q',len(key))+key+struct.pack('<II',4,15))
    assert gguf_file_type(model)==15
    commands=[];proc=Process()
    monkeypatch.setattr('nexus.seed.local_model_runtime.shutil.which',lambda _: '/vetted/local/llama-server')
    monkeypatch.setattr('nexus.seed.local_model_runtime.subprocess.run',lambda *a,**k:SimpleNamespace(stdout='fixture-runtime',stderr=''))
    monkeypatch.setattr('nexus.seed.local_model_runtime.file_hash',lambda _: 'f'*64)
    monkeypatch.setattr('nexus.seed.local_model_runtime.platform.platform',lambda: 'fixture OS')
    def spawn(args,**kwargs):commands.append(args);return proc
    monkeypatch.setattr('nexus.seed.local_model_runtime.subprocess.Popen',spawn)
    r=PersistentLocalRuntime(RuntimeConfig(str(model)))
    monkeypatch.setattr(r,'_http',lambda *a,**k:{'status':'ok'})
    first=r.start();r.start()
    assert len(commands)==1 and first['gguf_file_type']==15
    assert commands[0][commands[0].index('-ngl')+1]=='0'
    assert '--offline' in commands[0] and '--no-op-offload' in commands[0]
    assert '--api-key' in commands[0] and r._api_key not in json.dumps(first)
    assert commands[0][commands[0].index('-m')+1]==str(model.resolve())
    r.close();assert proc.terminations==1


@pytest.mark.parametrize('obj',(
    {},{'op':'sum','min':True,'order':'desc'}, {'op':'sum','min':float('nan'),'order':'desc'},
    {'op':'clarify','min':5,'order':'desc'}, {'op':'execute_shell','min':None,'order':'desc'},
    {'op':'rows','min':0,'order':'desc','extra':1},
))
def test_inconsistent_or_malformed_intents(obj):
    with pytest.raises(ValueError):validate_intent(obj)


class ModelFixture:
    def __init__(self,op='sum',minimum=5,order='desc'):
        self.obj=dict(op=op,min=minimum,order=order);self.prompts=[]
    def complete(self,prompt,schema):
        self.prompts.append(prompt)
        return dict(content=json.dumps(self.obj),request_sha256='fixture',telemetry=dict(
            inference_ran=True,application_cache_hit=False,input_tokens=1,generated_tokens=1,
            prompt_cache_tokens=None,runtime_timings=None,request_wall_s=.001))


def source(tmp_path,first='region',second='amount'):
    path=tmp_path/(first+'.csv')
    path.write_text(f'{first},{second}\nA,9\nA,12\nB,4\n')
    return path


def test_same_file_different_model_intent_changes_executable_action(tmp_path):
    path=source(tmp_path);model=ModelFixture();a=Assistant(model,'nexus_capsules')
    grouped=a.solve('sum instruction',path)
    model.obj['op']='rows'
    rows=a.solve('individual instruction',path)
    assert grouped['status']==rows['status']=='executed'
    assert grouped['output']==[{'region':'a','total':21.0}]
    assert rows['output']==[{'region':'a','amount':12.0},{'region':'a','amount':9.0}]
    assert grouped['program']!=rows['program']
    assert rows['counters']['capsule_hit']==0
    assert model.prompts[0]!=model.prompts[1]
    assert 'expected' not in model.prompts[0]


def test_all_methods_execute_without_promotion_and_match(tmp_path):
    path=source(tmp_path)
    outputs=[]
    for method in ('tools_retrieval','ordinary_cache','nexus_capsules'):
        a=Assistant(ModelFixture(),method);r=a.solve('request',path)
        assert r['status']=='executed' and r['counters']['candidate_executions']==1
        outputs.append(r['output'])
    assert outputs[0]==outputs[1]==outputs[2]


def test_program_cache_and_parameterized_capsule_rebinding(tmp_path):
    a=Assistant(ModelFixture(),'nexus_capsules');first=source(tmp_path)
    a.solve('one',first);cached=a.solve('repeat',first)
    assert cached['counters']['program_cache_hit']==1
    second=source(tmp_path,'zone','latency');rebound=a.solve('two',second)
    assert rebound['counters']['capsule_hit']==1
    assert rebound['output']==[{'zone':'a','total':21.0}]
    a.programs.clear()
    next(iter(a.capsules.values())).task_kind='wrong'
    rejected=a.solve('two',second)
    assert rejected['status']=='failure' and 'inappropriate' in rejected['error']


def test_clarification_and_unsupported_execute_nothing(tmp_path):
    path=source(tmp_path)
    for op in ('clarify','unsupported'):
        a=Assistant(ModelFixture(op,None),'nexus_capsules');r=a.solve('x',path)
        assert r['status']==op and r['counters']['candidate_executions']==0
        assert not a.programs and not a.capsules


def test_no_class_level_decode_cache_or_user_specific_paths():
    text=(ROOT/'src/nexus/seed/real_data_adapter_learning.py').read_text()
    assert '_DECODE_CACHE' not in text and '/Users/' not in text and '/opt/homebrew/' not in text


def test_no_empty_grid_success_and_independent_numerical_interval():
    config=json.loads((ROOT/'configs/seed_assistant_benchmark_v2.json').read_text())
    r=verifier.reconstruct([],config)
    assert not r['declared_complete'] and not r['passed'] and r['missing_trials']==144
    p=verifier.paired([1,2,3,4])
    assert p['mean']==2.5 and p['median']==2.5
    expected=3.182446305*(5/3)**.5/2
    assert abs(p['t95'][0]-(2.5-expected))<1e-12


def test_invalid_config_and_missing_model_fail_no_fallback(tmp_path):
    for cfg in (RuntimeConfig('x',host='0.0.0.0'),RuntimeConfig('x',backend='templates')):
        with pytest.raises(ValueError):PersistentLocalRuntime(cfg)
    r=PersistentLocalRuntime(RuntimeConfig(str(tmp_path/'missing.gguf')))
    with pytest.raises(FileNotFoundError):r.start()


def test_startup_failure_is_cleaned_up(monkeypatch,tmp_path):
    model=tmp_path/'model.gguf';model.write_bytes(b'unit fixture')
    monkeypatch.setattr('nexus.seed.local_model_runtime.shutil.which',lambda _: '/local/server')
    monkeypatch.setattr('nexus.seed.local_model_runtime.gguf_file_type',lambda _:15)
    monkeypatch.setattr('nexus.seed.local_model_runtime.subprocess.run',lambda *a,**k:SimpleNamespace(stdout='fixture',stderr=''))
    proc=Process();proc.code=3
    monkeypatch.setattr('nexus.seed.local_model_runtime.subprocess.Popen',lambda *a,**k:proc)
    r=PersistentLocalRuntime(RuntimeConfig(str(model)))
    with pytest.raises(RuntimeError,match='startup'):r.start()
    assert r.process is None


def mock_grid():
    """Synthetic timing records only; NOT generated target cases or outcomes."""
    c=json.loads((ROOT/'configs/seed_assistant_benchmark_v2.json').read_text())
    records=[dict(kind='live_integration',passed=True,fixture_only=True)]
    for rep in range(2):
        for m in verifier.METHODS:
            records.append(dict(kind='startup',repeat=rep,method=m,metadata={'model_sha256':c['model_sha256']}))
            for phase in ('cold','warm'):
                for index,case in enumerate(c['cases']):
                    seconds=2.0 if m=='nexus_capsules' else 3.0
                    result=dict(status='executed',workflow_s=seconds,stages={'mock_stage':seconds},
                        counters={'candidate_executions':1,'questions':0,'abstractions':0,'capsule_hit':0},
                        library_bytes=0,program=[{'mock':m}],output=[{'mock':index}],
                        telemetry=dict(inference_ran=True,application_cache_hit=False,input_tokens=7,
                                       generated_tokens=3,prompt_cache_tokens=None))
                    records.append(dict(kind='trial',repeat=rep,method=m,phase=phase,index=index,
                        task_id=case['id'],file_id=case['file'],correct=True,result=result,
                        cold_startup_s=1.0 if phase=='cold' and index==0 else 0,
                        amortized_startup_s=1/24))
    return c,records


def test_reconstructs_full_mock_grid_and_does_not_count_repetitions_as_tasks():
    c,records=mock_grid();r=verifier.reconstruct(records,c)
    assert r['declared_complete'] and r['expected_trials']==144
    assert r['methods']['nexus_capsules']['confirmed_model_calls']==48
    assert r['methods']['nexus_capsules']['generated_tokens_known_sum']==144
    p=r['paired_file_block_contrasts']['ordinary_cache']['baseline_minus_nexus_latency_s']
    assert p['mean']==pytest.approx(1.0) and p['independent_blocks']==4
    assert p['identical_differences_warning']


@pytest.mark.parametrize('removed',('method','task','startup','repetition'))
def test_missing_planned_blocks_are_incomplete(removed):
    c,records=mock_grid()
    if removed=='method':records=[r for r in records if r.get('method')!='ordinary_cache']
    if removed=='task':records=[r for r in records if r.get('task_id')!='repeat_1']
    if removed=='startup':records=[r for r in records if r['kind']!='startup']
    if removed=='repetition':records=[r for r in records if r.get('repeat')!=1]
    assert not verifier.reconstruct(records,c)['declared_complete']


def test_raw_corruption_and_stale_cache_telemetry_rejected():
    c,records=mock_grid();trial=next(r for r in records if r['kind']=='trial')
    records.append(deepcopy(trial))
    with pytest.raises(ValueError,match='duplicate'):verifier.reconstruct(records,c)
    records.pop();trial['result']['telemetry']['application_cache_hit']=True
    with pytest.raises(ValueError,match='stale'):verifier.reconstruct(records,c)
    assert verifier.parse_records(b'{"kind":"fixture"}\n{"broken":')[1]['kind']=='invalid_record'


def test_verifier_does_not_import_benchmark_result_builders():
    import ast
    tree=ast.parse((ROOT/'scripts/verify_seed_assistant_benchmark_v2.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):
            assert 'assistant_benchmark_v2' not in (node.module or '')


def test_worker_cannot_bypass_durable_host_reservation(tmp_path):
    s=importlib.util.spec_from_file_location('assistant_host_test',ROOT/'scripts/run_seed_assistant_benchmark_v2.py')
    host=importlib.util.module_from_spec(s);s.loader.exec_module(host)
    with pytest.raises(ValueError,match='registered'):
        host.worker(SimpleNamespace(directory=str(tmp_path)),{})


def test_infrastructure_amendment_preserves_the_scientific_design():
    a=json.loads((ROOT/'configs/seed_assistant_benchmark_v2.json').read_text())
    b=json.loads((ROOT/'configs/seed_assistant_benchmark_v2_1.json').read_text())
    for key in ('cases','files','runtime','cold_repetitions','order_seed','success_rule','model_sha256'):
        assert a[key]==b[key]
    assert b['carried_used_s']==pytest.approx(a['carried_used_s']+12)


def test_ordinary_signature_cache_includes_field_types(tmp_path):
    p=source(tmp_path);a=Assistant(ModelFixture(),'ordinary_cache')
    assert a.solve('x',p)['status']=='executed'
    p.write_text('region,amount\n9,A\n12,A\n4,B\n')
    result=a.solve('x',p)
    assert result['status']=='executed' and result['counters']['program_cache_hit']==0
    assert result['output']==[{'amount':'a','total':21.0}]


def test_saved_real_model_accounting_and_posthoc_analysis_reconstruct():
    path=ROOT/'artifacts/seed_assistant_benchmark_v2_1_raw.jsonl'
    if not path.exists():pytest.skip('post-run artifact not present in pre-run revision')
    records=verifier.parse_records(path.read_bytes())
    cfg=json.loads((ROOT/'configs/seed_assistant_benchmark_v2_1.json').read_text())
    summary=verifier.reconstruct(records,cfg)
    assert summary['declared_complete'] and not summary['passed']
    assert summary['methods']['nexus_capsules']['candidate_executions']==40
    for method in verifier.METHODS:
        assert summary['methods'][method]['correct']==40
        assert summary['methods'][method]['application_cache_hits']==26
    s=importlib.util.spec_from_file_location('posthoc_analysis_test',ROOT/'scripts/analyze_seed_assistant_benchmark_v2.py')
    a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
    result=a.analyze(records)
    assert result==json.loads((ROOT/'artifacts/seed_assistant_benchmark_v2_1_analysis.json').read_text())
    assert result['all_requests_including_integration']['confirmed_model_calls']==67
    assert result['all_requests_including_integration']['actual_generated_tokens']==956
    assert all(x['t95_s'][0]<0<x['t95_s'][1] for x in result['timing_reset_replication_sensitivity'].values())


def test_independent_saved_output_verifier_rejects_forged_correctness():
    path=ROOT/'artifacts/seed_assistant_benchmark_v2_1_raw.jsonl'
    if not path.exists():pytest.skip('post-run artifact not present in pre-run revision')
    records=verifier.parse_records(path.read_bytes())
    cfg=json.loads((ROOT/'configs/seed_assistant_benchmark_v2_1.json').read_text())
    verifier.verify_outputs(records,cfg,ROOT/'artifacts/seed_assistant_benchmark_v2_1_inputs')
    forged=deepcopy(records)
    next(r for r in forged if r['kind']=='trial' and not r['correct'])['correct']=True
    with pytest.raises(ValueError,match='forged'):
        verifier.verify_outputs(forged,cfg,ROOT/'artifacts/seed_assistant_benchmark_v2_1_inputs')


def test_exported_resource_journal_reconstructs_and_rejects_corruption():
    path=ROOT/'artifacts/seed_assistant_benchmark_v2_1_ledger.json'
    if not path.exists():pytest.skip('post-run journal export absent')
    s=importlib.util.spec_from_file_location('ledger_analysis_test',ROOT/'scripts/analyze_seed_assistant_benchmark_v2.py')
    a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
    ledger=json.loads(path.read_text())
    assert a.verify_ledger(ledger)==pytest.approx(2186.632103455996)
    assert len(ledger['events'])==8
    altered=deepcopy(ledger);altered['events'][-1]['payload_json']='{}'
    with pytest.raises(ValueError,match='event'):a.verify_ledger(altered)
