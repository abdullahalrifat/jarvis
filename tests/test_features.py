import json
from jarvis_cli.attachments import attach_files
from jarvis_cli.profiles import load_profiles
from jarvis_cli.repository_map import build_repository_map
from jarvis_cli.sessions import SessionStore
from jarvis_cli.web import search_web


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit=-1):
        return self.payload


def test_local_sessions_round_trip(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    created = store.create(workspace=str(tmp_path), task="answer", model="coder")
    finished = store.finish(created.id, result="done", trace_path="trace.jsonl")
    assert finished.status == "completed"
    assert store.get(created.id[:8]).result == "done"
    assert store.list()[0].id == created.id


def test_repository_map_contains_python_symbols(tmp_path):
    (tmp_path / "app.py").write_text("def answer():\n    return 42\n")
    result = build_repository_map(tmp_path)
    assert result["files"][0]["path"] == "app.py"
    assert result["files"][0]["symbols"][0]["name"] == "answer"


def test_model_profiles_load_and_route(tmp_path):
    path = tmp_path / "models.toml"
    path.write_text("""
[models.coder]
provider = "openai"
model = "qwen"
base_url = "https://models.test/v1"
priority = 10

[models.coder.capabilities]
tool_calling = true
structured_output = true
context_tokens = 32768
""")
    selected = load_profiles(path).select(required=("tool_calling",))
    assert selected.model == "qwen"


def test_searxng_search_returns_citation_context(monkeypatch):
    monkeypatch.setenv("JARVIS_SEARCH_URL", "https://search.test")

    def opener(request, timeout):
        assert "format=json" in request.full_url
        return Response(
            {
                "results": [
                    {
                        "title": "Source",
                        "url": "https://example.com/report",
                        "content": "Current evidence",
                    }
                ]
            }
        )

    result = search_web("current answer", opener=opener)
    assert result["results"][0]["url"] == "https://example.com/report"
    assert "Cite factual claims" in result["citation_context"]


def test_attachments_are_bounded_and_marked_untrusted(tmp_path):
    (tmp_path / "notes.txt").write_text("reference fact")
    prompt = attach_files("answer", tmp_path, ["notes.txt"])
    assert "Untrusted attachment: notes.txt" in prompt
    assert "reference fact" in prompt
