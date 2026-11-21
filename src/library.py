"""Small API adapter for pinned Copyparty 1.20.26; no listener or supervisor."""
import functools
import hashlib
import secrets
from collections import OrderedDict
import json
import os
from pathlib import Path
import stat
import threading
import time
import unicodedata
from urllib.parse import quote, urlsplit

PREFIX = ".cpr/media/"
VIDEO = frozenset("mp4 m4v mkv webm mov avi mpg mpeg m2v ts m2ts mts ogv flv wmv 3gp vob".split())
ROOT = Path(__file__).resolve().parent
API_VERSION = 1
# Stable extension surface; no event collection or statistics implementation.
CAPABILITIES = {"statistics": False, "personal_state": "browser", "move_preview": True}
move_plans = {}
move_lock = threading.Lock()
scan_lock = threading.Lock()
last_request = 0.0


class ThumbnailJobs:
    """One background caller, at most eight queued jobs; HTTP never waits for FFmpeg."""
    def __init__(self):
        self.condition = threading.Condition()
        self.queue = OrderedDict()
        self.failed = OrderedDict()
        self.active = None
        self.worker = None

    def submit(self, key, work):
        now = time.monotonic()
        with self.condition:
            if self.failed.get(key, 0) > now:
                return 204
            if self.active == key:
                return 202
            if key not in self.queue and len(self.queue) >= 8:
                return 429
            self.queue[key] = (now + 12, work)
            if self.worker is None:
                self.worker = threading.Thread(target=self.run, name="media-thumbnails", daemon=True)
                self.worker.start()
            self.condition.notify()
        return 202

    def run(self):
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                key, (expires, work) = self.queue.popitem(last=False)
                if expires < time.monotonic():
                    continue
                self.active = key
            ok = False
            try:
                ok = bool(work())
            except Exception:
                ok = False
            finally:
                with self.condition:
                    self.active = None
                    if not ok:
                        self.failed[key] = time.monotonic() + 60
                        while len(self.failed) > 256:
                            self.failed.popitem(last=False)


thumbnail_jobs = ThumbnailJobs()


def thumbnail(cli, vn):
    from copyparty.th_srv import thumb_path
    from copyparty.util import Pebkac
    rem = cli.uparam.get("path", "")
    if (not rem or len(rem) > 4096 or "\\" in rem or
            any(not p or p.startswith(".") for p in rem.split("/"))):
        raise Pebkac(400, "Invalid thumbnail path")
    child, child_rem = cli.asrv.vfs.get(vn.vpath + "/" + rem, cli.uname, True, False)
    if child is not vn:
        raise Pebkac(403, "Outside media volume")
    path = vn.canonical(child_rem)
    if vn.chk_ap(path) is not vn:
        raise Pebkac(403, "Outside media volume")
    try:
        info = os.stat(path)
    except OSError:
        raise Pebkac(404, "Video not found")
    tc = cli.thumbcli
    if (not tc or not stat.S_ISREG(info.st_mode) or not info.st_size or
            rem.rsplit(".", 1)[-1].lower() not in tc.thumbable or "dthumb" in vn.flags or
            "dvthumb" in vn.flags):
        return reply(cli, {}, 204)
    histpath = cli.asrv.vfs.histtab.get(vn.realpath)
    if not histpath:
        return reply(cli, {}, 204)
    # The shipped thumbnail profile is JPEG, with upstream's forced crop/size flags.
    fmt = "j"
    if "f" in vn.flags["crop"] and "n" in vn.flags["crop"]:
        fmt += "f"
    if "f" in vn.flags["th3x"] and "y" in vn.flags["th3x"]:
        fmt += "3"
    mtime = int(info.st_mtime)
    cached = thumb_path(histpath, rem, mtime, fmt, tc.fmt_ffa)
    try:
        cached_size = os.stat(cached).st_size
    except OSError:
        cached_size = None
    if cached_size is not None:
        if not cached_size:
            return reply(cli, {}, 204)
        cli.out_headers["Cache-Control"] = "private, no-cache"
        return cli.tx_file("oh_f", cached)

    def convert():
        # Recheck symlink boundaries after waiting in the queue.
        if vn.chk_ap(vn.canonical(rem)) is not vn:
            return None
        return tc.get(vn, rem, mtime, "j")

    status = thumbnail_jobs.submit((vn.realpath, rem, mtime, fmt), convert)
    cli.out_headers["Retry-After"] = "2"
    return reply(cli, {"pending": status != 204}, status)


