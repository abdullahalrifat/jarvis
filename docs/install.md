# Installing Jarvis

Jarvis is distributed in two forms:

1. **PyPI package** — recommended for developer machines. Install with `pipx` or `pip` and run `jarvis` from any directory.
2. **Standalone executable** — recommended for machines where Python is not desired. Download a release binary and run it directly.

## Current release: 0.11.0

Jarvis 0.11.0 makes bare tasks local-first: the CLI runs the agent loop and tools locally and calls `jarvis-inference` directly for model requests. AI Stack remains an optional remote control plane. The inference URL includes `/v1`; AI Stack's API root does not.

## PyPI installation

### pipx (recommended)

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install jarvis-agent-cli
jarvis --version
```

Upgrade:

```bash
pipx upgrade jarvis-agent-cli
```

Remove:

```bash
pipx uninstall jarvis-agent-cli
```

### pip

Use an existing virtual environment when possible:

```bash
python3 -m pip install jarvis-agent-cli
jarvis --version
```

Upgrade with `python3 -m pip install --upgrade jarvis-agent-cli`.

## Standalone releases

Each tagged release publishes binaries for:

- Linux amd64
- macOS arm64
- Windows amd64

The release also contains SHA256 checksums and build-provenance attestations.

Download the correct executable from the GitHub Releases page, then on Linux/macOS:

```bash
chmod +x ./jarvis-*
./jarvis-* --version
```

On Windows, run the `.exe` from PowerShell or Command Prompt.

## Configuration

For normal local repository work, configure the dedicated inference gateway:

```bash
export INFERENCE_BASE_URL=http://<inference-vm-ip>:8080/v1
export INFERENCE_API_KEY=<your-inference-secret>
export JARVIS_MODEL=qwen3:1.7b
jarvis model-doctor
jarvis "review this repository and fix the highest-impact issue"
```

Bare tasks use the standalone local agent. The agent loop, repository tools, approvals and verification run on the client machine. Only model requests leave that machine for the inference gateway. Keep port 8080 restricted to trusted clients on your private network.

AI Stack is optional. For durable remote Runs, configure its API and explicitly use `jarvis run` or `jarvis cloud`:

```bash
export AI_STACK_BASE_URL=http://<ai-stack-host>:8081
export AI_STACK_API_KEY=<your-ai-stack-agent-key>
jarvis run "review this repository" --workspace /workspace/repo
```

For an AI Stack hostname protected by Cloudflare Access, configure `CLOUDFLARE_ACCESS_CLIENT_ID` and `CLOUDFLARE_ACCESS_CLIENT_SECRET`. Never commit API keys or production secrets to the repository.

Never commit API keys or production secrets to the repository.

## Development

Clone the repository only when modifying Jarvis itself:

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
python3 -m pip install -e .
```

## Release process

A version bump in `src/jarvis_cli/__init__.py` followed by a merge to `main` triggers the release workflow. The workflow builds:

- a Python wheel and source distribution;
- standalone executables;
- SBOMs and SHA256 checksums;
- build-provenance attestations;
- a GitHub Release.

PyPI publishing uses GitHub Actions Trusted Publishing through the repository's `pypi` environment and the corresponding PyPI trusted publisher configuration.