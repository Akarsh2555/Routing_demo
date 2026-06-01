"""
CORS Proxy + Static File Server for EV Routing App
Serves webapp/ files and proxies /api/* requests to the remote routing engine.
"""
import http.server
import json
import os
import urllib.request
import urllib.error

API_BASE = "http://139.59.81.193"
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")
PORT = 8080


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEBAPP_DIR, **kwargs)

    # ── CORS headers ────────────────────────────────────────
    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    # ── OPTIONS preflight ───────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ── Proxy check ─────────────────────────────────────────
    def _is_api(self):
        return self.path.startswith("/api/") or self.path == "/health"

    def _proxy(self, method):
        url = API_BASE + self.path
        body = None
        headers = {}

        if method == "POST":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self._cors_headers()
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        if self._is_api():
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self._is_api():
            self._proxy("POST")
        else:
            self.send_response(405)
            self.end_headers()


if __name__ == "__main__":
    print(f"[*] EV Routing App running at http://localhost:{PORT}")
    print(f"    Proxying API requests to {API_BASE}")
    print(f"    Serving static files from {WEBAPP_DIR}")
    server = http.server.HTTPServer(("", PORT), ProxyHandler)
    server.serve_forever()
