# 美妍伊人医院 HRP V4.0 — Frappe v17 单应用多模块开发包

本包把原先的九个自研 Frappe App 合并为一个应用：`ione_hrp`。所有医院 HRP 业务能力通过 **36 个标准 Frappe Module** 组织，并共享同一套安装、版本、权限、事件、接口、测试和发布生命周期。仓库的默认分支为 `main`，治理规则见 `architecture/repository_governance.md`。

## 源码基线

- Frappe：`frappe/frappe@883224ff626c4635a58c47133f1ba6101cdbd938`
- ERPNext：`frappe/erpnext@372dff2ffa232f54595f48c2639d828c4a64ddde`
- Frappe HR：`frappe/hrms@2d9e4a0bc7a8d18c42c25cc7ff95eb52b460c6b1`
- 三个提交均解析自官方 `develop`，版本标识均为 `17.0.0-dev`
- Python：`>=3.10,<3.15`（兼容当前 Press v17 运行时）
- 默认数据库：MariaDB

`develop` 是滚动/nightly 源码，不能直接作为可重复部署基线。
`resolved_versions.lock.json` 是唯一机器权威；初始化脚本即使从 `develop`
克隆，也会在创建 Site 前切换到锁定 SHA 并验证远程地址、版本、工作树和
提交。更新基线必须单独提交锁文件、完成隔离 Bench 迁移测试，再经 PR 推广，
禁止部署时自动改写锁文件。

## 核心目录

```text
pyproject.toml                  Press/Frappe 应用元数据
ione_hrp/                       单一 Frappe 应用源码
architecture/                 单应用架构、模块注册表和版本策略
design/                       398 个 DocType 与字段等机器可读设计
doctype_blueprints/           按模块重组的 398 份 DocType 蓝图
api/ workflows/ backlog/      API、工作流和 Codex 任务
scripts/                      初始化、安装、加模块、版本锁定和校验脚本
AGENTS.md                      Codex 仓库级强制规则
```

## 非生产环境

```bash
cp .env.example .env
# 修改 .env 中两个密码
set -a && source .env && set +a
python scripts/environment_manager.py validate
python scripts/environment_manager.py plan development
python scripts/environment_manager.py provision development
```

仓库内置彼此隔离的 `development`、`test`、`demo` 三种配置档。它们分别使用
独立 Bench、Site、数据库和服务端口，默认只允许合成数据，并关闭外部集成和
邮件。测试和演示环境还关闭调度器；演示环境禁止测试接口。完整创建、验证、
审计、演示初始化和回滚方法见 `architecture/environments.md`。

## Fixtures 治理

Fixture 只用于 `ione_hrp` 对标准 Frappe/ERPNext/HRMS 对象的受控配置扩展。
当前白名单为模块归属的 Custom Field、Property Setter，以及四个 HRP 核心角色
归属的 Custom DocPerm。导出前先运行：

```bash
python scripts/fixture_manager.py plan
python scripts/fixture_manager.py validate
```

实际导出只允许受管理的 development Site，经显式 `--yes` 后连续导出两次并
校验确定性；生产、测试和演示 Site 均拒绝。完整白名单、敏感数据限制、审计、
升级和回滚规则见 `architecture/fixtures.md`。

## ADR 与变更治理

Git 中的 ADR 和结构化 COD 变更记录是工程治理的唯一权威。每个已完成任务
必须有 `changes/COD-XXX.json`；单应用边界、权限、上游基线、治理门禁和所有
破坏性变更必须关联 Accepted ADR。提交前运行：

```bash
python scripts/change_manager.py validate
python scripts/change_manager.py plan --base-ref origin/main --task COD-XXX
python scripts/change_manager.py check \
  --base-ref origin/main \
  --task COD-XXX \
  --correlation-id COD-XXX-local
```

