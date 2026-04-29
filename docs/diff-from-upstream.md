# 与上游 Google Online Boutique 的差异说明

本文档用于说明 `however-microservices-lab` 的上游来源、保留边界和工程改造点。目标是让读者可以快速确认：本仓库不是简单改名，而是在 Online Boutique 的多语言微服务样板之上，扩展成一个“云原生微服务 + AI 集成实验室”。

## 1. 上游来源与保留边界

- 上游项目：GoogleCloudPlatform/microservices-demo，也就是 Google Online Boutique。
- 上游协议：Apache License 2.0，本仓库保留根目录 [LICENSE](../LICENSE)。
- 衍生说明：本仓库新增 [LICENSE-HOWEVER.md](../LICENSE-HOWEVER.md)，用于说明 however 侧新增文档、脚本、配置和实验室定位。
- 保留的上游价值：多语言服务边界、gRPC 协议、Kubernetes 部署清单、Skaffold 构建方式、负载生成器和基础电商业务链路。
- 改造目标：把上游电商样例升级为可本地演示、可切换 AI 后端、可做 K8s 工程实践和 CI 质量演示的实验室。

## 2. 命名空间与仓库身份迁移

| 范围 | 上游形态 | however 改造 |
|---|---|---|
| 仓库定位 | Online Boutique demo | however microservices lab |
| Java 包名 | `hipstershop.*` | `com.however.microservices.adservice.*` |
| Gradle group | 上游包组织 | `com.however.microservices` |
| Java artifact | `adservice` | `however-adservice` |
| Node package | 上游服务名 | `however-currencyservice`、`however-paymentservice` |
| 文档入口 | Online Boutique README | AI microservices lab README |

可核验文件：

- [src/adservice/build.gradle](../src/adservice/build.gradle)
- [src/adservice/settings.gradle](../src/adservice/settings.gradle)
- [src/adservice/src/main/java/com/however/microservices/adservice/AdService.java](../src/adservice/src/main/java/com/however/microservices/adservice/AdService.java)
- [src/currencyservice/package.json](../src/currencyservice/package.json)
- [src/paymentservice/package.json](../src/paymentservice/package.json)
- [.github/HOWEVER_REPO_PROFILE.md](../.github/HOWEVER_REPO_PROFILE.md)

## 3. 配置外置与本地化

上游样例主要面向云端演示，本仓库把更多运行参数外置，便于本地、kind、GKE 和 CI 之间切换。

| 配置面 | 改造点 | 文件 |
|---|---|---|
| 通用环境模板 | 新增 `configs/however.env.example`，集中 Redis、Ollama、Gemini、AlloyDB、Tracing、Rate limit 等变量 | [configs/however.env.example](../configs/however.env.example) |
| 本地演示 | 新增 `docker-compose.local-demo.yml` 和 `make local-demo`，拉起本地 Redis/Ollama 并用 JSON catalog 启动助手服务 | [docker-compose.local-demo.yml](../docker-compose.local-demo.yml), [scripts/local-demo.sh](../scripts/local-demo.sh) |
| K8s 本地端点 | Kustomize component 覆盖 `REDIS_ADDR`、`OLLAMA_BASE_URL`、`VECTORSTORE_BACKEND=json` | [kustomize/components/local-endpoints/kustomization.yaml](../kustomize/components/local-endpoints/kustomization.yaml) |
| 运行时探针 | AI 服务新增 `/healthz`、`/readyz`、`/livez` 和 Prometheus `/metrics` | [src/shoppingassistantservice/shoppingassistantservice.py](../src/shoppingassistantservice/shoppingassistantservice.py) |

## 4. Shopping Assistant 新服务

上游 Online Boutique 的主链路是电商浏览、购物车、结算和推荐。本仓库新增 `shoppingassistantservice`，把 AI 购物助手作为独立服务接入前端。

新增能力：

