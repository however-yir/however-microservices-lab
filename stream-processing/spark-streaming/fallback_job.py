#!/usr/bin/env python3
"""Spark Structured Streaming fallback for simple count aggregation."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, from_json, window
from pyspark.sql.types import StructField, StructType, StringType, TimestampType

schema = StructType(
    [
        StructField("event_id", StringType()),
        StructField("user_id", StringType()),
        StructField("event_type", StringType()),
        StructField("event_time", TimestampType()),
    ]
)

spark = (
    SparkSession.builder.appName("spark-fallback-realtime-stats")
    .config("spark.sql.shuffle.partitions", "4")
    .getOrCreate()
)

raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "user_behavior_events")
    .load()
)

parsed = raw.select(from_json(col("value").cast("string"), schema).alias("event")).select("event.*")

result = (
    parsed.groupBy(window(col("event_time"), "1 minute"), col("event_type"))
    .agg(count("event_id").alias("pv"))
    .orderBy("window")
)

query = result.writeStream.outputMode("complete").format("console").start()
query.awaitTermination()
