"""Optional bounded numeric residual. New weights only; not active by default.

Targets are observed numeric outcome minus supplied prediction, clipped to the
declared output range; inputs use source-only RMS scaling. Boolean predictions
use the explicit empirical Bernoulli table in learning.py, not this residual.
"""
import copy


class NumericResidual:
    def __init__(self, width, bound=1., seed=0):
        import torch
        from torch import nn
        from nexus.nn.factory import build_mlp
        if type(width) is not int or not 1 <= width <= 16 or type(bound) not in (int, float) or not 0 < bound <= 100: raise ValueError('numeric_residual_shape')
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            trunk, size = build_mlp(width, (8,), 'tanh')
            self.model = nn.Sequential(trunk, nn.Linear(size, 1), nn.Tanh())
        self.width = width; self.bound = float(bound); self.scale = torch.ones(width)

    def predict(self, x): return self.model(x/self.scale).squeeze(-1)*self.bound

    def fit(self, source_x, observed_residual, *, steps=50):
        import torch
        if type(steps) is not int or not 1 <= steps <= 100 or source_x.ndim != 2 or source_x.shape[1] != self.width or observed_residual.shape != (len(source_x),) or not torch.isfinite(source_x).all() or not torch.isfinite(observed_residual).all(): raise ValueError('source_numeric_targets')
        self.scale = (source_x.square().mean(0).sqrt()).clamp_min(1e-6).detach()
        target = observed_residual.clamp(-self.bound, self.bound)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=.01)
        for _ in range(steps):
            optimizer.zero_grad(); loss = (self.predict(source_x)-target).square().mean(); loss.backward(); optimizer.step()
        return dict(updates=steps, examples=len(source_x)*steps, parameters=sum(p.numel() for p in self.model.parameters()))

    def checkpoint(self):
        return dict(schema='seed_structure_numeric_v1', width=self.width, bound=self.bound,
                    scale=self.scale.tolist(), state={k:v.detach().tolist() for k,v in self.model.state_dict().items()})

    @classmethod
    def load(cls, wire):
        import torch
        if set(wire) != {'schema','width','bound','scale','state'} or wire['schema'] != 'seed_structure_numeric_v1': raise ValueError('numeric_checkpoint_schema')
        out = cls(wire['width'], wire['bound']); scale = torch.tensor(wire['scale'])
        state = {k:torch.tensor(v) for k,v in wire['state'].items()}
        if scale.shape != (out.width,) or not torch.isfinite(scale).all() or not (scale > 0).all() or any(not torch.isfinite(v).all() for v in state.values()): raise ValueError('finite_numeric_checkpoint')
        out.model.load_state_dict(state, strict=True); out.scale = scale; out.model.eval()
        return out


def execute_numeric(model,state,binding,input_attributes,output_attribute,supplied_prediction):
    import torch
    from .state import entity,scalar,token
    token(output_attribute)
    if type(input_attributes) is not list or len(input_attributes)!=model.width:raise ValueError('numeric_input_bindings')
    for name in input_attributes:token(name)
    if type(supplied_prediction) not in (int,float):raise ValueError('numeric_supplied_prediction')
    scalar(supplied_prediction);obj=entity(state,binding)
    if obj is None:return dict(status='unknown')
    values=[obj['attributes'].get(k) for k in input_attributes]
    if any(type(v) not in (int,float) for v in values):return dict(status='unknown')
    target=obj['attributes'].get(output_attribute)
    if type(target) is bool:raise ValueError('bernoulli_interface_required')
    if output_attribute not in obj['attributes']:return dict(status='unknown')
    with torch.no_grad():residual=float(model.predict(torch.tensor([values],dtype=torch.float32))[0])
    out=copy.deepcopy(state);entity(out,binding)['attributes'][output_attribute]=scalar(supplied_prediction+residual)
    return dict(status='predicted',state=out,hypothetical=True,residual=residual,output='numeric')