def grouped_items(rows, vn, scope):
    """Collapse multi-video folders, treating the existing library containers as roots."""
    groups, singles = {}, []
    prefix = scope + "/" if scope else ""
    for rd, fn, size, modified in rows:
        item = video_item(vn, rd, fn, size, modified)
        relative = rd[len(prefix):] if prefix and rd.startswith(prefix) else ("" if rd == scope else rd)
        parts = relative.split("/") if relative else []
        base = scope
        if not scope and parts and parts[0].casefold() in ("filmy", "movies"):
            base = parts.pop(0)
        if parts:
            key = "/".join(filter(None, (base, parts[0])))
            groups.setdefault(key, []).append(item)
        else:
            singles.append(item)
    for key, videos in groups.items():
        if len(videos) == 1:
            singles.extend(videos)
        else:
            url = quote("/" + vn.vpath + "/" + key + "/", safe="/")
            singles.append({"kind": "folder", "name": key.split("/")[-1], "path": key,
                            "count": len(videos), "folder": "/" + key,
                            "url": url, "folder_url": url})
    return sorted(singles, key=lambda item: (czech_key(item["name"]), czech_key(item["folder"])))


def video_item(vn, rd, fn, size, modified):
    path = "/" + vn.vpath + "/" + (rd + "/" if rd else "")
    return {"kind": "video", "name": fn, "folder": "/" + rd if rd else "/",
            "url": quote(path + fn, safe="/"), "folder_url": quote(path, safe="/"),
            "path": (rd + "/" if rd else "") + fn, "size": size, "modified": modified}


@functools.lru_cache(maxsize=8192)
def czech_key(value):
    value = unicodedata.normalize("NFC", value).casefold()
    alphabet = "a b c č d e f g h ch i j k l m n o p q r ř s š t u v w x y z ž".split()
    weights = {char: i + 100 for i, char in enumerate(alphabet)}
    tokens, i = [], 0
    while i < len(value):
        char = value[i]
        if value[i:i + 2] == "ch":
            char = "ch"
            i += 1
        plain = char if char in weights else unicodedata.normalize("NFD", char)[0]
        tokens.append(weights.get(plain, ord(plain[0]) + 1000))
        i += 1
    return tokens, value


def compare(a, b):
    a, b = czech_key(a), czech_key(b)
    return (a > b) - (a < b)


def reply(cli, value, status=200):
    cli.out_headers["Cache-Control"] = "no-store"
    body = b"" if status == 204 else json.dumps(value, ensure_ascii=True).encode()
    cli.reply(body, status, mime="application/json")
    return True


def volume(cli):
    from copyparty.util import Pebkac
    path = os.environ["CP_VOLUME"].strip("/")
    vn, rem = cli.asrv.vfs.get(path, cli.uname, True, False)
    if rem or vn.vpath != path or "e2d" not in vn.flags:
        raise Pebkac(403, "Media library unavailable")
    return vn


def state(cli, vn):
    raw = cli.conn.hsrv.broker.ask("up2k.get_state", False, "").get()
    data = json.loads(raw)
    return {"scanning": data["scanning"] or time.monotonic() - last_request < 2,
            "state": data["volstate"].get(vn.vpath, "initializing")}


