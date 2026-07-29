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

## 首次使用

```bash
cp .env.example .env
# 修改 .env 中密码及目录
set -a && source .env && set +a
./scripts/bootstrap_latest_develop.sh
```

已有 Bench：

```bash
BENCH_DIR=/path/to/frappe-bench SITE_NAME=hrp.localhost   ./scripts/install_into_existing_bench.sh
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
python scripts/validate_package.py
python scripts/checksums.py
python -m unittest discover -s tests -p "test_*.py"
```

只允许仓库根目录的 `ione_hrp` 一个自研 App。禁止将 Frappe、ERPNext、Frappe HR
源码复制到本仓库，禁止新建 `ione_hrp_*` 业务 App。
