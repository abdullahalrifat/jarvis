from __future__ import annotations

import io
import json

from jarvis_cli.ide_protocol import CAPABILITIES, serve


def test_ide_initialize_and_shutdown() -> None:
    incoming = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}})
        + "\n"
    )
    outgoing = io.StringIO()

    def handler(method, params):
        assert params == {}
        if method == "initialize":
            return CAPABILITIES
        raise AssertionError(method)

    assert serve(handler, stdin=incoming, stdout=outgoing) == 0
    rows = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert rows[0]["result"]["protocol"] == "1.0"
    assert rows[1]["result"] == {"ok": True}
