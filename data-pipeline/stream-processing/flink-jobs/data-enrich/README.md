# data-enrich

可运行的 Flink ETL 作业：消费 `rag_raw_documents`，进行文本分块、向量化，并写入 Qdrant。

## 功能

- Kafka Source：`rag_raw_documents`
- Kafka Sink：`rag_processed_chunks`（可关闭）
- 文本分块：固定窗口 + overlap
- 向量化：本地可运行 Hash Embedding（便于无外部模型快速联调）
- 向量化：支持 `simple/http/openai` provider（默认 `simple`）
- Qdrant Sink：批量 upsert，点位 ID 使用 `doc_id#chunk_index` 的稳定 UUID
- Qdrant Sink：失败自动重试（指数退避）

## 构建

```bash
cd stream-processing/flink-jobs/data-enrich
mvn clean test package
```

## 提交运行

```bash
docker cp target/data-enrich-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/data-enrich.jar

docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/data-enrich.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --source.topic rag_raw_documents \
  --source.starting.offsets latest \
  --processed.topic rag_processed_chunks \
  --enable.processed.topic.sink true \
  --qdrant.url http://qdrant:6333 \
  --qdrant.collection rag_documents \
  --qdrant.max.retries 5 \
  --qdrant.retry.base.ms 200 \
  --qdrant.retry.max.ms 5000 \
  --chunk.size 500 \
  --chunk.overlap 80 \
  --embedding.dim 128 \
  --embedding.provider simple
```

## 输入消息示例

```json
{
  "doc_id": "doc-001",
  "source": "api",
  "content": "这是一个用于 RAG 的示例文档内容...",
  "event_time": "2026-04-09T01:00:00Z",
  "metadata": {
    "lang": "zh",
    "domain": "recruitment"
  }
}
```

## 说明

- 示例 embedding 为工程联调用，可替换为真实模型服务（OpenAI/本地 embedding 服务）。
- 建议保持 Qdrant 向量维度与 `embedding.dim` 一致。
- 若仅需写 Qdrant，可使用 `--enable.processed.topic.sink false`。
- OpenAI provider 需设置 `OPENAI_API_KEY` 或参数 `--embedding.openai.api.key`。
