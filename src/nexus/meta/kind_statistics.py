"""Original epsilon-greedy sample means, shared without optional NN imports.

This is the existing controller's numeric bookkeeping, not another learner.
Caller-specific feedback boundaries and action eligibility remain at adapters.
"""

def kind_value(sums,counts,kind):
    n=counts.get(kind,0)
    return 0.0 if n<=0 else sums[kind]/n


def observe_kind(sums,counts,kind,reward):
    sums[kind]=sums.get(kind,0.0)+float(reward)
    counts[kind]=counts.get(kind,0)+1
