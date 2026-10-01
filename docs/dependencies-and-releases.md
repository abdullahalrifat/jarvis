# Core dependency and release policy

Jarvis consumes the published `jarvis-agent-core` package from PyPI. Core owns its own semantic versioning and release automation; Jarvis does not copy Core source or edit the Core version as part of normal feature work.

## Current coordinated release

Jarvis 0.9.7 consumes the immutable `jarvis-agent-core==0.16.1` release. Core 0.16.1 owns the provider-neutral empirical route calibration contract; Jarvis owns real workload definitions and task-level evaluation, while AI Stack owns runtime telemetry and provider execution.

## Update flow

```text
jarvis-core Conventional Commit
    -> reviewed release PR
    -> tagged GitHub release
    -> validated PyPI publication
    -> Dependabot detects new jarvis-agent-core
    -> Jarvis dependency PR
    -> Jarvis CI + review
```

The dependency remains pinned to the tested Core release in `pyproject.toml`. Dependabot is the mechanism that advances that pin, so version updates are reviewable and reproducible rather than hand-edited.

## Compatibility rule

A Core release is consumed only after it is published to PyPI. Jarvis CI must install the exact dependency selected by the dependency PR and run the complete test suite before merge.

For a breaking Core release, the dependency PR is intentionally reviewed as a compatibility change rather than silently widening the allowed version range.
