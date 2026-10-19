"""No browser or microphone access: run actual speech handlers under Node."""

import shutil
import subprocess
from pathlib import Path


def test_actual_voice_handlers_review_and_submit_edited_text():
    node = shutil.which("node")
    assert node, "Node is required for mocked browser speech regressions (no npm packages)."
    result = subprocess.run([node, "tests/voice_lifecycle.cjs"], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
