"""H17 historical arithmetic dependency certificates. No scientific imports.

Interpret a bounded, pure data subset of Python AST; never exec source, import
historical modules, invoke their loaders, or construct an environment/model.
"""
import ast
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import time

from nexus.h16_selection_mechanism_diagnosis import require, verify_provenance
from nexus.h17_exclusion_coverage_review import REGISTRY, REGISTRY_SHA, contains
from nexus.h17_exclusion_registry_audit import parse_config
from nexus.h17_protocol_readiness import CONFIG, validate_draft
from nexus.h17_reservation_closure import PARENT, PARENT_SHA, Unsupported

BASE = '07a91522f9ba443f9fb5ac7af1bb2cb99d1a171c'
LIMIT = 5000000
OWN_FUNCTIONS = {'seed_groups','seed_streams','check_seeds','seed_sets',
                 'design_seed_groups','phase_seed_groups','horizon_seed_groups',
                 'diagnostic_seed_groups','proposed_seeds','replication_seed_groups'}


@dataclass(frozen=True)
class ModuleRef:
    path: str


@dataclass(frozen=True)
class SymbolRef:
    path: str
    name: str


class Returned(Exception):
    def __init__(self,value): self.value=value


class History:
    """All module dependencies are read at one immutable Git commit."""
    def __init__(self, read):
        self.read=read
        self.modules={}
        self.operations=0
        self.stack=[]
        self.config_reads={}

    def tick(self):
        self.operations+=1
        if self.operations>LIMIT or len(self.stack)>32:
            raise Unsupported('AST arithmetic resource limit exceeded')

    def module(self,path):
        if path not in self.modules:
            raw=self.read(path)
            self.modules[path]=Module(self,path,raw)
        return self.modules[path]

    def dependencies(self):
        files={p:m.raw for p,m in self.modules.items()}
        files.update(self.config_reads)
        return [dict(path=p,sha256=hashlib.sha256(raw).hexdigest()) for p,raw in sorted(files.items())]


