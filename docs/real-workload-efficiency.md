# Real workload efficiency benchmark

Jarvis owns the task-level workload corpus and quality evaluation. AI Stack owns runtime model telemetry, cost/latency accounting and empirical route calibration. `jarvis-core` remains provider-neutral and supplies reusable benchmark/calibration primitives.

Run the corpus through the normal benchmark runner and compare local-only, automatic and cloud-first routes using success rate, incorrect completions, tool failures, latency, input/output/cache tokens and estimated cost.

Do not change routing thresholds from a single observation. AI Stack applies a minimum sample count, quality floor and recency weighting before real workload evidence can change automatic routing.
