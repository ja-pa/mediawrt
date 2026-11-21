"""MediaWrt media-center API. Transport, auth and filesystem operations stay in Copyparty."""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET

import library as lib

ROOT = Path(__file__).resolve().parent / 'web'
PREFIX = '.cpr/media/v2/'
AUDIO = set('mp3 flac ogg opus m4a aac wav wma aiff alac'.split())
IMAGES = set('jpg jpeg png webp gif avif bmp'.split())
EPISODE = re.compile(r'(?i)(?:s(\d{1,2})[ ._-]*e(\d{1,3})|(\d{1,2})x(\d{1,3}))')
jobs = lib.ThumbnailJobs()
catalog_lock = threading.RLock()

@lru_cache(maxsize=1)
def public_config():
    return json.loads(os.environ.get('MW_PUBLIC_CONFIG', '{}'))

@contextmanager
def store():
    db = sqlite3.connect(str(Path(os.environ['CP_MEDIA_STATE']) / 'center-v2.sqlite'), timeout=10)
    db.execute('pragma busy_timeout=10000')
    db.execute('pragma temp_store=MEMORY')
    try:
        with db:
            yield db
    finally:
        db.close()

def init_store():
    with store() as db:
        db.executescript('CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY, added REAL);'
                        'CREATE TABLE IF NOT EXISTS overrides(id TEXT PRIMARY KEY, data TEXT);'
                        'CREATE TABLE IF NOT EXISTS metadata(id TEXT PRIMARY KEY, version TEXT, data TEXT);'
                        'CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);')

def identity(w):
    return hashlib.sha256(str(w).encode()).hexdigest()[:32]

def reconcile(up, vn):
    """Runs at explicit indexing boundaries, never on catalog reads."""
    cur = up.cur.get(vn.realpath)
    if cur is None:
        return
    rows = cur.execute('select w from up').fetchall()
    with catalog_lock, store() as db:
        baseline = db.execute("select value from settings where key='baseline'").fetchone()
        stamp = time.time() if baseline else None
        db.executemany('insert or ignore into seen values(?,?)', ((identity(w), stamp) for (w,) in rows))
        db.execute("insert or ignore into settings values('baseline','1')")

def safe_file(cli, vn, path, write=False, move=False):
    from copyparty.util import Pebkac
    if '\\' in path or any(not p or p.startswith('.') for p in path.split('/')):
        raise Pebkac(400, 'invalid_path')
    child, rem = cli.asrv.vfs.get(vn.vpath + '/' + path, cli.uname, not write, write, move)
    absolute = Path(child.canonical(rem))
    if child is not vn or child.chk_ap(str(absolute)) is not vn:
        raise Pebkac(403, 'outside_volume')
    return absolute

def item(vn, row):
    w, rd, fn, size, modified, uploaded = row
    path = '/'.join(filter(None, (rd, fn)))
    ext = fn.rsplit('.', 1)[-1].lower()
    kind = 'music' if ext in AUDIO else 'pictures' if ext in IMAGES else 'movies'
    match = EPISODE.search(fn) if kind == 'movies' else None
    source_role = None
    for source in sorted(public_config().get('sources', []), key=lambda s: len(s.get('path', '')), reverse=True):
        prefix = source.get('path', '').strip('/')
        if not prefix or path.startswith(prefix + '/'):
            source_role = source.get('kind'); break
    if kind == 'movies' and (match or source_role == 'series'): kind = 'series'
    season = int(match[1] or match[3]) if match else None
    episode = int(match[2] or match[4]) if match else None
    title = Path(fn).stem
    series = re.sub(r'[._]+', ' ', title[:match.start()]).strip(' -') if match else ''
    if kind == 'series' and not series:
        series = Path(rd).parent.name if re.match(r'(?i)(season|sez[oÄ‚Ĺ‚]na|s\d)', Path(rd).name) else Path(rd).name
    year = re.search(r'\b(19\d\d|20\d\d)\b', title)
    return {'id': identity(w), 'kind': kind, 'name': fn, 'title': title, 'path': path,
            'folder': rd, 'size': size, 'modified': modified, 'added': uploaded or None,
            'url': '/' + vn.vpath + '/' + quote(path, safe='/'), 'ext': ext,
            'series': series or Path(rd).name, 'season': season, 'episode': episode,
            'album': Path(rd).name, 'artist': Path(rd).parent.name,
            'year': int(year[1]) if year else None}

