"""One-run host for the standing-grant full-policy development screen."""
import json
import platform
import subprocess

import numpy as np
import torch
import gymnasium

from nexus.evolution2 import full_policy_source as h


if __name__=='__main__':
    if h.RESULT.exists():raise FileExistsError('preserve_closed_result')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=h.ROOT,text=True).strip():
        raise RuntimeError('commit_protocol_implementation_first')
    tracked=subprocess.check_output(['git','ls-files'],cwd=h.ROOT,text=True).splitlines()
    paths=['scripts/run_unified_full_policy_source.py','src/nexus/evolution2/full_policy_source.py',
           'tests/test_unified_full_policy_source.py',str(h.CONFIG.relative_to(h.ROOT)),
           str(h.PROTOCOL.relative_to(h.ROOT)),str(h.ALLOCATION.relative_to(h.ROOT))]
    if not set(paths)<=set(tracked):raise RuntimeError('implementation_must_be_committed')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip()
    torch.set_num_threads(1)
    result=h.run(json.loads(h.CONFIG.read_text()))
    result.update(execution_sha=revision,code_sha256={name:h.sha(h.ROOT/name) for name in paths},
                  dependencies=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,
                                    gymnasium=gymnasium.__version__,cpu_threads=1))
    with h.RESULT.open('x') as out:json.dump(result,out,allow_nan=False);out.write('\n')
    print(json.dumps({k:result.get(k) for k in ('declared_complete','failure','analysis','resources','session_ledger')}))
