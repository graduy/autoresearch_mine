# Runtime workflow

For new managed work, the control-plane state machine is:

```text
literature_scan -> relevance_screen -> innovation_package -> experiment_card
-> human_innovation_review -> human_compute_allocation -> human_approval
-> baseline -> pilot -> full -> multi_seed -> analysis
-> conclusion_review -> paper_draft -> archive -> cleanup
```

`labctl` is the executable local layer and `workflow/gate.py` is its small
control-plane entry point. The gate derives the next permitted stage from the
ledger; it does not accept a model recommendation as human approval. A run is
only accepted when the runner has a structured metric, a successful integrity
receipt, and a recorded artifact directory.

`innovation_package` must contain the literature synthesis, one concrete
innovation direction, an eligible SCI/SCIE journal baseline paper in Chinese
Academy of Sciences major-category 1 or 2 with impact factor strictly greater
than 4, the paper's baseline and experiment scheme, a
structured comparison table against the final scheme, an estimated compute
budget, a source-grounded architecture specification and reviewable raster
draft, and an experiment matrix with both `verification` and `ablation` rows.
Its core strategy is reference-first reproduction: reproduce the paper's
baseline and protocol, then select several complementary methods from a custom
two-year scope covering at least three CV venues, three machine-learning
venues, and the local code library. Combine them into one coherent whole-system
candidate and record every changed component. It does not claim a global
optimum or guarantee publication.
The comparison table is included in the first human-review payload. The next
two states are separate human gates. The innovation review records the human
edit, reviewed file hashes and source user message. The compute allocation records exact GPU,
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

The default three-CV/three-ML discovery scope is in
`config/research_sources.json`; topic cards may customize it with a recorded
basis and local implementation paths.

The GPU catalog supplied for current rental planning is in
`config/gpu_catalog.json`. The budget records the selected model, required
parallel cards, wall-clock hours and recommended rental; the model is selected
per task rather than fixed to RTX 4060.

The fixed-output checkpoint contract is in `workflow/OUTPUT_PROTOCOL.md` and
`workflow/output_protocol.json`. A new agent resumes with
`labctl storage status --task <task-id>`; it continues from the first incomplete
output and leaves later stages untouched. After a stage is fully validated, it
seals the hash-bound checkpoint with
`labctl storage checkpoint --task <task-id> --stage <stage-id>`.
