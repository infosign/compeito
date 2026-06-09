# Vendored third-party assets

Self-hosted to remove external CDN dependencies at runtime (the Web UI must work
without reaching unpkg / Google Fonts). Update by re-downloading the same
version and bumping the filename / reference in `src/templates/base.html`.

| File | Version | Source | License |
|------|---------|--------|---------|
| `htmx-2.0.4.min.js` | 2.0.4 | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js | Zero-Clause BSD (0BSD) |
| `../fonts/quicksand-700.woff2` | v37 (latin subset, weight 700) | Google Fonts (Quicksand) | SIL Open Font License 1.1 |

Both licenses permit redistribution. The font file is the `latin` subset only —
it backs the `.logo-text` wordmark, which is ASCII.
