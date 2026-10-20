# Run Seed with memory-aware adaptation

From this branch,with Python3.11+,PyTorch/NumPy and the project installed
(`python3 -m pip install -e .`):

```sh
python3 scripts/run_seed_adaptive_gui.py
```

Open **http://127.0.0.1:8777/seed**. This verifies the frozen core and final
registered seed6101 plasticity-controller hashes. It does not start meta-training,
select a better-looking model or contact an external LLM. Server expires in15minutes.

1. Teach **dax** using YES/NO. The meaning adapter learns the actual label.
   **Observe all modalities** exposes its uncalibrated learned score,which cannot
   bypass the symbolic execution checker. There is still no arbitrary language
   understanding; the parser and supplied finite grammar remain limited.
2. Set an object and goal. **Adaptive action + learn actual reward** ranks nine
   actions using frozen predicted reward plus a small learned correction,then
   learns only from the selected action's actual reward. This is one-step control,
   distinct from the unchanged **Imagine and act once** latent MPC.
3. **Choose teaching question by simulated learning** considers at most four
   examples and two possible answers. Imagined answers are discarded. Answer
   the actual card to provide evidence. Actual ask-action reward is separate.
4. Every eight actual lessons Seed automatically checks a bounded edit (at most
   three automatic checks/session). **Review meaning/reward skill edits** also compares keep,repair,scoped residual and
   merge using reserved development lessons. Insufficient evidence means keep.
   This is numeric skill adaptation,not generated Python or new symbolic primitives.
5. **Inspect/Observe/Local language** do not update learning state. **Save** then
   restart the same launcher and **Resume saved** to recover small weights,
   anchors and reserved assessments. **Stop** blocks actions and learning.

Every fourth actual lesson is assessment-only. At most24 actual lessons and
two scoped skills/session; after the cap learning stops. Corrections invalidate
the meaning block/anchors conservatively,without retraining the world model.
The journal preserves all old evidence; it cannot grant runtime capabilities.

Read [actual results](../NEXUS_SEED_MEMORY_AWARE_RESULTS.md): the architecture is
implemented,but learned plasticity did **not** clear the improvement threshold.
The fixed protected update remains a strong comparator. No general learning,
control improvement or AGI has been demonstrated by this implementation.
