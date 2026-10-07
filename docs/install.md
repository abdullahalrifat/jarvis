# Installing Jarvis

Jarvis is distributed in two forms:

1. **PyPI package** — recommended for developer machines. Install with `pipx` or `pip` and run `jarvis` from any directory.
2. **Standalone executable** — recommended for machines where Python is not desired. Download a release binary and run it directly.

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

For normal production use, Jarvis is a client of AI Stack. AI Stack owns orchestration, tools, memory/RAG and model routing; it calls jarvis-inference when model inference is required.

```bash
export AI_STACK_BASE_URL=http://<ai-stack-host>:8081
export AI_STACK_API_KEY=<your-ai-stack-agent-key>
# Optional: for an AI Stack hostname protected by Cloudflare Access
export CLOUDFLARE_ACCESS_CLIENT_ID=<cloudflare-service-token-client-id>
export CLOUDFLARE_ACCESS_CLIENT_SECRET=<cloudflare-service-token-client-secret>
export JARVIS_MODEL=qwen3:1.7b
jarvis model-doctor
```

Direct inference configuration is reserved for the explicit `jarvis local` diagnostic/developer path. Do not put inference credentials into the normal Jarvis environment.

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