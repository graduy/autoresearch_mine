# 命名规则

## 课题

`AR-YYYYMMDD-NNN-slug`，例如 `AR-20261005-001-window-allocation`。日期采用 Asia/Shanghai；`NNN` 是当天三位流水号；slug 只用小写字母、数字和单连字符。

## 参考资料

`REF-YYYY-slug`，例如 `REF-2026-autoresearch`。同一年同一 slug 只登记一次；来源 URL、作者、标题、类型、阅读深度和本地文件 SHA-256 必须保存在 `reference/metadata/`。

## 代码

`baseline-slug-<commit12>`、`variant-slug-<commit12>` 或 `reference-slug-<commit12>`。每个记录同时保存独立 checkout、Git 提交、分支名、源文件哈希和 tar.gz 快照；已有代码发生新提交时创建新记录，不改旧目录。

## 实验与交付

实验 ID 必须以小写课题 ID 开头，例如 `ar-20261005-001-window-allocation-baseline-b16`。运行目录由执行器生成唯一 run ID，禁止人工复用。文件建议使用 `YYYYMMDD_<stage>_<seed>_<role>.<ext>`；论文、图和 PPT 以课题为单位放在 `paper/`、`figures/`、`ppt/`，不可把临时文件当最终交付件。

## 状态

`proposed → confirmed → baseline → pilot → full → multi_seed → analysis → report_draft → archive → complete`。`rejected`、`blocked` 和 `historical` 只能由记录说明的人工或证据状态产生；建议、预测收益和文献结果不能写入实测指标字段。
