# foglamp-local

**View a [foglamp](https://foglamp.dev) codebase-scan with foglamp's real renderer — 100% on your machine. Your architecture never leaves your computer.**

foglamp draws a beautiful map of how a codebase works and how it uses AI. Normally you upload a small JSON summary to `foglamp.dev` and get a public link. **foglamp-local** lets you keep that JSON entirely local: it reuses foglamp's public renderer (loaded from their CDN) but embeds *your* data into a page served only from `localhost`, so nothing about your architecture is ever sent anywhere.

Great for private codebases, client work, or anyone who wants the map without the upload.

```
python3 foglamp-local.py run                 # see the built-in example
python3 foglamp-local.py run my-scan.json    # view your own scan
```
→ opens `http://localhost:8788/`. That's it. No install, no dependencies (Python 3 stdlib only).

---

## How it works (and why it's private)

```
your browser ──GET──▶ foglamp-local proxy (:8788, allow-list)
                         ├─ serves the built page (your scan JSON inline)  ── never uploaded
                         └─ forwards ONLY /_next/* asset GETs ──▶ foglamp CDN (public JS/CSS/fonts)
                            blocks  /api/* (favicons), /_vercel/* (analytics), ?_rsc, and ALL POSTs
```

- **`build`** fetches foglamp's server-rendered `/scan/<slug>` page once (the empty renderer "shell"), then swaps *your* scan JSON into its data payload and injects a client-side privacy guard. Output: a self-contained local HTML page.
- **`serve`** runs a tiny stdlib proxy on `:8788`. It serves that page at foglamp's original route path (so the Next.js renderer hydrates correctly) and **reverse-proxies only static `/_next` assets** to foglamp. Everything else is blocked and written to `.serve.log`, so the privacy claim is auditable.

The only network egress is GETs for foglamp's public renderer bundle — identical for every visitor, carrying **zero** of your data. Favicons render blank by design (fetching them would reveal your service domains).

## Get a scan of your codebase

`scan.json` follows foglamp's schema (models, tools, integrations, and the flow graph). The easiest way to produce one is to hand [`PROMPT.md`](PROMPT.md) to an AI coding agent (Claude Code, Cursor, etc.) pointed at your repo — it investigates the code and writes `scan.json`. Then:

```
python3 foglamp-local.py run scan.json
```

See [`example-scan.json`](example-scan.json) for the exact shape (it happens to map *this tool itself*).

## Commands

| command | what it does |
|---|---|
| `run [scan.json]` | fetch shell (once) + build + serve (default) |
| `build [scan.json]` | rebuild the local page from a scan file |
| `serve` | serve the last build |
| `fetch` | (re)download foglamp's renderer shell |

Env: `FOGLAMP_SHELL_URL` (any live `foglamp.dev/scan/<slug>` page to use as the shell — swap it if the default 404s), `PORT` (default `8788`).

## Notes & honesty

- **Not affiliated with foglamp.** This is an unofficial community tool that reuses foglamp's *public* renderer to view scans locally. It does **not** redistribute foglamp's code — the shell and renderer assets are fetched from `foglamp.dev` at runtime (and are gitignored, never committed). Please respect foglamp's terms of service.
- foglamp *can* see that your IP fetched their public asset files (unavoidable when reusing their renderer). Those requests contain none of your architecture. If you want zero contact with foglamp, you'd need a from-scratch renderer instead.
- The scan JSON is a high-level summary you author — no source code or secrets.

## License

MIT — see [LICENSE](LICENSE).
