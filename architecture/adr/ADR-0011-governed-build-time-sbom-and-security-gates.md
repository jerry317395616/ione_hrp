---
id: ADR-0011
title: 在站点外生成SBOM并执行固定版本安全门禁
status: Accepted
date: 2026-07-30
deciders:
  - 产品负责人
  - 架构负责人
task_ids:
  - COD-016
supersedes: []
superseded_by:
---

# ADR-0011 在站点外生成SBOM并执行固定版本安全门禁

## 背景与问题

`ione_hrp` 同时依赖锁定的 Frappe、ERPNext、Frappe HR，以及 Python 和 Node
工具链。仅依赖人工检查无法回答某次提交包含哪些组件、是否存在已知漏洞、Git
历史是否泄漏凭据、源码是否包含高风险模式，以及制品是否可追溯。

安全扫描若在 Frappe Web 请求、后台任务或 Press 生产站点内执行，会扩大站点权限，
占用业务 worker，并可能把 Git 历史、文件路径和原始发现写入数据库或日志。

## 决策驱动因素

- SBOM 必须确定、可验证，并包含 `ione_hrp` 与三个锁定上游组件。
- 扫描工具版本和二进制 SHA-256 必须固定。
- 每个未批准的秘密、高危漏洞和拒绝许可证必须阻止合并。
- 安全例外必须精确、限期、有原因和批准人，不能使用宽泛正则。
- 原始扫描报告不得上传、提交 Git 或写入 Frappe Site。
- CI 只使用 `contents: read`，不读取仓库 Secret 或生产凭据。
- 不创建第二个自研 App，不修改 Frappe、ERPNext 或 Frappe HR。

## 备选方案

1. 在 Frappe 后台任务中扫描：操作直观，但把源码扫描能力和原始发现带入生产站点。
2. 仅使用托管平台默认扫描：维护少，但工具版本、SBOM 构成和失败阈值不可完全控制。
3. 只生成 SBOM，不设置合并门禁：便于盘点，但不能阻止已知高风险变更。
4. 源码化策略、固定工具、站点外 CI 扫描、脱敏制品和只读站点契约。

## 决策

采用方案 4。

CI `Security` 作业在完整 Git 历史上执行：

- Bandit 静态安全分析；
- Gitleaks 历史秘密扫描；
- pip-audit 与 npm audit 依赖漏洞扫描；
- npm 原生 CycloneDX SBOM 生成；
- `ione_hrp`、锁定上游和 Python 组件的确定性合成；
- CycloneDX CLI 1.7 校验；
- Grype 对最终 SBOM 的漏洞和许可证分析。

工具版本、Linux 资产和 SHA-256 由
`ione_hrp/config/software_supply_chain.json` 固定。最终仅上传
`ione_hrp.cdx.json`、`security-summary.json` 和 `SHA256SUMS`，原始报告留在
CI 临时工作区。

`PLT-019` 仅允许系统管理角色读取脱敏治理契约。站点端不提供扫描、SBOM 生成、
报告上传或结果写入接口。

## 后果

每个 PR 增加一个可并行执行的安全作业和少量下载时间，Grype 首次下载数据库时耗时
更明显。换来的是确定性 SBOM、可复核工具身份、统一失败阈值和合并前阻断。

供应链策略变更本身属于受保护治理变更，必须经过新的 COD、变更记录和评审。

## 验证与退出条件

- 单元测试覆盖严格策略解析、确定性 SBOM、路径隔离、环境白名单和每个失败门禁。
- 锁定 Bench 集成测试覆盖角色先行、异常映射、无写入、脱敏审计和真实 HTTP。
- 仓库契约强制 `PLT-019` GET-only、站点外执行、工具固定和精确例外。
- CI 必须通过 Quality、Security、Integration 和 Required。
- CycloneDX CLI 必须验证最终 SBOM 为 1.7。

若后续改用签名构建服务或集中安全平台，新 ADR 可以替代具体执行器，但必须保留
相同的组件身份、门禁、例外、脱敏和站点隔离语义。

## 迁移与回滚

本决策不新增 DocType、表、Fixture、Patch 或 Workspace。常规 `bench migrate`
不产生数据变化。

回滚时恢复应用提交和 CI 配置，删除 CI 制品即可；Site 数据库无安全扫描记录需要
迁移或删除。已发布的 Git、PR 和 CI 审计历史不回写。

## 安全与合规

子进程环境使用白名单，不继承 Token、密码、索引凭据或工具覆盖变量。二进制先校验
SHA-256 再执行。SBOM 不包含个人信息、本地绝对路径、凭据或站点数据。

唯一历史 Gitleaks 例外使用完整提交、文件、规则和行号指纹，并在策略中记录到期日、
原因和批准人。例外到期时，即使当前没有发现，门禁也失败，迫使维护者复核。
