# Helm Deployment

本目录提供 `realtime-data-pipeline` 的 Helm chart（聚焦可观测性组件与 exporter）。

> 说明：Kafka/Flink/Elasticsearch 等重状态组件通常建议使用企业级 chart 或托管服务，本 chart 先覆盖本项目自研 exporter 与指标链路。

## 目录

- `realtime-data-pipeline/Chart.yaml`
- `realtime-data-pipeline/values.yaml`
- `realtime-data-pipeline/templates/*`

## 安装

```bash
helm upgrade --install rdp deploy/helm/realtime-data-pipeline \
  --namespace rdp --create-namespace
```

## 升级

```bash
helm upgrade rdp deploy/helm/realtime-data-pipeline -n rdp
```

## 卸载

```bash
helm uninstall rdp -n rdp
```

## 可配置项

- `streamMetricsExporter.*`
- `connectMonitorExporter.*`
- `resources`
