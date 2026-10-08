# 固定产出与断点续作协议

每个课题目录都必须复制一份 `manifests/output_protocol.json`。新 agent 开始工作时先执行：

```bash
PYTHONPATH=. python3 -m labctl storage status --task AR-YYYYMMDD-NNN-slug
```

返回的 `current_stage` 是第一个缺少固定产出的阶段；agent 只能补这个阶段及其前置缺口，不能因为后面的目录或文件已经存在就跳步。`completed_stages` 是已完成检查点，`skipped_stages` 只表示实验卡没有声明可选阶段，不表示阶段被绕过。

阶段输出通过后，需要显式封存哈希断点：

```bash
PYTHONPATH=. python3 -m labctl storage checkpoint --task <task-id> --stage <stage-id>
```

该命令只接受当前阶段及其前置阶段均已验证的输出，并把输出哈希写入
`manifests/checkpoints/<stage-id>.json`。后续文件或上游产出发生变化时，状态会重新回到对应阶段；保存新版本前会把旧 checkpoint 放入 `manifests/checkpoints/history/`。

课题输出根目录固定为 `/home/grady/forautoresearch/tasks/<task-id>/`：

| 阶段 | 固定产出 | 完成条件 |
|---|---|---|
| `literature_scan` | `manifests/references.json`、`reference/metadata/` | 有登记记录和来源元数据 |
| `relevance_screen` | `plans/relevance_screen.json` | 有 baseline、近两年 venue 范围、本地代码候选和筛选结论 |
| `innovation_package` | `plans/literature_synthesis.md`、`plans/innovation_proposal.md`、`plans/baseline_reference.json`、`plans/compute_budget.json`、`plans/experiment_matrix.json`、`figures/architecture_spec.md`、`figures/drafts/architecture_draft.png` | 研究包完整且通过机器校验 |
| `experiment_card` | `manifests/experiments.json`、`experiments/cards/<experiment>.json` | 实验卡绑定代码和研究包 |
| `human_innovation_review` | `approvals/innovation_review.json` | 用户人工编辑、审核并绑定当前文件哈希 |
| `human_compute_allocation` | `approvals/compute_allocation.json` | 用户给出 GPU、张数、小时、显存、运行次数和费用上限 |
| `human_approval` | `approvals/direction-budget-<hash>.json` | 用户直接批准执行 |
| `provision_server` | `result/training_records/<experiment>-server.json` | 只记录真实服务器生命周期，不能把计划写成已租用 |
| `baseline` | `runs/<experiment>/baseline/<run-id>/integrity_receipt.json` | 参考论文 baseline 完成并有完整性回执 |
| `code_patch` | `manifests/code.json` | 实际执行提交和快照已登记 |
| `pilot`、`full`、`multi_seed` | 对应 `runs/<experiment>/<stage>/<run-id>/integrity_receipt.json` | 仅当实验卡声明该阶段时检查 |
| `analysis` | `result/training_records/<experiment>.json`、`result/evaluations/<experiment>-analysis.json` | 日志和统计分析已冻结 |
| `conclusion_review` | `approvals/conclusion_review.json` | 用户核验结论并提供中英文原文与 run 引用 |
| `paper_draft` | `paper/zh/<task-id>-draft-vN.md`、`paper/en/<task-id>-draft-vN.md` | 只从审核结论生成初稿 |
| `report_draft` | `reports/<task-id>-report-vN.md`、`ppt/briefs/<task-id>-brief-vN.md` | 报告和 PPT 提纲绑定同一证据清单 |
| `archive` | `archive/archive_manifest.json` | 卡片、代码、环境、日志和交付物哈希归档 |
| `cleanup` | `manifests/cleanup_receipt.json` | 只清理明确授权的临时文件并留下回执 |

目录存在不等于阶段完成。JSON 清单必须有记录，目录必须有文件，运行阶段必须有完整性回执。协议只负责判断产出断点；文献资格、人工批准、算力批准和实验结论仍由各自门禁校验。

实验预算也属于固定产出。`plans/compute_budget.json` 必须逐行覆盖实验矩阵的 `row_id + seed`，并生成可直接审核的句子：

> 共有 X 个实验需要跑；需要 X 张 `<GPU>` 跑 X 小时；推荐租 X 张 `<GPU>`，运行 X 小时。

GPU 型号从 `config/gpu_catalog.json` 的当前可用清单中选择，不能把 RTX 4060 写成默认值。用户提供的清单只作为型号范围；库存、价格和最终租用仍以人工审核时的实际记录为准。
