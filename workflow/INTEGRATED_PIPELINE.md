# Integrated autoresearch pipeline

This pipeline joins the local autoresearch runner with the evidence-bound
literature, figure, presentation and reporting handoffs. The control plane
remains local and evidence-bound.

## End-to-end path

```text
ideation
  -> literature_scan
  -> innovation_package
  -> human_innovation_review
  -> human_compute_allocation
  -> experiment_card
  -> human_approval
  -> provision_server
  -> baseline
  -> code_patch
  -> code_review
  -> pilot
  -> full
  -> multi_seed
  -> statistical_analysis
  -> evidence_manifest
  -> conclusion_review
  -> paper_draft_zh
  -> paper_draft_en
  -> scientific_figures
  -> ppt_handoff
  -> boss_update
  -> next_hypothesis
```

`workflow/gate.py` owns the executable experiment order. The human-gated
contract is implemented in `labctl/research_gate.py`; it checks the innovation
package, review hashes, exact compute allocation, experiment-matrix completion
and the evidence snapshot used for conclusion review. `labctl/analysis.py`
owns descriptive statistics and refuses to estimate spread from one run.
`labctl/evidence.py` binds runs, receipts, artifacts, commits and protocol
fields. `labctl/deliver.py` creates the manuscript, presentation and progress
handoffs from the same manifest.

## Skill routing

- Use `daily-papers` and `paper-reader` for literature discovery and evidence
  extraction.
- Use the experiment card for the question, hypothesis, source papers,
  baseline, budget, seeds and stop rule.
- Use the research package for the literature synthesis, innovation direction,
  architecture draft and verification/ablation matrix. The package is edited
  and approved by a human before execution.
- Use `autoresearch-lab` for code, approval, baseline, pilot, full and
  multi-seed execution.
- Use Sivia for new scientific schematics and audits. Use standard plotting
  code for real experimental data.
- Use `ppt-master` for the editable deck. Its input is `ppt_brief.md` plus the
  evidence manifest; Sivia supplies approved scientific figures when needed.
- Use the human-approved conclusion record, manuscript input and claim ledger
  as the source for Chinese/English writing, polishing, reviewer simulation and
  response drafting.

## Commands

```bash
PYTHONPATH=. python3 -m labctl pipeline status --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl analysis run --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl analysis manifest --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl pipeline package --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl summary weekly
```

For a new human-gated card, the package command creates evidence-bound
handoffs and writes the exact human-approved conclusion text into
`paper_draft_zh.md` and `paper_draft_en.md` only after conclusion review. It
never turns a prediction into an experimental result.