def list_movies(cli, vn):
    from copyparty.util import Pebkac
    try:
        page = int(cli.uparam.get("page", "0"))
        if not 0 <= page <= 1000000:
            raise ValueError()
    except ValueError:
        raise Pebkac(400, "Invalid page")
    query = unicodedata.normalize("NFC", cli.uparam.get("q", "")).casefold()
    if len(query) > 200:
        raise Pebkac(400, "Query too long")
    hide_avi = cli.uparam.get("hide_avi", "1") != "0"
    grouped = cli.uparam.get("group", "0") == "1"
    scope = cli.uparam.get("folder", "") if grouped else ""
    if scope and ("\\" in scope or any(not p or p.startswith(".") for p in scope.split("/"))):
        raise Pebkac(400, "Invalid folder")
    idx = cli.conn.get_u2idx()
    cur = idx.get_cur(vn) if idx else None
    if cur is None:
        return reply(cli, {"error": "index_pending"}, 503)

    def visible(rd, fn):
        if rd.startswith("//") or fn.startswith("//"):
            return False  # invalid/unrepresentable filenames are not web movie titles
        parts = (rd + "/" + fn).strip("/").split("/")
        if any(p.startswith(".") or p in ("", "..") for p in parts):
            return False
        ext = fn.rsplit(".", 1)[-1].lower()
        if ext not in VIDEO or (hide_avi and ext == "avi"):
            return False
        if scope and rd != scope and not rd.startswith(scope + "/"):
            return False
        haystack = rd + "/" + fn if grouped else fn
        if query not in unicodedata.normalize("NFC", haystack).casefold():
            return False
        try:
            child, _ = cli.asrv.vfs.get(vn.vpath + "/" + "/".join(parts), cli.uname, True, False)
            return child is vn
        except Pebkac:
            return False

    db = cur.connection
    db.create_function("media_visible", 2, visible)
    db.create_collation("MEDIA_CZ", compare)
    where = " from up where media_visible(rd,fn)"
    if 'ids' in cli.uparam:
        ids = set(cli.uparam['ids'].split(','))
        if len(ids) > 500:
            raise Pebkac(400, 'too_many_ids')
        db.create_function('media_selected', 1, lambda w: hashlib.sha256(str(w).encode()).hexdigest()[:32] in ids)
        where += ' and media_selected(w)'
    if grouped:
        rows = cur.execute("select rd,fn,sz,mt" + where).fetchall()
        items = grouped_items(rows, vn, scope)
        selected = items[page * 60:(page + 1) * 60]
        attach_ids(cur, selected)
        return reply(cli, dict(items=selected, total=len(items),
                               video_total=len(rows), page=page, page_size=60, folder=scope, **state(cli, vn)))
    total = cur.execute("select count(*)" + where).fetchone()[0]
    order = 'mt desc, fn' if cli.uparam.get('sort') == 'newest' else 'fn collate MEDIA_CZ, rd collate MEDIA_CZ'
    rows = cur.execute("select rd,fn,sz,mt" + where +
                       " order by " + order + " limit 60 offset ?",
                       (page * 60,)).fetchall()
    items = []
    for rd, fn, size, modified in rows:
        items.append(video_item(vn, rd, fn, size, modified))
    attach_ids(cur, items)
    return reply(cli, dict(items=items, total=total, page=page, page_size=60, **state(cli, vn)))


def attach_ids(cur, items):
    # Copyparty preserves w on its own moves; no stat or new identity DB on reads.
    for item in items:
        if item['kind'] == 'folder':
            continue
        rd, _, fn = item['path'].rpartition('/')
        row = cur.execute('select w from up where rd=? and fn=?', (rd, fn)).fetchone()
        item['id'] = hashlib.sha256(str(row[0] if row else item['path']).encode()).hexdigest()[:32]


def get(cli, original):
    route = cli.vpath[len(PREFIX):]
    if route in ("media.js", "media.css"):
        cli.out_headers["Cache-Control"] = "no-cache"
        mime = "text/javascript; charset=utf-8" if route.endswith("js") else "text/css; charset=utf-8"
        cli.reply((ROOT / route).read_bytes(), mime=mime)
        return True
    vn = volume(cli)
    if route == "v1/config":
        return reply(cli, {"volume": "/" + vn.vpath + "/", "thumbnails": os.environ.get("CP_THUMBNAILS") == "1",
                           "upload": cli.uname in vn.axs.uwrite,
                           "move": cli.uname in vn.axs.umove and cli.uname in vn.axs.uwrite,
                           "api_version": API_VERSION, "capabilities": CAPABILITIES})
    if route == "v1/status":
        return reply(cli, state(cli, vn))
    if route == "v1/movies":
        return list_movies(cli, vn)
    if route == "v1/thumbnail":
        return thumbnail(cli, vn)
    if route == 'v1/move-preview':
        return preview_move(cli, vn)
    return reply(cli, {"error": "Not found"}, 404)


