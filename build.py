"""Build a self-contained MediaWrt executable using only checked-in sources."""
import argparse
import base64
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parent


def build(output):
    files = {'MediaWrt-LICENSE': (ROOT / 'LICENSE').read_bytes()}
    for path in sorted((ROOT / 'vendor').rglob('*'), key=lambda p: p.as_posix()):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
            continue
        files['vendor/' + path.relative_to(ROOT / 'vendor').as_posix()] = path.read_bytes()
    if 'vendor/copyparty/__main__.py' not in files or 'vendor/jinja2/__init__.py' not in files:
        raise ValueError('Vendored runtime sources are missing')
    for directory in ('server', 'web'):
        for path in sorted((ROOT / 'src' / directory).rglob('*'), key=lambda p: p.as_posix()):
            if not path.is_file() or path.suffix not in ('.py', '.js', '.css', '.html'):
                continue
            if path.name == 'launcher.py':
                continue
            name = path.name if directory == 'server' else 'web/' + path.relative_to(ROOT / 'src/web').as_posix()
            files[name] = path.read_text(encoding='utf-8').encode('utf-8')
    packed = {name: base64.b85encode(zlib.compress(data, 9)).decode('ascii') for name, data in files.items()}
    launcher = (ROOT / 'src/server/launcher.py').read_text(encoding='utf-8')
    Path(output).write_text(launcher.replace('BUNDLE = {}', 'BUNDLE = ' + repr(packed)), encoding='utf-8', newline='\n')
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'mediawrt.py')
    args = parser.parse_args()
    build(args.output)
