# Jarvis release certification

Current coordinated line: Jarvis 0.9.2 with Jarvis Core 0.9.4.

## Automated gates

- Python 3.10, 3.12 and 3.13 validation;
- black and critical Ruff checks;
- pytest with the 70% coverage floor;
- package build and clean-wheel installation;
- immutable Core 0.9.4 checksum verification;
- cross-repository Core protocol conformance.

## Evidence and completion

A successful model response is not proof. Completion claims should be backed by real command/test/tool observations and, where applicable, independently verified results. The Core `EvidenceLedger`/`EvidenceGate` contracts are available for this purpose; consumer integration must translate the local proof ledger into those contracts before treating them as a completion gate.

## Security certification

Run adversarial cases against repository content, web pages, browser content, MCP responses, Skills and Hooks. Secret-canary values must never appear in tool output, proof records or telemetry. Test bearer credentials, provider keys, cookies, authorization headers and assignment-style secrets separately.

## Cloud certification

For Server-backed work, certify lease fencing, stale-worker rejection, cancellation races, worker restart, database/network failures and idempotent submission. Fencing is not equivalent to per-task process isolation.

## World-class certification

CI passing establishes software-contract health, not model quality or production readiness. Release certification additionally requires retained real-repository benchmarks, red-team results, chaos/soak results, cloud isolation/resource limits and deterministic environment/bootstrap validation.
