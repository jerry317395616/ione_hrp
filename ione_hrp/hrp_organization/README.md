# HRP Organization

**领域组：** Core

**中文名称：** 组织管理

医疗集团、法人、医院、院区、科室、护理单元、病区和岗位组织模型。

## 当前实现

COD-018 交付医院、组织版本和组织单元三个标准 DocType。每个版本保存一所医院的完整
Nested Set 组织树，整树通过领域服务原子替换，发布后不可变，并支持按生效日期查询。

组织版本和节点在 Desk 中只读；`System Manager`、`HRP System Manager` 和
`HRP Data Steward` 通过受控 API 管理。ERPNext `Department` 和 `Cost Center` 映射由
COD-019 交付。
