# Core dependency and release policy

Jarvis consumes the published `jarvis-agent-core` package from PyPI. Core owns its own semantic versioning and release automation; Jarvis does not copy Core source or edit the Core version as part of normal feature work.

## Current coordinated release

Jarvis 0.11.4 consumes the immutable `jarvis-agent-core==0.17.3` release. Core 0.17.3 provides the shared inference gateway client and provider-neutral routing/runtime contracts. Jarvis owns local workload execution and task-level evaluation; AI Stack independently owns its own remote orchestration, persistence, telemetry and integrations. Neither application calls the other.

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

The dependency remains pinned to the tested Core release in `pyproject.toml`. This PR advances the pin to published Core 0.17.3. `jarvis-inference` is a separately deployed HTTP service, not a Python dependency of the CLI. Verify the deployed source commit or image digest and API compatibility. A published release is required only when deploying a prebuilt release image; source-based deployments do not need a tag solely to satisfy the version reference. Future Core updates should remain reviewable and reproducible rather than widening the dependency range.

## Compatibility rule

A Core release is consumed only after it is published to PyPI. Jarvis CI must install the exact dependency selected by the dependency PR and run the complete test suite before merge.

For a breaking Core release, the dependency PR is intentionally reviewed as a compatibility change rather than silently widening the allowed version range.