def post(cli, original):
    global last_request
    from copyparty.util import Pebkac
    # Header forces a CORS preflight for cross-origin JS; forms cannot supply it.
    if cli.headers.get("x-copyparty-media") != "1" or cli.headers.get("sec-fetch-site") == "cross-site":
        raise Pebkac(403, "Same-origin media request required")
    origin = cli.headers.get("origin")
    if origin and urlsplit(origin).netloc != cli.headers.get("host"):
        raise Pebkac(403, "Origin mismatch")
    if cli.headers.get("content-length", "0") != "0" or cli.headers.get("transfer-encoding"):
        raise Pebkac(400, "Body must be empty")
    vn = volume(cli)
    if cli.vpath == PREFIX + 'v1/move':
        return execute_move(cli, vn)
    if cli.vpath != PREFIX + "v1/scan":
        return reply(cli, {"error": "Not found"}, 404)
    with scan_lock:
        current = state(cli, vn)
        if not current["scanning"]:
            error = cli.conn.hsrv.broker.ask("up2k.rescan", cli.asrv.vfs.all_vols,
                                           [vn.vpath], False, True).get()
            if error and "already in progress" not in error:
                return reply(cli, {"error": error}, 503)
            last_request = time.monotonic()
    return reply(cli, {"scanning": True}, 202)


def checked_path(cli, vn, path, destination=False):
    from copyparty.util import Pebkac
    if not path or '\\' in path or any(not p or p.startswith('.') for p in path.split('/')):
        raise Pebkac(400, 'invalid_path')
    child, rem = cli.asrv.vfs.get(vn.vpath + '/' + path, cli.uname, not destination, destination, not destination)
    absolute = Path(child.canonical(rem))
    if child is not vn or child.chk_ap(str(absolute)) is not vn:
        raise Pebkac(403, 'outside_volume')
    return absolute


def preview_move(cli, vn):
    from copyparty.util import Pebkac
    source = cli.uparam.get('source', '')
    target = cli.uparam.get('target', '')
    src = checked_path(cli, vn, source)
    dst = checked_path(cli, vn, target, True)
    if not (src.is_file() or src.is_dir()) or src.is_symlink() or not dst.parent.is_dir():
        raise Pebkac(400, 'invalid_path')
    if src.stat().st_dev != dst.parent.stat().st_dev:
        raise Pebkac(409, 'cross_device')
    pairs = [(source, target)]
    # Include only recognized sidecars with an exact movie stem (optionally language).
    for side in (src.parent.iterdir() if src.is_file() else []):
        if side == src or not side.is_file() or side.is_symlink():
            continue
        if side.suffix.lower() in ('.srt', '.vtt', '.ass', '.ssa', '.sub', '.idx', '.nfo', '.jpg', '.png') and side.name.startswith(src.stem + '.'):
            rel = str(side.relative_to(Path(vn.realpath))).replace('\\', '/')
            dest = str(dst.with_name(dst.stem + side.name[len(src.stem):]).relative_to(Path(vn.realpath))).replace('\\', '/')
            pairs.append((rel, dest))
    stamps = []
    for a, b in pairs:
        ap, bp = checked_path(cli, vn, a), checked_path(cli, vn, b, True)
        if bp.exists() or bp.is_symlink():
            raise Pebkac(409, 'target_exists')
        st = ap.stat()
        stamps.append((st.st_size, st.st_mtime_ns, st.st_ino))
    token = secrets.token_urlsafe(24)
    with move_lock:
        now = time.monotonic()
        for key in list(move_plans):
            if move_plans[key][0] < now:
                del move_plans[key]
        if len(move_plans) >= 128:
            raise Pebkac(429, 'busy')
        move_plans[token] = (now + 120, cli.uname, pairs, stamps)
    return reply(cli, {'token': token, 'files': [{'source': a, 'target': b} for a, b in pairs]})


