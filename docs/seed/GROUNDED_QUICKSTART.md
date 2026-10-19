# Try the grounded Seed agent

Use Python 3.11+, PyTorch and NumPy (`python3 -m pip install -e .` installs the
declared dependencies). After the pilot produces its JSON model, run:

```sh
python3 scripts/run_learning_lab.py --allow-seed --port 8774 \
  --seed-grounded-model artifacts/seed_grounded_compact_tanh.json \
  --seed-grounded-sha256 HASH_FROM_THE_PILOT_ARTIFACT
```

Copy `models[0].sha256` from `artifacts/seed_grounded_pilot.json`; keep the hash
check enabled. Open `http://127.0.0.1:8774/seed.html`. The loopback server stops
after 900 seconds. Choose another port if this port is occupied.

1. **Observe all modalities** shows recurrent state and learned predictions.
   The canvas is an authored 18×18 object sensor, not a real camera.
2. Set object `o1` and a goal. **Imagine and act once** may move, ask, store or
   retrieve. Inspect predictions, actual reward and language. Plans can be poor.
3. Teach an invented word with YES/NO examples. Neural storage requires eight
   distinct property combinations and enough positive/negative examples. It can
   honestly reject. The finite checker and symbolic planner remain available.
4. **Ask as action**, then answer its card. Actual information feedback occurs
   only when the requested human label arrives.
5. **Save**, restart with the same model/hash, then **Resume saved**. The existing
   hash-chained journal restores evidence and recurrent state. A saved file
   cannot enable model access; the server owner must opt in again.
6. **Local language** exposes an actual small-decoder candidate and factual
   template. **Outer recipe proposal** works only between episodes and cannot
   start training, change evaluation rules or grant permissions.

No external LLM runs. This is not open-ended language, proven general learning
or AGI. See the separate protocol and results for what was actually measured.