- 前端增加 `/assistant` 页面和 `/bot` HTTP 转发入口。
- 助手支持文字需求和图片 URL/Base64 输入。
- Python Flask 服务提供请求校验、模型调用、商品检索、推荐 ID 规范化、健康检查和 Prometheus 指标。
- 前端可根据模型返回的 `[product_id]` 自动拉取商品元数据并展示商品卡片。
- 服务内置限流、重试、熔断和错误降级。

可核验文件：

- [src/frontend/templates/assistant.html](../src/frontend/templates/assistant.html)
- [src/frontend/handlers.go](../src/frontend/handlers.go)
- [src/shoppingassistantservice/shoppingassistantservice.py](../src/shoppingassistantservice/shoppingassistantservice.py)
- [src/shoppingassistantservice/model_client.py](../src/shoppingassistantservice/model_client.py)
- [src/shoppingassistantservice/retriever.py](../src/shoppingassistantservice/retriever.py)

## 5. Gemini/Ollama 可切换模型后端

`shoppingassistantservice` 通过 `MODEL_PROVIDER` 切换模型后端：

| 后端 | 使用场景 | 关键变量 |
|---|---|---|
| `gemini` | 云端 Gemini 推理，适合 GKE/AlloyDB/RAG 演示 | `MODEL_PROVIDER=gemini`, `GEMINI_VISION_MODEL`, `GEMINI_TEXT_MODEL`, `GOOGLE_API_KEY` |
| `ollama` | 本地或内网模型推理，适合离线演示和面试作品展示 | `MODEL_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_ALLOWED_HOSTS` |

安全与可靠性改造：

- `OLLAMA_ALLOWED_HOSTS` 限制可访问的 Ollama 主机，避免任意 URL 转发。
- 模型调用失败时返回保护模式文案，不让前端直接暴露异常堆栈。
- `MAX_RETRIES`、`RETRY_BACKOFF_SECONDS`、`CIRCUIT_BREAKER_*` 可调。

测试覆盖：

- Ollama endpoint/payload 契约。
- Gemini provider 契约。
- 模型失败降级。
- 健康检查和 readiness/liveness contract。

可核验文件：

- [src/shoppingassistantservice/tests/test_shoppingassistantservice_unit.py](../src/shoppingassistantservice/tests/test_shoppingassistantservice_unit.py)
- [src/shoppingassistantservice/tests/test_shoppingassistantservice_contract.py](../src/shoppingassistantservice/tests/test_shoppingassistantservice_contract.py)

## 6. JSON catalog fallback

上游商品目录默认来自本地 `products.json` 或云端扩展。本仓库把 fallback 显式做成 AI 服务质量策略：

- `productcatalogservice` 仍保留本地 `products.json` 作为商品目录基础数据。
- `shoppingassistantservice` 新增 `products.local.json`，用于本地 RAG-like 检索和 CI 测试。
- `VECTORSTORE_BACKEND=alloydb` 时会优先尝试 AlloyDB Vector Store。
- AlloyDB 配置不完整或初始化失败时，助手自动切换到 JSON catalog。
- JSON 检索会按 query token 与商品名称、描述、分类的重合度排序，返回可解释的候选商品。

可核验文件：

- [src/productcatalogservice/products.json](../src/productcatalogservice/products.json)
- [src/productcatalogservice/catalog_loader.go](../src/productcatalogservice/catalog_loader.go)
- [src/shoppingassistantservice/products.local.json](../src/shoppingassistantservice/products.local.json)
- [src/shoppingassistantservice/retriever.py](../src/shoppingassistantservice/retriever.py)

## 7. Kustomize 改造点

| 组件 | 作用 |
|---|---|
| `shopping-assistant` | 新增 AI 助手 Deployment、Service、ServiceAccount、Secret，并给 frontend 打开 `ENABLE_ASSISTANT=true` |
| `local-endpoints` | 将 Redis/Ollama/JSON catalog 指向本地演示依赖 |
| `shopping-assistant-canary` | 提供助手服务并行 canary 部署模板 |
| `network-policies` | 保留并增强微服务网络隔离实验 |
| `google-cloud-operations` | 保留云端可观测性路径 |

