# Code and design provenance

- Copyparty 1.20.26, by 9001 and contributors:
  <https://github.com/9001/copyparty/tree/v1.20.26>.
  The unmodified upstream `copyparty-sfx.py` is embedded with SHA-256
  `8f9a0def8a9c15252a06395781ec083372043b60caa80fb33c3d6dafa7f1b40a`.
  Copyparty and bundled-component licenses remain inside the SFX and extracted
  runtime. MediaWrt's MIT license does not replace dependency licenses.
- The library adapter originated in the MIT-licensed
  omnia_video_hdd project. The original copyright notice is retained in LICENSE.
- Criterion Editorial base styles and the ten color palettes were supplied by
  the project owner. They are integrated into `src/web/css/base.css` and `src/web/css/palettes/` with scoped theme tokens
  and application-specific accessibility, mobile, gallery and fullscreen fixes.
  Showcase scripts and demo media are not included.
- FFmpeg and ffprobe are external executables, not bundled in this repository.

Copyparty provides HTTP/Range, VFS, authentication/sessions, upload, SQLite indexing,
move/rename, the fallback file browser and thumbnail conversion pipeline.
MediaWrt adds the single-file launcher, media-center API, application UI and build.
