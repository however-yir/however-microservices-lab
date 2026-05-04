# However Microservices Lab Evidence Pack

This pack collects the shortest public proof path for reviewing the cloud-native AI microservices lab.

## Runtime Evidence

- Local demo: `docs/local-demo.md`
- Main CI: `.github/workflows/ci-main.yaml`
- Quick CI: `.github/workflows/quick-ci.yaml`
- SBOM workflow: `.github/workflows/sbom-ci.yaml`
- Image scan workflow: `.github/workflows/security-image-scan-ci.yaml`
- Baseline release: `AI Matrix Baseline 2026.05`
- Release: `v0.1.0 - AI Microservices Lab Baseline`

## Product And Architecture Evidence

- Architecture diagram: `docs/img/however-architecture.svg`
- Service architecture image: `docs/img/architecture-diagram.png`
- Frontend screenshot: `docs/img/frontend-screenshot.svg`
- Assistant screenshot: `docs/img/assistant-screenshot.svg`
- Engineering quality: `docs/ENGINEERING_QUALITY.md`
- CI workflows guide: `docs/ci-workflows.md`
- Local demo guide: `docs/local-demo.md`

## Verification Checklist

- Run the local demo path and confirm services boot.
- Check the shopping assistant fallback and model-provider configuration.
- Run or inspect the quick CI path.
- Review Kubernetes/Skaffold documentation for deployment evidence.
- Review SBOM and image scan workflows.
- Open the latest GitHub Actions run and confirm the core workflows are green.
