# Third-party code

- Copyparty 1.20.26 by 9001 and contributors is vendored as readable runtime
  sources in `vendor/copyparty/`. Its upstream license is retained there.
- Jinja2, MarkupSafe and prebuilt web dependencies are vendored from the matching
  official Copyparty release. Their licenses are retained in
  `vendor/copyparty/res/COPYING.txt` and embedded in the generated application.
- Exact origins and the source commit are recorded in [vendor/README.md](vendor/README.md).
  No upstream SFX is embedded or downloaded during the build.
- MediaWrt's library adapter originated in the MIT-licensed omnia_video_hdd project;
  its copyright notice remains in LICENSE.
- Criterion Editorial styles and palettes were supplied by the project owner;
  they live in `src/web/css/` with MediaWrt interaction/mobile fixes.
- FFmpeg and ffprobe are optional external executables, not bundled here.

MediaWrt's MIT license does not replace third-party licenses.
