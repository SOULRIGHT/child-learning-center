"""python app.py (__main__) 경로가 circular import 없이 초기화되는지 검증한다.

import app 만으로는 이 버그를 잡지 못한다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT


class AppMainBootTests(unittest.TestCase):
    def test_python_app_py_as_main_does_not_circular_import(self):
        tmp = Path(tempfile.mkdtemp(prefix='clc_main_boot_')) / 'boot.db'
        env = os.environ.copy()
        env['CLC_TESTING'] = '1'
        env['DATABASE_URL'] = 'sqlite:///' + tmp.resolve().as_posix()
        env['FIREBASE_CREDENTIALS_JSON'] = ''
        env['SECRET_KEY'] = 'clc-main-boot-test'
        env.pop('FLASK_ENV', None)

        result = subprocess.run(
            [sys.executable, 'app.py'],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        combined = (result.stdout or '') + '\n' + (result.stderr or '')
        self.assertNotIn('circular import', combined.lower(), combined)
        self.assertNotIn('ImportError', combined, combined)
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn('CLC_TESTING_MAIN_INIT_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
