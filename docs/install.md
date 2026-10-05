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

Installation only provides the Jarvis application. Model credentials and endpoints remain runtime configuration. For example:

```bash
export JARVIS_PROVIDER=openai
export JARVIS_BASE_URL=https://your-endpoint.example/v1
export JARVIS_MODEL=your-coding-model
export JARVIS_API_KEY=your-secret
jarvis model-doctor
```

Never commit API keys or production secrets to the repository.

## Development

Clone the repository only when modifying Jarvis itself:

```bash
git clone https://github.com/abdullahalrifat/jarvis.git
cd jarvis
python3 -m pip install -e .
```

## Release process

A version bump in `src/jarvis_cli/__init__.py` is followed by a `v<version>` Git tag. The release workflow builds:

- a Python wheel and source distribution;
- standalone executables;
- SBOMs and SHA256 checksums;
- build-provenance attestations;
- a GitHub Release.

PyPI publishing uses GitHub Actions trusted publishing when the repository variable `PUBLISH_PYPI=true` is enabled and the corresponding PyPI trusted publisher is configured.