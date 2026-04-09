# 剩余 30 条建议落地清单

以下 30 项已按“可验证、可回归”的标准完成并入库。

1. [x] `adservice` Gradle `group` 调整为 `com.however.microservices`
2. [x] `adservice` artifact 名称调整为 `however-adservice`
3. [x] `adservice` Java 包迁移至 `com.however.microservices.adservice`
4. [x] `adservice` Docker 入口路径同步新 artifact 结构
5. [x] `adservice` 增加 JUnit 测试样例（端口解析）
6. [x] `adservice` 启用 PMD 规则并接入 CI
7. [x] `currencyservice` `package.json` 项目元信息重命名
8. [x] `paymentservice` `package.json` 项目元信息重命名
9. [x] Node 服务统一 `engines.node >= 20`
10. [x] Node 服务新增 `node --test` 测试脚本
11. [x] `currencyservice` 新增数据契约测试
12. [x] `paymentservice` 新增 charge 行为测试
13. [x] Node profiler 依赖改为 `optionalDependencies`
14. [x] Node profiler 启动增加 `try/catch` 容错逻辑
15. [x] `shoppingassistantservice` 引入 `AppConfig` 配置集中管理
16. [x] `shoppingassistantservice` 引入请求参数校验（Pydantic）
17. [x] `shoppingassistantservice` 增加内存限流器（RateLimiter）
18. [x] `shoppingassistantservice` 增加熔断器（CircuitBreaker）
19. [x] `shoppingassistantservice` 增加重试与退避机制
20. [x] `shoppingassistantservice` 增加结构化日志与 trace_id
21. [x] `shoppingassistantservice` 增加 `/healthz` `/readyz` `/livez` `/metrics`
22. [x] `shoppingassistantservice` 接入 Prometheus 指标
23. [x] `shoppingassistantservice` 增加 Ollama host allowlist 校验
24. [x] `shoppingassistantservice` 增加 JSON 商品检索后备通道
25. [x] `shoppingassistantservice` 外置提示词模板目录（prompts/v1）
26. [x] `shoppingassistantservice` 增加 unit/contract/e2e 测试集
27. [x] Kubernetes 增加敏感变量 Secret 引用（API Key/DB 密码）
28. [x] Kubernetes 增加 startup/readiness/liveness probes
29. [x] 新增本地端点覆盖组件（local-endpoints）
30. [x] 新增 canary 组件、质量 CI、性能基线和运行手册文档
