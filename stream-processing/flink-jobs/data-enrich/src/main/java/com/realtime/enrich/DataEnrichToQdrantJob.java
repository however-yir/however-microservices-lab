package com.realtime.enrich;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.Serializable;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.util.Collector;

public class DataEnrichToQdrantJob {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        ParameterTool params = ParameterTool.fromArgs(args);

        String jobName = params.get("job.name", "data-enrich-to-qdrant");
        String defaultSchemaVersion = params.get("schema.version", "v1");
        String defaultTenantId = params.get("tenant.id", "default");

        String kafkaBootstrapServers = params.get("kafka.bootstrap.servers", "kafka:29092");
        String sourceTopic = params.get("source.topic", "rag_raw_documents");
        String groupId = params.get("group.id", "data-enrich-job");
        String sourceStartingOffsets = params.get("source.starting.offsets", "latest");
        String processedTopic = params.get("processed.topic", "rag_processed_chunks");
        boolean enableProcessedTopicSink = params.getBoolean("enable.processed.topic.sink", true);

        String qdrantUrl = params.get("qdrant.url", "http://qdrant:6333");
        String qdrantCollection = params.get("qdrant.collection", "rag_documents");
        int qdrantMaxRetries = params.getInt("qdrant.max.retries", 5);
        long qdrantRetryBaseMs = params.getLong("qdrant.retry.base.ms", 200L);
        long qdrantRetryMaxMs = params.getLong("qdrant.retry.max.ms", 5_000L);

        int chunkSize = params.getInt("chunk.size", 500);
        int chunkOverlap = params.getInt("chunk.overlap", 80);
        int embeddingDim = params.getInt("embedding.dim", 128);
        int sinkBatchSize = params.getInt("sink.batch.size", 32);

        EmbeddingConfig embeddingConfig = EmbeddingConfig.from(params);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(15_000, CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setCheckpointStorage("file:///tmp/flink-checkpoints");

        OffsetsInitializer offsetsInitializer = "earliest".equalsIgnoreCase(sourceStartingOffsets)
                ? OffsetsInitializer.earliest()
                : OffsetsInitializer.latest();

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(kafkaBootstrapServers)
                .setTopics(sourceTopic)
                .setGroupId(groupId)
                .setStartingOffsets(offsetsInitializer)
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        DataStream<ChunkRecord> chunkStream = env
                .fromSource(source, org.apache.flink.api.common.eventtime.WatermarkStrategy.noWatermarks(), "rag-doc-source")
                .map(json -> DocumentEvent.fromJson(json, defaultSchemaVersion, defaultTenantId))
                .returns(DocumentEvent.class)
                .filter(Objects::nonNull)
                .flatMap((DocumentEvent event, Collector<ChunkRecord> out) -> {
                    List<String> chunks = TextChunker.chunk(event.content, chunkSize, chunkOverlap);
                    for (int i = 0; i < chunks.size(); i++) {
                        String chunkText = chunks.get(i);
                        if (chunkText.isBlank()) {
                            continue;
                        }

                        String chunkId = event.docId + "#" + i;
                        String pointId = UUID.nameUUIDFromBytes(chunkId.getBytes(StandardCharsets.UTF_8)).toString();

                        ChunkRecord record = new ChunkRecord();
                        record.pointId = pointId;
                        record.docId = event.docId;
                        record.chunkId = chunkId;
                        record.chunkIndex = i;
                        record.chunkText = chunkText;
                        record.source = event.source;
                        record.eventTime = event.eventTime;
                        record.schemaVersion = event.schemaVersion;
                        record.tenantId = event.tenantId;
                        record.metadata = new HashMap<>(event.metadata);
                        record.metadata.put("chunk_index", i);
                        record.metadata.put("chunk_size", chunkText.length());
                        record.metadata.put("job_name", jobName);
                        record.metadata.put("embedding_provider", embeddingConfig.provider);
                        record.vector = EmbeddingProviders.embed(chunkText, embeddingDim, embeddingConfig);
                        out.collect(record);
                    }
                })
                .returns(ChunkRecord.class)
                .name("chunk-and-vectorize");

        chunkStream
                .addSink(new QdrantSink(
                        qdrantUrl,
                        qdrantCollection,
                        sinkBatchSize,
                        qdrantMaxRetries,
                        qdrantRetryBaseMs,
                        qdrantRetryMaxMs))
                .name("qdrant-upsert-sink");

        if (enableProcessedTopicSink) {
            KafkaSink<String> processedTopicSink = KafkaSink.<String>builder()
                    .setBootstrapServers(kafkaBootstrapServers)
                    .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                            .setTopic(processedTopic)
                            .setValueSerializationSchema(new SimpleStringSchema())
                            .build())
                    .build();

            chunkStream
                    .map(ChunkRecord::toJson)
                    .returns(String.class)
                    .sinkTo(processedTopicSink)
                    .name("processed-topic-sink");
        }

