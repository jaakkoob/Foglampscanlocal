#!/usr/bin/env python3
# The Unlicense — public domain, no rights reserved
import sys, os, re, json, time, pathlib, urllib.request, urllib.error, http.server
from html import escape

HERE = pathlib.Path(__file__).parent
SHELL_URL = os.environ.get('FOGLAMP_SHELL_URL', 'https://www.foglamp.dev/scan/sample-codebase-wgwf6i')
ORIGIN = re.match(r'^(https?://[^/]+)', SHELL_URL).group(1)
SLUG = re.sub(r'^https?://[^/]+', '', SHELL_URL) or '/'
PORT = int(os.environ.get('PORT', '8788'))
SHELL, VIEWER, LOG = HERE / '.shell.html', HERE / '.viewer.html', HERE / '.serve.log'
UA = {'User-Agent': 'Mozilla/5.0'}

PROMPT = '''Analyze THIS repository and write a foglamp "codebase scan" to scan.json — a map of how the
codebase works and how it uses AI. Produce ONLY the JSON below. Nothing is uploaded — a local
tool renders it on localhost, so your architecture never leaves your machine.

## Steps
1. Investigate the repo and build the JSON below. Write it to scan.json.
2. Then run:  python3 foglamp-local.py run scan.json   → opens http://localhost:8788/ with
   foglamp's real renderer, fully local.

## How to investigate
- Find where AI runs: generateText / streamText / generateObject / streamObject,
  @ai-sdk/* providers, agent loops, tool definitions (tool({...})).
- Identify the models and their provider (OpenAI, Anthropic, Google, …).
- Identify tools models can call (Exa, Firecrawl, Parallel, DB queries, internal
  functions) and external integrations/services.
- Map the business logic too: the internal services/pipelines the product is
  built from (billing, ingestion, background workers, domain services) — these
  become "service" nodes, and the interesting sentence goes on the edge
  (e.g. "charges Stripe on trial end").
- Map the main flows: entry points (routes, webhooks, pages, CLIs), scheduled jobs
  (crons/queues/workers), the agents, the models/tools they use, and the
  datastores/services they read and write.

## Output contract — write EXACTLY this shape to scan.json
{
  "version": 1,
  "project": {
    "name": "string (<=48)",
    "slug": "lowercase-dashed (<=48)",
    "tagline": "one line (<=80, optional)",
    "iconDomain": "favicon domain for the project, e.g. acme.com (optional)",
    "date": "YYYY-MM-DD"
  },
  "stats": { "agents": 0, "models": 0, "tools": 0, "integrations": 0 },
  "topModels":       [ { "id": "gpt-4o", "label": "GPT-4o", "domain": "openai.com" } ],
  "topTools":        [ { "id": "exa", "label": "Exa", "domain": "exa.ai" } ],
  "topIntegrations": [ { "id": "stripe", "label": "Stripe", "domain": "stripe.com" } ],
  "graph": {
    "nodes": [
      { "id": "chat", "label": "Dashboard chat", "kind": "entry", "sub": "/api/chat" },
      { "id": "agent", "label": "Support agent", "kind": "agent", "sub": "streamText",
        "sourceRef": "src/agents/support.ts:42",
        "detail": "Answers tickets with order lookups (<=200, optional)" },
      { "id": "gpt4o", "label": "GPT-4o", "kind": "model", "domain": "openai.com" },
      { "id": "billing", "label": "Billing service", "kind": "service",
        "sourceRef": "src/services/billing.ts" },
      { "id": "pg", "label": "Postgres", "kind": "store", "domain": "postgresql.org" }
    ],
    "edges": [
      { "from": "chat", "to": "agent", "kind": "triggers" },
      { "from": "agent", "to": "gpt4o", "kind": "calls" },
      { "from": "billing", "to": "pg", "kind": "writes", "label": "charges on trial end" }
    ]
  }
}

## Rules (these keep every scan consistent — do not break them)
- Caps: topModels <= 3, topTools <= 10, topIntegrations <= 10, graph.nodes <= 60,
  graph.edges <= 120. One map holds everything — AI flows AND business logic.
  Big maps are welcome (the viewer pans); aim for 20-40 nodes on a substantial
  codebase. Rich, not sparse — but every node must earn its place.
- Give every distinct agent its OWN node when there are <= 10 agents; only
  merge agents into one node when they are numerous and near-identical (then
  say so in sub, e.g. "12 near-identical scrapers"). Chain agents with
  agent->agent edges when one feeds the next.
- group (optional, <=24): tag related nodes with a shared group name — those
  nodes render as one labeled vertical stack. Group by feature/domain the way a
  team would say it ("Billing", "Ingestion", "Setup pipeline"), not by file
  layout. Use 2-3 groups of 3-6 nodes; leave hub-and-spoke nodes ungrouped.
- Node labels <= 28 chars, sub <= 40, edge labels <= 24.
- kind is one of: entry (trigger/route/page/CLI), cron (scheduled job), agent,
  model, tool, service (internal business-logic module/pipeline the project
  owns), store (DB/cache/index), external (3rd-party API).
- Edge kind (optional): "calls" | "reads" | "writes" | "triggers" — what the
  connection does. Prefer setting it; it's shown quietly (revealed when a flow
  is traced). Add a label only when a specific phrase says more (e.g. "charges
  on trial end" — put the business logic on edges); labels are always visible.
- domain is a favicon domain with no scheme (openai.com, anthropic.com, exa.ai,
  clickhouse.com). Add it to anything a recognizable company/product owns; omit it
  for purely internal nodes (entries, crons, services, internal tools). Use the
  product domain for models (gemini.google.com for Gemini, claude.ai for Claude).
- detail (optional, <=200) is shown when a node is clicked — one sentence of
  what it does. sourceRef (optional, <=120) is the repo path (plus :line) where
  the node lives, e.g. "src/agents/support.ts:42" — add it to internal nodes so
  teammates can jump to code.
- Every edge's from/to must reference an existing node id; ids unique.
- Use today's date for project.date.'''

