"""Read source/provenance only. No imports of NEXUS runtime, models or worlds.

Conservative static reachability is navigation evidence,not proof that an
unreachable module is safe to delete. Dynamic/reproduction paths remain.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE='a3fe49adeb0040fc9c10b253f0fc86c4de125bb6'
SNAPSHOTS=('AGENTS.md','docs/MASTER_CONTEXT.md','docs/NEXUS_CANONICAL_CURRENT_STATE.md','docs/NEXUS_CODE_REUSE_MAP.md','docs/NEXUS_FULL_RESEARCH_REGISTRY.md')


def module_map(root):
    return {'.'.join(p.relative_to(root/'src').with_suffix('').parts).removesuffix('.__init__'):p for p in sorted((root/'src/nexus').rglob('*.py'))}


def graph(root):
    modules=module_map(root);edges={};dynamic=[]
    for name,path in modules.items():
        tree=ast.parse(path.read_text());deps=set();package=name if path.name=='__init__.py' else name.rpartition('.')[0]
        for node in ast.walk(tree):
            targets=[]
            if isinstance(node,ast.Import):targets=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                prefix=package.split('.')[:len(package.split('.'))-node.level+1] if node.level else []
                base='.'.join(prefix+([node.module] if node.module else [])) if node.level else (node.module or '')
                targets=[base]+[base+'.'+a.name for a in node.names]
            elif isinstance(node,ast.Call) and (isinstance(node.func,ast.Name) and node.func.id in ('__import__','import_module') or isinstance(node.func,ast.Attribute) and node.func.attr in ('import_module','run_path')):
                dynamic.append(dict(module=name,line=node.lineno))
            for target in targets:
                if target in modules:deps.add(target)
        parts=name.split('.')
        deps.update('.'.join(parts[:i]) for i in range(1,len(parts)) if '.'.join(parts[:i]) in modules)
        edges[name]=deps-{name}
    return modules,edges,dynamic


def closure(edges,roots):
    seen=set();todo=list(roots)
    while todo:
        name=todo.pop()
        if name not in edges:raise ValueError('missing_source_module: '+name)
        if name not in seen:seen.add(name);todo.extend(edges[name]-seen)
    return sorted(seen)


def audit(root=ROOT):
    root=Path(root);modules,edges,dynamic=graph(root)
    roots=['nexus.seed.core','nexus.seed.lab','nexus.seed.grounded_agent','nexus.seed.action_readout']
    reachable=closure(edges,roots);snapshots={}
    for name in SNAPSHOTS:
        p=root/'docs/history/seed-focus-2026-10-20'/Path(name).name
        snapshots[name]=dict(snapshot=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    result=dict(schema='seed_focus_audit_v1',base=BASE,roots=roots,reachable_modules=reachable,
        reachable_source_sha256={str(modules[n].relative_to(root)):hashlib.sha256(modules[n].read_bytes()).hexdigest() for n in reachable},
        retained_outside_static_closure=sorted(set(modules)-set(reachable)),dynamic_paths_requiring_review=dynamic,
        safe_to_delete_automatically=[],historical_code_deleted=False,context_snapshots=snapshots,
        scientific_execution=False,model_inference=0,new_environment_interactions=0,
        ledger=dict(used_s=1905.6321034559958,remaining_s=1694.3678965440042))
    if (root/'.git').exists():
        result['inspected_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        result['tracked_tree_dirty']=bool(subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=root,text=True).strip())
        result['branches']=subprocess.check_output(['git','for-each-ref','--format=%(refname) %(objectname)','refs/heads','refs/remotes/github'],cwd=root,text=True).splitlines()
        result['worktrees']=subprocess.check_output(['git','worktree','list','--porcelain'],cwd=root,text=True).splitlines()
    else:result['branch_coverage']='not_a_git_checkout'
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2,allow_nan=False))
