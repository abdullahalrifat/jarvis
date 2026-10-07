# Changelog

## 0.10.4

- Make AI Stack the default control plane for normal bare-command and server-backed Jarvis work.
- Route normal inference through AI Stack -> jarvis-inference; keep direct model access explicitly local/diagnostic.
- Make `jarvis model-doctor` validate the end-to-end AI Stack model path and advertised concrete model ID.
- Add regression coverage for bare-command routing and the current AI Stack architecture.
- Align installation and model documentation with the production service boundary.

## 0.10.3

- Make AI Stack the primary control plane for normal Jarvis server-backed work.
- Use the dedicated inference gateway only behind AI Stack for normal operation.

## 0.10.2

- Send concrete model IDs to AI Stack instead of the removed `orchestrator` selector.
- Default the AI Stack integration to `qwen3:1.7b`, while allowing `JARVIS_MODEL` to override it.
- Align CLI tests with the concrete model-selector contract.

