import pytest

from jarvis_cli.cloud_isolation import (
    IsolationError,
    TaskResourceLimits,
    TaskSandboxPolicy,
    build_task_command,
)


def test_required_isolation_fails_closed_without_image(monkeypatch):
    monkeypatch.delenv("JARVIS_CLOUD_SANDBOX_IMAGE", raising=False)
    with pytest.raises(IsolationError, match="SANDBOX_IMAGE"):
        TaskSandboxPolicy.from_env()


def test_egress_requires_dedicated_network():
    policy = TaskSandboxPolicy(
        image="jarvis-worker:tested",
        network="egress",
        egress_network="bridge",
    )
    with pytest.raises(IsolationError, match="dedicated"):
        policy.validate()


def test_root_user_is_rejected():
    policy = TaskSandboxPolicy(image="jarvis-worker:tested", user="0")
    with pytest.raises(IsolationError, match="root"):
        policy.validate()


def test_resource_limits_are_bounded():
    with pytest.raises(ValueError, match="cpus"):
        TaskResourceLimits(cpus=0).validate()
    with pytest.raises(ValueError, match="pids"):
        TaskResourceLimits(pids=1).validate()


def test_docker_command_contains_per_task_limits_and_network_isolation(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("jarvis_cli.cloud_isolation.docker_available", lambda: True)
    policy = TaskSandboxPolicy(
        image="jarvis-worker:tested",
        network="deny",
        limits=TaskResourceLimits(cpus=1.5, memory="1g", pids=128, disk="4g"),
    )
    command = build_task_command(["python", "-m", "pytest", "-q"], tmp_path, policy)
    assert command[:3] == ["docker", "run", "--rm"]
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cpus") + 1] == "1.5"
    assert command[command.index("--memory") + 1] == "1g"
    assert command[command.index("--memory-swap") + 1] == "1g"
    assert command[command.index("--pids-limit") + 1] == "128"
    assert command[command.index("--storage-opt") + 1] == "size=4g"
    assert "--cap-drop" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in command
    assert "no-new-privileges:true" in command
    assert "--user" in command
    assert command[command.index("--user") + 1] != "0"
    assert "--mount" in command
    assert "dst=/workspace" in command[command.index("--mount") + 1]
    assert command[-4:] == ["jarvis-worker:tested", "python", "-m", "pytest", "-q"][-4:]


def test_egress_command_uses_only_policy_network(monkeypatch, tmp_path):
    monkeypatch.setattr("jarvis_cli.cloud_isolation.docker_available", lambda: True)
    policy = TaskSandboxPolicy(
        image="jarvis-worker:tested",
        network="egress",
        egress_network="jarvis-egress-policy",
    )
    command = build_task_command(["python", "-c", "print(1)"], tmp_path, policy)
    assert command[command.index("--network") + 1] == "jarvis-egress-policy"
    assert "--network" in command
    assert "host" not in command
