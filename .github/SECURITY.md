# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < main  | :x:                |

## Reporting a Vulnerability

To report a security issue, please use [g.co/vulnz](https://g.co/vulnz).

The Google Security Team will respond within 5 working days of your report on g.co/vulnz.

We use g.co/vulnz for our intake, and do coordination and disclosure here using GitHub Security Advisory to privately discuss and fix the issue.

**Do not open a public GitHub issue for security vulnerabilities.**

## Security Measures

This project implements the following security controls:

### SQL Injection Defense
- `ValidateSQLIdentifier()` enforces regex validation + whitelist for all SQL table identifiers
- `pgx.Identifier.Sanitize()` provides proper identifier quoting for database queries
- Unit tests cover injection payloads (semicolon, comment, unicode, schema-prefix)

### Container Security Scanning
- Trivy scans all container images for HIGH/CRITICAL CVEs on every push to `main` and `release/**`
- PR scans are advisory (report-only) to avoid blocking development
- Dependabot keeps `trivy-action` up to date

### Kubernetes Hardening
- `seccompProfile: RuntimeDefault` enabled by default in Helm values
- NetworkPolicy support available (set `networkPolicies.create: true` for production)
- SecurityContext enabled by default
- Secret management guidance in `helm-chart/values.yaml` (use External Secrets Operator, not plain env vars)

### Dependency Management
- Dependabot configured for GitHub Actions
- Regular CVE patching across Go, Java, Node.js, and Python services