可核验文件：

- [kustomize/components/shopping-assistant/kustomization.yaml](../kustomize/components/shopping-assistant/kustomization.yaml)
- [kustomize/components/local-endpoints/kustomization.yaml](../kustomize/components/local-endpoints/kustomization.yaml)
- [tests/e2e/kustomize/kustomization.yaml](../tests/e2e/kustomize/kustomization.yaml)

## 8. Helm 改造点

Helm chart 保留上游多服务部署结构，并做了 however 化：

- Chart 名称与说明改为 `however-microservices-lab`。
- `values.yaml` 暴露镜像、资源、Redis、服务开关等配置。
- `shoppingAssistantService` 作为显式实验项保留，目前推荐通过 Kustomize component 启用，避免 Helm 路径和 AI/AlloyDB 路径发生双重维护。

可核验文件：

- [helm-chart/Chart.yaml](../helm-chart/Chart.yaml)
- [helm-chart/values.yaml](../helm-chart/values.yaml)
- [helm-chart/README.md](../helm-chart/README.md)

## 9. Terraform 改造点

Terraform 路径保留上游 GKE 部署能力，并加入 however 文档化和可选云依赖：

- 文档入口改为 `however-microservices-lab`。
- Memorystore Redis 可选，用于替换集群内 Redis。
- 仍可与 Kustomize/Skaffold 路径组合，用于展示从本地到 GKE 的部署迁移。

可核验文件：

- [terraform/README.md](../terraform/README.md)
- [terraform/memorystore.tf](../terraform/memorystore.tf)
- [terraform/variables.tf](../terraform/variables.tf)

## 10. CI 改造点

上游 CI 偏向 Google 自有 self-hosted runner 和 GKE staging。本仓库保留这种重部署路径，同时新增不依赖 self-hosted runner 的快速质量基线。

| 工作流 | 改造目的 |
|---|---|
| `quick-ci.yaml` | 在 `ubuntu-latest` 上跑 Go、Node、Python、Java 基础测试 |
| `shoppingassistant-quality-ci.yaml` | 专门保护 AI 助手的 ruff/mypy/pytest |
| `adservice-quality-ci.yaml` | 保护 Java 包名迁移后的 Gradle 测试和 PMD |
| `node-service-tests-ci.yaml` | 保护 Node 服务元信息和单测 |
| `repo-contract-ci.yml` | 保护仓库工程质量清单 |
| `ci-pr.yaml` / `ci-main.yaml` | 清理旧式 `::set-env`，改用 `$GITHUB_ENV` |

可核验文件：

- [.github/workflows/quick-ci.yaml](../.github/workflows/quick-ci.yaml)
- [.github/workflows/ci-pr.yaml](../.github/workflows/ci-pr.yaml)
- [.github/workflows/ci-main.yaml](../.github/workflows/ci-main.yaml)

## 11. 质量基线与演示证据

本仓库用以下材料证明改造是可运行、可测试、可交付的工程样板：

- 本地演示：`make local-demo`
- 快速多语言 CI：`.github/workflows/quick-ci.yaml`
- AI 助手测试：`src/shoppingassistantservice/tests/`
- kind + Skaffold smoke：`tests/e2e/kind_skaffold_smoke.sh`
- 性能基线模板：`docs/performance-baseline.md` 和 `reports/performance/baseline-latest.md`
- 发布说明草稿：`docs/releasing/ai-microservices-lab-baseline.md`

## 12. 一句话结论

`however-microservices-lab` 的核心差异不是名称，而是把 Online Boutique 从“电商微服务样例”扩展为“多语言微服务工程改造样板”：它同时覆盖 AI 服务集成、本地 Ollama 演示、JSON catalog fallback、Kubernetes 组件化部署、云资源路径、快速 CI 和性能基线。
