# 部署蓝图

生产建议采用 Frappe v17 develop 高可用拓扑：Ingress/Nginx → 多 Web/Gunicorn 实例；独立短队列、默认队列和长队列 worker；独立 scheduler；Redis cache/queue/socketio；MariaDB 主从或受管高可用；S3/MinIO；集中日志、指标和追踪。

核心交易建议一个医疗集团按数据隔离要求选择：
- 单 Site、多法人/多院区：共享主数据与集团分析最便利，需严格行级权限和容量治理；
- 多 Site、集团数据平台：隔离更强，通过主数据中心、事件和数据仓库汇总；
- 不建议在第一期把每个领域拆成独立微服务。Frappe App 是代码边界，Site 内事务是核心一致性边界。

环境至少包括 local、CI、dev、SIT、UAT、preprod、prod、DR。配置和秘密不得进入 Git；使用 Vault/KMS/Secret Manager。生产发布采用不可变镜像、数据库备份、迁移预演、滚动发布和自动回滚闸门。
