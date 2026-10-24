"""Local web server: JSON API + static frontend. Python 3.9+, stdlib only.

Run from the repository root:

    python3 web/backend/server.py            # http://127.0.0.1:8000
    PORT=9000 python3 web/backend/server.py

Endpoints (see api/openapi.yaml):
    GET  /api/health
    GET  /api/limit-check?handle=<handle>
    POST /api/limit-check            {"handle", "evidence"?, "description"?}
    GET  /api/limit-check/schema
    POST /api/post-review            {"text"}
    POST /api/chat                   {"message"}
"""

import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "web", "frontend")
sys.path.insert(0, BACKEND_DIR)

from envfile import load_env_file  # noqa: E402

load_env_file(os.path.join(REPO_ROOT, ".env"))

import chat  # noqa: E402
import limit_check  # noqa: E402
import post_review  # noqa: E402
import xapi  # noqa: E402

VERSION = "1.0.0"
MAX_BODY_BYTES = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "XGrowthAssistant/" + VERSION

    # --- helpers -------------------------------------------------------------
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, code, message):
        self._send_json(status, {"error": {"code": code, "message": message}})

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise limit_check.ValidationError("body_too_large", "Request body exceeds 64 KB.")
        raw = self.rfile.read(length) if length else b""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise limit_check.ValidationError("invalid_json", "Request body must be valid UTF-8 JSON.")
        if not isinstance(data, dict):
            raise limit_check.ValidationError("invalid_json", "Request body must be a JSON object.")
        return data

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # --- routing -------------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/api/health":
                return self._send_json(200, {
                    "ok": True,
                    "version": VERSION,
                    "x_api": xapi.integration_status()["state"],
                })
            if path in ("/api/limit-check", "/api/v1/shadowban-check"):
                query = parse_qs(url.query)
                handle = query.get("handle", [None])[0]
                return self._send_json(200, limit_check.evaluate(handle))
            if path == "/api/limit-check/schema":
                return self._send_json(200, limit_check.evidence_schema())
            if path.startswith("/api/"):
                return self._error(404, "not_found", "Unknown endpoint.")
            return self._serve_static(path)
        except limit_check.ValidationError as exc:
            return self._error(400, exc.code, exc.message)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._read_json()
            if path == "/api/limit-check":
                result = limit_check.evaluate(
                    data.get("handle"), data.get("evidence"), data.get("description"))
                return self._send_json(200, result)
            if path == "/api/post-review":
                try:
                    return self._send_json(200, post_review.review(data.get("text")))
                except ValueError as exc:
                    return self._error(400, "invalid_text", str(exc))
            if path == "/api/chat":
                try:
                    return self._send_json(200, chat.respond(data.get("message")))
                except limit_check.ValidationError as exc:
                    return self._error(400, exc.code, exc.message)
                except ValueError as exc:
                    return self._error(400, "invalid_message", str(exc))
            return self._error(404, "not_found", "Unknown endpoint.")
        except limit_check.ValidationError as exc:
            return self._error(400, exc.code, exc.message)

    def do_PUT(self):
        self._error(405, "method_not_allowed", "Use GET or POST.")

    do_DELETE = do_PATCH = do_PUT

    # --- static files ----------------------------------------------------------
    def _serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        target = os.path.realpath(os.path.join(FRONTEND_DIR, path.lstrip("/")))
        if not target.startswith(os.path.realpath(FRONTEND_DIR) + os.sep) or not os.path.isfile(target):
            return self._error(404, "not_found", "File not found.")
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(target, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def make_server(host=None, port=None):
    host = host or os.environ.get("HOST", "127.0.0.1")
    port = int(port if port is not None else os.environ.get("PORT", "8000"))
    return ThreadingHTTPServer((host, port), Handler)


def main():
    httpd = make_server()
    host, port = httpd.server_address[:2]
    print("X Growth Assistant running at http://{}:{}/  (X API: {})".format(
        host, port, xapi.integration_status()["state"]), flush=True)
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

