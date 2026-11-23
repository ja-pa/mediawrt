"""Build from source-only checkout with network and site packages disabled."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfflineBuild(unittest.TestCase):
    def test_source_only_reproducible_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('build.py', 'LICENSE'):
                shutil.copyfile(ROOT / name, root / name)
            for name in ('src', 'vendor'):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            script = (
                "import sys, runpy; "
                "sys.addaudithook(lambda event, args: "
                "(_ for _ in ()).throw(RuntimeError('Network forbidden')) "
                "if event.startswith('socket.') else None); "
                "sys.argv=['build.py']; runpy.run_path('build.py', run_name='__main__')"
            )
            command = [sys.executable, '-I', '-S', '-c', script]
            subprocess.run(command, cwd=root, check=True, capture_output=True)
            first = (root / 'mediawrt.py').read_bytes()
            subprocess.run(command, cwd=root, check=True, capture_output=True)
            self.assertEqual(first, (root / 'mediawrt.py').read_bytes())
            self.assertEqual(first, (ROOT / 'mediawrt.py').read_bytes())
            self.assertFalse((root / '.cache').exists())
