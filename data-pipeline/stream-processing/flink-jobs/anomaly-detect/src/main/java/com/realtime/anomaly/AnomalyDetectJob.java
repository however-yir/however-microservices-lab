package com.realtime.anomaly;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.cep.CEP;
import org.apache.flink.cep.PatternSelectFunction;
import org.apache.flink.cep.pattern.Pattern;
import org.apache.flink.cep.pattern.conditions.SimpleCondition;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.ProcessFunction;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

public class AnomalyDetectJob {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        ParameterTool params = ParameterTool.fromArgs(args);

        String jobName = params.get("job.name", "anomaly-detect-cep");
        String bootstrapServers = params.get("kafka.bootstrap.servers", "kafka:29092");
        String sourceTopic = params.get("source.topic", "user_behavior_events");
        String outputTopic = params.get("output.topic", "anomaly_alerts");
        String groupId = params.get("group.id", "anomaly-detect-job");
        String sourceStartingOffsets = params.get("source.starting.offsets", "latest");
        String dlqTopic = params.get("dlq.topic", "dlq_anomaly_detect");

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(15_000, CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setCheckpointStorage("file:///tmp/flink-checkpoints");

        OffsetsInitializer offsetsInitializer = "earliest".equalsIgnoreCase(sourceStartingOffsets)
                ? OffsetsInitializer.earliest()
                : OffsetsInitializer.latest();

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setTopics(sourceTopic)
                .setGroupId(groupId)
                .setStartingOffsets(offsetsInitializer)
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        KafkaSink<String> dlqSink = KafkaSink.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(dlqTopic)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        OutputTag<String> dlqTag = new OutputTag<String>("dlq-parse") {};

        var parsedStream = env
                .fromSource(source, WatermarkStrategy.noWatermarks(), "anomaly-source")
                .process(new ProcessFunction<String, UserEvent>() {
                    @Override
                    public void processElement(String json, Context ctx, Collector<UserEvent> out) {
                        try {
                            UserEvent event = UserEvent.fromJson(json);
                            if (event != null && event.userId != null && !event.userId.isBlank()) {
                                out.collect(event);
                            } else {
                                ctx.output(dlqTag, toDlqJson(jobName, "parse", "empty_or_missing_fields", json));
                            }
                        } catch (Exception e) {
                            ctx.output(dlqTag, toDlqJson(jobName, "parse", e.getMessage(), json));
                        }
                    }
                })
                .returns(UserEvent.class);

        parsedStream.getSideOutput(dlqTag).sinkTo(dlqSink).name("dlq-sink");

        DataStream<UserEvent> eventStream = parsedStream
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<UserEvent>forBoundedOutOfOrderness(Duration.ofSeconds(5))
                                .withTimestampAssigner((event, ts) -> event.eventTime))
                .name("normalize-events");

        Pattern<UserEvent, ?> checkoutFunnelPattern = Pattern
                .<UserEvent>begin("product_viewed")
                .where(new SimpleCondition<UserEvent>() {
                    @Override
                    public boolean filter(UserEvent event) {
                        return "product_viewed".equals(event.businessStage());
                    }
                })
                .next("add_to_cart")
                .where(new SimpleCondition<UserEvent>() {
                    @Override
                    public boolean filter(UserEvent event) {
                        return "add_to_cart".equals(event.businessStage());
                    }
                })
                .next("checkout_completed")
                .where(new SimpleCondition<UserEvent>() {
                    @Override
                    public boolean filter(UserEvent event) {
                        return "checkout_completed".equals(event.businessStage());
                    }
                })
                .within(Time.minutes(10));

        DataStream<String> alertStream = CEP
                .pattern(eventStream.keyBy(event -> event.userId), checkoutFunnelPattern)
                .select((PatternSelectFunction<UserEvent, String>) pattern -> toAlertJson(jobName, pattern))
                .name("checkout-funnel-alerts");

        KafkaSink<String> alertSink = KafkaSink.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(outputTopic)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        alertStream.sinkTo(alertSink).name("anomaly-alert-sink");
        alertStream.print("ANOMALY");

        env.execute(jobName);
    }

    private static String toAlertJson(String jobName, Map<String, List<UserEvent>> pattern) throws Exception {
        UserEvent view = getFirst(pattern, "product_viewed");
        UserEvent addToCart = getFirst(pattern, "add_to_cart");
        UserEvent checkout = getFirst(pattern, "checkout_completed");

        ObjectNode node = MAPPER.createObjectNode();
        node.put("alert_type", "cep_checkout_funnel");
        node.put("job_name", jobName);
        node.put("user_id", checkout.userId);
        node.put("tenant_id", checkout.tenantId);
        node.put("schema_version", checkout.schemaVersion);
        node.put("channel", checkout.channel);
        node.put("sequence", "product_viewed->add_to_cart->checkout_completed");
        node.put("view_time", Instant.ofEpochMilli(view.eventTime).toString());
        node.put("add_to_cart_time", Instant.ofEpochMilli(addToCart.eventTime).toString());
        node.put("checkout_time", Instant.ofEpochMilli(checkout.eventTime).toString());
        node.put("event_time", Instant.now().toString());
        node.put("severity", "warning");
        return MAPPER.writeValueAsString(node);
    }

    private static String toDlqJson(String jobName, String stage, String reason, String raw) {
        try {
            ObjectNode node = MAPPER.createObjectNode();
            node.put("record_type", "dlq");
            node.put("job_name", jobName);
            node.put("stage", stage);
            node.put("reason", reason == null ? "unknown" : reason);
            node.put("raw", raw == null ? "" : raw);
            node.put("event_time", Instant.now().toString());
            return MAPPER.writeValueAsString(node);
        } catch (Exception e) {
            return "{\"record_type\":\"dlq\",\"job_name\":\"" + jobName + "\",\"stage\":\"" + stage + "\"}";
        }
    }

    private static UserEvent getFirst(Map<String, List<UserEvent>> pattern, String key) {
        List<UserEvent> events = pattern.get(key);
        if (events == null || events.isEmpty()) {
            throw new IllegalArgumentException("missing CEP stage: " + key);
        }
        return events.get(0);
    }

    static class UserEvent implements Serializable {
        public String userId;
        public String eventType;
        public String channel;
        public String tenantId;
        public String schemaVersion;
        public long eventTime;

        static UserEvent fromJson(String json) throws Exception {
            JsonNode node = MAPPER.readTree(json);
            if (node == null || node.get("user_id") == null || node.get("event_type") == null) {
                return null;
            }

            UserEvent event = new UserEvent();
            event.userId = node.get("user_id").asText();
            event.eventType = node.get("event_type").asText();
            event.channel = node.has("channel") ? node.get("channel").asText() : "unknown";
            event.tenantId = node.has("tenant_id") ? node.get("tenant_id").asText() : "default";
            event.schemaVersion = node.has("schema_version") ? node.get("schema_version").asText() : "v1";
            event.eventTime = parseEventTime(node.has("event_time") ? node.get("event_time").asText() : null);
            return event;
        }

        String businessStage() {
            if ("view".equals(eventType)) {
                return "product_viewed";
            }
            if ("purchase".equals(eventType)) {
                return "checkout_completed";
            }
            return eventType;
        }

        private static long parseEventTime(String eventTimeText) {
            if (eventTimeText == null || eventTimeText.isBlank()) {
                return System.currentTimeMillis();
            }
            try {
                return Instant.parse(eventTimeText).toEpochMilli();
            } catch (Exception ignored) {
                return System.currentTimeMillis();
            }
        }
    }
}
