# Teach Seed locally

## Start

Use Python 3.11+ and a browser. In the repository root:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8766
```

Visit **http://127.0.0.1:8766/seed**. No install, API key, model file or GPU is
needed. The loopback-only server ends after 900 seconds. To use another port,
replace 8766 in both the command and URL.

## A first teaching session

1. Enter `move dax left`. Any valid invented word works. Seed reports an unknown
   concept; it has no preinstalled definition of *dax*.
2. Enter the same word in **Teach with evidence**. For this walkthrough, decide
   that it means **blue and small**. In scene 0 select **o4**, then **Teach YES**.
3. Answer each generated question YES exactly when the example is blue and small;
   otherwise NO. Cards may be examples outside the displayed scene. Seed lists
   consistent grammar meanings, not invented confidence percentages.
4. Switch to **Different scene 1**. Enter `move dax left then move o1 down`.
   A resolved program executes and reports its actual trace. If meanings or
   referents remain ambiguous, teach more examples or use an object ID.

The intended demo rule is supplied to **you**, not to the learner. The separate
explicit-definition panel assigns a supplied predicate; that is not discovery.

## Keep and correct knowledge

- **Inspect** shows evidence, versions, hypotheses, events and costs.
- **Save** writes a new private JSON revision under `runs/seed-sessions/`.
- Stop Python with Ctrl+C. Restart with the same directory and command, then
  choose **Resume saved** in the same browser. The browser remembers the saved
  ID/hash; the server stores the actual evidence.
- **Correct** appends the opposite label for a selected current evidence record.
  It does not erase the original. Inspect the revision, then Save again.
- **Stop** prevents actions; **Continue session** resumes them explicitly.
- **New session** starts independent knowledge without deleting saved sessions.
- **Export JSON** downloads a typed snapshot. Arbitrary executable imports are
  unsupported. Keep private exports and session files out of Git.

Changing browser profiles or clearing browser storage loses the saved-ID shortcut,
not the server's files. Keep the ID/hash from the save response. The local API
can load those identifiers; a cross-device session-management UI is not implemented.

## Supported language

`move [the] WORD left|right|up|down [N]`; join up to eight clauses with `then`.
Also: `inspect`, `look`, `help`, `stop`. Use IDs such as `o1` to disambiguate.
Other conversation returns unsupported instead of a fabricated answer.

The authored 6×6 world has color, shape and size. Objects may share cells; there
is no learned collision physics. Programs allow at most 128 primitive moves and
a two-second cooperative request cap. The grammar has 37 predicates, depth ≤3.

## Troubleshooting

- **Seed not enabled:** restart with `--allow-seed`.
- **Port busy:** choose another port; do not stop another user's server.
- **Session stopped:** choose Continue session; evidence is retained.
- **Contradiction:** inspect and correct labels. Your intended meaning may also
  be outside the finite grammar; Seed must expose that limitation.
- **Blocked move:** stay inside the grid.
- **Session missing:** retain the original snapshot directory. Browser storage
  alone does not contain evidence; do not recreate revisions by hand.

Continue with [architecture](ARCHITECTURE.md), [results](../NEXUS_SEED_RESULTS.md)
or the [documentation hub](../README.md). The historical Lab at `/` is read-only
replay, not a live scientific backend.
