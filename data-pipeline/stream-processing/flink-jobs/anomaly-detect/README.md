# anomaly-detect

Flink CEP 异常检测作业，基于行为序列规则识别风险模式。

## 规则

当前内置规则：`view -> add_to_cart -> purchase` 在 10 分钟内连续发生，输出告警事件到 `anomaly_alerts`。

可用于识别：

- 高频刷单行为（可叠加 user/ip 过滤）
- 快速异常转化链路
- 业务行为序列偏移

## 构建

```bash
cd stream-processing/flink-jobs/anomaly-detect
mvn clean package -DskipTests
```

## 提交运行

```bash
docker cp target/anomaly-detect-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/anomaly-detect.jar

docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/anomaly-detect.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --source.topic user_behavior_events \
  --output.topic anomaly_alerts
```

## 告警输出示例

```json
{
  "alert_type": "cep_purchase_funnel",
  "job_name": "anomaly-detect-cep",
  "user_id": "user_42",
  "tenant_id": "tenant_demo",
  "schema_version": "v1",
  "channel": "app",
  "sequence": "view->add_to_cart->purchase",
  "severity": "warning",
  "event_time": "2026-04-09T03:00:00Z"
}
```
