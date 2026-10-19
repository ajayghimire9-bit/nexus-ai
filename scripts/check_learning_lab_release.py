"""Clean-venv replay acceptance; optional supplied fixture dependencies.

No installs/downloads, real simulators, trained model calls or paid services.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request,urlopen
import venv
import zipfile


def check(archive,fixture_dependencies=None):
    archive=Path(archive).resolve();report=dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        new_scientific_environment_steps=0,model_inference=0,dependency_downloads=0,fixture_restart_tested=False)
    with tempfile.TemporaryDirectory(prefix='nexus-clean-demo-') as tmp:
        root=Path(tmp)/'demo';root.mkdir()
        with zipfile.ZipFile(archive) as z:
            names=z.namelist()
            if len(names)!=len(set(names)) or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):raise ValueError('unsafe_archive')
            z.extractall(root)
        environment=Path(tmp)/'venv';venv.EnvBuilder(with_pip=False,system_site_packages=False).create(environment)
        python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        env={**os.environ,'PYTHONPATH':'','PYTHONNOUSERSITE':'1'}
        done=subprocess.run([str(python),'-I','-S',str(root/'scripts/verify_demo.py')],cwd=root,env=env,text=True,capture_output=True,timeout=15)
        if done.returncode:raise RuntimeError(done.stderr)
        report['manifest']=json.loads(done.stdout)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        child=subprocess.Popen([str(python),'-I','-S',str(root/'scripts/nexus_lab.py'),'--port',str(port),'--max-runtime-s','20'],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            base=f'http://127.0.0.1:{port}';status=None
            for _ in range(50):
                if child.poll() is not None:raise RuntimeError(child.communicate()[1])
                try:
                    with urlopen(base+'/api/status',timeout=.2) as r:status=json.load(r)
                    break
                except (URLError,TimeoutError):time.sleep(.05)
            if status is None or status['fixtures_enabled'] is not False or status['live_environment'] is not False:raise ValueError('isolated_server_start')
            for route,count in [('/api/operators',16),('/api/parent-retention',16)]:
                with urlopen(base+route,timeout=5) as r:value=json.load(r)
                if len(value['cases'])!=count or value['live'] is not False:raise ValueError('verified_recorded_grid')
            with urlopen(base+'/api/training-audit',timeout=5) as r:audit=json.load(r)
            with urlopen(base+'/api/preparation',timeout=5) as r:prepared=json.load(r)
            if audit['query_outcomes_used']!=0 or prepared['execution_authorized'] is not False:raise ValueError('mode_boundaries')
            with urlopen(base,timeout=5) as r:page=r.read()
            if b'parentCase' not in page or b'Persistent research notebook' not in page:raise ValueError('demo_content')
            report.update(clean_stdlib_replay_passed=True,recorded_D_E_present=True,F_unexecuted=True)
        finally:
            child.terminate()
            try:child.communicate(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.communicate()
        if fixture_dependencies is not None:
            dependencies=Path(fixture_dependencies).resolve()
            command='import sys,runpy;sys.path.insert(0,sys.argv.pop(1));script=sys.argv.pop(1);runpy.run_path(script,run_name="__main__")'
            folder=root/'saved-fixture'
            def run(*options):
                result=subprocess.run([str(python),'-I','-S','-c',command,str(dependencies),str(root/'scripts/run_learning_lab_session.py'),*options],cwd=root,env=env,text=True,capture_output=True,timeout=20)
                if result.returncode:raise RuntimeError(result.stderr)
                return json.loads(result.stdout)
            first=run('--new','--directory',str(folder),'--seed','7','--method','unified')
            last=run('--directory',str(folder),'--expected-head',first['head'])
            if first['task_cursor']!=2 or last['task_cursor']!=4 or last['host_calls']<first['host_calls'] or last['new_environment_interactions']!=0:raise ValueError('fixture_restart')
            report.update(fixture_restart_tested=True,fixture_dependency_scope='supplied third-party dependency directory; not a clean dependency installation',
                first_head=first['head'],last_head=last['head'],host_calls=last['host_calls'])
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--fixture-dependencies',type=Path);a=p.parse_args()
    print(json.dumps(check(a.archive,a.fixture_dependencies),indent=2))
