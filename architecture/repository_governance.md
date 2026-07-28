# ione_hrp 仓库与分支治理

## 范围

本仓库是医院 HRP 的唯一 mono-repo，也是可被 Press 直接克隆的标准 Frappe
App 仓库。自研代码只能位于根目录的 `ione_hrp` Python 包，业务边界使用
该 App 内部的 Frappe Module 和
Python 包表达。`frappe`、`erpnext`、`hrms` 是锁定提交的上游依赖，不纳入
本仓库，也不得修改其核心源码。

## 分支模型

- `main` 是唯一长期分支和可发布基线。
- 所有变更从短期任务分支发起，格式为 `cod/COD-XXX-short-name`。
- `main` 禁止直接推送、强制推送和删除。
- 合并必须使用 Pull Request，保持线性历史并解决全部评审讨论。
- 至少一名 CODEOWNER 批准；新提交会使旧批准失效。

`.github/branch-protection.json` 是机器可读的保护策略；GitHub 中的实际规则
必须与该文件保持一致。仓库管理员也受同一规则约束。

当前 GitHub 仓库为私有仓库，GitHub Free 对分支保护 API 返回 HTTP 403。
在升级 GitHub Pro 或明确批准公开仓库之前，策略文件只表示期望状态，不能
声明远端规则已经生效。禁止为了通过验证而擅自公开仓库。

COD-005 建立 CI 流水线后，再把对应状态检查加入分支保护。本任务不提前实现
COD-005。

## 单应用边界

1. 只允许仓库根目录的 `ione_hrp` 一个自研 App。
2. 新业务域登记到 `architecture/module_registry.yaml` 和
   `ione_hrp/modules.txt`，并创建对应模块包。
3. 禁止创建 `ione_hrp_budget`、`ione_hrp_supply` 等独立 App。
4. 跨模块调用通过公开 service facade 或领域事件。
5. 禁止直接写 `GL Entry`、`Stock Ledger Entry`、`Bin`。
6. 标准业务过账必须调用 ERPNext/Frappe HR 标准控制器。

## 变更流程

1. 从 backlog 选择一个未完成的 `COD-XXX`，一次只处理一个任务。
2. 在任务分支完成模型、服务、权限、API、测试、迁移和文档中适用的部分。
3. 运行：

   ```bash
   python scripts/repository_contract.py
   python scripts/validate_package.py
   python scripts/checksums.py
   python -m unittest discover -s tests -p "test_*.py"
   ```

4. 使用 PR 模板记录设计依据、测试证据、迁移影响和回滚方法。
5. 合并后由锁定提交构建 Press Bench；生产站点只执行经过备份验证的迁移。

Press 不支持从 Git 仓库子目录加载 App，因此 `pyproject.toml` 必须位于仓库
根目录，且 `ione_hrp/hooks.py` 必须可被 Press 的 App Source 直接发现。

## COD-001 适用性说明

COD-001 是仓库治理任务，不新增业务 DocType、写 API、Workspace、Fixture 或
数据库迁移，因此模型、服务、权限和业务幂等不适用。异常路径由仓库契约测试
覆盖，包括多 App、旧前缀、弱化分支保护和受保护台账写入模式。
