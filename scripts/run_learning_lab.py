"""Loopback-only recorded replay and opt-in bounded authored fixture playground."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from contextlib import nullcontext
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse,parse_qs
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.evolution2.learning_lab import load_control_replay,load_operator_replay,load_training_audit,load_preparation


def run_fixture_request(payload):
    from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost
    if type(payload) is not dict or set(payload)!={'seed','method'}:raise ValueError('fixture_options_only')
    if type(payload['seed']) is not int or not 0<=payload['seed']<=99 or payload['method'] not in ('unified','random_generation','fixed_generation','reset_memory','shuffled_memory'):raise ValueError('bounded_fixture_options')
    result=LearningCycle(payload['seed'],payload['method'],max_choices=8).run(FixtureHost(payload['seed']),steps_per_task=2)
    return dict(scientific=False,live_environment=False,result=result)


class LabHandler(BaseHTTPRequestHandler):
    def log_message(self,*unused):pass
    def send_json(self,status,value):
        body=json.dumps(value,allow_nan=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def local_request(self):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in hosts:return False
        return self.headers.get('Origin') in (None,)+tuple('http://'+h for h in hosts)
    def do_GET(self):
        if not self.local_request():return self.send_json(403,{'error':'local_origin_required'})
        parsed=urlparse(self.path)
        try:
            if parsed.path=='/foundation' and not parsed.query:
                body=(ROOT/'web/learning-lab/foundation.html').read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
                self.end_headers();return self.wfile.write(body)
            if not parsed.query and (parsed.path in ('/chat','/chat.css','/chat.js') or parsed.path=='/' and getattr(self.server,'seed_workspace',None)):
                name={'/':'chat.html','/chat':'chat.html','/chat.css':'chat.css','/chat.js':'chat.js'}[parsed.path]
                body=(ROOT/'web/learning-lab'/name).read_bytes();self.send_response(200)
                self.send_header('Content-Type',{'chat.html':'text/html; charset=utf-8','chat.css':'text/css; charset=utf-8','chat.js':'text/javascript; charset=utf-8'}[name])
                self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
                self.end_headers();return self.wfile.write(body)
            if parsed.path=='/labs' and not parsed.query:
                body=(ROOT/'web/learning-lab/shared.html').read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers();return self.wfile.write(body)
            if parsed.path=='/seed' and not parsed.query:
                body=(ROOT/'web/learning-lab/seed.html').read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers();return self.wfile.write(body)
            if parsed.path=='/experimental' and not parsed.query:
                body=(ROOT/'web/learning-lab/experimental.html').read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers();return self.wfile.write(body)
            if parsed.path=='/api/questions' and not parsed.query:
                from nexus.seed.question_selection import saved_replay
                return self.send_json(200,saved_replay(ROOT))
            if parsed.path=='/api/answer-free-utility' and not parsed.query:
                from nexus.seed.answer_free_utility import saved_replay
                return self.send_json(200,saved_replay(ROOT))
            if parsed.path=='/api/question-utility' and not parsed.query:
                from nexus.seed.question_utility import saved_replay
                return self.send_json(200,saved_replay(ROOT))
            if parsed.path=='/api/query-replication' and not parsed.query:
                from nexus.seed.query_replication import saved_replay
                return self.send_json(200,saved_replay(ROOT))
            if parsed.path=='/api/question-headroom' and not parsed.query:
                from nexus.seed.question_headroom import saved_replay
                return self.send_json(200,saved_replay(ROOT))
            if parsed.path=='/api/experimental' and not parsed.query:
                from nexus.seed.experimental import Sandbox
                state=Sandbox(ROOT,getattr(self.server,'experimental_directory',None)).view()
                if (ROOT/'artifacts/seed_investigation_transfer.json').exists():
                    from nexus.seed.investigation_transfer import saved_replay as investigation_replay
                    investigation=investigation_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=investigation['id']]+[investigation]
                if (ROOT/'artifacts/seed_investigation_hybrid.json').exists():
                    from nexus.seed.investigation_hybrid import saved_replay as hybrid_replay
                    hybrid=hybrid_replay(ROOT)
                    audit_path=ROOT/'artifacts/seed_investigation_hybrid_audit.json'
                    if audit_path.exists():
                        audit=json.loads(audit_path.read_text())
                        if audit['raw_sha256']!=hashlib.sha256((ROOT/'artifacts/seed_investigation_hybrid.json').read_bytes()).hexdigest():raise ValueError('hybrid_audit_mismatch')
                        hybrid['investigation_transfer']['mixture_sensitivity']=audit['mixture_sensitivity']
                    state['experiments']=[r for r in state['experiments'] if r['id']!=hybrid['id']]+[hybrid]
                if (ROOT/'artifacts/seed_investigation_replication.json').exists():
                    from nexus.seed.investigation_replication import saved_replay as replication_replay
                    replication=replication_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=replication['id']]+[replication]
                if (ROOT/'artifacts/seed_compiled_greedy.json').exists():
                    from nexus.seed.compiled_greedy import saved_replay as compiled_replay
                    compiled=compiled_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=compiled['id']]+[compiled]
                if (ROOT/'artifacts/seed_inferred_investigation.json').exists():
                    from nexus.seed.inferred_investigation import saved_replay as inferred_replay
                    inferred=inferred_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=inferred['id']]+[inferred]
                if (ROOT/'artifacts/seed_source_acquisition.json').exists():
                    from nexus.seed.source_acquisition import saved_replay as acquisition_replay
                    acquisition=acquisition_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=acquisition['id']]+[acquisition]
                if (ROOT/'artifacts/seed_query_context.json').exists():
                    from nexus.seed.query_context import saved_replay as context_replay
                    context=context_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=context['id']]+[context]
                if (ROOT/'artifacts/seed_conditioned_acquisition.json').exists():
                    from nexus.seed.conditioned_acquisition import saved_replay as conditioned_replay
                    conditioned=conditioned_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=conditioned['id']]+[conditioned]
                if (ROOT/'artifacts/seed_disjoint_meta.json').exists():
                    from nexus.seed.disjoint_meta import saved_replay as disjoint_meta_replay
                    disjoint_meta=disjoint_meta_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=disjoint_meta['id']]+[disjoint_meta]
                if (ROOT/'artifacts/seed_task_conditioned_replication.json').exists():
                    from nexus.seed.task_conditioned_meta import saved_replay as task_cond_replay
                    task_cond=task_cond_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=task_cond['id']]+[task_cond]
                if (ROOT/'artifacts/seed_meta_rule_evolution.json').exists():
                    from nexus.seed.meta_rule_evolution import saved_replay as meta_rule_evo_replay
                    meta_rule_evo=meta_rule_evo_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=meta_rule_evo['id']]+[meta_rule_evo]
                if (ROOT/'artifacts/seed_open_primitive_transfer.json').exists():
                    from nexus.seed.open_primitive_transfer import saved_replay as open_prim_replay
                    open_prim=open_prim_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=open_prim['id']]+[open_prim]
                if (ROOT/'artifacts/seed_executable_world.json').exists():
                    from nexus.seed.structure.study import saved_replay as structure_replay
                    structure=structure_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=structure['id']]+[structure]
                if (ROOT/'artifacts/seed_answer_free_utility.json').exists():
                    from nexus.seed.answer_free_utility import saved_replay as answer_free_replay
                    answer_free=answer_free_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=answer_free['id']]+[answer_free]
                if (ROOT/'artifacts/seed_question_utility.json').exists() and not any(r['id']=='seed-question-utility-1' for r in state['experiments']):
                    from nexus.seed.question_utility import saved_replay as utility_replay
                    state['experiments'].append(utility_replay(ROOT))
                if (ROOT/'artifacts/seed_query_replication_validation.json').exists():
                    from nexus.seed.query_replication import saved_replay as query_validated_replay
                    validated=query_validated_replay(ROOT)
                    state['experiments']=[r for r in state['experiments'] if r['id']!=validated['id']]+[validated]
                if (ROOT/'artifacts/seed_query_replication.json').exists() and not any(r['id']=='seed-query-replication-1' for r in state['experiments']):
                    from nexus.seed.query_replication import saved_replay as query_replay
                    state['experiments'].append(query_replay(ROOT))
                if (ROOT/'artifacts/seed_question_headroom.json').exists() and not any(r['id']=='seed-question-headroom-1' for r in state['experiments']):
                    from nexus.seed.question_headroom import saved_replay as headroom_replay
                    state['experiments'].append(headroom_replay(ROOT))
                if (ROOT/'artifacts/seed_question_selection.json').exists() and not any(r['id']=='seed-question-selection-1' for r in state['experiments']):
                    from nexus.seed.question_selection import saved_replay as questions_replay
                    state['experiments'].append(questions_replay(ROOT))
                if not state['experiments'] and (ROOT/'artifacts/seed_nonlinear_learning.json').exists():
                    from nexus.seed.nonlinear_learning_audit import saved_replay
                    state['experiments'].append(saved_replay(ROOT))
                if (ROOT/'artifacts/seed_update_diagnosis.json').exists() and not any(r['id']=='seed-source-update-diagnosis-1' for r in state['experiments']):
                    from nexus.seed.update_diagnosis import saved_replay as source_replay
                    state['experiments'].append(source_replay(ROOT))
                if (ROOT/'artifacts/seed_bounded_correction.json').exists() and not any(r['id']=='seed-bounded-correction-1' for r in state['experiments']):
                    from nexus.seed.bounded_correction import saved_replay as bounded_replay
                    state['experiments'].append(bounded_replay(ROOT))
                if (ROOT/'artifacts/seed_cumulative_learning.json').exists() and not any(r['id']=='seed-cumulative-learning-1' for r in state['experiments']):
                    from nexus.seed.cumulative_learning import saved_replay as cumulative_replay
                    state['experiments'].append(cumulative_replay(ROOT))
                if (ROOT/'artifacts/seed_update_gate.json').exists() and not any(r['id']=='seed-update-gate-1' for r in state['experiments']):
                    from nexus.seed.update_gate import saved_replay as gate_replay
                    state['experiments'].append(gate_replay(ROOT))
                if (ROOT/'artifacts/seed_prefix_consistency.json').exists() and not any(r['id']=='seed-prefix-consistency-1' for r in state['experiments']):
                    from nexus.seed.prefix_consistency import saved_replay as prefix_replay
                    state['experiments'].append(prefix_replay(ROOT))
                if (ROOT/'artifacts/seed_sequential_consistency.json').exists() and not any(r['id']=='seed-sequential-consistency-1' for r in state['experiments']):
                    from nexus.seed.sequential_consistency import saved_replay as sequential_replay
                    state['experiments'].append(sequential_replay(ROOT))
                if (ROOT/'artifacts/seed_learning_choice.json').exists() and not any(r['id']=='seed-learning-choice-1' for r in state['experiments']):
                    from nexus.seed.learning_choice import saved_replay as choice_replay
                    state['experiments'].append(choice_replay(ROOT))
                return self.send_json(200,state)
            if parsed.path=='/' and not parsed.query:
                body=(ROOT/'web/learning-lab/index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers();return self.wfile.write(body)
            if parsed.path=='/api/status':return self.send_json(200,dict(live_environment=False,fixtures_enabled=self.server.fixtures_enabled,requests_remaining=self.server.requests_remaining))
            if parsed.path=='/api/operators' and not parsed.query:return self.send_json(200,load_operator_replay(ROOT))
            if parsed.path=='/api/parent-retention' and not parsed.query:return self.send_json(200,load_operator_replay(ROOT,parent_retention=True))
            if parsed.path=='/api/preparation' and not parsed.query:return self.send_json(200,load_preparation(ROOT))
            if parsed.path=='/api/training-audit' and not parsed.query:return self.send_json(200,load_training_audit(ROOT))
            if parsed.path=='/api/replay':
                query=parse_qs(parsed.query)
                if set(query)!={'study'} or len(query['study'])!=1:raise ValueError('single_study_required')
                return self.send_json(200,load_control_replay(ROOT,query['study'][0]))
            return self.send_json(404,{'error':'unknown_route'})
        except (ValueError,KeyError,FileNotFoundError) as e:return self.send_json(400,{'error':str(e)})
    def do_POST(self):
        if not self.local_request() or self.headers.get('X-Nexus-Request')!='local-fixture':return self.send_json(403,{'error':'local_fixture_header_required'})
        if self.path=='/api/seed':
            if not getattr(self.server,'seed_workspace',None):return self.send_json(403,{'error':'seed_not_enabled'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384 or self.headers.get('Content-Type')!='application/json':raise ValueError('small_json_body_required')
                return self.send_json(200,self.server.seed_workspace.dispatch(json.loads(self.rfile.read(length))))
            except (ValueError,TypeError,KeyError,OSError) as e:return self.send_json(400,{'error':str(e)})
        if self.path!='/api/fixture':return self.send_json(404,{'error':'unknown_route'})
        if not self.server.fixtures_enabled:return self.send_json(403,{'error':'fixtures_not_enabled'})
        with getattr(self.server,'fixture_lock',nullcontext()):
            if self.server.requests_remaining<=0:return self.send_json(429,{'error':'process_fixture_request_cap'})
            self.server.requests_remaining-=1
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096 or self.headers.get('Content-Type')!='application/json':raise ValueError('small_json_body_required')
            payload=json.loads(self.rfile.read(length))
            # Fixed child command, not user code. A killable process preserves
            # the request cap when HTTP handlers use separate threads.
            worker=subprocess.run([sys.executable,__file__,'--fixture-worker'],input=json.dumps(payload),
                text=True,capture_output=True,timeout=2.,cwd=ROOT)
            if worker.returncode:raise ValueError('invalid_fixture_request')
            result=json.loads(worker.stdout)
            return self.send_json(200,result)
        except (ValueError,TypeError,KeyError,TimeoutError,subprocess.TimeoutExpired) as e:return self.send_json(400,{'error':str(e)})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765);parser.add_argument('--allow-fixtures',action='store_true');parser.add_argument('--allow-seed',action='store_true');parser.add_argument('--seed-directory',type=Path,default=ROOT/'runs/seed-sessions');parser.add_argument('--max-runtime-s',type=int,default=900);parser.add_argument('--fixture-worker',action='store_true',help=argparse.SUPPRESS);parser.add_argument('--seed-encoder',type=Path);parser.add_argument('--seed-encoder-sha256');parser.add_argument('--seed-meta-questions',action='store_true')
    parser.add_argument('--seed-grounded-model',type=Path);parser.add_argument('--seed-grounded-sha256')
    parser.add_argument('--seed-shared-model',type=Path);parser.add_argument('--seed-shared-sha256')
    parser.add_argument('--seed-action-readout',type=Path);parser.add_argument('--seed-action-readout-sha256')
    parser.add_argument('--seed-surprise-study',type=Path);parser.add_argument('--seed-surprise-sha256')
    parser.add_argument('--seed-plasticity-controller',type=Path);parser.add_argument('--seed-plasticity-sha256')
    parser.add_argument('--experimental-directory',type=Path,help='owner-selected read-only dashboard data; no execution endpoint');args=parser.parse_args()
    if bool(args.seed_plasticity_controller)!=bool(args.seed_plasticity_sha256) or args.seed_plasticity_controller and not args.seed_grounded_model:raise ValueError('plasticity_requires_owner_verified_core')
    if args.fixture_worker:
        print(json.dumps(run_fixture_request(json.loads(sys.stdin.read(4097))),allow_nan=False));return
    if not 1024<=args.port<=65535 or not 1<=args.max_runtime_s<=900:raise ValueError('local_server_limits')
    if bool(args.seed_encoder)!=bool(args.seed_encoder_sha256) or not args.allow_seed and (args.seed_encoder or args.seed_meta_questions):raise ValueError('explicit_seed_model_path_hash_and_opt_in_required')
    if bool(args.seed_shared_model)!=bool(args.seed_shared_sha256) or args.seed_shared_model and (not args.allow_seed or args.seed_grounded_model):raise ValueError('separate_owner_verified_shared_encoder_workspace_required')
    shared=None
    if args.seed_shared_model:
        import torch
        torch.set_num_threads(1)
        from nexus.world.seed_rssm import SeedRSSM
        shared,_=SeedRSSM.load(args.seed_shared_model,args.seed_shared_sha256)
    encoder=None
    grounded=None;plasticity=None;surprise=None
    readout=None
    if bool(args.seed_action_readout)!=bool(args.seed_action_readout_sha256) or args.seed_action_readout and not args.seed_grounded_model:raise ValueError('readout_requires_verified_parent')
    if bool(args.seed_surprise_study)!=bool(args.seed_surprise_sha256) or args.seed_surprise_study and not args.seed_grounded_model:raise ValueError('surprise_requires_verified_core')
    if bool(args.seed_grounded_model)!=bool(args.seed_grounded_sha256) or (args.seed_grounded_model and not args.allow_seed):
        raise ValueError('explicit_grounded_path_hash_and_opt_in_required')
    if args.seed_grounded_model:
        import torch
        torch.set_num_threads(1)
        from nexus.world.seed_rssm import SeedRSSM
        grounded,_=SeedRSSM.load(args.seed_grounded_model,args.seed_grounded_sha256)
        if args.seed_surprise_study:
            from nexus.seed.surprise import load_calibration
            surprise=load_calibration(args.seed_surprise_study,args.seed_surprise_sha256,args.seed_grounded_sha256)
        if args.seed_plasticity_controller:
            from nexus.seed.plasticity import PlasticityController
            plasticity=PlasticityController.load(args.seed_plasticity_controller,args.seed_plasticity_sha256)
        if args.seed_action_readout:
            from nexus.seed.action_readout import ActionReadout
            readout=ActionReadout.load(args.seed_action_readout,args.seed_action_readout_sha256,args.seed_grounded_sha256)
    if args.seed_encoder:
        from nexus.seed.perception import TinyCommandEncoder
        encoder=TinyCommandEncoder.load(args.seed_encoder,args.seed_encoder_sha256)
    if args.seed_meta_questions:
        from nexus.seed.question_policy import choose
        choose(())  # Optional dependency startup, not a measured question/request.
    with ThreadingHTTPServer(('127.0.0.1',args.port),LabHandler) as server:
        server.experimental_directory=args.experimental_directory
        if args.allow_seed:
            from nexus.seed.lab import SeedWorkspace
            server.seed_workspace=SeedWorkspace(args.seed_directory,language_encoder=encoder,meta_questions=args.seed_meta_questions,grounded_model=grounded,grounded_hash=args.seed_grounded_sha256,action_readout=readout,plasticity_controller=plasticity,plasticity_hash=args.seed_plasticity_sha256,surprise_gate=surprise,shared_model=shared,shared_hash=args.seed_shared_sha256)
        server.fixture_lock=threading.Lock()
        server.fixtures_enabled=args.allow_fixtures;server.requests_remaining=10;server.timeout=.5
        end=time.monotonic()+args.max_runtime_s
        print(f'NEXUS Learning Lab: http://127.0.0.1:{args.port} (recorded replay; authored fixtures={args.allow_fixtures})',flush=True)
        while time.monotonic()<end:server.handle_request()


if __name__=='__main__':main()
