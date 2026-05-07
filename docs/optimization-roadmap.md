# Optimization Roadmap (30 Items)

> 本清单分为 `P0（立即）`、`P1（短期）`、`P2（中期）`。`状态` 中 `Done` 表示已在本轮完成。

| # | 建议 | 优先级 | 状态 |
|---|---|---|---|
| 1 | 为 `data-enrich` 增加“写回 Kafka `rag_processed_chunks`”能力，形成可追踪 ETL 闭环 | P0 | Done |
| 2 | 为 `data-enrich` 增加参数化开关（开启/关闭 Kafka 输出、起始位点策略） | P0 | Done |
| 3 | 为 `data-enrich` 增加输入时间戳容错，避免异常时间字段导致任务失败 | P0 | Done |
| 4 | 为 `data-enrich` 增加单元测试（分块逻辑、向量维度与归一化） | P0 | Done |
| 5 | 提供 RAG 文档样例生产脚本，支持一键发送测试数据 | P0 | Done |
| 6 | 引入 Debezium + Kafka Connect 一键启动并自动注册 connector | P0 | Done |
| 7 | 给 Postgres 增加初始化 schema 与样例数据，降低 CDC 首次上手门槛 | P0 | Done |
| 8 | 为 Kafka Connect 内部 topic 固化 `compact` 策略 | P0 | Done |
| 9 | 补齐流式业务指标导出器（UV/PV/转化率/异常） | P0 | Done |
| 10 | Grafana 大屏升级为业务视图（UV/PV、转化率、异常、告警列表） | P0 | Done |
| 11 | 增加业务告警规则（转化率下滑、异常激增） | P0 | Done |
| 12 | 增加 `Makefile` 常用目标（构建、提交作业、生产测试、健康检查） | P0 | Done |
| 13 | 增加端到端 smoke check 脚本，自动验证关键依赖 | P0 | Done |
| 14 | 增加 CI（compose 校验、Python 语法、Flink 构建、单元测试） | P0 | Done |
| 15 | 增加 `.env.example` 变量说明（Connector/Webhook/Qdrant 维度等） | P1 | Done |
| 16 | 为 `realtime-stats` 增加指标输出到 Prometheus（替代 print-only） | P1 | Done |
| 17 | 为 Flink 任务增加统一日志字段规范（job_name/topic/partition/offset） | P1 | Done |
| 18 | 引入 Dead Letter Queue（DLQ）处理脏数据 | P1 | Done |
| 19 | 为 CDC 与 ETL 数据添加 schema 版本字段（schema_version） | P1 | Done |
| 20 | 引入 Schema Registry（Avro/JSON Schema）做契约管理 | P1 | Done |
| 21 | 为 Qdrant sink 增加重试与指数退避 | P1 | Done |
| 22 | 为 Kafka Connect 增加监控（任务状态、失败重试次数） | P1 | Done |
| 23 | 增加 Elasticsearch ILM 与索引生命周期策略 | P1 | Done |
| 24 | 为业务大屏增加漏斗与渠道分层（app/web/mini_program） | P1 | Done |
| 25 | 增加异常检测 CEP 作业（行为序列规则） | P1 | Done |
| 26 | 将 `SimpleEmbedding` 替换为真实 Embedding 服务（OpenAI/本地模型） | P2 | Done |
| 27 | 增加 K8s Helm chart，实现集群化部署 | P2 | Done |
| 28 | 增加压测脚本（事件吞吐、端到端延迟、稳定性） | P2 | Done |
| 29 | 增加多租户隔离策略（topic namespace + tenant id） | P2 | Done |
| 30 | 建立 SLO/SLI（摄取成功率、95 分位延迟、告警恢复时间） | P2 | Done |

## 本轮已实施重点

- 数据增强链路可运行（分块 + 向量化 + Qdrant + Kafka 输出）
- CDC 一键启动（Postgres + Connect + auto-init connector）
- 业务可观测性闭环（指标导出 + 告警 + Grafana 业务大屏）
- 工程化提升（Makefile/Smoke Check/CI）
- 流处理增强（统一日志字段、DLQ、schema_version、指标主题）
- 平台增强（Schema Registry、Connect 监控、ES ILM、CEP 作业）
- 生产化增强（真实 Embedding Provider、Helm、压测、多租户、SLO/SLI）
