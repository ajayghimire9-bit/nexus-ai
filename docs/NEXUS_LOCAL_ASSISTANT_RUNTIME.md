# Using the persistent local runtime

NEXUS can keep an existing quantized GGUF model loaded in an owned local
`llama-server`. It does not download a model, use a paid service or silently
replace failed inference with templates. Supply your own local model file and
installed llama.cpp server. Model weights are not checked into Git.

Set paths for your machine, for example:

```sh
export NEXUS_MODEL_PATH=/path/to/local/model.gguf
export NEXUS_LLAMA_SERVER=llama-server
export NEXUS_MODEL_HOST=127.0.0.1
export NEXUS_MODEL_PORT=0
export NEXUS_MODEL_CONTEXT=2048
export NEXUS_MODEL_BACKEND=llama_cpp_server
```

Port 0 chooses a free loopback port. The runtime refuses to take over an occupied
port. Current support is local CPU; backend names other than llama_cpp_server
fail clearly. Context, threads, timeouts, response caching and prompt caching are
also configurable through `RuntimeConfig`. No security setting is changed.

```python
from nexus.seed.local_model_runtime import RuntimeConfig, PersistentLocalRuntime
from nexus.seed.assistant_benchmark_v2 import SCHEMA, intent_prompt, validate_intent
import json

config = RuntimeConfig.from_environment()
with PersistentLocalRuntime(config) as runtime:
    result = runtime.complete(
        intent_prompt("Sum amounts per region, at least 5, largest first", {
            "region": {"inferred_type": "text"},
            "amount": {"inferred_type": "numeric"},
        }), SCHEMA,
    )
    print(validate_intent(json.loads(result["content"])))
    print(result["telemetry"])
```

Use a context manager or call `close()` to shut down the owned server. `cancel()`
closes the HTTP connection and stops that process; a timed-out server does not
silently restart. An ephemeral API key protects the local completion endpoint.
The secret is excluded from metadata. Application caches belong to one runtime
instance and clear on restart; prompt/KV reuse is a separate explicit setting.

`GrammarConstrainedLocalIntentModel` is now a compatibility facade over this
runtime. Its old two-mode intent schema is not the new assistant's four-way
schema and its historical benchmark totals must not be reused as current
latency/token evidence. Use the versioned runner and verifier for research.

The old v1 full benchmark/report entry points now refuse execution, and its
verifier defaults to a byte-preservation check. It will not rewrite historical
artifacts or launch model calls while someone is merely running tests.

Both recorded study IDs are consumed. **Do not rerun them** to seek a better
result. Replay the existing completed evidence without loading a model:

```sh
PYTHONPATH=src python3 scripts/verify_seed_assistant_benchmark_v2.py \
  artifacts/seed_assistant_benchmark_v2_1.json
python3 scripts/analyze_seed_assistant_benchmark_v2.py \
  artifacts/seed_assistant_benchmark_v2_1_raw.jsonl \
  --verify artifacts/seed_assistant_benchmark_v2_1_analysis.json
```

See [results](NEXUS_SEED_ASSISTANT_BENCHMARK_V2_1_RESULTS.md). All three methods
scored 83.33%; capsules did not improve on ordinary caching. The runtime is a
working inference component, not demonstrated autonomous learning or general AI.