CI 会对 Pull Request 的 base commit 和 `main` 推送的 before commit 执行相同
差异检查。Frappe 仅提供管理员只读、脱敏的治理状态 API，没有 HTTP 写入口。
ADR 状态机、风险门禁、审计与回滚规则见
`architecture/change_governance.md`。

## 统一异常与错误码

所有 `ione_hrp` 模块通过 `ione_hrp.services.errors` 抛出受控异常，不直接调用
`frappe.throw`。`ione_hrp/config/error_catalog.json` 定义稳定的
`IONE-CORE-xxxx` 机器码、HTTP 状态、重试语义和日志级别；英文源消息通过
标准 `ione_hrp/translations/zh.csv` 提供中文。错误响应包含安全的
`ione_error` 摘要、`X-Ione-Error-Code` 与随机 `X-Ione-Error-ID`，不包含
原因消息、堆栈、路径或业务载荷。

管理员可只读查询错误目录：

```text
GET /api/method/ione_hrp.api.v1.errors.get_error_catalog
```

错误目录没有 HTTP 写入口，也不创建 DocType 或站点数据。命名、兼容、安全、
开发用法与回滚规则见 `architecture/errors.md`。

安装到已有非生产 Bench：

```bash
BENCH_DIR=/path/to/frappe-bench SITE_NAME=hrp.localhost \
  ./scripts/install_into_existing_bench.sh
```

只验证已有 Bench，不安装应用：

```bash
python scripts/version_lock.py --bench /path/to/frappe-bench
```

查看锁定提交是否仍是官方 `develop` 当前头部（只用于基线刷新评估，不是日常
部署门禁）：

```bash
python scripts/version_lock.py --verify-remote-heads
```

新增代码模块（应用安装进 Bench 后）：

```bash
cd /path/to/frappe-bench
bench ione-hrp-create-module   --name "HRP Medical Insurance"   --group "Finance"   --label-cn "医保运营"   --description "医保目录、结算、拒付和申诉管理"   --yes
bench --site hrp.localhost migrate
```

也可在开发包根目录运行 `python3 scripts/create_module.py ...`。

注意：模块是版本控制中的代码结构，不允许普通业务用户在生产界面任意创建。应用内的 `HRP Module Setting` 只控制模块启用状态，不生成 Python 源码。

## 仓库契约

提交前必须运行：

```bash
python scripts/repository_contract.py
python scripts/change_manager.py validate
python scripts/validate_package.py
python scripts/checksums.py
python -m unittest discover -s tests -p "test_*.py"
```

只允许仓库根目录的 `ione_hrp` 一个自研 App。禁止将 Frappe、ERPNext、Frappe HR
源码复制到本仓库，禁止新建 `ione_hrp_*` 业务 App。

## 开发质量工具

安装锁定的开发工具：

```bash
python -m pip install -e ".[dev]"
npm ci
```

运行统一质量门禁：

```bash
python scripts/quality.py
```

该命令依次执行仓库契约、包校验、Python 编译、Ruff lint/format、仓库单元
测试、校验和、Pyright、ESLint 和 Prettier。工具缺失或任一步失败都会返回
非零状态，不允许静默跳过。只检查 Python 或 Node 工具可分别使用
`--mode python`、`--mode node`。详细规则见
`architecture/quality_tooling.md`。

## 持续集成

Pull Request、`main` 推送和人工运行都会触发 `.github/workflows/ci.yml`：

- `Quality` 执行秘密扫描、统一质量门禁和 Node 依赖漏洞扫描；
- `Integration` 用锁定的 Frappe、ERPNext、Frappe HR 提交创建临时 Bench，
  迁移新站点并运行全部 `ione_hrp` 集成测试；
- `Required` 只在两个作业都成功时通过，并由分支保护要求
  `Required` 检查上下文（GitHub 页面显示为 `CI / Required`）。

CI 使用一次性测试密码且不连接 Press 或生产环境。完整设计、安全边界和本地
复现命令见 `architecture/ci_pipeline.md`。
