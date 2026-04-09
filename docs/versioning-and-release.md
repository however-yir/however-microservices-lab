# 版本与发布策略

## 语义化版本

仓库采用 SemVer：

- `vMAJOR.MINOR.PATCH`
- 预发布：`vMAJOR.MINOR.PATCH-rc1` / `-beta1` / `-alpha1`

规则：

1. 破坏性变更提升 `MAJOR`。  
2. 向后兼容功能提升 `MINOR`。  
3. 兼容性修复提升 `PATCH`。  

## Tag 校验

已启用 GitHub Actions：`semver-tag-ci.yaml`。  
不符合语义化规则的 Tag 会直接失败，避免错误版本进入发布链路。

## 发布前检查

1. 所有质量工作流通过。  
2. Changelog 已更新。  
3. SBOM 已生成并归档。  
4. 性能基线已对比并记录。  
