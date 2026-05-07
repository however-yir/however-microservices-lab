# Flink Tutorial

## 1. 实时作业核心概念

### 1.1 Event Time

事件发生时间，来自业务字段 `event_time`，用于保证窗口计算逻辑正确。

### 1.2 Watermark

用于表达“系统认为不会再有更早事件到达”的进度线，解决乱序问题。

### 1.3 Window

将无限流切成可计算的时间片，本项目示例使用 1 分钟滚动窗口。

## 2. 示例作业说明

`stream-processing/flink-jobs/realtime-stats` 任务完成：

- 按 `event_type` 统计分钟级 PV
- 按 `user_id` 去重统计分钟级 UV
- 输出窗口指标到 Kafka `realtime_stats_metrics`
- 解析异常消息写入 `dlq_realtime_stats`

`stream-processing/flink-jobs/data-enrich` 任务完成：

- 消费 `rag_raw_documents`
- 文本分块（chunk + overlap）
- 本地 embedding 向量化
- 输出 `rag_processed_chunks`（可供下游任务复用）
- 批量 upsert 到 Qdrant
- Qdrant sink 支持指数退避重试
- 可选接入真实 Embedding 服务（OpenAI/HTTP）

`stream-processing/flink-jobs/anomaly-detect` 任务完成：

- Flink CEP 识别行为序列 `view -> add_to_cart -> purchase`
- 输出告警到 Kafka `anomaly_alerts`

## 3. Exactly-Once 配置

关键设置如下：

- `enableCheckpointing(10000, EXACTLY_ONCE)`
- 使用持久化 checkpoint 存储
- Kafka Source 保证 offset 与状态快照一致

## 4. 常见问题排查

### 4.1 作业无法消费数据

- 检查 Kafka 地址是否使用容器内地址 `kafka:29092`
- 检查 Topic 是否已创建
- 检查 Consumer Group 是否被其他任务占用

### 4.2 窗口无输出

- 检查 `event_time` 是否可解析为 ISO-8601 时间
- 检查水印策略是否过严
- 检查事件是否持续输入

### 4.3 checkpoint 失败

- 检查 checkpoint 路径权限
- 检查 TaskManager 内存配置
- 检查状态大小是否超过限制

## 5. 从样例到生产

建议按以下顺序演进：

1. 控制台 print sink 验证逻辑
2. 切换到 Elasticsearch/Kafka sink
3. 引入 CEP 与 Side Output
4. 引入状态 TTL 与回压监控
