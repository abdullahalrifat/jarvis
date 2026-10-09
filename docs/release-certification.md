# Jarvis release certification

Current coordinated line: **Jarvis 0.11.3 with Jarvis Core 0.17.2**. Verify the published CLI/Core package pins, the deployed inference source commit or image digest, API compatibility, and exact commit SHA before certifying any deployment.

## Automated gates

- Python 3.10, 3.12 and 3.13 validation;
- black and critical Ruff checks;
- pytest with the 70% coverage floor;
- package build and clean-wheel installation;
- immutable Core 0.17.2 release/checksum verification;
- cross-repository Core protocol conformance;
- real-repository benchmark harness;
- adversarial prompt-injection and secret-canary regression coverage;
- long-running worker/lease/heartbeat chaos coverage;
- per-task sandbox policy validation.

## Evidence and completion

A successful model response is not proof. Completion claims should be backed by real command/test/tool observations and, where applicable, independently verified results. The Core `EvidenceLedger`/`EvidenceGate` contracts are available for this purpose; consumer integration must translate the local proof ledger into those contracts before treating them as a completion gate.

## Security certification

Run adversarial cases against repository content, web pages, browser content, MCP responses, Skills and Hooks. Secret-canary values must never appear in tool output, proof records or telemetry. Test bearer credentials, provider keys, cookies, authorization headers and assignment-style secrets separately.

## Cloud certification

For Server-backed work, certify lease fencing, stale-worker rejection, cancellation races, worker restart, database/network failures and idempotent submission. Fencing is not equivalent to per-task process isolation. Shared-host execution requires the consumer-enforced sandbox/resource/egress policy to be enabled and validated.

## World-class certification

CI passing establishes software-contract health, not model quality or universal production readiness. The current release line has executable regression, security, real-repository evaluation and chaos coverage. Remaining certification work is primarily retained longitudinal benchmark results, model-quality measurement across the target local models, full offline/bootstrap reproducibility, backup/restore validation and hardware-specific soak testing.
