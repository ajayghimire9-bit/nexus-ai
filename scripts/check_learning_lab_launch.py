"""Repeatable local launch/preconnect check. Never enables fixture execution."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def check():
    root=Path(__file__).resolve().parents[1]
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    child=subprocess.Popen([sys.executable,str(root/'scripts/run_learning_lab.py'),'--port',str(port),'--max-runtime-s','15'],
        cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    idle=None
    try:
        # stdout readiness avoids starting a request before bind completes.
        if 'NEXUS Learning Lab:' not in child.stdout.readline():raise RuntimeError('server_start_failed')
        idle=socket.create_connection(('127.0.0.1',port),timeout=2.)
        # A browser may preconnect without sending headers. It must not block
        # other requests, as it did with the earlier single-thread server.
        with urlopen(f'http://127.0.0.1:{port}/api/status',timeout=3.) as response:status=json.load(response)
        with urlopen(f'http://127.0.0.1:{port}/api/operators',timeout=3.) as response:replay=json.load(response)
        assert status['fixtures_enabled'] is False and replay['live'] is False and len(replay['cases'])==16
        return dict(kind='local_recorded_launch_check',preconnect_does_not_block=True,query_cases=16,
            fixtures_enabled=False,capture_sha256=replay['capture_sha256'],new_environment_interactions=0)
    finally:
        if idle:idle.close()
        child.terminate()
        try:child.communicate(timeout=3.)
        except subprocess.TimeoutExpired:child.kill();child.communicate()


if __name__=='__main__':print(json.dumps(check(),indent=2))
