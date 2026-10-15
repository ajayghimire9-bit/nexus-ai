# NEXUS latent-adaptation evidence

This is an audit of recorded results. It does not train a model, collect environment data, or change a previous artifact. The numerical claims below are the committed JSON results. Weights were hash-checked locally and were not refit.

Base commit `f9468a5b233347135e3485fbae0fd25cdc981d61`. Manifest `artifacts/nexus_evidence_manifest.json`.

The sequence is evidence about specific Pendulum physics, frozen decoders, and a fixed H=16 random-shooting planner. It is not a general control improvement, not learning-to-learn, and not AGI.

## Provenance

Each result artifact records `source_dirty: false` at its implementation commit. The control-replication file also has `git.dirty: true` because the result files were present when the artifact was written. That flag is the worktree, not a second training run. The implementation SHA is the source lock.

| Result | Artifact sha256 | Implementation |
| --- | --- | --- |
| Direct latent source audit | `9681f5de77d53c8fafba54aa5c0e41eeb60cd39a8e0f4d8308615dcf7476f9dc` | `d037ffda2fb34238411f39c82d64ff5812b98810` |
| Direct latent confirmation | `1de5b1ebfa33caafe602f55d709490d71a25d07122a3198019a0aca5e73bb67f` | `aac5e33d677f05fc57e9191bd522e82982e3ef20` |
| Encoder distillation | `cd120f53ffdd1efbaaff8b632faad01b251e3b4e4afccd201af28c267ac1162f` | `29931126df34da0064a67fd3b8a239c673412f72` |
| Encoder representability | `a5967f26fc4e88a850b84a81c53647850945e8bb3275307e6e9ff27a76e08d5f` | `76c1e4aa87a611217288de15ccc59544689ff9da` |
| Broader-task development | `c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba` | `fd1e864cb2e1dff91e73bf35b184becc4c81be22` |
| Prediction confirmation | `18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa` | `4da390da236c2b8fb172bcbc13c65ebce6aae9da` |
| Three-decoder control | `ce04ce90f368a6d0ecd45b42cce881e045619fd642bfe39d13c8c32216c5e9b4` | `9506604ba1aae853d8be3421d87b9e9477a9b5a4` |
| Ten-decoder replication | `35c75320e1c243eaa1914cf6e726e9849d246910ebfc79f6ac0f390c86daf0e9` | `b3cd0cec251cf996bde1a8b87b52ac656d16be01` |
| Checkpoint manifest | `265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b` | matches the replication artifact |
| One-shot diagnostic | `f1f36506d3c64086898b6f462f9915a28037784dee52f47bce5c19b91bfe390a` | `a1f192e2be254c5511774254ee613a3597e3148c` |
| Receding-horizon diagnostic | `46b0eb85e655b7bb9e71d9a19268202733211f3741ab2fcb8729e193bc7c49f0` | `b6a079bab98c965b65a127e90a178a73ddcbb7f2` |

The one-shot artifact's recorded control-artifact hash matches the replication file. The standalone checkpoint manifest matches the copy embedded in the replication artifact. Three physics hashes stay distinct: direct-latent confirmation `87b83c41be34aa1a`, encoder confirmation and the earlier control group `baa655fcb94e61bc`, and the fresh control group `053e8efca60fb4ac`.

## Milestones

### Direct latent optimization

With the history decoder frozen, Adam at learning rate 0.1 for 256 updates from the global vector lowered source-audit angular-velocity error to **0.0628** versus zero **0.1151**, global **0.1109**, and wrong-support **0.1762**. Paired control-minus-task intervals on three model seeds exclude 0. The frozen encoder on the same rows stayed at **0.1256**. Cosine and sine paired differences versus the global vector include 0. The screen passed. This is a support-fit latent, not an encoder.

### Unseen-physics latent confirmation

The same locked fit on physics hash `87b83c41be34aa1a` reached angular velocity **0.152** versus zero **0.308**, global **0.314**, and wrong-support **0.398**. The five paired angular-velocity intervals exclude 0. The frozen encoder stayed at **0.307**. The replication unit is three model seeds, df = 2. Support loss fell and is not the screen.

### Encoder distillation failure

