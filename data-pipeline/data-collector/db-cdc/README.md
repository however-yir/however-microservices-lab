# db-cdc

使用 Debezium + Kafka Connect 实现 PostgreSQL 到 Kafka 的增量同步。

## 一键启动（推荐）

在项目根目录执行：

```bash
docker compose up -d
```

系统会自动完成：

- 启动 `postgres`（已开启逻辑复制）
- 启动 `kafka-connect`
- 自动注册 connector：`postgres-cdc-user-profile`
- 自动应用字段规范：`schema_version=v1`（SMT）

## 验证 CDC

1. 写入或更新数据：

```bash
docker exec -it rdp-postgres psql -U postgres -d app -c \
  "INSERT INTO user_profile(user_name, city, tags) VALUES ('carol', 'hangzhou', 'python,ml');"
```

2. 查看 CDC topic：

```bash
docker exec -it rdp-kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic cdc.public.user_profile \
  --from-beginning
```

## 手工注册（可选）

```bash
curl -X POST http://localhost:8083/connectors \
  -H 'Content-Type: application/json' \
  -d @register-postgres-connector.json
```

## 相关文件

- `register-postgres-connector.json`：完整 connector 请求体
- `postgres-connector-config.json`：用于 `PUT /connectors/{name}/config` 的纯配置体
- `initdb/01_schema.sql`：PostgreSQL 初始化表结构与样例数据
