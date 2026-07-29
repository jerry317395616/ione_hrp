# HRP Foundation

**领域组：** Core

**中文名称：** 基础平台

系统设置、模块注册、特性开关、公共字典、编号、规则与通用能力。

工程 ADR 和变更记录以 Git 为唯一权威。基础平台通过
`ione_hrp.services.change_governance` 提供管理员只读的脱敏治理状态；没有
站点内写入、审批或状态转换入口。规则见
`architecture/change_governance.md`。