The 584-parameter encoder trained to match those support-fit latents did not beat zero context on development. The selected cell, distillation only at epoch 120 with 128 support rows, had angular velocity **0.1747** versus zero **0.1587**. The paired control-minus-student interval is **−0.0159 [−0.0170, −0.0149]** on ten student seeds. Those seeds share three decoders, so that interval is narrower than a decoder-level interval. The point estimate is still worse than zero. Confirmation physics were not collected. The teacher on the same decoder was **0.0781**.

### Encoder representability

The same encoder can reproduce the eight saved training codes at Adam learning rate **0.01**. Final mean latent distance on the three decoders was **0.00745, 0.00211, and 0.000024**, against constant baselines of about **1.31, 1.75, and 1.51**. The recorded passing rate is 0.01. This is a fit to the supports that defined the codes.

### Broader-task encoder generalization

Trained at learning rate 0.01 on twelve further physics, development angular velocity at epoch 200 was **0.0913** versus zero **0.1587**, the frozen encoder **0.1773**, a global vector **0.1478**, and the teacher **0.0781**. The paired interval uses five student seeds that share three decoders. Training latent distance stayed **0.648**. The development screen passed. It is not the confirmation.

### Prediction confirmation

Retraining matched the development artifact with absolute deltas of 0, then scored physics hash `baa655fcb94e61bc`. Confirmation angular velocity was **0.1016** versus zero **0.2729**, the frozen encoder **0.2660**, and a global vector **0.2742**. Decoder-level gaps, n = 3, are **+0.171 [+0.136, +0.207]**, **+0.164 [+0.156, +0.173]**, and **+0.173 [+0.133, +0.213]**. The teacher was **0.0876**, and that paired interval includes 0. Latent distance stayed **1.558**. The primary unit is the decoder. Thirty encoder files were saved and hash-checked.

### Three-decoder control experiment

The same epoch-200 students in H=16 MPC returned **−683.0** versus zero **−768.4** and the frozen encoder **−773.2**. Decoder-level gaps are **+85.4 [−109.4, +280.3]** versus zero and **+90.2 [−5.7, +186.1]** versus the encoder. Both include 0. The pass rule required a 25-point margin and a lower bound above 0. The result is inconclusive. These episode seeds stay closed.

### Ten-decoder control replication

Ten decoders, with student seeds, tasks, and episodes averaged inside each decoder. On new episodes of physics `baa655fcb94e61bc`, student return was **−636.4** versus zero **−708.6** and the frozen encoder **−699.2**. Paired gaps are **+72.2 [+45.6, +98.8]** and **+62.8 [+31.3, +94.3]**. Both lower bounds clear 25. On fresh physics `053e8efca60fb4ac`, student return was **−716.0** versus zero **−696.6** and the encoder **−705.7**. The zero gap is **−19.4 [−35.4, −3.3]**, entirely below 0. The encoder gap is **−10.3 [−26.4, +5.9]** and includes 0. Visited angular-velocity error still improved on both sets (**+0.127 [+0.109, +0.144]** and **+0.116 [+0.093, +0.140]**). Seeds 0–2 are the earlier decoder weights, rescored on new episodes, with weight gap 0. Seeds 3–9 are new. The checkpoint manifest matches the artifact.

### One-shot prediction-control diagnostic

On new states, not a new episode-return test. Fresh one-step angular velocity improved by **0.1148 [0.1030, 0.1266]**, shared-candidate regret by **1.313 [0.507, 2.118]**, and H=16 reward-forecast error by **6.386 [5.450, 7.322]**. Correct selection rose by **0.1175 [0.0865, 0.1485]** and Spearman by **0.0597 [0.0177, 0.1016]**. The previous physics moved in the same direction: regret **0.805 [0.080, 1.529]**. The closed fresh episode gap was an input and was not remeasured. The fresh decision is `evaluation_variance`.

### Receding-horizon diagnostic

Live H=16 control on both physics groups, then same-state counterfactuals. All **1920 / 1920** stored decisions reproduced. Fresh pooled regret improved by **0.812 [−0.038, 1.662]** and the matched next-16 continuation changed by **−0.528 [−1.139, 0.083]**. Both include 0. Selected-sequence score error still fell by **4.751 [3.023, 6.480]**. The fresh decision is `inconclusive`. On the earlier physics the local measurements agree with the closed positive return. That agreement is a contrast. The next-16 sum is a matched continuation under a shared zero-context replanner. It is not a 200-step episode value.

