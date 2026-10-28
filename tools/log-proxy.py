"""Logging proxy between opencode and ollama: see the exact bytes opencode sends.

    python3 -I tools/log-proxy.py [port]        # default 11435, forwards to :11434

Then point the ollama provider in opencode.json at it:
    "options": { "baseURL": "http://127.0.0.1:11435/v1" }

Every POST body lands in ./dumps/NNN-<path>.json next to where you ran it; the
response is streamed back unchanged. Stdlib only. Framing is HTTP/1.0 +
Connection: close, so SSE streams end when the upstream closes, without
re-chunking. Used in docs/spikes/ to measure the host's prompt floor.
"""
import http.server
import json
import os
import sys
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("UPSTREAM", "http://127.0.0.1:11434")
DUMPS = os.path.join(os.getcwd(), "dumps")
os.makedirs(DUMPS, exist_ok=True)
counter = [0]


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):  # quieter than the default
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _forward(self, body):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection", "accept-encoding"):
                continue
            req.add_header(k, v)
        if body is not None:
            req.add_header("Content-Length", str(len(body)))
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            resp = e
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() in ("transfer-encoding", "content-length", "connection"):
                continue
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def do_GET(self):
        self._forward(None)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        counter[0] += 1
        name = "%03d-%s.json" % (counter[0], self.path.strip("/").replace("/", "_"))
        with open(os.path.join(DUMPS, name), "wb") as f:
            f.write(body)
        sys.stderr.write("dumped %s (%d bytes)\n" % (name, len(body)))
        self._forward(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    sys.stderr.write("log-proxy on 127.0.0.1:%d -> %s, dumps in %s\n" % (port, UPSTREAM, DUMPS))
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
