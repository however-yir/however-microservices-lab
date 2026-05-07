# Multi-Tenant Strategy

## 1. 目标

在不牺牲实时性的前提下实现多租户隔离与可观测：

- Topic 级隔离：按 namespace 规划 topic
- 数据级隔离：事件内统一携带 `tenant_id`
- 指标级隔离：Prometheus label 包含 `tenant_id`

## 2. Topic Namespace

默认 topic：

- `user_behavior_events`
- `rag_raw_documents`
- `rag_processed_chunks`

启用 namespace 后：

- `tenantA.user_behavior_events`
- `tenantA.rag_raw_documents`
- `tenantA.rag_processed_chunks`

相关配置：

- 生产端：`TOPIC_NAMESPACE`
- Kafka topic 初始化：`data-storage/kafka-config/create-topics.sh` 中 `TOPIC_NAMESPACE`

## 3. 事件字段规范

业务事件、CDC 与 ETL 数据都要求带：

- `tenant_id`
- `schema_version`

已实现位置：

- `data-collector/api-collector/producer.py`
- `data-collector/api-collector/rag_document_producer.py`
- `data-collector/db-cdc/postgres-connector-config.json`
- `stream-processing/flink-jobs/data-enrich/*`
- `stream-processing/flink-jobs/realtime-stats/*`

## 4. 运行建议

1. 先在单租户跑通，再扩展多 namespace。
2. 每个租户使用独立消费组与告警分组。
3. Grafana 看板默认聚合，可按 `tenant_id` 做二级看板。
