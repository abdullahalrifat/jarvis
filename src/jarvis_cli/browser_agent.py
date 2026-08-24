"""Optional Playwright-backed browser tools for end-to-end agent verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .client import APIError


BROWSER_TOOL_SCHEMAS = [
    {
        "name": "browser_open",
        "description": "Open a URL in the isolated Jarvis browser session.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "browser_snapshot",
        "description": "Return a bounded accessibility-oriented snapshot of the current page.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "browser_click",
        "description": "Click an element by CSS selector or visible text.",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
        },
    },
    {
        "name": "browser_type",
        "description": "Fill a browser element and optionally press Enter.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"},
                "enter": {"type": "boolean", "default": False},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "browser_wait",
        "description": "Wait for a selector or a bounded number of milliseconds.",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}, "milliseconds": {"type": "integer", "minimum": 0, "maximum": 10000}},
        },
    },
    {
        "name": "browser_console",
        "description": "Return bounded browser console messages captured in this session.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "browser_screenshot",
        "description": "Save a screenshot under .jarvis/browser and return the workspace-relative path.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string", "default": "page.png"}}},
    },
]


@dataclass
class BrowserSession:
    workspace: Path
    headless: bool = True

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._console: list[str] = []

    def _ensure(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:
            raise APIError(
                "Browser tools require Playwright. Install with 'pip install playwright' "
                "and run 'playwright install chromium'."
            ) from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(ignore_https_errors=False)
        self._page = self._context.new_page()
        self._page.on("console", lambda message: self._console.append(f"{message.type}: {message.text}") if len(self._console) < 500 else None)
        return self._page

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        page = self._ensure()
        if name == "browser_open":
            response = page.goto(str(arguments["url"]), wait_until="domcontentloaded", timeout=30000)
            return json.dumps({"url": page.url, "title": page.title(), "status": response.status if response else None})
        if name == "browser_snapshot":
            data = page.locator("body").inner_text(timeout=10000)
            return json.dumps({"url": page.url, "title": page.title(), "text": data[:20000]})
        if name == "browser_click":
            selector = arguments.get("selector")
            text = arguments.get("text")
            if selector:
                page.locator(str(selector)).first.click(timeout=10000)
            elif text:
                page.get_by_text(str(text), exact=False).first.click(timeout=10000)
            else:
                raise APIError("browser_click requires selector or text")
            return json.dumps({"url": page.url, "title": page.title()})
        if name == "browser_type":
            locator = page.locator(str(arguments["selector"])).first
            locator.fill(str(arguments["text"]), timeout=10000)
            if arguments.get("enter"):
                locator.press("Enter")
            return "ok"
        if name == "browser_wait":
            if arguments.get("selector"):
                page.locator(str(arguments["selector"])).first.wait_for(timeout=10000)
            else:
                page.wait_for_timeout(min(10000, max(0, int(arguments.get("milliseconds", 500)))))
            return "ok"
        if name == "browser_console":
            return json.dumps(self._console[-200:])
        if name == "browser_screenshot":
            raw_name = Path(str(arguments.get("name") or "page.png")).name
            if not raw_name.lower().endswith(".png"):
                raw_name += ".png"
            target = self.workspace / ".jarvis/browser" / raw_name
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target), full_page=True)
            return str(target.relative_to(self.workspace))
        raise APIError(f"unknown browser tool: {name}")

    def close(self) -> None:
        for resource in (self._context, self._browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = self._context = self._browser = self._playwright = None


_INSTALLED = False


def install_browser_tools() -> None:
    """Patch the existing local tool runtime once so agents can invoke browser tools."""
    global _INSTALLED
    if _INSTALLED:
        return
    from . import local_agent

    for schema in BROWSER_TOOL_SCHEMAS:
        if not any(item.get("name") == schema["name"] for item in local_agent.TOOL_SCHEMAS):
            local_agent.TOOL_SCHEMAS.append(schema)
    BaseTools = local_agent.LocalTools

    class BrowserLocalTools(BaseTools):
        def __init__(self, config, approval=None, artifact_resolver=None):
            super().__init__(config, approval=approval, artifact_resolver=artifact_resolver)
            self._browser_session = BrowserSession(config.workspace)

        def execute(self, name: str, arguments: dict[str, Any]) -> str:
            if name.startswith("browser_"):
                return self._browser_session.execute(name, arguments)
            return super().execute(name, arguments)

    local_agent.LocalTools = BrowserLocalTools
    _INSTALLED = True
