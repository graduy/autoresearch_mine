# autoresearch-lab

`autoresearch-lab` is the local execution layer for a sustainable autonomous
research loop. It combines the fixed evaluation discipline of Karpathy's
autoresearch with a budgeted funnel, an append-only experiment ledger, code
scope checks, integrity receipts, and evidence-grounded report generation.

The project deliberately keeps the experiment runner independent from any LLM
provider. An agent may propose a hypothesis or patch, but the runner owns the
metric, timeout, artifact capture, acceptance rule, and stop conditions.

## Design boundaries

- `prepare.py`, the data manifest, and the evaluator are protected inputs.
- Each experiment is represented by a versioned JSON card.
- A local user request can authorize a local run; cloud provisioning still
  requires an explicit approval record.
- Pilot results are for selection. Paper claims require a locked commit,
  multi-seed evidence, and an independent test when the project has one.
- Missing evidence becomes `TBD`; the report generator never invents metrics.
- New managed cards use a human-gated research-to-paper workflow: the
  reference paper is reproduced first, then one recent method is substituted
  under the same protocol as a controlled extension; the workflow does not
  assume that this guarantees publication. The package also requires an
  eligible SCI/SCIE journal baseline paper in Chinese Academy of Sciences
  major-category 1 or 2 (impact factor > 4), its baseline and
  experiment scheme, the final-scheme comparison table, innovation direction,
  compute estimate, architecture draft and verification/ablation matrix are
  shown for human review before training; exact resources are supplied by the
  human reviewer.
- After experiments, the human reviewer checks the evidence snapshot and
  approves the conclusion wording before the Chinese and English first drafts
  are generated.

## First adapter

The first adapter targets the pinned local checkout at
`/home/grady/.codex/local-repos/autoresearch`. It preserves the upstream
`train.py` metric (`val_bpb`) and records the current host's RTX 4060 Laptop
8 GB limitation separately from upstream H100-comparable runs.

## CLI

```bash
python -m labctl card validate --card experiments/cards/nanochat-local.json
python -m labctl approval record --experiment nanochat-local --decision approve --source user_request
python -m labctl run --experiment nanochat-local --stage baseline --seed 42
python -m labctl ledger show
python -m labctl report draft --experiment nanochat-local
python -m labctl workflow status --experiment nanochat-local
python -m labctl summary weekly
python -m labctl pipeline status --experiment nanochat-local
python -m labctl analysis run --experiment nanochat-local
python -m labctl pipeline package --experiment nanochat-local
```

The command contract is intentionally plain Python and SQLite so the runner is
usable before a cloud provider, tracking SaaS, or LLM API is configured.

The executable workflow gate is `workflow/gate.py`. It derives the next
permitted stage from the ledger and blocks stage skipping. `multi_seed` is
stability evidence: each declared seed must finish with a valid metric, but a
seed does not need to beat the best seed. The weekly summary is generated from
ledger rows and keeps absent evidence as `TBD`.

Execution requires a clean worktree on an `autoresearch/` branch. A candidate
must be committed before it can be run so the integrity receipt identifies the
exact code state.

The integrated handoff is documented in `workflow/INTEGRATED_PIPELINE.md`.
`pipeline package` writes an evidence manifest, statistical analysis, manuscript
input, PPT brief, and boss update under `deliverables/<experiment_id>/`. These
are generated from the same ledger. Human-gated cards additionally receive
`paper_draft_zh.md` and `paper_draft_en.md` only after conclusion review. The
gate contract is documented in `workflow/RESEARCH_TO_PAPER_GATES.md`.

## forautoresearch archive

The separate local archive at `/home/grady/forautoresearch` keeps literature,
innovation proposals, per-task code snapshots, runs, results, papers, figures,
and presentations under one auditable task ID. It is intentionally separate
from the upstream code checkout and from any synced ChatGPT project files.

```bash
PYTHONPATH=. python3 -m labctl storage init
PYTHONPATH=. python3 -m labctl storage task create \
  --title "Autoresearch innovation" --slug autoresearch-innovation
PYTHONPATH=. python3 -m labctl storage audit
```

New tasks start as `proposed`. A task must contain registered references, a
reviewed compute budget, a bound experiment card, and a direct user approval
record before the managed runner can execute it. `storage code add` records an
independent checkout and commit snapshot; it refuses weights, datasets,
credentials, and unsafe symlinks. Use `storage sync-run` after an approved run
to copy logs and receipts into the task archive without overwriting earlier
evidence. The detailed layout and naming rules are in
`docs/STORAGE_ARCHITECTURE.md` and the archive's `NAMING_RULES.md`.
