# Corrected-contract Seed GUI

From this branch with the project's PyTorch/NumPy dependencies:

```sh
python3 scripts/run_seed_contract_gui.py
```

Open `http://127.0.0.1:8776/seed`. The launcher verifies the fixed registered
aligned/tanh/5511 model hash. It never trains or chooses a better-looking model.
The loopback server expires after900seconds; restart it when needed.

- Inspect, Observe all modalities, and Local language are read-only for h/z,
  world and evidence. Preview norms may differ from committed inspector state;
  previews are not installed. Work counters still measure actual computation.
- Imagine and act once uses value pruning (48 imagined states). Imagine without
  pruning scores the same16 H4 candidates (64 states). Decisions can be poor.
- World conditioning uses the saved source bank. Taught prototypes/programs
  remain auditable and can resolve concepts, but do not replace that bank.
- Save/restart preserves h/z without assimilating history twice. Stop blocks
  both planning modes. The earlier one-step readout remains unrun/disabled.

Read [the negative results](../NEXUS_SEED_CONTRACT_RESULTS.md): practical
improvement failed; random/greedy/untrained controls remain strong. Trace text
generation is not language understanding. No concept-language expansion ran.