        chunkStream
                .map(record -> String.format(
                        "job=%s tenant=%s schema=%s doc_id=%s chunk_id=%s chunk_index=%d vector_dim=%d",
                        jobName,
                        record.tenantId,
                        record.schemaVersion,
                        record.docId,
                        record.chunkId,
                        record.chunkIndex,
                        record.vector.length))
                .name("chunk-log")
                .print("ENRICH");

        env.execute(jobName);
    }

    public static class EmbeddingConfig implements Serializable {
        public String provider;
        public String httpUrl;
        public String openaiUrl;
        public String openaiModel;
        public String openaiApiKey;
        public int timeoutMs;
        public boolean fallbackToSimple;

        static EmbeddingConfig from(ParameterTool params) {
            EmbeddingConfig config = new EmbeddingConfig();
            config.provider = params.get("embedding.provider", "simple").toLowerCase();
            config.httpUrl = params.get("embedding.http.url", "");
            config.openaiUrl = params.get("embedding.openai.url", "https://api.openai.com/v1/embeddings");
            config.openaiModel = params.get("embedding.openai.model", "text-embedding-3-small");
            config.openaiApiKey = params.get("embedding.openai.api.key", System.getenv("OPENAI_API_KEY") == null ? "" : System.getenv("OPENAI_API_KEY"));
            config.timeoutMs = params.getInt("embedding.timeout.ms", 10_000);
            config.fallbackToSimple = params.getBoolean("embedding.fallback.to.simple", true);
            return config;
        }
    }

    public static class EmbeddingProviders {
        private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();

        static float[] embed(String text, int dim, EmbeddingConfig config) {
            String provider = config == null || config.provider == null ? "simple" : config.provider;
            try {
                if ("openai".equals(provider)) {
                    return openAiEmbedding(text, dim, config);
                }
                if ("http".equals(provider)) {
                    return httpEmbedding(text, dim, config);
                }
                return SimpleEmbedding.embed(text, dim);
            } catch (Exception ex) {
                if (config != null && config.fallbackToSimple) {
                    return SimpleEmbedding.embed(text, dim);
                }
                throw new RuntimeException("embedding_failed provider=" + provider, ex);
            }
        }

        private static float[] httpEmbedding(String text, int dim, EmbeddingConfig config) throws Exception {
            if (config.httpUrl == null || config.httpUrl.isBlank()) {
                throw new IllegalArgumentException("embedding.http.url is required when provider=http");
            }

            ObjectNode body = MAPPER.createObjectNode();
            body.put("input", text);
            body.put("text", text);
            body.put("dim", dim);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(config.httpUrl))
                    .timeout(Duration.ofMillis(config.timeoutMs))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body)))
                    .build();

            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new RuntimeException("http embedding failed status=" + response.statusCode());
            }

            JsonNode root = MAPPER.readTree(response.body());
            JsonNode vectorNode = root.path("embedding");
            if (!vectorNode.isArray() || vectorNode.isEmpty()) {
                vectorNode = root.path("vector");
            }
            if (!vectorNode.isArray() || vectorNode.isEmpty()) {
                throw new RuntimeException("http embedding response missing vector/embedding array");
            }
            return normalizeDimension(vectorNode, dim);
        }

        private static float[] openAiEmbedding(String text, int dim, EmbeddingConfig config) throws Exception {
            if (config.openaiApiKey == null || config.openaiApiKey.isBlank()) {
                throw new IllegalArgumentException("OPENAI_API_KEY or embedding.openai.api.key is required when provider=openai");
            }

            ObjectNode body = MAPPER.createObjectNode();
            body.put("model", config.openaiModel);
            body.put("input", text);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(config.openaiUrl))
                    .timeout(Duration.ofMillis(config.timeoutMs))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + config.openaiApiKey)
                    .POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body)))
                    .build();

            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new RuntimeException("openai embedding failed status=" + response.statusCode() + " body=" + response.body());
            }

            JsonNode root = MAPPER.readTree(response.body());
            JsonNode data = root.path("data");
            if (!data.isArray() || data.isEmpty()) {
                throw new RuntimeException("openai embedding response missing data");
            }
            JsonNode vectorNode = data.get(0).path("embedding");
            if (!vectorNode.isArray() || vectorNode.isEmpty()) {
                throw new RuntimeException("openai embedding response missing embedding");
            }
            return normalizeDimension(vectorNode, dim);
        }

        private static float[] normalizeDimension(JsonNode vectorNode, int dim) {
            int safeDim = Math.max(dim, 16);
            float[] vector = new float[safeDim];
            int length = Math.min(vectorNode.size(), safeDim);
            for (int i = 0; i < length; i++) {
                vector[i] = (float) vectorNode.get(i).asDouble();
            }

            double norm = 0.0;
            for (float v : vector) {
                norm += v * v;
            }
            norm = Math.sqrt(norm);
            if (norm > 0.0) {
                for (int i = 0; i < vector.length; i++) {
                    vector[i] = (float) (vector[i] / norm);
                }
            }
            return vector;
        }
    }

    public static class DocumentEvent implements Serializable {
        public String docId;
        public String source;
        public String content;
        public String eventTime;
        public String schemaVersion;
        public String tenantId;
        public Map<String, Object> metadata;

        static DocumentEvent fromJson(String json, String defaultSchemaVersion, String defaultTenantId) throws Exception {
            JsonNode node = MAPPER.readTree(json);
            if (node == null || node.isNull()) {
                return null;
            }

            String content = getTextField(node, "content", "text", "body", "document");
            if (content == null || content.isBlank()) {
                return null;
            }

            DocumentEvent event = new DocumentEvent();
            String docId = getTextField(node, "doc_id", "docId", "id");
            event.docId = docId == null || docId.isBlank() ? UUID.randomUUID().toString() : docId;
            event.source = getTextField(node, "source", "source_type", "origin");
            event.source = event.source == null || event.source.isBlank() ? "unknown" : event.source;
            event.content = content;

            String eventTime = getTextField(node, "event_time", "eventTime", "created_at");
            event.eventTime = normalizeEventTime(eventTime);

            String schemaVersion = getTextField(node, "schema_version", "schemaVersion");
            event.schemaVersion = schemaVersion == null || schemaVersion.isBlank() ? defaultSchemaVersion : schemaVersion;

            String tenantId = getTextField(node, "tenant_id", "tenantId");
            event.tenantId = tenantId == null || tenantId.isBlank() ? defaultTenantId : tenantId;

            JsonNode metadataNode = node.get("metadata");
            if (metadataNode != null && metadataNode.isObject()) {
                event.metadata = MAPPER.convertValue(metadataNode, new TypeReference<Map<String, Object>>() {});
            } else {
                event.metadata = new HashMap<>();
            }
            event.metadata.putIfAbsent("ingest_source", event.source);
            event.metadata.put("schema_version", event.schemaVersion);
            event.metadata.put("tenant_id", event.tenantId);

            return event;
        }

        private static String getTextField(JsonNode node, String... names) {
            for (String name : names) {
                if (node.has(name) && !node.get(name).isNull()) {
                    return node.get(name).asText();
                }
            }
            return null;
        }

        private static String normalizeEventTime(String eventTime) {
            if (eventTime == null || eventTime.isBlank()) {
                return Instant.now().toString();
            }
            try {
                return Instant.parse(eventTime).toString();
            } catch (Exception ignored) {
                return Instant.now().toString();
            }
        }
    }

    public static class ChunkRecord implements Serializable {
        public String pointId;
        public String docId;
        public String chunkId;
        public int chunkIndex;
        public String chunkText;
        public String source;
        public String eventTime;
        public String schemaVersion;
        public String tenantId;
        public Map<String, Object> metadata;
        public float[] vector;

        public String toJson() {
            try {
                ObjectNode node = MAPPER.createObjectNode();
                node.put("point_id", pointId);
                node.put("doc_id", docId);
                node.put("chunk_id", chunkId);
                node.put("chunk_index", chunkIndex);
                node.put("chunk_text", chunkText);
                node.put("source", source);
                node.put("event_time", eventTime);
                node.put("schema_version", schemaVersion);
                node.put("tenant_id", tenantId);

                ArrayNode vectorNode = node.putArray("vector");
                if (vector != null) {
                    for (float value : vector) {
                        vectorNode.add(value);
                    }
                }

                ObjectNode metadataNode = node.putObject("metadata");
                if (metadata != null) {
                    for (Map.Entry<String, Object> entry : metadata.entrySet()) {
                        if (entry.getValue() == null) {
                            metadataNode.putNull(entry.getKey());
                        } else {
                            metadataNode.put(entry.getKey(), entry.getValue().toString());
                        }
                    }
                }
                return MAPPER.writeValueAsString(node);
            } catch (Exception exception) {
                throw new RuntimeException("failed_to_serialize_chunk_record", exception);
            }
        }
    }

    public static class TextChunker {
        static List<String> chunk(String text, int chunkSize, int chunkOverlap) {
            List<String> result = new ArrayList<>();
            if (text == null || text.isBlank()) {
                return result;
            }

            int safeChunkSize = Math.max(chunkSize, 64);
            int safeOverlap = Math.max(Math.min(chunkOverlap, safeChunkSize - 1), 0);

            int start = 0;
            int length = text.length();

            while (start < length) {
                int end = Math.min(start + safeChunkSize, length);
                String part = text.substring(start, end).trim();
                if (!part.isBlank()) {
                    result.add(part);
                }
                if (end >= length) {
                    break;
                }
                start = Math.max(end - safeOverlap, start + 1);
            }
            return result;
        }
    }

    public static class SimpleEmbedding {
        static float[] embed(String text, int dim) {
            int safeDim = Math.max(dim, 16);
            float[] vector = new float[safeDim];
            if (text == null || text.isBlank()) {
                return vector;
            }

            int index = 0;
            for (int codePoint : text.codePoints().toArray()) {
                int slotA = Math.floorMod(codePoint * 31 + index * 17, safeDim);
                int slotB = Math.floorMod(codePoint * 13 + index * 7, safeDim);
                vector[slotA] += 1.0f;
                vector[slotB] -= 0.35f;
                index++;
            }

            double norm = 0.0;
            for (float value : vector) {
                norm += value * value;
            }
            norm = Math.sqrt(norm);
            if (norm > 0.0) {
                for (int i = 0; i < vector.length; i++) {
                    vector[i] = (float) (vector[i] / norm);
                }
            }
            return vector;
        }
    }

    public static class QdrantSink extends RichSinkFunction<ChunkRecord> {
        private final String qdrantUrl;
        private final String collection;
        private final int batchSize;
        private final int maxRetries;
        private final long retryBaseMs;
        private final long retryMaxMs;

        private transient HttpClient client;
        private transient List<ChunkRecord> buffer;

        public QdrantSink(
                String qdrantUrl,
                String collection,
                int batchSize,
                int maxRetries,
                long retryBaseMs,
                long retryMaxMs) {
            this.qdrantUrl = qdrantUrl;
            this.collection = collection;
            this.batchSize = Math.max(1, batchSize);
            this.maxRetries = Math.max(0, maxRetries);
            this.retryBaseMs = Math.max(1L, retryBaseMs);
            this.retryMaxMs = Math.max(this.retryBaseMs, retryMaxMs);
        }

        @Override
        public void open(org.apache.flink.configuration.Configuration parameters) {
            this.client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(5))
                    .build();
            this.buffer = new ArrayList<>();
        }

        @Override
        public void invoke(ChunkRecord value, Context context) throws Exception {
            buffer.add(value);
            if (buffer.size() >= batchSize) {
                flushWithRetry();
            }
        }

        @Override
        public void close() throws Exception {
            flushWithRetry();
        }

        private void flushWithRetry() throws Exception {
            if (buffer == null || buffer.isEmpty()) {
                return;
            }

            Exception lastEx = null;
            for (int attempt = 0; attempt <= maxRetries; attempt++) {
                try {
                    flushOnce();
                    buffer.clear();
                    return;
                } catch (Exception ex) {
                    lastEx = ex;
                    if (attempt >= maxRetries) {
                        break;
                    }
                    long backoff = Math.min(retryMaxMs, retryBaseMs * (1L << attempt));
                    Thread.sleep(backoff);
                }
            }

            throw new RuntimeException(
                    "qdrant_upsert_failed_after_retries retries=" + maxRetries + " buffer_size=" + buffer.size(),
                    lastEx);
        }

        private void flushOnce() throws Exception {
            ObjectNode body = MAPPER.createObjectNode();
            ArrayNode points = body.putArray("points");

            for (ChunkRecord record : buffer) {
                ObjectNode point = points.addObject();
                point.put("id", record.pointId);

                ArrayNode vectorNode = point.putArray("vector");
                for (float v : record.vector) {
                    vectorNode.add(v);
                }

                ObjectNode payload = point.putObject("payload");
                payload.put("doc_id", record.docId);
                payload.put("chunk_id", record.chunkId);
                payload.put("chunk_index", record.chunkIndex);
                payload.put("chunk_text", record.chunkText);
                payload.put("source", record.source);
                payload.put("event_time", record.eventTime);
                payload.put("schema_version", record.schemaVersion);
                payload.put("tenant_id", record.tenantId);

                ObjectNode metadataNode = payload.putObject("metadata");
                if (record.metadata != null) {
                    for (Map.Entry<String, Object> entry : record.metadata.entrySet()) {
                        putValue(metadataNode, entry.getKey(), entry.getValue());
                    }
                }
            }

            String requestBody = MAPPER.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(qdrantUrl + "/collections/" + collection + "/points?wait=true"))
                    .header("Content-Type", "application/json")
                    .timeout(Duration.ofSeconds(20))
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            int status = response.statusCode();
            if (status < 200 || status >= 300) {
                throw new RuntimeException("qdrant_upsert_status=" + status + " body=" + response.body());
            }
        }

        private void putValue(ObjectNode node, String key, Object value) {
            if (value == null) {
                node.putNull(key);
            } else if (value instanceof Integer) {
                node.put(key, (Integer) value);
            } else if (value instanceof Long) {
                node.put(key, (Long) value);
            } else if (value instanceof Float) {
                node.put(key, (Float) value);
            } else if (value instanceof Double) {
                node.put(key, (Double) value);
            } else if (value instanceof Boolean) {
                node.put(key, (Boolean) value);
            } else {
                node.put(key, value.toString());
            }
        }
    }
}