EXAMPLE = '''{
  "version": 1,
  "project": { "name": "Localhost Foglamp Viewer", "slug": "localhost-foglamp-viewer",
    "tagline": "foglamp's renderer, your data, nothing uploaded", "iconDomain": "foglamp.dev",
    "date": "2026-07-17" },
  "stats": { "agents": 0, "models": 0, "tools": 2, "integrations": 1 },
  "topModels": [],
  "topTools": [ { "id": "curl", "label": "curl (fetch shell)" },
                { "id": "pyhttp", "label": "Python http.server", "domain": "python.org" } ],
  "topIntegrations": [ { "id": "foglamp", "label": "Foglamp CDN", "domain": "foglamp.dev" } ],
  "graph": {
    "nodes": [
      { "id": "browser", "label": "Your browser", "kind": "entry", "sub": "localhost:8788", "detail": "Opens the map and runs foglamp's renderer locally; the graph hydrates from data embedded in the page." },
      { "id": "proxy", "label": "serve proxy", "kind": "service", "sub": ":8788 · Python", "detail": "Serves the built page and reverse-proxies renderer asset requests. Nothing runs on foglamp's servers.", "group": "Local server" },
      { "id": "route", "label": "Route matcher", "kind": "service", "sub": "/ -> /scan/<slug>", "detail": "Serves the page at foglamp's original route path so Next hydration matches.", "group": "Local server" },
      { "id": "allowlist", "label": "Privacy allow-list", "kind": "service", "sub": "blocks /api · _vercel · POST", "detail": "Forwards only /_next asset GETs to foglamp; blocks favicons, analytics, RSC prefetch and all POSTs.", "group": "Local server" },
      { "id": "builder", "label": "build step", "kind": "service", "sub": "embed scan -> shell", "detail": "Swaps the scan JSON into the shell's data payload and injects the privacy guard.", "group": "Page build" },
      { "id": "shell", "label": "Foglamp shell", "kind": "store", "sub": "fetched once", "detail": "foglamp's server-rendered /scan page — the empty renderer container.", "group": "Page build" },
      { "id": "scandata", "label": "Scan JSON", "kind": "store", "sub": "foglamp schema", "detail": "The architecture map data. Embedded inline — never uploaded.", "group": "Page build" },
      { "id": "page", "label": "Built page", "kind": "store", "sub": "self-contained HTML", "detail": "Shell + inline scan data; only ever served from localhost.", "group": "Page build" },
      { "id": "cdn", "label": "Foglamp CDN", "kind": "external", "sub": "/_next JS · CSS · fonts", "domain": "foglamp.dev", "detail": "Serves the public renderer bundle — identical for every visitor, carrying none of your data." }
    ],
    "edges": [
      { "from": "builder", "to": "scandata", "kind": "reads" },
      { "from": "builder", "to": "shell", "kind": "reads" },
      { "from": "builder", "to": "page", "kind": "writes", "label": "embed scan -> HTML" },
      { "from": "browser", "to": "proxy", "kind": "calls", "label": "GET localhost:8788" },
      { "from": "proxy", "to": "route", "kind": "calls", "label": "match /scan/<slug>" },
      { "from": "route", "to": "page", "kind": "reads", "label": "serve built page" },
      { "from": "proxy", "to": "allowlist", "kind": "calls", "label": "screen every request" },
      { "from": "allowlist", "to": "cdn", "kind": "reads", "label": "/_next only · /api blocked" },
      { "from": "cdn", "to": "browser", "kind": "reads", "label": "renderer bundle" },
      { "from": "page", "to": "browser", "kind": "reads", "label": "inline data · no upload" }
    ]
  }
}'''

