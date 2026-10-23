"""Seed API binding for the SAME loopback Learning Lab server."""
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import shutil
import threading
import uuid
from .core import Session
from .storage import load, save


class SeedWorkspace:
    def __init__(self, directory, *, language_encoder=None, meta_questions=False, grounded_model=None, grounded_hash=None, action_readout=None,plasticity_controller=None,plasticity_hash=None,surprise_gate=None,shared_model=None,shared_hash=None,local_runtime=None,runtime_config=None,attach_local_runtime=True):
        self.directory = directory
        self.sessions = {}
        self.lock = threading.RLock()
        self.requests = 0
        self.language_encoder = language_encoder
        self.meta_questions = meta_questions
        self.grounded_model = grounded_model
        self.grounded_hash = grounded_hash
        self.action_readout=action_readout
        self.plasticity_controller=plasticity_controller;self.plasticity_hash=plasticity_hash
        self.surprise_gate=surprise_gate
        self.shared_model=shared_model;self.shared_hash=shared_hash
        self.local_runtime=local_runtime
        self.runtime_config=runtime_config
        self.attach_local_runtime=attach_local_runtime
        self._runtime_unavailable=None if attach_local_runtime else 'local_model_unavailable: runtime attachment disabled'
        self.attachments={}
        self.pending_test_cases=None
        self.knowledge_vault=None
        self.capsule_store=None
        self.titles={}

    def attach_grounded(self, session):
        if self.grounded_model is not None:
            from .grounded_agent import GroundedAgent
            from .adaptive_state import AdaptiveState
            adaptive=AdaptiveState(self.plasticity_controller) if self.plasticity_controller is not None else None
            import copy
            session.grounded_agent=GroundedAgent(self.grounded_model,self.grounded_hash,self.action_readout,adaptive,self.plasticity_hash,copy.deepcopy(self.surprise_gate))
            session.grounded_agent.restore_state(session)

    def procedures_dir(self):
        path=Path(self.directory)/'procedures';path.mkdir(parents=True,exist_ok=True);return path

    def coding_workspaces_dir(self):
        path=Path(self.directory)/'coding_workspaces';path.mkdir(parents=True,exist_ok=True);return path

    def list_coding_workspaces(self):
        root=self.coding_workspaces_dir()
        names=[]
        for child in sorted(root.iterdir()):
            if child.is_dir() and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', child.name):
                names.append(child.name)
        return names

    def outputs_dir(self):
        path=Path(self.directory)/'outputs';path.mkdir(parents=True,exist_ok=True);return path

    def runtime_status(self):
        ready=self.local_runtime is not None and (not hasattr(self.local_runtime,'process') or (
            getattr(self.local_runtime,'process',None) is not None and self.local_runtime.process.poll() is None))
        return dict(available=bool(ready),reason=None if ready else self._runtime_unavailable)

    def ensure_runtime(self):
        """Attach the owned CPU llama-server only. Metal is a separate grant path."""
        from .local_model_runtime import PersistentLocalRuntime,RuntimeConfig
        if not self.attach_local_runtime and self.local_runtime is None:
            self._runtime_unavailable=self._runtime_unavailable or 'local_model_unavailable: runtime attachment disabled'
            return None
        if self.local_runtime is not None:
            if isinstance(self.local_runtime,PersistentLocalRuntime):
                if self.local_runtime.process is None or self.local_runtime.process.poll() is not None:
                    self.local_runtime.start()
            self._runtime_unavailable=None
            return self.local_runtime
        cfg=self.runtime_config
        if cfg is None:
            cfg=RuntimeConfig.from_environment()
            if not os.environ.get('NEXUS_MODEL_PATH'):
                preferred=Path('.models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf')
                if preferred.is_file():
                    cfg=replace(cfg,model_path=str(preferred.resolve()))
            self.runtime_config=cfg
        model=Path(cfg.model_path).expanduser()
        if not model.is_file():
            self._runtime_unavailable='local_model_unavailable: model file not found at '+str(model)
            return None
        if not shutil.which(cfg.executable):
            self._runtime_unavailable='local_model_unavailable: llama-server executable not found'
            return None
        try:
            runtime=PersistentLocalRuntime(cfg)
            runtime.start()
            self.local_runtime=runtime
            self._runtime_unavailable=None
            return runtime
        except Exception as exc:
            self._runtime_unavailable='local_model_unavailable: '+type(exc).__name__+': '+str(exc)[:200]
            return None

    def pending_attachment(self, session_id):
        return self.attachments.get(session_id)

    def conversation_index_path(self):
        return Path(self.directory)/'conversation_index.json'

    def load_titles(self):
        path=self.conversation_index_path()
        if path.is_file():
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError):
                data={}
            if type(data) is dict:
                self.titles.update({k:v for k,v in data.items() if type(k) is str and type(v) is str})
        return self.titles

    def save_titles(self):
        path=self.conversation_index_path()
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.titles,allow_nan=False),encoding='utf-8')

    def dispatch(self, wire):
        if type(wire) is not dict or set(wire) != {'session_id','request'} or type(wire['request']) is not dict:
            raise ValueError('seed_envelope_schema')
        request = wire['request']; sid = wire['session_id']; op = request.get('op')
        # Out-of-band cancellation must not wait behind a search's lock.
        if op == 'stop' and set(request) == {'op'} and sid in self.sessions:
            self.sessions[sid].cancelled.set()
        with self.lock:
            if self.requests >= 500:
                raise ValueError('server_seed_request_cap')
            self.requests += 1
            if op == 'new' and set(request) == {'op'} and sid is None:
                if len(self.sessions) >= 16:
                    raise ValueError('server_session_cap')
                sid = uuid.uuid4().hex; self.sessions[sid] = Session(language_encoder=self.language_encoder,meta_questions=self.meta_questions)
                self.attach_grounded(self.sessions[sid])
                response = self.sessions[sid].request(dict(op='inspect'))
            elif op == 'load' and set(request) == {'op','saved_id','expected_hash'}:
                if len(self.sessions) >= 16 and request['saved_id'] not in self.sessions:
                    raise ValueError('server_session_cap')
                sid = request['saved_id']
                self.sessions[sid] = load(self.directory, sid, request['expected_hash'])
                # Runtime capabilities are owner-selected CLI settings, never
                # granted by saved evidence or a client payload.
                self.sessions[sid].language_encoder=self.language_encoder
                self.sessions[sid].meta_questions=self.meta_questions
                self.attach_grounded(self.sessions[sid])
                response = self.sessions[sid].request(dict(op='inspect'))
            elif sid not in self.sessions:
                raise ValueError('active_session_required')
            elif op == 'save' and set(request) == {'op'}:
                saved = save(self.directory, sid, self.sessions[sid])
                response = self.sessions[sid].request(dict(op='inspect'))
                response['saved'] = saved
            elif op == 'export' and set(request) == {'op'}:
                response = self.sessions[sid].request(dict(op='inspect'))
                response['export'] = self.sessions[sid].snapshot()
            elif type(op) is str and op.startswith('foundation_'):
                from .foundation.runtime import request as foundation_request
                response=foundation_request(self.sessions[sid],request)
            elif type(op) is str and op.startswith('structure_'):
                from .structure.runtime import request as structure_request
                response=structure_request(self.sessions[sid],request)
            elif type(op) is str and op.startswith('master_'):
                from .shared_brain import SharedBrain
                from .master.runtime import request as master_request
                response=master_request(self.sessions[sid],request,SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash))
            elif type(op) is str and op.startswith('workbench_'):
                from .symbiotic_workbench import SymbioticWorkbenchController
                ctrl=SymbioticWorkbenchController(self,self.sessions[sid],session_id=sid)
                response=dict(result=ctrl.execute_request(request))
            elif type(op) is str and op.startswith('lab_'):
                from .shared_brain import SharedBrain
                response=SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash).request(request)
            elif op in ('knowledge_list','knowledge_save','knowledge_delete','knowledge_preview'):
                from .unified_chat import delete_capsule,delete_document,knowledge_snapshot,save_capsule,save_document,vault_for
                if op=='knowledge_list' and set(request)=={'op'}:
                    response=dict(knowledge=knowledge_snapshot(self))
                elif op=='knowledge_save' and {'op','kind'}<=set(request)<= {'op','kind','title','content','doc_id','term','definition','pos_or_frame'}:
                    kind=request['kind']
                    if kind=='document':
                        fact=save_document(self,title=request.get('title') or 'Untitled',content=request.get('content') or '',doc_id=request.get('doc_id'))
                        response=dict(saved=dict(doc_id=fact.doc_id,title=fact.title,source_hash=fact.source_hash,timestamp=fact.timestamp),knowledge=knowledge_snapshot(self))
                    elif kind=='capsule':
                        capsule=save_capsule(self,term=request.get('term') or '',definition=request.get('definition') or '',pos_or_frame=request.get('pos_or_frame') or 'noun_phrase')
                        response=dict(saved=dict(term=capsule.term,definition=capsule.definition),knowledge=knowledge_snapshot(self))
                    else:
                        raise ValueError('knowledge_kind')
                elif op=='knowledge_delete' and set(request)=={'op','kind','id'}:
                    if request['kind']=='document':
                        ok=delete_document(self,request['id'])
                    elif request['kind']=='capsule':
                        ok=delete_capsule(self,request['id'])
                    elif request['kind']=='procedure':
                        path=self.procedures_dir()/(str(request['id'])+'.json')
                        ok=path.is_file()
                        if ok:
                            path.unlink()
                    else:
                        raise ValueError('knowledge_kind')
                    response=dict(deleted=bool(ok),knowledge=knowledge_snapshot(self))
                elif op=='knowledge_preview' and set(request)=={'op','doc_id'}:
                    fact=vault_for(self).get_document(request['doc_id'])
                    if fact is None:
                        raise ValueError('document_not_found')
                    response=dict(document=dict(doc_id=fact.doc_id,title=fact.title,content=fact.content,source_hash=fact.source_hash,timestamp=fact.timestamp))
                else:
                    raise ValueError('typed_knowledge_request')
            elif op=='attach' and {'op','kind','name','content'}<=set(request)<= {'op','kind','name','content','doc_id','language'}:
                if request['kind'] not in ('document','code'):
                    raise ValueError('attachment_kind')
                content=request['content']
                if type(content) is not str or not 1<=len(content)<=48000 or '\x00' in content:
                    raise ValueError('attachment_content')
                name=request['name']
                if type(name) is not str or not 1<=len(name)<=120 or '\x00' in name:
                    raise ValueError('attachment_name')
                self.attachments[sid]=dict(kind=request['kind'],name=name,content=content,doc_id=request.get('doc_id'),language=request.get('language'))
                if request['kind']=='document':
                    from .conversation import Conversation
                    from .shared_brain import SharedBrain
                    chat=Conversation(SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash),store=self,session_id=sid)
                    ctx=chat.view()['context']
                    ctx['workspace']['last_correction']='Attached document '+name+' as content, not as an instruction.'
                response=dict(attached=dict(kind=request['kind'],name=name,bytes=len(content.encode('utf-8')),instruction=False))
            elif op=='conversation_rename' and set(request)=={'op','title'}:
                title=request['title']
                if type(title) is not str or not 1<=len(title)<=80 or '\x00' in title:
                    raise ValueError('conversation_title')
                self.load_titles();self.titles[sid]=title;self.save_titles()
                response=dict(title=title)
            elif op=='conversation_delete' and set(request)=={'op'}:
                self.sessions.pop(sid,None)
                self.attachments.pop(sid,None)
                self.load_titles();self.titles.pop(sid,None);self.save_titles()
                saved_dir=Path(self.directory)/sid
                if saved_dir.is_dir() and not saved_dir.is_symlink():
                    shutil.rmtree(saved_dir)
                response=dict(deleted=True)
            elif op in ('chat_send','chat_view'):
                from .shared_brain import SharedBrain
                from .conversation import Conversation
                chat=Conversation(SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash),store=self,session_id=sid)
                if op=='chat_view' and set(request)=={'op'}:
                    view=chat.view();view['title']=self.load_titles().get(sid)
                    response=dict(text='Conversation restored without resubmitting messages.',chat=view)
                elif op=='chat_send' and {'op','text','id'}<=set(request)<= {'op','text','id','attachment'}:
                    attachment=request.get('attachment')
                    if attachment is not None:
                        if type(attachment) is not dict or attachment.get('kind') not in ('document','code'):
                            raise ValueError('attachment_kind')
                        content=attachment.get('content')
                        name=attachment.get('name') or 'attachment'
                        if type(content) is not str or not 1<=len(content)<=48000 or '\x00' in content:
                            raise ValueError('attachment_content')
                        self.attachments[sid]=dict(kind=attachment['kind'],name=str(name)[:120],content=content,
                                                   doc_id=attachment.get('doc_id'),language=attachment.get('language'))
                    response=chat.send(request['text'],request['id'])
                    if response.pop('save_requested',False):
                        response['saved']=save(self.directory,sid,self.sessions[sid])
                        response['notification']='Conversation saved locally.'
                else:raise ValueError('typed_chat_request')
            else:
                response = self.sessions[sid].request(request)
            return dict(session_id=sid, kind='live_authored_seed', scientific=False, response=response)
