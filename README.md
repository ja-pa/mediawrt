# MediaWrt

A self-hosted, Kodi-inspired web media center distributed as **one Python file**.
Browse films, TV shows, music and photos, or manage the underlying files.
MediaWrt embeds the pinned Copyparty 1.20.26 engine for authentication, uploads,
HTTP Range streaming, indexing and thumbnail generation.

This repository contains the application only. OpenWrt packaging and deployment
are maintained separately.

## Run

Use Python 3.11 or newer (3.11 is tested). No pip installation is needed for the
bundled application. FFmpeg and ffprobe on PATH are optional for thumbnails and
technical/audio metadata.

1. Download or clone this repository.
2. Copy `config.example.json` to `config.json`.
3. Set `media` to an existing media directory and `state_dir` to a private writable
   directory outside your media. Relative paths are resolved from the working directory.
4. Start:

```sh
python mediawrt.py --config config.json --check
python mediawrt.py --config config.json
```

Open <http://127.0.0.1:3924/media/>. The example binds to localhost and allows
anonymous read-only access. `--check` validates configuration without writing files.

To serve your LAN, set `listen` to the server's LAN address and `allow_cidr` to
your LAN subnet. Authentication uses HTTP by default; use a TLS reverse proxy
when traffic crosses an untrusted network. Do not put configuration or account
files in shared media directories.

## Features

- Film and episode libraries, search, sorting, favorites, watched state and resume.
- Local posters/NFO descriptions and cached FFmpeg previews when artwork is missing.
- HTML video playback, SRT/VTT subtitles, fullscreen and picture-in-picture where supported.
- Music albums/artists/tracks, persistent player, queue, shuffle and repeat.
- Photo gallery, zoom and slideshow.
- File browser, uploads, folder creation, rename and move with collision checks
  and optional related subtitles/artwork.
- Czech and English UI; ten Criterion Editorial color themes under Settings.
- Optional accounts with separate upload, move and explicit server-admin permissions.

Favorites, history, queue and theme preferences stay in the browser. They are
not synchronized by signing in. Switching themes writes no server state.

## Accounts

`anonymous` accepts `r` (read), `rw` (read/upload), `rwm` (also move), or an empty
string to require an account. Define accounts using:

```json
{
  "name": "editor",
  "password": "replace-with-your-own-password",
  "permissions": "rwm"
}
```

Put entries in the `users` array or point `users_file` at a private JSON array.
`server_admins: ["editor"]` separately grants metadata editing and visibility of
server storage paths. File-management permissions alone do not grant these rights.

## Storage and resource usage

`state_dir` provides defaults for `database`, `cache`, `runtime`, `temp` and `logs`.
Override them independently with `database_dir`, `cache_dir`, `runtime_dir`,
`temp_dir` and `logs_dir`. Put persistent databases/cache on your chosen disk and
runtime/temp on RAM-backed storage if desired. `file_logging` defaults to false.

The first index is built automatically; subsequent scans are manual. Full media
hashing and periodic rescanning are disabled. Previews are JPEG files in the cache,
not SQLite blobs. SQLite stores the catalog and extracted metadata. Thumbnail work
uses one worker with at most eight queued tasks; the UI requests at most two previews
at a time for visible/nearby cards. Cached results are reused; changes to paths or
modification times, or removal of cache files, can trigger regeneration.
Automatic cache cleanup is disabled by default, so administrators should monitor size.

`thumbnails: true` enables FFmpeg previews. `library_sources`, for example
`[{"path":"TV","kind":"series"}]`, supplies series classification hints; filenames
such as `S01E02` and `1x02` are also recognized.

## Build and test

The checked-in `mediawrt.py` is ready to run. Development sources are in `src/`;
rebuild after changing them:

```sh
python build.py --download-upstream
python -m unittest discover -s tests -v
node --check src/app.js
```

The download is explicit and its SHA-256 is checked before use. For an offline
build, supply an existing pinned release:

```sh
python build.py /path/to/copyparty-sfx-1.20.26.py
```

The build embeds HTML/CSS/JavaScript, adapters and the upstream SFX. The resulting
application needs no source directory, external fonts or CDN. Integration tests start
an actual bundled server with temporary data; they do not contact a deployed server.

## Current limits

Browser codec support determines playback; there is no audio/video transcoding or
stereo conversion. Simple uploads cannot resume after page reload. File deletion and
cross-device moves are not implemented. Duplicate-content identities may share
personal playback state. Client-side whole-library operations cap at 6,000 entries;
the server filters the entire index, so very large libraries need performance testing.
Personal-data export includes the queue, but import currently restores only history
and favorites. Online metadata providers and statistics collection are not implemented.
System fullscreen behavior on older Android devices still needs device-specific testing.

## License

MediaWrt code is MIT licensed; see [LICENSE](LICENSE).
Bundled dependencies retain their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).
