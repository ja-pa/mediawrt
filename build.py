"""Build one offline Python executable, preserving the pinned upstream SFX."""
import argparse
import urllib.request
import base64
import hashlib
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parent
SHA256 = '8f9a0def8a9c15252a06395781ec083372043b60caa80fb33c3d6dafa7f1b40a'

def build(source, output):
    payload = Path(source).read_bytes()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError('Copyparty 1.20.26 SFX checksum mismatch')
    files = {'copyparty-sfx.py': payload}
    files['MediaWrt-LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    files.update({name: (ROOT / 'src' / name).read_bytes()
                  for name in ('library.py', 'media.js', 'media.css', 'center.py', 'app.html', 'app.js', 'app.css')})
    packed = {name: base64.b85encode(zlib.compress(data, 9)).decode('ascii') for name, data in files.items()}
    launcher = (ROOT / 'src' / 'launcher.py').read_text(encoding='utf-8')
    Path(output).write_text(launcher.replace('BUNDLE = {}', 'BUNDLE = ' + repr(packed)), encoding='utf-8')
    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', type=Path,
                        default=ROOT / '.cache/copyparty-sfx-1.20.26.py')
    parser.add_argument('--download-upstream', action='store_true',
                        help='Download the pinned release and verify its checksum')
    args = parser.parse_args()
    if args.download_upstream:
        url = 'https://github.com/9001/copyparty/releases/download/v1.20.26/copyparty-sfx.py'
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != SHA256:
            raise ValueError('Downloaded upstream checksum mismatch')
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_bytes(payload)
    if not args.source.is_file():
        parser.error('Provide the pinned SFX path or use --download-upstream')
    build(args.source, ROOT / 'mediawrt.py')
