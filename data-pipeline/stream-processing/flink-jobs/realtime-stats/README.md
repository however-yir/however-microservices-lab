# realtime-stats

Flink 实时统计任务，消费 `user_behavior_events`，输出 PV/UV/转化率窗口指标到 `realtime_stats_metrics`。

## 本地构建

```bash
cd stream-processing/flink-jobs/realtime-stats
mvn clean package -DskipTests
```

## 提交到 Flink 集群

```bash
docker cp target/realtime-stats-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/realtime-stats.jar
docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/realtime-stats.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --source.topic user_behavior_events \
  --metrics.topic realtime_stats_metrics \
  --dlq.topic dlq_realtime_stats
```

## 技术点

- 事件时间 + 水印（乱序容忍 5 秒）
- 分钟级窗口聚合
- Checkpoint + Exactly-Once 语义
- 统一日志字段：`job_name/topic/partition/offset/schema_version`
- 脏数据 DLQ：`dlq_realtime_stats`