def execute_move(cli, vn):
    from copyparty.util import Pebkac
    with move_lock:
        token = cli.uparam.get('token', '')
        plan = move_plans.get(token)
        if not plan or plan[0] < time.monotonic() or plan[1] != cli.uname:
            raise Pebkac(409, 'plan_expired')
        del move_plans[token]
        _, _, pairs, stamps = plan
        if 'include' in cli.uparam:
            try:
                included = json.loads(cli.uparam['include'])
                if not isinstance(included, list) or not all(isinstance(x, str) for x in included):
                    raise ValueError()
                allowed = {a for a, _ in pairs}
                if not set(included) <= allowed or pairs[0][0] not in included:
                    raise ValueError()
                selected = [(pair, stamp) for pair, stamp in zip(pairs, stamps) if pair[0] in included]
                pairs, stamps = zip(*selected)
            except (ValueError, TypeError):
                raise Pebkac(400, 'invalid_selection')
        for (a, b), stamp in zip(pairs, stamps):
            ap, bp = checked_path(cli, vn, a), checked_path(cli, vn, b, True)
            st = ap.stat()
            if (st.st_size, st.st_mtime_ns, st.st_ino) != stamp or bp.exists() or bp.is_symlink():
                raise Pebkac(409, 'plan_changed')
        completed = []
        for a, b in pairs:
            try:
                cli.conn.hsrv.broker.ask('up2k.handle_mv', None, cli.uname, cli.ip,
                                         vn.vpath + '/' + a, vn.vpath + '/' + b).get()
                completed.append({'source': a, 'target': b})
            except Exception as error:
                cli.log('MediaWrt move failed: ' + str(error))
                return reply(cli, {'error': 'partial_move', 'completed': completed}, 409)
    return reply(cli, {'completed': completed})


def install():
    from copyparty.httpcli import HttpCli
    from copyparty.up2k import Up2k
    old_get, old_post, old_init = HttpCli.handle_get, HttpCli.handle_post, Up2k.init_indexes
    old_move = Up2k.handle_mv
    def safe_move(up, abrt, uname, ip, source, target):
        from copyparty.util import Pebkac
        sv, sr = up.vfs.get(source, uname, True, False, True)
        dv, dr = up.vfs.get(target, uname, False, True)
        sp, dp = Path(sv.canonical(sr)), Path(dv.canonical(dr))
        if sv.chk_ap(str(sp)) is not sv or dv.chk_ap(str(dp)) is not dv or sp.is_symlink():
            raise Pebkac(403, 'outside_volume')
        parent = dp.parent
        while not parent.exists():
            parent = parent.parent
        if sp.stat().st_dev != parent.stat().st_dev:
            raise Pebkac(409, 'cross_device')
        if sp.is_dir():
            # Never carry hidden private data or a nested mount/symlink through a folder move.
            count = 0
            for folder, dirs, files in os.walk(sp, followlinks=False):
                for name in dirs + files:
                    child = Path(folder) / name
                    count += 1
                    if count > 10000 or name.startswith('.') or child.is_symlink() or child.stat().st_dev != sp.stat().st_dev:
                        raise Pebkac(409, 'unsafe_folder')
        return old_move(up, abrt, uname, ip, source, target)
    Up2k.handle_mv = safe_move
    HttpCli.handle_get = lambda cli: get(cli, old_get) if cli.vpath.startswith(PREFIX) else old_get(cli)
    HttpCli.handle_post = lambda cli: post(cli, old_post) if cli.vpath.startswith(PREFIX) else old_post(cli)

    def init_indexes(up, all_vols, scan_vols, fscan, gid=0):
        target = os.environ["CP_VOLUME"].strip("/")
        vn = all_vols.get(target)
        marker = Path(os.environ["CP_MEDIA_STATE"]) / "library-indexed-v1"
        initial = vn is not None and not marker.exists() and (not scan_vols or target in scan_vols)
        # Never force-index the reserved .hist volume (SFX/cache/private DBs).
        selected = [target] if initial and not scan_vols else scan_vols
        old_init(up, all_vols, selected, fscan or initial, gid)
        if initial and not up.stop and up.volstate.get(target, "").startswith("online"):
            marker.write_text("1\n")
    Up2k.init_indexes = init_indexes
