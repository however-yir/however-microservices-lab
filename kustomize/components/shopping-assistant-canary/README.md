# Shopping Assistant Canary

该组件用于将 `shoppingassistantservice` 以 canary 形态并行部署：

- `shoppingassistantservice`：稳定流量
- `shoppingassistantservice-canary`：小流量验证

## 使用方式

在你的 kustomization 中加入：

```yaml
components:
  - ../kustomize/components/shopping-assistant
  - ../kustomize/components/shopping-assistant-canary
```

## 验证

```bash
kubectl get deploy shoppingassistantservice shoppingassistantservice-canary
kubectl get svc shoppingassistantservice shoppingassistantservice-canary
```

可通过临时端口转发直接访问 canary：

```bash
kubectl port-forward svc/shoppingassistantservice-canary 18080:80
curl -X POST http://127.0.0.1:18080/ -H 'Content-Type: application/json' -d '{\"message\":\"modern living room\",\"image\":\"\"}'
```
