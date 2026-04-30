# GitHub Actions Workflows

This page describes the CI/CD workflows for `however-microservices-lab`.

## Infrastructure

The default quality gate is [quick-ci.yaml](../.github/workflows/quick-ci.yaml), which runs on `ubuntu-latest` and does not require self-hosted runners.

The legacy PR/Main deployment workflows are still present for GKE staging scenarios that need Google Cloud credentials and self-hosted runner capacity. They should be treated as optional release/deployment infrastructure, not as the baseline contributor CI.

## Workflows

**Note**: `quick-ci.yaml` works for ordinary pull requests. Legacy deploy workflows that stage into GKE still require repository secrets and trusted runner access.

### Quick Multi-Language CI - [quick-ci.yaml](../.github/workflows/quick-ci.yaml)

Runs on `ubuntu-latest` for pull requests, pushes to `main`, and manual dispatch. It covers:

1. Go unit tests for `frontend`, `productcatalogservice`, `shippingservice` and `checkoutservice`.
2. Node.js tests for `currencyservice` and `paymentservice`.
3. Python ruff/mypy/pytest for `shoppingassistantservice`.
4. Java Gradle tests and PMD for `adservice`.

### Legacy GKE PR Staging - [ci-pr.yaml](../.github/workflows/ci-pr.yaml)

This workflow is manual-only. It still uses self-hosted runners and the historical GKE staging cluster, so it is kept for cloud staging compatibility rather than baseline PR quality gates.

### Deploy Tests - [ci-pr.yaml](../.github/workflows/ci-pr.yaml)

These tests run only through `workflow_dispatch`. This workflow:

1. Creates a dedicated GKE namespace for that PR, if it doesn't already exist, in the PR GKE cluster.
2. Uses `skaffold run` to build and push the images specific to that PR commit. Then skaffold deploys those images, via `kubernetes-manifests`, to the PR namespace in the test cluster.
3. Tests to make sure all the pods start up and become ready.
4. Gets the LoadBalancer IP for the frontend service.
5. Comments that IP in the pull request, for staging.

### Push and Deploy Latest - legacy upstream reference

The original upstream project included a push-and-deploy workflow for publishing `latest` images. In however-microservices-lab, production publishing should be treated as a release-specific decision rather than the default contributor path.

### Cleanup - [cleanup.yaml](../.github/workflows/cleanup.yaml)

This workflow runs when a PR closes, regardless of whether it was merged into main. This workflow deletes the PR-specific GKE namespace in the test cluster.