class Module:
    def __init__(self,history,path,raw):
        self.history,self.path,self.raw=history,path,raw
        self.tree=ast.parse(raw.decode())
        self.functions={n.name:n for n in self.tree.body if isinstance(n,ast.FunctionDef)}
        self.assignments={}
        self.imports={}
        for node in self.tree.body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name): self.assignments[target.id]=node.value
            elif isinstance(node,ast.ImportFrom) and node.module:
                if node.module=='nexus.world':
                    for alias in node.names:
                        self.imports[alias.asname or alias.name]=(f'src/nexus/world/{alias.name}.py',None)
                elif node.module.startswith('nexus.world.'):
                    path='src/'+node.module.replace('.','/')+'.py'
                    for alias in node.names: self.imports[alias.asname or alias.name]=(path,alias.name)
        self.resolving=set()

    def lookup(self,name,env):
        if name in env:
            value=env[name]
            return self.history.module(value.path).lookup(value.name,{}) if isinstance(value,SymbolRef) else value
        if name in self.imports:
            path,symbol=self.imports[name]
            return ModuleRef(path) if symbol is None else self.history.module(path).lookup(symbol,{})
        if name in self.assignments:
            if name in self.resolving: raise Unsupported('constant dependency cycle: '+name)
            self.resolving.add(name)
            try: return self.expr(self.assignments[name],{})
            finally: self.resolving.remove(name)
        raise Unsupported('unresolved name: '+name)

    def bind(self,target,value,env):
        if isinstance(target,ast.Name): env[target.id]=value
        elif isinstance(target,(ast.Tuple,ast.List)) and len(target.elts)==len(value):
            for t,v in zip(target.elts,value): self.bind(t,v,env)
        elif isinstance(target,ast.Subscript): self.expr(target.value,env)[self.expr(target.slice,env)]=value
        else: raise Unsupported('unsupported assignment target')

    def expr(self,node,env):
        self.history.tick()
        def e(n): return self.expr(n,env)
        if isinstance(node,ast.Constant) and type(node.value) in (int,str,bool,type(None)): return node.value
        if isinstance(node,ast.JoinedStr):
            return ''.join(str(e(v.value)) if isinstance(v,ast.FormattedValue) and v.format_spec is None and v.conversion==-1
                           else e(v) if isinstance(v,ast.Constant) else self._unsupported_format() for v in node.values)
        if isinstance(node,ast.Name): return self.lookup(node.id,env)
        if isinstance(node,ast.Attribute):
            base=e(node.value)
            if isinstance(base,ModuleRef): return self.history.module(base.path).lookup(node.attr,{})
        if isinstance(node,ast.Subscript): return e(node.value)[e(node.slice)]
        if isinstance(node,(ast.Tuple,ast.List,ast.Set)):
            values=[e(n) for n in node.elts]
            return tuple(values) if isinstance(node,ast.Tuple) else set(values) if isinstance(node,ast.Set) else values
        if isinstance(node,ast.Dict): return {e(k):e(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node,ast.DictComp):
            # Reuse bounded comprehension semantics for key/value pairs.
            proxy=ast.ListComp(elt=ast.Tuple(elts=[node.key,node.value],ctx=ast.Load()),generators=node.generators)
            return dict(e(proxy))
        if isinstance(node,ast.BinOp):
            left,right=e(node.left),e(node.right)
            if isinstance(node.op,ast.Add) and type(left) is type(right) and type(left) in (int,str,list,tuple): return left+right
            if type(left) is int and type(right) is int:
                if isinstance(node.op,ast.Sub): return left-right
                if isinstance(node.op,ast.Mult): return left*right
                if isinstance(node.op,ast.FloorDiv): return left//right
                if isinstance(node.op,ast.Mod): return left%right
            if type(left) is set and type(right) is set:
                if isinstance(node.op,ast.BitOr): return left|right
                if isinstance(node.op,ast.BitAnd): return left&right
        if isinstance(node,ast.UnaryOp):
            value=e(node.operand)
            if isinstance(node.op,ast.Not): return not value
            if isinstance(node.op,ast.USub) and type(value) is int: return -value
        if isinstance(node,ast.BoolOp):
            value=None
            for child in node.values:
                value=e(child)
                if isinstance(node.op,ast.Or) and value or isinstance(node.op,ast.And) and not value: return value
            return value
        if isinstance(node,ast.IfExp): return e(node.body if e(node.test) else node.orelse)
        if isinstance(node,ast.Compare) and len(node.ops)==1:
            a,b=e(node.left),e(node.comparators[0]); op=node.ops[0]
            if isinstance(op,ast.Eq): return a==b
            if isinstance(op,ast.NotEq): return a!=b
            if isinstance(op,ast.In): return a in b
            if isinstance(op,ast.NotIn): return a not in b
            if isinstance(op,ast.Lt): return a<b
            if isinstance(op,ast.Gt): return a>b
            if isinstance(op,ast.Is): return a is b
        if isinstance(node,(ast.SetComp,ast.ListComp,ast.GeneratorExp)):
            values=[]
            def walk(i,scope):
                self.history.tick()
                if i==len(node.generators):
                    values.append(self.expr(node.elt,scope));return
                gen=node.generators[i]
                if gen.is_async: raise Unsupported('async comprehension')
                for value in self.expr(gen.iter,scope):
                    local=dict(scope);self.bind(gen.target,value,local)
                    if all(self.expr(test,local) for test in gen.ifs): walk(i+1,local)
            walk(0,env)
            return set(values) if isinstance(node,ast.SetComp) else values
        if isinstance(node,ast.Call) and not node.keywords:
            args=[]
            for arg in node.args:
                if isinstance(arg,ast.Starred): args.extend(e(arg.value))
                else: args.append(e(arg))
            if isinstance(node.func,ast.Attribute):
                attr=node.func.attr
                if isinstance(node.func.value,ast.Name) and node.func.value.id=='itertools' and attr=='product':
                    count=1
                    for a in args: count*=len(a)
                    if count>100000: raise Unsupported('product limit exceeded')
                    return itertools.product(*args)
                obj=e(node.func.value)
                if isinstance(obj,ModuleRef): return self.history.module(obj.path).call(attr,args)
                if type(obj) is dict and attr in ('values','items') and not args: return list(obj.values()) if attr=='values' else list(obj.items())
                if type(obj) is set and attr=='union': return obj.union(*args)
            if isinstance(node.func,ast.Name):
                name=node.func.id
                if name=='range' and all(type(v) is int for v in args):
                    r=range(*args)
                    if len(r)>100000: raise Unsupported('range limit exceeded')
                    return r
                if name in ('set','list','tuple') and len(args)<=1:
                    return {'set':set,'list':list,'tuple':tuple}[name](*args)
                if name=='dict' and not args:return {}
                if name=='Path' and len(args)==1 and type(args[0]) is str and args[0].startswith('configs/') and '..' not in args[0]:
                    return args[0]  # A path label, not a filesystem object.
                if name=='int' and len(args)==1 and type(args[0]) is int:return args[0]
                if name=='len' and len(args)==1:return len(args[0])
                if name in ('max','min') and all(type(a) is int for a in args):return (max if name=='max' else min)(args)
                if name in env and isinstance(env[name],SymbolRef):
                    ref=env[name];return self.history.module(ref.path).call(ref.name,args)
                return self.call(name,args)
        raise Unsupported('unsupported arithmetic: '+ast.dump(node)[:160])

    def _unsupported_format(self):
        raise Unsupported('formatted string conversion/specification')

    def statements(self,nodes,env):
        for n in nodes:
            self.history.tick()
            if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('nexus.world.'):
                # A local import becomes a source reference, never a Python import.
                for a in n.names:
                    if a.name=='*':raise Unsupported('star import')
                    env[a.asname or a.name]=SymbolRef('src/'+n.module.replace('.','/')+'.py',a.name)
                continue
            elif isinstance(n,ast.Return): raise Returned(self.expr(n.value,env))
            if isinstance(n,(ast.Assign,ast.AnnAssign)):
                if n.value is None: continue
                value=self.expr(n.value,env)
                for target in n.targets if isinstance(n,ast.Assign) else [n.target]: self.bind(target,value,env)
            elif isinstance(n,ast.AugAssign):
                value=self.expr(ast.BinOp(left=n.target,op=n.op,right=n.value),env);self.bind(n.target,value,env)
            elif isinstance(n,ast.For):
                if n.orelse: raise Unsupported('for-else')
                for value in self.expr(n.iter,env):
                    self.history.tick();self.bind(n.target,value,env);self.statements(n.body,env)
            elif isinstance(n,ast.While):
                if n.orelse: raise Unsupported('while-else')
                while self.expr(n.test,env):
                    self.history.tick();self.statements(n.body,env)
            elif isinstance(n,ast.If): self.statements(n.body if self.expr(n.test,env) else n.orelse,env)
            elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and type(n.value.value) is str: continue
            elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute):
                call=n.value;obj=self.expr(call.func.value,env)
                if type(obj) is list and call.func.attr in ('extend','append') and len(call.args)==1 and not call.keywords:
                    value=self.expr(call.args[0],env)
                    if call.func.attr=='extend': obj.extend(value)
                    else: obj.append(value)
                elif type(obj) is set and call.func.attr=='add' and len(call.args)==1 and not call.keywords:
                    obj.add(self.expr(call.args[0],env))
                else: raise Unsupported('unsupported mutable operation')
            elif isinstance(n,ast.Raise): raise Unsupported('historical arithmetic guard rejected its inputs')
            else: raise Unsupported('unsupported arithmetic statement: '+type(n).__name__)

    def call(self,name,args):
        if name not in self.functions:
            if name in self.imports:
                path,symbol=self.imports[name]
                if symbol:return self.history.module(path).call(symbol,args)
            raise Unsupported('unknown arithmetic helper: '+name)
        fn=self.functions[name]
        # A historical loader is NOT invoked. Read only its committed YAML
        # mapping, bound through its default path or unique literal config.
        # This does not certify the loader's runtime validation or authorization.
        if name.startswith('load_') and 'config' in name:
            path=args[0] if args else None
            if path is None and fn.args.defaults:
                try:path=self.expr(fn.args.defaults[0],{})
                except Unsupported:pass
            if path is None:path=config_path(self)
            if type(path) is not str or not path.startswith('configs/') or '..' in path:
                raise Unsupported('unbound metadata-only config loader')
            raw=self.history.read(path);self.history.config_reads[path]=raw
            cfg=parse_config(raw.decode())
            if type(cfg) is not dict:raise Unsupported('config must be a mapping')
            return cfg
        if fn.args.vararg or fn.args.kwarg: raise Unsupported('complex function signature')
        params=fn.args.args
        if not len(params)-len(fn.args.defaults)<=len(args)<=len(params): raise Unsupported('argument count mismatch')
        env=dict(zip((a.arg for a in params),args))
        defaults=dict(zip((a.arg for a in params[-len(fn.args.defaults):]),fn.args.defaults)) if fn.args.defaults else {}
        for p in params[len(args):]:env[p.arg]=self.expr(defaults[p.arg],{})
        for param,default in zip(fn.args.kwonlyargs,fn.args.kw_defaults):
            if default is None:raise Unsupported('required keyword argument')
            env[param.arg]=self.expr(default,{})
        key=(self.path,name)
        if key in self.history.stack: raise Unsupported('recursive arithmetic dependency')
        self.history.stack.append(key)
        try:
            self.statements(fn.body,env)
        except Returned as result:return result.value
        finally:self.history.stack.pop()
        raise Unsupported('arithmetic helper has no return')

    def own(self,name,cfg):
        if name!='check_seeds':return self.call(name,[cfg])
        # Collision guards read old results/config loaders. Extract only the
        # top-level own groups/used declarations and their explicit updates.
        fn=self.functions[name];env={'cfg':cfg}
        for node in fn.body:
            target=(node.targets[0] if isinstance(node,ast.Assign) else node.target
                    if isinstance(node,ast.AugAssign) else None)
            if isinstance(target,ast.Name) and target.id in ('groups','used'):
                self.statements([node],env)
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Tuple):
                if any(isinstance(n,ast.Name) and n.id=='used' for n in node.targets[0].elts):
                    self.statements([node],env)
        if 'groups' in env:return env['groups']
        if 'used' in env:return env['used']
        raise Unsupported('no explicit own groups/used declaration')


