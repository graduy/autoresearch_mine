# Evidence analysis: Window allocation pilot on RTX 4060 Laptop at micro-batch 16

Primary metric: `val_bpb` (minimize); protocol: `hardware-adapted/local protocol`.

This is a ledger-derived analysis. It does not convert a pilot result into a general claim.

## Runs

| stage | seed | status | metric | runtime (s) | peak VRAM (MB) | run id |
|---|---:|---|---:|---:|---:|---|
| pilot | 42 | discard | 1.715169 | 575.8238819889993 | 6150.2 | `nanochat-window-slll-b16-pilot-42-c8a96451` |

## Paired comparisons

| run | stage | metric | reference | delta | improves |
|---|---|---:|---:|---:|---|
| `nanochat-window-slll-b16-pilot-42-c8a96451` | pilot | 1.715169 | 1.698031 | 0.017137999999999876 | False |

## Multi-seed statistics

- n: `0`
- mean: `TBD`
- standard deviation: `TBD`
- bootstrap 95% interval: `TBD`
- boundary: TBD: no valid metric

## Claim gate

- `locked_code_commit`: `False`
- `multi_seed`: `False`
- `independent_test`: `False`
- `statistics`: `False`

Paper claim ready: **False**.
Independent test: **TBD**.
