"""Check setup orchestration without installing packages or downloading models."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYTHON_STUB = r'''#!/bin/bash
printf '%s|%s\n' "$0" "$*" >> "$BOOKLAT_SETUP_TEST_LOG"
case "$*" in
  '-m venv .venv')
    [[ "$BOOKLAT_SETUP_TEST_FAIL" == venv ]] && exit 1
    mkdir -p .venv/bin
    cp "$0" .venv/bin/python
    ;;
  '-c '*) [[ "$BOOKLAT_SETUP_TEST_FAIL" == version ]] && exit 1 ;;
  '-m pip --version')
    [[ "$BOOKLAT_SETUP_TEST_FAIL" == pip || "$BOOKLAT_SETUP_TEST_FAIL" == ensurepip ]] && exit 1
    ;;
  '-m ensurepip --upgrade') [[ "$BOOKLAT_SETUP_TEST_FAIL" == ensurepip ]] && exit 1 ;;
  '-m pip install '*) [[ "$BOOKLAT_SETUP_TEST_FAIL" == install ]] && exit 1 ;;
esac
exit 0
'''


@unittest.skipIf(os.name == "nt", "POSIX setup scripts require a POSIX host; Windows uses setup-windows.cmd")
class SetupScriptsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'Booklat project'
        (self.root / 'scripts').mkdir(parents=True)
        for name in ['setup.sh', 'setup_vosk.sh']:
            shutil.copy2(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        self.bin = self.root / 'stub-bin'
        self.bin.mkdir()
        python = self.bin / 'python3'
        python.write_text(PYTHON_STUB)
        python.chmod(0o755)
        self.log = self.root / 'calls.log'
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin',
                        BOOKLAT_SETUP_TEST_LOG=str(self.log), BOOKLAT_SETUP_TEST_FAIL='')

    def run_setup(self, name='setup.sh', failure=''):
        return subprocess.run(['bash', str(self.root / 'scripts' / name)],
                              cwd=self.temporary.name,
                              env=dict(self.env, BOOKLAT_SETUP_TEST_FAIL=failure),
                              text=True, capture_output=True)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ''

    def test_fresh_setup_uses_local_pip_and_downloads_after_install(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertIn('|-m venv .venv', calls)
        self.assertIn('.venv/bin/python|-m pip install -r requirements.txt', calls)
        self.assertLess(calls.index('-m pip install'), calls.index('scripts/download_model.py'))

    def test_existing_environment_is_reused_and_missing_pip_is_bootstrapped(self):
        self.assertEqual(self.run_setup().returncode, 0)
        self.log.write_text('')
        result = self.run_setup(failure='pip')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('-m venv', self.calls())
        self.assertIn('-m ensurepip --upgrade', self.calls())

    def test_venv_failure_has_mint_instructions(self):
        result = self.run_setup(failure='venv')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sudo apt install python3 python3-venv python3-pip', result.stderr)
        self.assertNotIn('download_model', self.calls())

    def test_setup_stops_before_download_on_python_pip_or_install_failure(self):
        for failure in ['version', 'ensurepip', 'install']:
            with self.subTest(failure=failure):
                self.log.write_text('')
                result = self.run_setup(failure=failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('scripts/download_model.py', self.calls())

    def test_vosk_requires_environment_and_pip(self):
        result = self.run_setup('setup_vosk.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('./scripts/setup.sh', result.stderr)
        self.assertEqual(self.run_setup().returncode, 0)
        self.log.write_text('')
        result = self.run_setup('setup_vosk.sh', failure='pip')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pip is missing', result.stderr)
        self.assertNotIn('scripts/download_vosk.py', self.calls())

    def test_vosk_installs_into_same_environment(self):
        self.assertEqual(self.run_setup().returncode, 0)
        self.log.write_text('')
        result = self.run_setup('setup_vosk.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.venv/bin/python|-m pip install -r requirements-vosk.txt', self.calls())
        self.assertIn('scripts/download_vosk.py', self.calls())


if __name__ == '__main__':
    unittest.main()
