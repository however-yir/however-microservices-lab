# ADR-001: 选择 Apache Flink 作为主要流处理引擎

## 状态
已采纳

## 背景
项目需要一个流处理引擎来处理实时用户行为事件的窗口聚合、异常检测和 RAG 数据增强。候选方案包括 Apache Flink 和 Apache Spark Structured Streaming。

## 决策
采用 Apache Flink 作为主要流处理引擎，Spark Structured Streaming 保留为降级备选方案。

## 原因
1. **真正的事件时间处理**：Flink 原生支持 event time 和 watermark，Spark 的事件时间支持是后加的，处理逻辑更复杂
2. **低延迟**：Flink 的逐条处理模型（record-at-a-time）比 Spark 的微批处理（micro-batch）延迟更低
3. **Exactly-Once 语义**：Flink 的 checkpoint 机制提供端到端 exactly-once，Spark Structured Streaming 的 exactly-once 需要更多手动配置
4. **CEP 支持**：Flink CEP 库原生支持复杂事件模式匹配，用于异常检测场景
5. **状态管理**：Flink 的 RocksDB state backend 支持超大状态量，适合 UV 统计等有状态计算

## 后果
- 开发团队需要学习 Flink API（DataStream API、CEP API）
- Flink 部署模式（standalone/K8s Native）需要额外运维能力
- Spark 作为降级方案需要额外维护一个 fallback job

## 替代方案
- Apache Spark Structured Streaming：延迟较高（秒级），CEP 能力弱
- Apache Kafka Streams：仅限 JVM，无 Python 支持，不适合混合语言团队
