# GitHub Actions Workflows

This page describes the CI/CD workflows for `however-microservices-lab`.

## Infrastructure

The default quality gate is [quick-ci.yaml](quick-ci.yaml), which runs on `ubuntu-latest` and does not require self-hosted runners.

The legacy PR/Main deployment workflows are still present for GKE staging scenarios that need Google Cloud credentials and self-hosted runner capacity. They should be treated as optional release/deployment infrastructure, not as the baseline contributor CI.

## Workflows

**Note**: `quick-ci.yaml` works for ordinary pull requests. Legacy deploy workflows that stage into GKE still require repository secrets and trusted runner access.

### Quick Multi-Language CI - [quick-ci.yaml](quick-ci.yaml)

Runs on `ubuntu-latest` for pull requests, pushes to `main`, and manual dispatch. It covers:

1. Go unit tests for `frontend`, `productcatalogservice`, `shippingservice` and `checkoutservice`.
2. Node.js tests for `currencyservice` and `paymentservice`.
3. Python ruff/mypy/pytest for `shoppingassistantservice`.
4. Java Gradle tests and PMD for `adservice`.

### Code Tests - [ci-pr.yaml](ci-pr.yaml)

These legacy tests run on self-hosted runners and are kept for cloud staging compatibility.


### Deploy Tests- [ci-pr.yaml](ci-pr.yaml)

These tests run on every commit for every open PR, as well as any commit to main / any release branch. This workflow:

1. Creates a dedicated GKE namespace for that PR, if it doesn't already exist, in the PR GKE cluster.
2. Uses `skaffold run` to build and push the images specific to that PR commit. Then skaffold deploys those images, via `kubernetes-manifests`, to the PR namespace in the test cluster.
3. Tests to make sure all the pods start up and become ready.
4. Gets the LoadBalancer IP for the frontend service.
5. Comments that IP in the pull request, for staging.

### Push and Deploy Latest - legacy upstream reference

The original upstream project included a push-and-deploy workflow for publishing `latest` images. In however-microservices-lab, production publishing should be treated as a release-specific decision rather than the default contributor path.

### Cleanup - [cleanup.yaml](cleanup.yaml)

This workflow runs when a PR closes, regardless of whether it was merged into main. This workflow deletes the PR-specific GKE namespace in the test cluster.

## Appendix - Legacy self-hosted runners

Should one of the two self-hosted Github Actions runners (GCE instances) fail, or you want to add more runner capacity, this is how to provision a new runner. Note that you need IAM access to the admin Online Boutique GCP project in order to do this.

1. Create a GCE instance.
    - VM should be at least n1-standard-4 with 50GB persistent disk
    - VM should use custom service account with permissions to: access a GKE cluster, create GCS storage buckets, and push to GCR.
2. SSH into new VM through the Google Cloud Console.
3. Install project-specific dependencies, including go, docker, skaffold, and kubectl:

```
wget -O - https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/.github/workflows/install-dependencies.sh | bash
```

The instance will restart when the script completes in order to finish the Docker install.

4. SSH back into the VM.

5. Follow the instructions to add a new runner on the [Actions Settings page](https://github.com/GoogleCloudPlatform/microservices-demo/settings/actions) to authenticate the new runner
6. Start GitHub Actions as a background service:
```
sudo ~/actions-runner/svc.sh install ; sudo ~/actions-runner/svc.sh start
```
