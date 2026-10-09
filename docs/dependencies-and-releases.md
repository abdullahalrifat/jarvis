# Core dependency and release policy

Jarvis consumes the published `jarvis-agent-core` package from PyPI. Core owns its own semantic versioning and release automation; Jarvis does not copy Core source or edit the Core version as part of normal feature work.

## Current coordinated release

Jarvis 0.11.1 consumes the immutable `jarvis-agent-core==0.17.1` release. Core 0.17.1 provides the shared inference gateway client and provider-neutral routing/runtime contracts; Jarvis owns local workload execution and task-level evaluation, while AI Stack owns optional remote-run orchestration, persistence, telemetry and integrations.

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

The dependency remains pinned to the tested Core release in `pyproject.toml`. This PR advances the pin to published Core 0.17.1. The supported inference gateway target is `jarvis-inference` 0.3.1; deploy its immutable release image only after the `v0.3.1` tag workflow has published it. Future Core updates should remain reviewable and reproducible rather than widening the dependency range.

## Compatibility rule

A Core release is consumed only after it is published to PyPI. Jarvis CI must install the exact dependency selected by the dependency PR and run the complete test suite before merge.

For a breaking Core release, the dependency PR is intentionally reviewed as a compatibility change rather than silently widening the allowed version range.
