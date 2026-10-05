# Autoresearch weekly evidence summary

Window start (Asia/Shanghai): `2026-10-04T00:00:00+08:00`

This summary reports ledger evidence only. Missing values remain `TBD`; hypotheses and literature are not measured results.

## Runs in window

| experiment | stage | seed | status | primary metric | runtime (s) |
|---|---|---:|---|---:|---:|
| nanochat-local | baseline | 42 | crash | TBD | 2.5185208279999642 |
| nanochat-local | baseline | 42 | crash | TBD | 85.47077888199965 |
| nanochat-rtx4060 | baseline | 42 | crash | TBD | 21.359150133001094 |
| nanochat-rtx4060 | baseline | 42 | crash | TBD | 11.64079119499911 |
| nanochat-rtx4060-b16 | baseline | 42 | contested_crash | TBD | 22.015213455000776 |
| nanochat-rtx4060-b16 | baseline | 42 | keep | 1.698031 | 543.2611020860004 |
| nanochat-window-slll-b16 | pilot | 42 | discard | 1.715169 | 575.8238819889993 |

## Current workflow state

| experiment | state | next action | blockers |
|---|---|---|---|
| nanochat-local | baseline | repair or retry baseline after reviewing the recorded failure | none |
| nanochat-rtx4060-b16 | pilot | run pilot | none |
| nanochat-rtx4060 | baseline | repair or retry baseline after reviewing the recorded failure | none |
| nanochat-window-slll-b16 | candidate_rejected | revise the experiment card or create a new candidate before rerunning | pilot produced a discard; the same candidate is not rerun automatically |

## Requires attention

- `nanochat-window-slll-b16` requires action: revise the experiment card or create a new candidate before rerunning.