## Hypothesis table

| Experiment | Predeclared claim | Primary comparison | Replication unit | Outcome | Limitations | Unknown |
| --- | --- | --- | --- | --- | --- | --- |
| Direct latent optimization | A support-only latent beats zero, global, and wrong-support context on held-out source angular velocity | Control minus task angular velocity | 3 model seeds, df = 2 | Passed. Task **0.0628** versus zero **0.1151** | Source physics. Cosine and sine intervals include 0. The encoder was not trained | Whether an encoder can predict the latent |
| Unseen-physics latent confirmation | The locked fit transfers to hash `87b83c41be34aa1a` | Same three controls, 5% bar | 3 model seeds, df = 2 | Passed. Task **0.152** versus zero **0.308** | Exploratory n = 3. One physics draw | Whether the encoder amortizes the fit |
| Encoder distillation | The history encoder matches those latents and beats zero context on development angular velocity | Zero minus student | 10 student seeds sharing 3 decoders | Failed. Student **0.1747** versus zero **0.1587** | Confirmation physics were not collected. The seed interval overstates independence | Whether a higher learning rate can fit the saved codes |
| Encoder representability | The encoder can reproduce the eight saved codes | Latent distance versus a 0.25 / 0.5 threshold and a constant vector | 3 decoders | Passed at learning rate 0.01. Distances **0.00745, 0.00211, 0.000024** | The supports are the ones that defined the codes | Whether that fit lowers error on new tasks |
| Broader-task generalization | Training at 0.01 on twelve physics lowers development angular velocity below zero and the frozen encoder | Control minus student | 5 student seeds sharing 3 decoders | Passed. **0.0913** versus zero **0.1587** and encoder **0.1773** | Development screen. Latent distance stayed **0.648** | Whether new physics agree |
| Prediction confirmation | The retrained encoder lowers confirmation angular velocity at least 0.01 below zero, the frozen encoder, and a global vector | Control minus student | 3 decoders | Passed. **0.1016** versus zero **0.2729**, encoder **0.2660**, global **0.2742** | The teacher interval includes 0. Four physics tuples | Whether return improves |
| Three-decoder control | Student H=16 return beats zero and the frozen encoder by at least 25, with lower bounds above 0 | Student minus control | 3 decoders | Inconclusive. **+85.4 [−109.4, +280.3]** and **+90.2 [−5.7, +186.1]** | df = 2. Episode seeds closed | Whether more decoders separate the interval |
| Ten-decoder replication | The same 25-point rule holds on new episodes of the earlier physics and on disjoint physics | Student minus zero and student minus encoder | 10 decoders | Earlier physics passed. Fresh student minus zero **−19.4 [−35.4, −3.3]** | Seeds 0–2 reuse the old weights. Fresh encoder interval includes 0 | Why the return gap reverses |
| One-shot diagnostic | Better one-step prediction comes with worse shared-candidate ranking on the fresh physics | Zero minus student on regret and on one-step angular velocity | 10 decoders | Ranking improved with prediction. Fresh regret **+1.313 [+0.507, +2.118]** | The closed episode was not remeasured. Regret, correct selection, and Spearman share one candidate table | How a one-shot gain becomes a 200-step loss |
| Receding-horizon diagnostic | Visited-state regret reverses, or the matched next-16 continuation reverses, or live replay fails | Decoder-level Student-t on fresh visited states | 10 decoders | Inconclusive. Regret **+0.812 [−0.038, +1.662]**, next-16 **−0.528 [−1.139, +0.083]**. Replay **1920/1920** | Next-16 is not a full episode. Open-loop return repeats the regret contrast | Which part of the live episode carries the 19-point gap |

## Separated conclusions

These five statements are the consolidation. Each one has the scope written beside it.

**Fast learned context improves prediction on tested unfamiliar physics.** Supported on the named sets. The direct latent did so on hash `87b83c41be34aa1a`. The 584-parameter encoder did so on hash `baa655fcb94e61bc` after the broader-task training. The first distillation, before that training change, lost to zero context on development. Prediction here means angular-velocity error under the frozen decoder. It does not mean return.

