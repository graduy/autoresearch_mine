# Open-source component audit

Audit date: 2026-10-05. The repositories below were cloned at shallow depth
into `/home/grady/agent/oss-audit` and inspected at the recorded commit. The
selection is based on reusable behavior, license, test evidence, and fit for a
single-GPU research loop. It is not a claim that every public repository was
searched exhaustively.

| Repository | Commit | License | Reusable part | Decision |
|---|---|---|---|---|
| [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | local pinned `228791fb...` | MIT | fixed evaluator, 5-minute loop, one-file change boundary, `val_bpb` | use as the first experiment adapter |
| [renee-jia/scholar-loop](https://github.com/renee-jia/scholar-loop) | `f3f9d47...` | MIT | frozen scoring, smoke/verify/full funnel, append-only ledger, governor, calibration | implement equivalent behavior in stdlib/SQLite |
| [a0merr/autolab](https://github.com/a0merr/autolab) | `c4be39c...` | MIT | versioned run store, replay, guard, plugin interface, unattended stop conditions | use as runner and replay design reference |
| [EvoMap/AutoResearch](https://github.com/EvoMap/AutoResearch) | `21f5912...` | Apache-2.0 | provenance, recoverable state, role contracts, manifest and secret scans | use provenance and preflight patterns; do not copy provider-specific runtime blindly |
| [OpenNSWM-Lab/FAROS](https://github.com/OpenNSWM-Lab/FAROS) | `4e4e96f...` | inspect before redistribution | PlanPackage, evidence-first claims, human gates, ReviewX | use conceptual control-plane pattern; license requires separate review |
| [AutoResearch-Factory/Agon](https://github.com/AutoResearch-Factory/Agon) | `7572044...` | MIT | experiment auditor/reviewer, pilot/result validation, paper and figure workflow prompts | use review boundaries and figure claim checks |
| [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | `96bd516...` | AI Scientist Source Code License | idea generation, tree search, plotting and writeup pipeline | conceptual reference only; do not vendor code without a license decision |

Additional infrastructure references were checked from their official
documentation: [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)
for parameters/metrics/artifacts, [DVC](https://dvc.org/doc/user-guide) for
data and pipeline versioning, and [Optuna](https://github.com/optuna/optuna)
for constrained search and pruning. We keep the first implementation
dependency-free and local-first; these tools are optional adapters for a later
scale-out phase, not hidden runtime requirements.

The resulting framework is intentionally a composition of behaviors rather than
a copied multi-agent runtime. The authoritative implementation is the code in
`labctl/`; external repositories remain audit material.
