# 2026Q1 Execution Plan - however-microservices-lab

## Scope
- Complexity: complex
- Target commits: 20 (初始化 -> 核心功能 -> 修复 -> 测试 -> 文档/部署)
- Timebox: 2026-01-01 to 2026-03-28
- Planned issues: 8
- Planned PRs: 5

## Milestones
| Milestone | Window | Note |
|---|---|---|
| M1(1-3月) | 1-3月 | Q1执行主里程碑 |
| M2(4-7月) | 4-7月 | Q2-Q3扩展 |
| M3(8-10月) | 8-10月 | Q3深度优化 |
| M4(11-12月) | 11-12月 | 年度收口 |

## Issue Backlog (8)
| Issue | Title | Labels | Milestone | Month |
|---|---|---|---|---|
| #1 | Init-1 | type:feature, priority:P2, area:setup | M1(1-3月) | 2026-01 |
| #2 | Init-2 | type:feature, priority:P2, area:setup | M1(1-3月) | 2026-01 |
| #3 | Core-1 | type:feature, priority:P1, area:core | M1(1-3月) | 2026-02 |
| #4 | Core-2 | type:feature, priority:P1, area:core | M1(1-3月) | 2026-02 |
| #5 | Core-3 | type:feature, priority:P2, area:core | M1(1-3月) | 2026-03 |
| #6 | Fix-1 | type:bug, priority:P1, area:bugfix | M1(1-3月) | 2026-03 |
| #7 | Test-1 | type:test, priority:P2, area:qa | M1(1-3月) | 2026-03 |
| #8 | Docs-1 | type:docs, priority:P3, area:docs-deploy | M1(1-3月) | 2026-03 |

## PR Rhythm
- PR-1 (Initialization): Closes #1 #2
- PR-2 (Core Architecture): Closes #3
- PR-3 (Core Integration): Closes #4 #5
- PR-4 (Stability/Fix): Closes #6
- PR-5 (Test + Docs/Deploy): Closes #7 #8

## Commit Cadence
| # | 计划日期 | 阶段 | 建议提交信息 |
|---|---|---|---|
| C01 | 2026-01-03 | 初始化 | chore(init): bootstrap baseline part 1 |
| C02 | 2026-01-07 | 初始化 | chore(init): bootstrap baseline part 2 |
| C03 | 2026-01-11 | 初始化 | chore(init): bootstrap baseline part 3 |
| C04 | 2026-01-15 | 初始化 | chore(init): bootstrap baseline part 4 |
| C05 | 2026-01-20 | 初始化 | chore(init): bootstrap baseline part 5 |
| C06 | 2026-01-25 | 核心功能 | feat(core): deliver core capability slice 6 |
| C07 | 2026-01-30 | 核心功能 | feat(core): deliver core capability slice 7 |
| C08 | 2026-02-04 | 核心功能 | feat(core): deliver core capability slice 8 |
| C09 | 2026-02-09 | 核心功能 | feat(core): deliver core capability slice 9 |
| C10 | 2026-02-14 | 核心功能 | feat(core): deliver core capability slice 10 |
| C11 | 2026-02-19 | 核心功能 | feat(core): deliver core capability slice 11 |
| C12 | 2026-02-24 | 核心功能 | feat(core): deliver core capability slice 12 |
| C13 | 2026-03-01 | 修复 | fix(core): resolve regression and edge case 13 |
| C14 | 2026-03-06 | 修复 | fix(core): resolve regression and edge case 14 |
| C15 | 2026-03-10 | 修复 | fix(core): resolve regression and edge case 15 |
| C16 | 2026-03-14 | 测试 | test(core): add/adjust smoke and regression coverage 16 |
| C17 | 2026-03-18 | 测试 | test(core): add/adjust smoke and regression coverage 17 |
| C18 | 2026-03-21 | 测试 | test(core): add/adjust smoke and regression coverage 18 |
| C19 | 2026-03-24 | 文档/部署 | docs(deploy): finalize docs and release checklist 19 |
| C20 | 2026-03-28 | 文档/部署 | docs(deploy): finalize docs and release checklist 20 |
