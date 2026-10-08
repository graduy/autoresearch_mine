# Research-to-paper human gates

`human_gated_research_to_paper` is the default mode for new cards created by
`labctl storage bind-card`. It controls the path from literature research to a
Chinese and English paper first draft.

Every archive task also copies `workflow/output_protocol.json` to
`manifests/output_protocol.json`. The fixed-output contract and directory map
are documented in `workflow/OUTPUT_PROTOCOL.md`. A new agent must run
`labctl storage status --task <task-id>` first and resume at the first incomplete
output; later files never authorize skipping an earlier stage.

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

- the strategy declaration `reference_first_reproduction_and_whole_system_optimization`:
  reproduce the selected paper's baseline and protocol first, then select
  several complementary methods from the current or previous two publication
  years and combine them into one coherent whole-system candidate. Every
  changed component, source and compatibility reason is recorded. This is a
  controlled optimization based on prior work, not an independent architecture
  claim;
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
- an estimated compute budget with the explicit sentence structure “共有 X 个
  实验需要跑；需要 X 张卡跑 X 小时；推荐租 X 张 <GPU>”. The machine-readable
  fields are checked by the gate;
- a local-code-library record covering a custom scope of at least three CV
  venues and three machine-learning venues from the current and previous two
  publication years. Each selected method must point to a local code path and
  source record;
- a source-grounded architecture specification and reviewable PNG/JPEG/WebP
  draft;
- an `experiment_matrix.json` with both `verification` and `ablation` rows.

Each matrix row names `id`, `category`, `strategy_role`, `experiment_id`,
`stage`, unique integer `seeds`, `hypothesis`, `control`, `change`, `metric` and
`pass_rule`. `strategy_role` is `reference_reproduction`, `recent_optimization`
or `ablation`. The reproduction row must run at `baseline`; the optimization
row must run after that baseline stage. The card
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

GPU selection is task-specific. `config/gpu_catalog.json` records the current
user-provided rental list; the selected model is written into the proposal and
human allocation. The workflow does not assume a fixed RTX 4060 card.

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
  "research_strategy": "reference_first_reproduction_and_whole_system_optimization",
  "publication_positioning": "reproduction_plus_whole_system_optimization",
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
  "reference_reproduction": {
    "protocol_lock": "<what is copied exactly from the reference paper>",
    "allowed_deviations": "<only environment deviations and their reason>",
    "acceptance_rule": "<predeclared reproduction tolerance>",
    "source_location": "<paper methods and experiment sections>"
  },
  "recent_optimization": {
    "optimization_scope": "whole_system",
    "selected_methods": ["<method A>", "<method B>"],
    "method_sources": ["<paper/code source A>", "<paper/code source B>"],
    "publication_years": [2025, 2026],
    "changed_components": ["<component A>", "<component B>"],
    "coherence_rationale": "<why the selected methods form one coherent scheme>",
    "source_location": "<recent papers, local code records and optimization plan>"
  },
  "local_code_library": {
    "root": "<local code library root>",
    "lookback_years": 2,
    "scope_basis": "<why these venue scopes were selected>",
    "cv_venue_scope": ["<CV venue 1>", "<CV venue 2>", "<CV venue 3>"],
    "ml_venue_scope": ["<ML venue 1>", "<ML venue 2>", "<ML venue 3>"],
    "records": [{
      "venue": "<venue>", "year": 2025, "method": "<method>",
      "code_path": "<path in local library>", "source_location": "<record>"
    }]
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
  "candidate_selection": {
    "status": "candidate_best_under_recorded_evidence",
    "basis": "<why this whole-system candidate is preferred under the recorded comparison>",
    "alternatives_considered": ["<reference only>", "<other candidate>"]
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

The publication position is recorded as a reproduction plus controlled whole-
system optimization. The workflow may prepare a paper draft only after the
reference protocol is reproduced, the selected recent methods are evaluated as
one coherent candidate under the same data/evaluator, and the ablation and
multi-seed evidence support the claim. “Current possibly best” is a candidate
selection under the recorded evidence, not a measured global optimum. This
workflow does not promise acceptance or publication.

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

The proposal budget must also make the rental decision readable without
recomputing it:

```json
{
  "estimated_gpu_hours": 24,
  "estimated_runs": 3,
  "assumptions": "Each experiment uses the locked data and evaluator.",
  "schedule_basis": "Each matrix row and seed has a declared GPU count and duration.",
  "run_estimates": [
    {"row_id": "V1", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "baseline reproduction estimate"},
    {"row_id": "V2", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "whole-system optimization estimate"},
    {"row_id": "A1", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "ablation estimate"}
  ],
  "budget_summary": {
    "total_experiments": 3,
    "gpu_type": "<GPU model>",
    "required_gpu_count": 4,
    "wall_clock_hours": 6,
    "recommended_gpu_count": 4,
    "recommended_hours": 6,
    "recommended_rental": "推荐租4张<GPU model>，运行6小时"
  }
}
```

The sentence means: 3 experiments in total, 4 GPUs required for 6 hours,
and the recommended rental is 4 GPUs of the declared model for 6 hours. The
`run_estimates` must enumerate every matrix row and seed, and its GPU-hours
must sum to `estimated_gpu_hours`. The numbers are a plan until the human
reviewer supplies the exact allocation.

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
