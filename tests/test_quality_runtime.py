from pathlib import Path

from jarvis_core import ClaimProof, CompletionRequirement, ProofKind
from jarvis_cli.quality_runtime import (
    IncrementalRepositoryIndex,
    JsonCache,
    classify_request,
    should_use_multi_agent,
    audit_completion,
)


def test_complex_request_selects_multi_agent():
    analysis = classify_request("Refactor authentication across the entire repository")
    assert analysis.needs_multi_agent
    assert analysis.risk >= 0.45
    assert should_use_multi_agent(
        "Refactor authentication across the entire repository"
    )


def test_incremental_index_uses_hashes_and_symbols(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return 1\n")
    index = IncrementalRepositoryIndex(tmp_path, tmp_path / ".state/index.json")
    assert index.update()["changed"] == 1
    assert index.update()["changed"] == 0
    assert index.find_symbol("run")[0].path == "app.py"
    source.write_text("def run():\n    return 2\n")
    assert index.update()["changed"] == 1


def test_cache_and_evidence_gate(tmp_path):
    cache = JsonCache(tmp_path / "cache")
    assert cache.get("tool", {"path": "a"}) is None
    cache.put("tool", {"path": "a"}, {"ok": True})
    assert cache.get("tool", {"path": "a"}) == {"ok": True}
    audit = audit_completion(
        (CompletionRequirement("tests", (ProofKind.TEST,)),),
        (ClaimProof("tests", ProofKind.TEST, "pytest:0"),),
    )
    assert audit.passed
