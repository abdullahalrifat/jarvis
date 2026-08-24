"""Repository blast-radius analysis beyond direct source imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .repository_graph import RepositoryGraph

_CONFIG_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Makefile",
}
_CONFIG_SUFFIXES = {".yaml", ".yml", ".toml", ".json"}


def _candidate_configs(root: Path, max_files: int = 1000) -> list[Path]:
    rows = []
    for path in root.rglob("*"):
        if len(rows) >= max_files:
            break
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in {".git", ".jarvis", "node_modules", ".venv", "dist", "build"} for part in rel.parts):
            continue
        if path.name in _CONFIG_NAMES or (
            path.suffix.casefold() in _CONFIG_SUFFIXES
            and any(part in {".github", "deploy", "deployment", "k8s", "helm", "infra", "config"} for part in rel.parts)
        ):
            rows.append(path)
    return rows


def change_impact(workspace: str | Path, changed: Iterable[str]) -> dict[str, Any]:
    root = Path(workspace).resolve()
    changed_paths = [str(Path(value).as_posix()) for value in changed]
    graph = RepositoryGraph(root)
    graph.update()
    importers: set[str] = set()
    tests: set[str] = set()
    terms: set[str] = set()
    for rel in changed_paths:
        stem = Path(rel).stem
        terms.add(stem.casefold())
        tests.update(graph.related_tests(rel))
        importers.update(graph.importers(stem, 100))
    for importer in list(importers):
        tests.update(graph.related_tests(importer))
        terms.add(Path(importer).stem.casefold())

    config_hits: list[str] = []
    deployment_hits: list[str] = []
    for path in _candidate_configs(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").casefold()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        if not terms or not any(term and term in text for term in terms):
            # Root build manifests still affect broad dependency/build changes.
            if path.parent != root:
                continue
        config_hits.append(rel)
        if any(part in {".github", "deploy", "deployment", "k8s", "helm", "infra"} for part in path.relative_to(root).parts) or path.name.lower().startswith(("docker", "compose")):
            deployment_hits.append(rel)

    return {
        "changed": sorted(set(changed_paths)),
        "importers": sorted(importers),
        "tests": sorted(tests),
        "config": sorted(set(config_hits)),
        "deployment": sorted(set(deployment_hits)),
    }
