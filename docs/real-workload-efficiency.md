# Real workload efficiency benchmark

Jarvis owns local runtime observations, the task-level workload corpus and quality evaluation. AI Stack owns telemetry, cost/latency accounting and empirical calibration for server-side Runs. Each consumer adapts its own measurements to the provider-neutral `jarvis-core` observation/calibration primitives.

Run the corpus through the normal benchmark runner and compare local-only, automatic and cloud-first routes using success rate, incorrect completions, tool failures, latency, input/output/cache tokens and estimated cost.

Do not change routing thresholds from a single observation. AI Stack applies a minimum sample count, quality floor and recency weighting before real workload evidence can change automatic routing.
