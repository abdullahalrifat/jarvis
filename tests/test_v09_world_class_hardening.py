from types import SimpleNamespace

from jarvis_cli.local_agent import LocalConfig
from jarvis_cli import proof_runtime, world_class_hardening


def _profile(name, provider, model, base_url):
    return SimpleNamespace(
        name=name,
        provider=provider,
        model=model,
        base_url=base_url,
        capabilities=SimpleNamespace(max_output_tokens=4096),
    )


def test_same_model_on_different_endpoint_is_retained_as_fallback(tmp_path, monkeypatch):
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
    assert world_class_hardening._endpoint_identity(base) != world_class_hardening._endpoint_identity(configs[0])


def test_profile_key_never_reuses_primary_key_across_provider(tmp_path, monkeypatch):
    base = LocalConfig(
        provider="openai",
        model="coder",
        api_key="primary-openai-secret",
        base_url="https://api.openai.com/v1",
        workspace=tmp_path,
    )
    profile = _profile("reviewer", "anthropic", "claude-test", "https://api.anthropic.com")
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
