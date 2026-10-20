"""Seed-first local CLI. Status/help/JSON verification need only Python stdlib."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def repository(path):
    root=Path(path).expanduser().resolve()
    if not all((root/p).is_file() for p in ('AGENTS.md','scripts/run_learning_lab.py','web/learning-lab/seed.html')):
        raise ValueError('Seed repository required; use --repository /path/to/nexus-ai')
    return root


def command(args,root):
    """Typed allowlist; never interprets command strings or installs packages."""
    if args.action=='experimental':
        directory=['--directory',str(args.directory)] if args.directory is not None else []
        return [sys.executable,str(root/'scripts/nexus_experimental.py'),*directory,*args.options]
    if args.action=='serve':
        if not 1024<=args.port<=65535 or not 1<=args.seconds<=900:raise ValueError('bounded_loopback_server_required')
        if args.mode=='symbolic':
            return [sys.executable,'-I','-S',str(root/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(args.port),'--max-runtime-s',str(args.seconds)]
        return [sys.executable,str(root/'scripts/run_seed_adaptive_gui.py'),'--with-readout','--port',str(args.port),'--max-runtime-s',str(args.seconds)]
    scripts={'check':'check_repository.py','verify':'verify_seed_surprise_readout.py','audit-source':'audit_seed_focus.py'}
    if args.action=='verify' and (root/'artifacts/seed_spatial_transfer.json').exists():scripts['verify']='verify_seed_spatial_transfer.py'
    if args.action not in scripts:raise ValueError('explicit_seed_command_required')
    return [sys.executable,'-I','-S',str(root/'scripts'/scripts[args.action])]


def main(argv=None):
    p=argparse.ArgumentParser(description='NEXUS Seed: teach, remember, act; learning-to-learn is a research goal.')
    p.add_argument('--repository',type=Path,default=Path.cwd(),help='source checkout with web assets and saved evidence')
    s=p.add_subparsers(dest='action',required=True)
    serve=s.add_parser('serve',help='bounded local GUI; never starts research training')
    serve.add_argument('--mode',choices=('symbolic','readout'),default='symbolic');serve.add_argument('--port',type=int,default=8766);serve.add_argument('--seconds',type=int,default=900)
    experimental=s.add_parser('experimental',help='owner-controlled development sandbox; no automatic execution')
    experimental.add_argument('--directory',type=Path)
    experimental.add_argument('options',nargs=argparse.REMAINDER)
    for name in ('status','check','verify','audit-source'):s.add_parser(name)
    args=p.parse_args(argv)
    try:
        root=repository(args.repository)
        if args.action=='status':
            path=root/'artifacts/seed_surprise_readout.json';r=json.loads(path.read_text())
            status=dict(project='NEXUS Seed',learning_to_learn_established=False,action_readout_screen=r['analysis']['screen_passed'],core_replications=1,greedy_still_stronger=True,results=str(root/'docs/NEXUS_SEED_SURPRISE_READOUT_RESULTS.md'))
            spatial=root/'artifacts/seed_spatial_transfer.json'
            if spatial.exists():
                q=json.loads(spatial.read_text());status.update(spatial_transfer_complete=q['declared_complete'],spatial_transfer_screen=q['analysis']['screen_passed'],results=str(root/'docs/NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md'))
            print(json.dumps(status,indent=2));return
        env=dict(os.environ);env['PYTHONPATH']=str(root/'src')+os.pathsep+env.get('PYTHONPATH','')
        result=subprocess.run(command(args,root),cwd=root,env=env)
        if result.returncode:raise SystemExit(result.returncode)
    except (ValueError,FileNotFoundError,KeyError) as e:p.exit(2,str(e)+'\n')


if __name__=='__main__':main()
