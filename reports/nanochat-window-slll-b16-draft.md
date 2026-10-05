# Window allocation pilot on RTX 4060 Laptop at micro-batch 16: preliminary draft

> This is an evidence-bound draft. It is not a final submission and does not convert hypotheses into claims.

## Abstract

We tested the hypothesis: Replacing the SSSL attention-window allocation with SLLL may improve validation bits per byte under the same batch-16 hardware-adapted budget.

The current ledger contains 1 recorded run(s). The best recorded primary metric is TBD.
The locked reference metric from `nanochat-rtx4060-b16` is `1.698031`.

## Method

The primary metric was `val_bpb` with direction `minimize`. The evaluation script was `prepare.py:evaluate_bpb`.
Protected data and evaluation inputs were checked through an integrity receipt for every run.

## Results

| stage | seed | status | metric | runtime (s) | peak VRAM (MB) |
|---|---:|---|---:|---:|---:|
| pilot | 42 | discard | 1.715169 | 575.8238819889993 | 6150.2 |

## Innovation boundary

Any improvement is a candidate finding until it is repeated under the same protocol with multiple seeds and, where applicable, an independent test.

## Limitations

- The current draft does not claim cross-hardware comparability.
- Cloud cost is `TBD` unless a provider rate is configured and recorded.
- Unsupported or missing evidence remains `TBD`.