GUARD = ('<script>(function(){var B=/\\/api\\//;'
         'if(window.fetch){var f=window.fetch;window.fetch=function(i){var u=(i&&i.url)||i||"";'
         'return B.test(""+u)?Promise.reject(new Error("blocked-local")):f.apply(this,arguments);};}'
         'try{var d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,"src");'
         'if(d&&d.set)Object.defineProperty(HTMLImageElement.prototype,"src",{configurable:true,enumerable:d.enumerable,'
         'get:function(){return d.get.call(this);},set:function(v){if(typeof v==="string"&&/\\/api\\/favicon/.test(v))'
         'v="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";d.set.call(this,v);}});}catch(e){}})();</script>')

ONBOARD = '''<!DOCTYPE html><html lang="en" class="@HTML@"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>Foglamp Local</title>@CSS@</head><body class="@BODY@">@THEME@<div class="fixed inset-0 overflow-hidden bg-neutral-100 text-foreground dark:bg-background"><section class="absolute inset-0 z-0"><div class="absolute inset-0 overflow-hidden bg-[linear-gradient(color-mix(in_oklab,var(--border)_45%,transparent)_1px,transparent_1px),linear-gradient(90deg,color-mix(in_oklab,var(--border)_45%,transparent)_1px,transparent_1px)] bg-size-[56px_56px] bg-center dark:bg-[linear-gradient(color-mix(in_oklab,var(--border)_10%,transparent)_1px,transparent_1px),linear-gradient(90deg,color-mix(in_oklab,var(--border)_10%,transparent)_1px,transparent_1px)]"></div></section><div class="absolute top-6 left-6 z-20"><a class="flex w-fit items-center gap-2 rounded-full bg-card px-4 py-2.5 shadow-(--custom-shadow) transition-opacity hover:opacity-80" target="_blank" href="https://foglamp.dev"><span class="text-xs text-muted-foreground">Powered by</span><span class="flex items-center gap-1.5"><svg viewBox="0 0 96 48" class="h-2.5 w-auto" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="24" cy="24" r="24" class="fill-[#1e1e1e] dark:fill-[#EEE]"></circle><circle cx="48" cy="24" r="24" fill="#0090FD"></circle><circle cx="72" cy="24" r="24" fill="#FF5513"></circle></svg><span class="font-display text-sm font-semibold tracking-tight select-none">Foglamp</span></span></a></div><div class="absolute inset-0 z-10 flex items-center justify-center p-6"><div data-slot="card" data-size="default" class="group/card shadow-(--custom-shadow) corner-squircle bg-card text-sm text-card-foreground flex max-h-[50dvh] w-full max-w-2xl flex-col gap-4 overflow-hidden rounded-[36px] px-5 py-5"><h1 class="font-display text-lg font-semibold tracking-tight">Scan your codebase</h1><p class="text-sm text-muted-foreground">Paste this prompt into an AI coding agent in your repo — it investigates the code and writes <span class="font-mono text-foreground">scan.json</span>. Then run <span class="font-mono text-foreground">python3 foglamp-local.py run scan.json</span> — the map renders right here, fully local, nothing uploaded.</p><pre class="scroll-fade no-scrollbar corner-squircle min-h-0 flex-1 overflow-y-auto rounded-2xl bg-muted px-4 py-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">@PROMPT@</pre><div class="flex"><button id="copy" type="button" tabindex="0" data-slot="button" class="group/button inline-flex cursor-pointer items-center justify-center rounded-full bg-clip-padding text-sm font-medium whitespace-nowrap transition-all hover:duration-150 outline-none select-none focus-visible:border-ring focus-visible:ring-[1.5px] focus-visible:ring-ring/50 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-[1.5px] aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&amp;_svg]:pointer-events-none [&amp;_svg]:shrink-0 [&amp;_svg:not([class*=&#x27;size-&#x27;])]:size-3.5 shadow-(--custom-outline-shadow) bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:bg-card dark:hover:bg-muted h-8 gap-[5px] px-3 in-data-[slot=button-group]:rounded-full has-[&gt;svg:first-child]:pl-2.5 has-[&gt;svg:last-child]:pr-2.5 w-fit"><span class="relative inline-flex"><span class="inline-flex"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="tabler-icon tabler-icon-share-2 "><path d="M8 9h-1a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-8a2 2 0 0 0 -2 -2h-1"></path><path d="M12 14v-11"></path><path d="M9 6l3 -3l3 3"></path></svg></span></span><span id="copy-label">Copy prompt</span></button></div></div></div></div><script>(function(){var p=@PROMPTJS@,b=document.getElementById("copy"),l=document.getElementById("copy-label");function done(){l.textContent="Copied ✓";setTimeout(function(){l.textContent="Copy prompt"},1400)}function legacy(){var t=document.createElement("textarea");t.value=p;t.style.position="fixed";t.style.opacity="0";document.body.appendChild(t);t.select();var ok=false;try{ok=document.execCommand("copy")}catch(e){}t.remove();return ok}function manual(){var r=document.createRange();r.selectNodeContents(document.querySelector("pre"));var s=getSelection();s.removeAllRanges();s.addRange(r);l.textContent="Press ⌘C / Ctrl-C";setTimeout(function(){l.textContent="Copy prompt"},2500)}function fail(){legacy()?done():manual()}b.addEventListener("click",function(){if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(p).then(done,fail)}else{fail()}})})();</script></body></html>'''


