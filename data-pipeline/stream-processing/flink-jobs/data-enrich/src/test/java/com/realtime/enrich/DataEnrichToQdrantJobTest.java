package com.realtime.enrich;

import java.util.List;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

class DataEnrichToQdrantJobTest {

    @Test
    void chunkerShouldSplitTextWithOverlap() {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < 200; i++) {
            builder.append("ab");
        }
        String text = builder.toString();

        List<String> chunks = DataEnrichToQdrantJob.TextChunker.chunk(text, 120, 20);

        Assertions.assertTrue(chunks.size() >= 3, "expected multiple chunks");
        Assertions.assertTrue(chunks.get(0).length() <= 120);
        Assertions.assertTrue(chunks.get(1).length() <= 120);
        Assertions.assertFalse(chunks.get(0).isBlank());
    }

    @Test
    void embeddingShouldReturnRequestedDimensionAndNormalizedVector() {
        int dim = 64;
        float[] vector = DataEnrichToQdrantJob.SimpleEmbedding.embed("stream processing for rag", dim);

        Assertions.assertEquals(dim, vector.length);

        double norm = 0.0;
        for (float value : vector) {
            norm += value * value;
        }
        norm = Math.sqrt(norm);

        Assertions.assertTrue(norm > 0.99 && norm < 1.01, "vector should be normalized");
    }

    @Test
    void chunkRecordShouldSerializeToJson() {
        DataEnrichToQdrantJob.ChunkRecord record = new DataEnrichToQdrantJob.ChunkRecord();
        record.pointId = "p1";
        record.docId = "doc-1";
        record.chunkId = "doc-1#0";
        record.chunkIndex = 0;
        record.chunkText = "hello world";
        record.source = "test";
        record.eventTime = "2026-04-09T01:00:00Z";
        record.vector = new float[] {0.1f, 0.2f};

        String json = record.toJson();

        Assertions.assertTrue(json.contains("doc-1"));
        Assertions.assertTrue(json.contains("chunk_text"));
        Assertions.assertTrue(json.contains("vector"));
    }

    @Test
    void documentEventShouldFillDefaultSchemaAndTenant() throws Exception {
        String payload = "{\"doc_id\":\"d1\",\"content\":\"hello world\"}";

        DataEnrichToQdrantJob.DocumentEvent event =
                DataEnrichToQdrantJob.DocumentEvent.fromJson(payload, "v2", "tenant-a");

        Assertions.assertNotNull(event);
        Assertions.assertEquals("v2", event.schemaVersion);
        Assertions.assertEquals("tenant-a", event.tenantId);
        Assertions.assertEquals("d1", event.docId);
    }

    @Test
    void embeddingProviderSimpleShouldHonorDimension() {
        DataEnrichToQdrantJob.EmbeddingConfig config = new DataEnrichToQdrantJob.EmbeddingConfig();
        config.provider = "simple";
        config.fallbackToSimple = true;

        float[] vector = DataEnrichToQdrantJob.EmbeddingProviders.embed("vector me", 96, config);
        Assertions.assertEquals(96, vector.length);
    }
}
