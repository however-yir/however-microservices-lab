# Interview Notes

## One-Minute Pitch

`however-microservices-lab` is a cloud-native microservices and AI integration lab based on Google Online Boutique, extended with an AI Shopping Assistant, Ollama/Gemini provider switching, JSON catalog fallback, Kubernetes deployment paths, and multi-language quality checks.

## What It Proves

- AI functionality is integrated into an existing multi-service system instead of being isolated in a standalone demo.
- The repository covers Go, Python, Node.js, Java, and C# services with visible CI entry points.
- Kubernetes deployment is represented through raw manifests, Kustomize, Skaffold, Helm, and Terraform documentation.
- The assistant can run locally with JSON fallback and mock/local model paths, which makes the demo reproducible.
- The upstream-difference documentation makes it clear what comes from Online Boutique and what was changed.

## Best Technical Story

The strongest story is the introduction of `shoppingassistantservice` without hiding the original microservices architecture. The AI path has to coexist with frontend routing, product catalog data, local model configuration, health checks, metrics, fallback behavior, and Kubernetes deployment mechanics.

## Tradeoffs To Explain

- This is intentionally a lab: it values breadth across microservices, deployment, and AI integration over one polished SaaS product surface.
- Some infrastructure paths are experimental and documented separately so the main demo can stay runnable.
- Local JSON fallback is a reliability choice for demonstration, not a replacement for production vector infrastructure.

## Validation Path

```bash
make local-demo
make check-python
make check-node
make check-java
bash tests/repo_contract_test.sh
```

## Follow-Up Ideas

- Keep one short "green path" CI badge in the README and move secondary workflows into docs.
- Add a small performance baseline artifact for assistant latency and fallback behavior.
- Add a short architecture decision record for Ollama/Gemini/provider switching.
