# Scientific figure audit

Audit date: 2026-10-05. This review follows the Sivia scientific-figure
audit workflow and uses the saved design specification plus fresh PNG renders.

## Evidence used

- Claim and node/edge ledger: `docs/figures/design_spec.json`.
- Vector sources: `figures/autoresearch-architecture.svg`,
  `figures/experiment-funnel.svg`, and `figures/pilot-result.svg`.
- Rendered review images: the matching PNG files in `figures/`.
- Implementation evidence: `labctl/runner.py`, `labctl/ledger.py`, and
  `labctl/integrity.py`.
- Result data source: `docs/figures/pilot_result_spec.json` and the two
  referenced ledger run IDs.

## Findings

| Gate | Result | Evidence and boundary |
|---|---|---|
| Scientific claim fidelity | Pass for the stated figure roles | The architecture figures show the implemented evidence, approval, preflight, runner, ledger, and report stages. The separate result figure reports only the two ledger-bound pilot values and does not assert a causal performance gain. |
| Reading order and hierarchy | Pass | The architecture uses a left-to-right process spine and a lower feedback loop; the funnel separates idea, smoke, verification, full run, independent test, and paper claim. |
| Connector semantics | Pass | Solid arrows encode process, dashed arrows encode reviewed feedback, and dotted arrows encode artifact binding, matching the design specification. |
| Text and layout | Pass for current raster review | Fresh 1800 px renders were inspected. Labels are readable at the supplied review size and no clipping or connector overlap was found. |
| Data truthfulness | Pass | The only empirical chart is the ledger-bound two-run pilot comparison; no fabricated metric, feature map, or unlabeled SOTA comparison is present. Missing evidence is explicitly shown as `TBD`. |
| Pilot result data binding | Pass with explicit boundary | The result chart reads the two recorded `val_bpb` values and labels itself as a single-seed exploratory pilot; it does not imply statistical significance or generalization. |
| Vector editability | Pass as source-level editability | SVG sources are retained. Native PowerPoint or draw.io object editability has not been produced or tested. |
| Publication-size proof | Pending | A final journal column width, font policy, and target renderer were not supplied. The figures remain reviewable vector/raster drafts. |

## Required follow-up before publication

1. Re-render at the target paper width and verify minimum text size in the
   actual submission template.
2. If a native editable deliverable is required, reconstruct the approved
   figure in the requested PowerPoint or draw.io backend and re-audit it.
3. Add further aggregate result plots only after valid multi-seed or
   independent-test records exist in the ledger. The current OOM runs cannot
   supply those plots.

The audit therefore approves the three files for architecture review,
workflow documentation, and exploratory pilot reporting. It does not certify
them as final publication figures or certify a modeling improvement claim.
