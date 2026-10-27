# de3-val-7943 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "sink_then_offsets", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "wait_contiguous", "gold_maintenance": "delta_no_retract", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "v1_lenient", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
