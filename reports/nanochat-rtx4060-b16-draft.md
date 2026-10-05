# Hardware-adapted nanochat autoresearch on RTX 4060 Laptop with micro-batch 16: preliminary draft

> This is an evidence-bound draft. It is not a final submission and does not convert hypotheses into claims.

## Abstract

We tested the hypothesis: Reducing only the per-device micro-batch to 16 should make the fixed evaluation chain executable within 8 GB VRAM while preserving the 5-minute optimization budget.

The current ledger contains 2 recorded run(s). The best recorded primary metric is 1.698031.

## Method

The primary metric was `val_bpb` with direction `minimize`. The evaluation script was `prepare.py:evaluate_bpb`.
Protected data and evaluation inputs were checked through an integrity receipt for every run.

## Results

| stage | seed | status | metric | runtime (s) | peak VRAM (MB) |
|---|---:|---|---:|---:|---:|
| baseline | 42 | contested_crash | TBD | 22.015213455000776 | TBD |
| baseline | 42 | keep | 1.698031 | 543.2611020860004 | 6150.2 |

## Innovation boundary

Any improvement is a candidate finding until it is repeated under the same protocol with multiple seeds and, where applicable, an independent test.

## Limitations

- The current draft does not claim cross-hardware comparability.
- Cloud cost is `TBD` unless a provider rate is configured and recorded.
- Unsupported or missing evidence remains `TBD`.
