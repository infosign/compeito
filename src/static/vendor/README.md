# Vendored third-party assets

Self-hosted to remove external CDN dependencies at runtime (the Web UI must work
without reaching unpkg / Google Fonts). Update by re-downloading the same
version and bumping the filename / reference in `src/templates/base.html`.

| File | Version | Source | License | License text |
|------|---------|--------|---------|--------------|
| `htmx-2.0.4.min.js` | 2.0.4 | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js | Zero-Clause BSD (0BSD) | `htmx-2.0.4.LICENSE.txt` |
| `../fonts/quicksand-700.woff2` | v37 (latin subset, weight 700) | Google Fonts (Quicksand) | SIL Open Font License 1.1 | `../fonts/Quicksand-OFL.txt` |

Both licenses permit redistribution. **0BSD** imposes no conditions (not even
attribution). **OFL 1.1** requires the license + copyright to ship with the font
(done — see `../fonts/Quicksand-OFL.txt`), forbids selling the font on its own,
and forbids using the reserved name "Quicksand" for modified versions — none of
which we do (the font is embedded unmodified). The font file is the `latin`
subset only; it backs the `.logo-text` wordmark, which is ASCII.
