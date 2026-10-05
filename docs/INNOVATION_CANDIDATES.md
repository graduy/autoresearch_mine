# Budgeted candidate list

This list is deliberately conservative. A candidate is an experiment
hypothesis, not a contribution claim.

| Priority | Candidate | Code change | Budget | Boundary |
|---|---|---|---|---|
| 0 | RTX 4060 compatibility | `DEVICE_BATCH_SIZE 128 → 16` after a clean batch-32 OOM | one 5-minute run | hardware adaptation; not a new method and not H100-comparable |
| 1 | Window allocation | `WINDOW_PATTERN SSSL → SLLL` or one pre-registered alternative | one pilot + one confirmatory run | compute-allocation ablation; report as an engineering study unless repeated and theoretically supported |
| 2 | Matrix learning-rate sensitivity | one value around the locked `MATRIX_LR=0.04` | one pilot | hyperparameter sensitivity; no novelty claim without a broader controlled study |
| reject | tokenizer changes | change vocabulary or validation data | unavailable under fixed `prepare.py` | would change the evaluation protocol and invalidate direct comparison |
| reject | TACO-style optimizer transfer | port a fine-tuning optimizer result into pretraining | too large for current budget | source result is not evidence for this pretraining setup; revisit only with a dedicated adapter |

The primary candidate is window allocation because it changes one permitted
line, keeps data and evaluation fixed, and can be tested under the same five
minute budget after a runnable batch-16 baseline exists. The expected gain is a
hypothesis. The outcome can be positive, neutral, slower, or an OOM; all four
are valid evidence if recorded.

The first paired pilot was recorded on 2026-10-05 with seed 42. The batch-16
baseline was `val_bpb=1.698031`; `SLLL` produced `val_bpb=1.715169` in 575.8
seconds with 6150.2 MiB peak VRAM. The runner marked it `discard` and restored
the code to the batch-16 baseline commit. No multi-seed or paper improvement
claim follows from this pilot.
