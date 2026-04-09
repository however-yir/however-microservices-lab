# 性能基线说明

本仓库提供性能基线模板脚本：

```bash
./scripts/perf/generate_baseline_report.sh reports/performance/baseline-latest.md
```

建议每次发布前记录以下指标：

1. `loadgenerator` 总请求数与错误率  
2. `shoppingassistantservice` 请求耗时分位（p50/p95/p99）  
3. 资源占用（CPU/内存）  
4. 关键依赖耗时（Ollama/AlloyDB）

推荐把每次基线报告提交到 `reports/performance/` 目录，并与变更单关联。
