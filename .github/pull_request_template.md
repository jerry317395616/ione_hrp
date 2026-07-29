## 任务

- COD 编号：
- 设计依据：
- ADR 编号（无则说明原因）：
- 变更记录：`changes/COD-XXX.json`
- 风险等级：
- 破坏性变更：是 / 否

## 变更

- 模块与 DocType：
- 服务、权限与 API：
- Fixtures、Patch 与文档：

## 验证

- [ ] `python scripts/repository_contract.py`
- [ ] `python scripts/change_manager.py validate`
- [ ] `python scripts/change_manager.py check --base-ref origin/main --task COD-XXX`
- [ ] `python scripts/validate_package.py`
- [ ] 相关单元、集成、权限及异常路径测试已通过
- [ ] 未修改 Frappe、ERPNext、Frappe HR 核心源码
- [ ] 未直接写入 GL Entry、Stock Ledger Entry 或 Bin

## 发布

- 数据迁移影响：
- 回滚方法：
- 权限与安全影响：
- 接口样例或截图：
- 未决事项：
