# MediaWrt

A Kodi-inspired web media library with a file manager, built on Copyparty.
Runs as one Python file on OpenWrt, Linux, Windows or macOS; no pip packages,
Node.js or CDN required at runtime. Python 3.11+; FFmpeg/ffprobe are optional.
OpenWrt packaging lives outside this application repository.

## Run

Copy `config.example.json` to `config.json`, set `media` to an existing directory
and `state_dir` to private writable storage, then run:

```sh
python mediawrt.py --config config.json --check
python mediawrt.py --config config.json
```

Open <http://127.0.0.1:3924/media/>. The example allows anonymous read-only access.
Relative paths resolve against the configuration file, regardless of working directory.
Set `listen` and optionally `allow_cidr` for LAN access. HTTP is the default;
use a TLS proxy when needed.

## Storage

- `database_dir`, `cache_dir`, `logs_dir` default to subdirectories of `state_dir`
  (default: `state` beside the configuration). These are persistent.
- `runtime_dir`, `temp_dir` default to an instance-specific system temporary directory.
  OpenWrt normally backs `/tmp` with RAM; other systems may use disk.
- File logging and periodic rescans are disabled. Initial indexing runs once;
  subsequent scans require an explicit request and write permission.
- Thumbnails are opt-in (`thumbnails: true`), stored as JPEG files, and reused.
  One thumbnail worker has eight queue slots. Metadata has its own single-worker
  queue. Cache eviction is off by default.
- Browser history, favorites, playback queue and theme stay in localStorage.

For an OpenWrt disk mounted at `/mnt/media`, an application configuration can use:

```json
{
  "media": "/mnt/media",
  "state_dir": "/mnt/media/.mediawrt",
  "reserve_private_state": true,
  "required_mount": "/mnt/media",
  "storage_policy": "pinned-or-ram",
  "runtime_dir": "/tmp/mediawrt/runtime",
  "temp_dir": "/tmp/mediawrt/temp",
  "listen": "0.0.0.0",
  "port": 3924,
  "anonymous": "r"
}
```

`required_mount` refuses startup if that filesystem is not mounted. The optional
`pinned-or-ram` policy limits configured write directories to the media filesystem
or `/tmp`; it is intended for OpenWrt, not a requirement on other platforms.
These are startup checks, not protection against unplugging a running disk.
Do not expose state/configuration files through another file server.

## Accounts

`anonymous` accepts `r`, `rw`, `rwm`, or an empty string to require login.
Use `users` (or a private `users_file` JSON array) for accounts:

```json
[{"name":"editor","password":"replace-me","permissions":"rwm"}]
```

`r` reads, `w` uploads/creates directories and requests scans, `m` moves/renames.
`server_admins: ["editor"]` additionally permits metadata edits and storage-path
visibility. The file manager supports upload, rename and same-filesystem moves.
Deletion and resumable uploads are not implemented.

## Source and build

```text
src/server/          Python launcher, library and media APIs
src/web/index.html   Application shell
src/web/js/          UI logic and separate translations
src/web/css/base.css Shared layout, player and responsive styles
src/web/css/palettes/ One CSS file per selectable theme
vendor/             Copyparty sources, bundled dependencies and licenses
build.py            Packs local sources into mediawrt.py
mediawrt.py         Ready-to-run generated application
tests/             Integration and configuration tests
```

Edit sources, then rebuild. No frontend bundler is needed:

```sh
python build.py
python -m unittest discover -s tests -v
node --check src/web/js/app.js
```

Builds use only checked-in sources under `src/` and `vendor/`; no downloads,
SFX cache or pip installation are needed. `python build.py --output /path/mediawrt.py`
chooses the output file. Vendored versions and licenses are listed in
[vendor/README.md](vendor/README.md).
On systems with a RAM-backed temporary directory, set `TMPDIR` to a disk-backed
scratch directory when running upload/move tests; Copyparty rejects RAM-only uploads.

CSS files remain separate inside the bundle and over HTTP; only the selected palette
is requested. Node is only useful for development syntax checks.

## Limits

Playback depends on browser codecs; there is no transcoding or surround-to-stereo
conversion. Statistics are not collected. The catalog currently filters the whole
index in memory, so very large libraries need further optimization for small routers.
Client-wide operations stop at 6,000 entries. Duplicate-content IDs can share playback
state. Personal-data import restores favorites/history but not the exported queue.
Older Android fullscreen still needs physical-device testing.

MIT; see [LICENSE](LICENSE) and [dependency notices](THIRD_PARTY.md).
