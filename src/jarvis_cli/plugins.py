"""Capability-scoped Jarvis plugin packaging and installation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
from typing import Any

from .client import APIError


MANIFEST = "jarvis-plugin.json"
_ALLOWED_SECTIONS = {"skills", "hooks", "commands", "mcp"}


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str
    permissions: tuple[str, ...]
    files: dict[str, str]
    signature: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> "PluginManifest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        name = str(payload["name"]).strip()
        version = str(payload["version"]).strip()
        if not name or not version:
            raise ValueError("plugin name and version are required")
        files = {str(key): str(value) for key, value in dict(payload.get("files") or {}).items()}
        return cls(
            name=name,
            version=version,
            description=str(payload.get("description", "")),
            permissions=tuple(str(item) for item in payload.get("permissions", [])),
            files=files,
            signature=payload.get("signature"),
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe plugin path: {path}")
    if not candidate.parts or candidate.parts[0] not in _ALLOWED_SECTIONS:
        raise ValueError(f"plugin file must live under one of {sorted(_ALLOWED_SECTIONS)}: {path}")
    return candidate


def build_plugin(source: str | Path, output: str | Path) -> Path:
    root = Path(source).resolve()
    manifest_path = root / MANIFEST
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files: dict[str, str] = {}
    for section in _ALLOWED_SECTIONS:
        directory = root / section
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                relative = str(path.relative_to(root))
                _safe_relative(relative)
                files[relative] = _sha256(path)
    payload["files"] = files
    target = Path(output).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, json.dumps(payload, indent=2, sort_keys=True))
        for relative in files:
            archive.write(root / relative, relative)
    return target


class PluginRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.getenv("JARVIS_PLUGIN_HOME")
        self.root = Path(configured).expanduser() if configured else Path.home() / ".local/share/jarvis/plugins"
        self.root.mkdir(parents=True, exist_ok=True)

    def install(self, archive_path: str | Path, *, approve_permissions: bool = False) -> PluginManifest:
        archive = Path(archive_path).resolve()
        with tempfile.TemporaryDirectory(prefix="jarvis-plugin-") as temporary:
            stage = Path(temporary)
            with zipfile.ZipFile(archive) as zipped:
                for name in zipped.namelist():
                    if name == MANIFEST:
                        continue
                    _safe_relative(name)
                zipped.extractall(stage)
            manifest = PluginManifest.load(stage / MANIFEST)
            if manifest.permissions and not approve_permissions:
                raise PermissionError(
                    "plugin requests permissions; review and reinstall with explicit approval: "
                    + ", ".join(manifest.permissions)
                )
            for relative, expected in manifest.files.items():
                safe = _safe_relative(relative)
                source = stage / safe
                if not source.is_file() or _sha256(source) != expected:
                    raise APIError(f"plugin checksum mismatch: {relative}")
            target = self.root / manifest.name / manifest.version
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(stage, target)
            current = target.parent / "current.json"
            current.write_text(json.dumps({"version": manifest.version}), encoding="utf-8")
            return manifest

    def uninstall(self, name: str) -> None:
        target = self.root / name
        if target.exists():
            shutil.rmtree(target)

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir():
                continue
            current = directory / "current.json"
            if not current.is_file():
                continue
            version = str(json.loads(current.read_text(encoding="utf-8"))["version"])
            manifest = PluginManifest.load(directory / version / MANIFEST)
            rows.append({
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "permissions": list(manifest.permissions),
                "path": str(directory / version),
            })
        return rows

    def active_roots(self) -> list[Path]:
        return [Path(row["path"]) for row in self.list()]
