# Jarvis CLI certification evidence

Every release candidate must retain evidence tied to the exact Git SHA and the exact published jarvis-agent-core pin.

Record:

- Python matrix results, package build and clean-wheel install results;
- repository benchmark corpus revision, number of tasks, task success and incorrect-completion counts;
- evidence/proof verification results, including independent evidence identity checks;
- prompt-injection and secret-canary results for repository files, web content, MCP, Skills, Hooks and attachments;
- inference endpoint, model ID, latency and timeout/cancellation behavior without storing credentials or prompt secrets;
- command sandbox policy and a record of isolation capabilities actually enforced;
- exact Core package version, model manifest and runtime environment.

Do not call the CLI production-ready based on synthetic unit tests alone. Retain real-repository benchmark results and target-host isolation/soak evidence. A model's assertion of completion is not evidence; require observable changes and independent verification appropriate to the task.
