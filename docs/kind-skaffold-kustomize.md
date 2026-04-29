# kind + Skaffold + Kustomize 教程

本教程用于在本机 Kubernetes 集群里跑完整多语言微服务链路，并启用 AI Shopping Assistant 的本地化配置。

## 目标

- 使用 kind 创建一次性本地集群。
- 使用 Skaffold 构建并部署所有服务镜像。
- 使用 Kustomize 组合基础清单和 AI assistant 组件。
- 使用 mock Ollama 避免 CI 或演示时下载模型。
- 使用 frontend `/bot` 验证助手链路。

## 前置条件

```bash
kind version
kubectl version --client
skaffold version
docker version
```

## 一键 smoke test

仓库提供封装脚本：

```bash
make check-e2e
```

脚本会执行：

1. 创建或复用 `however-microservices-lab-e2e` kind 集群。
2. 创建 `however-e2e` namespace。
3. 通过 `skaffold run -p e2e` 部署测试 Kustomize overlay。
4. 等待 frontend、cartservice、checkoutservice、productcatalogservice、shoppingassistantservice 和 mock Ollama ready。
5. 通过 port-forward 访问 frontend。
6. 覆盖首页、商品页、加购、结算和 `/bot` 助手请求。

## 手动部署

创建集群：

```bash
kind create cluster --name however-microservices-lab-e2e
kubectl config use-context kind-however-microservices-lab-e2e
kubectl create namespace however-e2e --dry-run=client -o yaml | kubectl apply -f -
```

部署：

```bash
skaffold run -p e2e --namespace however-e2e
```

等待核心组件：

```bash
kubectl -n however-e2e wait --for=condition=available --timeout=600s deployment/frontend
kubectl -n however-e2e wait --for=condition=available --timeout=600s deployment/shoppingassistantservice
kubectl -n however-e2e wait --for=condition=available --timeout=600s deployment/ollama
```

访问前端：

```bash
kubectl -n however-e2e port-forward svc/frontend 18080:80
```

打开 `http://127.0.0.1:18080`，或直接请求健康检查：

```bash
curl -fsS http://127.0.0.1:18080/_healthz
```

验证助手链路：

```bash
curl -fsS \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:18080/bot" \
  -d '{"message":"Recommend warm lighting for a small room","image":""}'
```

## Kustomize overlay 说明

测试 overlay 位于 [tests/e2e/kustomize/kustomization.yaml](../tests/e2e/kustomize/kustomization.yaml)，组合了：

- `../../../kubernetes-manifests`
- `../../../kustomize/components/shopping-assistant`
- `mock-ollama.yaml`

关键覆盖：

- `frontend.ENABLE_ASSISTANT=true`
- `shoppingassistantservice.MODEL_PROVIDER=ollama`
- `shoppingassistantservice.OLLAMA_BASE_URL=http://ollama:11434`
- `shoppingassistantservice.VECTORSTORE_BACKEND=json`
- `shoppingassistantservice.PRODUCT_CATALOG_JSON=/shoppingassistantservice/products.local.json`

## 使用真实本地 Ollama

如果你已经运行本机 Ollama，可以在自己的 Kustomize overlay 中追加：

```yaml
components:
  - ../../../kustomize/components/shopping-assistant
  - ../../../kustomize/components/local-endpoints
```

该组件会把助手切到：

- `MODEL_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- `VECTORSTORE_BACKEND=json`

## 清理

```bash
skaffold delete -p e2e --namespace however-e2e
kind delete cluster --name however-microservices-lab-e2e
```
