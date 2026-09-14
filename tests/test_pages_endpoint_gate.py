#!/usr/bin/env python3
import http.server
import os
import pathlib
import subprocess
import tempfile
import threading
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
ORACLE = REPO / "scripts" / "verify_pages_endpoint.sh"
EXPECTED = "<title>सार्वजनिक अध्ययन महा-कॉकपिट | Universal Sovereign Study Lake</title>"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class PagesEndpointGateCourt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        handler = lambda *a, **kw: QuietHandler(*a, directory=self.tmp.name, **kw)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/index.html"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def run_oracle(self, html):
        (self.root / "index.html").write_text(html, encoding="utf-8")
        env = os.environ.copy()
        env["PAGES_ENDPOINT_URL"] = self.url
        return subprocess.run(
            ["bash", str(ORACLE)],
            cwd=REPO,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_known_good_identity_passes(self):
        result = self.run_oracle(f"<!doctype html><html><head>{EXPECTED}</head><body>ok</body></html>")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PUBLIC_ENDPOINT_VERIFIED", result.stdout)

    def test_http_200_wrong_content_is_red(self):
        result = self.run_oracle("<!doctype html><html><head><title>wrong</title></head><body>ok</body></html>")
        self.assertNotEqual(result.returncode, 0)

    def test_unsafe_physical_verification_marker_is_red(self):
        result = self.run_oracle(f"<!doctype html><html><head>{EXPECTED}</head><body>PASSED_PHYSICAL_VERIFICATION</body></html>")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale unsafe verification marker", result.stderr)


if __name__ == "__main__":
    unittest.main()