def audit(msg):
    try:
        with LOG.open('a') as f:
            f.write(time.strftime('%H:%M:%S ') + msg + '\n')
    except OSError:
        pass


def fetch():
    print(f'fetching renderer shell: {SHELL_URL}')
    try:
        with urllib.request.urlopen(urllib.request.Request(SHELL_URL, headers=UA), timeout=30) as r:
            page = r.read()
    except Exception as e:
        sys.exit(f'could not fetch shell ({e}) — set FOGLAMP_SHELL_URL to any live '
                 f'foglamp.dev/scan/<slug> page and retry')
    if b'\\"data\\":' not in page:
        sys.exit('fetched page has no scan data payload — FOGLAMP_SHELL_URL must be a /scan/<slug> page')
    SHELL.write_bytes(page)
    print(f'  saved {SHELL.name} ({len(page):,} bytes)')


def ensure_shell():
    if not SHELL.exists():
        fetch()


def build(arg=None):
    ensure_shell()
    src = pathlib.Path(arg or 'scan.json')
    if arg and not src.exists():
        sys.exit(f'{src} not found')
    scan = json.loads(src.read_text(encoding='utf-8')) if src.exists() else json.loads(EXAMPLE)
    origin = src.name if src.exists() else 'embedded example'
    data = json.dumps(scan, separators=(',', ':'), ensure_ascii=False).replace('\\', '\\\\').replace('"', '\\"')
    html = SHELL.read_text(encoding='utf-8')
    anchor = re.compile(r'(\\"data\\":)(.*?)(,\\"previous\\":null\}\])', re.S)
    if not anchor.search(html):
        sys.exit('shell format changed — could not find the scan data anchor; re-run fetch')
    html = anchor.sub(lambda m: m.group(1) + data + m.group(3), html, count=1)
    html = re.sub(r'<link rel="preload" as="image" href="/api/favicon[^>]*/>', '', html)
    html = html.replace('<head>', '<head>' + GUARD, 1)
    VIEWER.write_text(html, encoding='utf-8')
    graph = scan.get('graph', {})
    print(f'built {VIEWER.name} from {origin} — {scan.get("project", {}).get("name", "?")}: '
          f'{len(graph.get("nodes", []))} nodes, {len(graph.get("edges", []))} edges')


