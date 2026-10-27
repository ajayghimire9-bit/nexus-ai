# de3-dev-956 (Fixed_Policy)

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True), ('accounting_and_lag', True), ('gold_equals_recompute', True), ('silver_rederivation', True), ('lateness_conformance', False)]
