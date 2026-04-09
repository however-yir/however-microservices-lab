# 测试与质量保障

本文档用于统一 `however-microservices-lab` 的本地与 CI 检测入口。

## 1. 环境要求

- Java: 21（`adservice`）
- Node.js: 20（建议读取仓库根目录 `.nvmrc`）
- Python: 3.11+（`shoppingassistantservice`）

## 2. 一键执行

```bash
bash scripts/checks/run_all_checks.sh
```

可选参数：

- `USE_VENV=1`（默认）：创建 `.venv-checks` 运行 Python 检查。
- `PYTHON_BIN=python3.11`：指定 Python 可执行程序。

示例：

```bash
USE_VENV=1 PYTHON_BIN=python3.11 bash scripts/checks/run_all_checks.sh
```

## 3. 分服务执行

### 3.1 Java（AdService）

```bash
cd src/adservice
chmod +x gradlew
./gradlew test pmdMain
```

### 3.2 Node（Currency/Payment）

```bash
cd src/currencyservice && npm ci && npm test
cd src/paymentservice && npm ci && npm test
```

### 3.3 Python（Shopping Assistant）

```bash
cd src/shoppingassistantservice
python3 -m pip install -r requirements.txt
python3 -m ruff check .
python3 -m mypy shoppingassistantservice.py
python3 -m pytest
```

## 4. CI 对应关系

- `.github/workflows/adservice-quality-ci.yaml`
- `.github/workflows/node-service-tests-ci.yaml`
- `.github/workflows/shoppingassistant-quality-ci.yaml`
- `.github/workflows/security-image-scan-ci.yaml`
- `.github/workflows/sbom-ci.yaml`

## 5. 已知事项

- Node 本地版本若高于 20（如 24），`@google-cloud/profiler` 可能缺少预编译二进制。
- 仓库已将 profiler 设为可选依赖并增加容错启动，不影响主流程测试。
