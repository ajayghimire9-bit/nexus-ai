# Frozen Seed action ranking — first result

Execution d0a9ade911a3452a848e5282137375d5577b3abb, committed protocol first.
64 fresh registered states, all9 actions from exact cloned states; outcomes
shared across frozen parents.576 authored steps,1152 candidate transitions plus
128 observation-prior transitions. Inner timer .119s excludes module imports;
conservative1s charged against carried ledger:1861.6321034559958used /
1738.3678965440042remaining. No new training, old checkpoints/results unchanged.
Pre-execution relevant regression83 passed in4.87s.

Tanh reward-only optimal19/64(29.69%), mean regret .415625, pairwise accuracy
.50652. ReLU20/64(31.25%), regret .40625, accuracy .45373. Both fail80%/.05
descriptive screen. Exact uniform-action expected regret .463889 on same data.
Adding .9×value gave optimal18.75%/34.375%, regret .4125/.409375, no consistent
repair. This compares two different objectives with immediate reward, so it is
not a calibrated long-horizon value test.

Mean predicted reward span across actions is only .04882/.04000; mean absolute
reward error .15919/.16452. Reward-only boundary/interior regrets:
tanh .3625/.46875; ReLU .34375/.46875. Weak ranking is not confined to boundaries.
These are descriptive cold-start findings on an authored finite domain, not a
causal explanation of full-episode loss, novel physics, or independent model
replications. The two parents differ in architecture and each has one seed.

One justified improvement is now separately locked in
NEXUS_SEED_ACTION_READOUT_PROTOCOL.md: balanced fresh action supervision and a
small observed-state residual reward readout. It does not alter historical
RSSM weights or pretend a one-step selector is long-horizon MPC. Original GUI
controller remains available; fresh source/audit/control states are separate.
