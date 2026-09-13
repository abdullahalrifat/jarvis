import json
from pathlib import Path

import pytest

from jarvis_cli.browser_agent import BROWSER_TOOL_SCHEMAS
from jarvis_cli.jobs import JobStore, _cron_matches, _next_cron
from jarvis_cli.observability import CalibrationStore, RouteObservation
from jarvis_cli.plugins import PluginRegistry, build_plugin
from jarvis_cli.team_runtime import PersistentTaskBoard, TeamTaskSpec


def test_task_board_dependency_progression(tmp_path):
    first = TeamTaskSpec(title="inspect", task="inspect", id="a", write=False)
    second = TeamTaskSpec(
        title="implement", task="implement", id="b", dependencies=("a",)
    )
    board = PersistentTaskBoard(tmp_path / "board.json", [first, second])
    assert board.tasks["a"].status == "ready"
    assert board.tasks["b"].status == "pending"
    board.tasks["a"].status = "completed"
    board.refresh()
    assert board.tasks["b"].status == "ready"


def test_task_board_file_rejects_unknown_dependencies(tmp_path):
    source = tmp_path / "team.json"
    source.write_text(
        json.dumps({"tasks": [{"id": "b", "title": "b", "dependencies": ["missing"]}]})
    )
    with pytest.raises(ValueError):
        PersistentTaskBoard.from_file(source, tmp_path / "board.json")


def test_plugin_build_and_checksum_verified_install(tmp_path):
    source = tmp_path / "plugin"
    skill = source / "skills" / "review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\nReview carefully.\n"
    )
    (source / "jarvis-plugin.json").write_text(
        json.dumps(
            {
                "name": "review-pack",
                "version": "1.0.0",
                "description": "review",
                "permissions": [],
            }
        )
    )
    archive = build_plugin(source, tmp_path / "plugin.jarvis-plugin")
    registry = PluginRegistry(tmp_path / "installed")
    manifest = registry.install(archive)
    assert manifest.name == "review-pack"
    assert registry.list()[0]["version"] == "1.0.0"
    assert (registry.active_roots()[0] / "skills" / "review" / "SKILL.md").exists()


def test_plugin_permissions_require_explicit_approval(tmp_path):
    source = tmp_path / "plugin"
    source.mkdir()
    (source / "jarvis-plugin.json").write_text(
        json.dumps({"name": "network-pack", "version": "1", "permissions": ["network"]})
    )
    archive = build_plugin(source, tmp_path / "plugin.zip")
    with pytest.raises(PermissionError):
        PluginRegistry(tmp_path / "installed").install(archive)


def test_job_store_is_durable_and_claims_due_jobs(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.submit(["local", "inspect"])
    claimed = store.claim_due()
    assert claimed is not None and claimed.id == job_id and claimed.status == "running"
    store.finish(job_id, 0, "out", "err")
    assert JobStore(path).get(job_id).status == "completed"


def test_scheduler_cron_matching_and_next_occurrence():
    import datetime

    value = datetime.datetime(2026, 8, 24, 12, 0, tzinfo=datetime.timezone.utc)
    assert _cron_matches("0 12 * * *", value.timestamp())
    next_value = _next_cron("5 12 * * *", value.timestamp())
    assert (
        datetime.datetime.fromtimestamp(next_value, datetime.timezone.utc).minute == 5
    )


def test_calibration_prefers_successful_route(tmp_path):
    store = CalibrationStore(tmp_path / "routes.json")
    for _ in range(3):
        store.record(RouteObservation("safe", "code", True, 1.0, 500))
        store.record(
            RouteObservation("fast", "code", False, 0.0, 100, incorrect_completion=True)
        )
    board = store.leaderboard("code")
    assert board[0]["route"] == "safe"


def test_real_workload_record_is_marked_and_visible(tmp_path):
    store = CalibrationStore(tmp_path / "routes.json")
    store.record_real_workload(
        route="local-small",
        category="real-efficiency",
        success=True,
        score=0.9,
        latency_ms=250,
        tool_failures=0,
    )
    rows = store.load()
    assert rows[-1].source == "real_workload"
    assert rows[-1].recorded_at > 0
    assert store.leaderboard("real-efficiency", source="real_workload")[0]["route"] == "local-small"


def test_legacy_calibration_rows_remain_compatible(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text(
        json.dumps(
            [{
                "route": "legacy",
                "category": "code",
                "success": True,
                "score": 1.0,
                "latency_ms": 100,
            }]
        )
    )
    rows = CalibrationStore(path).load()
    assert rows[0].source == "benchmark"


def test_browser_tool_surface_is_native_and_bounded():
    names = {item["name"] for item in BROWSER_TOOL_SCHEMAS}
    assert {
        "browser_open",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_wait",
        "browser_console",
        "browser_screenshot",
    } <= names
