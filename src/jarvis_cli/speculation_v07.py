"""Safe speculative explorer execution with independent provider/ledger state."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import os

_INSTALLED = False


def _score(text: str) -> float:
    lowered = text.casefold()
    score = min(0.35, len(text) / 16000)
    score += 0.12 * sum(token in lowered for token in ("file", "symbol", "test", "evidence"))
    score += 0.15 if "line" in lowered or "sha256" in lowered else 0.0
    score -= 0.35 if "error:" in lowered or "unable" in lowered else 0.0
    return score


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

        def candidate(index: int):
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
            child = local_agent._LocalAgentBackend(
                self.config,
                None,
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

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="jarvis-speculate") as pool:
            futures = [pool.submit(candidate, 0), pool.submit(candidate, 1)]
            done, pending = wait(futures, return_when=FIRST_COMPLETED)
            first = next(iter(done))
            try:
                result = first.result()
                if _score(result.summary) >= 0.55:
                    for future in pending:
                        future.cancel()
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
        return base_run(
            self,
            role=role,
            task=task,
            context=context,
            max_output_tokens=max_output_tokens,
        )

    local_agent._LocalAgentBackend.run = run
    _INSTALLED = True
