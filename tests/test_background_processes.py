import sys
import time
from pathlib import Path

from jarvis_cli.background_processes import BackgroundProcessManager


def test_background_process_can_start_poll_and_stop(tmp_path: Path):
    manager = BackgroundProcessManager(tmp_path)
    item = manager.start([sys.executable, "-c", "import time; print('ready'); time.sleep(10)"])
    assert item["id"]
    process_id = str(item["id"])
    deadline = time.time() + 3
    while time.time() < deadline:
        status = manager.status(process_id)
        if "ready" in str(status["output"]):
            break
        time.sleep(0.05)
    assert "ready" in str(manager.status(process_id)["output"])
    stopped = manager.stop(process_id)
    assert stopped["running"] is False
