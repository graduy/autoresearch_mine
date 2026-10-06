# Runtime workflow

For new managed work, the control-plane state machine is:

```text
literature_scan -> innovation_package -> human_innovation_review
-> human_compute_allocation -> human_approval
-> baseline -> pilot -> full -> multi_seed -> analysis
-> conclusion_review -> paper_draft -> archive -> cleanup
```

`labctl` is the executable local layer and `workflow/gate.py` is its small
control-plane entry point. The gate derives the next permitted stage from the
ledger; it does not accept a model recommendation as human approval. A run is
only accepted when the runner has a structured metric, a successful integrity
receipt, and a recorded artifact directory.

`innovation_package` must contain the literature synthesis, one concrete
innovation direction, an estimated compute budget, a source-grounded
architecture specification and reviewable raster draft, and an experiment
matrix with both `verification` and `ablation` rows. The next two states are
separate human gates. The innovation review records the human edit, reviewed
file hashes and source user message. The compute allocation records exact GPU,
VRAM, GPU-hour, runtime, run-count and cost limits.

After the experiment stages finish, `conclusion_review` requires the human to
check the evidence snapshot and provide the exact approved Chinese and English
conclusion text. Only then does `pipeline package` generate the bilingual
first drafts.

`server create/destroy` currently manages a local lifecycle record and
intentionally refuses to imply that a remote GPU was provisioned. A provider
adapter can be added later behind the same card and ledger contract.

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

The full contract and JSON records are in
`workflow/RESEARCH_TO_PAPER_GATES.md`. Cards created through
`labctl storage bind-card` receive this mode automatically. Existing cards are
listed in `config/research_policy.json` as historical compatibility records;
they are not retroactively presented as having passed the new gates.
