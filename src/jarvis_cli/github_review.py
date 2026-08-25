"""Minimal GitHub PR review client with bounded diff retrieval and optional review posting."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .client import APIError

_MAX_DIFF = 4 * 1024 * 1024


def _token() -> str:
    value = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not value:
        raise APIError("GitHub review requires GITHUB_TOKEN or GH_TOKEN")
    return value


def _request(method: str, url: str, *, body: dict[str, Any] | None = None, accept: str = "application/vnd.github+json") -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Jarvis/0.9",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read(_MAX_DIFF + 1)
    except HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", errors="replace")
        raise APIError(f"GitHub API failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise APIError(f"GitHub API failed: {exc}") from exc
    if len(raw) > _MAX_DIFF:
        raise APIError("GitHub response exceeded 4 MiB limit")
    if accept.endswith("diff"):
        return raw.decode("utf-8", errors="replace")
    if not raw:
        return {}
    return json.loads(raw)


def fetch_pull_request(owner: str, repo: str, number: int) -> dict[str, Any]:
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/pulls/{number}"
    metadata = _request("GET", base)
    diff = _request("GET", base, accept="application/vnd.github.diff")
    return {
        "number": number,
        "title": metadata.get("title"),
        "body": metadata.get("body") or "",
        "base": (metadata.get("base") or {}).get("sha"),
        "head": (metadata.get("head") or {}).get("sha"),
        "html_url": metadata.get("html_url"),
        "diff": diff,
    }


def review_prompt(pr: dict[str, Any]) -> str:
    diff = str(pr.get("diff") or "")
    return (
        "Review this pull request as a senior code-review agent. Focus on concrete correctness, security, "
        "regressions, concurrency, compatibility, tests, and maintainability. Do not invent issues. "
        "For every finding cite the file and relevant changed code. End with a machine-readable line "
        "VERDICT: APPROVE or VERDICT: COMMENT or VERDICT: REQUEST_CHANGES.\n\n"
        f"PR #{pr['number']}: {pr.get('title') or ''}\n"
        f"Body:\n{str(pr.get('body') or '')[:12000]}\n\nDIFF:\n{diff[:3_500_000]}"
    )


def post_review(owner: str, repo: str, number: int, body: str, *, event: str = "COMMENT") -> dict[str, Any]:
    event = event.upper()
    if event not in {"COMMENT", "APPROVE", "REQUEST_CHANGES"}:
        raise ValueError("invalid GitHub review event")
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/pulls/{number}/reviews"
    return _request("POST", url, body={"body": body[:60_000], "event": event})
