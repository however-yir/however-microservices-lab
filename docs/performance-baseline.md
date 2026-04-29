# Loadgenerator 性能基线说明

本仓库保留 Online Boutique 的 `loadgenerator`，并把它作为 however 微服务实验室的性能基线入口。基线不是压出极限值，而是记录一次可重复的工程状态：吞吐、错误率、助手链路延迟和资源占用。

## 生成报告模板

```bash
./scripts/perf/generate_baseline_report.sh reports/performance/baseline-latest.md
```

## Kubernetes 基线流程

1. 部署完整应用：

```bash
skaffold run
```

2. 启动或更新 loadgenerator：

```bash
skaffold run --module loadgenerator
```

3. 观察聚合日志：

```bash
kubectl logs -l app=loadgenerator -f
```

4. 记录 Pod 资源：

```bash
kubectl top pods
```

5. 如启用了 AI assistant，记录助手指标：

```bash
kubectl port-forward svc/shoppingassistantservice 18081:80
curl -sS http://127.0.0.1:18081/metrics | grep shopping_assistant
```

## 推荐记录项

| 指标 | 来源 |
|---|---|
| 总请求数 | `loadgenerator` 聚合日志 |
| 错误数和错误率 | `loadgenerator` 聚合日志 |
| `shoppingassistantservice` 请求数 | `shopping_assistant_requests_total` |
| 助手请求延迟 | `shopping_assistant_request_latency_seconds` |
| JSON 检索命中率 | `shopping_assistant_retrieval_hit_ratio` |
| CPU/内存 | `kubectl top pods` |
| 模型后端 | `/healthz` 中的 `model_provider` |
| 检索后端 | `/healthz` 中的 `vectorstore_backend` |

推荐把每次基线报告提交到 `reports/performance/` 目录，并与变更单关联。

## 发布基线建议

发布 `AI microservices lab baseline` 前至少记录：

- 一次 `make local-demo` 健康检查结果。
- 一次 `make check-e2e` 或等价 kind smoke test。
- 一次 `loadgenerator` 聚合日志截图或摘要。
- 一次 `shoppingassistantservice /metrics` 摘要。
