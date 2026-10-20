"""Outer Seed adapter. Same controller, immutable candidates/limits, no executor."""
from dataclasses import dataclass,asdict
import math
from nexus.meta.controller import EpsilonGreedyController
from nexus.evolution1.fixtures import Journal


@dataclass(frozen=True)
class Recipe:
    name:str
    trunk_width:int
    activation:str
    environment:str='authored_grid'


RECIPES=(Recipe('compact_tanh',32,'tanh'),Recipe('compact_relu',16,'relu'))


class OuterSeedMeta:
    def __init__(self):
        self.controller=EpsilonGreedyController(epsilon=0.)
        self.journal=Journal();self.seen=set()

    def choose_learning(self,available,rng,*,explore=False):
        allowed=('ask','test_concept','repair','add_skill','keep')
        if not available or any(a not in allowed for a in available):raise ValueError('bounded_learning_action')
        unseen=[a for a in available if not self.controller.kind_n.get('lesson/'+a,0)]
        if explore and unseen:return unseen[0]
        if explore and rng.random()<.2:return rng.choice(list(available))
        return max(available,key=lambda a:(self.controller.predicted_kind_value((),'lesson/'+a),-allowed.index(a)))

    def reveal_learning(self,action,receipt,*,phase):
        if phase!='source_training' or action not in ('ask','test_concept','repair','add_skill','keep') or type(receipt) is not dict or set(receipt)!={'id','probe_error_before','probe_error_after','labels','compute'}:raise ValueError('permitted_learning_probe_only')
        if receipt['id'] in self.seen or type(receipt['id']) is not str:raise ValueError('unique_learning_probe')
        if any(type(receipt[k]) not in (int,float) or not math.isfinite(receipt[k]) or receipt[k]<0 for k in ('probe_error_before','probe_error_after','labels','compute')):raise ValueError('learning_probe_numeric')
        cost=receipt['labels']+.1*receipt['compute']
        if cost<=0:raise ValueError('positive_learning_cost')
        reward=(receipt['probe_error_before']-receipt['probe_error_after'])/cost
        self.controller.update((),'lesson/'+action,reward);self.seen.add(receipt['id'])
        self.journal.append('seed_meta_learning_probe',dict(action=action,receipt=receipt,reward=reward))

    def propose(self, *, in_episode, remaining_s, remaining_steps):
        if in_episode:raise ValueError('outer_controller_only_between_episodes')
        if remaining_s<=0 or remaining_steps<=0:return None
        unseen=[r for r in RECIPES if self.controller.kind_n.get(r.name,0)==0]
        r=unseen[0] if unseen else max(RECIPES,key=lambda r:self.controller.predicted_kind_value((),r.name))
        self.journal.append('seed_meta_proposal',dict(recipe=asdict(r),execution_authorized=False))
        return r

    def reveal(self,recipe,receipt,*,phase):
        if phase!='training' or recipe not in RECIPES or type(receipt) is not dict or set(receipt)!={'id','observed_training_loss'}:
            raise ValueError('permitted_training_receipt_only')
        loss=receipt['observed_training_loss']
        if receipt['id'] in self.seen or type(loss) not in (int,float) or not math.isfinite(loss) or loss<0:
            raise ValueError('unique_finite_training_receipt')
        self.seen.add(receipt['id']);self.controller.update((),recipe.name,-loss)
        self.journal.append('seed_meta_training_feedback',dict(recipe=recipe.name,receipt=receipt,reward=-loss))


def expression_for(predicate):
    """Reuse existing numeric expression trees as signed predicate margins.

    x is the vector of authored +/-1 literal satisfactions. Summation is an
    executable numeric tree; original Predicate handles the boolean truth.
    """
    from nexus.nn.expr import validate_tree
    tree=('x',) if len(predicate.literals)==1 else ('binary','add',('x',),('x',))
    validate_tree(tree)
    return tree


def program_truth(predicate,obj):
    import torch
    from nexus.nn.expr import eval_expr
    signed=[1. if (obj[k]==v)!=neg else -1. for k,v,neg in predicate.literals]
    margin=eval_expr(expression_for(predicate),torch.tensor([sum(signed)/len(signed)]))
    return bool(float(margin[0])>len(signed)-1)
