from datetime import datetime, timedelta, timezone
import subprocess

from jarvis_core import MemoryRecord, ReviewHunk

from jarvis_cli.attachments import attachment_context, expand_attachment_paths
from jarvis_cli.change_review import ReviewLedger, render_hunks
from jarvis_cli.instructions import MemoryStore, explain_instructions, load_instructions
from jarvis_cli.mcp import load_mcp_config
from jarvis_cli.sessions import SessionStore


def test_session_continuation_fork_archive_and_approval(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create(workspace=str(tmp_path), task="hello", model="coder", name="one")
    store.append_message(session.id, "assistant", "hi")
    approval = store.request_approval(session.id, "patch", {"path": "a.py"})
    resumed, transcript, pending = store.resume(session.id)
    assert resumed.status == "awaiting_approval"
    assert [item["content"] for item in transcript] == ["hello", "hi"]
    assert pending[0]["id"] == approval
    store.resolve_approval(approval, True)
    child = store.fork(session.id, name="branch")
    assert child.parent_id == session.id
    assert len(store.transcript(child.id)) == 2
    assert store.rename(child.id, "renamed").name == "renamed"
    store.archive(child.id)
    assert child.id not in {item.id for item in store.list()}
    assert child.id in {item.id for item in store.list(include_archived=True)}


def test_multimodal_selection_preview_and_budget(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "b.py").write_text("print('ok')")
    selected = expand_attachment_paths(tmp_path, ["**/*.py", "a.txt"])
    assert {item.name for item in selected} == {"a.txt", "b.py"}
    context, descriptors = attachment_context(tmp_path, ["a.txt"])
    assert "BEGIN ATTACHMENT" in context
    assert descriptors[0].estimated_tokens > 0


def test_instruction_precedence_and_expiring_memory(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    (config / "jarvis").mkdir(parents=True)
    (config / "jarvis/AGENTS.md").write_text("user")
    (tmp_path / "AGENTS.md").write_text("workspace")
    src = tmp_path / "src"
    src.mkdir()
    (src / "AGENTS.md").write_text("directory")
    target = src / "a.py"
    target.write_text("")
    instructions = load_instructions(tmp_path, target)
    assert [item.content for item in instructions] == ["user", "workspace", "directory"]
    assert "directory" in explain_instructions(instructions)

    memory = MemoryStore(tmp_path / "memory.json")
    memory.set(MemoryRecord("active", "yes"))
    memory.set(
        MemoryRecord(
            "expired",
            "no",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    assert [item.key for item in memory.list()] == ["active"]
    assert memory.delete("active")


def test_review_render_and_mcp_policy_config(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "base"], cwd=tmp_path, check=True, capture_output=True)
    hunk = ReviewHunk("a.py", "@@ -1 +1 @@\n-old\n+new", ("pytest passed",))
    ledger = ReviewLedger(tmp_path, tmp_path / "reviews")
    transaction = ledger.create([hunk])
    transaction.approve({hunk.id})
    rendered = render_hunks(transaction, color=False)
    assert hunk.id in rendered
    assert "pytest passed" in rendered

    config = tmp_path / "mcp.toml"
    config.write_text(
        """
[servers.docs]
transport = "http"
endpoint = "https://mcp.example.com"
health_interval_seconds = 10

[servers.docs.tools.search]
allow = true
requires_approval = false
read_only = true
"""
    )
    loaded = load_mcp_config(config)
    assert loaded["docs"].permissions[0].allow
    assert loaded["docs"].permissions[0].read_only
