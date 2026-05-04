# however-microservices-lab

<p align="center">
  <img src="docs/img/however-logo.svg" width="340" alt="however logo" />
</p>

`however-microservices-lab` 是一个”云原生微服务 + AI 集成实验室”。它基于 Google Online Boutique 的多语言微服务样例继续改造，但核心目标已经从”电商 demo”升级为”可展示工程能力的微服务改造样板”：AI Shopping Assistant、本地 Ollama、JSON catalog fallback、Kubernetes 部署、多语言服务测试和 CI 基线都放在同一个仓库里。

> **Based on [GoogleCloudPlatform/microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo) (Online Boutique), extended with:**
> AI Shopping Assistant (Gemini/Ollama) · Local Ollama Demo · JSON Catalog Fallback · Kustomize Components · `ubuntu-latest` CI · Namespace Migration

<p align="center">
  <img src="https://img.shields.io/badge/AI-Gemini%20%7C%20Ollama-0b66d7" alt="AI backends" />
  <img src="https://img.shields.io/badge/Runtime-Kubernetes-22c55e" alt="Kubernetes" />
  <img src="https://img.shields.io/badge/Protocols-gRPC%20%2B%20HTTP-f59e0b" alt="Protocols" />
  <img src="https://img.shields.io/badge/Services-Go%20Python%20Node%20Java%20C%23-f59e0b" alt="languages" />
  <img src="https://img.shields.io/badge/CI-ubuntu--latest-64748b" alt="quick ci" />
  <br/>
  <img src="https://github.com/however-yir/however-microservices-lab/actions/workflows/quick-ci.yaml/badge.svg" alt="Quick CI">
  <img src="https://github.com/however-yir/however-microservices-lab/actions/workflows/shoppingassistant-quality-ci.yaml/badge.svg" alt="AI Assistant Quality">
</p>

## 首屏重点

| 能力 | 入口 | 说明 |
|---|---|---|
| AI Shopping Assistant | `src/shoppingassistantservice` + `/assistant` | Python Flask 助手服务接入 Go frontend，支持文本/图片输入、商品 ID 推荐、健康检查、指标、限流、熔断和降级 |
| 本地 Ollama 演示 | `make local-demo` | 本地 Redis + Ollama + JSON 商品数据，快速验证 `MODEL_PROVIDER=ollama` 和 `VECTORSTORE_BACKEND=json` |
| Kubernetes 部署 | `skaffold run` / `make check-e2e` | 原生 manifests、Kustomize components、kind smoke、Skaffold 构建部署 |
| 多语言工程矩阵 | Go / Python / Node.js / Java / C# | 保留电商主链路，同时补 AI 服务、质量测试和 CI 现代化 |

![however architecture](docs/img/however-architecture.svg)

| Frontend | AI assistant |
|---|---|
| ![frontend screenshot](docs/img/frontend-screenshot.svg) | ![assistant screenshot](docs/img/assistant-screenshot.svg) |

## 矩阵角色

`however-microservices-lab` 是 however-yir AI 工程作品矩阵中的“云原生微服务 + AI 集成实验室”，负责展示多语言微服务、Kubernetes/Skaffold/Kustomize、gRPC/HTTP、AI Shopping Assistant、Ollama/Gemini 切换和本地降级链路。完整项目矩阵见 [docs/project-matrix.md](docs/project-matrix.md)。

## 快速开始

### 1. 本地 AI 演示

```bash
make local-demo
curl -sS http://127.0.0.1:18081/healthz
```

需要真实 Ollama 推理时再拉模型：

```bash
LOCAL_DEMO_PULL_MODEL=1 make local-demo
curl -sS \
  -H "Content-Type: application/json" \
  -d '{"message":"Recommend warm lighting for a small reading corner","image":""}' \
  http://127.0.0.1:18081/
```

停止：

```bash
make local-demo-stop
```

完整说明见 [docs/local-demo.md](docs/local-demo.md)。

### 2. 本地 Kubernetes smoke

```bash
make check-e2e
```

该路径使用 kind + Skaffold + Kustomize，启用 AI assistant 和 mock Ollama，覆盖首页、商品页、加购、结算和 `/bot` 助手请求。手动步骤见 [docs/kind-skaffold-kustomize.md](docs/kind-skaffold-kustomize.md)。

### 3. 默认 Kubernetes 部署

```bash
skaffold run
kubectl port-forward deployment/frontend 8080:8080
```

访问 `http://127.0.0.1:8080`。

## 多语言服务矩阵

| 服务 | 语言 | 职责 | 改造重点 |
|---|---|---|---|
| `frontend` | Go | Web 入口、页面渲染、购物助手转发 | `/assistant`、`/bot`、商品元数据卡片 |
| `shoppingassistantservice` | Python | AI 购物助手 | Gemini/Ollama、JSON/AlloyDB 检索、healthz、metrics、fallback |
| `productcatalogservice` | Go | 商品目录 | JSON catalog、本地/AlloyDB 数据路径 |
| `cartservice` | C# | 购物车 | Redis/外部存储切换 |
| `checkoutservice` | Go | 结算编排 | gRPC 调用链和金额计算测试 |
| `paymentservice` | Node.js | 支付模拟 | Node 20、包元信息和基础测试 |
| `currencyservice` | Node.js | 汇率转换 | Node 20、汇率数据测试 |
| `shippingservice` | Go | 运费模拟 | Go 单测 |
| `emailservice` | Python | 邮件模拟 | Python gRPC 服务 |
| `recommendationservice` | Python | 商品推荐 | Python gRPC 服务 |
| `adservice` | Java | 广告推荐 | `com.however.microservices` 包迁移、Gradle/PMD |
| `loadgenerator` | Python | 性能流量 | Locust baseline |

