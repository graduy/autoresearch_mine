# Sustainable operation runbook

This runbook is the smallest repeatable operating procedure for the local
single-GPU adapter. It is designed to stop safely when evidence, compute, or
scope is invalid.

## Before an experiment

1. Read `docs/OSS_AUDIT.md` and the relevant candidate record.
2. Create or revise an experiment card under `experiments/cards/`.
3. Record the primary metric, direction, protected evaluator, code-change
   boundary, time budget, VRAM budget, declared seeds, and stop rule.
4. Record an approval in the ledger:

   ```bash
   PYTHONPATH=. python3 -m labctl approval record \
     --experiment nanochat-rtx4060 --decision approve \
     --source user_request --actor codex
   ```
5. Keep the code checkout clean and on an `autoresearch/` branch. Commit the
   candidate in `train.py` before running it; the runner records that commit in
   the integrity receipt.

## Execution order

Run the same seed for the baseline and pilot. Do not change the evaluator,
data, or time budget between them.

```bash
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage baseline --seed 42
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage pilot --seed 42
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage full --seed 42
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage multi_seed --seed 17
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage multi_seed --seed 42
PYTHONPATH=. python3 -m labctl run --experiment nanochat-rtx4060 --stage multi_seed --seed 3407
```

The runner performs a GPU exclusivity check before starting, unsets the
configured SOCKS proxy variables that broke the first download attempt, saves
stdout/stderr, extracts only declared metrics, checks protected hashes and
changed paths, and records the result in SQLite. A busy GPU, crash, integrity
failure, budget violation, or missing metric is a stopping signal.

## Evidence decisions

- `baseline` establishes the reference and is never a paper improvement claim.
- `pilot` selects or rejects a candidate under the paired seed.
- `full` repeats a selected candidate at the declared budget.
- `multi_seed` estimates stability; it is not an independent test.
- A paper number must point to a ledger row, its logs, its integrity receipt,
  and the exact code commit.

If the device is occupied by another user process, wait for that process to
finish. Do not kill it or reinterpret a contended OOM as a capacity result.
If a cloud backend is added later, it must implement the same receipts and
approval boundary; the current `server` command only records a local lifecycle
file and is not a cloud provider adapter.

## Review and archive

```bash
PYTHONPATH=. python3 -m labctl ledger show --experiment nanochat-rtx4060
PYTHONPATH=. python3 -m labctl report draft --experiment nanochat-rtx4060
PYTHONPATH=. python3 -m labctl archive --experiment nanochat-rtx4060
```

Regenerate the report after every evidence boundary. Keep `TBD` when the
ledger has no valid value. Archive only after the experiment card, code
snapshot, environment record, run records, and figure/report drafts are
present.
