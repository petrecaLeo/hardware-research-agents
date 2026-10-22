import asyncio
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from researcher.coordinator import research
from researcher.terminal import print_event

# Só esta máquina acessa: cada pesquisa gasta a chave do .env.
HOST, PORT = "127.0.0.1", 8000
ALLOWED_HOSTS = {f"{HOST}:{PORT}", f"localhost:{PORT}"}
WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC = {
    "/": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
running = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in STATIC:
            self.send_error(404)
            return
        name, content_type = STATIC[self.path]
        body = (WEB_DIR / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # A pesquisa volta como NDJSON: um evento por linha, enviado assim que acontece.
    def do_POST(self):
        if self.path != "/api/pesquisa":
            self.send_error(404)
            return
        # Exigir JSON e o Host certo impede que outro site aberto no navegador dispare uma pesquisa aqui.
        if self.headers.get("Host") not in ALLOWED_HOSTS or self.headers.get_content_type() != "application/json":
            self.reply_error(403, "Pedido recusado.")
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            request = body["pedido"].strip()
        except (ValueError, KeyError, AttributeError):
            self.reply_error(400, "Mande o pedido em JSON, no campo pedido.")
            return
        if not request:
            self.reply_error(400, "O pedido está vazio.")
            return
        if not running.acquire(blocking=False):
            self.reply_error(409, "Já tem uma pesquisa rodando.")
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            mode = "sequencial" if body.get("sequencial") else "paralelo"
            asyncio.run(self.stream(request, mode, bool(body.get("simularTimeout"))))
        finally:
            running.release()

    async def stream(self, request, mode, simulate_timeout):
        task = asyncio.current_task()
        page_open = True

        def emit(event):
            nonlocal page_open
            print_event(event)
            if not page_open:
                return
            try:
                self.wfile.write(json.dumps(event, ensure_ascii=False).encode() + b"\n")
            except OSError:
                # A aba fechou: cancelar a pesquisa encerra o Claude Code e para de gastar.
                # Uma vez só: um segundo cancel interromperia o SDK no meio do encerramento.
                page_open = False
                task.cancel()

        try:
            await research(request, emit, mode, simulate_timeout)
        except asyncio.CancelledError:
            print("\nPesquisa interrompida: a página fechou.")
        except Exception as error:
            emit({"type": "error", "message": str(error)})
            raise

    def reply_error(self, status, message):
        body = json.dumps({"error": message}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Tela em {url} (Ctrl+C para sair)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
