import http.server
import socketserver
import os
import signal
import sys
import time

PORT = 4000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

os.chdir(BASE_DIR)


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header(
            "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"
        )
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        sys.stderr.write("[serve] ERROR: %s\n" % (format % args))
        sys.stderr.flush()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def shutdown_handler(signum, frame):
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

while True:
    try:
        with ReusableTCPServer(("0.0.0.0", PORT), NoCacheHandler) as httpd:
            print(f"[serve] Serving on http://0.0.0.0:{PORT}", flush=True)
            httpd.serve_forever()
    except OSError:
        time.sleep(2)
    except Exception:
        time.sleep(2)
