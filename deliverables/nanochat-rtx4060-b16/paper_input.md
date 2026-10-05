# Manuscript input: Hardware-adapted nanochat autoresearch on RTX 4060 Laptop with micro-batch 16

> This is a source-grounded manuscript input pack, not a final submission.

## Research question and hypothesis

Reducing only the per-device micro-batch to 16 should make the fixed evaluation chain executable within 8 GB VRAM while preserving the 5-minute optimization budget.

The hypothesis remains a hypothesis until the locked experiment and claim gate are complete.

## Evidence sources

- autoresearch README small-compute guidance: https://github.com/karpathy/autoresearch#platform-support (hardware adaptation guidance)

## Results ledger

- Valid metric-bearing runs: `1`
- Best recorded primary metric: `1.698031`
- Evidence manifest: `/home/grady/agent/autoresearch-lab/deliverables/nanochat-rtx4060-b16/evidence_manifest.json`
- Analysis: `/home/grady/agent/autoresearch-lab/deliverables/nanochat-rtx4060-b16/analysis.md`

## Claim boundary

- Pilot results are selection evidence.
- Multi-seed stability is `TBD` until all declared seeds finish.
- Independent-test evidence is `TBD` unless explicitly recorded in the experiment card.
- Missing checkpoints, data availability records, and supplementary artifacts remain `TBD`.