def all_items(cli, vn):
    from copyparty.util import Pebkac
    idx = cli.conn.get_u2idx()
    cur = idx.get_cur(vn) if idx else None
    if cur is None: raise Pebkac(503, 'index_pending')
    with store() as db:
        seen = dict(db.execute('select id,added from seen'))
        overrides = dict(db.execute('select id,data from overrides'))
        cached = {key: (version, json.loads(data)) for key, version, data in db.execute('select id,version,data from metadata')}
    result = []
    for row in cur.execute('select w,rd,fn,sz,mt,at from up'):
        path = '/'.join(filter(None, row[1:3]))
        if any(p.startswith('.') or not p for p in path.split('/')): continue
        if row[2].rsplit('.', 1)[-1].lower() not in lib.VIDEO | AUDIO | IMAGES: continue
        try:
            child, _ = cli.asrv.vfs.get(vn.vpath + '/' + path, cli.uname, True, False)
            if child is not vn: continue
        except Pebkac: continue
        value = item(vn, row)
        value['added'] = value['added'] or seen.get(value['id'])
        known = cached.get(value['id'])
        if known and known[0] == meta_key(value):
            tags = known[1].get('format', {}).get('tags', {})
            if value['kind'] == 'music':
                for field in ('title', 'album', 'artist'):
                    if tags.get(field): value[field] = tags[field]
                value['track'] = tags.get('track', '')
            value['duration'] = known[1].get('format', {}).get('duration')
        if value['id'] in overrides: value.update(json.loads(overrides[value['id']]))
        result.append(value)
    return result

def catalog(cli, vn):
    values = all_items(cli, vn)
    query = cli.uparam.get('q', '').casefold()[:200]
    kind = cli.uparam.get('kind', 'all')
    values = [x for x in values if (kind == 'all' or x['kind'] == kind) and
              (not query or query in (x['title'] + ' ' + x['folder']).casefold()) and
              not (cli.uparam.get('hide_avi') == '1' and x['ext'] == 'avi')]
    ids = cli.uparam.get('ids')
    if ids is not None:
        selected = set(ids.split(','))
        values = [x for x in values if x['id'] in selected]
    for field in ('series', 'album', 'artist', 'folder'):
        if field in cli.uparam: values = [x for x in values if str(x[field]) == cli.uparam[field]]
    if cli.uparam.get('season'): values = [x for x in values if str(x['season']) == cli.uparam['season']]
    if cli.uparam.get('new') == '1': values = [x for x in values if x['added']]
    group = cli.uparam.get('group')
    if group in ('series', 'album', 'artist', 'folder'):
        groups = {}
        for value in values:
            label = value[group] or 'Ă˘â‚¬â€ť'
            # Albums are disambiguated by directory, including identical album names.
            key = value['folder'] if group == 'album' else label
            if key not in groups:
                groups[key] = dict(value, id='group:' + hashlib.sha256(key.encode()).hexdigest()[:20],
                                   sample_id=value['id'], title=label, group=group, group_key=key, count=0)
            groups[key]['count'] += 1
        values = list(groups.values())
    order = cli.uparam.get('sort', 'title')
    if order in ('added', 'year', 'modified'): values.sort(key=lambda x: (x.get(order) or 0, x['title']), reverse=True)
    elif order == 'track': values.sort(key=lambda x: (x.get('album', ''), int(str(x.get('track') or '0').split('/')[0]) if str(x.get('track') or '0').split('/')[0].isdigit() else 0, lib.czech_key(x['path'])))
    elif order == 'episode': values.sort(key=lambda x: (x['season'] or 0, x['episode'] or 0, lib.czech_key(x['title'])))
    else: values.sort(key=lambda x: lib.czech_key(x['title']))
    try: page = max(0, min(100000, int(cli.uparam.get('page', '0'))))
    except ValueError: page = 0
    selected = values[page*60:page*60+60]
    # Only visible audio entries request tag extraction; the rest of the HDD stays asleep.
    pending = False
    if kind == 'music':
        for value in selected[:8]:
            try:
                _, waiting = metadata(cli, vn, dict(value, id=value.get('sample_id', value['id'])))
                pending = pending or waiting
            except OSError: pass
    return lib.reply(cli, {'items': selected, 'total': len(values), 'page': page, 'metadata_pending': pending,
                           'page_size': 60, **lib.state(cli, vn)})

def meta_key(value):
    return hashlib.sha256((value['id'] + ':' + str(value['modified']) + ':' + str(value['size'])).encode()).hexdigest()

