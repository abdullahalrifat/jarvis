"""Accurate run-scoped execution evidence and tool-result deduplication."""

from __future__ import annotations

from contextvars import ContextVar
import hashlib
import json
from typing import Any

from jarvis_core import summarize_tool_result as core_summarize_tool_result

from . import efficiency_runtime

_INSTALLED = False
_DIGESTS: ContextVar[set[str] | None] = ContextVar("jarvis_v07_tool_digests", default=None)


def _is_test_command(arguments: dict[str, Any]) -> bool:
    argv = arguments.get("argv")
    if not isinstance(argv, list):
        return False
    joined = " ".join(str(part).casefold() for part in argv)
    return any(
        marker in joined
        for marker in (
            "pytest",
            "unittest",
            "go test",
            "cargo test",
            "npm test",
            "npm run test",
            "pnpm test",
            "yarn test",
            "mvn test",
            "gradle test",
            "./gradlew test",
        )
    )


def _exit_failed(result: str) -> bool:
    lowered = result.casefold()
    if "[exit 0]" in lowered:
        return False
    if "[exit " in lowered:
        try:
            suffix = lowered.rsplit("[exit ", 1)[1].split("]", 1)[0]
            return int(suffix.strip()) != 0
        except (ValueError, IndexError):
            pass
    return any(marker in lowered for marker in ("traceback", " tests failed", " failed,"))


def install_evidence_v07() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    base_tools = local_agent.LocalTools
    base_run = local_agent.run_local_agent

    class AccurateEvidenceTools(base_tools):
        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            state = efficiency_runtime._RUN.get()
            before = None
            if state is not None:
                before = (
                    state.tests_passed,
                    state.tests_failed,
                    state.commands_passed,
                    state.commands_failed,
                )
            result = super().execute(name, arguments)
            if state is not None and name == "run_command" and before is not None:
                # Undo the coarse v0.7 first-pass classification and apply exact
                # exit-code + argv-aware accounting.
                (
                    state.tests_passed,
                    state.tests_failed,
                    state.commands_passed,
                    state.commands_failed,
                ) = before
                failed = _exit_failed(result)
                if _is_test_command(arguments):
                    state.tests_failed += int(failed)
                    state.tests_passed += int(not failed)
                else:
                    state.commands_failed += int(failed)
                    state.commands_passed += int(not failed)
            return result

    def per_run_summary(name: str, result: Any, *, max_chars: int = 6000, artifact_store=None):
        raw = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        seen = _DIGESTS.get()
        if seen is not None and digest in seen:
            state = efficiency_runtime._RUN.get()
            if state is not None:
                state.duplicate_results += 1
            return {
                "duplicate_of": digest,
                "note": "identical tool result already supplied in this run; use its artifact/digest instead of duplicating context",
            }
        if seen is not None:
            seen.add(digest)
        return core_summarize_tool_result(
            name,
            result,
            max_chars=max_chars,
            artifact_store=artifact_store,
        )

    def run(task: str, config, **kwargs):
        token = _DIGESTS.set(set())
        try:
            return base_run(task, config, **kwargs)
        finally:
            _DIGESTS.reset(token)

    local_agent.LocalTools = AccurateEvidenceTools
    local_agent.summarize_tool_result = per_run_summary
    local_agent.run_local_agent = run
    _INSTALLED = True