## AI 助手设计

```mermaid
flowchart LR
  U["Browser / assistant page"] --> F["frontend /bot"]
  F --> SA["shoppingassistantservice"]
  SA --> M{"MODEL_PROVIDER"}
  M --> G["Gemini"]
  M --> O["Ollama"]
  SA --> R{"VECTORSTORE_BACKEND"}
  R --> A["AlloyDB vector store"]
  R --> J["JSON catalog fallback"]
  SA --> H["/healthz /readyz /livez /metrics"]
```

关键配置：

| 变量 | 作用 |
|---|---|
| `MODEL_PROVIDER=gemini\|ollama` | 切换云端 Gemini 或本地 Ollama |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | 本地模型端点和模型名 |
| `OLLAMA_ALLOWED_HOSTS` | 限制可访问的 Ollama host |
| `VECTORSTORE_BACKEND=alloydb\|json` | 切换 AlloyDB 向量检索或 JSON fallback |
| `PRODUCT_CATALOG_JSON` | JSON 商品数据路径 |
| `MAX_RETRIES` / `CIRCUIT_BREAKER_*` | 错误重试和降级保护 |

## 部署路径

| 路径 | 入口 | 场景 |
|---|---|---|
| Local demo | `make local-demo` | 本机 Redis/Ollama/JSON 助手演示 |
| Raw manifests | `kubernetes-manifests/` | 最小 Kubernetes 部署 |
| Kustomize | `kustomize/components/*` | AI assistant、local endpoints、network policies、cloud operations 等组合 |
| Skaffold | `skaffold.yaml` | 本地或 GKE 构建部署 |
| Helm | `helm-chart/` | 实验性 Helm 部署路径 |
| Terraform | `terraform/` | GKE + 可选 Memorystore 基础设施 |

## 与上游的差异

完整证据链见 [docs/diff-from-upstream.md](docs/diff-from-upstream.md)。摘要如下：

| 维度 | 上游 (Google Online Boutique) | however 改造 |
|---|---|---|
| 定位 | 电商微服务 demo | 云原生微服务 + AI 集成实验室 |
| AI 服务 | 无 | `shoppingassistantservice`（Gemini/Ollama 切换） |
| 本地演示 | 无 | `make local-demo`（Redis + Ollama + JSON catalog） |
| 向量检索 | 无 | AlloyDB / JSON catalog fallback |
| Java 包名 | `hipstershop.*` | `com.however.microservices.*` |
| CI | 仅 self-hosted + GKE | 新增 `ubuntu-latest` 快速多语言 CI |
| 部署路径 | 原生 manifests + Skaffold | + Kustomize components + Helm + Terraform |

- 明确保留 Google Online Boutique 的 Apache-2.0 来源和多语言微服务基线。
- 新增本地 Redis + Ollama + JSON 演示路径。
- 增强 Kustomize components、Helm/Terraform 文档、kind smoke、loadgenerator 性能基线。
- 清理旧式 `::set-env`，改用 `$GITHUB_ENV`。

## 质量与 CI

本地快速检查：

```bash
make check-python
make check-node
make check-java
bash tests/repo_contract_test.sh
```

完整聚合入口：

```bash
make check-all
```

CI 入口：

- [.github/workflows/quick-ci.yaml](.github/workflows/quick-ci.yaml)：Go、Node、Python、Java 基础测试，运行在 `ubuntu-latest`。
- [.github/workflows/shoppingassistant-quality-ci.yaml](.github/workflows/shoppingassistant-quality-ci.yaml)：AI 助手 ruff/mypy/pytest。
- [.github/workflows/repo-contract-ci.yml](.github/workflows/repo-contract-ci.yml)：仓库质量契约。

## 性能基线

生成模板：

```bash
./scripts/perf/generate_baseline_report.sh reports/performance/baseline-latest.md
```

运行 `loadgenerator`：

```bash
skaffold run --module loadgenerator
kubectl logs -l app=loadgenerator -f
```

说明见 [docs/performance-baseline.md](docs/performance-baseline.md)。

## Release baseline

本仓库的第一条建议发布线是 `AI microservices lab baseline`，突出：

- 多语言微服务工程改造能力
- Kubernetes/Skaffold/Kustomize 部署能力
- Gemini/Ollama AI 服务集成能力
- JSON fallback 和错误降级质量能力

Release note 草稿见 [docs/releasing/ai-microservices-lab-baseline.md](docs/releasing/ai-microservices-lab-baseline.md)。

## 协议

- 上游协议：[LICENSE](LICENSE)
- however 衍生说明：[LICENSE-HOWEVER.md](LICENSE-HOWEVER.md)
