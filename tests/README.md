# Tests

This directory contains repository-level checks and end-to-end smoke tests.

## Repository Contract

```bash
bash tests/repo_contract_test.sh
```

## Kind + Skaffold Smoke Test

The e2e smoke test creates or reuses a local kind cluster, deploys the app with
the `e2e` Skaffold profile, and verifies the homepage, product page, cart,
checkout flow, and AI assistant route.

```bash
bash tests/e2e/kind_skaffold_smoke.sh
```

Useful overrides:

```bash
CLUSTER_NAME=however-e2e NAMESPACE=however-e2e FRONTEND_PORT=18080 \
  bash tests/e2e/kind_skaffold_smoke.sh
```
