"""Vetted numeric-data worker. No environment, shell, repository write or promotion.

This is a development adapter, not another agent/world model. New adapters must
be reviewed and metered in the host before their operations can be dispatched.
"""
import math
from pathlib import Path
import resource
import sys
import time

from .experimental import data_rows, number, read, recipe, write_new


def limits(caps):
    # Kernel process CPU limit; threads share the process allowance. This worker
    # never forks. macOS RLIMIT_AS is unreliable: use host RSS watchdog instead.
    seconds = max(1, math.ceil(caps['cpu_s']))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
    if sys.platform.startswith('linux'):
        memory = caps['memory_mb']*1024*1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10_000_000, 10_000_000))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def build(spec, width):
    import torch
    from torch import nn
    from nexus.nn.factory import build_mlp
    trunk, out = build_mlp(width, tuple(spec['hidden']), spec['activation'])
    return nn.Sequential(trunk, nn.Linear(out, 1))


def export(model, spec, width):
    return dict(schema='experimental_numeric_mlp_v1', recipe=spec, width=width,
                state={k:v.detach().cpu().tolist() for k,v in model.state_dict().items()})


def load(row):
    import torch
    if set(row) != {'schema','recipe','width','state'} or row['schema']!='experimental_numeric_mlp_v1':
        raise ValueError('model_schema')
    recipe(row['recipe'])
    if type(row['width']) is not int or not 1<=row['width']<=128:
        raise ValueError('model_width')
    model = build(row['recipe'], row['width'])
    values = {k:torch.tensor(v, dtype=torch.float32) for k,v in row['state'].items()}
    if any(not torch.isfinite(v).all() for v in values.values()):
        raise ValueError('nonfinite_model')
    model.load_state_dict(values, strict=True)
    model.eval()
    return model


def run(request):
    import torch
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    curve = []
    def tensors(data):
        data_rows(data)
        return (torch.tensor([r['x'] for r in data['rows']], dtype=torch.float32),
                torch.tensor([r['y'] for r in data['rows']], dtype=torch.float32))
    if request['mode']=='exploration':
        spec = recipe(request['recipe'])
        torch.manual_seed(spec['seed'])
        x,y = tensors(request['inputs']['train'])
        dx,dy = tensors(request['inputs']['development'])
        model = build(spec, x.shape[1])
        optimizer = (torch.optim.Adam if spec['optimizer']=='adam' else torch.optim.SGD)(model.parameters(), lr=spec['learning_rate'])
        for update in range(1, spec['updates']+1):
            optimizer.zero_grad()
            loss = ((model(x).squeeze(-1)-y)**2).mean()
            if not torch.isfinite(loss):
                raise ValueError('nonfinite_training_loss_no_retry')
            loss.backward(); optimizer.step()
            with torch.no_grad():
                train_loss = float(((model(x).squeeze(-1)-y)**2).mean())
                dev_loss = float(((model(dx).squeeze(-1)-dy)**2).mean())
            curve.append(dict(update=update, train_mse=train_loss, development_mse=dev_loss))
        evaluation = (dx,dy)
        saved = export(model, spec, x.shape[1])
    elif request['mode'] in ('validation','confirmation'):
        model = load(request['inputs']['model'])
        evaluation = tensors(request['inputs']['assessment'])
        saved = request['inputs']['model']
    else:
        raise ValueError('mode_required')
    with torch.no_grad():
        x,y = evaluation
        errors = (model(x).squeeze(-1)-y)**2
        baseline = request['inputs'].get('baseline_model')
        reference = (load(baseline)(x).squeeze(-1)-y)**2 if baseline else y*y
        metrics = dict(mse=float(errors.mean()), baseline_mse=float(reference.mean()),
                       worst_error_increase=float((errors-reference).max()))
    for value in metrics.values():
        number(value, -1e12)
    return dict(metrics=metrics, curve=curve, model=saved,
                runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=torch.get_num_threads()),
                resources=dict(updates=len(curve),real_steps=0,imagined_transitions=0,
                               cpu_s=time.process_time(),
                               training_examples=len(request['inputs']['train']['rows'])*len(curve) if curve else 0,
                               development_examples=len(x)*(len(curve)+1) if curve else 0,
                               assessment_examples=len(x) if not curve else 0,
                               network_forwards=3*len(curve)+1+int(bool(request['inputs'].get('baseline_model'))),
                               parameter_count=sum(p.numel() for p in model.parameters())))


if __name__=='__main__':
    request = read(Path(sys.argv[1]))
    limits(request['caps'])  # before importing the optional neural runtime
    if request.get('adapter')=='seed_question_selection_v1':
        from .question_selection import run as run_questions
        result=run_questions(request)
    elif request.get('adapter')=='seed_learning_choice_v1':
        from .learning_choice import run as run_learning_choice
        result=run_learning_choice(request)
    elif request.get('adapter')=='seed_sequential_consistency_v1':
        from .sequential_consistency import run as run_sequential
        result=run_sequential(request)
    elif request.get('adapter')=='seed_prefix_consistency_v1':
        from .prefix_consistency import run as run_prefix
        result=run_prefix(request)
    elif request.get('adapter')=='seed_update_gate_v1':
        from .update_gate import run as run_gate
        result=run_gate(request)
    elif request.get('adapter')=='seed_cumulative_learning_v1':
        from .cumulative_learning import run as run_cumulative
        result=run_cumulative(request)
    elif request.get('adapter')=='seed_bounded_correction_v1':
        from .bounded_correction import run as run_bounded
        result=run_bounded(request)
    elif request.get('adapter')=='seed_update_diagnosis_v1':
        from .update_diagnosis import run as run_diagnosis
        result=run_diagnosis(request)
    elif request.get('adapter')=='seed_nonlinear_learning_v1':
        from .nonlinear_learning import run as run_study
        result=run_study(request)
    else:result=run(request)
    write_new(Path(sys.argv[2]), result)
