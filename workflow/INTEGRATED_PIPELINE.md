# Integrated autoresearch pipeline

This pipeline joins the existing local autoresearch runner with the verified
paper, figure, presentation and reporting skills. The control plane remains
local and evidence-bound; the named `nature-*` skills in the reference image
are treated as functional roles because their exact `SKILL.md` files are not
installed in this environment.

## End-to-end path

```text
ideation
  -> literature_scan
  -> relevance_screen
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
  -> scientific_figures
  -> manuscript_input
  -> ppt_handoff
  -> boss_update
  -> next_hypothesis
```

`workflow/gate.py` owns the executable experiment order. `labctl/analysis.py`
owns descriptive statistics and refuses to estimate spread from one run.
`labctl/evidence.py` binds runs, receipts, artifacts, commits and protocol
fields. `labctl/deliver.py` creates the manuscript, presentation and progress
handoffs from the same manifest.

## Skill routing

- Use `daily-papers` and `paper-reader` for literature discovery and evidence
  extraction.
- Use the experiment card for the question, hypothesis, source papers,
  baseline, budget, seeds and stop rule.
- Use `autoresearch-lab` for code, approval, baseline, pilot, full and
  multi-seed execution.
- Use Sivia for new scientific schematics and audits. Use standard plotting
  code for real experimental data.
- Use `ppt-master` for the editable deck. Its input is `ppt_brief.md` plus the
  evidence manifest; Sivia supplies approved scientific figures when needed.
- Use the manuscript input and claim ledger as the source for writing,
  polishing, reviewer simulation and response drafting.

## Commands

```bash
PYTHONPATH=. python3 -m labctl pipeline status --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl analysis run --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl analysis manifest --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl pipeline package --experiment nanochat-rtx4060-b16
PYTHONPATH=. python3 -m labctl summary weekly
```

The package command does not manufacture a paper claim or PPT result. It
creates evidence-bound handoffs and leaves `TBD` where the experiment has not
produced the required evidence.
