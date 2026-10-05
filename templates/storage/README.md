# forautoresearch

这是本地 autoresearch 总档案库。它把文献、候选创新、已确认课题、代码快照、实验证据和交付物分开保存，并用哈希与清单建立引用关系。

总索引在 `INDEX.md`。每个课题位于 `tasks/AR-YYYYMMDD-NNN-slug/`，课题编号一经创建不复用。课题目录存在只表示已登记，不表示方向已获批准或训练已完成。

公共参考资料放在 `reference/`，课题专属资料放在对应课题的 `reference/`。旧的 autoresearch 论文库继续保留为外部来源库；登记到课题时记录来源 URL、阅读深度和本地文件哈希。

当前代码、数据与权重的边界保持分离：代码快照只登记 Git 提交和源文件哈希，不复制数据集、凭据或模型权重。实验运行结果通过 `storage sync-run` 镜像到课题目录；原始日志和完整性回执以实验执行层为准。

使用 `PYTHONPATH=/home/grady/agent/autoresearch-lab python3 -m labctl storage audit` 检查清单。发现哈希变化时创建新版本，禁止覆盖旧证据。
