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
- a source-backed baseline paper record in `baseline_reference.json`. For a
  journal, the default qualification is SCI/SCIE indexed, Chinese Academy of
  Sciences major-category 1 or 2, and impact factor strictly greater than 4;
  record the publication venue, year, category, metric years, ranking sources
  and verification time;
- the reference paper's adopted baseline and experiment scheme, plus the final
  experiment scheme proposed for this task;
- a comparison table with separate rows for model/baseline, data and split,
  training protocol, evaluation metrics and ablation protocol. This table is
  shown as part of the first `human_innovation_review` payload;
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
    "architecture_draft": "<path>",
    "baseline_reference": "<path to baseline_reference.json>"
  },
  "human_reviews": {
    "innovation": "<path>",
    "compute": "<path>",
    "conclusion": "<path>"
  }
}
```

`baseline_reference.json` uses this structure. The `comparison_table` is a
structured table so the status command can display it directly during the
first human review:

```json
{
  "paper": {
    "title": "<paper title>",
    "venue": "<journal, conference or other publication venue>",
    "venue_type": "journal",
    "year": 2024,
    "publication_source": "<publisher or indexing record>",
    "full_text_source": "<full-text source>",
    "indexing": "SCI or SCIE",
    "indexing_source": "<Web of Science record>",
    "quartile_system": "CAS",
    "quartile_scope": "major",
    "quartile_category": "<category>",
    "sci_quartile": "1 or 2",
    "impact_factor": 5.2,
    "doi": "<doi or url>",
    "quartile_source": "<CAS source>",
    "quartile_year": 2024,
    "impact_factor_source": "<JCR source>",
    "impact_factor_year": 2024,
    "verified_at": "<ISO-8601 with timezone>"
  },
  "reference_baseline": {
    "name": "<baseline name>",
    "model": "<model and backbone>",
    "input_or_sequence": "<input or temporal context>",
    "reported_metrics": ["<metric>"],
    "source_location": "<paper section or table>"
  },
  "reference_experiment_scheme": {
    "dataset": "<dataset>",
    "split": "<split>",
    "training": "<training protocol>",
    "evaluation": "<evaluation protocol>",
    "metrics": ["<metric>"],
    "ablation": "<reported ablation scheme>",
    "source_location": "<paper section or table>"
  },
  "final_experiment_scheme": {
    "method": "<final method>",
    "dataset": "<dataset>",
    "split": "<split>",
    "training": "<training protocol>",
    "evaluation": "<evaluation protocol>",
    "metrics": ["<metric>"],
    "ablation_plan": "<ablation plan>",
    "experiment_matrix_sha256": "<sha256 of current experiment_matrix.json>"
  },
  "comparison_table": [
    {
      "dimension_key": "model_baseline",
      "dimension": "Model/baseline",
      "reference_paper": "<reference description>",
      "final_scheme": "<final scheme description>",
      "decision_or_difference": "<why this is fixed or changed>",
      "source_location": "<paper/plan section>",
      "comparable": true
    }
  ]
}
```

The gate checks the declared sources and fields; it does not independently
authenticate a journal ranking or impact factor. The human reviewer must check
those source records before approving the innovation package. A conference may
be used only through its separate quality record: full/regular paper type,
peer-review evidence, proceedings source and a documented venue-standing
basis. It must not be assigned a journal impact factor or CAS quartile. A
missing, ineligible or incomplete baseline record keeps the workflow at
`human_innovation_review` and prevents compute allocation and execution.

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
  "baseline_eligibility_checked": true,
  "protocol_comparison_checked": true,
  "conference_quality_confirmed": false,
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
