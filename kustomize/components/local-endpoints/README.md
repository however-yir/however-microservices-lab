# Local Endpoints Component

该组件用于把默认部署切换到本地依赖地址，主要覆盖：

- `cartservice.REDIS_ADDR -> host.docker.internal:6379`
- `shoppingassistantservice.MODEL_PROVIDER -> ollama`
- `shoppingassistantservice.OLLAMA_BASE_URL -> http://host.docker.internal:11434`
- `shoppingassistantservice.VECTORSTORE_BACKEND -> json`

## 用法

在你的 `kustomization.yaml` 里追加组件：

```yaml
components:
  - ../components/local-endpoints
```

应用：

```bash
kubectl apply -k .
```
