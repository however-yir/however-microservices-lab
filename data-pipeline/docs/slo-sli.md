# SLO / SLI Baseline

本文定义平台的首版可靠性目标与可观测指标，便于迭代期统一验收口径。

## 1. SLI 指标

1. `ingestion_success_rate`：摄取成功率
- 定义：`1 - parse_failures / (events + parse_failures)`
- PromQL：

```promql
100 * (1 - (sum(increase(rdp_event_parse_failures_total[10m])) / clamp_min(sum(increase(rdp_events_total[10m])) + sum(increase(rdp_event_parse_failures_total[10m])), 1)))
```

2. `pipeline_latency_p95`：端到端延迟 P95
- 定义：从事件 `event_time` 到 exporter 采集时刻的延迟分位
- PromQL：

```promql
histogram_quantile(0.95, sum(rate(rdp_pipeline_latency_seconds_bucket[5m])) by (le))
```

3. `critical_alert_recovery_time`：关键告警恢复时间
- 定义：critical 告警持续 firing 的时长
- 观测：`ALERTS{alertstate="firing", severity="critical"}`

## 2. SLO 目标

- 摄取成功率（10 分钟窗口）：`>= 99.0%`
- 端到端延迟 P95（5 分钟窗口）：`<= 5s`
- 关键告警恢复时间：`<= 15m`

## 3. 告警映射

- `IngestionSuccessRateLow`
- `PipelineLatencyP95High`
- `CriticalAlertRecoverySlow`

规则定义见：`monitoring/alerting/alert_rules.yml`。

## 4. 验证方式

1. 启动平台并持续写入事件流。
2. 使用 `scripts/load_test.py` 压测 5~10 分钟。
3. 在 Grafana `Realtime Business Overview` 查看：
- Ingestion Success Rate (10m)
- Pipeline Latency P95 (s)
- Active Alerts
