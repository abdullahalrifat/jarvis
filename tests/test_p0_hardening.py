"""P0 hardening regressions (see WORKSPACE REVIEW.md).

Covers: platform-runtime gating (CLI-1), subprocess env scrub (CLI-2),
step-scoped tool idempotency (CLI-3), dangling tool_call durability (CLI-4),
patch-guard traversal rejection (CLI-5), atomic checkpoints (CLI-7),
.env parsing (CLI-8), budget-stop patch filenames (CLI-16), and
corrective read/list behavior (CLI-17).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from typing import Any

import pytest

from jarvis_cli.client import APIError  # noqa: F401  (matches repo test style)
from jarvis_cli.local_agent import (
    LocalConfig,
    LocalTools,
    _budget_stop_summary,
    _run_single_agent,
)
from jarvis_cli.patch_guard_v07 import PatchPlan, PatchTarget, _allowed
from jarvis_cli.provider_messages import to_openai
from jarvis_cli.sessions import SessionStore


def config(tmp_path, **values):
    defaults = dict(
        provider="openai",
        model="scripted",
        api_key="secret",
        base_url="https://model.test/v1",
        workspace=tmp_path,
    )
    defaults.update(values)
    return LocalConfig(**defaults)


class ScriptedProvider:
    """Two-turn provider: tool-call(s), then a final answer."""

    last_usage = {"prompt_tokens": 10, "completion_tokens": 5}
    active_provider = "openai"
    active_model = "scripted"

    def __init__(self, turns: list[tuple[str | None, dict[str, Any], str]]) -> None:
        self._turns = iter(turns)

    def complete(self, messages, schemas):
        name, arguments, final = next(self._turns)
        if name is None:
            return final, [], {"role": "assistant", "content": final}
        raw = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call-{name}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ],
        }
        calls = [{"id": f"call-{name}", "name": name, "arguments": arguments}]
        return "", calls, raw


class CountingTools:
    def __init__(self, root) -> None:
        self.root = root
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        return json.dumps({"echo": name})


# --- CLI-1: platform runtime installs for normalized bare tasks -----------


def test_platform_runtime_installs_for_bare_task(monkeypatch) -> None:
    from jarvis_cli import v06_main

    installed: list[bool] = []
    monkeypatch.setattr(v06_main, "install_plugin_runtime", lambda: None)
    monkeypatch.setattr(
        v06_main, "install_platform_runtime", lambda: installed.append(True)
    )
    monkeypatch.setattr("jarvis_cli.v05_main.main", lambda argv: 0)

    rc = v06_main.main(["fix the failing tests"])

    assert rc == 0
    assert installed == [True]


def test_platform_runtime_installs_for_session_resume(monkeypatch) -> None:
    from jarvis_cli import v06_main

    installed: list[bool] = []
    monkeypatch.setattr(v06_main, "install_plugin_runtime", lambda: None)
    monkeypatch.setattr(
        v06_main, "install_platform_runtime", lambda: installed.append(True)
    )
    monkeypatch.setattr("jarvis_cli.v05_main.main", lambda argv: 0)

    v06_main.main(["session-resume"])

    assert installed == [True]


# --- CLI-2: base LocalTools subprocesses must not inherit secrets ---------


def test_run_command_never_inherits_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INFERENCE_API_KEY", "super-secret")
    monkeypatch.setenv("JARVIS_COMMAND_ENV_ALLOW", "")
    tools = LocalTools(config(tmp_path, accept_commands=True))

    output = tools.execute(
        "run_command",
        {
            "argv": [
                "python",
                "-c",
                "import os; print('INFERENCE_API_KEY' in os.environ)",
            ]
        },
    )

    assert "False" in output


# --- CLI-3: identical mutating tool args re-execute across steps ----------


def test_identical_run_command_args_execute_again_on_a_later_step(
    tmp_path,
) -> None:
    provider = ScriptedProvider(
        [
            ("run_command", {"argv": ["pytest", "-q"]}, ""),
            ("run_command", {"argv": ["pytest", "-q"]}, ""),
            (None, {}, "done"),
        ]
    )
    tools = CountingTools(tmp_path)

    _run_single_agent(
        "run the tests twice",
        config(tmp_path, accept_commands=True, max_steps=8),
        provider=provider,
        tools=tools,
    )

    assert [call[0] for call in tools.calls] == ["run_command", "run_command"]


# --- CLI-4a: interrupts never persist dangling tool_calls -----------------


def test_interrupt_during_tools_backfills_synthetic_results(
    tmp_path, monkeypatch
) -> None:
    class InterruptingTools:
        def __init__(self, root) -> None:
            self.root = root

        def execute(self, name, arguments):
            raise KeyboardInterrupt()

    checkpoints: list[list[dict[str, Any]]] = []

    def checkpoint(messages):
        checkpoints.append([dict(message) for message in messages])

    provider = ScriptedProvider(
        [
            ("run_command", {"argv": ["pytest", "-q"]}, ""),
            (None, {}, "unused"),
        ]
    )

    with pytest.raises(KeyboardInterrupt):
        _run_single_agent(
            "interrupted task",
            config(tmp_path, accept_commands=True),
            provider=provider,
            tools=InterruptingTools(tmp_path),
            checkpoint=checkpoint,
        )

    final = checkpoints[-1]
    assert final[-1]["role"] == "tool"
    assert "interrupted" in final[-1]["content"].lower()
    # The repaired transcript must convert to a valid provider request.
    repaired = to_openai(final)
    assistant_positions = [
        index
        for index, message in enumerate(repaired)
        if message.get("role") == "assistant"
    ]
    for index in assistant_positions:
        assert index + 1 < len(repaired)
        assert repaired[index + 1]["role"] == "tool"


def test_verifier_submit_verdict_closes_its_tool_call(tmp_path) -> None:
    checkpoints: list[list[dict[str, Any]]] = []

    def checkpoint(messages):
        checkpoints.append([dict(message) for message in messages])

    provider = ScriptedProvider(
        [("submit_verdict", {"status": "passed", "checks": []}, '{"status": "passed"}')]
    )

    result = _run_single_agent(
        "verify",
        config(tmp_path, allow_edits=False),
        provider=provider,
        tools=CountingTools(tmp_path),
        checkpoint=checkpoint,
        role="verifier",
    )

    assert json.loads(result)["status"] == "passed"
    final = checkpoints[-1]
    assert final[-1]["role"] == "tool"


# --- CLI-4b: provider_messages repair pass --------------------------------


def test_dangling_tool_calls_are_repaired_before_the_next_user_message() -> None:
    transcript = [
        {"role": "user", "content": "do it"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "run_command", "arguments": "{}"},
                }
            ],
        },
        {"role": "user", "content": "and then this"},
    ]

    repaired = to_openai(transcript)

    assert [message["role"] for message in repaired] == [
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert repaired[2]["tool_call_id"] == "c1"
    assert "interrupted" in repaired[2]["content"]


def test_dangling_tool_calls_are_repaired_before_a_later_assistant() -> None:
    transcript = [
        {"role": "user", "content": "do it"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "run_command", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": "continuing",
        },
    ]

    repaired = to_openai(transcript)

    assert [message["role"] for message in repaired] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]


def test_trailing_dangling_tool_call_is_repaired_at_end() -> None:
    transcript = [
        {"role": "user", "content": "do it"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "apply_patch", "arguments": "{}"},
                }
            ],
        },
    ]

    repaired = to_openai(transcript)

    assert repaired[-1]["role"] == "tool"
    assert repaired[-1]["tool_call_id"] == "c1"


# --- CLI-5: patch guard keeps traversal rejected --------------------------


def test_patch_guard_strips_only_literal_dot_slash_prefix(tmp_path) -> None:
    plan = PatchPlan(
        goal="add helper",
        category="edit",
        targets=(PatchTarget(path="src/app.py"),),
        allow_new_files=True,
    )
    discovered: set[str] = set()

    assert _allowed("src/app.py", plan, discovered, tmp_path) is True
    assert _allowed("./src/app.py", plan, discovered, tmp_path) is True
    # A leading-dot-dot path must keep its traversal marker and be rejected.
    assert _allowed("../etc-placeholder", plan, discovered, tmp_path) is False
    assert _allowed("/etc/hosts", plan, discovered, tmp_path) is False


def test_patch_guard_rejects_dotdot_laundering_regression(tmp_path) -> None:
    plan = PatchPlan(
        goal="sneaky",
        category="edit",
        targets=(PatchTarget(path="workspace-only/src/core.py"),),
        allow_new_files=True,
    )

    assert _allowed("../etc-placeholder", plan, set(), tmp_path) is False


# --- CLI-7: checkpoints are atomic ----------------------------------------


def test_failed_checkpoint_leaves_transcript_intact(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create(workspace=str(tmp_path), task="t", model="scripted")
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]
    store.checkpoint(session.id, messages)
    assert store.transcript(session.id) == messages

    class Unserializable:
        pass  # json.dumps raises before the second INSERT commits

    crashing = messages + [{"role": "tool", "content": Unserializable()}]

    with pytest.raises(TypeError):
        store.checkpoint(session.id, crashing)

    # DELETE + inserts share one transaction: the previous transcript survives
    # a crash after the first row was inserted.
    assert store.transcript(session.id) == messages


# --- CLI-8: .env parsing handles quotes and export ------------------------


def test_env_loader_unquotes_values_and_handles_export(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        'export CLI8_QUOTED="quoted value"\n'
        "CLI8_SINGLE='single value'\n"
        "CLI8_BARE=bare\n"
        "\n"
        "# comment\n",
        encoding="utf-8",
    )
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("CLI8_")
    }
    env["PYTHONPATH"] = "/mnt/work/code/ai-infra/jarvis/src"
    env.pop("JARVIS_GLOBAL_ENV", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import jarvis_cli.main, os, json;"
            "print(json.dumps({key: os.environ.get(key) for key in"
            " ('CLI8_QUOTED', 'CLI8_SINGLE', 'CLI8_BARE')}))",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded["CLI8_QUOTED"] == "quoted value"
    assert loaded["CLI8_SINGLE"] == "single value"
    assert loaded["CLI8_BARE"] == "bare"


# --- CLI-16: budget-stop summary recovers patched filenames ---------------


def test_budget_stop_summary_lists_patched_files_from_patch_text() -> None:
    patch = "--- /dev/null\n+++ b/src/tiny.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "apply_patch",
                        "arguments": json.dumps({"patch": patch}),
                    },
                }
            ],
        }
    ]

    summary = _budget_stop_summary(messages, "run output token budget exceeded")

    assert "Patches were applied to: src/tiny.py" in summary
    assert "apply_patch" in summary


# --- CLI-17: list_files truncation + read_file range corrections ----------


def test_list_files_marks_truncation(tmp_path) -> None:
    for index in range(600):
        (tmp_path / f"f{index:04}.txt").write_text("x")
    tools = LocalTools(config(tmp_path))

    output = tools.execute("list_files", {"path": "."})

    assert output.count(".txt") == 500
    assert "truncated" in output


def test_read_file_out_of_range_is_corrective_not_silent(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo\n")
    tools = LocalTools(config(tmp_path))

    assert "beyond the end" in tools.execute(
        "read_file", {"path": "a.txt", "start_line": 9}
    )
    assert "before start_line" in tools.execute(
        "read_file", {"path": "a.txt", "start_line": 2, "end_line": 1}
    )
    assert (
        tools.execute("read_file", {"path": "a.txt", "start_line": 2, "end_line": 2})
        == "2: two"
    )


# --- CLI-11: run wall-clock deadline and documented step cap ---------------


def test_run_deadline_stops_run_between_steps(monkeypatch, tmp_path) -> None:
    """The run stops with a deterministic summary once the wall clock expires."""
    ticks = iter([100.0, 105.0, 111.0, 120.0, 130.0])
    monkeypatch.setattr("jarvis_cli.local_agent.time.monotonic", lambda: next(ticks))
    provider = ScriptedProvider([("read_file", {"path": "a.txt"}, "")])
    tools = CountingTools(tmp_path)
    cfg = config(tmp_path, run_timeout_seconds=10.0, max_steps=5)

    result = _run_single_agent("t", cfg, provider=provider, tools=tools)

    assert "run wall-clock deadline of 10s" in result
    assert "JARVIS_RUN_TIMEOUT_SECONDS" in result
    # Exactly one step ran; the deadline check blocked the second model call.
    assert tools.calls == [("read_file", {"path": "a.txt"})]


def test_run_deadline_is_disabled_when_zero(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("jarvis_cli.local_agent.time.monotonic", lambda: 10**9)
    provider = ScriptedProvider([(None, {}, "all done")])
    cfg = config(tmp_path, run_timeout_seconds=0.0, max_steps=3)

    result = _run_single_agent(
        "t", cfg, provider=provider, tools=CountingTools(tmp_path)
    )

    assert result == "all done"


def test_max_steps_cap_is_env_overridable(monkeypatch) -> None:
    from jarvis_cli.local_agent import _max_steps_cap

    monkeypatch.delenv("JARVIS_MAX_STEPS_CAP", raising=False)
    assert _max_steps_cap() == 100
    monkeypatch.setenv("JARVIS_MAX_STEPS_CAP", "250")
    assert _max_steps_cap() == 250
    monkeypatch.setenv("JARVIS_MAX_STEPS_CAP", "0")
    assert _max_steps_cap() == 1  # never below 1


def test_resolve_local_config_applies_cap_and_run_deadline(monkeypatch) -> None:
    from jarvis_cli.local_agent import resolve_local_config

    monkeypatch.setenv("INFERENCE_BASE_URL", "http://model.test/v1")
    monkeypatch.setenv("INFERENCE_API_KEY", "k")
    monkeypatch.setenv("JARVIS_RUN_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("JARVIS_MAX_STEPS_CAP", "200")

    class Args:
        provider = "openai"
        model = "scripted-test-model"
        max_steps = 500
        timeout = 60.0
        write = False
        accept_edits = False
        accept_commands = False

    cfg = resolve_local_config(Args)
    assert cfg.max_steps == 200  # clamped by the env-overridable cap
    assert cfg.run_timeout_seconds == 60.0


# --- CLI-13: resume status and ambiguous-prefix guards ---------------------


def test_resume_refuses_running_session(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create(workspace=str(tmp_path), task="t", model="scripted")
    assert session.status == "running"

    with pytest.raises(ValueError, match="still marked 'running'"):
        store.resume(session.id)

    # The explicit escape hatch for SIGKILLed sessions still works.
    resumed, _, _ = store.resume(session.id, force=True)
    assert resumed.id == session.id


def test_resume_allows_finished_sessions(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create(workspace=str(tmp_path), task="t", model="scripted")
    store.finish(session.id, result="done")
    resumed, messages, _ = store.resume(session.id)
    assert resumed.status == "completed"
    assert messages


def test_get_requires_unique_prefix_match(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    first = store.create(workspace=str(tmp_path), task="t", model="scripted")

    # Exact ids always resolve.
    assert store.get(first.id).id == first.id
    # A unique prefix still resolves...
    assert store.get(first.id[:12]).id == first.id

    # ...but an ambiguous prefix must fail loudly instead of silently
    # picking the most recently updated session (CLI-13).
    store.connection.execute(
        "INSERT INTO sessions"
        " (id, workspace, task, status, model, created_at, updated_at, metadata)"
        " VALUES (?, ?, ?, 'completed', 'scripted', ?, ?, '{}')",
        (
            first.id[:8] + "-ambiguous",
            str(tmp_path),
            "t",
            first.created_at,
            first.created_at,
        ),
    )
    store.connection.commit()
    with pytest.raises(LookupError, match="ambiguous"):
        store.get(first.id[:8])
    with pytest.raises(LookupError, match="not found"):
        store.get("00000000")