def metadata(cli, vn, value):
    key = meta_key(value)
    with store() as db:
        cached = db.execute('select data from metadata where id=? and version=?', (value['id'], key)).fetchone()
    if cached: return json.loads(cached[0]), False
    src = safe_file(cli, vn, value['path'])
    def work():
        # Revalidate after queue wait; no full movie hashing.
        if vn.chk_ap(str(src)) is not vn: return False
        data = {}
        try:
            command = ['ffprobe', '-v', 'error', '-show_entries',
                'format=duration:format_tags=title,artist,album,track,date:stream=codec_name,codec_type,width,height',
                '-of', 'json', str(src)]
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
                # Bound the pipe while reading, not after communicate() has allocated it.
                timer = threading.Timer(15, proc.kill)
                timer.daemon = True
                timer.start()
                try:
                    output = proc.stdout.read(1024 * 1024 + 1)
                    if len(output) > 1024 * 1024:
                        proc.kill()
                    if proc.wait() == 0 and len(output) <= 1024 * 1024:
                        data = json.loads(output)
                finally:
                    timer.cancel()
                    if proc.poll() is None:
                        proc.kill()
        except (OSError, ValueError): pass
        with catalog_lock, store() as db:
            db.execute('insert or replace into metadata values(?,?,?)', (value['id'], key, json.dumps(data)))
        return True
    status = jobs.submit(key, work)
    return {}, status in (202,429)

def detail(cli, vn):
    from copyparty.util import Pebkac
    value = next((x for x in all_items(cli, vn) if x['id'] == cli.uparam.get('id')), None)
    if not value: raise Pebkac(404, 'not_found')
    src = safe_file(cli, vn, value['path'])
    if not src.is_file(): raise Pebkac(404, 'not_found')
    value['subtitles'] = []
    for child in src.parent.iterdir():
        if child.suffix.lower() in ('.srt', '.vtt') and child.name.startswith(src.stem + '.'):
            rel = child.relative_to(Path(vn.realpath)).as_posix()
            safe_file(cli, vn, rel)
            value['subtitles'].append({'name': child.name, 'path': rel})
    nfo = src.with_suffix('.nfo')
    if nfo.is_file() and nfo.stat().st_size <= 262144:
        try:
            safe_file(cli, vn, nfo.relative_to(Path(vn.realpath)).as_posix())
            raw = nfo.read_bytes()
            if b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper():
                tree = ET.fromstring(raw)
                for field in ('plot','genre','year','title'):
                    value.setdefault('local', {})[field] = (tree.findtext(field) or '')[:4000]
        except (OSError, ValueError, ET.ParseError): pass
    value['technical'], value['metadata_pending'] = metadata(cli, vn, value)
    return lib.reply(cli, value)

def artwork(cli, vn):
    path = cli.uparam.get('path', '')
    src = safe_file(cli, vn, path)
    for candidate in [src.with_suffix('.jpg'), src.parent/'poster.jpg', src.parent/'folder.jpg',
                      src.parent/'cover.jpg', src.parent/'poster.png', src.parent/'cover.png']:
        if candidate.is_file():
            safe_file(cli, vn, candidate.relative_to(Path(vn.realpath)).as_posix())
            return cli.tx_file('oh_f', str(candidate))
    return lib.reply(cli, {}, 204)

def subtitle(cli, vn):
    from copyparty.util import Pebkac
    path = safe_file(cli, vn, cli.uparam.get('path', ''))
    if path.suffix.lower() not in ('.srt','.vtt') or path.stat().st_size > 2*1024*1024:
        raise Pebkac(400, 'unsupported')
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    if path.suffix.lower() == '.srt':
        text = 'WEBVTT\n\n' + re.sub(r'(\d\d:\d\d:\d\d),(\d{3})', r'\1.\2', text)
    cli.reply(text.encode('utf-8'), mime='text/vtt; charset=utf-8'); return True

