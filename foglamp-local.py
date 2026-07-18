#!/usr/bin/env python3
"""foglamp-local — view a foglamp codebase-scan with foglamp's real renderer, 100% locally.

Your scan data is embedded into a locally-served page and NEVER uploaded. The only thing
fetched from the network is foglamp's public renderer bundle (JS/CSS/fonts under /_next),
proxied on demand; every other request (/api favicons, /_vercel analytics, RSC prefetch,
and all POSTs) is blocked and logged. So you get the polished foglamp map without sending
a single byte of your architecture to anyone.

Usage:
  python3 foglamp-local.py run  [scan.json]   # fetch shell (once) + build + serve   [default]
  python3 foglamp-local.py build [scan.json]  # rebuild the page from a scan file
  python3 foglamp-local.py serve              # just serve the last build
  python3 foglamp-local.py fetch              # (re)download foglamp's renderer shell

Then open the printed http://localhost:8788/  (Ctrl-C to stop).

Config via env:
  FOGLAMP_SHELL_URL   a foglamp /scan/<slug> page to reuse as the renderer shell
  PORT                default 8788
"""
import sys, os, re, json, pathlib, urllib.request, urllib.error, http.server, time

HERE = pathlib.Path(__file__).parent
SHELL_URL = os.environ.get('FOGLAMP_SHELL_URL', 'https://www.foglamp.dev/scan/sample-codebase-wgwf6i')
ORIGIN = re.match(r'^(https?://[^/]+)', SHELL_URL).group(1)   # e.g. https://www.foglamp.dev
SLUG = re.sub(r'^https?://[^/]+', '', SHELL_URL) or '/'       # e.g. /scan/sample-codebase-wgwf6i
PORT = int(os.environ.get('PORT', '8788'))
SHELL = HERE / '.shell.html'          # foglamp's page, downloaded (gitignored — not redistributed)
VIEWER = HERE / '.viewer.html'        # shell + your data inline (gitignored — your data)
LOG = HERE / '.serve.log'
DEFAULT_SCAN = 'scan.json' if (HERE / 'scan.json').exists() else 'example-scan.json'

# ---- privacy guard injected into the page (belt-and-suspenders; the proxy also blocks) ----
GUARD = ('<script>(function(){var B=/\\/api\\//;'
         'if(window.fetch){var f=window.fetch;window.fetch=function(i){var u=(i&&i.url)||i||"";'
         'return B.test(""+u)?Promise.reject(new Error("blocked-local")):f.apply(this,arguments);};}'
         'try{var d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,"src");'
         'if(d&&d.set)Object.defineProperty(HTMLImageElement.prototype,"src",{configurable:true,enumerable:d.enumerable,'
         'get:function(){return d.get.call(this);},set:function(v){if(typeof v==="string"&&/\\/api\\/favicon/.test(v))'
         'v="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";d.set.call(this,v);}});}catch(e){}})();</script>\n')


def fetch():
    print(f'fetching renderer shell: {SHELL_URL}')
    req = urllib.request.Request(SHELL_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            SHELL.write_bytes(r.read())
    except Exception as e:
        sys.exit(f'could not fetch shell ({e}).\n'
                 f'The sample slug may have expired — set FOGLAMP_SHELL_URL to any live '
                 f'foglamp.dev/scan/<slug> page and retry.')
    if b'\\"data\\":' not in SHELL.read_bytes():
        sys.exit('fetched page has no scan data payload — FOGLAMP_SHELL_URL must be a /scan/<slug> page.')
    print(f'  saved {SHELL.name} ({SHELL.stat().st_size} bytes)')


def build(scan_file):
    if not SHELL.exists():
        fetch()
    html = SHELL.read_text(encoding='utf-8')
    scan = json.loads((HERE / scan_file).read_text(encoding='utf-8'))
    name = scan.get('project', {}).get('name', 'Scan')
    esc = json.dumps(scan, separators=(',', ':'), ensure_ascii=False).replace('\\', '\\\\').replace('"', '\\"')
    pat = re.compile(r'(\\"data\\":)(.*?)(,\\"previous\\":null\}\])', re.S)
    if not pat.search(html):
        sys.exit('shell format changed — could not find the scan data anchor. Re-run `fetch`.')
    html = pat.sub(lambda m: m.group(1) + esc + m.group(3), html, count=1)
    html = re.sub(r'<link rel="preload" as="image" href="/api/favicon[^>]*/?>', '', html)
    html = html.replace('<head>', '<head>\n' + GUARD, 1)
    VIEWER.write_text(html, encoding='utf-8')
    print(f'built {VIEWER.name} from {scan_file} — {len(scan["graph"]["nodes"])} nodes, '
          f'{len(scan["graph"]["edges"])} edges; project: {name}')


def _audit(msg):
    try:
        with open(LOG, 'a') as f:
            f.write(time.strftime('%H:%M:%S ') + msg + '\n')
    except Exception:
        pass


def serve():
    if not VIEWER.exists():
        sys.exit('nothing built yet — run `python3 foglamp-local.py build [scan.json]` first.')

    class H(http.server.BaseHTTPRequestHandler):
        def _s(self, code, body=b'', ctype=None):
            self.send_response(code)
            if ctype:
                self.send_header('content-type', ctype)
            self.send_header('cache-control', 'no-store')
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_POST(self):                       # block every POST (no beacons/uploads)
            _audit('BLOCK POST ' + self.path); self._s(204)

        def do_GET(self):
            path, _, query = self.path.partition('?')
            if path == '/':
                self.send_response(302); self.send_header('location', SLUG); self.end_headers(); return
            if path == SLUG:
                if '_rsc' in query:
                    _audit('BLOCK rsc  ' + self.path); return self._s(204)
                _audit('SERVE page'); return self._s(200, VIEWER.read_bytes(), 'text/html; charset=utf-8')
            if path.startswith('/_next/') or path == '/favicon.ico':   # allow-list: static assets only
                try:
                    req = urllib.request.Request(ORIGIN + self.path, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=25) as r:
                        _audit('PROXY ' + path); return self._s(200, r.read(), r.headers.get('content-type'))
                except urllib.error.HTTPError as e:
                    return self._s(e.code)
                except Exception:
                    return self._s(502)
            _audit('BLOCK ' + self.path); return self._s(204)   # /api, /_vercel, anything else

        def log_message(self, *a):
            pass

    url = f'http://localhost:{PORT}{SLUG}'
    print(f'\n  ✔ foglamp map ready — open:  {url}')
    print(f'    (only foglamp /_next assets are fetched; /api, analytics & POST are blocked — see .serve.log)')
    print(f'    Ctrl-C to stop.\n')
    try:
        http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
    except KeyboardInterrupt:
        print('stopped.')


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'run'
    if cmd == 'fetch':
        fetch()
    elif cmd == 'build':
        build(args[1] if len(args) > 1 else DEFAULT_SCAN)
    elif cmd == 'serve':
        serve()
    elif cmd == 'run':
        build(args[1] if len(args) > 1 else DEFAULT_SCAN)
        serve()
    else:  # treat a bare `foglamp-local.py myscan.json` as `run myscan.json`
        build(cmd)
        serve()


if __name__ == '__main__':
    main()
