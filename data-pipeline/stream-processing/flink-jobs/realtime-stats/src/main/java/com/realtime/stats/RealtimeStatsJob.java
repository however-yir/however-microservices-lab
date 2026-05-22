package com.realtime.stats;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.kafka.source.reader.deserializer.KafkaRecordDeserializationSchema;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.windowing.ProcessAllWindowFunction;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;
import org.apache.kafka.clients.consumer.ConsumerRecord;

public class RealtimeStatsJob {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        ParameterTool params = ParameterTool.fromArgs(args);

        String jobName = params.get("job.name", "realtime-stats");
        String defaultSchemaVersion = params.get("schema.version", "v1");
        String bootstrapServers = params.get("kafka.bootstrap.servers", "kafka:29092");
        String sourceTopic = params.get("source.topic", "user_behavior_events");
        String groupId = params.get("group.id", "realtime-stats-job");
        String sourceStartingOffsets = params.get("source.starting.offsets", "latest");
        String metricsTopic = params.get("metrics.topic", "realtime_stats_metrics");
        String dlqTopic = params.get("dlq.topic", "dlq_realtime_stats");
        int windowMinutes = params.getInt("window.minutes", 1);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(10_000, CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setCheckpointStorage("file:///tmp/flink-checkpoints");

        OffsetsInitializer offsetsInitializer = "earliest".equalsIgnoreCase(sourceStartingOffsets)
                ? OffsetsInitializer.earliest()
                : OffsetsInitializer.latest();

        KafkaSource<RawKafkaEvent> source = KafkaSource.<RawKafkaEvent>builder()
                .setBootstrapServers(bootstrapServers)
                .setTopics(sourceTopic)
                .setGroupId(groupId)
                .setStartingOffsets(offsetsInitializer)
                .setDeserializer(new SourceEventDeserializationSchema())
                .build();

        DataStream<ParseResult> parsedStream = env
                .fromSource(source, WatermarkStrategy.noWatermarks(), "kafka-events")
                .map(raw -> ParseResult.fromRaw(raw, jobName, defaultSchemaVersion))
                .returns(ParseResult.class)
                .name("parse-events");

        KafkaSink<String> dlqSink = KafkaSink.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(dlqTopic)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        parsedStream
                .filter(result -> !result.valid)
                .map(ParseResult::toDlqJson)
                .returns(String.class)
                .sinkTo(dlqSink)
                .name("dlq-sink");

        DataStream<UserEvent> eventStream = parsedStream
                .filter(result -> result.valid)
                .map(result -> result.event)
                .returns(UserEvent.class)
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<UserEvent>forBoundedOutOfOrderness(Duration.ofSeconds(5))
                                .withTimestampAssigner((event, ts) -> event.eventTime))
                .name("valid-event-stream");

        OutputTag<UserEvent> lateDataTag = new OutputTag<UserEvent>("late-data") {};

        var pvMetricsOp = eventStream
                .keyBy(event -> event.eventType)
                .window(TumblingEventTimeWindows.of(Time.minutes(windowMinutes)))
                .sideOutputLateData(lateDataTag)
                .process(new PvWindowFunction(jobName))
                .name("pv-window-metric");

        pvMetricsOp.getSideOutput(lateDataTag)
                .map(event -> "LATE_DATA event_type=" + event.eventType + " user_id=" + event.userId)
                .returns(String.class)
                .print("LATE");

        DataStream<StatsMetric> pvMetrics = pvMetricsOp;

        DataStream<StatsMetric> uvMetrics = eventStream
                .windowAll(TumblingEventTimeWindows.of(Time.minutes(windowMinutes)))
                .process(new UvWindowFunction(jobName, defaultSchemaVersion))
                .name("uv-window-metric");

        DataStream<StatsMetric> conversionMetrics = eventStream
                .windowAll(TumblingEventTimeWindows.of(Time.minutes(windowMinutes)))
                .process(new ConversionWindowFunction(jobName, defaultSchemaVersion))
                .name("conversion-window-metric");

        DataStream<StatsMetric> allMetrics = pvMetrics.union(uvMetrics, conversionMetrics);

        KafkaSink<StatsMetric> metricsSink = KafkaSink.<StatsMetric>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(new StatsMetricSerializationSchema(metricsTopic))
                .build();

        allMetrics.sinkTo(metricsSink).name("metrics-kafka-sink");

        allMetrics
                .map(StatsMetric::toLogJson)
                .returns(String.class)
                .name("metric-log")
                .print("STATS");

