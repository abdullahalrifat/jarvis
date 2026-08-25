from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis_cli import proof_runtime, world_class_hardening
from jarvis_cli.client import APIError
from jarvis_cli.local_agent import LocalConfig


def _profile(name, provider, model, base_url):
    return SimpleNamespace(
        name=name,
        provider=provider,
        model=model,
        base_url=base_url,
        capabilities=SimpleNamespace(max_output_tokens=4096),
    )


def test_same_model_on_different_endpoint_is_retained_as_fallback(
    tmp_path, monkeypatch
):
    base = LocalConfig(
        provider="openai",
        model="coder",
        api_key="local-key",
        base_url="http://127.0.0.1:4000/v1",
        workspace=tmp_path,
    )
    remote = _profile(
        "remote-coder",
        "openai",
        "coder",
        "https://api.example.test/v1",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "remote-key")
    monkeypatch.setattr(
        "jarvis_cli.profiles.profile_api_key_env", lambda _name: None
    )
    configs = world_class_hardening._fallback_configs(
        base,
        {remote.name: remote},
        [remote.name],
    )
    assert len(configs) == 1
    assert configs[0].model == base.model
    assert configs[0].base_url == "https://api.example.test/v1"
    assert configs[0].api_key == "remote-key"
    assert world_class_hardening._endpoint_identity(
        base
    ) != world_class_hardening._endpoint_identity(configs[0])


def test_profile_key_never_reuses_primary_key_across_provider(
    tmp_path, monkeypatch
):
    base = LocalConfig(
        provider="openai",
        model="coder",
        api_key="primary-openai-secret",
        base_url="https://api.openai.com/v1",
        workspace=tmp_path,
    )
    profile = _profile(
        "reviewer", "anthropic", "claude-test", "https://api.anthropic.com"
    )
    monkeypatch.delenv("JARVIS_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setattr(
        "jarvis_cli.profiles.profile_api_key_env", lambda _name: None
    )
    assert world_class_hardening._profile_api_key(profile, base) == "anthropic-secret"
    assert world_class_hardening._profile_api_key(profile, base) != base.api_key


def test_browser_click_is_a_side_effect_after_hardening():
    proof_runtime._MUTATING_TOOLS.discard("browser_click")
    world_class_hardening._INSTALLED = False
    world_class_hardening.install_world_class_hardening()
    assert proof_runtime._is_mutating("browser_click", {"selector": "button"})


def test_incomplete_independent_verification_fails_closed():
    with pytest.raises(APIError, match="Independent verification did not pass"):
        world_class_hardening._require_verified_completion(
            "Implementation result\n\n"
            "Verification (incomplete: independent verification did not pass): failed"
        )


def test_bounded_file_list_skips_generated_trees_and_stops_at_limit(tmp_path):
    for index in range(20):
        (tmp_path / f"file-{index}.py").write_text("pass\n", encoding="utf-8")
    generated = tmp_path / "node_modules" / "pkg"
    generated.mkdir(parents=True)
    for index in range(20):
        (generated / f"generated-{index}.js").write_text("x\n", encoding="utf-8")

    class Tools:
        root = tmp_path

        def _path(self, value):
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = self.root / candidate
            candidate = candidate.resolve()
            candidate.relative_to(self.root)
            return candidate

    rows = world_class_hardening._bounded_file_list(Tools(), ".", limit=5).splitlines()
    assert len(rows) == 5
    assert all("node_modules" not in row for row in rows)
