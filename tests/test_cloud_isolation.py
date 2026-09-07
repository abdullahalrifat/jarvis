import pytest

from jarvis_cli.cloud_isolation import (
    IsolationError,
    TaskResourceLimits,
    TaskSandboxPolicy,
    build_task_command,
    validate_host_boundary,
)


def test_required_isolation_fails_closed_without_image(monkeypatch):
    monkeypatch.delenv("JARVIS_CLOUD_SANDBOX_IMAGE", raising=False)
    with pytest.raises(IsolationError, match="sandbox image"):
        TaskSandboxPolicy.from_env()


def test_egress_requires_dedicated_network():
    policy = TaskSandboxPolicy(image="jarvis-worker:tested", network="egress", egress_network="bridge")
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


def test_docker_command_contains_per_task_limits_and_network_isolation(tmp_path):
    policy = TaskSandboxPolicy(
        image="jarvis-worker:tested",
        network="deny",
        limits=TaskResourceLimits(cpus=1.5, memory="1g", pids=128, disk="4g"),
    )
    command = build_task_command(["python", "-m", "pytest", "-q"], tmp_path, policy, require_docker=False)
    assert command[:3] == ["docker", "run", "--rm"]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cpus") + 1] == "1.5"
    assert command[command.index("--memory") + 1] == "1g"
    assert command[command.index("--memory-swap") + 1] == "1g"
    assert command[command.index("--pids-limit") + 1] == "128"
    assert command[command.index("--storage-opt") + 1] == "size=4g"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--user") + 1] != "0"
    assert "dst=/workspace" in command[command.index("--mount") + 1]


def test_egress_command_uses_only_policy_network(tmp_path):
    policy = TaskSandboxPolicy(
        image="jarvis-worker:tested",
        network="egress",
        egress_network="jarvis-egress-policy",
    )
    command = build_task_command(["python", "-c", "print(1)"], tmp_path, policy, require_docker=False)
    assert command[command.index("--network") + 1] == "jarvis-egress-policy"
    assert "host" not in command


def test_docker_socket_configuration_is_rejected(monkeypatch):
    monkeypatch.setenv("DOCKER_SOCKET_MOUNT", "/var/run/docker.sock:/var/run/docker.sock")
    with pytest.raises(IsolationError):
        validate_host_boundary()