        env.execute(jobName);
    }

    static class SourceEventDeserializationSchema implements KafkaRecordDeserializationSchema<RawKafkaEvent> {

        @Override
        public void deserialize(ConsumerRecord<byte[], byte[]> record, Collector<RawKafkaEvent> out) {
            RawKafkaEvent event = new RawKafkaEvent();
            event.topic = record.topic();
            event.partition = record.partition();
            event.offset = record.offset();
            event.timestamp = record.timestamp();
            event.value = record.value() == null ? "" : new String(record.value(), StandardCharsets.UTF_8);
            out.collect(event);
        }

        @Override
        public TypeInformation<RawKafkaEvent> getProducedType() {
            return TypeInformation.of(RawKafkaEvent.class);
        }
    }

    static class RawKafkaEvent implements Serializable {
        public String topic;
        public int partition;
        public long offset;
        public long timestamp;
        public String value;
    }

    static class ParseResult implements Serializable {
        public boolean valid;
        public String raw;
        public String reason;
        public UserEvent event;
        public String jobName;
        public String topic;
        public int partition;
        public long offset;
        public String schemaVersion;

        static ParseResult fromRaw(RawKafkaEvent rawEvent, String jobName, String defaultSchemaVersion) {
            ParseResult result = new ParseResult();
            result.raw = rawEvent == null ? "" : rawEvent.value;
            result.jobName = jobName;
            result.topic = rawEvent == null ? "unknown" : rawEvent.topic;
            result.partition = rawEvent == null ? -1 : rawEvent.partition;
            result.offset = rawEvent == null ? -1L : rawEvent.offset;
            result.schemaVersion = defaultSchemaVersion;

            try {
                result.event = UserEvent.fromJson(
                        result.raw,
                        result.topic,
                        result.partition,
                        result.offset,
                        defaultSchemaVersion);
                result.valid = result.event != null;
                if (result.valid) {
                    result.schemaVersion = result.event.schemaVersion;
                } else {
                    result.reason = "empty_or_missing_required_fields";
                }
            } catch (Exception exception) {
                result.valid = false;
                result.reason = exception.getMessage() == null ? "parse_exception" : exception.getMessage();
            }
            return result;
        }

        String toDlqJson() {
            try {
                ObjectNode node = MAPPER.createObjectNode();
                node.put("record_type", "dlq");
                node.put("job_name", jobName);
                node.put("stage", "parse");
                node.put("topic", topic);
                node.put("partition", partition);
                node.put("offset", offset);
                node.put("schema_version", schemaVersion);
                node.put("reason", reason == null ? "unknown" : reason);
                node.put("raw", raw == null ? "" : raw);
                node.put("event_time", Instant.now().toString());
                return MAPPER.writeValueAsString(node);
            } catch (Exception exception) {
                return "{\"record_type\":\"dlq\",\"job_name\":\"" + jobName + "\",\"stage\":\"parse\",\"reason\":\"dlq_serialize_error\"}";
            }
        }
    }

    static class PvWindowFunction extends ProcessWindowFunction<UserEvent, StatsMetric, String, TimeWindow> {
        private final String jobName;

        PvWindowFunction(String jobName) {
            this.jobName = jobName;
        }

        @Override
        public void process(String key, Context context, Iterable<UserEvent> elements, Collector<StatsMetric> out) {
            int count = 0;
            UserEvent last = null;
            for (UserEvent event : elements) {
                count++;
                last = event;
            }
            if (last == null) {
                return;
            }

            out.collect(StatsMetric.metric(
                    jobName,
                    last.schemaVersion,
                    "pv",
                    "counter",
                    key,
                    last.tenantId,
                    count,
                    context.window(),
                    last.topic,
                    last.partition,
                    last.offset));
        }
    }

    static class UvWindowFunction extends ProcessAllWindowFunction<UserEvent, StatsMetric, TimeWindow> {
        private final String jobName;
        private final String defaultSchemaVersion;

        UvWindowFunction(String jobName, String defaultSchemaVersion) {
            this.jobName = jobName;
            this.defaultSchemaVersion = defaultSchemaVersion;
        }

        @Override
        public void process(Context context, Iterable<UserEvent> elements, Collector<StatsMetric> out) {
            Set<String> uniqueUsers = new HashSet<>();
            UserEvent last = null;
            for (UserEvent event : elements) {
                uniqueUsers.add(event.userId);
                last = event;
            }

            String schemaVersion = last == null ? defaultSchemaVersion : last.schemaVersion;
            String tenantId = last == null ? "default" : last.tenantId;
            String topic = last == null ? "unknown" : last.topic;
            int partition = last == null ? -1 : last.partition;
            long offset = last == null ? -1 : last.offset;

            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "uv",
                    "gauge",
                    "all",
                    tenantId,
                    uniqueUsers.size(),
                    context.window(),
                    topic,
                    partition,
                    offset));
        }
    }

    static class ConversionWindowFunction extends ProcessAllWindowFunction<UserEvent, StatsMetric, TimeWindow> {
        private final String jobName;
        private final String defaultSchemaVersion;

        ConversionWindowFunction(String jobName, String defaultSchemaVersion) {
            this.jobName = jobName;
            this.defaultSchemaVersion = defaultSchemaVersion;
        }

        @Override
        public void process(Context context, Iterable<UserEvent> elements, Collector<StatsMetric> out) {
            double views = 0;
            double purchases = 0;
            double assistantRecommendations = 0;
            double assistantRecommendationClicks = 0;
            double addToCart = 0;
            double checkoutTotal = 0;
            double checkoutSuccess = 0;
            double cartWithoutView = 0;
            double checkoutWithoutCart = 0;
            UserEvent last = null;
            List<UserEvent> orderedEvents = new ArrayList<>();

            for (UserEvent event : elements) {
                orderedEvents.add(event);
            }
            orderedEvents.sort(Comparator.comparingLong(event -> event.eventTime));

            Map<String, Set<String>> userStages = new HashMap<>();
            for (UserEvent event : orderedEvents) {
                String stage = event.businessStage();
                if ("product_viewed".equals(stage)) {
                    views += 1;
                    if ("assistant".equals(event.source)) {
                        assistantRecommendationClicks += 1;
                    }
                }
                if ("assistant_recommended".equals(stage)) {
                    assistantRecommendations += 1;
                }
                if ("add_to_cart".equals(stage)) {
                    addToCart += 1;
                }
                if ("checkout_completed".equals(stage)) {
                    purchases += 1;
                    checkoutTotal += 1;
                    if (event.success) {
                        checkoutSuccess += 1;
                    }
                }

                Set<String> stages = userStages.computeIfAbsent(event.userId, ignored -> new HashSet<>());
                if ("add_to_cart".equals(stage) && !stages.contains("product_viewed")) {
                    cartWithoutView += 1;
                }
                if ("checkout_completed".equals(stage) && !stages.contains("add_to_cart")) {
                    checkoutWithoutCart += 1;
                }
                stages.add(stage);
                last = event;
            }

            String schemaVersion = last == null ? defaultSchemaVersion : last.schemaVersion;
            String tenantId = last == null ? "default" : last.tenantId;
            String topic = last == null ? "unknown" : last.topic;
            int partition = last == null ? -1 : last.partition;
            long offset = last == null ? -1 : last.offset;
            double conversion = views > 0 ? (purchases / views) * 100.0 : 0.0;
            double recommendationClickRate = assistantRecommendations > 0
                    ? (assistantRecommendationClicks / assistantRecommendations) * 100.0
                    : 0.0;
            double addToCartConversionRate = views > 0 ? (addToCart / views) * 100.0 : 0.0;
            double checkoutSuccessRate = checkoutTotal > 0 ? (checkoutSuccess / checkoutTotal) * 100.0 : 0.0;

            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "conversion_rate",
                    "gauge",
                    "all",
                    tenantId,
                    conversion,
                    context.window(),
                    topic,
                    partition,
                    offset));
            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "recommendation_click_rate",
                    "gauge",
                    "assistant",
                    tenantId,
                    recommendationClickRate,
                    context.window(),
                    topic,
                    partition,
                    offset));
            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "add_to_cart_conversion_rate",
                    "gauge",
                    "all",
                    tenantId,
                    addToCartConversionRate,
                    context.window(),
                    topic,
                    partition,
                    offset));
            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "checkout_success_rate",
                    "gauge",
                    "all",
                    tenantId,
                    checkoutSuccessRate,
                    context.window(),
                    topic,
                    partition,
                    offset));
            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "abnormal_sequence",
                    "counter",
                    "cart_without_view",
                    tenantId,
                    cartWithoutView,
                    context.window(),
                    topic,
                    partition,
                    offset));
            out.collect(StatsMetric.metric(
                    jobName,
                    schemaVersion,
                    "abnormal_sequence",
                    "counter",
                    "checkout_without_cart",
                    tenantId,
                    checkoutWithoutCart,
                    context.window(),
                    topic,
                    partition,
                    offset));
        }
    }

    static class StatsMetric implements Serializable {
        public String jobName;
        public String schemaVersion;
        public String metricName;
        public String metricType;
        public String eventType;
        public String tenantId;
        public double value;
        public long windowStart;
        public long windowEnd;
        public String eventTime;
        public String topic;
        public int partition;
        public long offset;

        static StatsMetric metric(
                String jobName,
                String schemaVersion,
                String metricName,
                String metricType,
                String eventType,
                String tenantId,
                double value,
                TimeWindow window,
                String topic,
                int partition,
                long offset) {
            StatsMetric metric = new StatsMetric();
            metric.jobName = jobName;
            metric.schemaVersion = schemaVersion;
            metric.metricName = metricName;
            metric.metricType = metricType;
            metric.eventType = eventType;
            metric.tenantId = tenantId;
            metric.value = value;
            metric.windowStart = window.getStart();
            metric.windowEnd = window.getEnd();
            metric.eventTime = Instant.now().toString();
            metric.topic = topic;
            metric.partition = partition;
            metric.offset = offset;
            return metric;
        }

        String toJson() {
            try {
                ObjectNode node = MAPPER.createObjectNode();
                node.put("record_type", "metric");
                node.put("job_name", jobName);
                node.put("schema_version", schemaVersion);
                node.put("metric_name", metricName);
                node.put("metric_type", metricType);
                node.put("event_type", eventType);
                node.put("tenant_id", tenantId);
                node.put("value", value);
                node.put("window_start", windowStart);
                node.put("window_end", windowEnd);
                node.put("event_time", eventTime);
                node.put("topic", topic);
                node.put("partition", partition);
                node.put("offset", offset);
                return MAPPER.writeValueAsString(node);
            } catch (Exception exception) {
                throw new RuntimeException("failed_to_serialize_metric", exception);
            }
        }

        String toLogJson() {
            try {
                ObjectNode node = MAPPER.createObjectNode();
                node.put("job_name", jobName);
                node.put("stage", "window_metric");
                node.put("topic", topic);
                node.put("partition", partition);
                node.put("offset", offset);
                node.put("schema_version", schemaVersion);
                node.put("metric_name", metricName);
                node.put("event_type", eventType);
                node.put("tenant_id", tenantId);
                node.put("value", value);
                node.put("window_start", windowStart);
                node.put("window_end", windowEnd);
                node.put("event_time", eventTime);
                return MAPPER.writeValueAsString(node);
            } catch (Exception exception) {
                return "{\"job_name\":\"" + jobName + "\",\"stage\":\"window_metric\",\"message\":\"log_serialize_failed\"}";
            }
        }
    }

    static class StatsMetricSerializationSchema implements KafkaRecordSerializationSchema<StatsMetric> {
        private final String topic;

        StatsMetricSerializationSchema(String topic) {
            this.topic = topic;
        }

        @Override
        public org.apache.kafka.clients.producer.ProducerRecord<byte[], byte[]> serialize(
                StatsMetric element,
                KafkaSinkContext context,
                Long timestamp) {
            return new org.apache.kafka.clients.producer.ProducerRecord<>(
                    topic,
                    element.tenantId == null ? null : element.tenantId.getBytes(StandardCharsets.UTF_8),
                    element.toJson().getBytes(StandardCharsets.UTF_8));
        }
    }

    static class UserEvent implements Serializable {
        public String userId;
        public String eventType;
        public String tenantId;
        public String channel;
        public long eventTime;
        public String source;
        public boolean success;
        public String schemaVersion;
        public String topic;
        public int partition;
        public long offset;

        static UserEvent fromJson(
                String json,
                String topic,
                int partition,
                long offset,
                String defaultSchemaVersion) throws Exception {
            JsonNode node = MAPPER.readTree(json);
            if (node == null || node.get("user_id") == null || node.get("event_type") == null) {
                return null;
            }

            UserEvent event = new UserEvent();
            event.userId = node.get("user_id").asText();
            event.eventType = node.get("event_type").asText();
            event.tenantId = node.has("tenant_id") ? node.get("tenant_id").asText() : "default";
            event.channel = node.has("channel") ? node.get("channel").asText() : "unknown";
            event.source = node.has("source") ? node.get("source").asText() : "";
            event.success = !node.has("success") || node.get("success").asBoolean();
            event.schemaVersion = node.has("schema_version")
                    ? node.get("schema_version").asText()
                    : defaultSchemaVersion;
            String eventTimeText = node.has("event_time") ? node.get("event_time").asText() : null;
            event.eventTime = parseEventTime(eventTimeText);
            event.topic = topic;
            event.partition = partition;
            event.offset = offset;
            return event;
        }

        String businessStage() {
            if ("view".equals(eventType)) {
                return "product_viewed";
            }
            if ("click".equals(eventType)) {
                return "assistant_recommended";
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
