# 生产运行手册（Runbook）

## 1. 服务健康检查

```bash
kubectl get pods
kubectl get svc
kubectl logs deploy/shoppingassistantservice --tail=200
```

探针接口：

- `GET /livez`：进程活性
- `GET /readyz`：依赖就绪
- `GET /healthz`：运行状态
- `GET /metrics`：Prometheus 指标

## 2. 常见故障排查

### 2.1 推荐接口 500

1. 检查 `MODEL_PROVIDER` 与后端地址是否匹配。  
2. 检查 `GOOGLE_API_KEY` 或 `OLLAMA_BASE_URL` 是否可用。  
3. 检查日志中的 `trace_id` 关联调用链。  

### 2.2 请求被限流（429）

1. 检查 `RATE_LIMIT_WINDOW_SECONDS` 与 `RATE_LIMIT_MAX_REQUESTS` 配置。  
2. 根据业务峰值临时调大阈值并回归验证。  

### 2.3 熔断进入保护模式

1. 检查模型服务错误率与时延。  
2. 等待 `CIRCUIT_BREAKER_RESET_SECONDS` 后自动恢复。  
3. 必要时切换 `MODEL_PROVIDER` 或回退发布。  

## 3. 回滚步骤

```bash
kubectl rollout history deploy/shoppingassistantservice
kubectl rollout undo deploy/shoppingassistantservice --to-revision=<REVISION>
kubectl rollout status deploy/shoppingassistantservice
```

## 4. 扩容与容量策略

```bash
kubectl scale deploy/shoppingassistantservice --replicas=3
```

建议结合 HPA，按 CPU 与延迟阈值自动扩缩容。

## 5. 变更发布检查清单

1. 单元测试/契约测试/E2E 全部通过。  
2. 静态检查、镜像扫描、SBOM 生成通过。  
3. 性能基线已更新。  
4. 回滚路径已确认。  
