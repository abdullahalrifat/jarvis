"""Dependency-aware parallel agent teams using isolated Git worktrees."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from threading import RLock
from time import time
from typing import Any, Callable
import uuid

from .quality_runtime import WorktreeManager


TERMINAL = {"completed", "failed", "cancelled", "blocked"}


@dataclass
class TeamTaskSpec:
    title: str
    task: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    dependencies: tuple[str, ...] = ()
    role: str = "implementer"
    write: bool = True


@dataclass
class TeamTaskState:
    spec: TeamTaskSpec
    status: str = "pending"
    owner: str | None = None
    worktree: str | None = None
    branch: str | None = None
    result: str | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec"]["dependencies"] = list(self.spec.dependencies)
        return payload


class PersistentTaskBoard:
    def __init__(self, path: str | Path, specs: list[TeamTaskSpec] | None = None) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.tasks: dict[str, TeamTaskState] = {}
        if self.path.is_file():
            self._load()
        for spec in specs or []:
            if spec.id in self.tasks:
                raise ValueError(f"duplicate task id: {spec.id}")
            self.tasks[spec.id] = TeamTaskState(spec=spec)
        self.refresh()
        self.save()

    @classmethod
    def from_file(cls, path: str | Path, state_path: str | Path) -> "PersistentTaskBoard":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("tasks", [])
        specs = [
            TeamTaskSpec(
                id=str(item.get("id") or uuid.uuid4().hex[:12]),
                title=str(item["title"]),
                task=str(item.get("task") or item["title"]),
                dependencies=tuple(str(dep) for dep in item.get("dependencies", [])),
                role=str(item.get("role", "implementer")),
                write=bool(item.get("write", True)),
            )
            for item in rows
        ]
        known = {item.id for item in specs}
        missing = sorted({dep for item in specs for dep in item.dependencies if dep not in known})
        if missing:
            raise ValueError("unknown task dependencies: " + ", ".join(missing))
        return cls(state_path, specs)

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("tasks", []):
            raw_spec = item["spec"]
            spec = TeamTaskSpec(
                title=raw_spec["title"],
                task=raw_spec["task"],
                id=raw_spec["id"],
                dependencies=tuple(raw_spec.get("dependencies", [])),
                role=raw_spec.get("role", "implementer"),
                write=bool(raw_spec.get("write", True)),
            )
            self.tasks[spec.id] = TeamTaskState(
                spec=spec,
                status=item.get("status", "pending"),
                owner=item.get("owner"),
                worktree=item.get("worktree"),
                branch=item.get("branch"),
                result=item.get("result"),
                error=item.get("error"),
                started_at=item.get("started_at"),
                finished_at=item.get("finished_at"),
            )

    def refresh(self) -> None:
        with self._lock:
            for state in self.tasks.values():
                if state.status not in {"pending", "ready", "blocked"}:
                    continue
                dependencies = [self.tasks[dep].status for dep in state.spec.dependencies]
                if any(status in {"failed", "cancelled", "blocked"} for status in dependencies):
                    state.status = "blocked"
                elif all(status == "completed" for status in dependencies):
                    state.status = "ready"
                else:
                    state.status = "pending"

    def ready(self) -> list[TeamTaskState]:
        self.refresh()
        return [item for item in self.tasks.values() if item.status == "ready"]

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "tasks": [item.to_dict() for item in self.tasks.values()]}
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.path)

    def summary(self) -> dict[str, Any]:
        self.refresh()
        counts: dict[str, int] = {}
        for task in self.tasks.values():
            counts[task.status] = counts.get(task.status, 0) + 1
        return {"counts": counts, "tasks": [item.to_dict() for item in self.tasks.values()]}


class TeamCoordinator:
    """Runs dependency-ready tasks concurrently, each on its own worktree branch."""

    def __init__(
        self,
        repository: str | Path,
        board: PersistentTaskBoard,
        runner: Callable[[TeamTaskSpec, Path], str],
        *,
        workers: int = 3,
        worktree_root: str | Path | None = None,
    ) -> None:
        self.repository = Path(repository).resolve()
        self.board = board
        self.runner = runner
        self.workers = max(1, min(workers, 8))
        self.worktree_root = Path(worktree_root or self.repository / ".jarvis/worktrees/team").resolve()
        self.manager = WorktreeManager(self.repository, self.worktree_root)

    def _run_one(self, state: TeamTaskState, worker: str) -> str:
        target = self.manager.create(state.spec.id)
        metadata = json.loads((target / ".jarvis-worktree.json").read_text(encoding="utf-8"))
        state.owner = worker
        state.worktree = str(target)
        state.branch = metadata.get("branch")
        state.status = "running"
        state.started_at = time()
        self.board.save()
        try:
            result = self.runner(state.spec, target)
        except BaseException as exc:
            state.status = "failed"
            state.error = str(exc)[:4000]
            state.finished_at = time()
            self.board.save()
            raise
        state.result = result
        state.status = "completed"
        state.finished_at = time()
        self.board.save()
        return result

    def run(self) -> dict[str, Any]:
        futures: dict[Future[str], str] = {}
        worker_index = 0
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="jarvis-team") as pool:
            while True:
                self.board.refresh()
                active_ids = set(futures.values())
                for state in self.board.ready():
                    if state.spec.id in active_ids or len(futures) >= self.workers:
                        continue
                    worker_index += 1
                    future = pool.submit(self._run_one, state, f"worker-{worker_index}")
                    futures[future] = state.spec.id
                if not futures:
                    if all(item.status in TERMINAL for item in self.board.tasks.values()):
                        break
                    # No runnable work means unresolved dependency cycle.
                    pending = [item for item in self.board.tasks.values() if item.status not in TERMINAL]
                    for item in pending:
                        item.status = "blocked"
                        item.error = "dependency cycle or unsatisfied dependency"
                    self.board.save()
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    task_id = futures.pop(future)
                    try:
                        future.result()
                    except BaseException:
                        pass
                    self.board.refresh()
                    self.board.save()
        return self.board.summary()
