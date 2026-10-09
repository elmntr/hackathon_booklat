"""Run interface-state regressions without a speech model or browser dependency."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_browser_ui_states():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is optional for the inline browser interface self-check')
    subprocess.run([node, '--test', str(Path(__file__).with_name('browser_ui.cjs'))],
                   check=True, capture_output=True, text=True)
