# Engineering Quality Plan

This document defines the quality baseline and delivery policy for `however-yir/however-microservices-lab`.

## 1. Scope

- Repository: `however-yir/however-microservices-lab`
- Primary language: `Python`
- Baseline release tag: `health-baseline-2026-04-12`

## 2. Quality Gates

- Security scans: CodeQL + secret scanning workflows
- Dependency hygiene: Dependabot for GitHub Actions and detected ecosystems
- Contract checks: `tests/repo_contract_test.sh` in CI
- Build and test checks: existing project-specific workflows remain the source of truth

## 3. Test Strategy

- Contract layer: repository invariants (docs, security files, workflow presence)
- Project layer: language/framework tests already configured in existing CI
- Release layer: tag-based baseline validation for reproducible milestones

## 4. Pull Request Definition of Done

- CI pipelines pass
- Contract test passes
- Docs updated for behavior changes
- Security impact acknowledged for risky changes

## 5. Next Deepening Steps

- Add service-level integration tests for critical user journeys
- Add performance regression checks on core paths
- Track flaky tests and enforce deflaking SLA