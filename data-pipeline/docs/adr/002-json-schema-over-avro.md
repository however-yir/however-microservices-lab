# ADR-002: 选择 JSON Schema 而非 Avro 作为序列化格式

## 状态
已采纳

## 背景
Kafka 消息需要 Schema 管理。Confluent Schema Registry 支持 Avro、JSON Schema 和 Protobuf 三种格式。

## 决策
使用 JSON Schema 作为 Kafka 消息的主要序列化格式。

## 原因
1. **开发效率**：JSON 可读性好，调试方便，无需额外的编译步骤
2. **Python 兼容**：Producer 是 Python 实现，JSON 原生支持，Avro 需要额外的 fastavro 库
3. **多语言支持**：Java Flink job 和 Python producer 都能轻松处理 JSON
4. **RAG 场景**：RAG 文档天然使用 JSON 格式，无需格式转换
5. **Schema Registry 兼容**：Confluent Schema Registry 对 JSON Schema 的支持已成熟

## 后果
- JSON 比 Avro 体积大约 30-50%，带宽消耗更高
- 缺少 Avro 的 schema evolution 的强类型保证
- 需要在性能敏感场景评估是否切换到 Avro/Protobuf

## 替代方案
- Avro：体积小、schema evolution 好，但 Python 支持差、不可读
- Protobuf：性能好、schema evolution 好，但需要编译 .proto 文件、可读性差
