package com.realtime.anomaly;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class AnomalyDetectJobTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void userEventShouldParseValidJson() throws Exception {
        String json = "{\"user_id\":\"u1\",\"event_type\":\"view\",\"channel\":\"app\",\"tenant_id\":\"t1\",\"schema_version\":\"v1\",\"event_time\":\"2026-01-01T00:00:00Z\"}";
        AnomalyDetectJob.UserEvent event = AnomalyDetectJob.UserEvent.fromJson(json);
        assertNotNull(event);
        assertEquals("u1", event.userId);
        assertEquals("view", event.eventType);
        assertEquals("app", event.channel);
        assertEquals("t1", event.tenantId);
    }

    @Test
    void userEventShouldReturnNullForMissingEventType() throws Exception {
        String json = "{\"user_id\":\"u1\"}";
        AnomalyDetectJob.UserEvent event = AnomalyDetectJob.UserEvent.fromJson(json);
        assertNull(event);
    }

    @Test
    void userEventShouldReturnNullForEmptyJson() throws Exception {
        AnomalyDetectJob.UserEvent event = AnomalyDetectJob.UserEvent.fromJson("");
        assertNull(event);
    }

    @Test
    void userEventShouldReturnNullForNullUserId() throws Exception {
        String json = "{\"event_type\":\"view\"}";
        AnomalyDetectJob.UserEvent event = AnomalyDetectJob.UserEvent.fromJson(json);
        assertNull(event);
    }

    @Test
    void userEventShouldParseEventTimeFallback() throws Exception {
        String json = "{\"user_id\":\"u1\",\"event_type\":\"click\"}";
        AnomalyDetectJob.UserEvent event = AnomalyDetectJob.UserEvent.fromJson(json);
        assertNotNull(event);
        assertTrue(event.eventTime > 0);
    }
}
