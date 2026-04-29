# Release Notes: AI microservices lab baseline

Suggested tag: `ai-microservices-lab-baseline`

## Headline

AI microservices lab baseline: multi-language cloud-native services with Kubernetes deployment paths and switchable Gemini/Ollama shopping assistant.

## Highlights

- Repositions the repo as `however-microservices-lab`, a cloud-native microservices and AI integration lab derived from Google Online Boutique.
- Adds `shoppingassistantservice`, a Python AI shopping assistant with Gemini/Ollama provider switching.
- Adds JSON catalog fallback for local demos and degraded operation when AlloyDB or model backends are unavailable.
- Adds `make local-demo` for local Redis + Ollama + JSON catalog assistant health checks.
- Adds kind + Skaffold + Kustomize smoke path for full local Kubernetes validation.
- Adds `ubuntu-latest` quick multi-language CI for Go, Node.js, Python and Java.
- Cleans deprecated GitHub Actions `::set-env` usage from legacy PR/Main workflows.
- Documents Kustomize, Helm, Terraform, CI and performance baseline differences from upstream.

## Validation Checklist

- `make local-demo`
- `make check-python`
- `make check-node`
- `make check-java`
- `bash tests/repo_contract_test.sh`
- `make check-e2e` when Docker, kind, kubectl and skaffold are available

## Release Body Draft

````markdown
# AI microservices lab baseline

This release establishes however-microservices-lab as a cloud-native microservices + AI integration baseline rather than a simple Online Boutique rename.

Key additions:

- Multi-language service matrix covering Go, Python, Node.js, Java and C#.
- AI Shopping Assistant integrated through the frontend and a standalone Python service.
- Gemini/Ollama model provider switching.
- JSON catalog fallback for local and CI-friendly operation.
- Local Redis + Ollama + JSON demo via `make local-demo`.
- Kubernetes deployment paths through raw manifests, Kustomize, Skaffold, Helm and Terraform.
- Fast `ubuntu-latest` CI across Go, Node, Python and Java.
- Upstream diff documentation in `docs/diff-from-upstream.md`.

Recommended first checks:

```bash
make local-demo
make check-python
bash tests/repo_contract_test.sh
```
````
