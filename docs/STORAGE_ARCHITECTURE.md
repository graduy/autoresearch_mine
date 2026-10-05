# forautoresearch 档案架构

`/home/grady/forautoresearch` 是档案和审核层，`/home/grady/agent/autoresearch-lab` 是执行与清单代码，`/home/grady/.codex/local-repos/autoresearch` 是上游实验代码，三者保持分离。

```text
forautoresearch/
├── reference/                 公共文献、笔记、来源元数据、参考代码登记
├── tasks/AR-.../              一个确认候选课题一个目录
│   ├── ideas/ plans/ approvals/
│   ├── code/{baseline,variants,snapshots}/
│   ├── experiments/cards/ runs/ result/
│   ├── paper/{zh,en}/ figures/ ppt/
│   └── manifests/ archive/
├── indexes/                   机器索引与审计入口
└── INDEX.md
```

这套结构借鉴 `SmokeSegmentation` 中 `reference/`、`main/`、`result/`、`papper/`、`output/`、`dispatch/` 的职责分离，但将课题编号、代码版本和审批哈希改为强绑定，避免多个实验共用一个模糊目录。

目录初始化不会搬运 SmokeSegmentation 的代码、数据或权重，也不会修改它；引用项目仅用于结构参考。
