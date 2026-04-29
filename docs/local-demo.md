# 本地演示：Redis + Ollama + JSON Catalog

本地演示目标是快速证明 AI Shopping Assistant 可以脱离云依赖运行：

- Redis 在本机 Docker 中运行，作为购物车依赖的本地替代。
- Ollama 在本机 Docker 中运行，作为可替换模型后端。
- `shoppingassistantservice` 使用 `VECTORSTORE_BACKEND=json` 读取本地商品数据。
- 默认只验证健康检查，避免第一次演示被模型下载拖慢。

## 前置条件

- Docker Desktop 或兼容的 Docker Engine
- Python 3.11+
- `curl`

## 启动

```bash
make local-demo
```

启动后会得到三个本地端点：

| 组件 | 端点 |
|---|---|
| Redis | `127.0.0.1:6379` |
| Ollama | `http://127.0.0.1:11434` |
| shoppingassistantservice | `http://127.0.0.1:18081` |

健康检查：

```bash
curl -sS http://127.0.0.1:18081/healthz
```

预期能看到：

```json
{
  "status": "ok",
  "model_provider": "ollama",
  "vectorstore_backend": "json",
  "circuit_breaker_open": false
}
```

## 拉取模型并发起一次真实请求

默认 `make local-demo` 不会拉模型。需要走真实 Ollama 推理时执行：

```bash
LOCAL_DEMO_PULL_MODEL=1 make local-demo
```

默认模型是 `qwen2.5:0.5b`，可覆盖：

```bash
OLLAMA_MODEL=qwen2.5:7b LOCAL_DEMO_PULL_MODEL=1 make local-demo
```

请求助手：

```bash
curl -sS \
  -H "Content-Type: application/json" \
  -d '{"message":"Recommend warm lighting for a small reading corner","image":""}' \
  http://127.0.0.1:18081/
```

返回内容应包含 `content` 和 `trace_id`。如果模型暂时不可用，服务会返回保护模式文案和 `推荐ID: [NO_MATCH]`，而不是让前端暴露异常。

## 停止

```bash
make local-demo-stop
```

查看状态：

```bash
make local-demo-status
```

## 与 Kubernetes 演示的关系

`make local-demo` 只跑本地依赖和 AI 助手服务，适合快速展示 Gemini/Ollama 切换和 JSON fallback。完整前端、多服务、Kubernetes 编排请使用 [kind + skaffold + kustomize 教程](kind-skaffold-kustomize.md)。
