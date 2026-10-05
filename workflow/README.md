# Runtime workflow

The control-plane state machine is:

```text
literature_scan -> relevance_screen -> experiment_card -> approval
-> baseline -> pilot -> full -> multi_seed -> analysis -> report -> archive
-> cleanup
```

`labctl` is the executable local layer and `workflow/gate.py` is its small
control-plane entry point. The gate derives the next permitted stage from the
ledger; it does not accept a model recommendation as human approval. A run is
only accepted when the runner has a structured metric, a successful integrity
receipt, and a recorded artifact directory.

No cloud provider is assumed. `server create/destroy` currently manages a
local lifecycle record and intentionally refuses to imply that a remote GPU
was provisioned. A provider adapter can be added later behind the same card
and ledger contract.

## Control-plane commands

```bash
PYTHONPATH=. python3 -m labctl workflow status --experiment nanochat-rtx4060-b16
python3 workflow/gate.py next --experiment nanochat-rtx4060-b16
python3 workflow/gate.py validate --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl summary weekly
```

The runner refuses to skip a required baseline, pilot, full, or multi-seed
stage. After a candidate is discarded, the same card stops at
`candidate_rejected`; revise or create a new card before spending more runs.
Runs also require a clean worktree on an `autoresearch/` branch. This keeps the
commit recorded in the integrity receipt attributable to the executed code and
prevents pre-existing protected-file edits from being mistaken for a clean
experiment.
