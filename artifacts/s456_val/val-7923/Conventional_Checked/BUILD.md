# val-7923 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "none", "gold_maintenance": "recompute_affected", "lateness": "watermark", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "iso_only", "ts_parse": "text"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
