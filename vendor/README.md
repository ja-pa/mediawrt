# Vendored runtime

- `copyparty/`: runtime package from Copyparty **1.20.26**, upstream commit
  `7ccebb69487ba76232f96f5591cbd614eef765d2`:
  https://github.com/9001/copyparty/tree/v1.20.26/copyparty
  Python sources are copied from that tag, not the stripped SFX sources.
  Upstream's LICENSE is in `copyparty/LICENSE`.
- Missing prebuilt web dependencies and `res/COPYING.txt` come from the matching
  official `copyparty-sfx.py` release (SHA-256
  `8f9a0def8a9c15252a06395781ec083372043b60caa80fb33c3d6dafa7f1b40a`).
  Gzip assets are stored decompressed; original source assets take precedence.
- `jinja2/` (2.11.3) and `markupsafe/` are the pure-Python runtime copies shipped
  in that SFX, including upstream's compatibility adjustments. Their notices and
  the web dependency licenses are retained in `copyparty/res/COPYING.txt`.

No SFX, upstream Git history, development environment or release download is needed
by our build. Optional FTP/TFTP packages from the SFX are not included: MediaWrt
uses HTTP only. Keep this provenance and licenses when updating vendored sources.