def get(cli):
    route = cli.vpath[len(PREFIX):]
    vn = lib.volume(cli)
    if route == 'config':
        cfg = public_config(); admin = cli.uname in cfg.get('server_admins', [])
        return lib.reply(cli, {'version': '0.2.0', 'user': cli.uname, 'volume': '/'+vn.vpath+'/',
            'upload': cli.uname in vn.axs.uwrite, 'move': cli.uname in vn.axs.umove and cli.uname in vn.axs.uwrite,
            'admin': admin, 'sources': cfg.get('sources', []), 'paths': cfg.get('paths', {}) if admin else {},
            'thumbnails': os.environ.get('CP_THUMBNAILS') == '1', 'statistics': False})
    if route == 'catalog': return catalog(cli, vn)
    if route == 'detail': return detail(cli, vn)
    if route == 'artwork': return artwork(cli, vn)
    if route == 'subtitle': return subtitle(cli, vn)
    if route == 'thumbnail':
        # Existing bounded upstream pipeline also handles image thumbnails.
        return lib.thumbnail(cli, vn)
    return lib.reply(cli, {'error':'not_found'}, 404)

def post(cli):
    from copyparty.util import Pebkac
    from urllib.parse import urlsplit
    if cli.headers.get('x-mediawrt') != '1' or cli.headers.get('sec-fetch-site') == 'cross-site':
        raise Pebkac(403, 'origin')
    origin = cli.headers.get('origin')
    if origin and urlsplit(origin).netloc != cli.headers.get('host'): raise Pebkac(403, 'origin')
    if cli.headers.get('content-length','0') != '0' or cli.headers.get('transfer-encoding'):
        raise Pebkac(400, 'body')
    vn = lib.volume(cli)
    route = cli.vpath[len(PREFIX):]
    if route == 'mkdir':
        path = cli.uparam.get('path', '')
        safe_file(cli, vn, path, write=True)
        return cli._mkdir(vn.vpath + '/' + path)
    if route == 'override':
        if cli.uname not in public_config().get('server_admins', []): raise Pebkac(403, 'forbidden')
        data = {key: cli.uparam[key][:200] for key in ('title','series') if key in cli.uparam}
        if cli.uparam.get('kind') in ('movies','series'): data['kind'] = cli.uparam['kind']
        ident = cli.uparam.get('id', '')
        if not any(x['id'] == ident for x in all_items(cli, vn)): raise Pebkac(404, 'not_found')
        with catalog_lock, store() as db:
            db.execute('insert or replace into overrides values(?,?)', (ident, json.dumps(data)))
        return lib.reply(cli, {'ok':True})
    return lib.reply(cli, {'error':'not_found'}, 404)

def install():
    from copyparty.httpcli import HttpCli
    from copyparty.up2k import Up2k
    from copyparty.util import Pebkac
    init_store()
    assets = {p.relative_to(ROOT).as_posix(): (p.read_bytes(),
              'text/javascript; charset=utf-8' if p.suffix == '.js' else 'text/css; charset=utf-8')
              for p in ROOT.rglob('*') if p.suffix in ('.js', '.css')}
    old_get, old_post, old_init = HttpCli.handle_get, HttpCli.handle_post, Up2k.init_indexes
    def handle_get(cli):
        if cli.vpath in ('app', 'app/') or (cli.vpath.rstrip('/') == 'media' and not cli.uparam):
            cli.out_headers['Cache-Control'] = 'no-cache'
            html = (ROOT/'index.html').read_text(encoding='utf-8').replace('<script defer', '<script nonce="' + cli.js_nonce + '" defer')
            cli.reply(html.encode('utf-8'), mime='text/html; charset=utf-8'); return True
        if cli.vpath.startswith('app/'):
            # Exact manifest lookup; arbitrary paths and traversal are never served.
            asset = assets.get(cli.vpath[4:])
            if asset is not None:
                body, mime = asset
                cli.out_headers['Cache-Control'] = 'no-cache'
                cli.reply(body, mime=mime)
                return True
        if cli.vpath.startswith(PREFIX):
            try: return get(cli)
            except Pebkac as e: return lib.reply(cli, {'error':'request_failed'}, e.code)
            except (OSError, ValueError): return lib.reply(cli, {'error':'unavailable'}, 503)
        return old_get(cli)
    HttpCli.handle_get = handle_get
    def handle_post(cli):
        if cli.vpath.startswith(PREFIX):
            try: return post(cli)
            except Pebkac as e: return lib.reply(cli, {'error':'request_failed'}, e.code)
        return old_post(cli)
    HttpCli.handle_post = handle_post
    def indexes(up, all_vols, scan_vols, fscan, gid=0):
        result = old_init(up, all_vols, scan_vols, fscan, gid)
        vn = all_vols.get(os.environ['CP_VOLUME'].strip('/'))
        if vn and not up.stop:
            try: reconcile(up, vn)
            except Exception as e: up.log('MediaWrt catalog sync failed: ' + str(e))
        return result
    Up2k.init_indexes = indexes