**Contextual control improves return on the earlier physics group.** Supported by the ten-decoder replication on hash `baa655fcb94e61bc`: student minus zero **+72.2 [+45.6, +98.8]** and student minus frozen encoder **+62.8 [+31.3, +94.3]**. The three-decoder experiment on the same physics family was inconclusive and is not a second sample of those three models.

**Contextual control transfers negatively on the fresh physics group.** Supported versus zero context on hash `053e8efca60fb4ac`: **−19.4 [−35.4, −3.3]**. The paired gap versus the frozen encoder includes 0. Visited prediction still favored the student on that set.

**One-shot action ranking improves in some measurements.** Supported on the sampled-state diagnostic, where fresh regret improved by **1.313 [0.507, 2.118]** and the earlier physics improved by **0.805 [0.080, 1.529]**. The pooled visited-state regret in the receding-horizon audit is **0.812 [−0.038, 1.662]** and includes 0. Step 0 of that audit still favored the student. Those are different state samples, not one pooled ranking result.

**The fresh-physics receding-horizon mechanism remains unresolved.** The primary decision is `inconclusive`. Replay of the stored live decisions succeeded, the pooled visited-state regret interval includes 0, and the matched next-16 interval includes 0. Score error on the selected sequence still favored the student. None of the registered mechanism branches fired.

## Dependent metrics

Counting every reported column as a separate confirmation would overstate the evidence.

On all 640 receding-horizon cells, `regret_improvement` and `sequence_return_improvement` differ by at most **4.0e-14**. On a shared candidate set, the regret gap is the selected sequence's realized-return gap. They are one contrast.

On the same cells, `continuation_improvement` and `action_regret_improvement` differ by at most **4.0e-14**. The three first actions share one continuation, so the return gap is the selected-action regret gap. They are one contrast.

In the one-shot diagnostic, regret, correct selection, and Spearman are three summaries of one predicted-score vector and one realized-return vector. Reward-forecast error is a different functional of that same table. The decision rule used them as a conjunction. They are not four replications.

One-step angular velocity is one coordinate of the one-step state error. In the direct-latent audits, overall MAE moved with angular velocity, while the cosine and sine paired intervals included 0. Horizon-3, horizon-8, and horizon-16 errors are longer rollouts of the same model. They are related measurements, not additional seeds.

Student-minus-zero and student-minus-encoder share the student returns. Requiring both is a conjunction. It does not double the sample.

Decoder seeds 0–2 in the ten-decoder replication are the weights from the three-decoder control experiment, evaluated on new episodes. The ten-decoder interval is the replication of the return question. Adding the two intervals would count those three models twice.

The amortized and development-generalization intervals use student seeds that share three decoders. Both artifacts say so. From the prediction confirmation onward, the primary unit is the decoder.

The prediction confirmation, both control studies, the one-shot diagnostic, and the receding-horizon diagnostic reuse those decoders. They are repeated measurements of the same models. They are not forty independent decoders.

## Checkpoints and GitHub

`.gitignore` excludes `*.pt`, `*.pth`, and `checkpoints/`. `git ls-files` tracks no weight file. This machine has **191** local `.pt` files.

Hash checks matched **120** recorded weight files and found **0** mismatches and **0** missing files: **30** confirmation encoders, **84** replication-manifest files (7 history decoders, 7 global vectors, and 70 student encoders), **3** parent history decoders, and **3** parent MLP checkpoints. The replication manifest hash is `265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b`.

GitHub carries the JSON results and that manifest. A clone can audit the numbers. It cannot reload the encoders or decoders, because the binary weights are absent there. This consolidation did not retrain them. The other local `.pt` files are intermediate snapshots outside the 120-file hash set.

## One next question

On newly registered fresh-physics episodes, with the saved student and zero-context controllers held fixed, what fraction of the paired student-minus-zero return difference accumulates during steps 0-15, and what fraction accumulates during steps 16-199?

The closed fresh gap is about nineteen return points. The matched diagnostic continuation differed by about half a point, and that interval includes 0. The diagnostic continuation is not the live controller's own cumulative return. Closed episode seeds stay closed. The network, horizon, and candidate count stay fixed. This question was not run.
