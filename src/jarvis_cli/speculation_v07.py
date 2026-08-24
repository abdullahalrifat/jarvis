"""Safe speculative explorer execution with independent provider/ledger state."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
import os
from threading import Event

_INSTALLED = False


def _score(text: str) -> float:
    lowered = text.casefold()
    score = min(0.35, len(text) / 16000)
    score += 0.12 * sum(
        token in lowered for token in ("file", "symbol", "test", "evidence")
    )
    score += 0.15 if "line" in lowered or "sha256" in lowered else 0.0
    score -= 0.35 if "error:" in lowered or "unable" in lowered else 0.0
    return score


class _CancellableProvider:
    """Stop a losing explorer before its next model turn."""

    def __init__(self, provider, cancelled: Event) -> None:
        self.provider = provider
        self.cancelled = cancelled
        self.last_usage = {}
        self.active_provider = getattr(provider, "active_provider", provider.config.provider)

    def complete(self, messages, tools):
        if self.cancelled.is_set():
            raise CancelledError("speculative candidate cancelled")
        result = self.provider.complete(messages, tools)
        self.last_usage = getattr(self.provider, "last_usage", {})
        self.active_provider = getattr(
            self.provider, "active_provider", self.provider.config.provider
        )
        if self.cancelled.is_set():
            raise CancelledError("speculative candidate cancelled")
        return result


def install_safe_speculation() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from . import efficiency_runtime, local_agent

    # Disable the first composition's simple speculative branch and replace it
    # with this independent-state implementation.
    should_speculate = efficiency_runtime.should_speculate
    efficiency_runtime.should_speculate = lambda task: False
    base_run = local_agent._LocalAgentBackend.run

    def run(self, *, role: str, task: str, context, max_output_tokens: int):
        enabled = os.getenv("JARVIS_SPECULATIVE", "auto").casefold() != "off"
        if role != "explorer" or not enabled or not should_speculate(task):
            return base_run(
                self,
                role=role,
                task=task,
                context=context,
                max_output_tokens=max_output_tokens,
            )

        cancelled = Event()

        def candidate(index: int):
            if cancelled.is_set():
                raise CancelledError("speculative candidate cancelled")
            variant = task + (
                "\nIndependent explorer A: prioritize definitions, references, and impact-linked tests."
                if index == 0
                else "\nIndependent explorer B: prioritize failure modes, recent Git changes, and alternative causes."
            )
            budget = local_agent.TokenBudget(
                max_run_input=self.config.max_input_tokens,
                max_run_output=self.config.max_output_tokens,
                max_turn_input=min(32000, self.config.max_input_tokens),
                max_turn_output=min(4096, self.config.max_output_tokens),
                max_agent_input=max(4000, self.config.max_input_tokens // 2),
                max_agent_output=max(1000, self.config.max_output_tokens // 2),
            )
            provider = _CancellableProvider(
                local_agent.build_model_provider(self.config), cancelled
            )
            child = local_agent._LocalAgentBackend(
                self.config,
                provider,
                self.tools,
                local_agent.TokenLedger(budget),
                local_agent.MemoryArtifactStore(),
            )
            return base_run(
                child,
                role=role,
                task=variant,
                context=context,
                max_output_tokens=max_output_tokens,
            )

        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jarvis-speculate")
        futures = [pool.submit(candidate, 0), pool.submit(candidate, 1)]
        try:
            done, pending = wait(futures, return_when=FIRST_COMPLETED)
            first = next(iter(done))
            try:
                result = first.result()
                if _score(result.summary) >= 0.55:
                    cancelled.set()
                    for future in pending:
                        future.cancel()
                    # Running requests can finish their current HTTP call, but the
                    # cancellation provider prevents any later model turns.
                    pool.shutdown(wait=False, cancel_futures=True)
                    return result
            except BaseException:
                pass
            wait(futures)
            successful = []
            for future in futures:
                try:
                    successful.append(future.result())
                except BaseException:
                    continue
            if successful:
                return max(successful, key=lambda item: _score(item.summary))
        finally:
            cancelled.set()
            pool.shutdown(wait=False, cancel_futures=True)
        return base_run(
            self,
            role=role,
            task=task,
            context=context,
            max_output_tokens=max_output_tokens,
        )

    local_agent._LocalAgentBackend.run = run
    _INSTALLED = True
