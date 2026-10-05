# Evidence analysis: Hardware-adapted nanochat autoresearch on RTX 4060 Laptop with micro-batch 16

Primary metric: `val_bpb` (minimize); protocol: `hardware-adapted/local protocol`.

This is a ledger-derived analysis. It does not convert a pilot result into a general claim.

## Runs

| stage | seed | status | metric | runtime (s) | peak VRAM (MB) | run id |
|---|---:|---|---:|---:|---:|---|
| baseline | 42 | contested_crash | TBD | 22.015213455000776 | TBD | `nanochat-rtx4060-b16-baseline-42-af269448` |
| baseline | 42 | keep | 1.698031 | 543.2611020860004 | 6150.2 | `nanochat-rtx4060-b16-baseline-42-555c4a52` |

## Paired comparisons

| run | stage | metric | reference | delta | improves |
|---|---|---:|---:|---:|---|

## Multi-seed statistics

- n: `0`
- mean: `TBD`
- standard deviation: `TBD`
- bootstrap 95% interval: `TBD`
- boundary: TBD: no valid metric

## Claim gate

- `locked_code_commit`: `True`
- `multi_seed`: `False`
- `independent_test`: `False`
- `statistics`: `False`

Paper claim ready: **False**.
Independent test: **TBD**.
