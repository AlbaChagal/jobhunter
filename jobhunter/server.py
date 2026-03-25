"""Local HTTP server for jobhunter — tracks applied jobs across sessions."""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

PORT = 8765


def _read_db(db_path: Path) -> dict:
    if db_path.exists():
        try:
            return json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"applied": []}


def _write_db(db_path: Path, data: dict) -> None:
    tmp = db_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(db_path)


class _Handler(BaseHTTPRequestHandler):
    # Set by JobHunterServer before serving
    report_path: Path
    db_path: Path

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # suppress default request logging

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_file(self.__class__.report_path, "text/html; charset=utf-8")
        elif path == "/api/applied":
            db = _read_db(self.__class__.db_path)
            self._send_json({"applied": db.get("applied", [])})
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/applied":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        job_id = body.get("job_id", "")
        if not job_id:
            self._send_json({"error": "job_id required"}, 400)
            return
        db = _read_db(self.__class__.db_path)
        if job_id not in db["applied"]:
            db["applied"].append(job_id)
            _write_db(self.__class__.db_path, db)
        self._send_json({"applied": db["applied"]})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        # Expect /api/applied/{job_id}
        prefix = "/api/applied/"
        if not path.startswith(prefix):
            self.send_error(404)
            return
        job_id = path[len(prefix):]
        db = _read_db(self.__class__.db_path)
        db["applied"] = [j for j in db["applied"] if j != job_id]
        _write_db(self.__class__.db_path, db)
        self._send_json({"applied": db["applied"]})


class JobHunterServer:
    """
    Lightweight local HTTP server for the jobhunter HTML report.

    Args:
        report_path: Path to the generated HTML report file.
        db_path: Path to the applied-jobs JSON database (created if absent).
        port: TCP port to listen on. Defaults to 8765.
    """

    def __init__(self, report_path: str, db_path: str | None = None, port: int = PORT) -> None:
        self.report_path = Path(report_path).resolve()
        if db_path:
            self.db_path = Path(db_path).resolve()
        else:
            self.db_path = self.report_path.parent / "db.json"
        self.port = port

    def start(self) -> None:
        """Start the server (blocking). Opens the report in the default browser."""
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report not found: {self.report_path}")

        # Initialise db if missing
        if not self.db_path.exists():
            _write_db(self.db_path, {"applied": []})

        # Inject paths into handler class (simple class-level state)
        _Handler.report_path = self.report_path
        _Handler.db_path = self.db_path

        url = f"http://localhost:{self.port}"
        server = HTTPServer(("localhost", self.port), _Handler)
        print(f"Serving report at {url}")
        print(f"Applied jobs stored in {self.db_path}")
        print("Press Ctrl+C to stop.\n")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
