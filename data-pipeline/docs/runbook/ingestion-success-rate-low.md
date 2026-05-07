# Runbook: IngestionSuccessRateLow

## 告警描述
数据摄取成功率低于 99% SLO，存在大量事件解析失败。

## 排查步骤

### 1. 检查 DLQ 消息
```bash
docker exec rdp-kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic dlq_realtime_stats \
  --from-beginning --max-messages 10
```

### 2. 检查 Schema Registry
```bash
curl http://localhost:8086/subjects
curl http://localhost:8086/subjects/user_behavior_events-value/versions/latest
```

### 3. 检查 Producer 输出
查看 producer 日志，确认发送的 JSON 格式是否正确。

## 修复方案

### 场景 1：Schema 不兼容
修复 producer 输出格式，确保符合注册的 JSON Schema。

### 场景 2：上游数据异常
在 producer 端增加数据校验，过滤异常数据。

### 场景 3：Schema Registry 不可用
```bash
docker restart rdp-schema-registry
```
