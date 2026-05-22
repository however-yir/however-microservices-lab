package com.realtime.stats;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class RealtimeStatsJobTest {

    @Test
    void userEventShouldParseValidJson() throws Exception {
        String json = "{\"user_id\":\"u1\",\"event_type\":\"checkout_completed\",\"tenant_id\":\"t1\",\"channel\":\"web\",\"schema_version\":\"v1\",\"event_time\":\"2026-01-01T00:00:00Z\",\"source\":\"assistant\",\"success\":true}";
        RealtimeStatsJob.UserEvent event = RealtimeStatsJob.UserEvent.fromJson(json, "topic", 0, 0, "v1");
        assertNotNull(event);
        assertEquals("u1", event.userId);
        assertEquals("checkout_completed", event.eventType);
        assertEquals("t1", event.tenantId);
        assertEquals("web", event.channel);
        assertEquals("v1", event.schemaVersion);
        assertEquals("assistant", event.source);
        assertTrue(event.success);
        assertEquals("checkout_completed", event.businessStage());
    }

    @Test
    void userEventShouldReturnNullForMissingUserId() throws Exception {
        String json = "{\"event_type\":\"view\"}";
        RealtimeStatsJob.UserEvent event = RealtimeStatsJob.UserEvent.fromJson(json, "topic", 0, 0, "v1");
        assertNull(event);
    }

    @Test
    void userEventShouldReturnNullForEmptyJson() throws Exception {
        RealtimeStatsJob.UserEvent event = RealtimeStatsJob.UserEvent.fromJson("", "topic", 0, 0, "v1");
        assertNull(event);
    }

    @Test
    void userEventShouldApplyDefaultValues() throws Exception {
        String json = "{\"user_id\":\"u1\",\"event_type\":\"click\"}";
        RealtimeStatsJob.UserEvent event = RealtimeStatsJob.UserEvent.fromJson(json, "src-topic", 3, 42, "v2");
        assertNotNull(event);
        assertEquals("default", event.tenantId);
        assertEquals("unknown", event.channel);
        assertEquals("v2", event.schemaVersion);
        assertEquals("src-topic", event.topic);
        assertEquals(3, event.partition);
        assertEquals(42L, event.offset);
        assertEquals("assistant_recommended", event.businessStage());
    }

    @Test
    void parseResultShouldGenerateDlqJson() throws Exception {
        RealtimeStatsJob.RawKafkaEvent raw = new RealtimeStatsJob.RawKafkaEvent();
        raw.topic = "test-topic";
        raw.partition = 0;
        raw.offset = 100;
        raw.value = "not-json";

        RealtimeStatsJob.ParseResult result = RealtimeStatsJob.ParseResult.fromRaw(raw, "test-job", "v1");
        assertFalse(result.valid);
        assertNotNull(result.reason);

        String dlqJson = result.toDlqJson();
        assertNotNull(dlqJson);
        assertTrue(dlqJson.contains("dlq"));
        assertTrue(dlqJson.contains("test-job"));
    }

    @Test
    void statsMetricShouldSerializeToJson() {
        // We can't easily test window metrics without Flink test harness,
        // but we can verify the serialization path
        RealtimeStatsJob.StatsMetric metric = new RealtimeStatsJob.StatsMetric();
        metric.jobName = "test-job";
        metric.schemaVersion = "v1";
        metric.metricName = "pv";
        metric.metricType = "counter";
        metric.eventType = "view";
        metric.tenantId = "t1";
        metric.value = 42.0;
        metric.windowStart = 0;
        metric.windowEnd = 60000;
        metric.eventTime = "2026-01-01T00:00:00Z";
        metric.topic = "test";
        metric.partition = 0;
        metric.offset = 0;

        String json = metric.toJson();
        assertNotNull(json);
        assertTrue(json.contains("pv"));
        assertTrue(json.contains("42.0"));
    }
}
