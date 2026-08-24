from pathlib import Path

from jarvis_core import ClaimProof, CompletionRequirement, ProofKind
from jarvis_cli.quality_runtime import (
    IncrementalRepositoryIndex,
    JsonCache,
    LSPClient,
    audit_completion,
    classify_request,
    should_use_multi_agent,
)
from jarvis_cli.repository_map import build_repository_map


def test_complex_request_selects_multi_agent():
    analysis = classify_request("Refactor authentication across the entire repository")
    assert analysis.needs_multi_agent
    assert analysis.risk >= 0.45
    assert should_use_multi_agent(
        "Refactor authentication across the entire repository"
    )


def test_incremental_index_is_bounded_and_uses_hashes(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return 1\n")
    generated = tmp_path / "node_modules" / "generated.js"
    generated.parent.mkdir()
    generated.write_text("function ignored() {}\n")
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\0" * 1024)

    index = IncrementalRepositoryIndex(tmp_path, tmp_path / ".state/index.json")
    first = index.update()
    assert first["changed"] == 1
    assert first["skipped"] >= 2
    assert index.update()["changed"] == 0
    assert index.find_symbol("run")[0].path == "app.py"

    source.write_text("def run():\n    return 2\n")
    assert index.update()["changed"] == 1


def test_cache_is_versioned_and_atomic(tmp_path):
    cache = JsonCache(tmp_path / "cache")
    assert cache.get("tool", {"path": "a"}) is None
    cache.put("tool", {"path": "a"}, {"ok": True})
    assert cache.get("tool", {"path": "a"}) == {"ok": True}
    assert not list((tmp_path / "cache").glob("tmp*"))


def test_lsp_frame_parser_round_trip():
    message = {"jsonrpc": "2.0", "id": 2, "result": [{"name": "run"}]}
    framed = LSPClient._frame(message)
    assert LSPClient._parse_messages(framed) == [message]


def test_repository_map_integrates_symbols_imports_tests_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_LSP_ANALYSIS", "false")
    (tmp_path / "service.py").write_text("import json\n\ndef run():\n    return json.dumps({})\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_service.py").write_text("from service import run\n\ndef test_run():\n    assert run()\n")

    first = build_repository_map(tmp_path)
    service = next(item for item in first["files"] if item["path"] == "service.py")
    assert any(symbol["name"] == "run" for symbol in service["symbols"])
    assert "json" in service["imports"]
    assert "tests/test_service.py" in service["tests"]
    assert first["graph"]["imports"]
    assert first["index"]["cache_hit"] is False

    second = build_repository_map(tmp_path)
    assert second["index"]["cache_hit"] is True


def test_cache_and_evidence_gate(tmp_path):
    cache = JsonCache(tmp_path / "cache")
    cache.put("tool", {"path": "a"}, {"ok": True})
    audit = audit_completion(
        (CompletionRequirement("tests", (ProofKind.TEST,)),),
        (ClaimProof("tests", ProofKind.TEST, "pytest:0"),),
    )
    assert audit.passed