def onboarding():
    ensure_shell()
    shell = SHELL.read_text(encoding='utf-8')
    theme = re.search(r'<script>\(\(a,b.*?</script>', shell, re.S)
    cls = lambda tag: (re.search(rf'<{tag}[^>]* class="([^"]*)"', shell) or [None, ''])[1]
    return (ONBOARD.replace('@CSS@', ''.join(re.findall(r'<link rel="stylesheet"[^>]*>', shell)))
            .replace('@HTML@', cls('html'))
            .replace('@BODY@', cls('body'))
            .replace('@THEME@', theme.group(0) if theme else '')
            .replace('@PROMPT@', escape(PROMPT))
            .replace('@PROMPTJS@', json.dumps(PROMPT).replace('<', '\\u003c'))).encode('utf-8')


def serve(pages, msg):
    class H(http.server.BaseHTTPRequestHandler):
        def _s(self, code, body=b'', ctype=None):
            self.send_response(code)
            if ctype:
                self.send_header('content-type', ctype)
            self.send_header('cache-control', 'no-store')
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_POST(self):
            audit('BLOCK POST ' + self.path)
            self._s(204)

        def do_GET(self):
            path, _, query = self.path.partition('?')
            page = pages.get(path)
            if page is not None:
                if '_rsc' in query:
                    audit('BLOCK rsc ' + self.path)
                    return self._s(204)
                audit('SERVE ' + path)
                return self._s(200, page, 'text/html; charset=utf-8')
            if path == '/':
                self.send_response(302)
                self.send_header('location', next(iter(pages)))
                self.end_headers()
                return
            if path.startswith('/_next/') or path == '/favicon.ico':
                try:
                    with urllib.request.urlopen(urllib.request.Request(ORIGIN + self.path, headers=UA), timeout=25) as r:
                        audit('PROXY ' + path)
                        return self._s(200, r.read(), r.headers.get('content-type'))
                except urllib.error.HTTPError as e:
                    return self._s(e.code)
                except Exception:
                    return self._s(502)
            audit('BLOCK ' + self.path)
            return self._s(204)

        def log_message(self, *a):
            pass

    print(f'\n  ✔ {msg} — open:  http://localhost:{PORT}/')
    print('    only foglamp /_next asset GETs leave your machine; /api, analytics & POST are blocked — audit: .serve.log')
    print('    Ctrl-C to stop.\n')
    try:
        http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
    except KeyboardInterrupt:
        print('stopped.')
    except OSError as e:
        sys.exit(f'cannot listen on port {PORT} ({e}) — set PORT and retry')


def run_map(arg=None):
    build(arg)
    serve({SLUG: VIEWER.read_bytes()}, 'foglamp map ready')


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else None
    arg = args[1] if len(args) > 1 else None
    if cmd == 'fetch':
        fetch()
    elif cmd == 'build':
        build(arg)
    elif cmd == 'serve':
        if not VIEWER.exists():
            sys.exit('nothing built yet — run: python3 foglamp-local.py run [scan.json]')
        serve({SLUG: VIEWER.read_bytes()}, 'foglamp map ready')
    elif cmd == 'run':
        run_map(arg)
    elif cmd is None:
        if pathlib.Path('scan.json').exists():
            run_map()
        else:
            serve({'/': onboarding()}, 'no scan.json yet — copy the prompt into your AI agent')
    else:
        run_map(cmd)


if __name__ == '__main__':
    main()
