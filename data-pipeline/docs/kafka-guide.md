# Kafka Guide

## 1. Topic 规划建议

| Topic | 用途 | 分区建议 | 保留策略 |
|---|---|---|---|
| `user_behavior_events` | 用户行为主事件流 | 6 | 7 天 |
| `rag_raw_documents` | 原始文档事件 | 3 | 14 天 |
| `rag_processed_chunks` | 清洗分块后数据 | 3 | 14 天 |
| `cdc_user_profile` | 用户画像 CDC 数据 | 3 | 7 天 |
| `app_logs` | 应用日志流 | 3 | 3 天 |
| `cdc.public.user_profile` | Debezium 输出 Topic | 3 | 7 天 |
| `realtime_stats_metrics` | Flink 实时统计指标流 | 3 | 7 天 |
| `dlq_realtime_stats` | 统计作业脏数据 DLQ | 3 | 7 天 |
| `anomaly_alerts` | CEP 异常检测告警流 | 3 | 7 天 |

## 2. 分区键策略

- 行为事件：`user_id`（保持单用户事件有序）
- 文档事件：`doc_id`（保持文档处理有序）
- CDC 事件：主键 ID（保证行级顺序）

## 3. 生产端建议

- `acks=all` 保证写入可靠性
- `retries>=3` 避免瞬时网络抖动
- `linger.ms` 小幅批量发送提升吞吐

## 4. 消费端建议

- Flink 消费组与业务隔离（不同任务不同 group）
- 避免多个异构任务共享同一个 group id
- 对关键 Topic 开启消费延迟监控（lag）

## 5. 运维建议

- 使用 `create-topics.sh` 统一初始化 Topic
- Kafka Connect 内部 Topic（`_connect_*`）必须使用 `cleanup.policy=compact`
- 把 Topic 配置纳入版本管理
- 定期检查 ISR、Under Replicated Partitions、Lag 指标
- 引入 Schema Registry 并使用 `register_schemas.py` 自动注册契约
- 多租户场景启用 `TOPIC_NAMESPACE`，配合 `tenant_id` 做双层隔离
