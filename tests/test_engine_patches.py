"""未经核对的引擎构建不得被按固定地址修改。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EnginePatches(unittest.TestCase):
    def test_unknown_engine_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / 'libwxhld.so'
            original = b'\x7fELF' + b'unknown engine build' * 64
            for script in ('17_disable_scan_sig.py', '21_fake_appender.py'):
                with self.subTest(script=script):
                    library.write_bytes(original)
                    result = subprocess.run(
                        [sys.executable, str(ROOT / 'scripts' / script), str(library)],
                        capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('引擎校验失败', result.stderr)
                    self.assertEqual(library.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
