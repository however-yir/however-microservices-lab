#!/usr/bin/env bash
set -euo pipefail

OUT_FILE="${1:-reports/performance/baseline-latest.md}"
DATE="$(date '+%Y-%m-%d %H:%M:%S %z')"

mkdir -p "$(dirname "${OUT_FILE}")"

cat > "${OUT_FILE}" <<EOF
# 性能基线报告（自动生成）

- 生成时间: ${DATE}
- 测试入口: loadgenerator 日志聚合
- 目标: 记录每次改造后的吞吐、错误率与关键接口延迟

## 指标模板

| 指标 | 数值 | 备注 |
|---|---:|---|
| 总请求数 | 待填充 | 从 loadgenerator 日志提取 |
| 错误数 | 待填充 | 从 loadgenerator 日志提取 |
| 错误率 | 待填充 | 错误数 / 总请求数 |
| p50 延迟 | 待填充 | 建议接入 Prometheus |
| p95 延迟 | 待填充 | 建议接入 Prometheus |
| p99 延迟 | 待填充 | 建议接入 Prometheus |

## 结论模板

1. 与上次基线相比，吞吐变化：待填充
2. 与上次基线相比，错误率变化：待填充
3. 主要瓶颈：待填充
4. 下一步优化项：待填充
EOF

echo "Performance baseline template generated at ${OUT_FILE}"
