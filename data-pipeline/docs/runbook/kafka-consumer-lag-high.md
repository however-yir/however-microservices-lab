# Runbook: KafkaConsumerLagHigh

## 告警描述
Kafka consumer group 消费堆积超过阈值，可能导致数据处理延迟。

## 排查步骤

### 1. 确认哪个 consumer group 堆积
```bash
docker exec rdp-kafka kafka-consumer-groups --bootstrap-server kafka:29092 --all-groups --describe
```

### 2. 检查 Flink 任务状态
访问 Flink Web UI (http://localhost:8081)，检查：
- 任务是否正在运行
- 是否有 backpressure
- checkpoint 是否正常

### 3. 检查下游存储
- Elasticsearch: `curl localhost:9200/_cluster/health`
- Qdrant: `curl localhost:6333/healthz`

## 修复方案

### 场景 1：Flink 任务异常
重启异常的 Flink 任务。

### 场景 2：下游存储慢
- 检查 ES 是否需要 forcemerge
- 检查 Qdrant 批量大小是否需要调整

### 场景 3：流量突增
增加 Flink TaskManager 并行度：
```bash
# 在 docker-compose.yml 中增加 taskmanager.numberOfTaskSlots
# 或在 K8s 环境中 scale deployment
```
