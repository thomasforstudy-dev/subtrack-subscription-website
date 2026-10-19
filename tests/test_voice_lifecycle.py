"""No browser or microphone access: run actual speech handlers under Node."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_actual_voice_handlers_review_and_submit_edited_text():
    node = shutil.which("node")
    if not node:
        # GitHub Actions sets CI=true and has Node, so the check always runs there.
        # A server PC without Node skips it instead of refusing every update.
        if os.getenv("CI"):
            pytest.fail("Node is required for mocked browser speech regressions (no npm packages).")
        pytest.skip("Node isn't installed on this PC; the voice check runs on GitHub instead.")
    result = subprocess.run([node, "tests/voice_lifecycle.cjs"], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
