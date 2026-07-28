# 单应用多模块架构

## 决策

HRP 自研能力统一放入 `ione_hrp` 一个 Frappe App。Frappe、ERPNext 和 Frappe HR 仍是独立上游依赖。业务边界使用 Frappe Module、Python 包、领域服务、权限和事件隔离，而不是拆成九个自研 App。

## 为什么采用一个 App

- 一次安装、一次迁移、一次版本发布，降低医院项目交付复杂度。
- DocType Link、Workflow、Workspace、报表和权限可在同一 App 内原子升级。
- Codex 可以按模块工作，同时共享统一基础服务。
- 避免九个自研 App 的依赖环、安装顺序、版本矩阵和跨 App Patch 管理。

## 边界约束

一个 App 不等于无边界。必须遵守：

1. 模块 DocType 位于对应模块包。
2. 跨模块调用通过公开 service facade 或领域事件。
3. 禁止模块直接导入另一模块的私有 `doctype` 控制器。
4. 基础能力向业务模块单向依赖；业务模块不得反向污染基础层。
5. 财务和库存过账仍委托 ERPNext 标准单据控制器。
6. 人事、薪资和考勤标准能力优先复用 Frappe HR。

## 目录模式

```text
pyproject.toml
architecture/
└── module_registry.yaml
ione_hrp/
├── hooks.py
├── modules.txt
├── common/
├── services/
├── integrations/
├── setup/
├── api/v1/
├── hrp_foundation/
├── hrp_budget/
├── hrp_procurement/
└── ...
```

仓库根目录即 Frappe App 根目录，使 Press 可以直接克隆、审核、构建和更新。

## 模块新增流程

1. 在 Bench 中运行 `bench ione-hrp-create-module ... --yes`，或在开发包根目录运行 `scripts/create_module.py`。
2. 审查 `modules.txt`、模块包和 `module_registry.yaml`。
3. 在模块目录中创建标准 DocType/Report/Page/Workspace。
4. 运行 `bench --site <site> migrate`；`after_migrate` 会补齐 Module Def 与 HRP Module Setting。
5. 提交代码、迁移、权限、测试和文档。

生产界面只允许启停已发布模块，不允许生成源代码模块。
