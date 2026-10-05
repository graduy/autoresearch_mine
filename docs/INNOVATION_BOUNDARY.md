# Innovation boundary and compute policy

The first local GPU is an RTX 4060 Laptop with approximately 8 GiB VRAM while
the upstream autoresearch README describes H100 testing. A clean comparison
must therefore distinguish:

1. upstream-comparable protocol: untouched `train.py` and fixed upstream
   evaluator; the current default run already produced an OOM on this host;
2. hardware-adapted protocol: only the permitted training file changes, with
   a declared micro-batch or model-size change; results are local engineering
   evidence, not H100-comparable research claims;
3. innovation candidate: a controlled change motivated by a cited source or
   an explicit architecture hypothesis, evaluated against the adapted
   baseline under the same data, evaluator, time budget and seeds.

The initial candidate family is intentionally narrow:

- attention-window allocation such as `SSSL` versus one declared alternative;
- optimizer schedule or learning-rate changes only when the hypothesis and
  expected compute effect are recorded before the run;
- model-width/depth changes only as a budget study, never presented as a new
  method without a paired baseline and multi-seed evidence.

Acceptance requires an improvement in `val_bpb` in the same protocol, no
protected-file modification, no unrecorded dependency, and no budget breach.
Pilot results select candidates; full and multi-seed results support a paper
claim. Independent-test results, if the project has them, remain separate from
selection holdout results.

