# Research-to-paper human gates

`human_gated_research_to_paper` is the default mode for new cards created by
`labctl storage bind-card`. It controls the path from literature research to a
Chinese and English paper first draft.

## Required order

```text
literature_scan
  -> innovation_package
  -> human_innovation_review
  -> human_compute_allocation
  -> human_approval
  -> baseline -> pilot -> full -> multi_seed
  -> analysis
  -> conclusion_review
  -> paper_draft
  -> archive
```

A card may omit pilot or full for a deliberately smaller experiment, but the
remaining stages keep their order. `innovation_package` must include:

- a literature synthesis and one concrete innovation direction;
- an estimated compute budget;
- a source-grounded architecture specification and reviewable PNG/JPEG/WebP
  draft;
- an `experiment_matrix.json` with both `verification` and `ablation` rows.

Each matrix row names `id`, `category`, `experiment_id`, `stage`, unique integer
`seeds`, `hypothesis`, `control`, `change`, `metric` and `pass_rule`. The card
named by `experiment_id` must exist, declare the row's stage and use the same
primary metric. An ablation row also names the removed or replaced `component`.
This binds the validity check and ablation to executable cards rather than to a
free-form plan.

The innovation review is a human edit and review gate. It requires
`human_reviewed=true`, `human_edited=true`, a non-empty edit summary, the user
actor, the source thread, the user's review text, the current package hashes
and the current card hash. A file that only says “approved” cannot pass.

The compute allocation is a separate human gate. It records the exact GPU
type, GPU count, VRAM, GPU-hour limit, run limit, per-run time limit, VRAM
limit and cost limit. It binds to the innovation-review hash. The runner uses
the stricter value when both the card and allocation specify a limit. No run or
server record is admitted while this gate is missing, incomplete, stale or
contains a placeholder.

After the declared experiment rows finish, the workflow stops at
`conclusion_review`. The human checks the current evidence snapshot and writes
the exact approved Chinese and English conclusion text with run references.
`pipeline package` copies those approved sentences into
`paper_draft_zh.md` and `paper_draft_en.md`; it does not invent a conclusion
before review.

## Card paths

A managed card uses absolute paths so the experiment runner in the GitHub
checkout can read the evidence archive in `/home/grady/forautoresearch`:

```json
{
  "workflow_mode": "human_gated_research_to_paper",
  "research_package": {
    "literature_synthesis": "<path>",
    "innovation_proposal": "<path>",
    "compute_budget": "<path>",
    "experiment_matrix": "<path>",
    "architecture_spec": "<path>",
    "architecture_draft": "<path>"
  },
  "human_reviews": {
    "innovation": "<path>",
    "compute": "<path>",
    "conclusion": "<path>"
  }
}
```

## Review records

Innovation review:

```json
{
  "decision": "approve",
  "human_reviewed": true,
  "human_edited": true,
  "actor": "user",
  "reviewer": "<human>",
  "reviewed_at": "<ISO-8601 with timezone>",
  "source_thread_id": "<thread>",
  "user_quote": "<user's review text>",
  "edit_summary": "<what changed>",
  "package_sha256": {"<package field>": "<sha256>"},
  "card_sha256": "<sha256>"
}
```

Compute allocation:

```json
{
  "decision": "approve",
  "human_reviewed": true,
  "actor": "user",
  "reviewer": "<human>",
  "reviewed_at": "<ISO-8601 with timezone>",
  "source_thread_id": "<thread>",
  "user_quote": "<user's allocation text>",
  "allocation_basis": "<resource source or reservation>",
  "innovation_review_sha256": "<sha256>",
  "gpu_type": "<exact model>", "gpu_count": 1, "vram_gb": 8,
  "max_gpu_hours": 4, "max_runtime_seconds": 660, "max_runs": 12,
  "max_vram_gb": 8, "max_cost_usd": 0
}
```

Conclusion review:

```json
{
  "decision": "approve",
  "human_reviewed": true,
  "actor": "user",
  "reviewer": "<human>",
  "reviewed_at": "<ISO-8601 with timezone>",
  "source_thread_id": "<thread>",
  "user_quote": "<user's conclusion review text>",
  "evidence_checked": true,
  "claim_scope": "<scope supported by the evidence>",
  "evidence_sha256": "<sha256 of the current evidence snapshot>",
  "approved_conclusions": [{
    "id": "C1",
    "zh": "<human-verified Chinese conclusion>",
    "en": "<human-verified English conclusion>",
    "evidence_refs": ["<ledger run_id>"]
  }]
}
```

Every referenced run must be a completed run with a metric, exit code zero and
an integrity receipt. Placeholder values such as `TBD` and `待定` are rejected.

## Commands

```bash
PYTHONPATH=. python3 -m labctl card validate --card experiments/cards/<experiment>.json
PYTHONPATH=. python3 -m labctl workflow status --experiment <experiment>
PYTHONPATH=. python3 -m labctl workflow validate --experiment <experiment>
PYTHONPATH=. python3 -m labctl pipeline package --experiment <experiment>
```

The status command reports the first unmet gate. `run` and `server create` are
blocked until the research package, both pre-experiment human records and the
ordinary experiment approval are valid. Existing cards are listed in
`config/research_policy.json` as historical compatibility records; they remain
readable but are not described as having passed this new process.