def flatten(value):
    if type(value) is dict:return set().union(*(flatten(v) for v in value.values()))
    if type(value) in (tuple,list):return set().union(*(flatten(v) for v in value))
    if type(value) is set and all(type(v) is int and 0<=v<2**32 for v in value):return value
    raise Unsupported('expected integer seed sets')


def config_path(module):
    for key in ('CONFIG','CONFIG_PATH','DESIGN_CONFIG_PATH'):
        node=module.assignments.get(key)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Path' and len(node.args)==1:
            value=ast.literal_eval(node.args[0])
            if type(value) is str and value.startswith('configs/') and '..' not in value:return value
    # The old design module has no CONFIG constant: its loader contains one
    # explicit ROOT / 'configs/...' operand. Bind that literal without ROOT I/O.
    fn=module.functions.get('load_design_config')
    paths={n.value for n in ast.walk(fn) if isinstance(n,ast.Constant) and type(n.value) is str
           and n.value.startswith('configs/') and n.value.endswith(('.yaml','.yml','.json'))} if fn else set()
    if len(paths)==1:return paths.pop()
    raise Unsupported('no literal configuration path')


def certificate(history,path,cfg,name,ranges):
    values=flatten(history.module(path).own(name,cfg))
    require(bool(values),'empty own registry')
    return dict(count=len(values),minimum=min(values),maximum=max(values),
                seed_set_sha256=hashlib.sha256(json.dumps(sorted(values),separators=(',',':')).encode()).hexdigest(),
                outside_reservations=sorted(v for v in values if not contains(ranges,v)),
                operations=history.operations,dependencies=history.dependencies())


