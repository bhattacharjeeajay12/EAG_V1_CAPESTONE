from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Tuple

HOST = "127.0.0.1"
PORT = 8765


class MCPHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        # Keep server quiet; rely on client-side structured logs
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {"raw": body}

        if self.path == "/echo":
            self._send(200, {"echo": data})
        else:
            self._send(404, {"error": "not_found"})


def run_server(host: str = HOST, port: int = PORT) -> Tuple[str, int]:
    server = HTTPServer((host, port), MCPHandler)
    print(f"MCP server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return host, port


if __name__ == "__main__":
    run_server()
