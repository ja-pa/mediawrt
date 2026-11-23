#!/usr/bin/env python3
"""MediaWrt: movie-first UI on the pinned Copyparty 1.20.26 engine. MIT."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import zlib

BUNDLE = {}
VERSION = '0.2.0'

def configuration(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    config_dir = Path(path).resolve().parent
    def resolve(value):
        target = Path(value).expanduser()
        return (target if target.is_absolute() else config_dir / target).resolve()
    root = resolve(cfg['media'])
    if not root.is_dir():
        raise ValueError('media must be a directory')
    base = resolve(cfg.get('state_dir', 'state'))
    scratch = Path(tempfile.gettempdir()) / ('mediawrt-' + hashlib.sha256(str(base).encode()).hexdigest()[:12])
    paths = {key: resolve(cfg.get(key + '_dir', str((scratch if key in ('runtime', 'temp') else base) / key)))
             for key in ('runtime', 'database', 'cache', 'temp', 'logs')}
    if cfg.get('required_mount'):
        mount = resolve(cfg['required_mount'])
        if not os.path.ismount(mount) or (root != mount and mount not in root.parents):
            raise ValueError('Required media mount is unavailable: ' + str(mount))
    if cfg.get('storage_policy') not in (None, 'pinned-or-ram'):
        raise ValueError('Unknown storage_policy')
    private_name = cfg.get('private_state_name', '.mediawrt')
    if private_name not in ('.mediawrt', '.hist'):
        raise ValueError('private_state_name must be .mediawrt or .hist')
    private = root / private_name if cfg.get('reserve_private_state', False) else None
    if private and private.is_symlink():
        raise ValueError('Private state cannot be a symlink')
    for path in [base, *paths.values()]:
        if (path == root or root in path.parents) and not (private and (path == private or private in path.parents)):
            raise ValueError('Private state must be outside the media directory: ' + str(path))
    # OpenWrt defaults: persistent writes only through the pinned disk; scratch in RAM.
    if cfg.get('storage_policy') == 'pinned-or-ram':
        ram = Path('/tmp').resolve(strict=True)
        for target in [base, *paths.values()]:
            allowed = root if target == root or root in target.parents else ram if target == ram or ram in target.parents else None
            if allowed is None:
                raise ValueError('Storage policy rejects path outside pinned HDD or /tmp: ' + str(target))
            ancestor = target
            while not ancestor.exists(): ancestor = ancestor.parent
            if ancestor.stat().st_dev != allowed.stat().st_dev:
                raise ValueError('Storage policy rejects nested filesystem: ' + str(target))
    if cfg.get('users_file'):
        cfg['users'] = json.loads(resolve(cfg['users_file']).read_text(encoding='utf-8'))
    anon = cfg.get('anonymous', 'r')
    users = cfg.get('users', [])
    if anon not in ('', 'r', 'rw', 'rwm'):
        raise ValueError('anonymous must be empty, r, rw, or rwm')
    names = set()
    for user in users:
        name, password, permissions = user['name'], user['password'], user.get('permissions', 'r')
        if not name or not password or any(x in name for x in ':,\r\n') or any(x in password for x in '\r\n'):
            raise ValueError('Invalid account name or password')
        if name in names or name == '*' or permissions not in ('r', 'rw', 'rwm'):
            raise ValueError('Invalid account permissions or duplicate name')
        names.add(name)
    if not anon and not users:
        raise ValueError('At least one reader is required')
    return cfg, root, paths

def arguments(cfg, root, paths):
    access = [cfg.get('anonymous', 'r')] if cfg.get('anonymous', 'r') else []
    access.extend(u.get('permissions', 'r') + ',' + u['name'] for u in cfg.get('users', []))
    argv = ['mediawrt', '-i', cfg.get('listen', '127.0.0.1'), '-p', str(cfg.get('port', 3924)), '-j', '1',
            '-v', str(root) + ':/media:' + ':'.join(access),
            '--hist', str(paths['cache']), '--dbpath', str(paths['database']),
            '--ses-db', str(paths['database'] / 'sessions.db'),
            '-e2d', '--no-fastboot', '--no-hash', '.*', '--re-maxage', '0', '--no-rescan', '--no-mtag-ff',
            '--no-acode', '--no-bacode', '--no-athumb', '--no-dirsz', '--no-snap', '--no-db-ip',
            '--no-dav', '--no-del', '--no-cp', '--no-logues', '--no-readme', '--no-html', '--no-robots',
            '--no-zip', '--no-ansi', '--no-voldump', '--http-only', '--xvol', '--xdev', '--unpost', '0',
            '--dotpart']
    if not any('m' in perm.split(',')[0] for perm in access):
        argv += ['--no-mv']
    if cfg.get('reserve_private_state', False):
        private_name = cfg.get('private_state_name', '.mediawrt')
        argv += ['-v', str(root / private_name) + ':/media/' + private_name + ':']
    if (root / '.hist').is_dir() and not (cfg.get('reserve_private_state') and cfg.get('private_state_name') == '.hist'):
        argv += ['-v', str(root / '.hist') + ':/media/.hist:']
    if cfg.get('allow_cidr'):
        argv += ['--ipa', cfg['allow_cidr']]
    for user in cfg.get('users', []):
        argv += ['-a', user['name'] + ':' + user['password']]
    if cfg.get('thumbnails', False):
        argv += ['--th-mt', '1', '--th-size', '320x256', '--th-convt', '30', '--th-ram-max', '0.25',
                 '--th-dec', 'ff', '--th-ff-jpg', '--th-no-webp', '--th-no-jxl',
                 '--th-poke', '0', '--th-clean', str(int(cfg.get('cache_cleanup_seconds', 0))),
                 '--th-maxage', str(int(cfg.get('cache_max_age_seconds', 604800)))]
    else:
        argv += ['--no-thumb']
    if cfg.get('file_logging', False):
        argv += ['-lo', str(paths['logs'] / 'mediawrt-%Y-%m-%d.log'), '--no-logflush']
    return argv

def main():
    parser = argparse.ArgumentParser(description='MediaWrt ' + VERSION)
    parser.add_argument('--config', required=True, help='JSON configuration; see config.example.json')
    parser.add_argument('--check', action='store_true', help='Validate configuration without writing or starting a server')
    parser.add_argument('--engine-help', action='store_true')
    opts = parser.parse_args()
    cfg, root, paths = configuration(opts.config)
    if opts.check:
        print(json.dumps({'version': VERSION, 'media': str(root), 'paths': {k: str(v) for k, v in paths.items()}}, indent=2))
        return
    os.umask(0o077)
    sys.dont_write_bytecode = True
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    # No default state, extraction, cache or log writes beside films or on router flash.
    os.environ.update(HOME=str(paths['runtime']), PRTY_XD=str(paths['runtime']), XDG_CONFIG_HOME=str(paths['database']),
                      TMPDIR=str(paths['temp']), TEMP=str(paths['temp']), TMP=str(paths['temp']),
                      PYTHONDONTWRITEBYTECODE='1', PRTY_NO_IMPRESO='1',
                      CP_VOLUME='media', CP_MEDIA_STATE=str(paths['database']),
                      CP_THUMBNAILS='1' if cfg.get('thumbnails', False) else '0')
    os.environ['MW_CACHE_DIR'] = str(paths['cache'])
    os.environ['MW_PUBLIC_CONFIG'] = json.dumps({'sources': cfg.get('library_sources', []),
        'server_admins': cfg.get('server_admins', []),
        'paths': {key: str(value) for key, value in paths.items()}})
    tempfile.tempdir = str(paths['temp'])
    for name, encoded in BUNDLE.items():
        data = zlib.decompress(base64.b85decode(encoded))
        dest = paths['runtime'] / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or hashlib.sha256(dest.read_bytes()).digest() != hashlib.sha256(data).digest():
            tmp = dest.with_name(dest.name + '.new')
            tmp.write_bytes(data)
            tmp.replace(dest)
    sys.path[:0] = [str(paths['runtime'] / 'vendor'), str(paths['runtime'])]
    sys.argv = arguments(cfg, root, paths)
    if opts.engine_help:
        sys.argv = ['mediawrt', '--help']
    import library
    library.install()
    import center
    center.install()
    from copyparty.__main__ import main as engine_main
    engine_main()

if __name__ == '__main__':
    main()