def review(root):
    root=Path(root);started=time.monotonic();ledger=verify_provenance(root)
    git=lambda *args:subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.PIPE)
    git('merge-base','--is-ancestor',BASE,'HEAD')
    parent_raw=(root/PARENT).read_bytes();require(hashlib.sha256(parent_raw).hexdigest()==PARENT_SHA,'inventory drift')
    registry_raw=(root/REGISTRY).read_bytes();require(hashlib.sha256(registry_raw).hexdigest()==REGISTRY_SHA,'registry drift')
    parent=json.loads(parent_raw);registry=json.loads(registry_raw)
    good,bad=[],[]
    for row in parent['all_reachable_inputs']:
        if not row['path'].endswith('.py'):continue
        raw=git('cat-file','blob',row['git_blob']);tree=ast.parse(raw.decode())
        names={n.name for n in tree.body if isinstance(n,ast.FunctionDef)} & OWN_FUNCTIONS
        for name in sorted(names):
            record=dict(path=row['path'],git_blob=row['git_blob'],commit=row['reachable_commit'],function=name)
            try:
                history=History(lambda path:git('show',row['reachable_commit']+':'+path))
                module=history.module(row['path'])
                require(module.raw==raw,'historical source/config binding mismatch')
                cfgpath=config_path(module);cfgraw=git('show',row['reachable_commit']+':'+cfgpath)
                record.update(config_path=cfgpath,config_sha256=hashlib.sha256(cfgraw).hexdigest())
                record.update(certificate(history,row['path'],parse_config(cfgraw.decode()),name,registry['conservative_seed_reservations']))
                good.append(record)
            except (Unsupported,ValueError,TypeError,KeyError,subprocess.CalledProcessError) as exc:
                bad.append(dict(**record,error=str(exc)))
    return dict(verdict='BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE',starting_sha=BASE,
                source_revision=git('rev-parse','HEAD').decode().strip(),parent_sha256=PARENT_SHA,
                registry_sha256=REGISTRY_SHA,certificates=good,unresolved=bad,
                proposed_budget=validate_draft(json.loads((root/CONFIG).read_text())),
                remaining_gaps=['Any unresolved own-registry records are not certified.',
                                'RNG call-site coverage and semantic artifact-field classification remain separate requirements.'],
                ledger_used_s=ledger['ledger_used_s'],ledger_remaining_s=ledger['ledger_remaining_s'],
                new_environment_steps=0,new_imagined_transitions=0,model_inference_calls=0,training_updates=0,
                target_selected=False,numerical_seeds_registered=False,locked=False,authorized=False,
                wall_clock_s=time.monotonic()-started)
